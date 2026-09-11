"""SQLite results store.

jobs:    one row per (suite, job_key) — status, runtime, full payload (JSON), settings.
         Resumability: a job with a row is skipped unless --retry-failed and it failed.
results: one row per structure x test (quantity), each value tagged with provenance.
         simulated_provenance is always "simulated"; reference_provenance is
         "mp_computed" (MP DFT), "experimental" (with citation), or "wbm_computed" (WBM DFT).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from monty.json import MontyEncoder

from harness.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    suite TEXT NOT NULL,
    job_key TEXT NOT NULL,
    status TEXT NOT NULL,          -- ok | failed | timeout | skipped
    error TEXT,
    runtime_s REAL,
    payload TEXT,                  -- JSON: relaxed structures, diagnostics
    settings TEXT,                 -- JSON: model, dtype, device, relax settings, threads
    finished_at TEXT,
    PRIMARY KEY (suite, job_key)
);
CREATE TABLE IF NOT EXISTS results (
    suite TEXT NOT NULL,
    job_key TEXT NOT NULL,
    structure TEXT NOT NULL,       -- human label, e.g. "Si->Ge (mp-149 -> mp-32)"
    formula TEXT,
    family TEXT,
    test TEXT NOT NULL,            -- quantity, e.g. "a", "vol_per_atom", "energy_per_atom"
    units TEXT,
    simulated_value REAL,
    simulated_provenance TEXT DEFAULT 'simulated',
    reference_value REAL,
    reference_provenance TEXT,     -- mp_computed | experimental | wbm_computed
    reference_source TEXT,         -- mp-id, DOI / citation, WBM id
    error_abs REAL,                -- simulated - reference
    error_pct REAL,
    flags TEXT,                    -- JSON: magnetic / transition_metal / f_electron / ...
    settings TEXT,                 -- JSON engine metadata for the simulated value
    runtime_s REAL,
    created_at TEXT,
    PRIMARY KEY (suite, job_key, test)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_DB_OVERRIDE: list[Path] = []


@contextmanager
def using(path: Path):
    """Read (and write) another results database inside this block — e.g. a pre-change snapshot."""
    _DB_OVERRIDE.append(Path(path))
    try:
        yield
    finally:
        _DB_OVERRIDE.pop()


def snapshot(dest: Path) -> Path:
    """Consistent copy of the live results database (sqlite online backup; safe while the runner writes)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(DB_PATH, timeout=60)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


@contextmanager
def connect(path: Path | None = None):
    path = Path(path) if path else (_DB_OVERRIDE[-1] if _DB_OVERRIDE else DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")  # the unattended runner writes while reports read
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def completed_keys(suite: str, retry_failed: bool = False) -> set[str]:
    with connect() as con:
        q = "SELECT job_key FROM jobs WHERE suite = ?" + (" AND status = 'ok'" if retry_failed else "")
        return {r["job_key"] for r in con.execute(q, (suite,))}


def record_job(suite: str, job_key: str, status: str, payload: dict | None = None, settings: dict | None = None,
               error: str | None = None, runtime_s: float | None = None) -> None:
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?)",
            (suite, job_key, status, error, runtime_s,
             json.dumps(payload, cls=MontyEncoder) if payload is not None else None,
             json.dumps(settings, default=str) if settings is not None else None, _now()),
        )


def record_results(rows: list[dict]) -> None:
    cols = ["suite", "job_key", "structure", "formula", "family", "test", "units", "simulated_value",
            "simulated_provenance", "reference_value", "reference_provenance", "reference_source",
            "error_abs", "error_pct", "flags", "settings", "runtime_s", "created_at"]
    with connect() as con:
        for r in rows:
            r = {"simulated_provenance": "simulated", "created_at": _now(), **r}
            for k in ("flags", "settings"):
                if r.get(k) is not None and not isinstance(r[k], str):
                    r[k] = json.dumps(r[k], default=str)
            con.execute(f"INSERT OR REPLACE INTO results ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                        [r.get(c) for c in cols])


def load_table(table: str, suite: str | None = None):
    import pandas as pd

    with connect() as con:
        q = f"SELECT * FROM {table}" + (" WHERE suite = ?" if suite else "")
        return pd.read_sql_query(q, con, params=(suite,) if suite else None)


def load_payloads(suite: str, status: str = "ok", tag: str | None = None) -> dict[str, dict]:
    """Payloads of finished jobs; with `tag`, only jobs run at that settings tag ("...@<tag>")."""
    from monty.json import MontyDecoder

    with connect() as con:
        rows = con.execute("SELECT job_key, payload FROM jobs WHERE suite=? AND status=?", (suite, status))
        return {r["job_key"]: json.loads(r["payload"], cls=MontyDecoder) for r in rows
                if r["payload"] and (tag is None or r["job_key"].endswith(f"@{tag}"))}
