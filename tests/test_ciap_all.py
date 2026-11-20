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


def test_preloaded_ciap_modal_with_distinct_checkbox_names_is_diagnosed(tmp_path):
    """Estrutura observada no SISAB: hidden lsCid + checkbox cid-W235-1."""
    html = with_ciap_control(
        '<input type="hidden" id="lsCid" name="lsCid" value="">'
        '<div id="modal-default-cid" style="display:none">'
        '<input type="checkbox" name="cid-W235-1" id="cid-W235-1" value="W235">'
        '<input type="checkbox" name="cid-W236-1" id="cid-W236-1" value="W236">'
        '<input type="checkbox" name="cid-N72-1" id="cid-N72-1" value="N72">'
        '</div>'
    )
    page = parse_page(html, URL)
    assert page.ciap_modal is not None
    assert page.ciap_modal["quantidade_checkboxes"] == 3
    assert page.ciap_modal["campo_oculto"] == "lsCid"
    assert page.ciap_modal["serializacao_confirmada"] is False
    assert page.ciap_cid is None

    client = Client(URL, delay=0, retries=0, diagnostics_dir=tmp_path)
    client.page = page
    client._last_html = html

    def fail_if_requested(*unused, **kwargs):
        pytest.fail("Modal preloaded: não deve executar JSF/AJAX imaginário nem CSV")

    client._request = fail_if_requested
    with pytest.raises(PortalError, match="campo oculto lsCid"):
        prepare("federal", client, page, args())
    diagnostic = (tmp_path / "diagnostico_ciap_federal.json").read_text(
        encoding="utf-8"
    )
    assert '"quantidade_checkboxes": 3' in diagnostic
    assert "JSF123" not in diagnostic


def _real_sisab_modal_html():
    """Replica os atributos e o JavaScript observados no SISAB."""
    return with_ciap_control(
        '<input id="lsCid" name="lsCid" type="hidden" value="">'
        '<div id="modal-default-cid" style="display:none">'
        '<input type="checkbox" id="cid-W235-1" name="cid-W235-1" '
        'onclick="addCid(&#39;W235-1&#39;)">'
        '<input type="checkbox" id="cid-N72-1" name="cid-N72-1" '
        'onclick="addCid(&#39;N72-1&#39;)">'
        '<input type="checkbox" id="cid-59-1" name="cid-59-1" '
        'onclick="addCid(&#39;59-1&#39;)">'
        '</div><script>'
        'var lsCid = ""; '
        'function addCid(cid) {'
        ' if (lsCid.search(cid+",")>=0) { lsCid=lsCid.replace(cid+",",""); }'
        ' else { lsCid += cid+","; }'
        " document.getElementById('lsCid').value = lsCid;"
        '}</script>'
    )


def test_real_sisab_hidden_field_modal_and_addcid_are_parsed():
    page = parse_page(_real_sisab_modal_html(), URL)
    assert page.ciap_modal["serializacao_confirmada"] is True
    assert page.ciap_modal["quantidade_selecionavel"] == 3
    assert page.ciap_cid.name == "lsCid"
    assert page.ciap_cid.serialization == "comma_trailing"
    assert list(page.ciap_cid.options) == ["W235-1", "N72-1", "59-1"]
    assert next(prepare("federal", None, page, args()).jobs()).ciap_cid == (
        "W235-1", "N72-1", "59-1"
    )


def test_real_sisab_post_writes_single_comma_terminated_hidden_lscid():
    page = parse_page(_real_sisab_modal_html(), URL)
    job = next(prepare("federal", None, page, args()).jobs())
    client = Client(URL, delay=0, retries=0)
    client.page = page
    sent = []

    class Response:
        content = b"Uf;Ibge;Municipio;CID;\nMG;3146107;Ouro Preto;10;\n"
        headers = {"Content-Type": "text/csv"}

    def fake_request(method, url, **kwargs):
        assert method == "POST"
        sent.extend(kwargs["data"])
        return Response()

    client._request = fake_request
    assert client.download(job) == Response.content
    assert [value for name, value in sent if name == "lsCid"] == [
        "W235-1,N72-1,59-1,"
    ]
    assert ("cid-W235-1", "on") not in sent
    assert ("lsCid", "") not in sent


def test_modal_without_addcid_serialization_never_guesses_lscid(tmp_path):
    html = _real_sisab_modal_html().replace(
        "lsCid += cid+\",\";", "lsCid += cid;"
    )
    page = parse_page(html, URL)
    assert page.ciap_modal["serializacao_confirmada"] is False
    assert page.ciap_cid is None
    client = Client(URL, delay=0, retries=0, diagnostics_dir=tmp_path)
    client.page = page
    client._last_html = html
    client._request = lambda *a, **kw: pytest.fail("Nunca enviar POST.")
    with pytest.raises(PortalError, match="campo oculto lsCid"):
        prepare("federal", client, page, args())
