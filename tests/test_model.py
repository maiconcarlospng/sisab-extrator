import pytest
from sisab_extrator.model import AGE_GROUPS, Job, months, parse_month


def example_job(**changes):
    args = dict(report="federal", url="https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/saude/RelSauProducao.xhtml",
                competencia="202401", linha="MUN.CO_MUNICIPIO_IBGE", linha_label="Municipio",
                coluna="CIAP_CID", coluna_label="CIAP/CID", faixa_etaria="De 20 a 24 anos",
                idade_inicio=20, idade_fim=24, tp_idade="ano", sexo="Feminino", sexo_valor="1")
    args.update(changes)
    return Job(**args)


def test_months_across_years():
    assert months("202312", "202402") == ["202312", "202401", "202402"]
    assert len(months("201801", "202512")) == 96


@pytest.mark.parametrize("invalid", ["202400", "202413", "1900", "xxxxxx", "2024-01"])
def test_invalid_month(invalid):
    with pytest.raises(ValueError):
        parse_month(invalid)


def test_ages_match_18_datasus_groups():
    assert len(AGE_GROUPS) == 18
    assert AGE_GROUPS[0][0] == "Menor de 1 ano"
    assert AGE_GROUPS[-1][0] == "80 anos ou mais"
    assert AGE_GROUPS[5][0] == "De 20 a 24 anos"


def test_job_id_is_deterministic_and_filter_sensitive():
    j = example_job()
    assert j.key == example_job().key
    assert j.key != example_job(sexo="Masculino", sexo_valor="0").key
    assert len(j.key) == 24
