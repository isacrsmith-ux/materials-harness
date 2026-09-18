#!/usr/bin/env python
"""Round-4 driver: re-measure the three carried-over families. Development only.

    python scripts/round4.py assert-engine
    python scripts/round4.py split            # make the calibration draws (once)
    python scripts/round4.py enqueue          # queue them

f-electron, intermetallic and pnictide carry the 2026-09-12 thresholds, fitted on 1,747 / 645 / 202
labelable rows. Nothing in round 2 or round 3 touched them.

This driver reserves NO held-out half and opens NO locked half. The engine assertion is not a
formality: the round-1 calibration silently ran on MACE-MP-0 because HARNESS_MODEL was unset and
produced a certification verdict that was wrong.
"""

from __future__ import annotations

import sys

from harness import round4
from harness.config import QUEUE_DB, load_compute_config
from harness import jobqueue, store

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from round2 import _assert_locked_untouched, assert_engine  # noqa: E402  reuse, do not re-implement


def _assert_round4_reserves_nothing() -> None:
    """Round 4 must not be able to hand out a held-out half, because it never made one."""
    if not round4.SPLIT_FILE.exists():
        return
    for fam in round4.groups():
        if round4.load()["groups"][fam]["test"] is not None:
            raise SystemExit(f"ABORT - round 4 reserved a test half for {fam!r}; it is development only")
        try:
            round4.test_ids(fam)
        except PermissionError:
            continue
        raise SystemExit(f"ABORT - round4.test_ids({fam!r}) handed out ids")
    print("round 4 reserves no held-out half: asserted for every family")


def make_split() -> None:
    from harness.suites import ood

    assert_engine()
    _assert_locked_untouched()
    out = round4.make_split(ood.load_summary())
    print(f"\nwrote {round4.SPLIT_FILE}")
    print(f"  pool {out['pool_size']:,}   prior ids excluded {out['excluded_prior_ids']:,}   "
          f"locked test ids excluded {out['locked_test_ids_excluded']:,}   "
          f"dropped on locked formula {out['dropped_sharing_locked_test_formula']:,}")
    for fam, g in out["groups"].items():
        print(f"  {fam:14s} calibration {g['calibration']['n']:5,}  of {g['available']:7,} available  "
              f"({g['unspent_after_draw']:7,} left unspent and still eligible)  "
              f"was fitted on {g['carried_over_threshold_n']:,}")
    print(f"  all ids sha256 {out['sha256_all_calibration_ids']}")
    _assert_round4_reserves_nothing()


def enqueue() -> None:
    from harness import orchestrator as O

    tag, compute = assert_engine()
    _assert_locked_untouched()
    _assert_round4_reserves_nothing()

    ids = {i for fam in round4.groups() for i in round4.calibration_ids(fam)}
    for fam in round4.groups():
        print(f"  round 4 {fam}: {len(round4.calibration_ids(fam)):,} calibration ids")
    jobs = O.build_round4_jobs(compute, only_ids=ids)
    done = set()
    for suite in ("ood", "substitution_auto", "substitution", "stability"):
        done |= store.completed_keys(suite, retry_failed=True)
    info = jobqueue.enqueue(jobs, QUEUE_DB, done_keys=done)
    print(f"round4: {len(jobs)} jobs -> {info}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "assert-engine":
        assert_engine()
        _assert_locked_untouched()
        _assert_round4_reserves_nothing()
    elif cmd == "split":
        make_split()
    elif cmd == "enqueue":
        enqueue()
    else:
        raise SystemExit(__doc__)
