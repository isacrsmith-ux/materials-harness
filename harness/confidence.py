"""Empirical confidence for stability calls, fitted on the WBM CALIBRATION set only.

Method: Mondrian (group-conditional) split-conformal prediction on the residual
    r = predicted hull distance − true hull distance   (eV/atom)
with groups = chemistry family × predicted hull bin. For a new candidate in group g with prediction p,
    true hull distance ≤ p − q_lo(g)   with probability ≥ 1 − α   (upper bound: used for a 'stable' call)
    true hull distance ≥ p − q_hi(g)   with probability ≥ 1 − α   (lower bound: used for an 'unstable' call)
(one-sided finite-sample conformal bounds, distribution-free, marginal over the group; together they form
a ≥ 1 − 2α interval). Groups with fewer than MIN_GROUP calibration members fall back to the family, then
to the whole calibration set; the fallback used is recorded with every interval.

Why conformal and not isotonic calibration:
  * the product needs a guarantee in the pessimistic direction ("this candidate is stable with at least
    90 % confidence"), and split conformal gives exactly that per group without assuming anything about the
    error distribution — important here, because the model's error is biased (over-stabilises
    high-energy structures) and heavy-tailed;
  * isotonic regression of P(stable | prediction) needs a monotone relation and enough data per group to
    fit a step function, and provides no coverage guarantee; with ~4,000 calibration structures split into
    ~30 groups it would be noisy exactly where it matters (the few stable candidates per group);
  * the "right X % of the time" statement users see is reported alongside as an observed frequency per group
    (empirical_reliability), with a bootstrap interval, so nothing is hidden behind the interval arithmetic.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from pymatgen.core import Composition

from harness import compare
from harness import metrics as M

ALPHA = 0.10
MIN_GROUP = 40
FAMILIES = ("f-electron", "intermetallic", "oxide", "halide", "chalcogenide", "pnictide", "other")
HALOGENS = {"F", "Cl", "Br", "I"}
CHALCOGENS = {"S", "Se", "Te"}
PNICTOGENS = {"N", "P", "As", "Sb"}


def family(formula: str) -> str:
    """Coarse chemistry family (first match wins): f-electron, intermetallic (all metals), oxide, halide,
    chalcogenide, pnictide, other."""
    els = Composition(formula).elements
    syms = {e.symbol for e in els}
    if syms & compare.F_ELECTRON:
        return "f-electron"
    if all(e.is_metal for e in els):
        return "intermetallic"
    if "O" in syms:
        return "oxide"
    if syms & HALOGENS:
        return "halide"
    if syms & CHALCOGENS:
        return "chalcogenide"
    if syms & PNICTOGENS:
        return "pnictide"
    return "other"


def conformal_bounds(residuals, alpha: float = ALPHA, two_sided: bool = False) -> tuple[float, float]:
    """Split-conformal quantiles (q_lo, q_hi) of the residuals (finite-sample corrected ranks; ±inf when the
    group is too small for the level). Default ONE-SIDED: each bound alone holds with probability ≥ 1 − alpha,
    which is what a stable / unstable decision needs (a stable call only uses the upper bound of the true
    hull distance). two_sided=True gives a ≥ 1 − alpha interval instead."""
    r = np.sort(np.asarray(residuals, float))
    n = len(r)
    a = alpha / 2 if two_sided else alpha
    k_hi = math.ceil((n + 1) * (1 - a))
    k_lo = math.floor((n + 1) * a)
    q_hi = r[k_hi - 1] if 1 <= k_hi <= n else math.inf
    q_lo = r[k_lo - 1] if 1 <= k_lo <= n else -math.inf
    return float(q_lo), float(q_hi)


@dataclass
class ConformalModel:
    alpha: float = ALPHA
    min_group: int = MIN_GROUP
    table: dict = field(default_factory=dict)  # "family|bin" -> [q_lo, q_hi, n]

    def _lookup(self, fam: str, b: str):
        for key, level in ((f"{fam}|{b}", "family × predicted bin"), (f"{fam}|*", "family"), ("*|*", "all")):
            if key in self.table:
                return self.table[key], level
        raise KeyError("conformal model has no global entry")

    def interval(self, formula: str, pred: float) -> dict:
        fam, b = family(formula), compare.hull_bin(pred, below_zero_bin=True)
        (q_lo, q_hi, n), level = self._lookup(fam, b)
        return {"lo": pred - q_hi, "hi": pred - q_lo, "family": fam, "pred_bin": b, "group_level": level, "n_group": n,
                "coverage": 1 - self.alpha, "coverage_meaning": "each bound alone"}

    def to_json(self) -> str:
        return json.dumps({"alpha": self.alpha, "min_group": self.min_group, "table": self.table}, indent=1)

    @classmethod
    def from_json(cls, text: str) -> "ConformalModel":
        d = json.loads(text)
        return cls(d["alpha"], d["min_group"], d["table"])


def fit(df: pd.DataFrame, alpha: float = ALPHA, min_group: int = MIN_GROUP) -> ConformalModel:
    """df: formula, each_pred, each_true (calibration rows only)."""
    d = df.assign(r=df.each_pred - df.each_true, fam=df.formula.map(family),
                  b=df.each_pred.map(lambda e: compare.hull_bin(e, below_zero_bin=True)))
    table = {"*|*": [*conformal_bounds(d.r, alpha), len(d)]}
    for fam, g in d.groupby("fam"):
        if len(g) >= min_group:
            table[f"{fam}|*"] = [*conformal_bounds(g.r, alpha), len(g)]
        for b, gb in g.groupby("b"):
            if len(gb) >= min_group:
                table[f"{fam}|{b}"] = [*conformal_bounds(gb.r, alpha), len(gb)]
    return ConformalModel(alpha, min_group, table)


def crossval_coverage(df: pd.DataFrame, alpha: float = ALPHA, k: int = 5, seed: int = 0) -> pd.DataFrame:
    """k-fold cross-validated coverage of each one-sided bound (target ≥ 1 − alpha each) and of the
    two-sided interval (target ≥ 1 − 2·alpha), per family (calibration data only)."""
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, k, len(df))
    rows = []
    for i in range(k):
        model = fit(df[fold != i], alpha)
        for r in df[fold == i].itertuples():
            iv = model.interval(r.formula, r.each_pred)
            rows.append({"family": iv["family"], "upper holds": r.each_true <= iv["hi"], "lower holds": r.each_true >= iv["lo"],
                         "width": iv["hi"] - iv["lo"]})
    out = pd.DataFrame(rows)
    out["both hold"] = out["upper holds"] & out["lower holds"]

    def agg(g):
        return pd.Series({"n": len(g), "upper bound holds": g["upper holds"].mean(), "lower bound holds": g["lower holds"].mean(),
                          "interval holds": g["both hold"].mean(), "median width (eV/atom)": g.width.median()})

    summary = out.groupby("family").apply(agg, include_groups=False)
    summary.loc["all"] = agg(out)
    return summary.reset_index().rename(columns={"index": "family"})


# --- certified decision thresholds (Learn-then-Test style precision control) -------------------------------
# Observed on the calibration set: one-sided conformal bounds hold ~90 % of the time per group, yet only ~65 %
# of the candidates whose upper bound falls below 0 were truly stable — marginal coverage does not control the
# error rate AMONG THE CANDIDATES A RULE SELECTS, which is what a lab budget depends on. Decisions therefore
# use thresholds certified directly on that quantity: for each chemistry family, the loosest threshold t whose
# 'stable' calls (prediction ≤ t) have precision ≥ target with a one-sided Clopper-Pearson bound at confidence
# 1 − (1 − conf)/|grid| (Bonferroni over the threshold grid, so picking the best t keeps the guarantee), and
# likewise the most inclusive threshold whose 'unstable' calls have NPV ≥ target. A family that cannot certify
# a side gets no label on that side (its candidates go to DFT). Conformal bounds are still reported as the
# uncertainty shown next to each prediction.
DEC_GRID = tuple(round(x, 3) for x in np.arange(-0.30, 0.3001, 0.01))
TARGET_PRECISION, TARGET_NPV, CERT_CONF, MIN_SELECTED, MIN_FAMILY = 0.90, 0.95, 0.95, 20, 100


def cp_lower(k: int, n: int, conf: float) -> float:
    """One-sided Clopper-Pearson lower confidence bound on a proportion k/n."""
    from scipy.stats import beta

    return 0.0 if k <= 0 else float(beta.ppf(1 - conf, k, n - k + 1))


def certify(pred, stable, target: float, side: str, conf: float = CERT_CONF, grid=DEC_GRID,
            min_selected: int = MIN_SELECTED) -> float | None:
    """Certified threshold, or None. side='stable': loosest t with precision(pred ≤ t) certified ≥ target;
    side='unstable': lowest t with NPV(pred > t) certified ≥ target."""
    pred, stable = np.asarray(pred, float), np.asarray(stable, bool)
    level = 1 - (1 - conf) / len(grid)
    ok = []
    for t in grid:
        sel = pred <= t + M.ON_HULL_TOL if side == "stable" else pred > t + M.ON_HULL_TOL
        n = int(sel.sum())
        if n < min_selected:
            continue
        k = int(stable[sel].sum()) if side == "stable" else int((~stable[sel]).sum())
        if cp_lower(k, n, level) >= target:
            ok.append(t)
    if not ok:
        return None
    return max(ok) if side == "stable" else min(ok)


@dataclass
class DecisionRule:
    target_precision: float = TARGET_PRECISION
    target_npv: float = TARGET_NPV
    conf: float = CERT_CONF
    thresholds: dict = field(default_factory=dict)  # family -> {"stable": t|None, "unstable": t|None, "n": n}

    def decide(self, formula: str, pred: float) -> tuple[str | None, str]:
        fam = family(formula)
        th = self.thresholds.get(fam)
        if th is None:
            return None, f"no certified thresholds for family '{fam}' (too few calibration structures)"
        if th["stable"] is not None and pred <= th["stable"] + M.ON_HULL_TOL:
            return "stable", f"prediction ≤ certified stable threshold {th['stable'] * 1000:+.0f} meV/atom ({fam})"
        if th["unstable"] is not None and pred > th["unstable"] + M.ON_HULL_TOL:
            return "unstable", f"prediction > certified unstable threshold {th['unstable'] * 1000:+.0f} meV/atom ({fam})"
        return None, "between the certified thresholds (low confidence)"


def fit_decision(df: pd.DataFrame, target_precision: float = TARGET_PRECISION, target_npv: float = TARGET_NPV,
                 conf: float = CERT_CONF, min_family: int = MIN_FAMILY) -> DecisionRule:
    """Certify per-family thresholds on calibration rows (formula, each_pred, each_true). Pass only the rows
    that would actually receive a label (i.e. after the weak-chemistry / structure-change exclusions)."""
    d = df.assign(fam=df.formula.map(family), stable=df.each_true <= M.ON_HULL_TOL)
    th = {}
    for fam, g in d.groupby("fam"):
        if len(g) < min_family:
            continue
        th[fam] = {"stable": certify(g.each_pred, g.stable, target_precision, "stable", conf),
                   "unstable": certify(g.each_pred, g.stable, target_npv, "unstable", conf), "n": len(g)}
    return DecisionRule(target_precision, target_npv, conf, th)


def empirical_reliability(df: pd.DataFrame, threshold: float, n_boot: int = 1000) -> pd.DataFrame:
    """Per chemistry family × predicted bin: how often the stable / unstable call at `threshold` is right."""
    d = df.assign(fam=df.formula.map(family), b=df.each_pred.map(lambda e: compare.hull_bin(e, below_zero_bin=True)),
                  call=df.each_pred <= threshold + M.ON_HULL_TOL, truth=df.each_true <= M.ON_HULL_TOL)
    rows = []
    for (fam, b), g in d.groupby(["fam", "b"]):
        right = (g.call == g.truth).astype(float)
        rows.append({"family": fam, "predicted bin": b, "n": len(g), "call": "stable" if g.call.mean() >= 0.5 else "unstable",
                     "call right": M.boot_ci(right, M.MEAN, n_boot)})
    return pd.DataFrame(rows)
