"""CLI:  python -m harness run --suite smoke|substitution|stability|ood|experimental|bulk|all
       python -m harness report
       python -m harness benchmark
       python -m harness info
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time

import harness  # noqa: F401  (sets cache env vars first)
from harness.config import LOG_DIR, load_compute_config
from harness.platform_check import PlatformError, assert_native_arm64, machine_info

SUITES = ["smoke", "substitution", "stability", "ood", "experimental", "bulk"]


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

    sub.add_parser("report", help="write reports/validation_report.md from the results table")
    sub.add_parser("benchmark", help="CPU/float64 vs MPS/float32 + worker/thread layouts -> config/compute.json")
    sub.add_parser("info", help="print machine + compute config")

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

        run_benchmark()
        return 0
    if args.cmd == "report":
        from harness.report import write_report

        path = write_report()
        print(f"Wrote {path}")
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
