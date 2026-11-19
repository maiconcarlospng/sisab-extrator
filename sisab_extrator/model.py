"""Contratos de consulta e competências mensais."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

REPORT_URLS = {
    "federal": "https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/saude/RelSauProducao.xhtml",
    "municipal": "https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/municipio/saude/RelSauProducao.xhtml",
}

# Faixas conforme o scraper de referência. Uso opcional; a possibilidade de cruzar
# com todas as colunas/linhas depende do portal.
AGE_GROUPS = [
    ("Menor de 1 ano", 0, 364, "dias"),
    ("De 1 a 4 anos", 1, 4, "ano"),
    *[(f"De {i} a {i+4} anos", i, i+4, "ano") for i in range(5, 80, 5)],
    ("80 anos ou mais", 80, 200, "ano"),
]
SEXES = [("Masculino", "0"), ("Feminino", "1")]


def parse_month(value: str) -> int:
    if len(value) != 6 or not value.isascii() or not value.isdigit():
        raise ValueError(f"Competência inválida: {value!r}; use AAAAMM.")
    year, month = int(value[:4]), int(value[4:])
    if year < 1900 or not 1 <= month <= 12:
        raise ValueError(f"Competência inválida: {value!r}.")
    return year * 12 + month - 1


def month_from_index(value: int) -> str:
    return f"{value // 12:04d}{value % 12 + 1:02d}"


def months(start: str, end: str) -> list[str]:
    a, b = parse_month(start), parse_month(end)
    if a > b:
        raise ValueError("Competência inicial posterior à final.")
    return [month_from_index(i) for i in range(a, b + 1)]


@dataclass(frozen=True)
class Job:
    report: str
    url: str
    competencia: str
    linha: str
    linha_label: str
    coluna: str
    coluna_label: str
    faixa_etaria: str
    idade_inicio: int
    idade_fim: int
    tp_idade: str
    sexo: str
    sexo_valor: str
    tipo_producao: str = ""
    tipo_producao_label: str = ""

    @property
    def key(self) -> str:
        # Mantém as chaves antigas quando não havia seleção de produção.
        data = asdict(self)
        if not self.tipo_producao:
            data.pop("tipo_producao")
            data.pop("tipo_producao_label")
        return hashlib.sha256(
            json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:24]

    @property
    def ano(self) -> int:
        return int(self.competencia[:4])

    def to_dict(self) -> dict:
        return {"id": self.key, **asdict(self)}
