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


def route(c: Candidate, model: ConformalModel, policy: RoutingPolicy) -> Decision:
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
    straddles = iv["lo"] <= policy.threshold < iv["hi"]
    if straddles:
        reasons.append(f"low confidence: {iv['coverage']:.0%} interval [{iv['lo'] * 1000:+.0f}, {iv['hi'] * 1000:+.0f}] meV/atom "
                       f"straddles the threshold")
    if reasons:
        return Decision(c.id, SEND_TO_DFT, reasons, iv)
    return Decision(c.id, LIKELY_STABLE if iv["hi"] <= policy.threshold else LIKELY_UNSTABLE, [], iv)


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
