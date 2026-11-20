"""Leitura do formulário JSF público e exportação CSV.

Não simula login, não acessa microdados e não pressupõe que CIAP/CID seja um
filtro: ele pode ser apenas uma opção em 'Coluna'.
"""
from __future__ import annotations

import json
import logging
import re
import time
import random
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .model import Job
from .dynamic import column_event, response_fragments


LOG = logging.getLogger("sisab_extrator.portal")


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
    multiselect: bool = False

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
    tipo_producao: Field | None = None
    ciap_cid: Field | None = None

    def as_dict(self) -> dict:
        return {
            "report_url": self.report_url,
            "form_action": self.action,
            "form_id": self.form_id,
            "competencias": self.competencia.options,
            "linha": {"name": self.linha.name, "options": self.linha.options},
            "coluna": {"name": self.coluna.name, "options": self.coluna.options},
            "tipo_producao": (
                {"name": self.tipo_producao.name, "options": self.tipo_producao.options}
                if self.tipo_producao else None
            ),
            "ciap_cid": (
                {"name": self.ciap_cid.name, "options": self.ciap_cid.options,
                 "multiselect": self.ciap_cid.multiselect}
                if self.ciap_cid else None
            ),
            "outros_campos": self.other_fields,
            "botao_csv_identificado": bool(self.csv_button),
        }


def _field_identifier(value: str) -> str:
    """Compara identificadores JSF com/sem acento ou separadores."""
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in value if ch.isalnum() and not unicodedata.combining(ch))


def _extract_field(form, *keys: str) -> Field | None:
    # Prioriza nomes específicos (ex.: selectLinha) antes de aliases (linha).
    for key in keys:
        needle = _field_identifier(key)
        for select in form.find_all("select"):
            ident = select.get("id", "")
            name = select.get("name", ident)
            if needle in _field_identifier(ident) or needle in _field_identifier(name):
                return Field(
                    name=name,
                    id=ident,
                    options={o.get("value", ""): o.get_text(" ", strip=True)
                             for o in select.find_all("option")},
                )
    return None



def _extract_ciap_field(form) -> Field | None:
    """Encontra opcoes reais do filtro CIAP/CID, sem adivinhar valores JSF.

    Formulários com widget AJAX que não apresenta opções no HTML inicial
    precisarão de integração específica; nesse caso não enviaremos lsCid vazio.
    """
    def is_ciap(name: str, ident: str, text: str = "") -> bool:
        key = _field_identifier(name + " " + ident)
        context = _field_identifier(text)
        return (
            any(term in key for term in
                ("lscid", "ciapcid", "selectcid", "filtrocid", "listacid", "listacodigo"))
            or "ciapcid" in context
            or "codigociap" in context
            or "codigocid" in context
        )

    for select in form.find_all("select"):
        name = select.get("name", "")
        ident = select.get("id", "")
        options_nodes = select.find_all("option")
        options = {o.get("value", ""): o.get_text(" ", strip=True)
                   for o in options_nodes}
        parent = select.parent
        parent_marker = ""
        if parent is not None:
            parent_marker = " ".join(
                [parent.get("id", ""), " ".join(parent.get("class", []))]
            )
        context = " ".join([select.get_text(" ", strip=True), parent_marker])
        code_like = any(
            re.match(r"^(?:[A-Z]\d{2,3}|[A-Z]\d{2}(?:\.\d+)?)$", value.strip(), re.I)
            for value in options
            if value
        )
        if (is_ciap(name, ident) or
                (code_like and any(term in _field_identifier(context)
                                   for term in ("ciap", "cid")))) and name:
            if any(options):
                return Field(name, ident, options, multiselect=select.has_attr("multiple"))

    checkboxes = [item for item in form.find_all("input")
                  if item.get("type", "").casefold() == "checkbox"
                  and is_ciap(
                      item.get("name", ""), item.get("id", ""),
                      item.parent.get_text(" ", strip=True) if item.parent else "",
                  )
                  and item.get("name")]
    if checkboxes:
        first = checkboxes[0]
        name = first["name"]
        options = {item.get("value", ""): item.get("data-label", item.get("value", ""))
                   for item in checkboxes if item.get("name") == name}
        if any(options):
            return Field(name, first.get("id", ""), options, multiselect=True)
    return None


def _all_ciap_values(field: Field | None) -> tuple[str, ...]:
    """Seleciona 'Todos' explícito quando disponível, senão todas as opções.

    Somente opções não vazias presentes no HTML são enviadas ao portal.
    """
    if field is None:
        raise PortalError(
            "CIAP/CID = Todos solicitado, mas o formulário inicial não expôs "
            "valores selecionáveis. O portal pode usar AJAX/JavaScript. "
            "Não é seguro enviar lsCid vazio ou inventar códigos. "
            "Consulte data/inspecao/<relatorio>.json (outros_campos) para "
            "identificar o controle antes de adaptar a integração."
        )
    choices = [(value, label) for value, label in field.options.items() if value]
    if not choices:
        raise PortalError("Filtro CIAP/CID encontrado sem opções selecionáveis.")
    for value, label in choices:
        if _field_identifier(label) in ("todos", "todas", "todososcodigos", "todasasopcoes"):
            return (value,)
    if not field.multiselect:
        raise PortalError(
            "O campo CIAP/CID só aceita uma opção por vez e não oferece "
            "um valor explícito 'Todos'. Não é seguro enviar várias opções "
            "como se o controle fosse múltiplo; requer consultas separadas."
        )
    return tuple(value for value, _ in choices)


def parse_page(html: str, report_url: str) -> Page:
    check_url(report_url)
    soup = BeautifulSoup(html, "html.parser")
    forms = [f for f in soup.find_all("form")
             if f.find("input", attrs={"name": "javax.faces.ViewState"})]
    if not forms:
        title = soup.title.get_text(" ", strip=True)[:120] if soup.title else "(sem título)"
        raise PortalError(
            f"Formulário do relatório com ViewState não encontrado; título recebido: {title!r}. "
            "A página pode ser de login, erro ou ter mudado."
        )

    def form_score(f):
        selects = f.find_all("select")
        has_comp = _extract_field(f, "competencia", "competência") is not None
        has_linha = _extract_field(f, "selectLinha", "linha") is not None
        has_coluna = _extract_field(f, "selectcoluna", "coluna") is not None
        return (int(has_comp) + int(has_linha) + int(has_coluna),
                len(selects))

    # Algumas páginas têm mais de um form JSF. O primeiro pode não ser o
    # relatório; escolha o que contém mais campos relevantes.
    form = max(forms, key=form_score)
    view = form.find("input", attrs={"name": "javax.faces.ViewState"})
    if not view.get("value"):
        raise PortalError("ViewState ausente no formulário do relatório.")

    comp = _extract_field(form, "competencia", "competência")
    if comp is None:
        for select in form.find_all("select"):
            opts = select.find_all("option")
            values = [o.get("value", "") for o in opts]
            if any(re.fullmatch(r"\d{6}", v) for v in values):
                comp = Field(select.get("name", select.get("id", "")), select.get("id", ""),
                             {o.get("value", ""): o.get_text(" ", strip=True) for o in opts})
                break
    linha = _extract_field(form, "selectLinha", "linha")
    coluna = _extract_field(form, "selectcoluna", "coluna")
    if not comp or not linha or not coluna:
        missing = [name for name, obj in [("competência", comp), ("linha", linha), ("coluna", coluna)] if obj is None]
        names = [s.get("id", s.get("name", "")) for s in form.find_all("select")][:15]
        raise PortalError(
            "Campos não encontrados: " + ", ".join(missing) +
            f". Campos select presentes no formulário: {names!r}. "
            "O formulário real pode ter mudado ou depender de JavaScript."
        )

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
    tipo_producao = _extract_field(form, "tpProducao")
    ciap_cid = _extract_ciap_field(form)
    return Page(report_url, action, form.get("id", ""), view["value"], comp, linha,
                coluna, button, fields, hidden, tipo_producao=tipo_producao,
                ciap_cid=ciap_cid)


def sniff_csv(content: bytes) -> bool:
    sample = content[:25000]
    if b";" not in sample or b"<html" in sample.lower() or b"<partial-response" in sample.lower():
        return False
    return any(sep in sample for sep in (b"Uf;Ibge;Municipio;", b"Uf;Ibge;Munic", b";"))


def _safe_url(url: str) -> str:
    """Remove parâmetros e fragmentos que possam conter identificadores sensíveis."""
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="", params="").geturl()


def _diagnostic_response(response, requested_url: str) -> dict:
    """Metadados seguros da resposta: não salva HTML nem valores de formulários."""
    soup = BeautifulSoup(response.text, "html.parser")
    # Resumos de erro visíveis do JSF / PrimeFaces, sem copiar o HTML completo.
    warnings = []
    selectors = (
        ".ui-messages-error-summary, .ui-messages-error-detail, "
        ".ui-message-error, .ui-message-error-detail, "
        ".ui-messages-warn-summary, .ui-messages-warn-detail, "
        ".ui-growl-message, .alert-danger, [role='alert']"
    )
    for node in soup.select(selectors):
        value = node.get_text(" ", strip=True)[:240]
        if value and value not in warnings and len(warnings) < 12:
            warnings.append(value)
    return {
        "url_solicitada": _safe_url(requested_url),
        "url_recebida": _safe_url(getattr(response, "url", requested_url)),
        "status_http": getattr(response, "status_code", None),
        "tipo_conteudo": response.headers.get("Content-Type", ""),
        "tamanho_bytes": len(
            getattr(response, "content", response.text.encode("utf-8"))
        ),
        "titulo_pagina": soup.title.get_text(" ", strip=True)[:160] if soup.title else "",
        "mensagens_portal": warnings,
        "formularios": [
            {"id": f.get("id", ""), "name": f.get("name", ""),
             "quantidade_selects": len(f.find_all("select"))}
            for f in soup.find_all("form")[:15]
        ],
        "selects": [
            {"id": select.get("id", ""), "name": select.get("name", ""),
             "quantidade_opcoes": len(select.find_all("option"))}
            for select in soup.find_all("select")[:60]
        ],
        "aviso": ("O diagnóstico não inclui cookies, ViewState, HTML completo "
                  "ou valores de campos de formulário.")
    }


def _diagnostic_label(url: str) -> str:
    path = urlparse(url).path
    if "/federal/" in path:
        return "federal"
    if "/municipio/" in path:
        return "municipal"
    return "personalizado"


class Client:
    def __init__(self, url: str, delay: float = 2.0, timeout: int = 900,
                 retries: int = 6, backoff: float = 5.0,
                 diagnostics_dir: Path | None = None):
        self.url = check_url(url)
        self.delay = max(delay, 0)
        self.timeout = timeout
        self.retries = max(retries, 0)
        self.backoff = max(backoff, 0)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "sisab-extrator/0.1 (pesquisa; acesso a relatorios publicos)"})
        self.page: Page | None = None
        self._last_html = ""
        self.diagnostics_dir = Path(diagnostics_dir) if diagnostics_dir is not None else None

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
            # Não registrar dados POST, cookies ou tokens no log.
            safe_path = urlparse(url).path
            LOG.info("SISAB %s %s | tentativa %d/%d | limite %ss",
                     method, safe_path, attempt + 1, self.retries + 1, self.timeout)
            started = time.monotonic()
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                LOG.info("SISAB %s concluído | HTTP %d | %.1fs | %d bytes",
                         method, response.status_code,
                         time.monotonic() - started, len(response.content))
                return response
            except requests.RequestException as exc:
                error = exc
                LOG.warning("SISAB %s falhou | tentativa %d/%d | %.1fs | %s",
                            method, attempt + 1, self.retries + 1,
                            time.monotonic() - started, type(exc).__name__)
                if attempt < self.retries:
                    wait = min(self.backoff * (2 ** attempt), 120) + random.random()
                    LOG.info("Aguardando %.1fs antes de repetir...", wait)
                    time.sleep(wait)
        raise PortalError(f"Falha de rede após tentativas: {error}")

    def open(self) -> Page:
        resp = self._request("GET", self.url)
        resp.encoding = resp.encoding or "utf-8"
        try:
            self._last_html = resp.text
            self.page = parse_page(resp.text, self.url)
            return self.page
        except PortalError as exc:
            message = str(exc)
            if self.diagnostics_dir is not None:
                try:
                    self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
                    label = _diagnostic_label(self.url)
                    target = self.diagnostics_dir / f"diagnostico_{label}.json"
                    target.write_text(
                        json.dumps(_diagnostic_response(resp, self.url),
                                   indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    message += f" Diagnóstico da página recebido em: {target}."
                except OSError as write_exc:
                    message += f" Não foi possível gravar diagnóstico: {write_exc}."
            raise PortalError(message) from exc

    def reveal_ciap(self, linha: str, coluna: str, competencia: str,
                    tipo_producao: str = "") -> Field:
        """Dispara somente o onchange JSF identificado da coluna CIAP/CID.

        Não solicita CSV, e não inventa seletores ou valores de códigos.
        """
        page = self.page or self.open()
        if page.ciap_cid is not None:
            return page.ciap_cid
        soup = BeautifulSoup(self._last_html, "html.parser")
        form = next((f for f in soup.find_all("form")
                     if f.get("id") == page.form_id), None)
        select = next((t for t in form.find_all("select")
                       if t.get("name") == page.coluna.name), None) if form else None
        handler = select.get("onchange", "") if select else ""
        event = column_event(handler or "", select.get("id", "") if select else "")
        info = {
            "operacao": "ativar_coluna_ciap_cid",
            "campo_coluna": page.coluna.name,
            "eventos_coluna": {
                "onchange": bool(handler), "onchange_tamanho": len(handler or ""),
                "framework_identificado": event["framework"] if event else None,
            },
            "resposta": None, "atualizacoes": [], "codigos_detectados": 0,
        }
        target = (self.diagnostics_dir /
                  f"diagnostico_ciap_{_diagnostic_label(self.url)}.json"
                  if self.diagnostics_dir is not None else None)

        def save_diagnostic():
            if target is None:
                return
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            except OSError as exc:
                LOG.warning("Diagnostico CIAP/CID nao salvo: %s", exc)

        if event is None:
            info["motivo"] = (
                "A coluna CIAP/CID pode depender de JavaScript, mas o "
                "manipulador AJAX da coluna não foi identificado."
            )
            save_diagnostic()
            raise PortalError(
                "CIAP/CID aparece após selecionar a coluna, mas o evento de "
                "atualização não foi identificado. "
                f"Diagnóstico: {target or 'não configurado'}."
            )
        payload = [(k, v) for k, v in page.hidden_fields
                   if k != "javax.faces.ViewState"]
        payload.extend([
            (page.form_id, page.form_id),
            ("javax.faces.ViewState", page.view_state),
            (page.competencia.name, competencia),
            (page.linha.name, linha),
            (page.coluna.name, coluna),
            (page.tipo_producao.name if page.tipo_producao else "tpProducao",
             tipo_producao),
            ("javax.faces.partial.ajax", "true"),
            ("javax.faces.source", event["source"]),
            ("javax.faces.partial.execute", event["execute"]),
            ("javax.faces.partial.render", event["render"]),
            ("javax.faces.behavior.event", event["event"]),
            ("javax.faces.partial.event", event["event"]),
        ])
        response = self._request(
            "POST", page.action, data=payload,
            headers={"Faces-Request": "partial/ajax",
                     "X-Requested-With": "XMLHttpRequest"},
        )
        response.encoding = response.encoding or "utf-8"
        info["resposta"] = response.headers.get("Content-Type", "")
        try:
            fragments, view_state, updates = response_fragments(response.text)
        except Exception as exc:
            info["motivo"] = "Resposta JSF parcial inválida."
            save_diagnostic()
            raise PortalError(
                f"Falha ao interpretar atualização de CIAP/CID: {exc}"
            ) from exc
        info["atualizacoes"] = updates
        field = None
        for fragment in fragments:
            parsed = BeautifulSoup(fragment, "html.parser")
            field = _extract_ciap_field(parsed)
            if field:
                if view_state is None:
                    new_view = parsed.find(
                        "input", attrs={"name": "javax.faces.ViewState"}
                    )
                    if new_view:
                        view_state = new_view.get("value")
                break
        if field is None:
            info["motivo"] = (
                "O evento JSF foi processado, mas a resposta não trouxe "
                "uma lista CIAP/CID reconhecível. Pode existir outra etapa."
            )
            save_diagnostic()
            raise PortalError(
                "A seleção da coluna não revelou códigos CIAP/CID reconhecíveis. "
                f"Diagnóstico: {target or 'não configurado'}."
            )
        info["codigos_detectados"] = sum(bool(v) for v in field.options)
        page.ciap_cid = field
        if view_state:
            page.view_state = view_state
        info["motivo"] = "Opções CIAP/CID identificadas após seleção da coluna."
        save_diagnostic()
        LOG.info("Filtro CIAP/CID ativado: %d opcoes.",
                 info["codigos_detectados"])
        return field

    def _save_export_diagnostic(self, response, job: Job, page: Page,
                                details: dict | None = None) -> Path | None:
        """Registra uma exportação que devolveu HTML; não grava payload nem CSV."""
        if self.diagnostics_dir is None:
            return None
        try:
            self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
            filename = f"diagnostico_exportacao_{_diagnostic_label(self.url)}.json"
            target = self.diagnostics_dir / filename
            info = (details or _diagnostic_response(response, self.url)).copy()
            info["operacao"] = "exportacao_csv"
            info["consulta"] = {
                "competencia": job.competencia,
                "linha": job.linha_label,
                "coluna": job.coluna_label,
                "tipo_producao": job.tipo_producao_label or job.tipo_producao,
                "sexo": job.sexo,
                "faixa_etaria": job.faixa_etaria,
                "quantidade_ciap_cid": len(job.ciap_cid),
            }
            info["campos_enviados"] = {
                "formulario": page.form_id,
                "competencia": page.competencia.name,
                "linha": page.linha.name,
                "coluna": page.coluna.name,
                "botao_csv": page.csv_button,
            }
            target.write_text(json.dumps(info, indent=2, ensure_ascii=False),
                              encoding="utf-8")
            return target
        except OSError as exc:
            LOG.warning("Nao foi possivel gravar diagnostico da exportacao: %s", exc)
            return None

    def download(self, job: Job) -> bytes:
        page = self.page or self.open()
        if job.competencia not in page.competencia.options:
            raise PortalError(f"Competência {job.competencia} não disponível no portal.")
        if page.tipo_producao is not None:
            is_production_dimension = any(
                "tipodeproducao" in _field_identifier(label)
                for label in (job.linha_label, job.coluna_label)
            )
            if not job.tipo_producao and not is_production_dimension:
                available = [label for value, label in page.tipo_producao.options.items()
                             if value]
                raise PortalError(
                    "O SISAB exige Tipo de Produção quando esta variável não está "
                    "na linha/coluna. Informe tipo_producao no sisab_baixar(), "
                    f"usando uma das opções apresentadas pelo portal: {available!r}."
                )
            if job.tipo_producao and job.tipo_producao not in page.tipo_producao.options:
                raise PortalError(
                    f"Tipo de Produção {job.tipo_producao!r} não existe no formulário atual."
                )
        if job.ciap_cid and page.ciap_cid is None:
            raise PortalError(
                "Filtro CIAP/CID solicitado, mas não existem opções identificáveis "
                "no HTML do formulário. O envio foi interrompido antes do POST."
            )
        error = None
        previous_html_signature = None
        for attempt in range(self.retries + 1):
            page = self.page or self.open()
            if job.ciap_cid and (
                page.ciap_cid is None or
                any(value not in page.ciap_cid.options for value in job.ciap_cid)
            ):
                raise PortalError(
                    "As opções CIAP/CID do formulário mudaram. "
                    "Execute sisab_inspecionar() novamente antes de baixar."
                )
            # Recriar payload a cada tentativa: ViewState e nomes JSF podem mudar.
            hidden = [(k, v) for k, v in page.hidden_fields
                      if k != "javax.faces.ViewState"
                      and (not job.ciap_cid or k != page.ciap_cid.name)]
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
                (page.tipo_producao.name if page.tipo_producao else "tpProducao",
                 job.tipo_producao),
                (page.csv_button, page.csv_button),
            ]
            if job.sexo_valor:
                payload.append(("sexo", job.sexo_valor))
            if job.ciap_cid:
                payload.extend((page.ciap_cid.name, value) for value in job.ciap_cid)
            # Não enviar lsCid vazio: quando CIAP/CID é uma dimensão,
            # o SISAB pode exigir valores efetivamente selecionados.
            if "lsSigtap" not in fields:
                payload.append(("lsSigtap", ""))
            response = self._request("POST", page.action, data=payload)
            if sniff_csv(response.content):
                return response.content
            raw_text = response.content.decode("utf-8", errors="replace")
            if "A consulta não retornou nenhum dado" in raw_text or "A consulta n&#227;o retornou nenhum dado" in raw_text:
                raise NoData(f"Consulta sem dados: {job.key}")
            latin_text = response.content.decode("iso-8859-1", errors="replace")
            if "A consulta não retornou nenhum dado" in latin_text:
                raise NoData(f"Consulta sem dados: {job.key}")
            content_type = response.headers.get("Content-Type", "")
            html_response = "html" in content_type.casefold() or (
                b"<html" in response.content[:2000].lower()
            )
            details = _diagnostic_response(response, self.url) if html_response else None
            diagnostic = self._save_export_diagnostic(response, job, page, details)
            diagnostic_text = f" Diagnóstico: {diagnostic}." if diagnostic else ""
            messages = details.get("mensagens_portal", []) if details else []
            if messages:
                # Validacao do JSF: outra tentativa com os mesmos filtros nao resolve.
                reason = "; ".join(messages)
                error = (
                    f"O SISAB rejeitou os filtros da consulta: {reason}."
                    f"{diagnostic_text} Nao repetiremos esta consulta sem alterar os filtros."
                )
                LOG.error("Validacao do formulario: %s", reason)
                raise PortalError(error)
            error = (
                f"O SISAB respondeu à exportação, mas devolveu {content_type!r} "
                f"em vez de CSV ({len(response.content)} bytes)."
                f"{diagnostic_text} Verifique se o filtro escolhido exige "
                "outra configuração no formulário."
            )
            if html_response:
                # O portal altera tokens JSF entre paginas, entao nao comparamos
                # HTML inteiro. Duas respostas com mesmo tamanho/titulo/tipo
                # ja sao um sinal suficiente para nao insistir sete vezes.
                signature = (
                    content_type.casefold(),
                    len(response.content),
                    details.get("titulo_pagina", "") if details else "",
                )
                if signature == previous_html_signature:
                    raise PortalError(
                        error + " Duas respostas HTML consecutivas tiveram as "
                        "mesmas características; novas tentativas foram interrompidas."
                    )
                previous_html_signature = signature
            if attempt < self.retries:
                LOG.warning("%s Nova tentativa em seguida.", error)
                time.sleep(min(self.backoff * (2 ** attempt), 120) + random.random())
                self.open()
        raise PortalError(error or "SISAB não retornou CSV")
