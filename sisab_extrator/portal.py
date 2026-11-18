"""Leitura do formulário JSF público e exportação CSV.

Não simula login, não acessa microdados e não pressupõe que CIAP/CID seja um
filtro: ele pode ser apenas uma opção em 'Coluna'.
"""
from __future__ import annotations

import re
import time
import random
import unicodedata
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .model import Job


class PortalError(RuntimeError):
    """Falha de acesso, configuração ou formato do relatório."""


class NoData(PortalError):
    """Consulta válida, porém sem dados."""


def check_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "sisab.saude.gov.br":
        raise ValueError("Somente relatórios HTTPS públicos de sisab.saude.gov.br são permitidos.")
    if not parsed.path.endswith(".xhtml"):
        raise ValueError("URL deve apontar para um relatório .xhtml do SISAB.")
    return url


@dataclass
class Field:
    name: str
    id: str
    options: dict[str, str]

    def choose(self, selector: str) -> list[tuple[str, str]]:
        """Retorna (valor, rótulo); aceita valor, rótulo ou 'all'."""
        nonempty = [(v, label) for v, label in self.options.items() if v]
        if selector.lower() == "all":
            return nonempty
        def norm(v: str) -> str:
            return "".join(ch for ch in unicodedata.normalize("NFKD", v.casefold().strip())
                           if not unicodedata.combining(ch))
        normalized = norm(selector)
        exact = [(v, label) for v, label in nonempty if norm(v) == normalized or norm(label) == normalized]
        if exact:
            return exact
        fuzzy = [(v, label) for v, label in nonempty if normalized in norm(label)]
        if len(fuzzy) == 1:
            return fuzzy
        if not fuzzy:
            raise ValueError(f"Opção {selector!r} não encontrada no campo {self.id}. Execute 'probe'.")
        raise ValueError(f"Opção ambígua {selector!r} em {self.id}: {[label for _,label in fuzzy]}")


@dataclass
class Page:
    report_url: str
    action: str
    form_id: str
    view_state: str
    competencia: Field
    linha: Field
    coluna: Field
    csv_button: str
    other_fields: list[dict]
    hidden_fields: list[tuple[str, str]]

    def as_dict(self) -> dict:
        return {
            "report_url": self.report_url,
            "form_action": self.action,
            "form_id": self.form_id,
            "competencias": self.competencia.options,
            "linha": {"name": self.linha.name, "options": self.linha.options},
            "coluna": {"name": self.coluna.name, "options": self.coluna.options},
            "outros_campos": self.other_fields,
            "botao_csv_identificado": bool(self.csv_button),
        }


def _extract_field(form, *keys: str) -> Field | None:
    for select in form.find_all("select"):
        ident = select.get("id", "")
        name = select.get("name", ident)
        if any(k.casefold() in ident.casefold() or k.casefold() in name.casefold() for k in keys):
            return Field(
                name=name,
                id=ident,
                options={o.get("value", ""): o.get_text(" ", strip=True) for o in select.find_all("option")},
            )
    return None


def parse_page(html: str, report_url: str) -> Page:
    check_url(report_url)
    soup = BeautifulSoup(html, "html.parser")
    form = next((f for f in soup.find_all("form") if f.find("input", attrs={"name": "javax.faces.ViewState"})), None)
    if form is None:
        raise PortalError("Formulário com javax.faces.ViewState não encontrado. O SISAB pode ter mudado.")
    view = form.find("input", attrs={"name": "javax.faces.ViewState"})
    if not view.get("value"):
        raise PortalError("ViewState ausente.")

    comp = _extract_field(form, "competencia")
    if comp is None:
        for select in form.find_all("select"):
            opts = select.find_all("option")
            values = [o.get("value", "") for o in opts]
            if any(re.fullmatch(r"\d{6}", v) for v in values):
                comp = Field(select.get("name", select.get("id", "")), select.get("id", ""),
                             {o.get("value", ""): o.get_text(" ", strip=True) for o in opts})
                break
    linha = _extract_field(form, "selectLinha")
    coluna = _extract_field(form, "selectcoluna")
    if not comp or not linha or not coluna:
        missing = [name for name, obj in [("competência", comp), ("selectLinha", linha), ("selectcoluna", coluna)] if obj is None]
        raise PortalError("Campos não encontrados: " + ", ".join(missing) + ". Execute 'probe' e verifique a página.")

    button = ""
    for a in form.find_all("a"):
        if a.get_text(" ", strip=True).casefold() != "csv":
            continue
        onclick = a.get("onclick", "")
        match = re.search(r"\{'([^']+)':'\1'\}", onclick)
        if match:
            button = match.group(1)
            break
    if not button:
        for element in form.find_all(["input", "button"]):
            if element.get("value", "").casefold() == "csv" or element.get_text(" ", strip=True).casefold() == "csv":
                button = element.get("name", "")
                if button:
                    break
    if not button:
        raise PortalError("Controle de exportação CSV não encontrado; não é seguro inventá-lo.")

    hidden = [(el.get("name"), el.get("value", "")) for el in form.find_all("input")
              if el.get("name") and el.get("type", "text").casefold() == "hidden"]
    fields = []
    for element in form.find_all(["input", "select", "textarea"]):
        fields.append({"tag": element.name, "id": element.get("id", ""),
                       "name": element.get("name", ""), "type": element.get("type", ""),
                       "options": [{"value": o.get("value", ""), "label": o.get_text(" ", strip=True)}
                                   for o in element.find_all("option")] if element.name == "select" else []})

    action = urljoin(report_url, form.get("action") or report_url)
    check_url(action)
    return Page(report_url, action, form.get("id", ""), view["value"], comp, linha,
                coluna, button, fields, hidden)


def sniff_csv(content: bytes) -> bool:
    sample = content[:25000]
    if b";" not in sample or b"<html" in sample.lower() or b"<partial-response" in sample.lower():
        return False
    return any(sep in sample for sep in (b"Uf;Ibge;Municipio;", b"Uf;Ibge;Munic", b";"))


class Client:
    def __init__(self, url: str, delay: float = 2.0, timeout: int = 900,
                 retries: int = 6, backoff: float = 5.0):
        self.url = check_url(url)
        self.delay = max(delay, 0)
        self.timeout = timeout
        self.retries = max(retries, 0)
        self.backoff = max(backoff, 0)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "sisab-extrator/0.1 (pesquisa; acesso a relatorios publicos)"})
        self.page: Page | None = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.session.close()

    def _request(self, method: str, url: str, **kwargs):
        error = None
        for attempt in range(self.retries + 1):
            if self.delay:
                time.sleep(self.delay)
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                error = exc
                if attempt < self.retries:
                    time.sleep(min(self.backoff * (2 ** attempt), 120) + random.random())
        raise PortalError(f"Falha de rede após tentativas: {error}")

    def open(self) -> Page:
        resp = self._request("GET", self.url)
        resp.encoding = resp.encoding or "utf-8"
        self.page = parse_page(resp.text, self.url)
        return self.page

    def download(self, job: Job) -> bytes:
        page = self.page or self.open()
        if job.competencia not in page.competencia.options:
            raise PortalError(f"Competência {job.competencia} não disponível no portal.")
        error = None
        for attempt in range(self.retries + 1):
            page = self.page or self.open()
            # Recriar payload a cada tentativa: ViewState e nomes JSF podem mudar.
            hidden = [(k, v) for k, v in page.hidden_fields if k != "javax.faces.ViewState"]
            fields = {k for k, _ in hidden}
            payload = hidden + [
                (page.form_id, page.form_id),
                ("javax.faces.ViewState", page.view_state),
                (page.competencia.name, job.competencia),
                (page.linha.name, job.linha),
                (page.coluna.name, job.coluna),
                ("idadeInicio", str(job.idade_inicio)),
                ("idadeFim", str(job.idade_fim)),
                ("tpIdade", job.tp_idade),
                ("tpProducao", ""),
                (page.csv_button, page.csv_button),
            ]
            if job.sexo_valor:
                payload.append(("sexo", job.sexo_valor))
            for key in ("lsCid", "lsSigtap"):
                if key not in fields:
                    payload.append((key, ""))
            response = self._request("POST", page.action, data=payload)
            if sniff_csv(response.content):
                return response.content
            raw_text = response.content.decode("utf-8", errors="replace")
            if "A consulta não retornou nenhum dado" in raw_text or "A consulta n&#227;o retornou nenhum dado" in raw_text:
                raise NoData(f"Consulta sem dados: {job.key}")
            latin_text = response.content.decode("iso-8859-1", errors="replace")
            if "A consulta não retornou nenhum dado" in latin_text:
                raise NoData(f"Consulta sem dados: {job.key}")
            error = f"Resposta não-CSV ({response.headers.get('Content-Type')}); início: {raw_text[:160]!r}"
            if attempt < self.retries:
                time.sleep(min(self.backoff * (2 ** attempt), 120) + random.random())
                self.open()
        raise PortalError(error or "SISAB não retornou CSV")
