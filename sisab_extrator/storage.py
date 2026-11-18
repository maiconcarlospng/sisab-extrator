"""Controle de downloads e localização dos arquivos."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

from .model import Job


class Catalog:
    def __init__(self, data_dir: Path):
        self.root = data_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.root / "consultas.sqlite")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS consultas (
            id TEXT PRIMARY KEY,
            competencia TEXT NOT NULL,
            ano INTEGER NOT NULL,
            relatorio TEXT NOT NULL,
            especificacao TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pendente',
            raw_path TEXT,
            parquet_path TEXT,
            linhas INTEGER DEFAULT 0,
            erro TEXT,
            atualizada_em TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        self.conn.execute("CREATE INDEX IF NOT EXISTS ix_consultas_mes ON consultas(competencia, status)")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def add_jobs(self, jobs: Iterable[Job]) -> None:
        self.conn.executemany("""INSERT OR IGNORE INTO consultas
            (id, competencia, ano, relatorio, especificacao, status)
            VALUES (?,?,?,?,?, 'pendente')""",
            ((j.key, j.competencia, j.ano, j.report, json.dumps(j.to_dict(), ensure_ascii=False, sort_keys=True)) for j in jobs))
        self.conn.commit()

    def get(self, key: str):
        return self.conn.execute("SELECT * FROM consultas WHERE id = ?", (key,)).fetchone()

    def update(self, key: str, status: str, *, raw: str | None = None,
               parquet: str | None = None, linhas: int = 0, erro: str | None = None) -> None:
        self.conn.execute("""UPDATE consultas SET status = ?, raw_path = COALESCE(?, raw_path),
            parquet_path = COALESCE(?, parquet_path), linhas = ?, erro = ?,
            atualizada_em = CURRENT_TIMESTAMP WHERE id = ?""",
                          (status, raw, parquet, linhas, erro, key))
        self.conn.commit()

    def rows(self, start: str | None = None, end: str | None = None):
        query = "SELECT * FROM consultas WHERE 1=1"
        params: list[str] = []
        if start:
            query += " AND competencia >= ?"
            params.append(start)
        if end:
            query += " AND competencia <= ?"
            params.append(end)
        query += " ORDER BY competencia, relatorio, id"
        return self.conn.execute(query, params).fetchall()

    def summary(self, start: str | None = None, end: str | None = None) -> dict:
        rows = self.rows(start, end)
        result: dict[str, int] = {}
        for row in rows:
            result[row["status"]] = result.get(row["status"], 0) + 1
        return {"consultas": len(rows), "por_status": result}


def raw_path(root: Path, job: Job) -> Path:
    return root / "brutos" / job.report / job.competencia[:4] / job.competencia / f"{job.key}.csv.zip"


def parquet_path(root: Path, job: Job) -> Path:
    return root / "mensal" / job.report / job.competencia[:4] / job.competencia / f"{job.key}.parquet"


def save_raw_zip(path: Path, content: bytes, job: Job) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", prefix=".tmp-", dir=path.parent, delete=False) as f:
            temp_name = f.name
        with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.writestr("resposta_original.csv", content)
            z.writestr("metadados.json", json.dumps(job.to_dict(), ensure_ascii=False, indent=2))
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def read_raw_zip(path: Path) -> bytes:
    with zipfile.ZipFile(path) as z:
        return z.read("resposta_original.csv")
