"""CIAP/CID aparece depois do evento JSF que seleciona a coluna."""
from types import SimpleNamespace

import pytest

from sisab_extrator.dynamic import column_event, response_fragments
from sisab_extrator.portal import Client, PortalError, parse_page
from sisab_extrator.cli import prepare
from test_portal import HTML, URL


def dynamic_html():
    return HTML.replace(
        'id="selectcoluna" name="selectcoluna"',
        'id="selectcoluna" name="selectcoluna" '
        'onchange="jsf.ajax.request(&quot;selectcoluna&quot;,event,'
        '{execute:&quot;selectcoluna&quot;,render:&quot;cidPanel&quot;})"',
    )


def request_args():
    return SimpleNamespace(
        start="202401", end="202401",
        lines="Municipio", columns="CIAP/CID",
        ages="none", sexes="none", production_type="none", ciap_cid="all",
    )


def ajax_response():
    class Response:
        status_code = 200
        headers = {"Content-Type": "text/xml;charset=UTF-8"}
        encoding = "utf-8"
        text = (
            "<partial-response><changes>"
            "<update id='cidPanel'><![CDATA["
            "<select id='lsCid' name='lsCid' multiple>"
            "<option value='A01'>CIAP A01</option>"
            "<option value='B02'>CIAP B02</option>"
            "</select>"
            "]]></update>"
            "<update id='javax.faces.ViewState'><![CDATA[JSF-UPDATED]]></update>"
            "</changes></partial-response>"
        )
        content = text.encode("utf-8")
    return Response()


def test_jsf_event_is_parsed_from_column_html():
    assert column_event(
        'jsf.ajax.request("selectcoluna",event,{execute:"selectcoluna",render:"cidPanel"})'
    ) == {"source": "selectcoluna", "execute": "selectcoluna",
          "render": "cidPanel", "event": "change", "framework": "jsf"}
    assert column_event("someOtherHandler()") is None


def test_jsf_partial_response_contains_codes_and_new_view_state():
    fragments, state, updates = response_fragments(ajax_response().text)
    assert "A01" in fragments[0]
    assert state == "JSF-UPDATED"
    assert updates == ["cidPanel", "javax.faces.ViewState"]


def test_dynamic_selection_then_all_codes_before_csv(tmp_path):
    html = dynamic_html()
    client = Client(URL, delay=0, retries=0, diagnostics_dir=tmp_path)
    client.page = parse_page(html, URL)
    client._last_html = html
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return ajax_response()

    client._request = fake_request
    plan = prepare("federal", client, client.page, request_args())
    job = next(plan.jobs())
    assert job.ciap_cid == ("A01", "B02")
    assert client.page.view_state == "JSF-UPDATED"
    assert len(calls) == 1
    assert ("javax.faces.partial.ajax", "true") in calls[0][2]["data"]
    assert ("selectcoluna", "CID") in calls[0][2]["data"]
    assert ("j_idt99", "j_idt99") not in calls[0][2]["data"]
    assert (tmp_path / "diagnostico_ciap_federal.json").exists()


def test_no_known_dynamic_event_writes_diagnostic_without_post(tmp_path):
    client = Client(URL, delay=0, diagnostics_dir=tmp_path)
    client.page = parse_page(HTML, URL)
    client._last_html = HTML
    client._request = lambda *args, **kwargs: pytest.fail("Não deve enviar POST")
    with pytest.raises(PortalError, match="evento de atualização"):
        prepare("federal", client, client.page, request_args())
    diagnostic = (tmp_path / "diagnostico_ciap_federal.json").read_text(encoding="utf-8")
    assert "onchange" in diagnostic
    assert "JSF123" not in diagnostic


def test_mojarra_this_source_uses_element_id():
    event = column_event(
        "mojarra.ab(this,event,'valueChange','selectcoluna','cidPanel')",
        "selectcoluna",
    )
    assert event["source"] == "selectcoluna"
    assert event["render"] == "cidPanel"
