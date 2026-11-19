"""Normalização conservadora e consolidação incremental de Parquet.

NÃO agrega ou soma arquivos de consultas diferentes: são visões estatísticas
que podem se sobrepor. O consolidado é a união *rastreável* dessas visões.
"""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Iterator

from .model import Job, months
from .storage import Catalog

# Colunas geográficas históricas variam conforme a versão do relatório.
# Não pressupomos que os nomes alternativos tenham sempre o mesmo significado:
# mantemos as dimensões originais em dimensoes_json.
DIMENSIONS = {"uf", "sg_uf", "co_uf", "ibge_uf", "co_uf_ibge", "codigo_uf",
              "ibge", "co_municipio_ibge", "codigo_municipio", "co_municipio",
              "municipio", "município", "nome_municipio", "nm_municipio",
              "regiao", "região", "macrorregiao", "macrorregião", "cnes", "ine",
              "equipe", "equipe iné", "estabelecimento", "profissional", "cbo",
              "unidade federativa", "municipio ibge"}
UF_ALIASES = ("uf", "sg_uf", "co_uf", "ibge_uf", "co_uf_ibge", "codigo_uf", "unidade federativa")
IBGE_ALIASES = ("ibge", "co_municipio_ibge", "codigo_municipio", "co_municipio", "municipio ibge")
MUNICIPIO_ALIASES = ("municipio", "município", "nome_municipio", "nm_municipio")


def _first_dimension(dimensions: dict[str, str], names: tuple[str, ...]) -> str | None:
    return next((dimensions[k] for k in names if k in dimensions and dimensions[k].strip()), None)


def _uf_standard(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    # Equivalências inequívocas para MG; demais códigos são preservados.
    return "MG" if cleaned in {"31", "310000", "MG"} else cleaned



def decode_csv(content: bytes) -> str:
    for enc in ("utf-8-sig", "iso-8859-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV sem codificação suportada")


def table_rows(content: bytes) -> Iterator[tuple[list[str], list[str], int]]:
    """Lê bytes de uma única consulta; arquivos ZIP usam table_rows_reader."""
    yield from table_rows_reader(io.StringIO(decode_csv(content), newline=""))


def table_rows_reader(text_file) -> Iterator[tuple[list[str], list[str], int]]:
    """Identifica o cabeçalho real após metadados e produz registros originais.

    dimension_count é estritamente baseado em nomes identificáveis; quando
    o portal muda o esquema, exige ajuste explícito, não inventa uma métrica.
    """
    reader = csv.reader(text_file, delimiter=";")
    header = None
    n_dims = 0
    for row in reader:
        if not row or not any(v.strip() for v in row):
            continue
        if header is None:
            cleaned = [x.lstrip("\ufeff").strip() for x in row]
            if cleaned[0].casefold() not in DIMENSIONS or len(cleaned) < 2:
                continue
            while cleaned and not cleaned[-1]:
                cleaned.pop()
            for name in cleaned:
                if name.casefold() in DIMENSIONS:
                    n_dims += 1
                else:
                    break
            if n_dims == 0 or len(cleaned) == n_dims:
                raise ValueError("Cabeçalho sem dimensão ou sem medida; verifique o CSV original")
            header = cleaned
            continue
        while len(row) > len(header) and not row[-1].strip():
            row.pop()
        if len(row) != len(header):
            raise ValueError(f"Linha CSV com {len(row)} campos; esperados {len(header)}")
        yield header, row, n_dims
    if header is None:
        raise ValueError("Cabeçalho de tabela reconhecível não encontrado no CSV SISAB")


def br_number(value: str) -> int | None:
    v = value.strip().replace("\u00a0", "")
    if not v or v in {"-", "...", "*"}:
        return None
    # SISAB usa quantidades inteiras com ponto de milhar.
    if not v.lstrip("-").replace(".", "").isdigit():
        raise ValueError(f"Quantidade não inteira no CSV: {value!r}")
    return int(v.replace(".", ""))


def normalizar(content: bytes, job: Job) -> Iterator[dict]:
    yield from normalizar_linhas(table_rows(content), job)


def normalizar_linhas(entries: Iterator[tuple[list[str], list[str], int]], job: Job) -> Iterator[dict]:
    for cols, cells, n_dims in entries:
        dims = dict(zip(cols[:n_dims], (x.strip() for x in cells[:n_dims])))
        lower = {k.casefold(): v for k, v in dims.items()}
        for label, val in zip(cols[n_dims:], cells[n_dims:]):
            if not label.strip():
                continue
            number = br_number(val)
            if number is None:
                # Campo vazio ou suprimido, nunca supor zero.
                continue
            yield {
                "consulta_id": job.key,
                "competencia": job.competencia,
                "ano": job.ano,
                "relatorio": job.report,
                "fonte_url": job.url,
                "linha": job.linha_label,
                "coluna": job.coluna_label,
                "faixa_etaria": job.faixa_etaria or None,
                "sexo": job.sexo or None,
                "uf": _uf_standard(_first_dimension(lower, UF_ALIASES)),
                "ibge": _first_dimension(lower, IBGE_ALIASES),
                "municipio": _first_dimension(lower, MUNICIPIO_ALIASES),
                "categoria": label.strip(),
                "valor": number,
                "dimensoes_json": json.dumps(dims, ensure_ascii=False, sort_keys=True),
            }


def _arrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("PyArrow indisponível. Instale com 'pip install -e .' ") from exc
    return pa, pq


def schema():
    pa, _ = _arrow()
    return pa.schema([
        ("consulta_id", pa.string()),
        ("competencia", pa.string()),
        ("ano", pa.int32()),
        ("relatorio", pa.string()),
        ("fonte_url", pa.string()),
        ("linha", pa.string()),
        ("coluna", pa.string()),
        ("faixa_etaria", pa.string()),
        ("sexo", pa.string()),
        ("uf", pa.string()),
        ("ibge", pa.string()),
        ("municipio", pa.string()),
        ("categoria", pa.string()),
        ("valor", pa.int64()),
        ("dimensoes_json", pa.string()),
    ])


def write_monthly(path: Path, content: bytes, job: Job, batch_size: int = 25000) -> int:
    return _write_monthly_rows(path, normalizar(content, job), batch_size)


def write_monthly_from_zip(path: Path, raw_zip: Path, job: Job, batch_size: int = 25000,
                           progress_callback=None) -> int:
    """Converte ZIP diretamente em lotes, sem descompactar o CSV inteiro na RAM."""
    with zipfile.ZipFile(raw_zip) as z:
        with z.open("resposta_original.csv") as compressed:
            sample = compressed.peek(65536)[:65536]
            try:
                sample.decode("utf-8-sig")
                encoding = "utf-8-sig"
            except UnicodeDecodeError:
                encoding = "iso-8859-1"
            with io.TextIOWrapper(compressed, encoding=encoding, newline="") as text:
                rows = normalizar_linhas(table_rows_reader(text), job)
                return _write_monthly_rows(path, rows, batch_size, progress_callback)


def _write_monthly_rows(path: Path, rows: Iterator[dict], batch_size: int = 25000,
                        progress_callback=None) -> int:
    pa, pq = _arrow()
    sc = schema()
    path.parent.mkdir(parents=True, exist_ok=True)
    file_name = None
    writer = None
    count = 0
    try:
        with tempfile.NamedTemporaryFile(suffix=".parquet", prefix=".tmp-", dir=path.parent, delete=False) as f:
            file_name = f.name
        writer = pq.ParquetWriter(file_name, sc, compression="zstd")
        batch = []
        for item in rows:
            batch.append(item)
            if len(batch) >= batch_size:
                writer.write_table(pa.Table.from_pylist(batch, schema=sc))
                count += len(batch)
                if progress_callback is not None:
                    progress_callback(count)
                batch.clear()
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=sc))
            count += len(batch)
            if progress_callback is not None:
                progress_callback(count)
        if count == 0:
            raise ValueError("CSV sem medidas numéricas; não marcar como download concluído")
        writer.close()
        writer = None
        os.replace(file_name, path)
        return count
    finally:
        if writer is not None:
            writer.close()
        if file_name and os.path.exists(file_name):
            os.unlink(file_name)


# Campos essenciais para a rastreabilidade; outros podem ser completados com null
# quando versões antigas do Parquet tinham menos dimensões.
REQUIRED_FIELDS = {"consulta_id", "competencia", "ano", "relatorio", "linha", "coluna", "categoria", "valor"}


def _align_table(table, target_schema):
    """Alinha por nome e converte tipos de forma segura, sem inferência automática."""
    import pyarrow as pa
    import pyarrow.compute as pc

    absent = REQUIRED_FIELDS.difference(table.schema.names)
    if absent:
        raise ValueError(f"Parquet sem campos essenciais: {', '.join(sorted(absent))}")
    columns = []
    for field in target_schema:
        if field.name in table.schema.names:
            columns.append(pc.cast(table[field.name], field.type, safe=True))
        else:
            columns.append(pa.nulls(table.num_rows, type=field.type))
    return pa.Table.from_arrays(columns, schema=target_schema)


def _concatenate(paths: list[Path], target: Path, *, start: str | None = None,
                 end: str | None = None) -> int:
    """Concatena por lotes com esquema canônico e gravação atômica em disco."""
    pa, pq = _arrow()
    sc = schema()
    target.parent.mkdir(parents=True, exist_ok=True)
    filename = None
    writer = None
    total = 0
    try:
        with tempfile.NamedTemporaryFile(suffix=".parquet", prefix=".tmp-", dir=target.parent, delete=False) as f:
            filename = f.name
        writer = pq.ParquetWriter(filename, sc, compression="zstd")
        for file in sorted(paths):
            if not file.is_file():
                raise FileNotFoundError(f"Parquet ausente: {file}")
            pf = pq.ParquetFile(file)
            for batch in pf.iter_batches(batch_size=25000):
                table = _align_table(pa.Table.from_batches([batch]), sc)
                if start or end:
                    import pyarrow.compute as pc
                    mask = None
                    if start:
                        mask = pc.greater_equal(table["competencia"], start)
                    if end:
                        upper = pc.less_equal(table["competencia"], end)
                        mask = pc.and_(mask, upper) if mask is not None else upper
                    if mask is not None:
                        table = table.filter(mask)
                if table.num_rows:
                    writer.write_table(table)
                    total += table.num_rows
        writer.close()
        writer = None
        os.replace(filename, target)
        return total
    finally:
        if writer is not None:
            writer.close()
        if filename and os.path.exists(filename):
            os.unlink(filename)


def consolidate(catalog: Catalog, start: str, end: str,
                allow_partial: bool = False) -> dict:
    period = months(start, end)
    relevant = catalog.rows(start, end)
    if not relevant:
        raise ValueError("Nenhuma consulta cadastrada nesse período; execute download primeiro.")
    pending = [r for r in relevant if r["status"] not in ("ok", "sem_dados")]
    if pending and not allow_partial:
        raise ValueError(f"Consolidação bloqueada: {len(pending)} consultas pendentes/com erro. "
                         "Use --allow-partial apenas se quiser uma série incompleta.")
    annual_paths = []
    annual = {}
    for year in sorted({int(m[:4]) for m in period}):
        # O anual reúne TODOS os arquivos válidos conhecidos para aquele ano.
        all_year = [r for r in catalog.rows(f"{year}01", f"{year}12") if r["status"] == "ok"]
        files = [Path(r["parquet_path"]) for r in all_year]
        if not files:
            annual[str(year)] = {"status": "sem_dados", "linhas": 0}
            continue
        target = catalog.root / "consolidado" / "anual" / f"sisab_{year}.parquet"
        count = _concatenate(files, target)
        annual[str(year)] = {"arquivo": str(target), "linhas": count, "consultas": len(files)}
        annual_paths.append(target)
    if not annual_paths:
        raise ValueError("Nenhum Parquet mensal concluído no período.")
    target_series = catalog.root / "consolidado" / "serie" / f"sisab_{start}_{end}.parquet"
    series_count = _concatenate(annual_paths, target_series, start=start, end=end)
    manifest = {
        "periodo": {"inicio": start, "fim": end},
        "parcial": bool(pending),
        "avisos": ["São contagens agregadas e potencialmente sobrepostas; NÃO some todas as linhas indiscriminadamente.",
                   "CID e CIAP são categorias retornadas pelo relatório, não microdados individuais."],
        "consultas": catalog.summary(start, end),
        "anuais": annual,
        "serie": {"arquivo": str(target_series), "linhas": series_count},
    }
    (target_series.parent / f"sisab_{start}_{end}.manifesto.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
