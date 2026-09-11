"""Stratified, uncertainty-aware metrics for the report.

Every statistic comes with a 95 % bootstrap interval (fixed seed), and verdicts use the pessimistic end of
the interval: the upper bound for errors, the lower bound for scores such as precision. Stability calls:
"stable" is the positive class; a material is called stable when its predicted energy above hull is at or
below the decision threshold, and is truly stable when its reference energy above hull is at or below 0
(Matbench Discovery's definition).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pymatgen.core import Composition

N_BOOT = 2000
SEED = 0
ON_HULL_TOL = 1e-6  # eV/atom


def _finite(x) -> np.ndarray:
    a = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    return a


def boot_ci(x, stat=lambda v: float(np.mean(np.abs(v))), n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    """(point, 2.5 %, 97.5 %) of stat over x (non-finite values ignored)."""
    a = _finite(x)
    if not len(a):
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), (n_boot, len(a)))
    bs = np.array([stat(a[i]) for i in idx])
    return float(stat(a)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


MAE = lambda v: float(np.mean(np.abs(v)))  # noqa: E731
MEDIAN_ABS = lambda v: float(np.median(np.abs(v)))  # noqa: E731
MEAN = lambda v: float(np.mean(v))  # noqa: E731
RMSE = lambda v: float(np.sqrt(np.mean(np.square(v))))  # noqa: E731


def error_summary(err, n_boot: int = N_BOOT) -> dict:
    """n, MAE, median |error|, mean signed error and RMSE, each with a bootstrap interval."""
    a = _finite(err)
    out = {"n": len(a)}
    for name, f in (("mae", MAE), ("median_abs", MEDIAN_ABS), ("mean_signed", MEAN), ("rmse", RMSE)):
        out[name] = boot_ci(a, f, n_boot)
    return out


def by_group(df: pd.DataFrame, group_col: str, err_col: str, order=None, n_boot: int = N_BOOT, extra=None) -> pd.DataFrame:
    """One row per group: n, MAE [CI], median |error| [CI], mean signed [CI]. `extra(g)` adds columns."""
    rows = []
    groups = order if order is not None else sorted(df[group_col].dropna().unique())
    for g in groups:
        sub = df[df[group_col] == g]
        s = error_summary(sub[err_col], n_boot)
        row = {group_col: g, "n": s["n"], "MAE": s["mae"], "median |err|": s["median_abs"], "mean signed": s["mean_signed"]}
        if extra is not None:
            row.update(extra(sub))
        rows.append(row)
    return pd.DataFrame(rows)


def fmt_ci(t, spec="{:.1f}") -> str:
    if t is None or not isinstance(t, tuple) or not np.isfinite(t[0]):
        return "n/a"
    return f"{spec.format(t[0])} [{spec.format(t[1])}, {spec.format(t[2])}]"


# --- stability decisions -------------------------------------------------------------------------------

def confusion(pred_stable, true_stable) -> dict:
    p, t = np.asarray(pred_stable, bool), np.asarray(true_stable, bool)
    tp, fp = int(np.sum(p & t)), int(np.sum(p & ~t))
    fn, tn = int(np.sum(~p & t)), int(np.sum(~p & ~t))
    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    npv = tn / (tn + fn) if tn + fn else float("nan")
    prev = (tp + fn) / n if n else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if tp else (0.0 if tp + fp + fn else float("nan"))
    return {"n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec, "f1": f1, "npv": npv,
            "accuracy": (tp + tn) / n if n else float("nan"), "prevalence": prev,
            "daf": prec / prev if prev and np.isfinite(prec) else float("nan"),
            "called_stable": tp + fp}


DECISION_METRICS = ("precision", "recall", "f1", "npv", "accuracy", "daf")


def decision_metrics(pred_e_hull, true_e_hull, threshold: float = 0.0, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Confusion-matrix metrics at a decision threshold, each with a bootstrap interval (rows resampled)."""
    pe, te = np.asarray(pred_e_hull, float), np.asarray(true_e_hull, float)
    ok = np.isfinite(pe) & np.isfinite(te)
    pe, te = pe[ok], te[ok]
    pred, true = pe <= threshold + ON_HULL_TOL, te <= ON_HULL_TOL
    point = confusion(pred, true)
    rng = np.random.default_rng(seed)
    samples = {m: [] for m in DECISION_METRICS}
    for _ in range(n_boot):
        i = rng.integers(0, len(pe), len(pe))
        c = confusion(pred[i], true[i])
        for m in DECISION_METRICS:
            samples[m].append(c[m])
    out = dict(point)
    for m in DECISION_METRICS:
        s = np.asarray(samples[m], float)
        s = s[np.isfinite(s)]
        out[f"{m}_ci"] = (point[m], float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))) if len(s) else (point[m],) + (float("nan"),) * 2
    out["threshold"] = threshold
    return out


def threshold_sweep(pred_e_hull, true_e_hull, thresholds) -> pd.DataFrame:
    """Point metrics at every threshold (for the precision-recall curve and the cost analysis)."""
    pe, te = np.asarray(pred_e_hull, float), np.asarray(true_e_hull, float)
    ok = np.isfinite(pe) & np.isfinite(te)
    pe, te = pe[ok], te[ok]
    rows = []
    for thr in thresholds:
        c = confusion(pe <= thr + ON_HULL_TOL, te <= ON_HULL_TOL)
        rows.append({"threshold": float(thr), **c})
    return pd.DataFrame(rows)


def expected_cost(sweep: pd.DataFrame, cost_fp: float, cost_fn: float) -> pd.DataFrame:
    """Expected cost per screened candidate at every threshold: (FP * cost of a wasted lab test +
    FN * cost of a missed stable material) / N."""
    out = sweep.copy()
    out["expected_cost"] = (out.fp * cost_fp + out.fn * cost_fn) / out.n
    return out


def cost_optimal_threshold(sweep: pd.DataFrame, cost_fp: float, cost_fn: float) -> dict:
    c = expected_cost(sweep, cost_fp, cost_fn)
    best = c.loc[c.expected_cost.idxmin()]
    return {"threshold": float(best.threshold), "expected_cost": float(best.expected_cost),
            "precision": float(best.precision), "recall": float(best.recall), "cost_fp": cost_fp, "cost_fn": cost_fn}


# --- verdicts from the pessimistic bound ----------------------------------------------------------------

def pessimistic(ci: tuple, lower_is_better: bool) -> float:
    """The bound a verdict uses: upper bound of an error, lower bound of a score."""
    return ci[2] if lower_is_better else ci[1]


def verdict(value: float, good: float, caution: float, lower_is_better: bool) -> str:
    if value is None or not np.isfinite(value):
        return "no data"
    if lower_is_better:
        return "trustworthy" if value <= good else "use with caution" if value <= caution else "not trustworthy"
    return "trustworthy" if value >= good else "use with caution" if value >= caution else "not trustworthy"


def verdict_ci(ci: tuple, good: float, caution: float, lower_is_better: bool) -> str:
    """Verdict from the pessimistic end of the 95 % interval."""
    if ci is None or not np.isfinite(ci[0]):
        return "no data"
    return verdict(pessimistic(ci, lower_is_better), good, caution, lower_is_better)


# --- per element ------------------------------------------------------------------------------------------

def per_element(df: pd.DataFrame, formula_col: str, err_col: str, min_count: int = 20, n_boot: int = N_BOOT) -> tuple[pd.DataFrame, int]:
    """Error attributed to every element of each compound: n, MAE [CI], mean signed [CI], only for elements
    in >= min_count compounds. Returns (table, number of elements below the minimum count)."""
    rows = []
    for f, e in zip(df[formula_col], df[err_col]):
        if e is None or not isinstance(f, str) or not np.isfinite(e):
            continue
        for el in Composition(f).elements:
            rows.append((el.symbol, float(e)))
    if not rows:
        return pd.DataFrame(columns=["element", "n", "MAE", "mean signed"]), 0
    d = pd.DataFrame(rows, columns=["element", "err"])
    out, below = [], 0
    for el, g in d.groupby("element"):
        if len(g) < min_count:
            below += 1
            continue
        out.append({"element": el, "n": len(g), "MAE": boot_ci(g.err, MAE, n_boot), "mean signed": boot_ci(g.err, MEAN, n_boot)})
    t = pd.DataFrame(out)
    if len(t):
        t = t.assign(_upper=t.MAE.map(lambda c: c[2])).sort_values("_upper", ascending=False).drop(columns="_upper")
    return t, below
