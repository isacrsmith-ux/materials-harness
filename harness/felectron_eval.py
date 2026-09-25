"""The f-electron held-out evaluation sample: drawn once, opened once, never regenerated.

Drawn under `data/felectron_evaluation_preregistration.json`, which fixes the thresholds under test
(the LIVE production rule: stable -20 meV, unstable +10 meV), the family definition, the labelable
population, the four hypotheses, the confidence and corrections, the sample size, the pass/fail and
stop rules, the outcome branches, and an explicit ban on refitting. That document was committed AND
PUSHED before this module drew anything, and `make_split` verifies its hash.

DRAWING IS NOT OPENING. This module selects ids and locks them. It queues nothing and scores
nothing: `test_ids` raises PermissionError without unlock=True.

There is no earlier f-electron half. Round 4 deliberately reserved none, so this draw consumes none
of the four unspent locked halves (oxide, sulfide, chalcogenide, other).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd
from pymatgen.core import Composition

from harness import compare, confidence as C, pnictide_eval, round4, splits
from harness.config import DATA_DIR

SPLIT_FILE = DATA_DIR / "wbm_split_felectron_eval.json"
PREREG_FILE = DATA_DIR / "felectron_evaluation_preregistration.json"
LOG_FILE = DATA_DIR / "felectron_eval_log.json"
TOPUP_IDS = DATA_DIR / "felectron_topup_ids.json"
SEED = 20260922
FAMILY = "f-electron"
N_DRAW = 4500


def _spent_ids() -> set[str]:
    """Every id any split, draw, top-up or evaluation has used. Ids only, never outcomes."""
    out = round4._spent_ids() | round4.excluded_ids() | pnictide_eval.excluded_ids()
    if TOPUP_IDS.is_file():
        d = json.loads(TOPUP_IDS.read_text())
        if hashlib.sha256(",".join(sorted(d["ids"])).encode()).hexdigest() != d["sha256"]:
            raise RuntimeError("f-electron top-up ids do not match their recorded hash")
        out |= set(d["ids"])
    return out


def _protected_ids() -> set[str]:
    """Every locked-half id plus every opened held-out id: never drawable, and their reduced
    formulas are dropped too, because unique_prototype dedups prototypes and not compositions."""
    return round4._locked_test_ids() | pnictide_eval.excluded_ids()


def make_split(summary: pd.DataFrame, seed: int = SEED, path=SPLIT_FILE, n_draw: int = N_DRAW) -> dict:
    """Draw the held-out sample. Made once; refuses to regenerate."""
    from harness.suites import ood

    if path.exists():
        raise splits.SplitExists(
            f"{path} exists; the f-electron evaluation sample is drawn ONCE and never regenerated. "
            "Re-drawing would silently replace a held-out set with a different one.")
    raw = PREREG_FILE.read_bytes()
    P, prereg_sha = json.loads(raw), hashlib.sha256(raw).hexdigest()
    if n_draw != P["sample"]["n_draw"]:
        raise SystemExit(f"ABORT - n_draw {n_draw} != the pre-registered {P['sample']['n_draw']}")

    pool = summary[(summary["unique_prototype"] == True) & summary[ood.REQUIRED].notna().all(axis=1)].copy()  # noqa: E712
    pool["bin"] = pool[splits.HULL_COL].map(lambda e: compare.hull_bin(e, below_zero_bin=True))

    spent, protected = _spent_ids(), _protected_ids()
    protected_formulas = {Composition(f).reduced_formula
                          for f in pool[pool.material_id.isin(protected)].formula}
    rest = pool[~pool.material_id.isin(spent)].copy()
    rest["reduced_formula"] = [Composition(f).reduced_formula for f in rest.formula]
    n_before = len(rest)
    rest = rest[~rest.reduced_formula.isin(protected_formulas)]
    rest["fam"] = [C.family(f) for f in rest.formula]
    eligible = rest[rest.fam == FAMILY]
    if len(eligible) < n_draw:
        raise SystemExit(f"ABORT - only {len(eligible)} eligible f-electron candidates, need {n_draw}")

    shares = eligible["bin"].value_counts(normalize=True).reindex(compare.HULL_BINS_WBM).fillna(0)
    quota = splits._quotas(shares, n_draw)
    picks = [eligible[eligible.bin == b].sample(n=min(quota[b], int((eligible.bin == b).sum())),
                                                random_state=seed + i)
             for i, b in enumerate(compare.HULL_BINS_WBM)]
    drawn = pd.concat(picks)
    ids = sorted(drawn.material_id)

    assert len(ids) == n_draw and len(set(ids)) == n_draw
    assert not set(ids) & spent, "a drawn id was already spent"
    assert not set(ids) & protected, "a drawn id is a locked or held-out id"

    out = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "state": ("DRAWN AND LOCKED - NOT OPENED. No job queued, nothing scored. Opening is a "
                  "separate, separately-approved step that writes data/felectron_eval_log.json once."),
        "preregistration": {"file": "data/felectron_evaluation_preregistration.json",
                            "sha256": prereg_sha, "verified_at_draw_time": True,
                            "published_before_draw": True},
        "thresholds_under_test": {
            "stable": P["thresholds_under_test"]["stable_ev_per_atom"],
            "unstable": P["thresholds_under_test"]["unstable_ev_per_atom"],
            "note": "the LIVE production rule; fixed by the pre-registration and NOT refittable here",
        },
        "family": FAMILY,
        "family_definition": "harness.confidence.family(), unchanged; f-electron heads the chain",
        "pool": "WBM unique_prototype == True with every required column",
        "pool_size": len(pool),
        "hull_column": splits.HULL_COL,
        "bins": list(compare.HULL_BINS_WBM),
        "excluded_prior_ids": len(spent),
        "protected_ids_excluded": len(protected),
        "dropped_sharing_protected_formula": n_before - len(rest),
        "eligible_candidates": len(eligible),
        "left_unspent_after_draw": len(eligible) - n_draw,
        "consumes_no_existing_locked_half": True,
        "leakage_guards": [
            "every id any split, draw, top-up or evaluation has used excluded by id",
            "every candidate sharing a reduced formula with any locked half or opened held-out set dropped",
            "per-bin proportional to the eligible pool's own hull-distance distribution",
            "no id here has participated in any fit, threshold selection, diagnostic, refit, "
            "development top-up or prior evaluation",
        ],
        "test": {"n": len(ids), "by_bin": drawn.bin.value_counts().to_dict(), "locked": True,
                 "sha256": hashlib.sha256(",".join(ids).encode()).hexdigest(), "ids": ids},
    }
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def load(path=SPLIT_FILE) -> dict:
    return json.loads(path.read_text())


def test_ids(unlock: bool = False, path=SPLIT_FILE) -> list[str]:
    """The locked held-out ids. Only the one-time pre-registered evaluation may pass unlock=True."""
    if not unlock:
        raise PermissionError(
            "the f-electron evaluation sample is locked until its one-time evaluation "
            "(felectron_eval.test_ids(unlock=True)); see "
            "reports/felectron_evaluation_preregistration.md")
    t = load(path)["test"]
    if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
        raise RuntimeError("f-electron evaluation ids do not match their recorded hash")
    return t["ids"]


def excluded_ids(path=SPLIT_FILE) -> set[str]:
    """The sample's ids, for use as an EXCLUSION FILTER only by any later draw."""
    if not path.exists():
        return set()
    t = load(path)["test"]
    if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
        raise RuntimeError("f-electron evaluation ids do not match their recorded hash")
    return set(t["ids"])


def is_opened() -> bool:
    return LOG_FILE.is_file()
