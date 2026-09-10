"""Job queue: idempotent filling, priority order, crash-safe reset, retries, never redoing done jobs."""

import pytest

from harness import jobqueue as q


def _jobs(n, suite="ood"):
    return [{"suite": suite, "job_key": f"k{i}@tag", "inputs": {"x": i}, "priority": n - i, "n_atoms": i}
            for i in range(n)]


def test_enqueue_is_idempotent_and_respects_done(tmp_path):
    db = tmp_path / "q.sqlite"
    assert q.enqueue(_jobs(5), db, done_keys={"k0@tag"}) == {"added": 5, "already_queued": 0, "already_done": 1}
    again = q.enqueue(_jobs(5), db)
    assert again["added"] == 0 and again["already_queued"] == 5
    assert q.counts(db)["ood"] == {"pending": 4, "done": 1}


def test_claim_orders_by_priority_and_never_returns_done(tmp_path):
    db = tmp_path / "q.sqlite"
    q.enqueue(_jobs(5), db, done_keys={"k4@tag"})  # k4 has the lowest priority value but is done
    rows = q.claim(10, "run1", db)
    assert [r["job_key"] for r in rows] == ["k3@tag", "k2@tag", "k1@tag", "k0@tag"]
    assert all(r["status"] == "running" for r in rows)
    assert q.claim(10, "run1", db) == []
    assert q.decode_inputs(rows[0]) == {"x": 3}


def test_reset_stale_running_rows(tmp_path):
    db = tmp_path / "q.sqlite"
    q.enqueue(_jobs(3), db)
    q.claim(2, "dead-run", db)
    assert q.reset_stale(db) == 2
    assert q.counts(db)["ood"] == {"pending": 3}
    assert all(r["attempts"] == 0 for r in q.claim(3, "new-run", db))  # a crash is not an attempt


def test_retry_then_final_failure(tmp_path):
    db = tmp_path / "q.sqlite"
    q.enqueue(_jobs(1), db)
    (row,) = q.claim(1, "r", db)
    q.requeue(row["id"], db, error="ValueError: boom", count_attempt=True)
    (row,) = q.claim(1, "r", db)
    assert row["attempts"] == 1
    q.finish(row["id"], "failed", db, error="ValueError: boom again", attempts=2)
    assert q.claim(1, "r", db) == []
    (f,) = q.failures_by_type(db)
    assert f["error_type"] == "ValueError" and f["n"] == 1


def test_requeue_without_counting_an_attempt(tmp_path):
    db = tmp_path / "q.sqlite"
    q.enqueue(_jobs(1), db)
    (row,) = q.claim(1, "r", db)
    q.requeue(row["id"], db, error="RelaxTimeout: slept", count_attempt=False)
    (row,) = q.claim(1, "r", db)
    assert row["attempts"] == 0


def test_mark_done_only_touches_pending(tmp_path):
    db = tmp_path / "q.sqlite"
    q.enqueue(_jobs(3), db)
    (row,) = q.claim(1, "r", db)  # k2 (lowest priority value) is running
    assert q.mark_done({"k0@tag", "k2@tag"}, db) == 1
    assert q.counts(db)["ood"] == {"pending": 1, "running": 1, "done": 1}


def test_median_runtime(tmp_path):
    db = tmp_path / "q.sqlite"
    q.enqueue(_jobs(3), db)
    for row, t in zip(q.claim(3, "r", db), (1.0, 2.0, 10.0)):
        q.finish(row["id"], "done", db, runtime_s=t)
    assert q.median_runtime(db) == 2.0 and q.median_runtime(db, "ood") == 2.0


@pytest.mark.parametrize("msg,expected", [
    ("RelaxTimeout: exceeded 900 s wall-clock limit", "RelaxTimeout"),
    ("post-processing error: KeyError: 'x'", "post-processing: KeyError"),
    ("worker crashed: A process in the process pool was terminated abruptly", "worker crash"),
    ("hard timeout: no result after 1800 s", "hard timeout (watchdog)"),
    ("something odd happened", "other"),
    (None, None),
])
def test_classify_error(msg, expected):
    assert q.classify_error(msg) == expected
