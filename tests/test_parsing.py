import pytest
from sisab_extrator.parquet import br_number, normalizar, table_rows
from test_model import example_job

CSV = ("RELATÓRIO DE SAÚDE\n"
       "Competência: 202401\n"
       "Uf;Ibge;Municipio;E11;I10;Total;\n"
       "MG;3146107;Ouro Preto;1.234;0;1.234;\n"
       "MG;3140000;Mariana;-;8;8;\n")


def test_keep_zeros_and_missing_separate():
    rows = list(normalizar(CSV.encode("iso-8859-1"), example_job()))
    assert len(rows) == 5
    assert any(x["categoria"] == "I10" and x["valor"] == 0 for x in rows)
    assert not any(x["ibge"] == "3140000" and x["categoria"] == "E11" for x in rows)
    assert next(x for x in rows if x["categoria"] == "E11")["valor"] == 1234
    assert all(x["consulta_id"] == example_job().key for x in rows)


def test_table_after_metadata():
    entries = list(table_rows(CSV.encode("utf-8")))
    assert len(entries) == 2
    assert entries[0][2] == 3


@pytest.mark.parametrize("val,expected", [("2.340", 2340), ("0", 0), ("-", None), ("", None), ("*", None)])
def test_numbers(val, expected):
    assert br_number(val) == expected


def test_invalid_numeric_fails():
    with pytest.raises(ValueError):
        br_number("texto")


def test_nonstandard_header_fails_explicitly():
    with pytest.raises(ValueError):
        list(table_rows(b"Um relatorio;com muitos;campos\nX;Y;Z\n"))
