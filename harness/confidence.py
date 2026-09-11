"""Empirical confidence for stability calls, fitted on the WBM CALIBRATION set only.

Method: Mondrian (group-conditional) split-conformal prediction on the residual
    r = predicted hull distance − true hull distance   (eV/atom)
with groups = chemistry family × predicted hull bin. For a new candidate in group g with prediction p,
the true hull distance lies in [p − q_hi(g), p − q_lo(g)] with probability ≥ 1 − α (finite-sample,
distribution-free, marginal over the group), where q_lo / q_hi are the conformal quantiles of the group's
calibration residuals. Groups with fewer than MIN_GROUP calibration members fall back to the family, then
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


def conformal_bounds(residuals, alpha: float = ALPHA) -> tuple[float, float]:
    """Two-sided split-conformal quantiles (q_lo, q_hi) of the residuals at level 1 − alpha
    (finite-sample corrected ranks; ±inf when the group is too small for the level)."""
    r = np.sort(np.asarray(residuals, float))
    n = len(r)
    k_hi = math.ceil((n + 1) * (1 - alpha / 2))
    k_lo = math.floor((n + 1) * (alpha / 2))
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
                "coverage": 1 - self.alpha}

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
    """k-fold cross-validated coverage and width of the intervals, per family (calibration data only)."""
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, k, len(df))
    rows = []
    for i in range(k):
        model = fit(df[fold != i], alpha)
        for r in df[fold == i].itertuples():
            iv = model.interval(r.formula, r.each_pred)
            rows.append({"family": iv["family"], "covered": iv["lo"] <= r.each_true <= iv["hi"], "width": iv["hi"] - iv["lo"]})
    out = pd.DataFrame(rows)
    summary = out.groupby("family").agg(n=("covered", "size"), coverage=("covered", "mean"), median_width_ev=("width", "median"))
    total = pd.DataFrame({"n": [len(out)], "coverage": [out.covered.mean()], "median_width_ev": [out.width.median()]}, index=["all"])
    return pd.concat([summary, total]).reset_index().rename(columns={"index": "family"})


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
