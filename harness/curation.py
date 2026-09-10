"""Curate substitution pairs from data/substitution_candidates.csv.

For each candidate: the parent is the lowest-PBE-hull MP material of that formula in the stated
space group; the target is the lowest-PBE-hull polymorph of the target formula whose PBE structure
matches the parent's prototype (same space group + anonymized StructureMatcher at pymatgen's
default tolerances). Candidates without such a target are dropped and logged with the reason and
the polymorphs that were available — never silently.
"""

from __future__ import annotations

import csv
import json
import logging

import numpy as np
from pymatgen.core import Composition

from harness import compare, mp_data
from harness.config import DATA_DIR

log = logging.getLogger(__name__)

CANDIDATES = DATA_DIR / "substitution_candidates.csv"
PAIRS = DATA_DIR / "substitution_pairs.json"
DROPPED = DATA_DIR / "substitution_dropped.json"
SPACE_ANIONS = {"O", "N", "C", "F"}


def parse_mapping(text: str) -> dict[str, str]:
    """'Si:B;C:N' -> {'Si': 'B', 'C': 'N'}"""
    out = {}
    for part in filter(None, (p.strip() for p in text.split(";"))):
        src, dst = (x.strip() for x in part.split(":"))
        out[src] = dst
    return out


def is_space_relevant(formula: str) -> bool:
    """Oxides, nitrides, carbides, fluorides (compounds only)."""
    els = {e.symbol for e in Composition(formula).elements}
    return len(els) > 1 and bool(els & SPACE_ANIONS)


def _pbe_magnetization(structure) -> float:
    mags = structure.site_properties.get("magmom")
    return float(np.sum(np.abs(mags)) / len(structure)) if mags else 0.0


def _flags(target: dict) -> dict:
    summ = target.get("summary") or {}
    pbe_mag = _pbe_magnetization(target["structure"])
    doc = {
        "ordering": summ.get("ordering"),
        "is_magnetic": bool(summ.get("is_magnetic")) or pbe_mag > 0.05,
        "total_magnetization_normalized_formula_units": summ.get("total_magnetization_normalized_formula_units"),
    }
    flags = compare.system_flags(target["structure"].composition.elements, doc)
    flags["pbe_abs_magmom_per_site"] = pbe_mag
    return flags


def resolve_pairs(force: bool = False) -> list[dict]:
    if PAIRS.is_file() and not force:
        return json.loads(PAIRS.read_text())
    pairs, dropped = [], []
    with CANDIDATES.open() as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        pid = f"{r['parent']}->{r['target']}"
        base = {"pair_id": pid, "family": r["family"], "parent_formula": r["parent"], "target_formula": r["target"],
                "mapping": r["mapping"], "note": r["note"]}
        mapping = parse_mapping(r["mapping"])
        try:
            parent = mp_data.ground_state(r["parent"], int(r["parent_sg"]))
        except KeyError as exc:
            dropped.append({**base, "reason": f"parent not found: {exc}"})
            continue
        sub = compare.substitute(parent["structure"], mapping)
        want = Composition(r["target"]).reduced_formula
        if sub.composition.reduced_formula != want:
            dropped.append({**base, "reason": f"mapping yields {sub.composition.reduced_formula}, not {want}"})
            continue
        cands = mp_data.pbe_candidates(r["target"])
        same_sg = [c for c in cands if c["spacegroup_number"] == parent["spacegroup_number"]]
        matching = [c for c in same_sg if compare.same_prototype(parent["structure"], c["structure"])]
        if not matching:
            avail = sorted(cands, key=lambda c: c["energy_above_hull"] if c["energy_above_hull"] is not None else 9)[:6]
            dropped.append({**base, "parent_id": parent["material_id"],
                            "reason": (f"no {want} polymorph in SG {parent['spacegroup_number']} matching the parent "
                                       f"prototype ({len(cands)} PBE polymorphs, {len(same_sg)} in same SG)"),
                            "available": [(c["material_id"], c["spacegroup_number"], c["energy_above_hull"]) for c in avail]})
            continue
        target = min(matching, key=lambda c: (c["energy_above_hull"] is None, c["energy_above_hull"] or 0.0))
        lowest = min((c["energy_above_hull"] for c in cands if c["energy_above_hull"] is not None), default=None)
        pairs.append({
            **base,
            "parent_id": parent["material_id"],
            "parent_sg": parent["spacegroup_number"],
            "target_id": target["material_id"],
            "target_sg": target["spacegroup_number"],
            "expected_target_sg": int(r["expected_target_sg"]),
            "target_functional": target["functional"],
            "target_e_above_hull": target["energy_above_hull"],
            "target_is_formula_ground_state": lowest is not None and target["energy_above_hull"] <= lowest + 1e-6,
            "n_target_polymorphs": len(cands),
            "space_relevant": is_space_relevant(r["target"]),
            "flags": _flags(target),
        })
        log.info("pair %-18s %s -> %s (SG %s, e_hull %.3f)", pid, parent["material_id"], target["material_id"],
                 target["spacegroup_number"], target["energy_above_hull"] or 0.0)
    for d in dropped:
        log.warning("DROPPED %s: %s", d["pair_id"], d["reason"])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PAIRS.write_text(json.dumps(pairs, indent=1, default=str) + "\n")
    DROPPED.write_text(json.dumps(dropped, indent=1, default=str) + "\n")
    return pairs


def load_dropped() -> list[dict]:
    return json.loads(DROPPED.read_text()) if DROPPED.is_file() else []
