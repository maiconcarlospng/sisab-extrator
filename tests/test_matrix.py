from types import SimpleNamespace

from sisab_extrator.cli import prepare
from sisab_extrator.portal import parse_page
from test_portal import HTML, URL


def test_prepare_uses_only_validated_pairs(tmp_path):
    matrix = tmp_path / "compatibilidade.json"
    matrix.write_text(
        '{"combinacoes": ['
        '{"relatorio":"federal","linha":"MUN.CO_MUNICIPIO_IBGE",'
        '"coluna":"PROC","status":"valida"},'
        '{"relatorio":"municipal","linha":"MUN.CO_MUNICIPIO_IBGE",'
        '"coluna":"CID","status":"valida"}]}',
        encoding="utf-8",
    )
    args = SimpleNamespace(
        start="202401", end="202401", lines="all", columns="all",
        ages="none", sexes="none", production_type="none",
        ciap_cid="none", compatibility_matrix=matrix,
    )
    page = parse_page(HTML, URL)
    prepared = prepare("federal", None, page, args)
    assert [(job.linha, job.coluna) for job in prepared.jobs()] == [
        ("MUN.CO_MUNICIPIO_IBGE", "PROC")
    ]
