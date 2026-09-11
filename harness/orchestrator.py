"""Unattended runs: build the job queue, then drain it with a crash-safe process pool.

Orchestration only. Every job runs the same job function (harness.jobs.relax_job), relaxation
settings and recorder (the suites' _record) as `python -m harness run`; nothing here changes what
is computed or how it is scored.

Safety properties
* One runner per queue: an fcntl lock the kernel releases on kill -9, crash or reboot.
* On start: orphaned workers of a killed runner are killed, 'running' rows go back to 'pending',
  and rows whose results already exist in results.sqlite are marked done — finished work is
  never redone.
* Per-job timeout: the engine's in-worker limit (900 s per relaxation) plus a watchdog on the
  monotonic clock (Mac sleep doesn't count) that restarts a hung pool.
* A failed or timed-out job is retried once, then kept as failed with its error. A timeout that
  overlapped a system sleep is retried without counting as an attempt.
* Power: pmset every power_poll_s; on battery, stop dispatching, let running jobs finish and wait
  for AC.
* Stop: SIGTERM/SIGINT, `python -m harness stop`, or --stop-at HH:MM all drain gracefully.
"""

from __future__ import annotations

import fcntl
import json
import logging
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime, timedelta
from pathlib import Path

from harness import ROOT, jobqueue, notify, power, store
from harness.config import (DEFAULT_RELAX, LOG_DIR, MODEL, QUEUE_DB, REPORTS_DIR, load_compute_config,
                            load_unattended_config, settings_tag)
from harness.jobs import run_job
from harness.platform_check import core_counts
from harness.runner import _init_worker, _safe_call

log = logging.getLogger(__name__)

AUTO_SUITE = "substitution_auto"
SLEEP_GAP_S = 60.0       # wall-clock minus monotonic time above this => the Mac slept during the job
STATE_EVERY_S = 2.0


class AlreadyRunning(RuntimeError):
    pass


def paths(queue_db) -> dict[str, Path]:
    stem = Path(queue_db).stem
    return {"lock": LOG_DIR / f"runner-{stem}.lock", "state": LOG_DIR / f"runner-{stem}.state.json",
            "stop": LOG_DIR / f"runner-{stem}.STOP", "workers": LOG_DIR / f"runner-{stem}.workers.json"}


def layout(mode: str, compute: dict, cfg: dict) -> tuple[int, int]:
    """(workers, threads per worker) from the benchmarked layout. polite: leave
    cfg['polite_reserved_cores'] performance cores free; full: use all performance cores."""
    perf = core_counts()["performance"]
    threads = max(1, int(compute.get("threads_per_worker") or 1))
    budget = perf - int(cfg["polite_reserved_cores"]) if mode == "polite" else perf
    bench_workers = int(compute.get("workers") or max(1, perf // threads))
    workers = min(bench_workers, budget // threads)
    if workers < 1:
        return 1, max(1, budget)
    return workers, threads


def parse_stop_at(text: str | None, now: datetime | None = None) -> datetime | None:
    """Next occurrence of HH:MM after `now` (so a 23:00 start with 07:00 stop ends tomorrow morning)."""
    if not text:
        return None
    now = now or datetime.now()
    h, m = (int(x) for x in text.split(":"))
    stop = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return stop if stop > now else stop + timedelta(days=1)


def _init_unattended(threads: int, nice: int) -> None:
    if nice:
        try:
            os.nice(nice)
        except OSError:
            pass
    _init_worker(threads, {})


def _recorder(suite: str):
    if suite in ("substitution", AUTO_SUITE):
        from harness.suites.substitution import _record
        return _record
    if suite == "ood":
        from harness.suites.ood import _record
        return _record
    if suite == "stability":
        from harness.suites.stability import _record_competitor
        return _record_competitor
    raise KeyError(f"no recorder for suite {suite!r}")


# --- building the queue --------------------------------------------------------------------------

def _settings(compute: dict) -> tuple[str, dict]:
    tag = settings_tag(compute["device"], compute["dtype"])
    return tag, {"device": compute["device"], "dtype": compute["dtype"], "settings_tag": tag,
                 "relax": DEFAULT_RELAX.as_dict(), "model": MODEL["file"], "model_sha256": MODEL["sha256"]}


def _plain(d: dict) -> dict:
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in d.items()}


def _queue_rows(jobs: list[dict], suite: str, settings: dict, rank_of=None) -> list[dict]:
    """Wrap suite job dicts as queue rows (device/dtype are added by the runner at dispatch)."""
    rows = []
    for i, j in enumerate(jobs):
        inputs = {k: v for k, v in j.items() if k not in ("device", "dtype")} | {"suite": suite}
        if "settings" in inputs:
            inputs["settings"] = settings
        rows.append({"suite": suite, "job_key": j["job_key"], "rank": rank_of(j) if rank_of else i,
                     "n_atoms": len(j["structure"]), "model": MODEL["file"], "settings": settings, "inputs": inputs})
    return rows


def build_auto_substitution_jobs(pairs: list[dict], kinds: list[str], compute: dict) -> list[dict]:
    from harness.suites.substitution import build_jobs

    tag, settings = _settings(compute)
    rank = {p["pair_id"]: i for i, p in enumerate(pairs)}
    jobs = build_jobs(pairs, kinds, compute, suite=AUTO_SUITE)
    return _queue_rows(jobs, AUTO_SUITE, settings, rank_of=lambda j: rank[j["pair"]["pair_id"]])


def build_curated_substitution_jobs(kinds: list[str], compute: dict) -> list[dict]:
    from harness.suites.substitution import SUITE, build_jobs

    tag, settings = _settings(compute)
    return _queue_rows(build_jobs(resolve_curated(), kinds, compute, suite=SUITE), SUITE, settings)


def resolve_curated() -> list[dict]:
    from harness.curation import resolve_pairs

    return resolve_pairs()


def build_competitor_retry_jobs(compute: dict) -> list[dict]:
    from harness.suites import stability

    from harness.suites import mode_b

    tag, settings = _settings(compute)
    extra = mode_b.chemsys_list(mode_b.make_sample()) if mode_b.SAMPLE_FILE.is_file() else ()
    jobs = stability.retry_jobs(resolve_curated(), compute, tag, extra_chemsys=extra)
    return _queue_rows(jobs, stability.SUITE, settings)


def build_retry_jobs(compute: dict) -> list[dict]:
    """Fallback ladder for every relaxation the guard rejects, in every suite (competitors, curated and
    auto substitution pairs, WBM). Each result is recorded under its original key, all rungs kept."""
    from harness import pairgen
    from harness.suites import ood, substitution

    tag, settings = _settings(compute)
    rows = build_competitor_retry_jobs(compute)
    for suite, pairs in (("substitution", resolve_curated()), (AUTO_SUITE, pairgen.load_pairs())):
        rows += _queue_rows(substitution.retry_jobs(suite, pairs, compute, tag), suite, settings)
    rows += _queue_rows(ood.retry_jobs(compute, tag), "ood", settings)
    return rows


def build_ood_jobs(n: int, compute: dict) -> list[dict]:
    from harness.suites import ood

    tag, settings = _settings(compute)
    summary = ood.load_summary()
    ids = ood.load_sample(summary, n=n)
    structs = ood.load_structures(ids, cache_file=ood.sample_structs_path(n))
    summary = summary.set_index("material_id")
    jobs = []
    for rank, wid in enumerate(ids):
        if wid not in structs:
            continue
        key = f"{wid}@{tag}"
        s = structs[wid]
        jobs.append({"suite": "ood", "job_key": key, "rank": rank, "n_atoms": len(s), "model": MODEL["file"],
                     "settings": settings,
                     "inputs": {"job_key": key, "wbm_id": wid, "structure": s, "ref": _plain(summary.loc[wid].to_dict()),
                                "suite": "ood"}})
    return jobs


def build_wbm_calibration_jobs(compute: dict) -> list[dict]:
    """Relaxation (from the WBM initial structure) + single point (at the DFT-relaxed structure) for every
    WBM CALIBRATION id. The locked test ids are never queued here (splits.test_ids is locked)."""
    from harness import splits
    from harness.suites import ood

    tag, settings = _settings(compute)
    ids = splits.calibration_ids()
    starts = ood.load_structures(ids, cache_file=ood.WBM_DIR / "calibration_init_structs.json")
    cses = ood.load_entries(ids, ood.WBM_DIR / "calibration_cse.json")
    summary = ood.load_summary().set_index("material_id")
    jobs = []
    for rank, wid in enumerate(ids):
        ref = _plain(summary.loc[wid].to_dict())
        if wid in starts:
            key = f"{wid}@{tag}"
            jobs.append({"suite": "ood", "job_key": key, "rank": rank, "n_atoms": len(starts[wid]), "model": MODEL["file"],
                         "settings": settings, "inputs": {"job_key": key, "wbm_id": wid, "structure": starts[wid], "ref": ref,
                                                          "suite": "ood"}})
        if wid in cses:
            key = f"{wid}:static@{tag}"
            jobs.append({"suite": "ood", "job_key": key, "rank": rank, "n_atoms": len(cses[wid].structure), "model": MODEL["file"],
                         "settings": settings, "inputs": {"job_key": key, "wbm_id": wid, "structure": cses[wid].structure,
                                                          "ref": ref, "job_fn": "static", "suite": "ood"}})
    return jobs


def build_mode_b_jobs(compute: dict) -> tuple[list[dict], dict]:
    """Competitor relaxations for the mode (b) sample of WBM calibration systems (stability suite keys, so
    phases shared with other systems or with the curated gate are relaxed once)."""
    import numpy as np

    from harness.suites import mode_b

    tag, settings = _settings(compute)
    sample = mode_b.make_sample()
    done = store.completed_keys("stability", retry_failed=True)
    jobs, by_cs = mode_b.competitor_jobs(sample, compute, tag, done)
    rows = _queue_rows(jobs, "stability", settings)
    n = [r["n_atoms"] for r in rows]
    return rows, {"systems": len(by_cs), "unique_phases": len({m for v in by_cs.values() for m in v}),
                  "to_relax": len(rows), "n_atoms_median": float(np.median(n)) if n else 0, "n_atoms_max": max(n, default=0)}


def build_screening_jobs(compute: dict, pair_kinds=("sub", "sub_rescaled", "ctrl", "static")) -> list[dict]:
    """The screening subset (harness/screening.py) for the ACTIVE model: every pair kind for the subset's pairs,
    relaxation + DFT-geometry single point for its WBM calibration structures."""
    from harness import pairgen, screening
    from harness.suites import ood

    subset = screening.make_subset()
    ids = set(subset["pair_ids"])
    pairs = [p for p in pairgen.load_pairs() if p["pair_id"] in ids]
    rows = build_auto_substitution_jobs(pairs, list(pair_kinds), compute)
    wbm = set(subset["wbm_ids"])
    rows += [j for j in build_wbm_calibration_jobs(compute) if j["inputs"]["wbm_id"] in wbm]
    for j in rows:
        j["priority"] = -j["n_atoms"]  # large cells first: the tail is short
    return rows


def prepare(cfg: dict | None = None, queue_db=QUEUE_DB, do_pairs: bool = True, do_ood: bool = True,
            force_pairs: bool = False, curated_kinds: list[str] | None = None, competitor_retries: bool = False,
            retries: bool = False, wbm_calibration: bool = False, mode_b: bool = False, screening: bool = False) -> dict:
    """Bulk-download and cache MP/WBM inputs, generate pairs, and enqueue every job (idempotent).

    curated_kinds queues curated-pair substitution kinds; competitor_retries queues the fallback ladder
    for rejected stability competitors. Both run first (longest jobs first keeps the tail short)."""
    from harness import pairgen

    cfg = cfg or load_unattended_config()
    compute = load_compute_config()
    info: dict = {"config": {k: cfg[k] for k in ("max_pairs", "max_atoms", "ood_sample", "auto_pair_kinds")}}
    sub_jobs, ood_jobs, first = [], [], []
    if screening:
        first += build_screening_jobs(compute)
        info["screening"] = len(first)
    if competitor_retries or retries:
        retry = build_retry_jobs(compute) if retries else build_competitor_retry_jobs(compute)
        for j in retry:
            j["priority"] = -2000
        first += retry
        info["competitor_retries"] = len(retry)
    if mode_b:
        mb, info["mode_b"] = build_mode_b_jobs(compute)
        for j in mb:
            j["priority"] = 10_000_000 - j["n_atoms"]  # after everything else already queued, big cells first
        first += mb
    if curated_kinds:
        cur = build_curated_substitution_jobs(curated_kinds, compute)
        for j in cur:
            j["priority"] = -1000 - j["n_atoms"]
        first += cur
        info["curated_kinds"] = {"kinds": curated_kinds, "jobs": len(cur)}
    if do_pairs:
        if cfg.get("pair_design") == "stratified":
            info["pairs"] = pairgen.generate_stratified(cfg["max_atoms"], cfg.get("stratified"), force=force_pairs)
        else:
            info["pairs"] = pairgen.generate(cfg["max_pairs"], cfg["max_atoms"], force=force_pairs)
        sub_jobs = build_auto_substitution_jobs(pairgen.load_pairs(), cfg["auto_pair_kinds"], compute)
    if wbm_calibration:
        ood_jobs = build_wbm_calibration_jobs(compute)
    elif do_ood:
        ood_jobs = build_ood_jobs(cfg["ood_sample"], compute)
    # Space-relevant pairs keep their order; WBM jobs are interleaved proportionally so every
    # partial report has both in- and out-of-distribution results.
    n_pairs = max(1, len({j["rank"] for j in sub_jobs}))
    n_ood = max(1, len(ood_jobs))
    for j in sub_jobs:
        j["priority"] = 10 * j["rank"]
    for j in ood_jobs:
        j["priority"] = int(10 * j["rank"] * (n_pairs / n_ood if sub_jobs else 1)) + 5
    done = set()
    for suite in (AUTO_SUITE, "ood", "substitution", "stability"):
        done |= store.completed_keys(suite, retry_failed=True)
    info["enqueue"] = jobqueue.enqueue(first + sub_jobs + ood_jobs, queue_db, done_keys=done)
    info["jobs"] = {AUTO_SUITE: len(sub_jobs), "ood": len(ood_jobs), "first": len(first)}
    info["n_atoms"] = _size_summary(first + sub_jobs + ood_jobs)
    return info


def _size_summary(jobs: list[dict]) -> dict:
    import numpy as np

    if not jobs:
        return {}
    n = np.array([j["n_atoms"] for j in jobs])
    return {"median": float(np.median(n)), "p90": float(np.percentile(n, 90)), "max": int(n.max())}


# --- runner --------------------------------------------------------------------------------------

class Runner:
    def __init__(self, mode: str = "polite", queue_db=QUEUE_DB, stop_at: str | None = None, max_jobs: int | None = None,
                 power_poll_s: float | None = None, workers: int | None = None, report_every: int | None = None,
                 cfg: dict | None = None, threads: int | None = None):
        self.cfg = cfg or load_unattended_config()
        self.compute = load_compute_config()
        self.mode = mode
        self.qdb = Path(queue_db)
        self.paths = paths(self.qdb)
        self.workers, self.threads = layout(mode, self.compute, self.cfg)
        if workers:
            self.workers = workers
        if threads:
            self.threads = threads
        self.tag = settings_tag(self.compute["device"], self.compute["dtype"])
        self.stop_at = parse_stop_at(stop_at)
        self.max_jobs = max_jobs
        self.power_poll_s = float(power_poll_s or self.cfg["power_poll_s"])
        self.report_every = int(report_every or self.cfg["report_every"])
        self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = REPORTS_DIR / self.run_id
        self.started_at = datetime.now()
        self.inflight: dict = {}
        self.paused = False
        self.pause_since: datetime | None = None
        self.draining: str | None = None
        self.power = "unknown"
        self.dispatched = self.n_done = self.n_failed = self.n_retried = 0
        self.last_report_at = 0
        self.report_proc: subprocess.Popen | None = None
        self.failure_alerted = False
        self._stop_signal = False
        self._last_power = -1e18
        self._last_state = 0.0
        self._lock_fh = None
        self.pool: ProcessPoolExecutor | None = None

    # -- process management --
    def _acquire_lock(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = open(self.paths["lock"], "a+")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.seek(0)
            raise AlreadyRunning(f"a runner is already working on {self.qdb} (pid {fh.read().strip() or '?'})")
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        self._lock_fh = fh

    def _kill_orphans(self) -> int:
        p = self.paths["workers"]
        if not p.is_file():
            return 0
        killed = 0
        for pid in json.loads(p.read_text()).get("pids", []):
            try:
                cmd = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True,
                                     timeout=5).stdout
            except (OSError, subprocess.SubprocessError):
                continue
            if "multiprocessing" in cmd and str(ROOT) in cmd:  # our spawned worker, not a reused pid
                try:
                    os.kill(pid, signal.SIGKILL)
                    killed += 1
                except ProcessLookupError:
                    pass
        p.unlink(missing_ok=True)
        return killed

    def _new_pool(self) -> None:
        nice = int(self.cfg["polite_nice"]) if self.mode == "polite" else 0
        self.pool = ProcessPoolExecutor(max_workers=self.workers, mp_context=mp.get_context("spawn"),
                                        initializer=_init_unattended, initargs=(self.threads, nice))

    def _kill_pool(self) -> None:
        if self.pool is None:
            return
        for proc in list((getattr(self.pool, "_processes", None) or {}).values()):
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        self.pool.shutdown(wait=False, cancel_futures=True)

    def _restart_pool(self) -> None:
        self._kill_pool()
        self._new_pool()

    def _save_worker_pids(self) -> None:
        pids = list((getattr(self.pool, "_processes", None) or {}).keys())
        self.paths["workers"].write_text(json.dumps({"runner_pid": os.getpid(), "pids": pids}))

    def _on_signal(self, signum, frame) -> None:  # noqa: ARG002
        self._stop_signal = True

    # -- main --
    def run(self) -> str:
        self._acquire_lock()
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        killed = self._kill_orphans()
        reset = jobqueue.reset_stale(self.qdb)
        keys = set()
        for suite in jobqueue.suites(self.qdb):
            keys |= store.completed_keys(suite, retry_failed=True)
        marked = jobqueue.mark_done(keys, self.qdb)
        self.paths["stop"].unlink(missing_ok=True)
        if power.override_path():
            log.warning("power source override active (%s) — test mode", power.override_path())
        jobqueue.start_run(self.run_id, self.mode, os.getpid(), self.workers, self.threads, self.qdb)
        log.info("run %s: mode %s, %d workers x %d threads, queue %s; reset %d stale running jobs, killed %d orphaned "
                 "workers, %d jobs found already complete%s", self.run_id, self.mode, self.workers, self.threads,
                 self.qdb, reset, killed, marked, f"; stops at {self.stop_at:%Y-%m-%d %H:%M}" if self.stop_at else "")
        self._new_pool()
        status = "crashed"
        try:
            status = self._loop()
        except Exception as exc:
            log.exception("runner crashed")
            notify.notify("Materials harness: run FAILED", f"Runner crashed: {type(exc).__name__}: {exc}")
            raise
        finally:
            self._shutdown(status)
        return status

    def _loop(self) -> str:
        while True:
            self._check_stop()
            self._check_power()
            if not self.draining and not self.paused:
                self._fill()
            if self.inflight:
                done, _ = wait(list(self.inflight), timeout=2.0, return_when=FIRST_COMPLETED)
                for fut in done:
                    if fut in self.inflight:
                        self._handle(fut)
                self._watchdog()
            else:
                if self.draining:
                    return "stopped"
                if not self._has_pending():
                    return "finished"
                time.sleep(2.0 if self.paused else 0.2)
            self._maybe_report()
            self._write_state()

    def _has_pending(self) -> bool:
        return any(st.get("pending", 0) for st in jobqueue.counts(self.qdb).values())

    def _fill(self) -> None:
        free = self.workers - len(self.inflight)
        if self.max_jobs is not None:
            if self.dispatched >= self.max_jobs:
                self._drain(f"max-jobs {self.max_jobs} reached")
                return
            free = min(free, self.max_jobs - self.dispatched)
        rows = jobqueue.claim(free, self.run_id, self.qdb)
        for row in rows:
            if not row["job_key"].endswith(f"@{self.tag}"):
                jobqueue.finish(row["id"], "failed", self.qdb, attempts=row["attempts"],
                                error="SettingsMismatch: queued under a different settings tag; re-run prepare")
                continue
            job = jobqueue.decode_inputs(row)
            job.update(device=self.compute["device"], dtype=self.compute["dtype"],
                       layout={"tier": "unattended", "mode": self.mode, "workers": self.workers,
                               "threads_per_worker": self.threads})
            try:
                fut = self.pool.submit(_safe_call, run_job, job)
            except (BrokenProcessPool, RuntimeError):
                log.warning("process pool unusable; restarting it")
                self._restart_pool()
                fut = self.pool.submit(_safe_call, run_job, job)
            self.inflight[fut] = {"row": row, "job": job, "mono0": time.monotonic(), "wall0": time.time()}
            self.dispatched += 1
        if rows:
            self._save_worker_pids()

    def _handle(self, fut) -> None:
        meta = self.inflight.pop(fut)
        try:
            res = fut.result()
        except BrokenProcessPool as exc:
            self._pool_broke(meta, exc)
            return
        except Exception as exc:  # noqa: BLE001
            res = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        slept = (time.time() - meta["wall0"]) - (time.monotonic() - meta["mono0"]) > SLEEP_GAP_S
        self._settle(meta["row"], meta["job"], res, slept)

    def _pool_broke(self, first: dict, exc: Exception) -> None:
        metas = [first, *self.inflight.values()]
        self.inflight.clear()
        log.error("a worker process died (%s); %d in-flight jobs count one attempt each", exc, len(metas))
        self._restart_pool()
        for m in metas:
            self._settle(m["row"], m["job"], {"status": "failed", "error": f"worker crashed: {exc}"}, slept=False)

    def _watchdog(self) -> None:
        hard = float(self.cfg["hard_timeout_s"])
        now_m = time.monotonic()
        # Multi-rung jobs (fallback ladder) carry their own budget; the watchdog never cuts them shorter.
        stuck = {f for f, m in self.inflight.items()
                 if now_m - m["mono0"] > max(hard, float(m["job"].get("budget_s") or 0))}
        if not stuck:
            return
        metas = dict(self.inflight)
        self.inflight.clear()
        log.error("watchdog: %d job(s) without a result after %.0f s; restarting the pool", len(stuck), hard)
        self._restart_pool()
        for f, m in metas.items():
            if f in stuck:
                self._settle(m["row"], m["job"], {"status": "timeout", "error": f"hard timeout: no result after "
                                                  f"{hard:.0f} s (watchdog killed the worker)"}, slept=False)
            else:
                jobqueue.requeue(m["row"]["id"], self.qdb, error="requeued: pool restarted by the watchdog",
                                 count_attempt=False)

    def _settle(self, row: dict, job: dict, res: dict, slept: bool) -> None:
        status = res.get("status", "failed")
        runtime = res.get("wall_time_s") or res.get("job_wall_s")
        rec = _recorder(row["suite"])
        if status == "ok":
            try:
                rec(job, res)
            except Exception as exc:  # noqa: BLE001 — scoring errors must not stop the run
                log.exception("post-processing failed for %s", row["job_key"])
                status = "failed"
                res = {"status": "failed", "job_wall_s": runtime,
                       "error": f"post-processing error: {type(exc).__name__}: {exc}"}
            else:
                jobqueue.finish(row["id"], "done", self.qdb, runtime_s=runtime, worker_pid=res.get("worker_pid"))
                self.n_done += 1
                return
        error = res.get("error") or status
        if status == "timeout" and slept:
            jobqueue.requeue(row["id"], self.qdb, count_attempt=False,
                             error=f"{error} (overlapped a system sleep; retried without counting an attempt)")
            log.warning("%s timed out during a system sleep; requeued without penalty", row["job_key"])
            return
        attempts = int(row.get("attempts") or 0) + 1
        if attempts < int(self.cfg["max_attempts"]):
            jobqueue.requeue(row["id"], self.qdb, error=error, count_attempt=True)
            self.n_retried += 1
            log.warning("%s %s (attempt %d/%d), will retry: %s", row["job_key"], status, attempts,
                        self.cfg["max_attempts"], error)
            return
        try:
            rec(job, {**res, "status": status, "error": error})
        except Exception:  # noqa: BLE001
            log.exception("could not record the final failure of %s", row["job_key"])
        jobqueue.finish(row["id"], status, self.qdb, runtime_s=runtime, error=error, attempts=attempts,
                        worker_pid=res.get("worker_pid"))
        self.n_failed += 1
        log.error("%s %s after %d attempts: %s", row["job_key"], status, attempts, error)
        self._check_failure_rate()

    def _check_failure_rate(self, final: bool = False) -> None:
        finished = self.n_done + self.n_failed
        if self.failure_alerted or not finished:
            return
        frac = self.n_failed / finished
        if frac > float(self.cfg["failure_alert_fraction"]) and (final or finished >= int(self.cfg["failure_alert_min_jobs"])):
            self.failure_alerted = True
            notify.notify("Materials harness: high failure rate",
                          f"{self.n_failed} of {finished} jobs failed ({frac:.0%}) in run {self.run_id}. "
                          "See: python -m harness status")

    def _drain(self, reason: str) -> None:
        if not self.draining:
            self.draining = reason
            log.info("draining (%s): finishing %d running jobs, starting no new ones", reason, len(self.inflight))
            self._write_state(force=True)

    def _check_stop(self) -> None:
        if self.draining:
            return
        if self._stop_signal:
            self._drain("signal received")
        elif self.paths["stop"].exists():
            self._drain("stop requested")
        elif self.stop_at and datetime.now() >= self.stop_at:
            self._drain(f"stop time {self.stop_at:%H:%M} reached")

    def _check_power(self) -> None:
        now_m = time.monotonic()
        if now_m - self._last_power < self.power_poll_s:
            return
        self._last_power = now_m
        self.power = power.power_source()
        if self.power == "battery" and not self.paused:
            self.paused, self.pause_since = True, datetime.now()
            log.warning("on battery power: pausing — finishing %d running jobs, then waiting for AC", len(self.inflight))
            notify.notify("Materials harness paused (battery)",
                          f"On battery. Finishing {len(self.inflight)} running jobs, then waiting for AC. {self._progress()}")
            self._write_state(force=True)
        elif self.power != "battery" and self.paused:
            log.info("AC power is back after %s: resuming", datetime.now() - self.pause_since)
            self.paused, self.pause_since = False, None
            notify.notify("Materials harness resumed", f"Back on AC power. {self._progress()}")
            self._write_state(force=True)

    def _progress(self) -> str:
        c = jobqueue.counts(self.qdb)
        done = sum(s.get("done", 0) for s in c.values())
        total = sum(sum(s.values()) for s in c.values())
        return f"{done}/{total} jobs done."

    def _maybe_report(self) -> None:
        if self.n_done - self.last_report_at < self.report_every:
            return
        self.last_report_at = self.n_done
        if self.report_proc and self.report_proc.poll() is None:
            log.info("previous partial report still running; skipping this one")
            return
        out = self.run_dir / "partial"
        logf = open(LOG_DIR / f"report-{self.run_id}.log", "a")
        self.report_proc = subprocess.Popen([sys.executable, "-m", "harness", "report", "--out", str(out)],
                                            stdout=logf, stderr=subprocess.STDOUT, cwd=ROOT)
        log.info("partial report started after %d completed jobs -> %s", self.n_done, out)

    def _write_state(self, force: bool = False, status: str | None = None) -> None:
        if not force and time.monotonic() - self._last_state < STATE_EVERY_S:
            return
        self._last_state = time.monotonic()
        st = status or ("paused" if self.paused else "draining" if self.draining else "running")
        state = {"status": st, "pid": os.getpid(), "run_id": self.run_id, "mode": self.mode, "workers": self.workers,
                 "threads": self.threads, "queue_db": str(self.qdb), "run_dir": str(self.run_dir),
                 "started_at": self.started_at.isoformat(timespec="seconds"),
                 "heartbeat": datetime.now().isoformat(timespec="seconds"), "heartbeat_epoch": time.time(),
                 "power": self.power, "paused": self.paused,
                 "pause_since": self.pause_since.isoformat(timespec="seconds") if self.pause_since else None,
                 "draining": self.draining, "stop_at": self.stop_at.isoformat(timespec="minutes") if self.stop_at else None,
                 "running_jobs": [m["row"]["job_key"] for m in self.inflight.values()],
                 "done_this_run": self.n_done, "failed_this_run": self.n_failed, "retried_this_run": self.n_retried}
        tmp = self.paths["state"].with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1))
        tmp.replace(self.paths["state"])

    def _shutdown(self, status: str) -> None:
        if self.pool is not None:
            if status in ("finished", "stopped"):
                self.pool.shutdown(wait=True)
            else:
                self._kill_pool()
        self.paths["workers"].unlink(missing_ok=True)
        if self.report_proc and self.report_proc.poll() is None:
            try:
                self.report_proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                self.report_proc.kill()
        report_dir = None
        if status != "crashed" and (self.n_done or self.n_failed):
            try:
                from harness.report import write_report

                write_report(out_dir=self.run_dir, compare_previous=True)
                report_dir = self.run_dir
            except Exception:  # noqa: BLE001
                log.exception("final report failed")
        jobqueue.end_run(self.run_id, status, self.n_done, self.n_failed, str(report_dir) if report_dir else None, self.qdb)
        self._check_failure_rate(final=True)
        c = jobqueue.counts(self.qdb)
        pending = sum(s.get("pending", 0) for s in c.values())
        title = {"finished": "Materials harness: run finished", "stopped": "Materials harness: run stopped",
                 "crashed": "Materials harness: run FAILED"}[status]
        msg = (f"{self.n_done} jobs done, {self.n_failed} failed this run; {pending} still pending."
               + (f" Report: reports/{self.run_id}/" if report_dir else "") + (f" ({self.draining})" if self.draining else ""))
        if status != "crashed":
            notify.notify(title, msg)
        log.info("%s — %s", title, msg)
        self._write_state(force=True, status=status)
        self.paths["stop"].unlink(missing_ok=True)
        if self._lock_fh:
            self._lock_fh.close()


# --- status / stop -------------------------------------------------------------------------------

def runner_pid(queue_db=QUEUE_DB) -> int | None:
    """PID of the live runner holding this queue's lock, else None."""
    p = paths(queue_db)["lock"]
    if not p.exists():
        return None
    with open(p, "a+") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.seek(0)
            txt = fh.read().strip()
            return int(txt) if txt.isdigit() else -1
        fcntl.flock(fh, fcntl.LOCK_UN)
    return None


def read_state(queue_db=QUEUE_DB) -> dict:
    p = paths(queue_db)["state"]
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def request_stop(queue_db=QUEUE_DB) -> int | None:
    pid = runner_pid(queue_db)
    if pid:
        paths(queue_db)["stop"].write_text(datetime.now().isoformat(timespec="seconds"))
    return pid


def _fmt_dur(s: float | None) -> str:
    if s is None:
        return "unknown"
    s = int(round(s))
    if s < 90:
        return f"{s} s"
    if s < 5400:
        return f"{s / 60:.0f} min"
    return f"{s // 3600} h {(s % 3600) // 60:02d} min"


def _historic_median(suite: str) -> float | None:
    """Median runtime of finished jobs of this kind outside the queue (the earlier suite runs)."""
    import numpy as np

    df = store.load_table("jobs", "substitution" if suite == AUTO_SUITE else suite)
    if df.empty:
        return None
    v = df[(df.status == "ok") & df.runtime_s.notna()].runtime_s
    return float(np.median(v)) if len(v) else None


def eta_seconds(queue_db, workers: int) -> float | None:
    total = 0.0
    overall = jobqueue.median_runtime(queue_db)
    for suite, st in jobqueue.counts(queue_db).items():
        left = st.get("pending", 0) + st.get("running", 0)
        if not left:
            continue
        med = jobqueue.median_runtime(queue_db, suite) or overall or _historic_median(suite)
        if med is None:
            return None
        total += left * med
    return total / max(1, workers)


def status_report(queue_db=QUEUE_DB) -> str:
    cfg, compute = load_unattended_config(), load_compute_config()
    qdb = Path(queue_db)
    if not qdb.exists():
        return f"No queue at {qdb}. Build it with: python -m harness prepare"
    pid = runner_pid(qdb)
    st = read_state(qdb)
    lines = [f"Queue {qdb}"]
    if pid:
        age = time.time() - st.get("heartbeat_epoch", time.time())
        label = {"paused": f"PAUSED on battery since {st.get('pause_since')}",
                 "draining": f"DRAINING ({st.get('draining')})"}.get(st.get("status"), "RUNNING")
        lines.append(f"Runner: {label} — pid {pid}, mode {st.get('mode')}, {st.get('workers')} workers x "
                     f"{st.get('threads')} thread(s), run {st.get('run_id')}, heartbeat {age:.0f} s ago"
                     + (f", stops at {st['stop_at']}" if st.get("stop_at") else ""))
        lines.append(f"This run: {st.get('done_this_run', 0)} done, {st.get('failed_this_run', 0)} failed, "
                     f"{st.get('retried_this_run', 0)} retried; power: {st.get('power')}")
    else:
        last = jobqueue.last_runs(qdb, 1)
        lines.append("Runner: not running" + (f" (last run {last[0]['run_id']}: {last[0]['status']}, "
                                              f"{last[0]['n_done'] or 0} done, {last[0]['n_failed'] or 0} failed)" if last else ""))
    c = jobqueue.counts(qdb)
    tot = {s: sum(v.get(s, 0) for v in c.values()) for s in jobqueue.STATUSES}
    total = sum(tot.values())
    lines.append(f"Progress: {tot['done']}/{total} done ({tot['done'] / max(1, total):.1%}), {tot['running']} running, "
                 f"{tot['pending']} pending ({jobqueue.pending_retries(qdb)} awaiting retry), {tot['failed']} failed, "
                 f"{tot['timeout']} timed out")
    for suite in sorted(c):
        v = c[suite]
        n = sum(v.values())
        med = jobqueue.median_runtime(qdb, suite)
        lines.append(f"  {suite:<18} {v.get('done', 0):>6}/{n:<6} done  pending {v.get('pending', 0):>6}  "
                     f"failed {v.get('failed', 0) + v.get('timeout', 0):>4}  median {med:.1f} s/job" if med else
                     f"  {suite:<18} {v.get('done', 0):>6}/{n:<6} done  pending {v.get('pending', 0):>6}  "
                     f"failed {v.get('failed', 0) + v.get('timeout', 0):>4}")
    wp, _ = layout("polite", compute, cfg)
    wf, _ = layout("full", compute, cfg)
    cur = st.get("workers") if pid else None
    eta_line = f"ETA (median job runtime): polite {_fmt_dur(eta_seconds(qdb, wp))} ({wp} workers), " \
               f"full {_fmt_dur(eta_seconds(qdb, wf))} ({wf} workers)"
    if cur and cur not in (wp, wf):
        eta_line += f", current {_fmt_dur(eta_seconds(qdb, cur))} ({cur} workers)"
    if pid and st.get("status") == "paused":
        eta_line += " — paused; the clock restarts when AC returns"
    lines.append(eta_line)
    fails = jobqueue.failures_by_type(qdb)
    if fails:
        lines.append("Failures by type:")
        for f in fails:
            lines.append(f"  {f['error_type'] or 'unknown':<28} {f['n']:>5}  [{f['suites']}]  e.g. {(f['example'] or '')[:110]}")
    runs = [r for r in jobqueue.last_runs(qdb, 3) if r.get("report_dir")]
    if runs:
        lines.append(f"Latest report: {Path(runs[0]['report_dir']).relative_to(ROOT) if str(ROOT) in runs[0]['report_dir'] else runs[0]['report_dir']}/validation_report.md")
    elif pid and (Path(st.get("run_dir", "")) / "partial" / "validation_report.md").is_file():
        lines.append(f"Latest partial report: {st['run_dir']}/partial/validation_report.md")
    return "\n".join(lines)
