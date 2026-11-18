from pathlib import Path
from sisab_extrator.storage import Catalog, raw_path, read_raw_zip, save_raw_zip
from test_model import example_job


def test_catalog_and_resume(tmp_path: Path):
    c = Catalog(tmp_path)
    j = example_job()
    try:
        c.add_jobs([j, j])
        assert c.summary()["consultas"] == 1
        assert c.get(j.key)["status"] == "pendente"
        c.update(j.key, "ok", linhas=8)
        assert c.get(j.key)["linhas"] == 8
        assert c.summary()["por_status"]["ok"] == 1
    finally:
        c.close()


def test_raw_original_bytes_preserved(tmp_path: Path):
    j = example_job()
    path = raw_path(tmp_path, j)
    b = "Uf;Ibge;Municipio;E11\nMG;3146107;Ouro Preto;3\n".encode("iso-8859-1")
    save_raw_zip(path, b, j)
    assert read_raw_zip(path) == b
