#!/usr/bin/env python
"""TRACK 2, step 1 — FREEZE the f-electron development top-up before any outcome is computed.

    python scripts/felectron_topup_freeze.py

Writes data/felectron_topup_freeze.json (the frozen analysis plan) and
data/felectron_topup_ids.json (the candidate ids and their sha256), then stops. Refuses to overwrite
either. It runs NO job and computes NO outcome: the whole point is that the plan and the candidate
set exist, committed, before any number is calculated.

DEVELOPMENT EVIDENCE ONLY. The top-up comes from unspent f-electron candidates and is combined with
the round-4 f-electron development draw, which is already spent. No locked set is touched, no
held-out sample is read, and the result cannot change the live f-electron production rule.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone

import pandas as pd
from pymatgen.core import Composition
from scipy.stats import binom

from harness import compare, confidence as C, pnictide_eval, round4, splits
from harness.config import DATA_DIR

FREEZE = DATA_DIR / "felectron_topup_freeze.json"
IDS = DATA_DIR / "felectron_topup_ids.json"
FAMILY = "f-electron"
SEED = 20260921
N_TOPUP = 4800
GRID = len(C.DEC_GRID)
N_FAMILY_SIDE = 6                       # 3 families x 2 sides, the round-4 selection multiplicity
LEVEL_GRID = 1 - 0.05 / GRID            # the development standard round 4 used
LEVEL_FAMILY = 1 - 0.05 / (GRID * N_FAMILY_SIDE)   # the FULL family correction

# Existing round-4 f-electron observations at the live -20 meV rule. Design inputs only.
EXISTING = {"A": {"correct": 414, "calls": 441, "rate": 441 / 4000},
            "B": {"correct": 405, "calls": 429, "rate": 429 / 4000}}


def _kstar(n, target, level):
    if C.cp_lower(n, n, level) < target:
        return None
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if C.cp_lower(mid, n, level) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _power(n, p, target, level):
    ks = _kstar(n, target, level)
    return 0.0 if ks is None else float(1 - binom.cdf(ks - 1, n, p)) if ks else 1.0


def _spent() -> set[str]:
    """Every id any split, draw or evaluation has used, including the pnictide held-out sample."""
    return round4._spent_ids() | round4.excluded_ids() | pnictide_eval.excluded_ids()


def main() -> None:
    if FREEZE.exists() or IDS.exists():
        raise SystemExit("already frozen; the plan and candidate set are written once")
    from harness.suites import ood

    summary = ood.load_summary()
    pool = summary[(summary["unique_prototype"] == True) & summary[ood.REQUIRED].notna().all(axis=1)].copy()  # noqa: E712
    pool["bin"] = pool[splits.HULL_COL].map(lambda e: compare.hull_bin(e, below_zero_bin=True))

    spent = _spent()
    locked = round4._locked_test_ids() | pnictide_eval.excluded_ids()
    locked_formulas = {Composition(f).reduced_formula for f in pool[pool.material_id.isin(locked)].formula}
    rest = pool[~pool.material_id.isin(spent)].copy()
    rest["rf"] = [Composition(f).reduced_formula for f in rest.formula]
    n_before = len(rest)
    rest = rest[~rest.rf.isin(locked_formulas)]
    rest["fam"] = [C.family(f) for f in rest.formula]
    eligible = rest[rest.fam == FAMILY]
    if len(eligible) < N_TOPUP:
        raise SystemExit(f"ABORT - {len(eligible)} eligible, need {N_TOPUP}")

    shares = eligible["bin"].value_counts(normalize=True).reindex(compare.HULL_BINS_WBM).fillna(0)
    quota = splits._quotas(shares, N_TOPUP)
    picks = [eligible[eligible.bin == b].sample(n=min(quota[b], int((eligible.bin == b).sum())),
                                               random_state=SEED + i)
             for i, b in enumerate(compare.HULL_BINS_WBM)]
    drawn = pd.concat(picks)
    ids = sorted(drawn.material_id)
    assert len(ids) == N_TOPUP and len(set(ids)) == N_TOPUP
    assert not set(ids) & spent and not set(ids) & locked

    existing_ids = sorted(round4.calibration_ids(FAMILY))
    combined = sorted(set(existing_ids) | set(ids))
    assert len(combined) == len(existing_ids) + len(ids), "top-up overlaps the round-4 draw"

    # pre-specified power, at the frozen n, under the FULL family correction
    power = {}
    for path, e in EXISTING.items():
        p = e["correct"] / e["calls"]
        total_calls = int(round((4000 + N_TOPUP) * e["rate"]))
        power[path] = {
            "assumed_truth": p,
            "expected_total_calls": total_calls,
            "expected_topup_calls": total_calls - e["calls"],
            "max_errors_allowed_family_corrected": total_calls - (_kstar(total_calls, 0.90, LEVEL_FAMILY) or total_calls),
            "power_family_corrected": _power(total_calls, p, 0.90, LEVEL_FAMILY),
            "power_grid_only": _power(total_calls, p, 0.90, LEVEL_GRID),
            "current_bound_family_corrected": C.cp_lower(e["correct"], e["calls"], LEVEL_FAMILY),
            "current_bound_grid_only": C.cp_lower(e["correct"], e["calls"], LEVEL_GRID),
        }

    IDS.write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "f-electron DEVELOPMENT top-up candidate ids, frozen before any outcome was computed",
        "family": FAMILY, "seed": SEED, "n": len(ids),
        "sha256": hashlib.sha256(",".join(ids).encode()).hexdigest(),
        "pool_size": len(pool), "eligible_after_guards": len(eligible),
        "excluded_prior_ids": len(spent), "locked_or_heldout_ids_excluded": len(locked),
        "dropped_sharing_locked_formula": n_before - len(rest),
        "left_unspent_after_topup": len(eligible) - N_TOPUP,
        "by_bin": drawn.bin.value_counts().to_dict(),
        "leakage_guards": [
            "every id any split, draw or evaluation has used is excluded by id, INCLUDING the pnictide "
            "held-out sample",
            "every candidate sharing a reduced formula with any locked half or the pnictide held-out "
            "sample is dropped",
            "asserted disjoint from the round-4 f-electron development draw it will be combined with",
        ],
        "combined_analysis_population": {
            "round4_development_ids": len(existing_ids),
            "topup_ids": len(ids),
            "total": len(combined),
            "sha256_combined": hashlib.sha256(",".join(combined).encode()).hexdigest(),
        },
        "ids": ids,
    }, indent=1) + "\n")

    FREEZE.write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "state": "FROZEN BEFORE ANY OUTCOME WAS COMPUTED. No job has been run for the top-up ids.",
        "tier": "DEVELOPMENT EVIDENCE ONLY",
        "question": (
            "After adequate development sample size and the FULL family correction, can the f-electron "
            "stable side clear the 0.90 precision requirement on either or both production paths?"),
        "why": (
            "Round 4 found no certifiable f-electron stable threshold at n=3,495 and the live -20 meV "
            "rule scored a corrected bound of 0.8944 against a 0.90 target. Round 4b appeared to rescue "
            "it on the second-engine path (bound 0.900359) but round 4c showed that rescue does not "
            "survive the 6-fold family correction (bound 0.892556, margin -0.0074). f-electron is "
            "therefore unresolved on both paths, and it is the only family that can currently return "
            "'likely stable' in production."),
        "hypotheses": {
            "F1": {"path": "A (single engine)", "claim": "a stable threshold certifies on the enlarged "
                   "development population under the full family correction", "target": 0.90},
            "F2": {"path": "B (second engine / disagreement filter)", "claim": "same", "target": 0.90},
        },
        "secondary_descriptive": (
            "the LIVE -20 meV rule's bound on the enlarged population, under both the grid-only and the "
            "family-corrected standard, on both paths. Descriptive: it cannot by itself change the "
            "production rule."),
        "analysis_population": (
            "the round-4 f-electron development draw (4,000 ids, already spent) PLUS this top-up "
            f"({N_TOPUP} ids) = {4000 + N_TOPUP} structures. Both are development data; combining them "
            "is legitimate precisely because neither is nor ever can be held-out."),
        "correction_procedure": {
            "primary": f"Bonferroni over the {GRID}-point threshold grid AND over the "
                       f"{N_FAMILY_SIDE} family x side selections round 4 made: level "
                       f"{LEVEL_FAMILY:.6f}. This is the FULL family correction.",
            "secondary": f"grid only, level {LEVEL_GRID:.6f} - the standard round 4 used, reported for "
                         "comparability and NOT the primary criterion",
            "bound": "one-sided Clopper-Pearson; verdict read from the bound, never the point estimate",
        },
        "sample_size": {"topup": N_TOPUP, "combined": 4000 + N_TOPUP,
                        "basis": ("sized for >= 90% power on Path B under the full family correction "
                                  "against the round-4 point estimate; this is the size previously "
                                  "proposed (~3,320 at 80%, ~4,793 at 90%)")},
        "prespecified_power": power,
        "acknowledged_limitation": (
            "At this size Path A is UNDERPOWERED under the full family correction - roughly 5,325 "
            "top-up structures would be needed for 80% power there against 4,800 drawn. This is "
            "recorded now, before any result: a Path-A failure to certify must therefore be reported "
            "as inconclusive-at-this-size, NOT as evidence that no Path-A threshold exists."),
        "stopping_rule": (
            "One analysis, after every job for every combined id has completed. No interim looks, no "
            "sequential testing, no adding structures after seeing a result. If jobs fail, the failure "
            "count is reported and the analysis proceeds on what completed; it is not rescued by "
            "retrying into a different relaxation rung."),
        "forbidden": [
            "changing the live f-electron production rule on the basis of this result, in either "
            "direction - this is development evidence and a production change needs a pre-registered "
            "held-out evaluation",
            "opening any locked set, or reading the pnictide held-out sample",
            "changing the family definition, precedence, labelable definition, exclusions or targets",
            "enlarging the top-up after seeing an outcome",
            "reporting the grid-only bound as if it were the primary criterion",
        ],
        "candidate_ids_file": {"file": "data/felectron_topup_ids.json",
                               "sha256": hashlib.sha256(IDS.read_bytes()).hexdigest()},
    }, indent=1) + "\n")

    print(f"wrote {IDS}\nwrote {FREEZE}")
    print(f"\n  top-up n = {len(ids):,}  sha256 {hashlib.sha256(','.join(ids).encode()).hexdigest()}")
    print(f"  eligible f-electron candidates {len(eligible):,}; left unspent after this draw "
          f"{len(eligible) - N_TOPUP:,}")
    print(f"  combined development population {len(combined):,} "
          f"(sha256 {hashlib.sha256(','.join(combined).encode()).hexdigest()[:16]}...)")
    for path, pw in power.items():
        print(f"  Path {path}: expected {pw['expected_total_calls']:,} total calls, "
              f"power(family-corrected) {pw['power_family_corrected']:.3f}, "
              f"current bound {pw['current_bound_family_corrected']:.6f}")


if __name__ == "__main__":
    main()
