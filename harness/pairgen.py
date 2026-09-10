"""Automatic substitution-pair generator (Materials Project, PBE structures).

1. Candidates: every non-deprecated MP material with <= max_atoms sites (light metadata, bulk
   download) is grouped by (space group, site count, anonymized reduced formula). Inside a group,
   two materials form a candidate when their compositions differ by exactly one element
   substitution: A -> B with identical amounts, every other element identical.
2. Order: space-relevant targets (oxides, nitrides, carbides, fluorides) first; within each tier,
   round-robin across prototypes so no single prototype dominates; within a prototype, pairs of
   experimentally known (non-theoretical), near-hull materials first. The parent is the partner
   closer to the hull.
3. Confirm: each candidate is checked on the PBE structures with the same test the curated suite
   uses — pymatgen StructureMatcher on anonymized structures at default tolerances
   (compare.same_prototype) — plus the substitution reproducing the target composition and the
   PBE cells staying within max_atoms. Accept until max_pairs; every rejection is counted by reason.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone

from pymatgen.core import Composition

from harness import compare, mp_data
from harness.config import DATA_DIR
from harness.curation import _flags, is_space_relevant, parse_mapping, resolve_pairs

log = logging.getLogger(__name__)

AUTO_PAIRS = DATA_DIR / "auto_pairs.json"
AUTO_META = DATA_DIR / "auto_pairs_meta.json"
ROUND = 6


def _amounts(comp: dict) -> dict[str, float]:
    return {str(k): round(float(v), ROUND) for k, v in comp.items()}


def one_element_substitution(a: dict, b: dict) -> tuple[str, str] | None:
    """(x, y) if composition b is composition a with element x replaced by y at the same amount."""
    a, b = _amounts(a), _amounts(b)
    if len(a) != len(b):
        return None
    only_a, only_b = set(a) - set(b), set(b) - set(a)
    if len(only_a) != 1 or len(only_b) != 1:
        return None
    x, y = only_a.pop(), only_b.pop()
    if a[x] != b[y] or any(a[e] != b[e] for e in set(a) & set(b)):
        return None
    return x, y


def prototype_key(doc: dict) -> tuple:
    return doc["sg_number"], doc["nsites"], Composition(doc["composition_reduced"]).anonymized_formula


def _hull(doc: dict) -> float:
    e = doc.get("energy_above_hull")
    return float(e) if e is not None else 9e9


def _orient(da: dict, db: dict, ea: str, eb: str, key: tuple) -> dict:
    """Parent = the partner closer to the hull (then lower id); mapping replaces parent's element."""
    if (_hull(da), da["material_id"]) <= (_hull(db), db["material_id"]):
        parent, target, src, dst = da, db, ea, eb
    else:
        parent, target, src, dst = db, da, eb, ea
    sg_number, nsites, anon = key
    return {
        "parent_id": parent["material_id"], "target_id": target["material_id"],
        "parent_formula": parent["formula"], "target_formula": target["formula"],
        "mapping": f"{src}:{dst}", "prototype": f"{anon}_{parent.get('sg_symbol') or sg_number}",
        "sg_number": sg_number, "nsites": nsites,
        "space_relevant": is_space_relevant(target["formula"]),
        "known_count": int(not parent.get("theoretical")) + int(not target.get("theoretical")),
        "e_hull_sum": _hull(parent) + _hull(target),
        "target_summary": {k: target.get(k) for k in ("is_magnetic", "ordering",
                                                      "total_magnetization_normalized_formula_units")},
    }


def candidate_pairs(docs: list[dict], supported: set[str] | None = None) -> list[dict]:
    """All one-element-substitution pairs within each (space group, sites, anonymized formula) group.

    Bucketing: for each material and each of its elements e, the signature (the other elements with
    their amounts, amount of e) is shared exactly by materials that differ from it only in e.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for d in docs:
        if not d.get("composition_reduced") or d.get("sg_number") is None:
            continue
        if supported is not None and not set(d["elements"]) <= supported:
            continue
        groups[prototype_key(d)].append(d)
    out, seen = [], set()
    for key, members in groups.items():
        if len(members) < 2:
            continue
        buckets: dict[tuple, list] = defaultdict(list)
        for d in members:
            amt = _amounts(d["composition_reduced"])
            for e, n in amt.items():
                rest = tuple(sorted((k, v) for k, v in amt.items() if k != e))
                buckets[(rest, n)].append((e, d))
        for items in buckets.values():
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    (ea, da), (eb, db) = items[i], items[j]
                    if ea == eb:  # same composition (polymorphs), not a substitution
                        continue
                    ids = tuple(sorted((da["material_id"], db["material_id"])))
                    if ids in seen:
                        continue
                    seen.add(ids)
                    out.append(_orient(da, db, ea, eb, key))
    return out


def prioritize(cands: list[dict]) -> list[dict]:
    def inner(c):
        return -c["known_count"], c["e_hull_sum"], c["parent_id"], c["target_id"]

    ordered: list[dict] = []
    for tier in (True, False):
        by_proto: dict[str, list] = defaultdict(list)
        for c in cands:
            if bool(c["space_relevant"]) == tier:
                by_proto[c["prototype"]].append(c)
        for lst in by_proto.values():
            lst.sort(key=inner)
        queues = deque(deque(by_proto[p]) for p in sorted(by_proto, key=lambda p: inner(by_proto[p][0])))
        while queues:  # round-robin across prototypes
            q = queues.popleft()
            ordered.append(q.popleft())
            if q:
                queues.append(q)
    return ordered


def _check(c: dict, max_atoms: int) -> tuple[str | None, dict | None]:
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    try:
        parent = mp_data.pbe_reference(c["parent_id"])
        target = mp_data.pbe_reference(c["target_id"])
    except KeyError:
        return "no PBE (GGA/GGA+U) reference", None
    ps, ts = parent["structure"], target["structure"]
    if len(ps) > max_atoms or len(ts) > max_atoms:
        return f"PBE cell has more than {max_atoms} atoms", None
    try:
        sub = compare.substitute(ps, parse_mapping(c["mapping"]))
    except ValueError:
        return "mapping not applicable to the PBE structure", None
    if sub.composition.reduced_formula != ts.composition.reduced_formula:
        return "substitution does not give the target composition", None
    if not compare.same_prototype(ps, ts):
        return "StructureMatcher (anonymized): different prototype", None
    pair = {
        "pair_id": f"{parent['formula']}->{target['formula']} [{c['parent_id']}>{c['target_id']}]",
        "family": c["prototype"], "parent_formula": parent["formula"], "target_formula": target["formula"],
        "mapping": c["mapping"], "note": "auto-generated", "source": "auto",
        "parent_id": c["parent_id"], "parent_sg": SpacegroupAnalyzer(ps, symprec=0.1).get_space_group_number(),
        "target_id": c["target_id"], "target_sg": SpacegroupAnalyzer(ts, symprec=0.1).get_space_group_number(),
        "target_functional": target["functional"], "target_e_above_hull": target["energy_above_hull"],
        "space_relevant": c["space_relevant"], "n_atoms_parent": len(ps), "n_atoms_target": len(ts),
        "flags": _flags({"structure": ts, "summary": c["target_summary"]}),
    }
    return None, pair


def verify(ordered: list[dict], max_pairs: int, max_atoms: int, exclude: set | frozenset = frozenset(),
           batch: int = 300) -> tuple[list[dict], dict]:
    accepted: list[dict] = []
    rejected: dict[str, int] = defaultdict(int)
    examples: dict[str, list] = defaultdict(list)
    pos = 0
    while len(accepted) < max_pairs and pos < len(ordered):
        chunk = [c for c in ordered[pos:pos + batch] if (c["parent_id"], c["target_id"]) not in exclude]
        pos += batch
        mp_data.prefetch_pbe({c[k] for c in chunk for k in ("parent_id", "target_id")})
        for c in chunk:
            reason, pair = _check(c, max_atoms)
            if pair:
                accepted.append(pair)
                if len(accepted) >= max_pairs:
                    break
            else:
                rejected[reason] += 1
                if len(examples[reason]) < 5:
                    examples[reason].append(f"{c['parent_id']}->{c['target_id']}")
        log.info("pair verification: %d candidates examined, %d accepted, %d rejected", min(pos, len(ordered)),
                 len(accepted), sum(rejected.values()))
    return accepted, {"candidates_examined": min(pos, len(ordered)), "rejected": dict(rejected),
                      "rejected_examples": dict(examples)}


def supported_elements() -> set[str]:
    """Elements the pinned MACE-MP-0 model has in its element table."""
    from ase.data import chemical_symbols

    from harness import engine

    calc = engine.get_calculator("cpu", "float64")
    return {chemical_symbols[int(z)] for z in calc.models[0].atomic_numbers}


def load_pairs() -> list[dict]:
    return json.loads(AUTO_PAIRS.read_text()) if AUTO_PAIRS.is_file() else []


def load_meta() -> dict:
    return json.loads(AUTO_META.read_text()) if AUTO_META.is_file() else {}


def generate(max_pairs: int, max_atoms: int, force: bool = False) -> dict:
    config = {"max_pairs": max_pairs, "max_atoms": max_atoms}
    meta = load_meta()
    if AUTO_PAIRS.is_file() and meta.get("config") == config and not force:
        log.info("auto pairs already generated for %s — reusing data/auto_pairs.json", config)
        return meta
    docs = mp_data.bulk_summary(max_atoms)
    supported = supported_elements()
    cands = candidate_pairs(docs, supported)
    ordered = prioritize(cands)
    curated = {(p["parent_id"], p["target_id"]) for p in resolve_pairs()}
    log.info("%d MP materials <= %d atoms, %d candidate pairs (%d space-relevant); verifying in priority order",
             len(docs), max_atoms, len(cands), sum(c["space_relevant"] for c in cands))
    pairs, vstats = verify(ordered, max_pairs, max_atoms, exclude=curated)
    fl = [p["flags"] for p in pairs]
    meta = {
        "config": config, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_materials": len(docs), "n_supported_elements": len(supported),
        "n_prototype_groups": len({prototype_key(d) for d in docs if d.get("composition_reduced")}),
        "n_candidates": len(cands), "n_candidates_space_relevant": sum(c["space_relevant"] for c in cands),
        "accepted": len(pairs), "accepted_space_relevant": sum(p["space_relevant"] for p in pairs),
        "accepted_prototypes": len({p["family"] for p in pairs}),
        "flagged": {"magnetic": sum(f["magnetic"] for f in fl), "f_electron": sum(f["f_electron"] for f in fl),
                    "transition_metal": sum(f["transition_metal"] for f in fl),
                    "spin_caveat": sum(f["spin_caveat"] for f in fl)},
        "excluded_curated_pairs": len(curated), **vstats,
    }
    AUTO_PAIRS.write_text(json.dumps(pairs, indent=1, default=str) + "\n")
    AUTO_META.write_text(json.dumps(meta, indent=1, default=str) + "\n")
    return meta
