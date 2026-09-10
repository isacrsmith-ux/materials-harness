"""Materials Project access with a permanent on-disk cache and rate-limit backoff.

Every query is cached under cache/mp/ as JSON keyed by the query, so reruns never hit the
API (and don't even need a key once the cache is warm). The API key is read from .env and
passed straight to MPRester; it is never printed, logged, or written anywhere else.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable

from monty.json import MontyDecoder, MontyEncoder
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential

from harness import ROOT
from harness.config import MP_CACHE_DIR

log = logging.getLogger(__name__)

SUMMARY_FIELDS = [
    "material_id", "formula_pretty", "chemsys", "structure", "nsites", "volume", "density",
    "symmetry", "energy_per_atom", "uncorrected_energy_per_atom", "formation_energy_per_atom",
    "energy_above_hull", "is_stable", "theoretical", "is_magnetic", "ordering",
    "total_magnetization", "total_magnetization_normalized_formula_units", "database_IDs",
    "deprecated", "bulk_modulus",
]


class MissingAPIKey(RuntimeError):
    pass


def _api_key() -> str:
    from dotenv import dotenv_values

    key = (dotenv_values(ROOT / ".env").get("MP_API_KEY") or "").strip()
    if not key:
        raise MissingAPIKey(
            "MP_API_KEY is not set in .env (cache miss needs the API). "
            "Copy .env.example to .env and paste your key."
        )
    return key


def _is_retryable(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(t in text for t in ("429", "rate", "too many", "timeout", "timed out", "connection",
                                   "502", "503", "504", "temporarily"))


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=2, min=2, max=120),
    stop=stop_after_attempt(7),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)


def _rester():
    from mp_api.client import MPRester

    return MPRester(api_key=_api_key(), mute_progress_bars=True)


def _cache_path(category: str, key: dict) -> Path:
    blob = json.dumps(key, sort_keys=True, default=str)
    digest = hashlib.sha256(blob.encode()).hexdigest()[:20]
    return MP_CACHE_DIR / category / f"{digest}.json"


def cached(category: str, key: dict, fetch: Callable[[], Any]) -> Any:
    """Return the cached value for (category, key), fetching (with backoff) on a miss."""
    path = _cache_path(category, key)
    if path.is_file():
        return json.loads(path.read_text(), cls=MontyDecoder)["value"]
    value = _retry(fetch)()
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps({"query": key, "value": value}, cls=MontyEncoder)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(blob)
    tmp.replace(path)
    # Return exactly what a cache hit would return, so first runs and reruns see identical types.
    return json.loads(blob, cls=MontyDecoder)["value"]


def _docs_to_dicts(docs) -> list[dict]:
    out = []
    for d in docs:
        dd = d.model_dump() if hasattr(d, "model_dump") else dict(d)
        out.append({k: v for k, v in dd.items() if k in SUMMARY_FIELDS or k == "material_id"})
    return out


def _summary_search(**criteria) -> list[dict]:
    def fetch():
        with _rester() as mpr:
            docs = mpr.materials.summary.search(**criteria, fields=SUMMARY_FIELDS)
        return _docs_to_dicts(docs)

    return cached("summary", criteria, fetch)


def summary(material_id: str) -> dict:
    docs = _summary_search(material_ids=[material_id])
    if not docs:
        raise KeyError(f"{material_id} not found in Materials Project")
    return _normalize(docs[0])


def search_formula(formula: str, **extra) -> list[dict]:
    return [_normalize(d) for d in _summary_search(formula=formula, **extra)]


def _normalize(doc: dict) -> dict:
    """Flatten the bits we use everywhere; keep Structure objects as Structures."""
    from pymatgen.core import Structure

    d = dict(doc)
    d["material_id"] = str(d["material_id"])
    if isinstance(d.get("structure"), dict):
        d["structure"] = Structure.from_dict(d["structure"])
    sym = d.get("symmetry") or {}
    if not isinstance(sym, dict):
        sym = sym.model_dump() if hasattr(sym, "model_dump") else dict(sym)
    d["spacegroup_symbol"] = sym.get("symbol")
    d["spacegroup_number"] = sym.get("number")
    d["crystal_system"] = str(sym.get("crystal_system")) if sym.get("crystal_system") else None
    d["ordering"] = str(d["ordering"]) if d.get("ordering") is not None else None
    if d["ordering"] and "." in d["ordering"]:
        d["ordering"] = d["ordering"].split(".")[-1]
    return d


# --- PBE (GGA/GGA+U) references ------------------------------------------------------------
# IMPORTANT: MP's summary endpoint now serves r2SCAN structures/energies for many materials
# (e.g. Ge: summary a = 5.675 Å, E = -13.87 eV/atom; GGA a = 5.763 Å, E = -4.62 eV/atom).
# MACE-MP-0 was trained on PBE/PBE+U (MPtrj), so every reference value MUST come from the
# GGA_GGA+U thermo documents below — never from summary["structure"] or summary energies.
PBE_THERMO_TYPE = "GGA_GGA+U"


def _thermo(**criteria) -> list[dict]:
    def fetch():
        with _rester() as mpr:
            docs = mpr.materials.thermo.search(**criteria)
        return [d.model_dump(mode="json") for d in docs]

    return cached("thermo", criteria, fetch)


def _pbe_from_thermo(t: dict, requested_id: str | None = None) -> dict:
    from pymatgen.entries.computed_entries import ComputedStructureEntry

    entries = t.get("entries") or {}
    run_type = next((rt for rt in ("GGA", "GGA+U") if rt in entries), None)
    if run_type is None:
        raise KeyError(f"{t.get('material_id')}: GGA_GGA+U thermo doc has no GGA/GGA+U entry ({list(entries)})")
    raw = entries[run_type]
    entry = raw if isinstance(raw, ComputedStructureEntry) else ComputedStructureEntry.from_dict(raw)
    return {
        "material_id": str(t["material_id"]),
        "requested_id": requested_id or str(t["material_id"]),
        "formula": entry.composition.reduced_formula,
        "structure": entry.structure,
        "entry": entry,
        "run_type": run_type,  # "GGA" (PBE) or "GGA+U" (PBE+U)
        "functional": "PBE+U" if run_type == "GGA+U" else "PBE",
        "thermo_type": t.get("thermo_type"),
        "uncorrected_energy_per_atom": entry.uncorrected_energy_per_atom,
        "corrected_energy_per_atom": t.get("energy_per_atom"),
        "energy_above_hull": t.get("energy_above_hull"),
        "is_stable": t.get("is_stable"),
        "task_id": str(entry.data.get("task_id") or entry.entry_id),
    }


def pbe_reference(material_id: str) -> dict:
    """PBE/PBE+U structure, uncorrected energy and GGA-hull stability for one material."""
    docs = [t for t in _thermo(material_ids=[material_id]) if t.get("thermo_type") == PBE_THERMO_TYPE]
    if not docs:
        raise KeyError(f"{material_id}: no {PBE_THERMO_TYPE} thermo document (no PBE reference)")
    return _pbe_from_thermo(docs[0], requested_id=material_id)


def pbe_candidates(formula: str) -> list[dict]:
    """All polymorphs of a formula with PBE data, joined with summary metadata (symmetry, magnetism)."""
    thermo = [t for t in _thermo(formula=formula, thermo_types=[PBE_THERMO_TYPE])
              if t.get("thermo_type") == PBE_THERMO_TYPE]
    meta = {d["material_id"]: d for d in search_formula(formula)}
    out = []
    for t in thermo:
        try:
            ref = _pbe_from_thermo(t)
        except KeyError as exc:  # doc without a GGA/GGA+U entry: no PBE reference for this polymorph
            log.debug("skipping %s: %s", t.get("material_id"), exc)
            continue
        m = meta.get(ref["material_id"], {})
        if m.get("deprecated"):
            continue
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

        ref["spacegroup_number"] = SpacegroupAnalyzer(ref["structure"], symprec=0.1).get_space_group_number()
        ref["summary"] = m
        out.append(ref)
    return out


def ground_state(formula: str, spacegroup_number: int | None = None) -> dict:
    """Lowest PBE-hull-energy MP material for a formula (optionally within one space group).

    The space group is taken from the PBE structure itself (symprec 0.1), not the summary.
    """
    docs = pbe_candidates(formula)
    if spacegroup_number is not None:
        docs = [d for d in docs if d["spacegroup_number"] == spacegroup_number]
    if not docs:
        raise KeyError(f"No PBE MP entry for {formula}" + (f" in SG {spacegroup_number}" if spacegroup_number else ""))
    return min(docs, key=lambda d: (d["energy_above_hull"] is None, d["energy_above_hull"] or 0.0,
                                    d["uncorrected_energy_per_atom"]))


def str_keys(obj):
    """Recursively turn dict keys into strings (Element('O') -> 'O')."""
    if isinstance(obj, dict):
        return {str(k): str_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [str_keys(v) for v in obj]
    return obj


def entries_in_chemsys(chemsys: str) -> list:
    """GGA/GGA+U ComputedStructureEntries for a chemical system.

    MP serves entry.data["oxidation_states"] keyed by Element objects, but pymatgen's
    MaterialsProject2020Compatibility looks anions up by symbol string (.get("F", 0)); an
    Element key never matches, silently dropping to its electronegativity fallback. Keys are
    normalised to strings here (this also makes the entries JSON-cacheable).
    """

    def fetch():
        with _rester() as mpr:
            entries = mpr.get_entries_in_chemsys(
                chemsys.split("-"), additional_criteria={"thermo_types": ["GGA_GGA+U"]}
            )
        for e in entries:
            e.data = str_keys(e.data)
        return entries

    return cached("entries_chemsys", {"chemsys": "-".join(sorted(chemsys.split("-"))), "thermo": "GGA_GGA+U"}, fetch)


def elasticity(material_id: str) -> dict | None:
    def fetch():
        with _rester() as mpr:
            docs = mpr.materials.elasticity.search(material_ids=[material_id])
        if not docs:
            return None
        d = docs[0].model_dump()
        return {k: d.get(k) for k in ("material_id", "bulk_modulus", "shear_modulus", "state", "warnings")}

    return cached("elasticity", {"material_id": material_id}, fetch)
