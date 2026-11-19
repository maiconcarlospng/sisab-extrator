"""Validação de Tipo de Produção a partir do formulário real (fixture local)."""
from types import SimpleNamespace

import pytest

from sisab_extrator.cli import prepare
from sisab_extrator.portal import Client, PortalError, parse_page
from test_model import example_job
from test_portal import HTML, URL


HTML_COM_TIPO = HTML.replace(
    "</form>",
    "<select id='tpProducao' name='tpProducao'>"
    "<option value=''>Selecione</option>"
    "<option value='1'>Atendimento Individual</option>"
    "<option value='7'>Procedimento</option>"
    "</select></form>",
)


def args(tipo_producao="none"):
    return SimpleNamespace(
        start="202401", end="202401", lines="Municipio",
        columns="CIAP/CID", ages="none", sexes="none",
        production_type=tipo_producao,
    )


def test_inspection_exposes_tipo_producao_values():
    page = parse_page(HTML_COM_TIPO, URL)
    assert page.tipo_producao is not None
    assert page.tipo_producao.options["1"] == "Atendimento Individual"
    assert page.as_dict()["tipo_producao"]["options"]["7"] == "Procedimento"


def test_no_production_filter_is_rejected_before_download():
    page = parse_page(HTML_COM_TIPO, URL)
    with pytest.raises(ValueError, match="Tipo de Produção"):
        prepare("municipal", None, page, args())


def test_explicit_production_filter_produces_separate_job():
    page = parse_page(HTML_COM_TIPO, URL)
    p = prepare("municipal", None, page, args("Atendimento Individual"))
    assert p.count == 1
    j = next(p.jobs())
    assert j.tipo_producao == "1"
    assert j.tipo_producao_label == "Atendimento Individual"
    assert j.key != example_job().key


def test_all_production_types_yield_separate_jobs_not_merged():
    page = parse_page(HTML_COM_TIPO, URL)
    p = prepare("municipal", None, page, args("all"))
    jobs = list(p.jobs())
    assert p.count == 2
    assert {j.tipo_producao for j in jobs} == {"1", "7"}
    assert len({j.key for j in jobs}) == 2


def test_post_contains_exact_type_selected_from_page():
    page = parse_page(HTML_COM_TIPO, URL)
    client = Client(URL, retries=0, delay=0)
    client.page = page
    job = next(prepare("municipal", None, page, args("Atendimento Individual")).jobs())
    calls = []

    class CsvResponse:
        content = b"Uf;Ibge;Municipio;Atendimento Individual\nMG;3146107;Ouro Preto;1\n"
        headers = {"Content-Type": "text/csv"}

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return CsvResponse()

    client._request = request
    assert client.download(job).startswith(b"Uf;Ibge")
    assert len(calls) == 1
    assert ("tpProducao", "1") in calls[0][2]["data"]
    assert ("tpProducao", "") not in calls[0][2]["data"]


def test_direct_client_refuses_blank_production_filter():
    page = parse_page(HTML_COM_TIPO, URL)
    client = Client(URL, delay=0)
    client.page = page
    client._request = lambda *args, **kwargs: pytest.fail("Não deve fazer POST")
    with pytest.raises(PortalError, match="Tipo de Produção"):
        client.download(example_job())
