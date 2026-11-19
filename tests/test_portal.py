import pytest
from sisab_extrator.portal import parse_page, PortalError, check_url

URL = "https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/saude/RelSauProducao.xhtml"
HTML = """
<form id="j_idt44" action="/paginas/acessoRestrito/relatorio/federal/saude/RelSauProducao.xhtml">
<input type="hidden" name="javax.faces.ViewState" value="JSF123">
<span id="competencia"><select name="form:competencia" id="form:competencia">
<option value="202401">Jan/2024</option><option value="202402">Fev/2024</option>
</select></span>
<select id="selectLinha" name="selectLinha">
<option value="">Selecione...</option><option value="MUN.CO_MUNICIPIO_IBGE">Município</option>
</select>
<select id="selectcoluna" name="selectcoluna">
<option value="">Selecione...</option><option value="CID">CIAP/CID</option>
<option value="PROC">Procedimento</option>
</select>
<a onclick="mojarra.jsfcljs(document.getElementById('j_idt44'),{'j_idt99':'j_idt99'},'');return false">CSV</a>
</form>
"""


def test_find_jsf_form_and_enumerate_columns():
    p = parse_page(HTML, URL)
    assert p.view_state == "JSF123"
    assert p.csv_button == "j_idt99"
    assert p.competencia.name == "form:competencia"
    assert p.coluna.choose("CIAP/CID") == [("CID", "CIAP/CID")]
    assert p.linha.choose("Municipio") == [("MUN.CO_MUNICIPIO_IBGE", "Município")]
    assert len(p.coluna.choose("all")) == 2


def test_no_jsf_viewstate_fails_honestly():
    with pytest.raises(PortalError):
        parse_page("<html>sem formulário</html>", URL)


def test_refuse_other_domains():
    with pytest.raises(ValueError):
        check_url("https://example.com/data.xhtml")
    with pytest.raises(ValueError):
        check_url("http://sisab.saude.gov.br/index.xhtml")


def test_unknown_field_fails_without_guessing():
    p = parse_page(HTML, URL)
    with pytest.raises(ValueError):
        p.coluna.choose("CID-10 nivel individual")


def test_selects_report_form_instead_of_first_jsf_form():
    html = (
        '<html><head><title>Relatório de Saúde</title></head><body>'
        '<form id="login"><input type="hidden" name="javax.faces.ViewState" value="LOGIN"></form>'
        + HTML.replace('value="JSF123"', 'value="REPORT"') +
        '</body></html>'
    )
    p = parse_page(html, URL)
    assert p.form_id == "j_idt44"
    assert p.view_state == "REPORT"


def test_aliases_and_accented_field_identifiers():
    html = (HTML.replace('name="form:competencia" id="form:competencia"',
                         'name="form:competência" id="form:competência"')
                .replace('id="selectLinha" name="selectLinha"',
                         'id="form:linha" name="form:linha"')
                .replace('id="selectcoluna" name="selectcoluna"',
                         'id="form:coluna" name="form:coluna"'))
    page = parse_page(html, URL)
    assert page.linha.name == "form:linha"
    assert page.coluna.name == "form:coluna"
    assert "202401" in page.competencia.options


def test_bad_html_creates_safe_diagnostic_file(tmp_path):
    import json
    from sisab_extrator.portal import Client

    class Response:
        url = "https://sisab.saude.gov.br/acesso/login.xhtml?token=sensitive"
        status_code = 200
        headers = {"Content-Type": "text/html"}
        encoding = "utf-8"
        text = ('<title>Entrar no sistema</title><form id="login">'
                '<input type="hidden" name="javax.faces.ViewState" value="SECRET"></form>')

    client = Client(URL, delay=0, diagnostics_dir=tmp_path)
    client._request = lambda *args, **kwargs: Response()
    with pytest.raises(PortalError, match="diagnostico_federal.json"):
        client.open()
    diagnostic = json.loads((tmp_path / "diagnostico_federal.json").read_text(encoding="utf-8"))
    assert diagnostic["titulo_pagina"] == "Entrar no sistema"
    assert diagnostic["url_recebida"].endswith("/acesso/login.xhtml")
    assert diagnostic["formularios"][0]["id"] == "login"
    assert "SECRET" not in json.dumps(diagnostic)
    assert "sensitive" not in json.dumps(diagnostic)


def test_html_instead_of_csv_writes_export_diagnostic(tmp_path):
    """Uma página HTTP 200 não deve ser confundida com CSV exportado."""
    import json
    from sisab_extrator.portal import Client
    from test_model import example_job

    class Response:
        url = URL + "?session_token=SECRET"
        status_code = 200
        headers = {"Content-Type": "text/html;charset=UTF-8"}
        text = (
            "<html><head><title>Relatório SISAB</title></head><body>"
            "<div class='ui-messages-error-summary'>Selecione um filtro válido.</div>"
            "<form id='j_idt44'>"
            "<input type='hidden' name='javax.faces.ViewState' value='SECRET'>"
            "<select name='selectcoluna' id='selectcoluna'><option>CID</option></select>"
            "</form></body></html>"
        )
        content = text.encode("utf-8")

    client = Client(URL, delay=0, retries=0, diagnostics_dir=tmp_path)
    client.page = parse_page(HTML, URL)
    client._request = lambda *args, **kwargs: Response()
    with pytest.raises(PortalError, match="diagnostico_exportacao_federal.json"):
        client.download(example_job(coluna="CID"))
    diagnostic = json.loads(
        (tmp_path / "diagnostico_exportacao_federal.json").read_text(encoding="utf-8")
    )
    assert diagnostic["operacao"] == "exportacao_csv"
    assert diagnostic["tipo_conteudo"].startswith("text/html")
    assert diagnostic["consulta"]["competencia"] == "202401"
    assert diagnostic["consulta"]["coluna"] == "CIAP/CID"
    assert diagnostic["campos_enviados"]["botao_csv"] == "j_idt99"
    assert diagnostic["mensagens_portal"] == ["Selecione um filtro válido."]
    assert diagnostic["url_recebida"] == URL
    assert diagnostic["tamanho_bytes"] == len(Response.content)
    assert "SECRET" not in json.dumps(diagnostic)


def test_explicit_no_data_stays_no_data_without_diagnostic(tmp_path):
    from sisab_extrator.portal import Client, NoData
    from test_model import example_job

    class Response:
        content = "A consulta não retornou nenhum dado".encode("utf-8")
        headers = {"Content-Type": "text/html"}

    client = Client(URL, delay=0, retries=0, diagnostics_dir=tmp_path)
    client.page = parse_page(HTML, URL)
    client._request = lambda *args, **kwargs: Response()
    with pytest.raises(NoData):
        client.download(example_job())
    assert not list(tmp_path.glob("diagnostico_exportacao_*.json"))
