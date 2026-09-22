#!/usr/bin/env python
"""Draw the f-electron held-out sample under its pre-registration. Drawn once.

    python scripts/draw_felectron_eval.py

DRAWS ONLY. Queues nothing, scores nothing, opens nothing. Refuses unless the pre-registration has
already been PUSHED: a protocol that exists only locally when the sample is drawn is not a
pre-registration, and this is the one check the pnictide draw could not make automatically.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from harness import felectron_eval as FE

sys.path.insert(0, str(Path(__file__).parent))
from round2 import _assert_locked_untouched, assert_engine  # noqa: E402


def _assert_prereg_published() -> None:
    """The pre-registration must be committed AND on the remote before the sample exists."""
    rel = "data/felectron_evaluation_preregistration.json"
    try:
        sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", rel],
                                      text=True).strip()
        if not sha:
            raise SystemExit(f"ABORT - {rel} is not committed")
        subprocess.check_call(["git", "merge-base", "--is-ancestor", sha, "origin/main"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        remote = subprocess.check_output(["git", "show", f"origin/main:{rel}"])
    except subprocess.CalledProcessError:
        raise SystemExit(f"ABORT - the pre-registration commit is not on origin/main. Push it "
                         "before drawing: a protocol that exists only locally is not a "
                         "pre-registration.")
    if hashlib.sha256(remote).hexdigest() != hashlib.sha256(FE.PREREG_FILE.read_bytes()).hexdigest():
        raise SystemExit("ABORT - the local pre-registration differs from the published one")
    print(f"pre-registration published at {sha[:7]} and identical to the local copy")


def main() -> None:
    assert_engine()
    _assert_locked_untouched()
    _assert_prereg_published()
    if FE.is_opened():
        raise SystemExit(f"{FE.LOG_FILE} exists: the sample has already been opened.")

    from harness.suites import ood

    out = FE.make_split(ood.load_summary())
    print(f"\nwrote {FE.SPLIT_FILE}")
    print(f"  {out['state'].splitlines()[0]}")
    print(f"  pre-registration sha256 {out['preregistration']['sha256']}")
    print(f"  thresholds under test: stable {out['thresholds_under_test']['stable']*1000:+.0f} meV, "
          f"unstable {out['thresholds_under_test']['unstable']*1000:+.0f} meV (the LIVE rule, FIXED)")
    print(f"  pool {out['pool_size']:,}  prior ids excluded {out['excluded_prior_ids']:,}  "
          f"protected ids excluded {out['protected_ids_excluded']:,}  "
          f"dropped on protected formula {out['dropped_sharing_protected_formula']:,}")
    print(f"  eligible candidates {out['eligible_candidates']:,}")
    print(f"  DRAWN n = {out['test']['n']:,}   sha256 {out['test']['sha256']}")
    print(f"  left unspent and still eligible: {out['left_unspent_after_draw']:,}")
    print(f"  by bin: {out['test']['by_bin']}")
    print(f"  consumes no existing locked half: {out['consumes_no_existing_locked_half']}")

    try:
        FE.test_ids()
    except PermissionError:
        print("\n  locked: test_ids() refuses without unlock=True")
    else:
        raise SystemExit("ABORT - the sample handed out ids without unlock=True")
    print(f"  not opened: {FE.LOG_FILE.name} absent -> {not FE.is_opened()}")


if __name__ == "__main__":
    main()
