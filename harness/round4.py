"""Round 4: re-measure the three families the product carried over untouched.

`f-electron`, `intermetallic` and `pnictide` still carry the 2026-09-12 thresholds, fitted on
1,747 / 645 / 202 labelable rows of the original 4,000-id calibration set. Rounds 2 and 3 never
touched them. In the active bundle's `with_second_engine` rule set that leaves `intermetallic` with
an unstable-only rule and `pnictide` with no rule at all, so production sends every pnictide to DFT.

The unspent pool is not the constraint here that it was for halide. After excluding every id any
earlier split has spent and dropping every candidate that shares a reduced formula with any locked
test id, the pool still holds ~105,000 f-electron, ~37,700 intermetallic and ~9,400 pnictide
candidates. Round 2's experience — check availability before planning a draw — is satisfied.

DEVELOPMENT ONLY, and deliberately so:

  * **calibration draws only. No held-out half is reserved.** Reserving one is a separate decision
    that belongs with a pre-registration, and this module must not pre-empt it. Everything the draw
    does not take stays eligible, and the split file records how much that is per family.
  * nothing here refits, promotes or overwrites the frozen bundle, `confidence.family()`, the frozen
    spec v2 or any threshold in production;
  * no locked half is opened, inspected or scored. Every locked id is excluded by id before any job
    is built, and the exclusion goes through the accessors that verify each half's hash.

TAXONOMY. This uses `confidence.family()` unchanged — no round-2 / round-3 style overlay. That is
the point: the question is whether *production's own* f-electron / intermetallic / pnictide
populations can be certified on thousands of rows instead of hundreds, so the population measured has
to be exactly the one production routes. `pnictide` here therefore means what it means in production:
non-f-electron, non-intermetallic, non-oxide, non-halide, non-chalcogenide pnictides.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd
from pymatgen.core import Composition

from harness import compare, round2, splits
from harness.config import DATA_DIR

SPLIT_FILE = DATA_DIR / "wbm_split_round4.json"
SEED = 20260920
CARRIED_OVER = ("f-electron", "intermetallic", "pnictide")
CAL_N = 4000            # the same size round 2 and round 3 used, so results are comparable
MIN_FAMILY = 100        # confidence.certify's own floor; a draw below it could not certify anything


def _spent_ids() -> set[str]:
    """Every id any earlier split has spent — original, round-1 family, round-2, round-3 —
    calibration and locked test alike. Ids only, never outcomes, so nothing here can leak a label.
    Every test half's hash is verified on the way through the accessors."""
    out = round2._spent_ids_round3()
    for g in round2.load3()["groups"].values():
        out |= set(g["calibration"]["ids"])
        if g.get("test"):
            out |= set(g["test"]["ids"])
    return out


def _locked_test_ids() -> set[str]:
    """Every LOCKED TEST id, all six halves, for use as an exclusion filter only.

    Each accessor verifies its own recorded hash, so a tampered split cannot quietly shrink this set.
    `unlock=True` is never passed: these are ids, never outcomes."""
    out = splits.excluded_ids() - set(splits.calibration_ids())      # original WBM test half
    out |= splits.family_excluded_ids()                              # round-1 oxide + halide halves
    for g in round2.groups():                                        # round-2 (sulfide)
        t = round2.load()["groups"][g].get("test")
        if t:
            if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
                raise RuntimeError(f"round-2 {g} test ids do not match their recorded hash")
            out |= set(t["ids"])
    for g in round2.groups3():                                       # round-3 (chalcogenide, other)
        t = round2.load3()["groups"][g].get("test")
        if t:
            if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
                raise RuntimeError(f"round-3 {g} test ids do not match their recorded hash")
            out |= set(t["ids"])
    return out


def make_split(summary: pd.DataFrame, seed: int = SEED, path=SPLIT_FILE, n_cal: int = CAL_N) -> dict:
    """Calibration draws for the three carried-over families, on the same terms as every earlier
    split: only ids no split has used, every candidate sharing a reduced formula with ANY locked test
    id dropped, per-bin proportional so the family's own base rate is preserved, families drawn
    sequentially against a shared taken-set. Made once.

    No test half is reserved. See the module docstring.
    """
    from harness.confidence import family
    from harness.suites import ood

    if path.exists():
        raise splits.SplitExists(f"{path} exists; the round-4 split is made once and never regenerated")
    pool = summary[(summary["unique_prototype"] == True) & summary[ood.REQUIRED].notna().all(axis=1)].copy()  # noqa: E712
    pool["bin"] = pool[splits.HULL_COL].map(lambda e: compare.hull_bin(e, below_zero_bin=True))

    spent = _spent_ids()
    locked = _locked_test_ids()
    locked_formulas = {Composition(f).reduced_formula for f in pool[pool.material_id.isin(locked)].formula}

    rest = pool[~pool.material_id.isin(spent)].copy()
    rest["reduced_formula"] = [Composition(f).reduced_formula for f in rest.formula]
    n_before = len(rest)
    rest = rest[~rest.reduced_formula.isin(locked_formulas)]
    rest["fam"] = [family(f) for f in rest.formula]

    out = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": seed,
           "pool": "WBM unique_prototype == True with every required column", "pool_size": len(pool),
           "hull_column": splits.HULL_COL, "bins": list(compare.HULL_BINS_WBM),
           "excluded_prior_ids": len(spent),
           "locked_test_ids_excluded": len(locked),
           "dropped_sharing_locked_test_formula": n_before - len(rest),
           "taxonomy": ("harness.confidence.family() UNCHANGED — no round-2/3 overlay. The population "
                        "measured is exactly the population production routes."),
           "purpose": ("re-measure f-electron, intermetallic and pnictide, which still carry "
                       "thresholds fitted on 1,747 / 645 / 202 labelable rows from 2026-09-12 and "
                       "were not touched by round 2 or round 3"),
           "held_out_half": ("NONE RESERVED. This is a development-only draw. Reserving a locked half "
                             "is a separate decision that belongs with a pre-registration; "
                             "unspent_after_draw below records what remains eligible for one."),
           "method": ("only ids no earlier split has used; every candidate sharing a reduced formula "
                      "with ANY of the six locked test halves dropped; per-bin proportional to the "
                      "family's own share; families drawn sequentially against a shared taken-set"),
           "leakage_guards": ["every original, round-1, round-2 and round-3 calibration and locked-test "
                              "id excluded by id, each half's hash verified on the way",
                              "every candidate sharing a reduced formula with any locked-test id dropped",
                              "families drawn sequentially, so no id lands in two draws",
                              "no test half is reserved, so no id drawn here can later be mistaken "
                              "for held-out data"],
           "groups": {}}

    taken: set[str] = set()
    for gi, fam in enumerate(CARRIED_OVER):
        g = rest[(rest.fam == fam) & ~rest.material_id.isin(taken)]
        shares = g["bin"].value_counts(normalize=True).reindex(compare.HULL_BINS_WBM).fillna(0)
        quota = splits._quotas(shares, min(n_cal, len(g)))
        picks = []
        for i, b in enumerate(compare.HULL_BINS_WBM):
            avail = g[g.bin == b]
            picks.append(avail.sample(n=min(quota[b], len(avail)), random_state=seed + 1000 * gi + i))
        cal = pd.concat(picks)
        taken |= set(cal.material_id)
        ids = sorted(cal.material_id)
        assert not set(ids) & spent, f"{fam}: a round-4 id was already spent"
        assert not set(ids) & locked, f"{fam}: a round-4 id is a locked test id"
        out["groups"][fam] = {
            "family": fam, "available": len(g),
            "calibration": {"n": len(ids), "by_bin": cal.bin.value_counts().to_dict(),
                            "sha256": hashlib.sha256(",".join(ids).encode()).hexdigest(),
                            "ids": ids},
            "test": None,
            "unspent_after_draw": len(g) - len(ids),
            "carried_over_threshold_n": {"f-electron": 1747, "intermetallic": 645, "pnictide": 202}[fam],
        }

    all_ids = {i for g in out["groups"].values() for i in g["calibration"]["ids"]}
    assert len(all_ids) == sum(g["calibration"]["n"] for g in out["groups"].values()), "an id is in two draws"
    assert not all_ids & spent and not all_ids & locked
    out["n_unique_calibration_ids"] = len(all_ids)
    out["sha256_all_calibration_ids"] = hashlib.sha256(",".join(sorted(all_ids)).encode()).hexdigest()
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def load(path=SPLIT_FILE) -> dict:
    return json.loads(path.read_text())


def calibration_ids(fam: str, path=SPLIT_FILE) -> list[str]:
    g = load(path)["groups"][fam]["calibration"]
    if hashlib.sha256(",".join(g["ids"]).encode()).hexdigest() != g["sha256"]:
        raise RuntimeError(f"round-4 {fam} calibration ids do not match their recorded hash")
    return g["ids"]


def groups(path=SPLIT_FILE) -> list[str]:
    return list(load(path)["groups"])


def test_ids(fam: str, unlock: bool = False, path=SPLIT_FILE) -> list[str]:
    """There is no round-4 held-out half. This exists so that anything reaching for one is told why
    rather than getting a KeyError."""
    raise PermissionError(
        f"round 4 reserved no held-out half for {fam!r}: it is a development-only draw. "
        "A future locked evaluation needs a fresh draw from the unspent pool and its own "
        "pre-registration; see 'held_out_half' in data/wbm_split_round4.json."
    )


def excluded_ids(path=SPLIT_FILE) -> set[str]:
    """Every id round 4 has spent, for use as an exclusion filter by any later draw."""
    return {i for g in load(path)["groups"].values() for i in g["calibration"]["ids"]}
