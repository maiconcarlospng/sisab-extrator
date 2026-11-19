"""CLI: inspecionar, planejar, baixar, consolidar e verificar."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Iterator

from .model import AGE_GROUPS, REPORT_URLS, SEXES, Job, months, parse_month
from .portal import Client, NoData, Page, PortalError
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

    @property
    def count(self) -> int:
        return len(self.competencias) * len(self.linhas) * len(self.colunas) * len(self.idades) * len(self.sexos)

    def jobs(self) -> Iterator[Job]:
        for comp, linha, coluna, age, sexo in product(
            self.competencias, self.linhas, self.colunas, self.idades, self.sexos
        ):
            yield Job(self.name, self.page.report_url, comp,
                      linha[0], linha[1], coluna[0], coluna[1],
                      age[0], age[1], age[2], age[3], sexo[0], sexo[1])


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
    return Prepared(name, client, page, comps, linhas, colunas, ages, sexes)


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
                      f"{len(p.sexos)} sexos = {p.count} consultas")
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


def cmd_download(args) -> int:
    prepared = prepared_reports(args)
    catalog = Catalog(args.data_dir)
    failures = 0
    success = 0
    skipped = 0
    try:
        count = guard_large(prepared, args)
        LOG.info("Preparando %d consulta(s) do SISAB", count)
        for p in prepared:
            catalog.add_jobs(p.jobs())
        completed = 0
        for p in prepared:
            for job in p.jobs():
                completed += 1
                state = catalog.get(job.key)
                destination = parquet_path(args.data_dir, job)
                source = raw_path(args.data_dir, job)
                if not args.force and state and state["status"] == "sem_dados":
                    skipped += 1
                    continue
                if (not args.force and state and state["status"] == "ok"
                        and destination.exists() and source.exists()):
                    skipped += 1
                    continue
                try:
                    LOG.info("Consulta %d/%d | %s | competência %s | linha %s | coluna %s",
                             completed, count, p.name, job.competencia,
                             job.linha_label, job.coluna_label)
                    if not source.exists() or args.force:
                        LOG.info("Aguardando exportação CSV do portal...")
                        content = p.client.download(job)
                        LOG.info("CSV recebido: %d bytes. Salvando arquivo original...", len(content))
                        save_raw_zip(source, content, job)
                        del content
                    else:
                        LOG.info("Usando CSV já salvo, sem novo download")
                    LOG.info("Convertendo CSV para Parquet...")
                    from .parquet import write_monthly_from_zip
                    nr = write_monthly_from_zip(destination, source, job)
                    catalog.update(job.key, "ok", raw=str(source), parquet=str(destination), linhas=nr)
                    LOG.info("Consulta %d/%d concluída | %d registros Parquet",
                             completed, count, nr)
                    success += 1
                except NoData:
                    catalog.update(job.key, "sem_dados", linhas=0)
                    skipped += 1
                except Exception as exc:
                    catalog.update(job.key, "erro", raw=str(source) if source.exists() else None,
                                   erro=f"{type(exc).__name__}: {exc}")
                    failures += 1
                    LOG.error("Falha na consulta %s (%s/%s): %s", job.key, completed, count, exc)
                if completed % 10 == 0 or completed == count:
                    print(f"Progresso {completed}/{count} | novos {success} | "
                          f"ignorados/sem dados {skipped} | erros {failures}", flush=True)
        print(f"Downloads: {success} novos, {skipped} reutilizados/sem dados, {failures} erros")
        if failures:
            print("A consolidação automática será bloqueada até corrigir/repetir as consultas com erro.")
            return 2
        if not args.no_consolidate:
            LOG.info("Iniciando consolidação anual e da série histórica...")
            from .parquet import consolidate
            actual_start = min(c for p in prepared for c in p.competencias)
            actual_end = max(c for p in prepared for c in p.competencias)
            manifest = consolidate(catalog, actual_start, actual_end)
            print("Série histórica consolidada:", manifest["serie"]["arquivo"])
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
