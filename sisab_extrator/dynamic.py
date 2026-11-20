"""Leitura conservadora de eventos JSF relacionados a filtros dinâmicos.

Não executa JavaScript, não inventa URLs nem identifica controles sem evidência.
"""
from __future__ import annotations

import re
from xml.etree import ElementTree


def column_event(handler: str, source_id: str = "") -> dict[str, str] | None:
    """Extrai somente os parâmetros de handlers JSF reconhecidos."""
    if "PrimeFaces.ab(" in handler:
        opts = dict(re.findall(r"""(?:^|[,{\s])([sepu])\s*:\s*['"]([^'"]+)['"]""", handler))
        if "s" not in opts:
            return None
        return dict(source=opts["s"], execute=opts.get("p", "@this"),
                    render=opts.get("u", "@none"), event=opts.get("e", "change"),
                    framework="PrimeFaces")

    if "jsf.ajax.request(" in handler:
        call = handler.split("jsf.ajax.request(", 1)[1]
        source = re.match(r"""\s*['"]([^'"]+)['"]""", call)
        selected_source = source.group(1) if source is not None else (
            source_id if re.match(r"\s*this\b", call) else ""
        )
        if not selected_source:
            return None
        opts = dict(re.findall(
            r"""(?:^|[,{\s])(execute|render|event)\s*:\s*['"]([^'"]+)['"]""", call
        ))
        return dict(source=selected_source, execute=opts.get("execute", "@this"),
                    render=opts.get("render", "@none"),
                    event=opts.get("event", "change"), framework="jsf")

    if "mojarra.ab(" in handler:
        call = handler.split("mojarra.ab(", 1)[1].split(")", 1)[0]
        # mojarra.ab(source, event, eventName, execute, render, ...)
        args = re.findall(r"""(?:'[^']*'|"[^"]*"|\bthis\b|\bevent\b|\b\d+\b)""", call)
        if len(args) < 5 or args[1] != "event":
            return None
        def value(token):
            return token[1:-1] if token.startswith(("'", '"')) else token
        src = source_id if args[0] == "this" else value(args[0])
        if not src:
            return None
        return dict(source=src, execute=value(args[3]) or "@this",
                    render=value(args[4]) or "@none",
                    event="change", framework="mojarra")

    return None


def response_fragments(body: str) -> tuple[list[str], str | None, list[str]]:
    """Retorna HTML atualizado, ViewState e IDs atualizados por resposta AJAX."""
    if "<partial-response" not in body[:1000]:
        return [body], None, ["html"]
    root = ElementTree.fromstring(body)
    html = []
    state = None
    updates = []
    for node in root.findall(".//update"):
        update_id = node.attrib.get("id", "")
        updates.append(update_id[:120])
        if "javax.faces.ViewState" in update_id:
            state = (node.text or "").strip()
        else:
            html.append(node.text or "")
    return html, state, updates[:30]
