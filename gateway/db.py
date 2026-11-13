"""Warstwa danych: jeden adapter, trzy tryby uruchomienia (bez demona systemowego).

WM_DB=
  sqlite:///.run/wm.db                 - zero zależności (testy, CI)
  postgresql://postgres@127.0.0.1:5432/postgres
                                       - dowolny Postgres, w tym PGlite przez @electric-sql/pglite-socket
                                         (WASM, jeden proces, katalog danych jak plik SQLite)
  embedded:///.run/pgdata              - prawdziwy Postgres startowany jako proces potomny gatewaya
                                         (pip: pgembed / pgserver / pg0-embedded), zamykany razem z nim
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

ROOT = Path(os.environ.get("POLYCELL_ROOT", Path(__file__).resolve().parents[1]))


def _embedded_uri(datadir: str) -> str:
    Path(datadir).mkdir(parents=True, exist_ok=True)
    for mod in ("pgembed", "pgserver"):
        try:
            m = __import__(mod)
            return m.get_server(datadir, cleanup_mode="stop").get_uri()
        except ImportError:
            continue
    try:
        from pg0 import Pg0
        pg = Pg0(data_dir=datadir)
        pg.start()
        return pg.uri
    except ImportError as e:
        raise RuntimeError("embedded mode needs: pip install pgembed (or pgserver / pg0-embedded)") from e


class DB:
    def __init__(self, url: str | None = None):
        self.url = url or os.environ.get("WM_DB", f"sqlite:///{ROOT}/.run/wm.db")
        self.lock = threading.Lock()
        if self.url.startswith("sqlite://"):
            path = self.url.removeprefix("sqlite://")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.kind, self.ph = "sqlite", "?"
            self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self.conn.execute("pragma journal_mode=wal")
            self.conn.executescript((ROOT / "gen/sql/schema.sqlite.sql").read_text())
            return
        if self.url.startswith("embedded://"):
            self.url = _embedded_uri(self.url.removeprefix("embedded://"))
        import psycopg
        self.kind, self.ph = "postgres", "%s"
        # PGlite obsługuje jedno połączenie - używamy jednego, chronionego lockiem (wystarcza i jest szybkie).
        self.conn = psycopg.connect(self.url, autocommit=True)
        for stmt in (ROOT / "gen/sql/schema.postgres.sql").read_text().split(";"):
            body = "\n".join(ln for ln in stmt.splitlines() if not ln.strip().startswith("--")).strip()
            if body:
                self.conn.execute(body)

    def insert(self, table: str, row: dict, json_cols: set[str] = frozenset()) -> None:
        cols = list(row)
        vals = [json.dumps(v, ensure_ascii=False) if c in json_cols and v is not None else v for c, v in row.items()]
        marks = [f"{self.ph}::jsonb" if (self.kind == "postgres" and c in json_cols) else self.ph for c in cols]
        sql = f"insert into {table} ({', '.join(cols)}) values ({', '.join(marks)})"
        with self.lock:
            self.conn.execute(sql, vals)

    def query(self, sql: str, args: tuple = ()) -> list[dict]:
        with self.lock:
            cur = self.conn.execute(sql.replace("?", self.ph), args)
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]
