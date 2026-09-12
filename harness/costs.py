"""Cost-driven operating point, recomputed from cached results in seconds (no relaxations).

Which decision threshold is best depends entirely on two numbers only the product owner can supply: what a
wasted lab test costs, and what missing a stable material costs. `config/costs.json` currently holds
placeholders (1:1). This module recomputes the whole operating point for any cost pair straight from the
cached calibration results, so those numbers can be revised and re-answered in seconds.

Two things it adds beyond the sweep already in the report:

* **The plateau.** The threshold that minimises expected cost is often one of many that cost nearly the
  same. Knowing the flat region matters more than the argmin: if the cost curve is flat from -40 to +20
  meV/atom, the cost estimate does not have to be good, and arguing about it is wasted effort.
* **The implied precision floor.** Minimising expected cost means calling a candidate stable when its
  probability of being stable exceeds cost_fp / (cost_fp + cost_fn). Read backwards, any precision target
  *is* a claim about costs. The 90 % target used by the routing layer implies a wasted lab test is nine
  times worse than missing a stable material -- an assumption worth stating out loud rather than inheriting.

Calibration set only. The locked test set was opened once and is never re-optimised against.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from harness import metrics as M
from harness import splits
from harness.config import BASELINE_MODEL, MODELS, REPORTS_DIR, ROOT, settings_tag

SWEEP = tuple(round(x, 3) for x in np.arange(-0.30, 0.3001, 0.005))
PLATEAU_FRAC = 0.02  # thresholds within 2 % of the minimum expected cost count as "as good as optimal"
PRIMARY = ("mace-mpa-0-medium", "cpu", "float32")


def calibration(model: str = PRIMARY[0], device: str = PRIMARY[1], dtype: str = PRIMARY[2]) -> pd.DataFrame:
    """Usable WBM calibration rows for one engine (guard-rejected rows dropped, as everywhere else)."""
    from harness.suites import ood

    df = ood.table(settings_tag(device, dtype, model=model))
    df = df[df.wbm_id.isin(set(splits.calibration_ids()))]
    return df[df.rejection.isna()].copy()


def sweep(df: pd.DataFrame, thresholds=SWEEP) -> pd.DataFrame:
    return M.threshold_sweep(df.each_pred.values, df.each_true.values, thresholds)


def implied_precision_floor(cost_fp: float, cost_fn: float) -> float:
    """Cost-optimal rule: call stable when P(stable) > cost_fp / (cost_fp + cost_fn)."""
    return cost_fp / (cost_fp + cost_fn)


def implied_cost_ratio(precision_target: float) -> float:
    """The inverse: a precision target of p implies missed_stable / wasted_test = (1 - p) / p."""
    return (1.0 - precision_target) / precision_target


def plateau(sw: pd.DataFrame, cost_fp: float, cost_fn: float, frac: float = PLATEAU_FRAC) -> dict:
    """Range of thresholds whose expected cost is within `frac` of the minimum."""
    c = M.expected_cost(sw, cost_fp, cost_fn)
    lo = float(c.expected_cost.min())
    near = c[c.expected_cost <= lo * (1.0 + frac)]
    return {"best": float(c.loc[c.expected_cost.idxmin()].threshold), "min_cost": lo,
            "low": float(near.threshold.min()), "high": float(near.threshold.max()), "frac": frac,
            "n_thresholds": int(len(near))}


def ratio_table(sw: pd.DataFrame, ratios) -> pd.DataFrame:
    """How the optimum moves as missed-material cost rises relative to a wasted lab test."""
    rows = []
    for r in ratios:
        o = M.cost_optimal_threshold(sw, 1.0, float(r))
        p = plateau(sw, 1.0, float(r))
        rows.append({"missed ÷ wasted test": r, "optimal threshold (meV/atom)": o["threshold"] * 1000,
                     "as-good-as-optimal range (meV/atom)": f"{p['low'] * 1000:+.0f} … {p['high'] * 1000:+.0f}",
                     "precision": o["precision"], "recall": o["recall"],
                     "implied precision floor": implied_precision_floor(1.0, float(r)),
                     "expected cost per candidate": o["expected_cost"]})
    return pd.DataFrame(rows)


def operating_point(df: pd.DataFrame, cost_fp: float, cost_fn: float, n_boot: int = M.N_BOOT) -> dict:
    sw = sweep(df)
    opt = M.cost_optimal_threshold(sw, cost_fp, cost_fn)
    dm = M.decision_metrics(df.each_pred.values, df.each_true.values, opt["threshold"], n_boot)
    return {"optimum": opt, "metrics": dm, "plateau": plateau(sw, cost_fp, cost_fn),
            "floor": implied_precision_floor(cost_fp, cost_fn), "sweep": sw}


DEFAULT_RATIOS = (0.1, 0.25, 0.5, 1, 2, 4, 10, 25, 100)


def report(cost_fp: float, cost_fn: float, model: str = PRIMARY[0], device: str = PRIMARY[1],
           dtype: str = PRIMARY[2], ratios=DEFAULT_RATIOS, out=None) -> str:
    """Markdown answering 'given these costs, where do we set the threshold?'."""
    from harness.confidence import TARGET_PRECISION

    df = calibration(model, device, dtype)
    op = operating_point(df, cost_fp, cost_fn)
    opt, dm, pl = op["optimum"], op["metrics"], op["plateau"]
    name = MODELS[model]["name"]
    ratio = cost_fn / cost_fp if cost_fp else float("inf")
    L = [f"# Cost-based operating point — {name}", "",
         f"Costs supplied: a wasted lab test = **{cost_fp:g}**, a missed stable material = **{cost_fn:g}** "
         f"(ratio {ratio:g}:1). Computed on the {len(df):,} usable WBM **calibration** structures; the locked "
         "test set is not re-optimised against.", "",
         "## Answer", "",
         f"* **Threshold: {opt['threshold'] * 1000:+.0f} meV/atom.**",
         f"* Anything from **{pl['low'] * 1000:+.0f} to {pl['high'] * 1000:+.0f} meV/atom** costs within "
         f"{pl['frac']:.0%} of the optimum — inside that range the exact cost numbers do not change the answer.",
         f"* At that threshold: precision {M.fmt_ci(dm['precision_ci'], '{:.2f}')}, recall "
         f"{M.fmt_ci(dm['recall_ci'], '{:.2f}')}, NPV {M.fmt_ci(dm['npv_ci'], '{:.3f}')}, DAF "
         f"{M.fmt_ci(dm['daf_ci'], '{:.2f}')}.",
         f"* {dm['called_stable']:,} of {dm['n']:,} candidates called stable; {dm['fp']:,} of those are wrong "
         f"and {dm['fn']:,} stable materials are missed.",
         f"* Expected cost {opt['expected_cost']:.4f} per candidate screened.", "",
         "## What your costs imply about precision", "",
         f"Minimising expected cost means calling a candidate stable when its probability of being stable "
         f"exceeds `cost_fp / (cost_fp + cost_fn)` = **{op['floor']:.2f}**. Read the other way: the routing "
         f"layer's {TARGET_PRECISION:.0%} precision target is itself a cost claim — it assumes a wasted lab "
         f"test is {1 / implied_cost_ratio(TARGET_PRECISION):.0f}× worse than missing a stable material. If "
         "that is not your view, the target should move, not just the threshold.", "",
         "## Sensitivity", "",
         "How the optimum moves as a missed material gets more expensive relative to a wasted test:", "",
         ratio_table(op["sweep"], ratios).to_markdown(index=False, floatfmt=".3f"), "",
         "## Method", "",
         "Expected cost per screened candidate = (false positives × wasted-test cost + false negatives × "
         f"missed-material cost) ÷ N, minimised over thresholds from {SWEEP[0] * 1000:+.0f} to "
         f"{SWEEP[-1] * 1000:+.0f} meV/atom in {(SWEEP[1] - SWEEP[0]) * 1000:.0f} meV/atom steps. Intervals are "
         "95 % bootstrap. Re-run with `python -m harness costs --fp <n> --fn <n>`.", ""]
    path = out or (REPORTS_DIR / "costs.md")
    path.write_text("\n".join(L) + "\n")
    return str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path)
