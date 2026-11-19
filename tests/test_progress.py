"""Progresso de consultas e da conversão Parquet, sem acesso ao SISAB."""
import logging

from sisab_extrator.cli import _log_download_progress, _log_download_step
from sisab_extrator.parquet import write_monthly_from_zip
from sisab_extrator.storage import raw_path, save_raw_zip
from test_model import example_job


def test_log_progress_is_based_on_completed_queries(caplog):
    with caplog.at_level(logging.INFO, logger="sisab_extrator"):
        _log_download_step(1, 2, 2, "Solicitando CSV")
        _log_download_progress(1, 2, 1, 0, 0, 0.0)
        _log_download_progress(2, 2, 1, 0, 1, 0.0)
    assert "Consulta 1/2 | ETAPA 2/5 | Solicitando CSV" in caplog.text
    assert "1/2 consultas finalizadas (50.0%)" in caplog.text
    assert "2/2 consultas finalizadas (100.0%)" in caplog.text
    assert "erros: 1" in caplog.text


def test_parquet_reports_cumulative_written_rows(tmp_path):
    job = example_job()
    # 3 medidas para primeiro município, 2 para segundo = 5 registros.
    csv = (
        "UF;Ibge;Municipio;E11;I10;Total;\n"
        "MG;3146107;Ouro Preto;2;0;2;\n"
        "MG;3140000;Mariana;-;8;8;\n"
    )
    zip_path = raw_path(tmp_path, job)
    save_raw_zip(zip_path, csv.encode("utf-8"), job)
    observed = []
    output = tmp_path / "teste.parquet"
    total = write_monthly_from_zip(
        output, zip_path, job, batch_size=2,
        progress_callback=observed.append,
    )
    assert total == 5
    assert observed == [2, 4, 5]
    assert output.is_file()
