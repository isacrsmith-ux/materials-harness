"""Pure substitution / comparison math. Unit-tested in tests/test_compare.py."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pymatgen.core import Element, Structure

# 3d, 4d, 5d transition metals (group 3-12) and f-block elements.
TRANSITION_METALS = frozenset(
    ["Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
     "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
     "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg"]
)
F_ELECTRON = frozenset(e.symbol for e in Element if e.is_lanthanoid or e.is_actinoid)
# Transition metals that MP typically runs spin-polarized with +U / nonzero moments.
MAGNETIC_PRONE = frozenset(["V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Mo", "W"])

SYMPREC = 0.1  # for conventional-cell lattice parameters; same for simulated and reference


def substitute(structure: Structure, mapping: dict[str, str]) -> Structure:
    """Replace species per `mapping` (e.g. {"Si": "Ge"}), keeping positions and cell."""
    missing = set(mapping) - {el.symbol for el in structure.composition.elements}
    if missing:
        raise ValueError(f"Cannot substitute {sorted(missing)}: not present in {structure.composition.reduced_formula}")
    out = structure.copy()
    out.replace_species({k: v for k, v in mapping.items()})
    for prop in list(out.site_properties):
        out.remove_site_property(prop)
    return out


def perturb(structure: Structure, seed: int, rattle_angstrom: float = 0.03, strain: float = 0.01,
            supercell=(2, 2, 2)) -> Structure:
    """Deterministically break symmetry: supercell (so zone-boundary distortions such as
    octahedral tilts are representable), random symmetric cell strain, Gaussian atom rattle."""
    rng = np.random.default_rng(seed)
    s = structure.copy()
    s.make_supercell(list(supercell))
    eps = rng.normal(0.0, strain, (3, 3))
    eps = (eps + eps.T) / 2
    lattice = s.lattice.matrix @ (np.eye(3) + eps)
    cart = s.frac_coords @ lattice + rng.normal(0.0, rattle_angstrom, (len(s), 3))
    return Structure(lattice, s.species, cart, coords_are_cartesian=True)


def stable_seed(text: str) -> int:
    """Seed derived from a label, stable across runs and Python processes (unlike hash())."""
    import hashlib

    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


# Physical-sanity guard. Real bonds sit at >= ~0.75 of the covalent-radius sum (N2 0.78, O2 0.91);
# a MACE relaxation that collapsed solid O2 reached 0.05 with E = -1.2e11 eV/atom. Anything below
# this ratio is treated as an unphysical (failed) relaxation, never as a result.
UNPHYSICAL_DISTANCE_RATIO = 0.5


def min_distance_ratio(structure: Structure, cutoff: float = 4.0) -> float:
    """min over atom pairs (incl. periodic images) of d_ij / (r_cov_i + r_cov_j)."""
    from pymatgen.analysis.molecule_structure_comparator import CovalentRadius

    radii = CovalentRadius.radius
    best = np.inf
    for i, neighbors in enumerate(structure.get_all_neighbors(cutoff)):
        ri = radii[structure[i].specie.symbol]
        for n in neighbors:
            best = min(best, n.nn_distance / (ri + radii[n.specie.symbol]))
    return float(best)


def is_unphysical(structure: Structure) -> bool:
    return min_distance_ratio(structure) < UNPHYSICAL_DISTANCE_RATIO


def volume_per_atom(structure: Structure) -> float:
    return structure.volume / len(structure)


def pct_error(simulated: float, reference: float) -> float:
    """Signed percent error: positive means the simulation is larger than the reference."""
    if reference == 0:
        raise ZeroDivisionError("reference value is zero")
    return (simulated - reference) / abs(reference) * 100.0


def lattice_constant_from_volume(vol_per_atom: float, atoms_per_conventional_cell: int) -> float:
    """Cubic lattice constant a = (V_atom * N_conv)^(1/3)."""
    return (vol_per_atom * atoms_per_conventional_cell) ** (1.0 / 3.0)


@dataclass
class ConventionalCell:
    crystal_system: str
    spacegroup: int
    a: float
    b: float
    c: float
    alpha: float
    beta: float
    gamma: float


def conventional_cell(structure: Structure, symprec: float = SYMPREC) -> ConventionalCell:
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    sga = SpacegroupAnalyzer(structure, symprec=symprec)
    conv = sga.get_conventional_standard_structure()
    a, b, c = conv.lattice.abc
    al, be, ga = conv.lattice.angles
    return ConventionalCell(sga.get_crystal_system(), sga.get_space_group_number(), a, b, c, al, be, ga)


def compare_lattices(sim: Structure, ref: Structure, symprec: float = SYMPREC) -> dict:
    """Conventional-cell a/b/c % errors when both cells share a space group; else volume only."""
    cs, cr = conventional_cell(sim, symprec), conventional_cell(ref, symprec)
    out = {
        "sim_spacegroup": cs.spacegroup,
        "ref_spacegroup": cr.spacegroup,
        "same_spacegroup": cs.spacegroup == cr.spacegroup,
        "vol_per_atom_sim": volume_per_atom(sim),
        "vol_per_atom_ref": volume_per_atom(ref),
    }
    out["vol_per_atom_pct_err"] = pct_error(out["vol_per_atom_sim"], out["vol_per_atom_ref"])
    if out["same_spacegroup"]:
        for p in ("a", "b", "c"):
            out[f"{p}_sim"], out[f"{p}_ref"] = getattr(cs, p), getattr(cr, p)
            out[f"{p}_pct_err"] = pct_error(getattr(cs, p), getattr(cr, p))
        out["max_abs_lattice_pct_err"] = max(abs(out[f"{p}_pct_err"]) for p in ("a", "b", "c"))
    else:
        out["max_abs_lattice_pct_err"] = None
    return out


def same_prototype(s1: Structure, s2: Structure) -> bool:
    """Anonymized StructureMatcher at pymatgen default tolerances (never loosened)."""
    from pymatgen.analysis.structure_matcher import StructureMatcher

    return bool(StructureMatcher().fit_anonymous(s1, s2))


def relaxed_into_target(relaxed: Structure, target: Structure, allow_supercell: bool = False) -> bool:
    """Species-aware StructureMatcher at default tolerances. allow_supercell only lets it compare
    a supercell with a primitive cell (needed for the rattled runs); tolerances are unchanged."""
    from pymatgen.analysis.structure_matcher import StructureMatcher

    return bool(StructureMatcher(attempt_supercell=allow_supercell).fit(relaxed, target))


def energy_diff_mev(sim_ev_per_atom: float, ref_ev_per_atom: float) -> float:
    return (sim_ev_per_atom - ref_ev_per_atom) * 1000.0


def system_flags(elements, mp_doc: dict | None = None) -> dict:
    """Flags for systems MACE-MP-0 can't treat faithfully (no explicit spin)."""
    els = {str(e) for e in elements}
    tm = sorted(els & TRANSITION_METALS)
    f = sorted(els & F_ELECTRON)
    magnetic = False
    if mp_doc is not None:
        ordering = (mp_doc.get("ordering") or "NM").upper()
        mag = mp_doc.get("total_magnetization_normalized_formula_units") or 0.0
        magnetic = bool(mp_doc.get("is_magnetic")) or ordering not in ("NM", "UNKNOWN") or abs(mag) > 0.05
    return {"transition_metal": bool(tm), "f_electron": bool(f), "magnetic": magnetic,
            "tm_elements": tm, "f_elements": f,
            "spin_caveat": magnetic or bool(f) or bool(els & MAGNETIC_PRONE)}


def mae(values) -> float:
    arr = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    return float(np.mean(np.abs(arr))) if arr.size else float("nan")


def classification_metrics(pred_stable, true_stable) -> dict:
    """Precision / recall / accuracy / F1 treating 'stable' as the positive class."""
    p = np.asarray(pred_stable, dtype=bool)
    t = np.asarray(true_stable, dtype=bool)
    tp, fp = int(np.sum(p & t)), int(np.sum(p & ~t))
    fn, tn = int(np.sum(~p & t)), int(np.sum(~p & ~t))
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    acc = (tp + tn) / len(p) if len(p) else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if tp else (0.0 if (tp + fp + fn) else float("nan"))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall,
            "accuracy": acc, "f1": f1, "n": len(p)}
