"""Testes locais do modo CIAP/CID = Todos (sem fazer requisições reais)."""
from types import SimpleNamespace

import pytest

from sisab_extrator.cli import prepare
from sisab_extrator.portal import Client, PortalError, parse_page
from test_portal import HTML, URL


def with_ciap_control(control: str) -> str:
    return HTML.replace("</form>", control + "</form>")


def args(mode="all", column="CIAP/CID"):
    return SimpleNamespace(
        start="202401", end="202401", lines="Municipio",
        columns=column, ages="none", sexes="none",
        production_type="none", ciap_cid=mode,
    )


def test_multiselect_exposes_all_real_values_as_single_job():
    html = with_ciap_control(
        '<select id="lsCid" name="lsCid" multiple>'
        '<option value="">Selecione</option>'
        '<option value="A01">CIAP A01</option>'
        '<option value="B02">CIAP B02</option>'
        '</select>'
    )
    page = parse_page(html, URL)
    assert page.ciap_cid is not None
    assert page.ciap_cid.multiselect is True
    assert page.as_dict()["ciap_cid"]["options"]["A01"] == "CIAP A01"
    plan = prepare("federal", None, page, args())
    assert plan.count == 1
    job = next(plan.jobs())
    assert job.ciap_cid == ("A01", "B02")


def test_post_sends_all_ciap_values_not_empty_field():
    html = with_ciap_control(
        '<select id="lsCid" name="lsCid" multiple>'
        '<option value="A01">CIAP A01</option>'
        '<option value="B02">CIAP B02</option></select>'
        '<input type="hidden" name="lsCid" value="">'
    )
    page = parse_page(html, URL)
    job = next(prepare("federal", None, page, args()).jobs())
    client = Client(URL, delay=0, retries=0)
    client.page = page
    sent = []

    class Response:
        content = b"Uf;Ibge;Municipio;A01;B02;\nMG;3146107;Ouro Preto;4;5;\n"
        headers = {"Content-Type": "text/csv"}

    def mock_request(method, url, **kwargs):
        assert method == "POST"
        sent.extend(kwargs["data"])
        return Response()

    client._request = mock_request
    assert client.download(job) == Response.content
    assert [value for name, value in sent if name == "lsCid"] == ["A01", "B02"]
    assert ("lsCid", "") not in sent


def test_single_select_with_explicit_todos_uses_token():
    html = with_ciap_control(
        '<select id="lsCid" name="lsCid">'
        '<option value="">Selecione</option>'
        '<option value="ALL">Todos</option>'
        '<option value="A01">A01</option></select>'
    )
    page = parse_page(html, URL)
    assert page.ciap_cid.multiselect is False
    assert next(prepare("federal", None, page, args()).jobs()).ciap_cid == ("ALL",)


def test_single_select_without_todos_is_rejected():
    html = with_ciap_control(
        '<select name="lsCid"><option value="A01">A01</option>'
        '<option value="B02">B02</option></select>'
    )
    page = parse_page(html, URL)
    with pytest.raises(PortalError, match="só aceita uma opção"):
        prepare("federal", None, page, args())


def test_dynamic_ciap_control_is_not_faked_and_stops_before_http():
    # Um input oculto sem lista de opções não prova como selecionar todos via AJAX.
    html = with_ciap_control('<input type="hidden" name="lsCid" value="">')
    page = parse_page(html, URL)
    assert page.ciap_cid is None
    with pytest.raises(PortalError, match="AJAX/JavaScript"):
        prepare("federal", None, page, args())


def test_auto_ciap_selects_only_when_ciap_is_dimension():
    html = with_ciap_control(
        '<select name="lsCid" multiple>'
        '<option value="A01">A01</option></select>'
    )
    page = parse_page(html, URL)
    assert next(prepare("federal", None, page, args(mode="auto")).jobs()).ciap_cid == ("A01",)
    assert next(prepare("federal", None, page, args(mode="auto", column="Procedimento")).jobs()).ciap_cid == ()


def test_explicit_none_keeps_existing_queries_unchanged():
    page = parse_page(HTML, URL)
    job = next(prepare("federal", None, page, args(mode="none")).jobs())
    assert job.ciap_cid == ()


def test_auto_only_applies_to_ciap_jobs_in_mixed_all_columns():
    # Com todas as colunas selecionadas, os demais relatórios não devem
    # receber indevidamente o filtro CIAP/CID.
    html = with_ciap_control(
        '<select name="lsCid" multiple>'
        '<option value="A01">CIAP A01</option>'
        '<option value="B02">CIAP B02</option></select>'
    )
    page = parse_page(html, URL)
    a = args(mode="auto")
    a.columns = "all"
    plan = prepare("federal", None, page, a)
    jobs = list(plan.jobs())
    assert len(jobs) == 2
    assert next(j for j in jobs if j.coluna == "CID").ciap_cid == ("A01", "B02")
    assert next(j for j in jobs if j.coluna == "PROC").ciap_cid == ()


def test_checkbox_based_ciap_multiselect_is_supported():
    html = with_ciap_control(
        '<input type="checkbox" name="lsCid" value="A01">'
        '<input type="checkbox" name="lsCid" value="B02">'
    )
    page = parse_page(html, URL)
    assert page.ciap_cid is not None
    assert page.ciap_cid.multiselect
    assert next(prepare("federal", None, page, args()).jobs()).ciap_cid == ("A01", "B02")


def test_hidden_modal_ciap_select_is_detected_from_context():
    html = with_ciap_control(
        '<div id="ciapCidModal" style="display:none">'
        '<label>CIAP/CID</label>'
        '<select name="form:codigo" multiple>'
        '<option value="A01">A01</option><option value="B02">B02</option>'
        '</select></div>'
    )
    page = parse_page(html, URL)
    assert page.ciap_cid is not None
    assert page.ciap_cid.name == "form:codigo"
    assert next(prepare("federal", None, page, args()).jobs()).ciap_cid == ("A01", "B02")
