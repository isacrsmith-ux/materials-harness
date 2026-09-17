"""WBM calibration / locked-test split.

Made once, before any threshold tuning or calibration, and never regenerated (the file is refused
if it already exists). Pool: WBM's unique-prototype subset with every required column (the set Matbench
Discovery scores). Bins: energy above the MP hull, with a '<0' bin (compare.HULL_BINS_WBM).

Calibration = every id of the earlier 2,000-structure sample (all of it: those results were already used
to explore thresholds, so none may reach the test set) + new ids drawn per bin so the calibration set
has the pool's bin proportions. Test = a fresh draw from the rest of the pool, again in the pool's bin
proportions. Proportional allocation keeps the real base rate of stable materials in both sets, which
precision and the discovery acceleration factor depend on.

The test ids are only handed out by test_ids(unlock=True): relaxing or scoring them before the final
evaluation is a bug, not a shortcut.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from harness import compare
from harness.config import DATA_DIR

SPLIT_FILE = DATA_DIR / "wbm_split.json"
SEED = 20260911
N_CAL, N_TEST = 4000, 4000
HULL_COL = "e_above_hull_mp2020_corrected_ppd_mp"


class SplitExists(RuntimeError):
    pass


def _quotas(shares: pd.Series, n: int) -> dict[str, int]:
    """Largest-remainder rounding so the per-bin counts sum exactly to n."""
    raw = shares * n
    q = raw.astype(int)
    for b in (raw - q).sort_values(ascending=False).index[: n - int(q.sum())]:
        q[b] += 1
    return {b: int(v) for b, v in q.items()}


def make_split(summary: pd.DataFrame, prior_ids: list[str], n_cal: int = N_CAL, n_test: int = N_TEST,
               seed: int = SEED, path=SPLIT_FILE) -> dict:
    from harness.suites import ood

    if path.exists():
        raise SplitExists(f"{path} exists; the split is made once and never regenerated")
    pool = summary[(summary["unique_prototype"] == True) & summary[ood.REQUIRED].notna().all(axis=1)].copy()  # noqa: E712
    pool["bin"] = pool[HULL_COL].map(lambda e: compare.hull_bin(e, below_zero_bin=True))
    shares = pool["bin"].value_counts(normalize=True).reindex(compare.HULL_BINS_WBM).fillna(0)
    prior = pool[pool.material_id.isin(set(prior_ids))]
    rest = pool[~pool.material_id.isin(set(prior_ids))]
    cal_q, test_q = _quotas(shares, n_cal), _quotas(shares, n_test)
    cal_new, test = [], []
    for i, b in enumerate(compare.HULL_BINS_WBM):
        avail = rest[rest.bin == b]
        k_cal = max(0, cal_q[b] - int((prior.bin == b).sum()))
        new = avail.sample(n=min(k_cal, len(avail)), random_state=seed + i)
        cal_new.append(new)
        left = avail.drop(new.index)
        test.append(left.sample(n=min(test_q[b], len(left)), random_state=seed + 100 + i))
    cal = pd.concat([prior] + cal_new)
    test = pd.concat(test)
    assert not set(cal.material_id) & set(test.material_id)
    test_ids_sorted = sorted(test.material_id)
    out = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": seed,
        "pool": "WBM unique_prototype == True with every required column", "pool_size": len(pool),
        "bins": list(compare.HULL_BINS_WBM), "hull_column": HULL_COL,
        "pool_bin_shares": {b: float(shares[b]) for b in compare.HULL_BINS_WBM},
        "method": ("calibration = all ids of the earlier 2,000 sample (already used for threshold exploration) + new ids "
                   "per bin up to the pool's proportions; test = fresh per-bin draw from the remaining pool in the pool's "
                   "proportions; pandas.DataFrame.sample(random_state=seed + bin index)"),
        "calibration": {"n": len(cal), "n_prior_sample": len(prior), "by_bin": cal.bin.value_counts().to_dict(),
                        "ids": sorted(cal.material_id)},
        "test": {"n": len(test), "by_bin": test.bin.value_counts().to_dict(), "locked": True,
                 "sha256": hashlib.sha256(",".join(test_ids_sorted).encode()).hexdigest(), "ids": test_ids_sorted},
    }
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def load_split(path=SPLIT_FILE) -> dict:
    return json.loads(path.read_text())


def calibration_ids(path=SPLIT_FILE) -> list[str]:
    return load_split(path)["calibration"]["ids"]


def test_ids(unlock: bool = False, path=SPLIT_FILE) -> list[str]:
    """The locked test ids. Only the final, one-time evaluation may pass unlock=True."""
    if not unlock:
        raise PermissionError("the WBM test set is locked until the final evaluation (test_ids(unlock=True))")
    split = load_split(path)
    ids = split["test"]["ids"]
    if hashlib.sha256(",".join(ids).encode()).hexdigest() != split["test"]["sha256"]:
        raise RuntimeError("WBM test ids do not match their recorded hash")
    return ids


# --- per-family split: a NEW calibration task, disjoint from everything above ----------------------

FAMILY_SPLIT_FILE = DATA_DIR / "wbm_split_oxide_halide.json"
FAMILY_SEED = 20260917
FAMILY_SIZES = {"oxide": {"calibration": 4000, "test": 2000},
                "halide": {"calibration": 3500, "test": 2000}}


def excluded_ids(path=SPLIT_FILE) -> set[str]:
    """Every id already spent by the original split — calibration AND locked test — for use as an
    EXCLUSION FILTER only. It returns ids, never outcomes, so it cannot leak a label; the test half is
    still gated by test_ids(unlock=True) for anything that wants to read results. The test hash is
    verified here too, so a tampered split cannot quietly shrink the exclusion set."""
    split = load_split(path)
    ids = split["test"]["ids"]
    if hashlib.sha256(",".join(ids).encode()).hexdigest() != split["test"]["sha256"]:
        raise RuntimeError("WBM test ids do not match their recorded hash")
    return set(split["calibration"]["ids"]) | set(ids)


def make_family_split(summary: "pd.DataFrame", families=("oxide", "halide"), sizes=None, seed: int = FAMILY_SEED,
                      path=FAMILY_SPLIT_FILE, prior_path=SPLIT_FILE) -> dict:
    """Calibration + held-out test halves for chemistry families the original split could not certify.

    Drawn ONLY from the pool the original split never touched. Two leakage guards: every id from the
    original calibration and locked test set is excluded, and so is any candidate sharing a reduced
    formula with a locked-test id (WBM's unique_prototype dedups prototypes, not compositions). Each
    family is drawn in its OWN per-bin proportions, so its base rate is preserved and its thresholds are
    certified on its own chemistry — nothing is borrowed from another family. Made once, like the original.
    """
    from pymatgen.core import Composition

    from harness.confidence import family
    from harness.suites import ood

    if path.exists():
        raise SplitExists(f"{path} exists; the split is made once and never regenerated")
    sizes = sizes or FAMILY_SIZES
    pool = summary[(summary["unique_prototype"] == True) & summary[ood.REQUIRED].notna().all(axis=1)].copy()  # noqa: E712
    pool["bin"] = pool[HULL_COL].map(lambda e: compare.hull_bin(e, below_zero_bin=True))

    spent = excluded_ids(prior_path)
    locked_formulas = {Composition(f).reduced_formula for f in pool[pool.material_id.isin(spent)].formula}

    # family() can only return oxide/halide for a formula containing O or a halogen: prefilter, no false negatives.
    elems = pool.formula.str.findall(r"[A-Z][a-z]?")
    cand = pool[[bool({"O", "F", "Cl", "Br", "I"} & set(e)) for e in elems]].copy()
    cand = cand[~cand.material_id.isin(spent)]
    cand["family"] = [family(f) for f in cand.formula]
    cand = cand[cand.family.isin(families)].copy()
    cand["reduced_formula"] = [Composition(f).reduced_formula for f in cand.formula]
    n_before = len(cand)
    cand = cand[~cand.reduced_formula.isin(locked_formulas)]

    out = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": seed,
           "pool": "WBM unique_prototype == True with every required column",
           "pool_size": len(pool), "hull_column": HULL_COL, "bins": list(compare.HULL_BINS_WBM),
           "excluded_prior_ids": len(spent),
           "dropped_sharing_locked_test_formula": n_before - len(cand),
           "method": ("drawn only from ids the original split never used; per family, per-bin proportional to that "
                      "family's own share of the remaining pool; calibration drawn first, test from what is left; "
                      "pandas.DataFrame.sample(random_state=seed + bin index)"),
           "leakage_guards": ["every original calibration and locked-test id excluded by id",
                              "every candidate sharing a reduced formula with a locked-test id dropped",
                              "each family drawn and certified on its own chemistry only"],
           "families": {}}

    for fi, fam in enumerate(families):
        g = cand[cand.family == fam]
        shares = g["bin"].value_counts(normalize=True).reindex(compare.HULL_BINS_WBM).fillna(0)
        cal_q = _quotas(shares, sizes[fam]["calibration"])
        test_q = _quotas(shares, sizes[fam]["test"])
        cal, test = [], []
        for i, b in enumerate(compare.HULL_BINS_WBM):
            avail = g[g.bin == b]
            c = avail.sample(n=min(cal_q[b], len(avail)), random_state=seed + 1000 * fi + i)
            cal.append(c)
            left = avail.drop(c.index)
            test.append(left.sample(n=min(test_q[b], len(left)), random_state=seed + 1000 * fi + 500 + i))
        cal, test = pd.concat(cal), pd.concat(test)
        assert not set(cal.material_id) & set(test.material_id)
        assert not (set(cal.material_id) | set(test.material_id)) & spent
        t_ids = sorted(test.material_id)
        out["families"][fam] = {
            "available": len(g),
            "calibration": {"n": len(cal), "by_bin": cal.bin.value_counts().to_dict(),
                            "ids": sorted(cal.material_id)},
            "test": {"n": len(test), "by_bin": test.bin.value_counts().to_dict(), "locked": True,
                     "sha256": hashlib.sha256(",".join(t_ids).encode()).hexdigest(), "ids": t_ids},
        }
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def family_calibration_ids(fam: str, path=FAMILY_SPLIT_FILE) -> list[str]:
    return load_split(path)["families"][fam]["calibration"]["ids"]


def family_test_ids(fam: str, unlock: bool = False, path=FAMILY_SPLIT_FILE) -> list[str]:
    """Locked per-family test ids. Only the one-time evaluation of that family may pass unlock=True."""
    if not unlock:
        raise PermissionError(f"the {fam} test set is locked (family_test_ids('{fam}', unlock=True))")
    t = load_split(path)["families"][fam]["test"]
    if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
        raise RuntimeError(f"{fam} test ids do not match their recorded hash")
    return t["ids"]
