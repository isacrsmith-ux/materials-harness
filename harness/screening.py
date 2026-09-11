"""Model screening subset and the cross-model comparison (Phase 3).

Subset (data/screening_subset.json, fixed seed, made once): PAIRS_PER_BIN substitution pairs per target hull
bin from the round-2 pair set, plus N_WBM WBM CALIBRATION structures in the pool's bin proportions. Every
engine runs exactly these structures, so the comparison is paired. The locked test set is never touched.

Ranking (compare()): on the WBM screening structures, each engine's cost-optimal threshold (config/costs.json)
and its expected cost per screened candidate with a bootstrap interval, plus precision at that threshold with
its lower bound; energy error by hull bin with upper bounds for known (pairs) and new (WBM) materials.
Engines whose training data is not verified clean of WBM (registry 'compliant' != True) are ranked but
flagged: their WBM numbers may be optimistic.
"""

from __future__ import annotations

import json
import random

import numpy as np
import pandas as pd

from harness import compare, metrics as M, splits, store
from harness.config import DATA_DIR, MODELS, settings_tag

SUBSET_FILE = DATA_DIR / "screening_subset.json"
PAIRS_PER_BIN = 125
N_WBM = 500
SEED = 20260913


def make_subset(path=SUBSET_FILE) -> dict:
    from harness import pairgen

    if path.is_file():
        return json.loads(path.read_text())
    rng = random.Random(SEED)
    pairs = pairgen.load_pairs()
    chosen = []
    for b in compare.HULL_BINS_MP:
        ids = sorted(p["pair_id"] for p in pairs if compare.hull_bin(p["target_e_above_hull"]) == b)
        rng.shuffle(ids)
        chosen += ids[:PAIRS_PER_BIN]
    split = splits.load_split()
    cal = split["calibration"]["ids"]
    by_bin = split["calibration"]["by_bin"]
    from harness.suites import ood

    summ = ood.load_summary().set_index("material_id").loc[cal]
    wbm = []
    for b in compare.HULL_BINS_WBM:
        ids = sorted(w for w, e in summ[splits.HULL_COL].items() if compare.hull_bin(e, below_zero_bin=True) == b)
        rng.shuffle(ids)
        wbm += ids[: round(N_WBM * by_bin[b] / split["calibration"]["n"])]
    out = {"seed": SEED, "pairs_per_bin": PAIRS_PER_BIN, "pair_ids": chosen, "wbm_ids": sorted(wbm),
           "method": "pairs: per target hull bin, shuffled, first PAIRS_PER_BIN; WBM: calibration ids per bin in the "
                     "calibration set's proportions (random.Random(seed))"}
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out


# --- comparison ------------------------------------------------------------------------------------------

def _wbm_table(tag: str, ids: set) -> pd.DataFrame:
    from harness.suites import ood

    df = ood.table(tag)
    if df.empty:
        return df
    df = df[df.wbm_id.isin(ids)]
    return df


def _pair_table(tag: str, ids: set) -> pd.DataFrame:
    from harness import pairgen
    from harness.suites import substitution

    pairs = [p for p in pairgen.load_pairs() if p["pair_id"] in ids]
    return substitution.pair_table(tag, suite="substitution_auto", pairs=pairs)


def model_summary(key: str, device: str, dtype: str, subset: dict, costs: dict, n_boot: int = 2000) -> dict:
    tag = settings_tag(device, dtype, model=key)
    wb_all = _wbm_table(tag, set(subset["wbm_ids"]))
    au = _pair_table(tag, set(subset["pair_ids"]))
    out = {"model": MODELS[key]["name"], "key": key, "tag": tag, "setting": f"{device}/{dtype}",
           "compliant": MODELS[key]["compliant"], "license": MODELS[key]["license"]}
    if len(wb_all):
        wb = wb_all[wb_all.rejection.isna()]
        out.update({"wbm_done": len(wb_all), "wbm_rejected": int(wb_all.rejection.notna().sum())})
        sweep = M.threshold_sweep(wb.each_pred.values, wb.each_true.values, [round(x, 3) for x in np.arange(-0.2, 0.2001, 0.01)])
        opt = M.cost_optimal_threshold(sweep, costs["cost_false_positive"], costs["cost_missed_stable"])
        dm = M.decision_metrics(wb.each_pred.values, wb.each_true.values, opt["threshold"], n_boot)
        pred_stable = wb.each_pred.values <= opt["threshold"] + M.ON_HULL_TOL
        truly = wb.each_true.values <= M.ON_HULL_TOL
        per_item = (pred_stable & ~truly) * costs["cost_false_positive"] + (~pred_stable & truly) * costs["cost_missed_stable"]
        out.update({"threshold_mev": opt["threshold"] * 1000, "expected_cost": M.boot_ci(per_item, M.MEAN, n_boot),
                    "precision": dm["precision_ci"], "recall": dm["recall_ci"], "f1_at_0": M.decision_metrics(
                        wb.each_pred.values, wb.each_true.values, 0.0, 200)["f1"]})
        wb = wb.assign(bin=wb.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True)))
        for b in compare.HULL_BINS_WBM:
            out[f"new {b}"] = M.boot_ci(wb[wb.bin == b].de_mev, M.MAE, n_boot)
        out["new all"] = M.boot_ci(wb.de_mev, M.MAE, n_boot)
    if len(au):
        au = au.assign(bin=au.target_e_hull.astype(float).map(compare.hull_bin))
        same = au[au.ctrl_outcome == "same structure"]
        for b in compare.HULL_BINS_MP:
            out[f"known {b}"] = M.boot_ci(same[same.bin == b].ctrl_dE_mev.astype(float), M.MAE, n_boot)
        out["pairs_done"] = len(au)
        out["pairs_rejected"] = int(au.get("ctrl_rejection", pd.Series(dtype=object)).map(lambda x: isinstance(x, str)).sum())
    return out


def compare_models(models: list[tuple[str, str, str]], costs: dict | None = None) -> pd.DataFrame:
    """models: (registry key, device, dtype) of each engine's benchmarked setting."""
    from harness.report import _costs

    costs = costs or _costs()
    subset = make_subset()
    rows = [model_summary(k, d, t, subset, costs) for k, d, t in models]
    df = pd.DataFrame(rows)
    if "expected_cost" in df:
        df["_cost_upper"] = df.expected_cost.map(lambda c: c[2] if isinstance(c, tuple) else np.inf)
        df["_prec_lower"] = df.precision.map(lambda c: c[1] if isinstance(c, tuple) else -np.inf)
        df = df.sort_values(["_cost_upper", "_prec_lower"], ascending=[True, False]).drop(columns=["_cost_upper", "_prec_lower"])
    return df
