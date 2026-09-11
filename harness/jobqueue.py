"""Crash-safe SQLite job queue for unattended runs (results/queue.sqlite).

One row per job. Status: pending -> running -> done | failed | timeout.

Durability: WAL journal with synchronous=FULL and one short transaction per state change, so a
killed runner, a reboot or a power loss leaves the file consistent. Rows a dead runner left
'running' go back to 'pending' on the next start (reset_stale); 'done' rows are never claimed
again. `attempts` counts finished attempts that failed or timed out; the runner retries a job
until it reaches max_attempts, after which the row keeps its final status and error.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from monty.json import MontyDecoder, MontyEncoder

from harness.config import QUEUE_DB

STATUSES = ("pending", "running", "done", "failed", "timeout")

SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    suite       TEXT NOT NULL,
    job_key     TEXT NOT NULL UNIQUE,
    inputs      TEXT NOT NULL,              -- JSON (monty): everything the worker and recorder need
    status      TEXT NOT NULL DEFAULT 'pending',
    attempts    INTEGER NOT NULL DEFAULT 0, -- finished attempts that failed or timed out
    priority    INTEGER NOT NULL DEFAULT 0, -- lower runs first
    n_atoms     INTEGER,
    runtime_s   REAL,
    error       TEXT,
    error_type  TEXT,
    model       TEXT,
    settings    TEXT,                       -- JSON: device, dtype, settings tag, relax settings
    created_at  TEXT,
    started_at  TEXT,
    finished_at TEXT,
    worker_pid  INTEGER,
    run_id      TEXT
);
CREATE INDEX IF NOT EXISTS queue_claim ON queue (status, priority, id);
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    mode        TEXT,
    pid         INTEGER,
    workers     INTEGER,
    threads     INTEGER,
    started_at  TEXT,
    finished_at TEXT,
    status      TEXT,                       -- running | finished | stopped | crashed
    n_done      INTEGER,
    n_failed    INTEGER,
    report_dir  TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(path: Path | str = QUEUE_DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=60, isolation_level=None)  # autocommit; explicit BEGIN for batches
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.executescript(SCHEMA)
    try:
        yield con
    finally:
        con.close()


def classify_error(msg: str | None) -> str | None:
    """Group error messages for `status`: exception class, or a fixed label for runner-level errors."""
    if not msg:
        return None
    m = msg.strip()
    low = m.lower()
    if low.startswith("post-processing error:"):
        return "post-processing: " + (classify_error(m.split(":", 1)[1]) or "other")
    if low.startswith(("worker crashed", "worker pool broke")):
        return "worker crash"
    if low.startswith("hard timeout"):
        return "hard timeout (watchdog)"
    head = m.split(":", 1)[0].strip()
    return head if head.isidentifier() else "other"


# --- filling -------------------------------------------------------------------------------------

def enqueue(jobs: list[dict], path: Path | str = QUEUE_DB, done_keys: set[str] | frozenset = frozenset()) -> dict:
    """Insert jobs ({suite, job_key, inputs, priority, n_atoms, model, settings}); existing keys are left
    untouched (idempotent). Keys in done_keys (finished outside the queue) are inserted as 'done'."""
    added = already = pre_done = 0
    with connect(path) as con:
        con.execute("BEGIN IMMEDIATE")
        for j in jobs:
            status = "done" if j["job_key"] in done_keys else "pending"
            cur = con.execute(
                "INSERT OR IGNORE INTO queue (suite, job_key, inputs, status, priority, n_atoms, model, settings, "
                "created_at, error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (j["suite"], j["job_key"], json.dumps(j["inputs"], cls=MontyEncoder), status, int(j.get("priority", 0)),
                 j.get("n_atoms"), j.get("model"), json.dumps(j.get("settings"), default=str), now(),
                 "completed before it was queued" if status == "done" else None))
            if cur.rowcount:
                added += 1
                pre_done += status == "done"
            else:
                already += 1
        con.execute("COMMIT")
    return {"added": added, "already_queued": already, "already_done": pre_done}


def mark_done(keys: set[str], path: Path | str = QUEUE_DB) -> int:
    """Mark pending rows done when their results already exist (never redo finished work)."""
    keys = list(keys)
    n = 0
    with connect(path) as con:
        con.execute("BEGIN IMMEDIATE")
        for i in range(0, len(keys), 500):
            chunk = keys[i:i + 500]
            cur = con.execute(
                f"UPDATE queue SET status='done', error='completed outside the queue', finished_at=? "
                f"WHERE status='pending' AND job_key IN ({','.join('?' * len(chunk))})", [now(), *chunk])
            n += cur.rowcount
        con.execute("COMMIT")
    return n


# --- running -------------------------------------------------------------------------------------

def reset_stale(path: Path | str = QUEUE_DB) -> int:
    """'running' rows left by a dead runner go back to 'pending' (not counted as an attempt)."""
    with connect(path) as con:
        return con.execute("UPDATE queue SET status='pending', started_at=NULL, worker_pid=NULL "
                           "WHERE status='running'").rowcount


def claim(n: int, run_id: str, path: Path | str = QUEUE_DB) -> list[dict]:
    if n <= 0:
        return []
    with connect(path) as con:
        con.execute("BEGIN IMMEDIATE")
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM queue WHERE status='pending' ORDER BY priority, id LIMIT ?", (n,))]
        ts = now()
        for r in rows:
            con.execute("UPDATE queue SET status='running', started_at=?, run_id=? WHERE id=?", (ts, run_id, r["id"]))
            r.update(status="running", started_at=ts, run_id=run_id)
        con.execute("COMMIT")
    return rows


def decode_inputs(row: dict) -> dict:
    return json.loads(row["inputs"], cls=MontyDecoder)


def finish(job_id: int, status: str, path: Path | str = QUEUE_DB, runtime_s: float | None = None,
           error: str | None = None, attempts: int | None = None, worker_pid: int | None = None) -> None:
    assert status in ("done", "failed", "timeout"), status
    with connect(path) as con:
        con.execute("UPDATE queue SET status=?, runtime_s=?, error=?, error_type=?, finished_at=?, worker_pid=?, "
                    "attempts=COALESCE(?, attempts) WHERE id=?",
                    (status, runtime_s, error, classify_error(error), now(), worker_pid, attempts, job_id))


def requeue_failed(path: Path | str = QUEUE_DB, suite: str | None = None) -> int:
    """Put failed / timed-out rows back to pending with a fresh attempt budget (after a fix). The old
    error stays in the row, prefixed, until the job finishes again."""
    with connect(path) as con:
        q = ("UPDATE queue SET status='pending', attempts=0, started_at=NULL, finished_at=NULL, worker_pid=NULL, "
             "error='requeued after: ' || COALESCE(error, '') WHERE status IN ('failed','timeout')")
        return con.execute(q + (" AND suite=?" if suite else ""), (suite,) if suite else ()).rowcount


def requeue(job_id: int, path: Path | str = QUEUE_DB, error: str | None = None, count_attempt: bool = True) -> None:
    with connect(path) as con:
        con.execute("UPDATE queue SET status='pending', started_at=NULL, worker_pid=NULL, error=?, error_type=?, "
                    "attempts=attempts+? WHERE id=?", (error, classify_error(error), int(count_attempt), job_id))


# --- runs ----------------------------------------------------------------------------------------

def start_run(run_id: str, mode: str, pid: int, workers: int, threads: int, path: Path | str = QUEUE_DB) -> None:
    with connect(path) as con:
        con.execute("INSERT OR REPLACE INTO runs (run_id, mode, pid, workers, threads, started_at, status) "
                    "VALUES (?,?,?,?,?,?, 'running')", (run_id, mode, pid, workers, threads, now()))


def end_run(run_id: str, status: str, n_done: int, n_failed: int, report_dir: str | None,
            path: Path | str = QUEUE_DB) -> None:
    with connect(path) as con:
        con.execute("UPDATE runs SET finished_at=?, status=?, n_done=?, n_failed=?, report_dir=? WHERE run_id=?",
                    (now(), status, n_done, n_failed, report_dir, run_id))


def last_runs(path: Path | str = QUEUE_DB, n: int = 5) -> list[dict]:
    with connect(path) as con:
        return [dict(r) for r in con.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (n,))]


# --- statistics ----------------------------------------------------------------------------------

def counts(path: Path | str = QUEUE_DB) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    with connect(path) as con:
        for r in con.execute("SELECT suite, status, COUNT(*) AS n FROM queue GROUP BY suite, status"):
            out.setdefault(r["suite"], {})[r["status"]] = r["n"]
    return out


def suites(path: Path | str = QUEUE_DB) -> list[str]:
    with connect(path) as con:
        return [r["suite"] for r in con.execute("SELECT DISTINCT suite FROM queue")]


def median_runtime(path: Path | str = QUEUE_DB, suite: str | None = None) -> float | None:
    with connect(path) as con:
        q = "SELECT runtime_s FROM queue WHERE status='done' AND runtime_s IS NOT NULL" + (" AND suite=?" if suite else "")
        vals = [r["runtime_s"] for r in con.execute(q, (suite,) if suite else ())]
    return float(median(vals)) if vals else None


def failures_by_type(path: Path | str = QUEUE_DB) -> list[dict]:
    with connect(path) as con:
        return [dict(r) for r in con.execute(
            "SELECT error_type, COUNT(*) AS n, MIN(error) AS example, GROUP_CONCAT(DISTINCT suite) AS suites "
            "FROM queue WHERE status IN ('failed','timeout') GROUP BY error_type ORDER BY n DESC")]


def pending_retries(path: Path | str = QUEUE_DB) -> int:
    with connect(path) as con:
        return con.execute("SELECT COUNT(*) FROM queue WHERE status='pending' AND attempts > 0").fetchone()[0]
