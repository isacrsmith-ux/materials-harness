#!/usr/bin/env python
"""Round-2 driver: enqueue one phase at a time, asserting the production engine every time.

    python scripts/round2.py assert-engine
    python scripts/round2.py enqueue phase1          # ~500 per new family, the diagnostic pull
    python scripts/round2.py enqueue phase2          # the halide top-up
    python scripts/round2.py enqueue phase3          # the rest of the four new families
    python scripts/round2.py enqueue multistart      # phase 5 extra starting configurations
    python scripts/round2.py enqueue retries         # phase 6 fallback ladder for every failure

The engine assertion is not a formality: the round-1 calibration silently ran on MACE-MP-0 because
HARNESS_MODEL was unset, reported "0 failed", and produced a certification verdict that was wrong.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from harness import config, jobqueue, round2, store
from harness.calibration import PRODUCTION_ENGINE
from harness.config import QUEUE_DB, load_compute_config

PHASE1_PER_FAMILY = 500
PHASE1_SEED = 20260918
MULTISTART_N = 1000     # candidates given extra starting configurations in phase 5
MULTISTART_SEED = 4242


def assert_engine() -> tuple[str, dict]:
    """Abort unless this process is the adopted production engine, at its benchmarked layout."""
    key, device, dtype = PRODUCTION_ENGINE
    compute = load_compute_config()
    tag = config.settings_tag(compute["device"], compute["dtype"])
    expect = config.settings_tag(device, dtype, model=key)
    problems = []
    if config.ACTIVE_MODEL != key:
        problems.append(f"HARNESS_MODEL resolves to {config.ACTIVE_MODEL!r}, not the production engine {key!r}")
    if (compute["device"], compute["dtype"]) != (device, dtype):
        problems.append(f"compute config is {compute['device']}/{compute['dtype']}, not {device}/{dtype}")
    if tag != expect:
        problems.append(f"settings_tag {tag} != production tag {expect}")
    config.model_path(key)  # re-verifies the checkpoint sha256
    print(f"engine   {config.MODEL['name']} ({config.ACTIVE_MODEL})")
    print(f"checkpoint sha256 {config.MODEL['sha256']}  verified on disk")
    print(f"settings_tag {tag}   device {compute['device']}/{compute['dtype']}  "
          f"workers {compute.get('workers')}x{compute.get('threads_per_worker')}")
    if problems:
        raise SystemExit("ABORT - engine mismatch:\n  " + "\n  ".join(problems))
    print("locked sets: unlock=False asserted (nothing in this path passes unlock=True)")
    return tag, compute


def _assert_locked_untouched() -> None:
    """Every locked half is still locked, still hash-verified, and still refuses to hand out ids."""
    from harness import splits

    checks = [(splits.test_ids, ()), (splits.family_test_ids, ("oxide",)),
              (splits.family_test_ids, ("halide",)), (round2.test_ids, ("sulfide",)),
              (round2.test_ids, ("halide_topup",))]
    checks += [(round2.test_ids3, (g,)) for g in (round2.groups3() if round2.ROUND3_SPLIT_FILE.exists() else [])]
    for fn, args in checks:
        try:
            fn(*args)
        except PermissionError:
            continue
        raise SystemExit(f"ABORT - {fn.__name__}{args} handed out locked ids without unlock=True")
    n = len(splits.excluded_ids() | splits.family_excluded_ids() | round2.excluded_ids()
            | round2.excluded_ids3())
    print(f"locked/prior ids verified by hash and excluded from every draw: {n}")


def _phase1_ids() -> dict[str, list[str]]:
    out = {}
    for i, fam in enumerate(round2.NEW_FAMILIES):
        ids = round2.calibration_ids(fam)
        k = min(PHASE1_PER_FAMILY, len(ids))
        pick = np.random.default_rng(PHASE1_SEED + i).choice(len(ids), size=k, replace=False)
        out[fam] = sorted(ids[j] for j in pick)
    return out


def _enqueue(jobs, label) -> None:
    done = set()
    for suite in ("ood", "substitution_auto", "substitution", "stability"):
        done |= store.completed_keys(suite, retry_failed=True)
    info = jobqueue.enqueue(jobs, QUEUE_DB, done_keys=done)
    print(f"{label}: {len(jobs)} jobs -> {info}")


def enqueue(phase: str) -> None:
    from harness import orchestrator as O

    tag, compute = assert_engine()
    _assert_locked_untouched()

    if phase == "phase1":
        sel = _phase1_ids()
        for f, ids in sel.items():
            print(f"  phase 1 {f}: {len(ids)} of {len(round2.calibration_ids(f))}")
        ids = {i for v in sel.values() for i in v}
        (config.DATA_DIR / "round2_phase1_ids.json").write_text(
            json.dumps({"seed": PHASE1_SEED, "per_family": PHASE1_PER_FAMILY,
                        "groups": {k: v for k, v in sel.items()}}, indent=1) + "\n")
        _enqueue(O.build_round2_jobs(compute, only_ids=ids), "phase1")

    elif phase == "phase2":
        ids = set(round2.calibration_ids(round2.HALIDE_TOPUP))
        print(f"  phase 2 halide top-up: {len(ids)} new calibration ids "
              f"(round-1 halide calibration was 3,500; combined {3500 + len(ids)})")
        _enqueue(O.build_round2_jobs(compute, only_ids=ids), "phase2")

    elif phase == "phase3":
        sel = json.loads((config.DATA_DIR / "round2_phase1_ids.json").read_text())["groups"]
        done = {i for v in sel.values() for i in v}
        ids = {i for f in round2.NEW_FAMILIES for i in round2.calibration_ids(f)} - done
        print(f"  phase 3: {len(ids)} remaining ids across {', '.join(round2.NEW_FAMILIES)}")
        _enqueue(O.build_round2_jobs(compute, only_ids=ids), "phase3")

    elif phase == "round3":
        ids = {i for g in round2.groups3() for i in round2.calibration_ids3(g)}
        for g in round2.groups3():
            print(f"  round 3 {g}: {len(round2.calibration_ids3(g))} calibration ids")
        _enqueue(O.build_round3_jobs(compute, only_ids=ids), "round3")

    elif phase == "retries":
        jobs = O.build_retry_jobs(compute)
        _enqueue(jobs, "retries")

    else:
        raise SystemExit(f"unknown phase {phase!r}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "assert-engine":
        assert_engine()
        _assert_locked_untouched()
    elif sys.argv[1] == "enqueue":
        enqueue(sys.argv[2])
    else:
        raise SystemExit(__doc__)
