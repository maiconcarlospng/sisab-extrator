"""CLI: inspecionar, planejar, baixar, consolidar e verificar."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Iterator

from .model import AGE_GROUPS, REPORT_URLS, SEXES, Job, months, parse_month
from .portal import Client, NoData, Page, PortalError, _field_identifier, _all_ciap_values
from .storage import Catalog, parquet_path, raw_path, save_raw_zip

LOG = logging.getLogger("sisab_extrator")


@dataclass
class Prepared:
    name: str
    client: Client
    page: Page
    competencias: list[str]
    linhas: list[tuple[str, str]]
    colunas: list[tuple[str, str]]
    idades: list[tuple[str, int, int, str]]
    sexos: list[tuple[str, str]]
    tipos_producao: list[tuple[str, str]]
    ciap_cid: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return (len(self.competencias) * len(self.linhas) * len(self.colunas)
                * len(self.idades) * len(self.sexos) * len(self.tipos_producao))

    def jobs(self) -> Iterator[Job]:
        for comp, linha, coluna, age, sexo, producao in product(
            self.competencias, self.linhas, self.colunas, self.idades,
            self.sexos, self.tipos_producao,
        ):
            yield Job(self.name, self.page.report_url, comp,
                      linha[0], linha[1], coluna[0], coluna[1],
                      age[0], age[1], age[2], age[3], sexo[0], sexo[1],
                      producao[0], producao[1], self.ciap_cid)


def selected_reports(args) -> dict[str, str]:
    if args.report_url:
        from .portal import check_url
        return {"custom": check_url(args.report_url)}
    return REPORT_URLS if args.report == "all" else {args.report: REPORT_URLS[args.report]}


def make_client(url: str, args) -> Client:
    return Client(url, args.delay, args.timeout, args.retries, args.backoff,
                  diagnostics_dir=args.data_dir / "inspecao")


def prepare(name: str, client: Client, page: Page, args) -> Prepared:
    available = sorted(v for v in page.competencia.options if len(v) == 6 and v.isdigit())
    if not available:
        raise PortalError(f"{name}: o relatório não ofereceu competências mensais válidas")
    first = available[0] if args.start == "auto" else args.start
    last = available[-1] if args.end == "auto" else args.end
    requested = months(first, last)
    comps = [v for v in requested if v in page.competencia.options]
    missing = len(requested) - len(comps)
    if missing:
        LOG.warning("%s: %d competências solicitadas indisponíveis e excluídas do plano", name, missing)
    if not comps:
        raise PortalError(f"{name}: nenhuma competência disponível para {first}-{last}")
    linhas = page.linha.choose(args.lines)
    colunas = page.coluna.choose(args.columns)
    if args.ages == "all":
        ages = AGE_GROUPS
    elif args.ages == "none":
        ages = [("", 0, 0, "")]
    else:
        ages = [a for a in AGE_GROUPS if args.ages.casefold() in a[0].casefold()]
        if len(ages) != 1:
            raise ValueError("Faixa etária inválida ou ambígua; use all, none ou nome completo")
    sexes = SEXES if args.sexes == "both" else [("", "")] if args.sexes == "none" else [
        s for s in SEXES if s[0].casefold() == args.sexes.casefold()
    ]
    if not sexes:
        raise ValueError("Sexo inválido")
    requires_production_filter = any(
        "tipodeproducao" not in _field_identifier(row_label)
        and "tipodeproducao" not in _field_identifier(col_label)
        for _, row_label in linhas for _, col_label in colunas
    )
    if args.production_type == "none":
        if page.tipo_producao is not None and requires_production_filter:
            choices = [label for value, label in page.tipo_producao.options.items()
                       if value]
            raise ValueError(
                f"{name}: o SISAB exige Tipo de Produção para esta combinação de "
                "linha/coluna. Informe tipo_producao em sisab_planejar()/sisab_baixar(). "
                f"Escolha uma das opções: {choices!r}. "
                "Não escolhemos automaticamente para evitar mudar o recorte da pesquisa."
            )
        production_types = [("", "")]
    else:
        if page.tipo_producao is None:
            raise PortalError(
                f"{name}: filtro Tipo de Produção não encontrado neste relatório."
            )
        production_types = page.tipo_producao.choose(args.production_type)
        if not production_types:
            raise ValueError("Nenhuma opção de Tipo de Produção disponível.")
    # CIAP/CID 'all' seleciona códigos/grupos reais do controle do portal
    # em uma consulta, sem multiplicar o plano pelo número de códigos.
    ciap_mode = getattr(args, "ciap_cid", "none")
    if ciap_mode not in ("none", "all", "auto"):
        raise ValueError("ciap_cid deve ser 'none', 'all' ou 'auto'.")
    has_ciap_dimension = any(
        value == "CID" or "ciapcid" in _field_identifier(label)
        for value, label in linhas + colunas
    )
    requires_ciap = ciap_mode == "all" or (
        ciap_mode == "auto" and has_ciap_dimension
    )
    ciap_cid = _all_ciap_values(page.ciap_cid) if requires_ciap else ()
    return Prepared(name, client, page, comps, linhas, colunas, ages, sexes,
                    production_types, ciap_cid)


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report", choices=["federal", "municipal", "all"], default="all")
    parser.add_argument("--report-url", help="Relatório público XLS/HTML .xhtml do domínio sisab.saude.gov.br")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--delay", type=float, default=2.0, help="Segundos entre requisições (padrão 2)")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--backoff", type=float, default=5.0)


def add_filters(parser):
    parser.add_argument("--start", default="auto", help="Primeira competência AAAAMM, ou auto")
    parser.add_argument("--end", default="auto", help="Última competência AAAAMM, ou auto")
    parser.add_argument("--lines", default="all", help="Rótulo/valor da linha ou all")
    parser.add_argument("--columns", default="all", help='Rótulo/valor da coluna, ex.: "CIAP/CID", ou all')
    parser.add_argument("--ages", default="all", help="all, none ou nome exato da faixa")
    parser.add_argument("--sexes", default="both", choices=["both", "none", "Masculino", "Feminino"])
    parser.add_argument("--production-type", default="none",
                        help="Filtro Tipo de Produção: rótulo/valor oferecido pelo SISAB, all ou none")
    parser.add_argument("--ciap-cid", choices=("none", "auto", "all"), default="auto",
                        help="auto: Todos ao escolher CIAP/CID na linha ou coluna; "
                             "all: Todos explicitamente; none: sem seleção. "
                             "Se a lista não estiver no HTML, interrompe sem enviar.")
    parser.add_argument("--allow-large-plan", action="store_true", help="Aceita mais de 10 mil consultas")


def cmd_probe(args) -> int:
    for name, url in selected_reports(args).items():
        with make_client(url, args) as client:
            page = client.open()
            path = args.data_dir / "inspecao" / f"{name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(page.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"{name}: {path} | {len(page.competencia.options)} competências | "
                  f"{len(page.linha.options)} linhas | {len(page.coluna.options)} colunas")
            if page.tipo_producao:
                options = [(value, label) for value, label in
                           page.tipo_producao.options.items() if value]
                print("  Tipo de Produção disponível: " +
                      ", ".join(f"{label} (valor {value})" for value, label in options))
            if page.ciap_cid:
                option_count = sum(bool(v) for v in page.ciap_cid.options)
                tipo = "selecao multipla" if page.ciap_cid.multiselect else "selecao unica"
                print(f"  Filtro CIAP/CID: {option_count} opcoes no HTML; "
                      f"campo {page.ciap_cid.name} ({tipo})")
            else:
                print("  Filtro CIAP/CID: sem opções estáticas identificáveis; "
                      "pode exigir interação AJAX.")
    return 0


def prepared_reports(args):
    prepared = []
    try:
        for name, url in selected_reports(args).items():
            client = make_client(url, args)
            try:
                page = client.open()
                p = prepare(name, client, page, args)
                prepared.append(p)
                print(f"[{name}] {len(p.competencias)} competências × {len(p.linhas)} linhas × "
                      f"{len(p.colunas)} colunas × {len(p.idades)} idades × "
                      f"{len(p.sexos)} sexos × {len(p.tipos_producao)} tipos de produção"
                      f" = {p.count} consultas")
            except Exception:
                client.close()
                raise
        return prepared
    except Exception:
        for p in prepared:
            p.client.close()
        raise


def guard_large(prepared, args) -> int:
    count = sum(p.count for p in prepared)
    if count > 10_000 and not args.allow_large_plan:
        raise ValueError(f"Plano contém {count:,} consultas. Inspecione o plano e repita "
                         "com --allow-large-plan para autorizar essa carga.")
    return count


def cmd_plan(args) -> int:
    prepared = prepared_reports(args)
    try:
        count = guard_large(prepared, args)
        path = args.data_dir / "planos" / "plano.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for p in prepared:
                for j in p.jobs():
                    f.write(json.dumps(j.to_dict(), ensure_ascii=False) + "\n")
        print(f"Plano gravado: {path} ({count} consultas, sem realizar download)")
        return 0
    finally:
        for p in prepared:
            p.client.close()


def _log_download_progress(done: int, total: int, success: int, skipped: int,
                           failures: int, started: float) -> None:
    """Progresso de consultas concluídas, não dos bytes no servidor."""
    pct = 100.0 * done / total if total else 100.0
    LOG.info(
        "PROGRESSO: %d/%d consultas finalizadas (%.1f%%) | novas: %d | "
        "reutilizadas/sem dados: %d | erros: %d | tempo decorrido: %.1fs",
        done, total, pct, success, skipped, failures,
        time.monotonic() - started,
    )


def _log_download_step(index: int, total: int, step: int, message: str) -> None:
    LOG.info("Consulta %d/%d | ETAPA %d/5 | %s", index, total, step, message)


def cmd_download(args) -> int:
    started = time.monotonic()
    LOG.info("FASE 1/4 | Abrindo relatório do SISAB e identificando filtros disponíveis...")
    prepared = prepared_reports(args)
    catalog = Catalog(args.data_dir)
    failures = 0
    success = 0
    skipped = 0
    try:
        count = guard_large(prepared, args)
        LOG.info("FASE 2/4 | Plano validado: %d consulta(s). Registrando no catálogo...", count)
        for p in prepared:
            catalog.add_jobs(p.jobs())
        LOG.info("FASE 3/4 | Iniciando download e conversão em Parquet...")
        completed = 0
        for p in prepared:
            for job in p.jobs():
                completed += 1
                job_started = time.monotonic()
                state = catalog.get(job.key)
                destination = parquet_path(args.data_dir, job)
                source = raw_path(args.data_dir, job)
                if not args.force and state and state["status"] == "sem_dados":
                    skipped += 1
                    LOG.info("Consulta %d/%d | sem dados já registrado; ignorando", completed, count)
                    _log_download_progress(completed, count, success, skipped, failures, started)
                    continue
                if (not args.force and state and state["status"] == "ok"
                        and destination.exists() and source.exists()):
                    skipped += 1
                    LOG.info("Consulta %d/%d | arquivos já disponíveis; reutilizando", completed, count)
                    _log_download_progress(completed, count, success, skipped, failures, started)
                    continue
                stage = 1
                try:
                    _log_download_step(
                        completed, count, stage,
                        f"{p.name} | mês {job.competencia} | linha {job.linha_label} | "
                        f"coluna {job.coluna_label} | tipo de produção "
                        f"{job.tipo_producao_label or 'na dimensão/sem filtro'} | "
                        f"idade {job.faixa_etaria or 'sem filtro'} | "
                        f"sexo {job.sexo or 'sem filtro'}",
                    )
                    if not source.exists() or args.force:
                        stage = 2
                        _log_download_step(
                            completed, count, stage,
                            "Solicitando CSV ao SISAB; sem percentual enquanto o portal processa...",
                        )
                        content = p.client.download(job)
                        stage = 3
                        _log_download_step(
                            completed, count, stage,
                            f"CSV recebido ({len(content):,} bytes); salvando ZIP original...",
                        )
                        save_raw_zip(source, content, job)
                        del content
                        LOG.info("Arquivo original salvo: %s", source)
                    else:
                        stage = 3
                        _log_download_step(completed, count, stage,
                                           "CSV já salvo em ZIP; download dispensado")
                    stage = 4
                    _log_download_step(completed, count, stage,
                                       "Lendo CSV e convertendo para Parquet em lotes...")

                    def report_rows(rows: int) -> None:
                        LOG.info("Consulta %d/%d | ETAPA 4/5 | %d linhas convertidas até agora",
                                 completed, count, rows)

                    from .parquet import write_monthly_from_zip
                    nr = write_monthly_from_zip(destination, source, job,
                                                progress_callback=report_rows)
                    catalog.update(job.key, "ok", raw=str(source),
                                   parquet=str(destination), linhas=nr)
                    stage = 5
                    _log_download_step(
                        completed, count, stage,
                        f"Concluído: {nr:,} registros em {destination} "
                        f"({time.monotonic() - job_started:.1f}s)",
                    )
                    success += 1
                except NoData:
                    catalog.update(job.key, "sem_dados", linhas=0)
                    skipped += 1
                    LOG.info("Consulta %d/%d | SISAB informou ausência de dados",
                             completed, count)
                except Exception as exc:
                    catalog.update(job.key, "erro",
                                   raw=str(source) if source.exists() else None,
                                   erro=f"{type(exc).__name__}: {exc}")
                    failures += 1
                    LOG.error(
                        "Consulta %d/%d | FALHOU na etapa %d/5 após %.1fs | %s: %s",
                        completed, count, stage, time.monotonic() - job_started,
                        type(exc).__name__, exc,
                    )
                _log_download_progress(completed, count, success, skipped,
                                       failures, started)
        LOG.info("FASE 3/4 finalizada | novos: %d | reutilizados/sem dados: %d | erros: %d",
                 success, skipped, failures)
        if failures:
            LOG.error("FASE 4/4 | Consolidação não iniciada: existem %d consulta(s) com erro.",
                      failures)
            LOG.info("Use 'sisab_status()' para revisar o catálogo; o diagnóstico fica "
                     "na pasta data/inspecao quando o portal devolve HTML.")
            return 2
        if not args.no_consolidate:
            LOG.info("FASE 4/4 | Consolidando arquivos anuais e série histórica...")
            from .parquet import consolidate
            actual_start = min(c for p in prepared for c in p.competencias)
            actual_end = max(c for p in prepared for c in p.competencias)
            manifest = consolidate(catalog, actual_start, actual_end)
            LOG.info("Série histórica salva em: %s", manifest["serie"]["arquivo"])
        else:
            LOG.info("FASE 4/4 | Consolidação desativada (consolidar = FALSE).")
        LOG.info("FINALIZADO | Tempo total: %.1fs", time.monotonic() - started)
        return 0
    finally:
        catalog.close()
        for p in prepared:
            p.client.close()

def cmd_consolidate(args) -> int:
    parse_month(args.start)
    parse_month(args.end)
    catalog = Catalog(args.data_dir)
    try:
        from .parquet import consolidate
        manifest = consolidate(catalog, args.start, args.end, allow_partial=args.allow_partial)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    finally:
        catalog.close()


def cmd_status(args) -> int:
    c = Catalog(args.data_dir)
    try:
        print(json.dumps(c.summary(args.start, args.end), ensure_ascii=False, indent=2))
        errors = [r for r in c.rows(args.start, args.end) if r["status"] == "erro"]
        for row in errors[:25]:
            print(f"ERRO {row['competencia']} {row['id']}: {row['erro']}")
        return 0
    finally:
        c.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sisab-extrator",
        description="Extrai relatórios agregados públicos SISAB e gera Parquet anual + série histórica.")
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("probe", help="Descobrir opções reais do formulário; não faz POST")
    common(probe)
    probe.set_defaults(fn=cmd_probe)
    plan = commands.add_parser("plan", help="Criar manifesto de todos os downloads previstos")
    common(plan)
    add_filters(plan)
    plan.set_defaults(fn=cmd_plan)
    download = commands.add_parser("download", help="Baixar, normalizar e consolidar")
    common(download)
    add_filters(download)
    download.add_argument("--force", action="store_true", help="Ignora cache e refaz downloads")
    download.add_argument("--no-consolidate", action="store_true")
    download.set_defaults(fn=cmd_download)
    consolidate = commands.add_parser("consolidate", help="Consolidar anuais e depois a série")
    consolidate.add_argument("--start", required=True)
    consolidate.add_argument("--end", required=True)
    consolidate.add_argument("--data-dir", type=Path, default=Path("data"))
    consolidate.add_argument("--allow-partial", action="store_true")
    consolidate.set_defaults(fn=cmd_consolidate)
    status = commands.add_parser("status", help="Consultar andamento e erros")
    status.add_argument("--data-dir", type=Path, default=Path("data"))
    status.add_argument("--start")
    status.add_argument("--end")
    status.set_defaults(fn=cmd_status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        return args.fn(args)
    except (PortalError, ValueError, OSError, RuntimeError) as exc:
        LOG.error("%s: %s", type(exc).__name__, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
