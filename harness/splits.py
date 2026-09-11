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
