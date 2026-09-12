"""Placing an engine energy on the Materials Project DFT hull — mode (a), one implementation.

Mode (a) is the construction the report recommends for new materials (`reports/validation_report.md`:
relaxing every competitor with the engine makes the hull-distance error *larger*). It needs no
competitor relaxations: the engine's relaxed structure and energy become one MP2020-corrected entry,
and that entry is placed against the Materials Project GGA/GGA+U hull of its chemical system.

Everything the validation suites already did for MP substitution targets lives here now
(`material_id`, `process`, `mace_entry`, `signed_hull_energy`, `window_phases`); `harness.suites.stability`
re-exports all of it, so the suites are unchanged. What is new is the product half: a validation suite
always has an MP entry for the exact material it is scoring and can inherit that entry's VASP
parameters, while the product is handed a composition Materials Project may never have computed.
`product_entry` therefore builds the calculation parameters from the chemistry itself, using
MaterialsProject2020Compatibility's own U settings, and leaves `oxide_type` / `oxidation_states` unset
so the correction scheme derives them from the structure rather than from some other material's data.

Checked against the WBM calibration set (84 structures, all seven chemistry families): the hull
distance built this way reproduces Matbench Discovery's `each_pred` to < 1 meV/atom for 78 of 83, the
five others differing by 10-64 meV/atom because MP's hull has moved since the WBM release (the same
offset appears when the DFT energy is placed on it, so it is the reference hull, not this entry
construction). One structure of 84 could not be placed at all: see `IncompleteHullError`.
"""

from __future__ import annotations

import copy
import logging

from pymatgen.analysis.compatibility import MaterialsProject2020Compatibility
from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.core import Composition, Structure
from pymatgen.entries.computed_entries import ComputedStructureEntry

log = logging.getLogger(__name__)

COMPETITOR_WINDOW = 0.1  # eV/atom
# MP's API potcar_spec lacks summary stats, which pymatgen's POTCAR check needs; the prefetch
# diagnostic (logs/stability_prefetch.log) records how many entries each setting keeps.
CHECK_POTCAR = False


class IncompleteHullError(RuntimeError):
    """The MP GGA/GGA+U reference hull for this chemistry cannot be built.

    A convex hull needs an entry at every elemental corner of the chemical system. Some elements have
    no GGA/GGA+U thermo document at all in the Materials Project API this harness reads (Yb is the one
    in our calibration chemistries — 3.0 % of the WBM calibration set), so no hull distance can be
    computed for any compound containing them. The product refuses such a candidate rather than
    placing it on a hull that is missing a corner.
    """


def material_id(entry) -> str:
    """Canonical (new-format) MP id of an entry.

    MP entries carry entry_id = EntryID(identifier='mp-aaaaaprp', suffix='GGA') — a dict after the
    JSON cache round-trip — while entry.data['material_id'] still holds the LEGACY id (e.g.
    'mp-10597'). Pair/target ids are new-format, so the entry_id identifier must win.
    """
    eid = entry.entry_id
    if isinstance(eid, dict) and eid.get("identifier"):
        return str(eid["identifier"])
    if getattr(eid, "identifier", None):
        return str(eid.identifier)
    eid = str(eid) if eid is not None else ""
    if eid.startswith("mace:"):
        return str(entry.data.get("material_id") or eid)
    for suffix in ("-GGA+U", "-GGA", "-R2SCAN", "-r2SCAN"):
        if eid.endswith(suffix):
            return eid[: -len(suffix)]
    return eid or str(entry.data.get("material_id"))


def chemsys_of(formula: str) -> str:
    return "-".join(sorted(e.symbol for e in Composition(formula).elements))


def _compat() -> MaterialsProject2020Compatibility:
    return MaterialsProject2020Compatibility(check_potcar=CHECK_POTCAR)


def process(entries: list) -> list:
    """Strip existing corrections and re-apply MP2020 to every entry, identically."""
    return _compat().process_entries(copy.deepcopy(entries), clean=True, inplace=True)


def mace_entry(mp_entry, structure, energy_per_atom: float, label: str) -> ComputedStructureEntry:
    """An engine-energy entry that inherits the MP entry's calculation parameters for corrections.

    For a material Materials Project has computed: the correction then sees exactly the run type, U
    values and (where present) oxide type MP itself used. `product_entry` is the version for a
    composition MP has not computed.
    """
    keep = {k: v for k, v in mp_entry.data.items() if k in ("oxide_type", "oxidation_states", "run_type")}
    return ComputedStructureEntry(
        structure, energy_per_atom * len(structure), parameters=copy.deepcopy(mp_entry.parameters),
        data={**keep, "material_id": material_id(mp_entry), "source": "mace"}, entry_id=f"mace:{label}")


def product_parameters(composition: Composition) -> dict:
    """VASP calculation parameters MP2020 accepts for this chemistry, derived from the chemistry alone.

    MaterialsProject2020Compatibility rejects an entry whose Hubbard U on any element differs from the
    value it expects for that composition's most electronegative element, so the expected values are
    read from the correction scheme's own `u_settings` table rather than restated here. A chemistry
    with any non-zero expected U is a GGA+U calculation, which is the same rule as
    `mp_data.mp2020_run_type` (O/F compounds of Co, Cr, Fe, Mn, Mo, Ni, V, W).
    """
    els = [el for el in composition.elements if composition[el] > 0]
    most_electronegative = sorted(els, key=lambda el: el.X)[-1].symbol
    expected = _compat().u_settings.get(most_electronegative, {})
    hubbards = {el.symbol: float(expected.get(el.symbol, 0)) for el in els}
    is_hubbard = any(u != 0 for u in hubbards.values())
    return {"run_type": "GGA+U" if is_hubbard else "GGA", "is_hubbard": is_hubbard,
            "hubbards": hubbards if is_hubbard else None, "potcar_spec": []}


def product_entry(structure: Structure, energy_per_atom: float, label: str) -> ComputedStructureEntry:
    """An engine-energy entry for a candidate Materials Project may never have computed.

    `data` is deliberately left empty: MP2020 then derives the oxide / sulfide type from this very
    structure and guesses oxidation states from this very composition, instead of inheriting another
    material's values. Verified on WBM: the corrections this produces are identical to the ones
    Matbench Discovery applied to the same compositions.
    """
    return ComputedStructureEntry(structure, energy_per_atom * len(structure),
                                  parameters=product_parameters(structure.composition),
                                  data={"source": "harness-product"}, entry_id=f"pred:{label}")


def signed_hull_energy(competitors: list, target) -> float:
    """Target energy relative to the hull of `competitors` (negative = below it)."""
    pd_ = PhaseDiagram(competitors)
    _, e = pd_.get_decomp_and_e_above_hull(target, allow_negative=True)
    return float(e)


def window_phases(processed: list, window: float = COMPETITOR_WINDOW) -> list:
    pd_ = PhaseDiagram(processed)
    return [e for e in processed if pd_.get_e_above_hull(e) <= window + 1e-9]


def mp_competitors(chemsys: str, elements=None) -> list:
    """MP2020-processed GGA/GGA+U entries for a chemical system, refusing an incomplete hull.

    Raises IncompleteHullError when any element of the system has no elemental entry: the hull then
    has no corner there and every decomposition through it is undefined.
    """
    from harness import mp_data

    processed = process(mp_data.entries_in_chemsys(chemsys))
    wanted = {str(e) for e in (elements if elements is not None else chemsys.split("-"))}
    terminals = {e.composition.elements[0].symbol for e in processed if len(e.composition.elements) == 1}
    missing = sorted(wanted - terminals)
    if missing:
        raise IncompleteHullError(
            f"no Materials Project GGA/GGA+U reference for {', '.join(missing)}, so the hull of "
            f"{chemsys} has no corner there")
    return processed


def e_above_hull_mode_a(structure: Structure, energy_per_atom: float, label: str = "candidate") -> dict:
    """Mode (a) hull distance of an engine result: engine energy vs the MP DFT hull of its chemistry.

    Returns the signed distance (negative = below the MP hull), the clamped `e_above_hull`, and what
    the hull was built from. Raises IncompleteHullError (missing corner) or ValueError (pymatgen could
    not decompose the composition) — both are refusals, never a number.
    """
    comp = structure.composition
    chemsys = "-".join(sorted(e.symbol for e in comp.elements))
    competitors = mp_competitors(chemsys, [e.symbol for e in comp.elements])
    corrected = process([product_entry(structure, energy_per_atom, label)])
    if not corrected:
        raise ValueError("MaterialsProject2020Compatibility rejected the candidate entry")
    entry = corrected[0]
    signed = signed_hull_energy(competitors, entry)
    return {"signed": signed, "e_above_hull": max(signed, 0.0), "chemsys": chemsys,
            "n_mp_entries": len(competitors),
            "mp2020_corrections": {a.name: float(a.value) for a in entry.energy_adjustments},
            "construction": "mode (a): engine energy on the MP GGA/GGA+U hull, MP2020 corrections"}
