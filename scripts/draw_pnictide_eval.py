#!/usr/bin/env python
"""Draw the pnictide held-out sample under its pre-registration. Drawn once; refuses to regenerate.

    python scripts/draw_pnictide_eval.py

DRAWS ONLY. It queues nothing, scores nothing and opens nothing. After it runs, the ids exist and
are locked: the accessor raises PermissionError without unlock=True, and no opening log exists.
Evaluating the sample is a separate, separately-approved step.
"""

from __future__ import annotations

import sys
from pathlib import Path

from harness import pnictide_eval

sys.path.insert(0, str(Path(__file__).parent))
from round2 import _assert_locked_untouched, assert_engine  # noqa: E402


def main() -> None:
    # The engine assertion is not needed to draw ids, but it is the cheapest possible check that this
    # is the configured production environment before an irreversible act.
    assert_engine()
    _assert_locked_untouched()

    if pnictide_eval.is_opened():
        raise SystemExit(f"{pnictide_eval.LOG_FILE} exists: the sample has already been opened.")

    from harness.suites import ood

    out = pnictide_eval.make_split(ood.load_summary())

    print(f"\nwrote {pnictide_eval.SPLIT_FILE}")
    print(f"  state: {out['state'].splitlines()[0]}")
    print(f"  pre-registration sha256 verified: {out['preregistration']['sha256']}")
    print(f"  thresholds under test: stable {out['thresholds_under_test']['stable'] * 1000:+.0f} meV, "
          f"unstable {out['thresholds_under_test']['unstable'] * 1000:+.0f} meV (FIXED)")
    print(f"  pool {out['pool_size']:,}  prior ids excluded {out['excluded_prior_ids']:,}  "
          f"locked test ids excluded {out['locked_test_ids_excluded']:,}  "
          f"dropped on locked formula {out['dropped_sharing_locked_test_formula']:,}")
    print(f"  eligible pnictide candidates {out['eligible_pnictide_candidates']:,}")
    print(f"  DRAWN n = {out['test']['n']:,}   sha256 {out['test']['sha256']}")
    print(f"  left unspent and still eligible: {out['left_unspent_after_draw']:,}")
    print(f"  by bin: {out['test']['by_bin']}")

    # The accessor must refuse immediately, before anything else happens.
    try:
        pnictide_eval.test_ids()
    except PermissionError:
        print("\n  locked: test_ids() refuses without unlock=True")
    else:
        raise SystemExit("ABORT - the sample handed out ids without unlock=True")
    print(f"  not opened: {pnictide_eval.LOG_FILE.name} does not exist -> "
          f"{not pnictide_eval.is_opened()}")


if __name__ == "__main__":
    main()
