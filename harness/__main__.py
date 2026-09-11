"""CLI:  python -m harness run --suite smoke|substitution|stability|ood|experimental|bulk|all
       python -m harness report [--out DIR] [--compare-previous]
       python -m harness benchmark
       python -m harness info
       python -m harness prepare      bulk-download inputs, generate pairs, fill the job queue
       python -m harness unattended   drain the queue (use ./run_unattended.sh to run it in the background)
       python -m harness status       progress, ETA, mode, failures
       python -m harness stop         graceful stop (finish running jobs, then exit)
       python -m harness schedule     nightly launchd agent: generate the plist, print install commands
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time

import harness  # noqa: F401  (sets cache env vars first)
from harness.config import LOG_DIR, QUEUE_DB, load_compute_config, load_unattended_config
from harness.platform_check import PlatformError, assert_native_arm64, machine_info

SUITES = ["smoke", "substitution", "stability", "ood", "experimental", "bulk", "mode_b"]


def _setup_logging(verbose: bool) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format=fmt,
                        handlers=[logging.StreamHandler(sys.stderr), logging.FileHandler(LOG_DIR / "harness.log")])
    for noisy in ("urllib3", "matplotlib", "httpx", "botocore", "mp_api"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run validation suites (resumable)")
    run.add_argument("--suite", required=True, choices=SUITES + ["all"])
    run.add_argument("--retry-failed", action="store_true", help="re-run jobs that failed or timed out")
    run.add_argument("--workers", type=int, help="override config/compute.json")
    run.add_argument("--threads", type=int, help="torch threads per worker (override)")
    run.add_argument("--limit", type=int, help="only the first N jobs (debugging)")

    rep = sub.add_parser("report", help="write a validation report from the results table")
    rep.add_argument("--out", help="output directory (default: reports/)")
    rep.add_argument("--compare-previous", action="store_true", help="compare the scorecard with the previous run")
    bench = sub.add_parser("benchmark", help="device/dtype + worker layouts for the active model -> config/benchmark-<model>.json")
    bench.add_argument("--no-save-compute", action="store_true",
                       help="do not rewrite the model's compute config (always implied for the baseline model)")
    sub.add_parser("info", help="print machine + compute config")

    cfg = load_unattended_config()
    prep = sub.add_parser("prepare", help="bulk-download MP/WBM inputs, generate substitution pairs, fill the queue")
    prep.add_argument("--max-pairs", type=int, default=cfg["max_pairs"])
    prep.add_argument("--max-atoms", type=int, default=cfg["max_atoms"])
    prep.add_argument("--ood-n", type=int, default=cfg["ood_sample"], help="WBM out-of-distribution sample size")
    prep.add_argument("--skip-pairs", action="store_true")
    prep.add_argument("--skip-ood", action="store_true")
    prep.add_argument("--force-pairs", action="store_true", help="regenerate data/auto_pairs.json")
    prep.add_argument("--curated-kinds", help="comma list of curated-pair substitution kinds to queue "
                                              "(e.g. sub_rescaled,sub_rattled_rescaled,static)")
    prep.add_argument("--competitor-retries", action="store_true",
                      help="queue the fallback ladder for rejected stability competitor relaxations")
    prep.add_argument("--wbm-calibration", action="store_true",
                      help="queue relaxation + DFT-geometry single point for every WBM calibration id (never the test set)")
    prep.add_argument("--screening", action="store_true",
                      help="queue the model-screening subset (data/screening_subset.json) for the ACTIVE model (HARNESS_MODEL)")
    prep.add_argument("--mode-b", action="store_true",
                      help="queue competitor relaxations for the mode (b) sample of WBM calibration systems")
    prep.add_argument("--retries", action="store_true",
                      help="queue the fallback ladder for every guard-rejected relaxation in every suite")
    prep.add_argument("--queue-db", default=str(QUEUE_DB))

    un = sub.add_parser("unattended", help="drain the job queue (see ./run_unattended.sh)")
    un.add_argument("--mode", choices=["polite", "full"], default="polite")
    un.add_argument("--stop-at", help="HH:MM — finish running jobs and exit at this time")
    un.add_argument("--queue-db", default=str(QUEUE_DB))
    un.add_argument("--max-jobs", type=int, help="dispatch at most N jobs, then drain (testing)")
    un.add_argument("--power-poll", type=float, help="seconds between pmset checks (default from config)")
    un.add_argument("--workers", type=int, help="override the mode's worker count")
    un.add_argument("--threads", type=int, help="override torch threads per worker")
    un.add_argument("--report-every", type=int, help="partial report every N completed jobs")

    for name, text in (("status", "queue progress, ETA, mode, failures"), ("stop", "graceful stop request"),
                       ("requeue-failed", "put failed / timed-out queue jobs back to pending (after a fix)")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--queue-db", default=str(QUEUE_DB))
    ft = sub.add_parser("final-test", help="ONE-TIME locked-test evaluation (start -> queue -> evaluate)")
    ft.add_argument("action", choices=["start", "queue", "evaluate"])
    ft.add_argument("--models", help="comma list of registry keys: primary first, second engine for disagreement")
    ft.add_argument("--queue-db", default=str(QUEUE_DB))
    sub.add_parser("candidates", help="Phase 3 candidate table -> reports/phase3/candidates.md")
    sub.add_parser("compare-models", help="Phase 3 screening comparison -> reports/phase3/screening.md")
    p0 = sub.add_parser("phase0", help="Phase 0 audits, queue ETA, before/after report")
    p0.add_argument("action", choices=["audit", "eta", "report"])
    p0.add_argument("--queue-db", default=str(QUEUE_DB))
    sch = sub.add_parser("schedule", help="generate the nightly launchd plist and print install commands")
    sch.add_argument("--write", action="store_true", help="(re)write config/launchd/<label>.plist")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    try:
        assert_native_arm64()
    except PlatformError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "info":
        print(json.dumps({"machine": machine_info(), "compute": {k: v for k, v in load_compute_config().items()
                                                                if not k.endswith("benchmark")}}, indent=2))
        return 0
    if args.cmd == "benchmark":
        from harness.benchmark import run_benchmark
        from harness.config import ACTIVE_MODEL, BASELINE_MODEL

        run_benchmark(save_compute=not args.no_save_compute and ACTIVE_MODEL != BASELINE_MODEL)
        return 0
    if args.cmd == "report":
        from pathlib import Path

        from harness.report import write_report

        path = write_report(out_dir=Path(args.out) if args.out else None, compare_previous=args.compare_previous)
        print(f"Wrote {path}")
        return 0
    if args.cmd == "prepare":
        from harness.orchestrator import prepare

        cfg.update(max_pairs=args.max_pairs, max_atoms=args.max_atoms, ood_sample=args.ood_n)
        info = prepare(cfg, queue_db=args.queue_db, do_pairs=not args.skip_pairs, do_ood=not args.skip_ood,
                       force_pairs=args.force_pairs,
                       curated_kinds=[k for k in (args.curated_kinds or "").split(",") if k] or None,
                       competitor_retries=args.competitor_retries, retries=args.retries,
                       wbm_calibration=args.wbm_calibration, mode_b=args.mode_b, screening=args.screening)
        print(json.dumps(info, indent=1, default=str))
        return 0
    if args.cmd == "unattended":
        from harness.orchestrator import AlreadyRunning, Runner

        try:
            status = Runner(mode=args.mode, queue_db=args.queue_db, stop_at=args.stop_at, max_jobs=args.max_jobs,
                            power_poll_s=args.power_poll, workers=args.workers, report_every=args.report_every,
                            threads=args.threads).run()
        except AlreadyRunning as exc:
            print(f"Not started: {exc}", file=sys.stderr)
            return 3
        return 0 if status in ("finished", "stopped") else 1
    if args.cmd == "status":
        from harness.orchestrator import status_report

        print(status_report(args.queue_db))
        return 0
    if args.cmd == "requeue-failed":
        from harness import jobqueue

        print(f"{jobqueue.requeue_failed(args.queue_db)} failed / timed-out jobs put back to pending.")
        return 0
    if args.cmd == "stop":
        from harness.orchestrator import request_stop

        pid = request_stop(args.queue_db)
        print(f"Stop requested: runner pid {pid} will finish its running jobs and exit." if pid
              else "No runner is working on that queue.")
        return 0
    if args.cmd == "final-test":
        from harness import final_eval, jobqueue, screening

        if args.action == "start":
            print(json.dumps(final_eval.start(args.models.split(",")), indent=1))
        elif args.action == "queue":
            jobs = final_eval.build_test_jobs(load_compute_config())
            print(jobqueue.enqueue(jobs, args.queue_db))
        else:
            setting = {k: (k, d, t) for k, d, t in screening.benchmarked_models()}
            keys = args.models.split(",")
            print(f"Wrote {final_eval.evaluate(setting[keys[0]], setting[keys[1]] if len(keys) > 1 else None)}")
        return 0
    if args.cmd == "candidates":
        from harness import candidates

        print(f"Wrote {candidates.write()}")
        return 0
    if args.cmd == "compare-models":
        from harness import screening

        print(f"Wrote {screening.write_report()}")
        return 0
    if args.cmd == "phase0":
        from harness import phase0

        out = {"audit": phase0.audit, "eta": lambda: phase0.eta(args.queue_db), "report": phase0.report}[args.action]()
        print(json.dumps(out, indent=1, default=str) if isinstance(out, dict) else f"Wrote {out}")
        return 0
    if args.cmd == "schedule":
        from harness.schedule import instructions, write_plist

        if args.write:
            print(f"Wrote {write_plist()}")
        print(instructions())
        return 0

    compute = load_compute_config()
    if args.workers:
        compute["workers"] = args.workers
    if args.threads:
        compute["threads_per_worker"] = args.threads
    log = logging.getLogger("harness")
    log.info("compute: device=%s dtype=%s workers=%s threads/worker=%s (%s)", compute["device"], compute["dtype"],
             compute["workers"], compute["threads_per_worker"], compute.get("source"))

    status = 0
    for name in SUITES if args.suite == "all" else [args.suite]:
        try:
            mod = importlib.import_module(f"harness.suites.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"harness.suites.{name}":
                log.warning("suite %s is not implemented yet — skipping", name)
                continue
            raise
        t0 = time.perf_counter()
        log.info("=== suite %s ===", name)
        try:
            mod.run(compute=compute, retry_failed=args.retry_failed, limit=args.limit)
        except Exception:  # noqa: BLE001 — one broken suite shouldn't stop `--suite all`
            log.exception("suite %s crashed", name)
            status = 1
        log.info("=== suite %s finished in %.1f s ===", name, time.perf_counter() - t0)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
