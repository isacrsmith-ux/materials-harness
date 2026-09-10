"""Process-pool failure handling: a failing job or failing post-processing never aborts the batch."""

from harness.runner import run_pool


def ok_job(job: dict) -> dict:
    return {"value": job["x"] * 2}


def boom_job(job: dict) -> dict:
    raise ValueError("deliberate failure")


def test_failures_are_captured_and_batch_continues():
    seen = {}
    jobs = [{"job_key": "a", "x": 1}, {"job_key": "b", "x": 2}]
    run_pool(ok_job, jobs, workers=1, threads=1, on_result=lambda j, r: seen.__setitem__(j["job_key"], r))
    assert seen["a"]["status"] == "ok" and seen["a"]["value"] == 2 and seen["b"]["value"] == 4

    failed = {}
    run_pool(boom_job, [{"job_key": "c", "x": 0}], workers=1, threads=1,
             on_result=lambda j, r: failed.__setitem__(j["job_key"], r))
    assert failed["c"]["status"] == "failed" and "deliberate failure" in failed["c"]["error"]


def test_post_processing_error_is_redelivered_as_failure():
    calls = []

    def on_result(job, result):
        calls.append((job["job_key"], result["status"]))
        if result["status"] == "ok" and job["job_key"] == "bad":
            raise RuntimeError("analysis blew up")

    jobs = [{"job_key": "bad", "x": 1}, {"job_key": "good", "x": 2}]
    run_pool(ok_job, jobs, workers=1, threads=1, on_result=on_result)
    assert ("bad", "ok") in calls and ("bad", "failed") in calls  # retried as a recorded failure
    assert ("good", "ok") in calls  # the batch carried on
