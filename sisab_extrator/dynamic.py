"""Leitura conservadora de eventos JSF relacionados a filtros dinâmicos.

Não executa JavaScript, não inventa URLs nem identifica controles sem evidência.
"""
from __future__ import annotations

import re
from xml.etree import ElementTree


def column_event(handler: str) -> dict[str, str] | None:
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
        if source is None:
            return None
        opts = dict(re.findall(
            r"""(?:^|[,{\s])(execute|render|event)\s*:\s*['"]([^'"]+)['"]""", call
        ))
        return dict(source=source.group(1), execute=opts.get("execute", "@this"),
                    render=opts.get("render", "@none"),
                    event=opts.get("event", "change"), framework="jsf")

    if "mojarra.ab(" in handler:
        call = handler.split("mojarra.ab(", 1)[1]
        values = re.findall(r"""['"]([^'"]+)['"]""", call.split(")", 1)[0])
        if not values:
            return None
        return dict(source=values[0],
                    execute=values[2] if len(values) > 2 else "@this",
                    render=values[3] if len(values) > 3 else "@none",
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
