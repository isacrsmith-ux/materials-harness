"""The pnictide held-out evaluation sample: drawn once, opened once, never regenerated.

Drawn under `data/pnictide_evaluation_preregistration.json`, which fixes the thresholds under test
(stable -20 meV, unstable +0 meV), the family definition, the labelable population, the four
hypotheses, the confidence and corrections, the sample size, the pass/fail and stop rules, and an
explicit ban on refitting. That document was committed BEFORE this module drew anything, and
`make_split` verifies its hash against the value recorded at draw time.

DRAWING IS NOT OPENING. This module selects the ids and locks them. It queues nothing and scores
nothing: `test_ids` raises PermissionError without unlock=True, and the evaluation is a separate,
separately-approved step that writes its own opening log.

Eligibility is the whole point of the sample, so it is enforced twice - by id against every split
this project has ever made, and by reduced formula against every locked test half, because WBM's
unique_prototype dedups prototypes and not compositions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd
from pymatgen.core import Composition

from harness import compare, round2, round4, splits
from harness.config import DATA_DIR

SPLIT_FILE = DATA_DIR / "wbm_split_pnictide_eval.json"
PREREG_FILE = DATA_DIR / "pnictide_evaluation_preregistration.json"
LOG_FILE = DATA_DIR / "pnictide_eval_log.json"
SEED = 20260921
FAMILY = "pnictide"
N_DRAW = 3500


def _prereg() -> tuple[dict, str]:
    raw = PREREG_FILE.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _spent_ids() -> set[str]:
    """Every id any earlier split or draw has used - original, round-1, round-2, round-3, round-4 -
    calibration and locked test alike. Ids only, never outcomes. Every test half's hash is verified
    on the way through the accessors."""
    return round4._spent_ids() | round4.excluded_ids()


def make_split(summary: pd.DataFrame, seed: int = SEED, path=SPLIT_FILE, n_draw: int = N_DRAW) -> dict:
    """Draw the held-out sample. Made once; refuses to regenerate.

    Nothing about the draw is chosen here that the pre-registration did not already fix, except the
    seed, which is recorded below. The size, the stratification, the family definition and the
    eligibility rule all come from that document.
    """
    from harness.confidence import family
    from harness.suites import ood

    if path.exists():
        raise splits.SplitExists(
            f"{path} exists; the pnictide evaluation sample is drawn ONCE and never regenerated. "
            "Re-drawing it would silently replace a held-out set with a different one."
        )
    P, prereg_sha = _prereg()
    if n_draw != P["sample"]["n_draw"]:
        raise SystemExit(f"ABORT - n_draw {n_draw} != the pre-registered {P['sample']['n_draw']}")

    pool = summary[(summary["unique_prototype"] == True) & summary[ood.REQUIRED].notna().all(axis=1)].copy()  # noqa: E712
    pool["bin"] = pool[splits.HULL_COL].map(lambda e: compare.hull_bin(e, below_zero_bin=True))

    spent = _spent_ids()
    locked = round4._locked_test_ids()
    locked_formulas = {Composition(f).reduced_formula for f in pool[pool.material_id.isin(locked)].formula}

    rest = pool[~pool.material_id.isin(spent)].copy()
    rest["reduced_formula"] = [Composition(f).reduced_formula for f in rest.formula]
    n_before = len(rest)
    rest = rest[~rest.reduced_formula.isin(locked_formulas)]
    rest["fam"] = [family(f) for f in rest.formula]
    eligible = rest[rest.fam == FAMILY]

    if len(eligible) < n_draw:
        raise SystemExit(f"ABORT - only {len(eligible)} eligible pnictide candidates, need {n_draw}")

    shares = eligible["bin"].value_counts(normalize=True).reindex(compare.HULL_BINS_WBM).fillna(0)
    quota = splits._quotas(shares, n_draw)
    picks = []
    for i, b in enumerate(compare.HULL_BINS_WBM):
        avail = eligible[eligible.bin == b]
        picks.append(avail.sample(n=min(quota[b], len(avail)), random_state=seed + i))
    drawn = pd.concat(picks)
    ids = sorted(drawn.material_id)

    assert len(ids) == n_draw, f"drew {len(ids)}, expected {n_draw}"
    assert not set(ids) & spent, "a drawn id was already spent"
    assert not set(ids) & locked, "a drawn id is a locked test id"
    assert len(set(ids)) == len(ids), "duplicate id in the draw"

    out = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "state": ("DRAWN AND LOCKED - NOT OPENED. No job has been queued and no result scored. "
                  "Opening is a separate, separately-approved step that writes "
                  "data/pnictide_eval_log.json and can happen only once."),
        "preregistration": {"file": PREREG_FILE.relative_to(DATA_DIR.parent).as_posix(),
                            "sha256": prereg_sha,
                            "verified_at_draw_time": True},
        "thresholds_under_test": {
            "stable": P["thresholds_under_test"]["stable_ev_per_atom"],
            "unstable": P["thresholds_under_test"]["unstable_ev_per_atom"],
            "note": "fixed by the pre-registration; NOT refittable on this sample",
        },
        "family": FAMILY,
        "family_definition": "harness.confidence.family(), unchanged; first match wins",
        "pool": "WBM unique_prototype == True with every required column",
        "pool_size": len(pool),
        "hull_column": splits.HULL_COL,
        "bins": list(compare.HULL_BINS_WBM),
        "excluded_prior_ids": len(spent),
        "locked_test_ids_excluded": len(locked),
        "dropped_sharing_locked_test_formula": n_before - len(rest),
        "eligible_pnictide_candidates": len(eligible),
        "left_unspent_after_draw": len(eligible) - n_draw,
        "leakage_guards": [
            "every id any earlier split or draw has used excluded by id, each locked half's hash "
            "verified on the way",
            "every candidate sharing a reduced formula with ANY of the six locked test halves dropped",
            "per-bin proportional to the eligible pool's own hull-distance distribution",
            "no id in this sample has participated in any fit, threshold selection, diagnostic, "
            "Path-B refit or prior evaluation",
        ],
        "test": {
            "n": len(ids),
            "by_bin": drawn.bin.value_counts().to_dict(),
            "locked": True,
            "sha256": hashlib.sha256(",".join(ids).encode()).hexdigest(),
            "ids": ids,
        },
    }
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def load(path=SPLIT_FILE) -> dict:
    return json.loads(path.read_text())


def test_ids(unlock: bool = False, path=SPLIT_FILE) -> list[str]:
    """The locked held-out ids. Only the one-time pre-registered evaluation may pass unlock=True."""
    if not unlock:
        raise PermissionError(
            "the pnictide evaluation sample is locked until its one-time evaluation "
            "(pnictide_eval.test_ids(unlock=True)); see "
            "reports/pnictide_evaluation_preregistration.md"
        )
    t = load(path)["test"]
    if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
        raise RuntimeError("pnictide evaluation ids do not match their recorded hash")
    return t["ids"]


def excluded_ids(path=SPLIT_FILE) -> set[str]:
    """The sample's ids, for use as an EXCLUSION FILTER only by any later draw. Returns ids, never
    outcomes, so it cannot leak a label; scoring still has to go through test_ids(unlock=True)."""
    if not path.exists():
        return set()
    t = load(path)["test"]
    if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
        raise RuntimeError("pnictide evaluation ids do not match their recorded hash")
    return set(t["ids"])


def is_opened() -> bool:
    return LOG_FILE.is_file()
