"""Process pool for independent structures: fixed threads per worker, failures captured."""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from typing import Callable, Iterable

log = logging.getLogger(__name__)

THREAD_ENV_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


def _init_worker(threads: int, extra_env: dict[str, str]) -> None:
    os.environ.update(extra_env)
    for var in THREAD_ENV_VARS:
        os.environ[var] = str(threads)
    import harness  # noqa: F401  (redirects caches before torch import)

    # A spawned worker re-imports the parent's __main__ module, and a script that sets HARNESS_MODEL at
    # import time therefore pins harness.config to the PARENT's model before this initializer runs. When
    # a caller asked for a different engine (predict.py's second engine), re-read the registry so the
    # worker really runs the model it was asked for; the job's own metadata is checked as well.
    if "HARNESS_MODEL" in extra_env:
        import importlib
        import sys

        cfg = sys.modules.get("harness.config")
        if cfg is not None and cfg.ACTIVE_MODEL != extra_env["HARNESS_MODEL"]:
            importlib.reload(cfg)
    from harness.platform_check import assert_native_arm64

    assert_native_arm64()
    import torch

    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)


def safe_call(fn: Callable, job: dict) -> dict:
    """Run fn(job), turning any exception into a {"status": "failed"/"timeout", "error": ...} result."""
    t0 = time.perf_counter()
    try:
        out = fn(job)
        out.setdefault("status", "ok")
    except Exception as exc:  # noqa: BLE001 — a failed structure must never kill the batch
        out = {"status": "timeout" if type(exc).__name__ == "RelaxTimeout" else "failed",
               "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(limit=8)}
    out["job_wall_s"] = time.perf_counter() - t0
    out["worker_pid"] = os.getpid()
    return out


def run_pool(
    fn: Callable[[dict], dict],
    jobs: Iterable[dict],
    workers: int,
    threads: int,
    on_result: Callable[[dict, dict], None],
    extra_env: dict[str, str] | None = None,
) -> None:
    """Run fn(job) for every job in fresh spawned workers; on_result(job, result) in the parent.

    fn must be an importable top-level function. Worker crashes (e.g. segfault) are reported
    as failures for the jobs that were still pending rather than aborting the caller.
    """
    jobs = list(jobs)
    if not jobs:
        return
    extra_env = dict(extra_env or {})
    pending = {id(j): j for j in jobs}
    ctx = mp.get_context("spawn")
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx, initializer=_init_worker,
                                 initargs=(threads, extra_env)) as pool:
            futures = {pool.submit(safe_call, fn, job): job for job in jobs}
            for fut in as_completed(futures):
                job = futures[fut]
                pending.pop(id(job), None)
                try:
                    result = fut.result()
                except BrokenProcessPool as exc:
                    result = {"status": "failed", "error": f"worker crashed: {exc}"}
                _deliver(on_result, job, result)
    except BrokenProcessPool as exc:
        for job in pending.values():
            _deliver(on_result, job, {"status": "failed", "error": f"worker pool broke: {exc}"})


def _deliver(on_result: Callable[[dict, dict], None], job: dict, result: dict) -> None:
    """Call on_result; if post-processing a successful job raises, re-deliver it as a failure."""
    try:
        on_result(job, result)
    except Exception as exc:  # noqa: BLE001 — analysis errors must not abort the batch
        log.exception("post-processing failed for %s", job.get("job_key", job.get("name")))
        if result.get("status") == "ok":
            try:
                on_result(job, {"status": "failed", "error": f"post-processing error: {type(exc).__name__}: {exc}",
                                "job_wall_s": result.get("job_wall_s")})
            except Exception:  # noqa: BLE001
                log.exception("could not record failure for %s", job.get("job_key"))
