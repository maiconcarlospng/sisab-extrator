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
