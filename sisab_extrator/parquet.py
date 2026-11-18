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
from pathlib import Path
from typing import Iterator

from .model import Job, months
from .storage import Catalog

DIMENSIONS = {"uf", "ibge", "municipio", "município", "regiao", "região", "macrorregiao",
              "macrorregião", "cnes", "ine", "equipe", "equipe iné", "estabelecimento",
              "profissional", "cbo", "unidade federativa", "municipio ibge"}


def decode_csv(content: bytes) -> str:
    for enc in ("utf-8-sig", "iso-8859-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV sem codificação suportada")


def table_rows(content: bytes) -> Iterator[tuple[list[str], list[str], int]]:
    """Identifica o cabeçalho real após metadados e produz registros originais.

    dimension_count é estritamente baseado em nomes identificáveis; quando
    o portal muda o esquema, exige ajuste explícito, não inventa uma métrica.
    """
    reader = csv.reader(io.StringIO(decode_csv(content), newline=""), delimiter=";")
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
    for cols, cells, n_dims in table_rows(content):
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
                "uf": lower.get("uf"),
                "ibge": lower.get("ibge"),
                "municipio": lower.get("municipio", lower.get("município")),
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
        for item in normalizar(content, job):
            batch.append(item)
            if len(batch) >= batch_size:
                writer.write_table(pa.Table.from_pylist(batch, schema=sc))
                count += len(batch)
                batch.clear()
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=sc))
            count += len(batch)
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


def _concatenate(paths: list[Path], target: Path, *, start: str | None = None,
                 end: str | None = None) -> int:
    """Concatena em lotes, sem carregar o conjunto inteiro na memória."""
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
            if not pf.schema_arrow.equals(sc, check_metadata=False):
                raise ValueError(f"Esquema inconsistente em {file}")
            for batch in pf.iter_batches(batch_size=50000):
                if start or end:
                    table = pa.Table.from_batches([batch], schema=sc)
                    import pyarrow.compute as pc
                    mask = None
                    if start:
                        mask = pc.greater_equal(table["competencia"], start)
                    if end:
                        upper = pc.less_equal(table["competencia"], end)
                        mask = pc.and_(mask, upper) if mask is not None else upper
                    if mask is not None:
                        table = table.filter(mask)
                else:
                    table = pa.Table.from_batches([batch], schema=sc)
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
