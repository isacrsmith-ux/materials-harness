"""CLI:  python -m harness run --suite smoke|substitution|stability|ood|experimental|bulk|all
       python -m harness report [--out DIR] [--compare-previous]
       python -m harness predict --parent <mp-id|CIF|file> --substitute Sr:Ba [--json]
       python -m harness calibrate    freeze the product's calibration bundle (fitted once)
       python -m harness benchmark
       python -m harness info
       python -m harness prepare      bulk-download inputs, generate pairs, fill the job queue
       python -m harness unattended   drain the queue (use ./run_unattended.sh to run it in the background)
       python -m harness status       progress, ETA, mode, failures
       python -m harness stop         graceful stop (finish running jobs, then exit)
       python -m harness schedule     nightly launchd agents (run + backup): generate the plists, print install commands
       python -m harness standup [--verify]    the morning screen (and a database integrity check)
       python -m harness checkpoint "<message>" [--dry-run]   git commit with run metadata (never pushes)
       python -m harness backup [--dest DIR]  verified, pruned backup (use scripts/backup.sh; restore: scripts/restore.sh)
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

SUITES = ["smoke", "substitution", "stability", "ood", "experimental", "bulk", "mode_b", "polymorph"]


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

    pr = sub.add_parser("predict", help="one candidate -> one decision (the product)")
    pr.add_argument("--parent", required=True, help="mp-id, CIF string, or path to a structure file")
    pr.add_argument("--substitute", help="element swap, e.g. Sr:Ba (omit to score --parent as it stands)")
    pr.add_argument("--json", action="store_true", help="machine-readable output")
    pr.add_argument("--engine", help="registry key of the engine (default: the production engine)")
    pr.add_argument("--no-second-engine", action="store_true",
                    help="skip the disagreement check; uses the rule certified for that configuration")
    pr.add_argument("--bulk-modulus", action="store_true", help="also fit an EOS (nine more relaxations)")
    pr.add_argument("--no-ladder", action="store_true", help="do not run the fallback ladder on a rejected relaxation")
    cal = sub.add_parser("calibrate", help="freeze the product's calibration bundle from the calibration set")
    cal.add_argument("--force", action="store_true", help="refit and overwrite an existing bundle")

    poly = sub.add_parser("polymorph", help="polymorph ranking (build / eta / report; run with `run --suite polymorph`)")
    poly.add_argument("action", choices=["build", "eta", "report"])
    poly.add_argument("--force", action="store_true", help="re-choose the compositions")
    poly.add_argument("--n", type=int, help="number of compositions (build)")
    poly.add_argument("--per-relaxation-s", type=float, default=9.5, help="measured cost per relaxation, for the ETA")

    un_ = sub.add_parser("unseen", help="the unseen-real-materials test (build / eta / run / report)")
    un_.add_argument("action", choices=["build", "eta", "run", "report"])
    un_.add_argument("--force", action="store_true", help="rebuild an existing frozen set")
    un_.add_argument("--workers", type=int)
    un_.add_argument("--threads", type=int)
    un_.add_argument("--per-candidate-s", type=float, default=29.2,
                     help="measured serial cost per candidate, for the ETA")

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
    cst = sub.add_parser("costs", help="cost-based operating point from cached calibration results -> reports/costs.md")
    cst.add_argument("--fp", type=float, help="cost of one wasted lab test (default: config/costs.json)")
    cst.add_argument("--fn", type=float, help="cost of one missed stable material (default: config/costs.json)")
    cst.add_argument("--model", help="registry key (default: the recommended engine)")
    cst.add_argument("--out", help="write somewhere other than reports/costs.md")
    p0 = sub.add_parser("phase0", help="Phase 0 audits, queue ETA, before/after report")
    p0.add_argument("action", choices=["audit", "eta", "report"])
    p0.add_argument("--queue-db", default=str(QUEUE_DB))
    sch = sub.add_parser("schedule", help="generate the nightly launchd plist and print install commands")
    sch.add_argument("--write", action="store_true", help="(re)write config/launchd/<label>.plist")
    su = sub.add_parser("standup", help="the morning screen: progress, what finished, failures, mode, disk, metric moves")
    su.add_argument("--verify", action="store_true",
                    help="also check both databases open cleanly and the queue reconciles with the results table")
    su.add_argument("--queue-db", default=str(QUEUE_DB))
    ck = sub.add_parser("checkpoint", help="git commit code, reports and database schema/summaries with run metadata")
    ck.add_argument("message")
    ck.add_argument("--dry-run", action="store_true", help="show the files and message without committing")
    ck.add_argument("--queue-db", default=str(QUEUE_DB))
    bk = sub.add_parser("backup", help="verified, pruned snapshot of results/, reports/, config/ (use scripts/backup.sh)")
    bk.add_argument("--dest", help="destination directory (default: HARNESS_BACKUP_DIR from .env, else backups/)")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    try:
        assert_native_arm64()
    except PlatformError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "standup":
        from harness import ops

        text, ok = ops.standup(args.queue_db, verify=args.verify)
        print(text)
        return 0 if ok else 1
    if args.cmd == "checkpoint":
        from harness import ops

        print(ops.checkpoint(args.message, queue_db=args.queue_db, dry_run=args.dry_run))
        return 0
    if args.cmd == "backup":
        from harness import ops

        try:
            info = ops.backup(dest=args.dest)
        except RuntimeError as exc:
            print(f"STOP: {exc}", file=sys.stderr)
            return 3
        print(ops.backup_summary(info))
        return 1 if info["problems"] else 0

    if args.cmd == "info":
        print(json.dumps({"machine": machine_info(), "compute": {k: v for k, v in load_compute_config().items()
                                                                if not k.endswith("benchmark")}}, indent=2))
        return 0
    if args.cmd == "predict":
        from harness import predict as P
        from harness.screening import benchmarked_models

        engine = None
        if args.engine:
            setting = {k: (k, d, t) for k, d, t in benchmarked_models()}
            if args.engine not in setting:
                print(f"STOP: {args.engine} has no benchmarked compute config", file=sys.stderr)
                return 2
            engine = setting[args.engine]
        try:
            p = P.predict(args.parent, args.substitute, engine=engine,
                          second_engine=None if args.no_second_engine else P.SECOND_ENGINE,
                          use_ladder=not args.no_ladder, with_bulk_modulus=args.bulk_modulus)
        except (ValueError, KeyError, FileNotFoundError) as exc:
            print(f"STOP: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        print(p.to_json() if args.json else P.render(p))
        return 0
    if args.cmd == "calibrate":
        from harness import calibration

        try:
            b = calibration.build(force=args.force)
        except FileExistsError as exc:
            print(f"STOP: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote {calibration.BUNDLE_FILE.relative_to(harness.ROOT)} "
              f"({b['calibration_set']['n_usable']} calibration structures, engine {b['engine']['name']})")
        return 0
    if args.cmd == "polymorph":
        from harness.suites import polymorph

        if args.action == "build":
            doc = polymorph.build(**({"n_compositions": args.n} if args.n else {}), force=args.force)
            print(json.dumps({k: v for k, v in doc.items() if k != "sets"}, indent=1, default=str))
        elif args.action == "eta":
            doc = polymorph.load()
            c = load_compute_config()
            n = doc["n_relaxations"]
            for label, w in (("full", c["workers"]), ("polite", max(1, c["workers"] - 2))):
                print(f"{label} ({w} workers): {n} relaxations x {args.per_relaxation_s:.1f} s "
                      f"= {n * args.per_relaxation_s / w / 3600:.2f} h")
        else:
            print(f"Wrote {polymorph.report()}")
        return 0
    if args.cmd == "unseen":
        from harness import unseen

        if args.action == "build":
            print(json.dumps(unseen.build(force=args.force), indent=1, default=str))
        elif args.action == "eta":
            doc = unseen.load()
            for label, w in (("full", args.workers or 5), ("polite", 3)):
                print(f"{label}: {json.dumps(unseen.eta(doc['pairs'], w, args.per_candidate_s), default=str)}")
        elif args.action == "run":
            doc = unseen.load()
            print(json.dumps(unseen.eta(doc["pairs"], args.workers or 5, args.per_candidate_s), indent=1))
            unseen.prefetch(doc["pairs"])
            print(f"Wrote {unseen.run(workers=args.workers, threads=args.threads)}")
        else:
            print(f"Wrote {unseen.report()}")
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
    if args.cmd == "costs":
        from pathlib import Path

        from harness import costs, screening
        from harness.report import _costs

        cfg = _costs()
        fp = args.fp if args.fp is not None else cfg["cost_false_positive"]
        fn = args.fn if args.fn is not None else cfg["cost_missed_stable"]
        setting = {k: (k, d, t) for k, d, t in screening.benchmarked_models()}
        key, device, dtype = setting[args.model or costs.PRIMARY[0]]
        print(f"Wrote {costs.report(fp, fn, key, device, dtype, out=Path(args.out) if args.out else None)}")
        return 0
    if args.cmd == "phase0":
        from harness import phase0

        out = {"audit": phase0.audit, "eta": lambda: phase0.eta(args.queue_db), "report": phase0.report}[args.action]()
        print(json.dumps(out, indent=1, default=str) if isinstance(out, dict) else f"Wrote {out}")
        return 0
    if args.cmd == "schedule":
        from harness.schedule import instructions, write_plist

        if args.write:
            print("Wrote " + ", ".join(str(p) for p in write_plist()))
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
