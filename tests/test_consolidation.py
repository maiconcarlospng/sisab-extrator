from pathlib import Path
import pytest
from test_model import example_job
from sisab_extrator.storage import Catalog, parquet_path
from sisab_extrator.parquet import write_monthly, consolidate

pytest.importorskip("pyarrow")


def test_monthly_annual_and_series(tmp_path: Path):
    data = tmp_path / "data"
    cat = Catalog(data)
    jobs = [example_job(competencia="202312"), example_job(competencia="202401")]
    csv = b"Uf;Ibge;Municipio;E11;\nMG;3146107;Ouro Preto;3;\n"
    try:
        cat.add_jobs(jobs)
        for j in jobs:
            p = parquet_path(data, j)
            n = write_monthly(p, csv, j)
            cat.update(j.key, "ok", parquet=str(p), linhas=n)
        res = consolidate(cat, "202312", "202401")
        assert res["serie"]["linhas"] == 2
        assert (data / "consolidado/anual/sisab_2023.parquet").exists()
        assert (data / "consolidado/anual/sisab_2024.parquet").exists()
        assert (data / "consolidado/serie/sisab_202312_202401.parquet").exists()
    finally:
        cat.close()


def test_dont_consolidate_incomplete(tmp_path: Path):
    cat = Catalog(tmp_path)
    try:
        cat.add_jobs([example_job()])
        with pytest.raises(ValueError, match="bloqueada"):
            consolidate(cat, "202401", "202401")
    finally:
        cat.close()
