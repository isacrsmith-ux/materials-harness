#!/usr/bin/env python
"""The 'locked and unopened as of this document' ledger, verified rather than asserted.

For every locked half: its size, its recorded sha256, whether that hash still verifies, whether the
accessor still refuses without unlock=True, and whether any of its ids appear in the results store
(which would mean it had been relaxed or scored). Writes reports/round2_ledger.json.
"""

from __future__ import annotations

import hashlib
import json

from harness import round2, splits, store
from harness.calibration import PRODUCTION_ENGINE
from harness.config import REPORTS_DIR, settings_tag

# expected_opened: the original WBM test was deliberately opened once, for the final evaluation on
# 2026-09-12 (reports/final_test.md). Round 2 must not open it AGAIN, and must not open any other.
SETS = [
    ("original WBM locked test", lambda: splits.load_split()["test"], splits.test_ids, (), True),
    ("oxide locked test (round 1)", lambda: splits.load_split(splits.FAMILY_SPLIT_FILE)["families"]["oxide"]["test"],
     splits.family_test_ids, ("oxide",), False),
    ("halide locked test (round 1)", lambda: splits.load_split(splits.FAMILY_SPLIT_FILE)["families"]["halide"]["test"],
     splits.family_test_ids, ("halide",), False),
    ("sulfide locked test (round 2)", lambda: round2.load()["groups"]["sulfide"]["test"], round2.test_ids, ("sulfide",), False),
]


def main() -> None:
    key, device, dtype = PRODUCTION_ENGINE
    tag = settings_tag(device, dtype, model=key)
    scored = {k.split("@")[0].split(":")[0] for k in store.completed_keys("ood", retry_failed=True)}
    rows = []
    for name, get, accessor, args, expected_opened in SETS:
        t = get()
        ids = t["ids"]
        h = hashlib.sha256(",".join(ids).encode()).hexdigest()
        try:
            accessor(*args)
            refuses = False
        except PermissionError:
            refuses = True
        touched = sorted(set(ids) & scored)
        rows.append({"set": name, "n": t["n"], "locked": t["locked"], "opened_once_by_design": expected_opened,
                     "sha256": t["sha256"], "hash_verifies": h == t["sha256"],
                     "accessor_refuses_without_unlock": refuses,
                     "n_ids_with_results_in_store": len(touched),
                     "example_touched": touched[:3],
                     "state": ("opened once, 2026-09-12, reports/final_test.md" if expected_opened
                               else ("UNOPENED" if not touched else "*** TOUCHED ***"))})
    out = {"engine": f"{key} {device}/{dtype}", "settings_tag": tag,
           "meaning": ("'unopened' means: the hash still verifies, the accessor still raises "
                       "PermissionError without unlock=True, and no id of the set has a result in "
                       "the results store under the production tag. The original WBM test set was "
                       "opened once by design on 2026-09-12 and is reported as such; round 2 did "
                       "not open it again and did not open any other."),
           "sets": rows,
           "all_locked_and_unopened": all(
               r["hash_verifies"] and r["accessor_refuses_without_unlock"]
               and (r["n_ids_with_results_in_store"] == 0 or r["opened_once_by_design"]) for r in rows)}
    (REPORTS_DIR / "round2_ledger.json").write_text(json.dumps(out, indent=1) + "\n")
    for r in rows:
        print(f"{r['set']:32s} n={r['n']:5d} hash {'ok' if r['hash_verifies'] else 'FAIL'}  "
              f"refuses {'yes' if r['accessor_refuses_without_unlock'] else 'NO'}  "
              f"results in store: {r['n_ids_with_results_in_store']:5d}  {r['state']}")
    print("ALL LOCKED AND UNOPENED" if out["all_locked_and_unopened"] else "*** A LOCKED SET WAS TOUCHED ***")


if __name__ == "__main__":
    main()
