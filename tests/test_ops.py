"""Operational safety: backup -> verify -> restore, retention, checkpoint, and interrupted queue writes (offline)."""

import sqlite3
import subprocess
import sys
import textwrap
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from harness import jobqueue, ops, store

ROOT = Path(__file__).resolve().parents[1]
RESTORE = ROOT / "scripts" / "restore.sh"


def _project(tmp_path) -> Path:
    root = tmp_path / "project"
    for d in ("reports", "config", "results"):
        (root / d).mkdir(parents=True)
    (root / "reports" / "r.md").write_text("# report\n")
    (root / "config" / "c.json").write_text("{}\n")
    with store.connect(root / "results" / "results.sqlite") as con:
        con.execute("INSERT INTO jobs (suite, job_key, status) VALUES ('ood', 'k@t', 'ok')")
    jobqueue.enqueue([{"suite": "ood", "job_key": "k@t", "inputs": {}}], root / "results" / "queue.sqlite")
    return root


def _restore(archive, target):
    return subprocess.run(["bash", str(RESTORE), str(archive), str(target)], capture_output=True, text=True)


def test_backup_verifies_and_restores(tmp_path):
    root = _project(tmp_path)
    info = ops.backup(root=root, dest=tmp_path / "dest")
    assert info["problems"] == [] and info["files"] == 4
    assert info["archive"].with_name(info["archive"].name + ".sha256").is_file()

    target = tmp_path / "restored"
    out = _restore(info["archive"], target)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "RESTORE OK" in out.stdout and "integrity_check ok" in out.stdout
    assert (target / "reports" / "r.md").read_text() == "# report\n"
    with closing(sqlite3.connect(target / "results" / "queue.sqlite")) as con:
        assert con.execute("SELECT job_key, status FROM queue").fetchall() == [("k@t", "pending")]
    assert _restore(info["archive"], target).returncode != 0  # never over a non-empty directory


def test_corrupt_archive_is_caught(tmp_path):
    info = ops.backup(root=_project(tmp_path), dest=tmp_path / "dest")
    a = info["archive"]
    data = bytearray(a.read_bytes())
    data[len(data) // 2] ^= 0xFF
    a.write_bytes(bytes(data))
    assert ops.verify_archive(a)
    out = _restore(a, tmp_path / "r1")
    assert out.returncode != 0 and "checksum mismatch" in out.stderr
    a.with_name(a.name + ".sha256").unlink()  # without the sidecar, extraction or the manifest must still catch it
    out = _restore(a, tmp_path / "r2")
    assert out.returncode != 0 and "RESTORE FAILED" in out.stderr


def test_prune_keeps_7_daily_and_4_weekly(tmp_path):
    newest = datetime(2026, 9, 14)  # a Monday
    for d in range(40):
        for hour in (7, 19):  # two backups a day
            name = f"harness-{newest - timedelta(days=d) + timedelta(hours=hour):%Y%m%d-%H%M%S}.tar.gz"
            (tmp_path / name).write_bytes(b"x")
            (tmp_path / f"{name}.sha256").write_text("x")
    (tmp_path / "unrelated.tar.gz").write_text("never touched")

    removed = ops.prune(tmp_path, daily=7, weekly=4)

    kept = sorted(p.name for p in tmp_path.glob("harness-*.tar.gz"))
    days = ["0908", "0909", "0910", "0911", "0912", "0913", "0914"]  # the newest of each of the last 7 days
    weeks = ["0830", "0906"]  # plus the newest of the two older ISO weeks (the two recent weeks are already kept)
    assert kept == [f"harness-2026{md}-190000.tar.gz" for md in sorted(weeks + days)]
    assert len(removed) == 80 - 9 and len(list(tmp_path.glob("*.sha256"))) == 9
    assert (tmp_path / "unrelated.tar.gz").is_file()


def test_checkpoint_commits_summaries_and_leaves_big_files_out(tmp_path):
    root = _project(tmp_path)

    def git(*a):
        return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, text=True).stdout

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    (root / ".gitignore").write_text("results/*\n!results/schema.sql\n!results/summary.json\n")
    (root / "harness").mkdir()
    (root / "harness" / "x.py").write_text("x = 1\n")
    (root / "reports" / "big.bin").write_bytes(b"\0" * (ops.MAX_GIT_FILE_BYTES + 1))
    (root / "stray.txt").write_text("not under a checkpoint path")
    kw = {"root": root, "db_path": root / "results" / "results.sqlite", "queue_db": root / "results" / "queue.sqlite"}

    out = ops.checkpoint("phase done", **kw)

    files = set(git("show", "--name-only", "--format=", "HEAD").split())
    assert files == {"harness/x.py", "reports/r.md", "config/c.json", "results/schema.sql", "results/summary.json"}
    assert "reports/big.bin" in out
    msg = git("log", "-1", "--format=%B")
    assert msg.startswith("phase done\n") and "jobs: queue queue.sqlite 0 done" in msg and "settings" in msg
    assert "CREATE TABLE queue" in (root / "results" / "schema.sql").read_text()
    assert ops.checkpoint("again", **kw).startswith("nothing to commit")


def test_killed_mid_transaction_leaves_queue_consistent(tmp_path):
    db = tmp_path / "q.sqlite"
    jobqueue.enqueue([{"suite": "ood", "job_key": "k0@t", "inputs": {}}], db)
    code = textwrap.dedent(f"""
        import os
        from harness import jobqueue
        with jobqueue.connect({str(db)!r}) as con:
            con.execute("BEGIN IMMEDIATE")
            for i in range(1, 500):
                con.execute("INSERT INTO queue (suite, job_key, inputs) VALUES ('ood', ?, '{{}}')", (f"k{{i}}@t",))
            con.execute("UPDATE queue SET status = 'running'")
            os._exit(9)  # killed before COMMIT
    """)
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 9
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert jobqueue.counts(db) == {"ood": {"pending": 1}}
