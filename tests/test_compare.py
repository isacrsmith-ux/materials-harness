"""Unit tests for substitution and comparison math (fast, no MACE, no network)."""

import math

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

from harness import compare


def diamond(el="Si", a=5.43):
    return Structure.from_spacegroup(227, Lattice.cubic(a), [el], [[0, 0, 0]])


def rocksalt(a="Na", b="Cl", lat=5.64):
    return Structure.from_spacegroup(225, Lattice.cubic(lat), [a, b], [[0, 0, 0], [0.5, 0.5, 0.5]])


def corundum():
    return Structure.from_spacegroup(167, Lattice.hexagonal(4.76, 12.99), ["Al", "O"],
                                     [[0, 0, 0.352], [0.306, 0, 0.25]])


# --- substitution ---------------------------------------------------------------------------

def test_substitute_replaces_all_sites_and_keeps_geometry():
    si = diamond()
    ge = compare.substitute(si, {"Si": "Ge"})
    assert ge.composition.reduced_formula == "Ge"
    assert len(ge) == len(si) == 8
    np.testing.assert_allclose(ge.lattice.matrix, si.lattice.matrix)
    np.testing.assert_allclose(ge.frac_coords, si.frac_coords)
    assert si.composition.reduced_formula == "Si"  # input untouched


def test_substitute_partial_mapping_keeps_other_species():
    al2o3 = corundum()
    ga2o3 = compare.substitute(al2o3, {"Al": "Ga"})
    assert ga2o3.composition.reduced_formula == "Ga2O3"
    assert ga2o3.composition["O"] == al2o3.composition["O"]


def test_substitute_simultaneous_swap_is_not_sequential():
    nacl = rocksalt()
    swapped = compare.substitute(nacl, {"Na": "Cl", "Cl": "Na"})
    assert swapped.composition == nacl.composition
    assert str(swapped[0].specie) == "Cl"


def test_substitute_rejects_absent_element():
    with pytest.raises(ValueError):
        compare.substitute(diamond(), {"Ge": "Sn"})


def test_perturb_is_deterministic_and_breaks_symmetry():
    s = diamond(a=5.43).get_primitive_structure()
    p1 = compare.perturb(s, seed=7)
    p2 = compare.perturb(s, seed=7)
    p3 = compare.perturb(s, seed=8)
    assert len(p1) == 8 * len(s)
    np.testing.assert_allclose(p1.cart_coords, p2.cart_coords)
    assert not np.allclose(p1.cart_coords, p3.cart_coords)
    assert p1.composition.reduced_formula == "Si"
    assert compare.conventional_cell(p1, symprec=1e-3).spacegroup < 227  # symmetry actually broken
    assert compare.relaxed_into_target(p1, s, allow_supercell=True)  # small enough to still match


def test_stable_seed_is_stable():
    assert compare.stable_seed("CaF2->SrF2") == compare.stable_seed("CaF2->SrF2")
    assert compare.stable_seed("a") != compare.stable_seed("b")


def test_settings_tag_changes_with_protocol():
    from harness.config import DEFAULT_RELAX, RelaxSettings, settings_tag

    base = settings_tag("cpu", "float64")
    assert base == settings_tag("cpu", "float64", DEFAULT_RELAX)
    assert base != settings_tag("cpu", "float32")
    assert base != settings_tag("cpu", "float64", RelaxSettings(max_stress_gpa=0.1))


# --- scalar math ----------------------------------------------------------------------------

def test_pct_error_sign_and_value():
    assert compare.pct_error(5.7, 5.658) == pytest.approx((5.7 - 5.658) / 5.658 * 100)
    assert compare.pct_error(99.0, 100.0) == pytest.approx(-1.0)
    with pytest.raises(ZeroDivisionError):
        compare.pct_error(1.0, 0.0)


def test_volume_per_atom_diamond():
    s = diamond(a=5.43)
    assert compare.volume_per_atom(s) == pytest.approx(5.43**3 / 8)


def test_lattice_constant_from_volume_roundtrip():
    v = 5.43**3 / 8
    assert compare.lattice_constant_from_volume(v, 8) == pytest.approx(5.43)


def test_energy_diff_mev():
    assert compare.energy_diff_mev(-4.50, -4.52) == pytest.approx(20.0)


def test_mae_ignores_none_and_nan():
    assert compare.mae([1.0, -3.0, None, float("nan")]) == pytest.approx(2.0)
    assert math.isnan(compare.mae([]))


# --- lattice comparison ---------------------------------------------------------------------

def test_conventional_cell_from_primitive():
    prim = diamond(a=5.43).get_primitive_structure()
    assert len(prim) == 2
    cell = compare.conventional_cell(prim)
    assert cell.spacegroup == 227 and cell.a == pytest.approx(5.43, abs=1e-6)


def test_compare_lattices_isotropic_strain():
    ref = diamond(a=5.43)
    sim = ref.copy()
    sim.scale_lattice(ref.volume * 1.01**3)  # +1 % on a
    cmp = compare.compare_lattices(sim.get_primitive_structure(), ref)
    assert cmp["same_spacegroup"]
    assert cmp["a_pct_err"] == pytest.approx(1.0, abs=1e-6)
    assert cmp["vol_per_atom_pct_err"] == pytest.approx((1.01**3 - 1) * 100, abs=1e-6)
    assert cmp["max_abs_lattice_pct_err"] == pytest.approx(1.0, abs=1e-6)


def test_compare_lattices_hexagonal_a_and_c():
    ref = corundum()
    sim = Structure(Lattice.hexagonal(4.76 * 1.02, 12.99 * 0.99), ref.species, ref.frac_coords)
    cmp = compare.compare_lattices(sim, ref)
    assert cmp["a_pct_err"] == pytest.approx(2.0, abs=1e-6)
    assert cmp["c_pct_err"] == pytest.approx(-1.0, abs=1e-6)


def test_compare_lattices_different_spacegroup_falls_back_to_volume():
    cmp = compare.compare_lattices(rocksalt(), diamond())
    assert not cmp["same_spacegroup"]
    assert cmp["max_abs_lattice_pct_err"] is None
    assert "vol_per_atom_pct_err" in cmp


# --- structure matching ---------------------------------------------------------------------

def test_same_prototype_anonymous():
    assert compare.same_prototype(diamond("Si", 5.43), diamond("Ge", 5.66))
    assert compare.same_prototype(rocksalt("Na", "Cl"), rocksalt("Mg", "O", 4.21))
    assert not compare.same_prototype(rocksalt(), diamond())


def test_relaxed_into_target_is_species_aware():
    assert compare.relaxed_into_target(diamond("Ge", 5.70), diamond("Ge", 5.66))
    assert not compare.relaxed_into_target(diamond("Si", 5.66), diamond("Ge", 5.66))


# --- flags and classification ---------------------------------------------------------------

def test_system_flags():
    f = compare.system_flags(["Fe", "O"], {"ordering": "FM", "total_magnetization_normalized_formula_units": 4.0})
    assert f["transition_metal"] and f["magnetic"] and f["spin_caveat"] and not f["f_electron"]
    g = compare.system_flags(["Ce", "O"], {"ordering": "NM", "total_magnetization_normalized_formula_units": 0.0})
    assert g["f_electron"] and not g["magnetic"] and g["spin_caveat"]
    h = compare.system_flags(["Si"])
    assert not any(h[k] for k in ("transition_metal", "f_electron", "magnetic", "spin_caveat"))


def test_classification_metrics():
    m = compare.classification_metrics([True, True, False, False], [True, False, True, False])
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 1)
    assert m["precision"] == m["recall"] == m["accuracy"] == pytest.approx(0.5)
    m2 = compare.classification_metrics([False, False], [False, False])
    assert math.isnan(m2["precision"]) and m2["accuracy"] == 1.0
