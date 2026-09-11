"""One label per candidate: 'likely stable', 'likely unstable' or 'send to DFT'.

A candidate is sent to DFT when ANY of these holds (every reason is returned, not just the first):
  low confidence        its conformal interval for the true hull distance straddles the decision threshold
  model disagreement    the two engines' predicted hull distances differ by more than the tolerance
  known-weak chemistry  it contains an element whose calibration error is not shown to be acceptable
                        (per-element table: MAE upper bound above the caution line, or too few compounds)
  structure changed     the relaxation left the candidate's starting structure (StructureMatcher)
Otherwise it is 'likely stable' when the whole interval is at or below the threshold, 'likely unstable'
when the whole interval is above it.

DFT itself is out of scope: DFTBackend is the interface a future DFT check implements; FileQueueDFT only
records requests (data/dft_requests.jsonl) so the routing can be exercised end to end.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from pymatgen.core import Composition

from harness.config import DATA_DIR
from harness.confidence import ConformalModel

LIKELY_STABLE, LIKELY_UNSTABLE, SEND_TO_DFT = "likely stable", "likely unstable", "send to DFT"


@dataclass
class Candidate:
    id: str
    formula: str
    pred_e_hull: float                       # engine 1, eV/atom
    pred_e_hull_2: float | None = None       # engine 2 (disagreement signal), eV/atom
    structure_changed: bool | None = None    # relaxation left the starting structure
    extra: dict = field(default_factory=dict)


@dataclass
class RoutingPolicy:
    threshold: float = 0.0                   # eV/atom, decision threshold on the hull distance
    disagreement_tol: float | None = None    # eV/atom; None = no second engine yet
    weak_elements: frozenset = frozenset()   # from the per-element calibration table
    route_structure_change: bool = True


@dataclass
class Decision:
    id: str
    label: str
    reasons: list
    interval: dict


def route(c: Candidate, model: ConformalModel, policy: RoutingPolicy, rule=None) -> Decision:
    """With a certified DecisionRule (confidence.fit_decision), the stable / unstable call uses its per-family
    thresholds; without one, the conformal bounds decide (kept for comparison: it does not control precision
    among the selected candidates). The conformal interval is always attached for display."""
    iv = model.interval(c.formula, c.pred_e_hull)
    reasons = []
    weak = sorted({e.symbol for e in Composition(c.formula).elements} & set(policy.weak_elements))
    if weak:
        reasons.append(f"known-weak chemistry ({', '.join(weak)})")
    if policy.route_structure_change and c.structure_changed:
        reasons.append("relaxation changed the structure")
    if policy.disagreement_tol is not None and c.pred_e_hull_2 is not None \
            and abs(c.pred_e_hull - c.pred_e_hull_2) > policy.disagreement_tol:
        reasons.append(f"engines disagree by {abs(c.pred_e_hull - c.pred_e_hull_2) * 1000:.0f} meV/atom")
    if rule is not None:
        call, why = rule.decide(c.formula, c.pred_e_hull)
        if call is None:
            reasons.append(f"low confidence: {why}")
        if reasons:
            return Decision(c.id, SEND_TO_DFT, reasons, iv)
        return Decision(c.id, LIKELY_STABLE if call == "stable" else LIKELY_UNSTABLE, [why], iv)
    straddles = iv["lo"] <= policy.threshold < iv["hi"]
    if straddles:
        reasons.append(f"low confidence: neither {iv['coverage']:.0%} bound clears the threshold")
    if reasons:
        return Decision(c.id, SEND_TO_DFT, reasons, iv)
    return Decision(c.id, LIKELY_STABLE if iv["hi"] <= policy.threshold else LIKELY_UNSTABLE, [], iv)


def weak_elements_from(df: "pd.DataFrame", err_col: str | None = None, min_count: int = 20, caution_mev: float = 60.0,
                       n_boot: int = 500) -> frozenset:
    """Known-weak chemistry: elements that are demonstrably bad (MAE lower 95 % bound above the caution line)
    or too rare in the calibration set to judge (fewer than min_count compounds).

    Not 'upper bound above the caution line': per-element errors attribute every compound's error to all of
    its elements, so common elements (O, N, ...) inherit the overall error and would flag nearly everything —
    the conformal interval already carries the overall uncertainty; this rule is for chemistry that is worse."""
    from pymatgen.core import Composition as _C

    from harness import metrics as M

    d = df if err_col else df.assign(_err=(df.each_pred - df.each_true) * 1000)
    col = err_col or "_err"
    present = {e.symbol for f in d.formula for e in _C(f).elements}
    table, _ = M.per_element(d, "formula", col, min_count, n_boot)
    judged = set(table.element) if len(table) else set()
    bad = {r.element for r in table.itertuples() if r.MAE[1] > caution_mev}
    return frozenset(bad | (present - judged))


def labelable(df: "pd.DataFrame", policy: RoutingPolicy) -> "pd.Series":
    """Rows that no exclusion rule sends to DFT (the population the certified thresholds must hold on)."""
    from pymatgen.core import Composition as _C

    ok = ~df.formula.map(lambda f: bool({e.symbol for e in _C(f).elements} & set(policy.weak_elements)))
    if policy.route_structure_change and "structure_changed" in df:
        ok &= ~df.structure_changed.fillna(False).astype(bool)
    if policy.disagreement_tol is not None and "pred_2" in df:
        ok &= ~((df.each_pred - df.pred_2).abs() > policy.disagreement_tol)
    return ok


def crossval_routing(df: "pd.DataFrame", alpha: float = 0.10, k: int = 5, seed: int = 0, threshold: float = 0.0,
                     disagreement_tol: float | None = None, certified: bool = True) -> "pd.DataFrame":
    """Route every calibration structure with a conformal model, weak-element list and (certified=True)
    per-family decision thresholds all fitted on the OTHER folds (k-fold), so the label quality is estimated
    without touching the test set. df: formula, each_pred, each_true, optional pred_2, structure_changed."""
    import numpy as np
    import pandas as pd

    from harness import confidence as C

    rng = np.random.default_rng(seed)
    fold = rng.integers(0, k, len(df))
    rows = []
    for i in range(k):
        train, test = df[fold != i], df[fold == i]
        model = C.fit(train, alpha)
        pol = RoutingPolicy(threshold=threshold, disagreement_tol=disagreement_tol, weak_elements=weak_elements_from(train))
        rule = C.fit_decision(train[labelable(train, pol)]) if certified else None
        for r in test.itertuples():
            cand = Candidate(str(getattr(r, "wbm_id", r.Index)), r.formula, r.each_pred,
                             getattr(r, "pred_2", None), getattr(r, "structure_changed", None))
            d = route(cand, model, pol, rule)
            rows.append({"id": cand.id, "label": d.label, "truly_stable": r.each_true <= 1e-6, "each_true": r.each_true,
                         "reasons": "; ".join(d.reasons), "family": d.interval["family"]})
    return pd.DataFrame(rows)


def routing_summary(dec: "pd.DataFrame") -> dict:
    n = len(dec)
    st = dec[dec.label == LIKELY_STABLE]
    un = dec[dec.label == LIKELY_UNSTABLE]
    dft = dec[dec.label == SEND_TO_DFT]
    n_stable = int(dec.truly_stable.sum())
    return {"n": n, "likely stable": len(st), "likely unstable": len(un), "send to DFT": len(dft),
            "precision of 'likely stable'": st.truly_stable.mean() if len(st) else float("nan"),
            "NPV of 'likely unstable'": (~un.truly_stable).mean() if len(un) else float("nan"),
            "share sent to DFT": len(dft) / n if n else float("nan"),
            "truly stable found as 'likely stable'": len(st[st.truly_stable]) / n_stable if n_stable else float("nan"),
            "truly stable sent to DFT": len(dft[dft.truly_stable]) / n_stable if n_stable else float("nan"),
            "truly stable wrongly called 'likely unstable'": len(un[un.truly_stable]) / n_stable if n_stable else float("nan")}


class DFTBackend(Protocol):
    """What a future DFT check must provide. Not implemented here (out of scope)."""

    def submit(self, candidate: Candidate, decision: Decision) -> str: ...
    def status(self, ticket: str) -> str: ...
    def result(self, ticket: str) -> dict | None: ...


class FileQueueDFT:
    """Stub backend: appends each request to a JSON-lines file; never computes anything."""

    def __init__(self, path: Path = DATA_DIR / "dft_requests.jsonl"):
        self.path = Path(path)

    def submit(self, candidate: Candidate, decision: Decision) -> str:
        ticket = f"dft-{candidate.id}"
        rec = {"ticket": ticket, "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "candidate": asdict(candidate), "reasons": decision.reasons, "interval": decision.interval}
        with self.path.open("a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        return ticket

    def status(self, ticket: str) -> str:
        return "queued (no DFT backend configured)"

    def result(self, ticket: str) -> dict | None:
        return None
