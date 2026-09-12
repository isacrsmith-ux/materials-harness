"""Physical-sanity guard: collapsed geometries are rejected, real short bonds are not."""

import numpy as np
from pymatgen.core import Lattice, Structure

from harness import compare
from harness.suites.stability import rejection_reason


def molecular_crystal(el, bond, box=6.0):
    return Structure(Lattice.cubic(box), [el, el], [[0, 0, 0], [bond, 0, 0]], coords_are_cartesian=True)


def test_real_short_bonds_pass():
    for el, bond in [("N", 1.10), ("O", 1.21), ("C", 1.20), ("H", 0.74)]:
        s = molecular_crystal(el, bond)
        assert not compare.is_unphysical(s), (el, compare.min_distance_ratio(s))


def test_collapsed_pair_is_rejected():
    s = molecular_crystal("O", 0.067)  # the geometry MACE produced for solid O2 (mp-aaaaatej)
    assert compare.min_distance_ratio(s) < 0.1
    assert compare.is_unphysical(s)


def test_periodic_images_count():
    s = Structure(Lattice.cubic(0.3), ["Si"], [[0, 0, 0]])  # atom 0.3 Å from its own image
    assert compare.is_unphysical(s)


def test_rejection_reason():
    ok = molecular_crystal("N", 1.10)
    assert rejection_reason({"converged": True, "relaxed": ok}) is None
    assert rejection_reason({"converged": False, "relaxed": ok}) == "not converged"
    bad = molecular_crystal("O", 0.067)
    assert rejection_reason({"converged": True, "relaxed": bad}).startswith("unphysical")
    assert rejection_reason({"converged": True, "relaxed": ok, "min_distance_ratio": float(np.nan)}) is None


# --- absolute energy plausibility (the AlN->AlSb class of failure) --------------------------------

def test_plausible_energies_pass():
    ok = molecular_crystal("N", 1.10)
    for e in (-13.3, -6.0, -0.04):
        assert rejection_reason({"converged": True, "relaxed": ok, "energy_per_atom": e}) is None, e


def test_energy_outside_the_physical_window_is_rejected():
    """AlN->AlSb [mp-aaaaaazl>mp-aaacfybs]: converged in 68 steps, |stress| 0.0096 GPa, min d/r_cov
    0.514 (above the collapse cut) and E = -1131 eV/atom. Convergence and geometry cannot catch it."""
    ok = molecular_crystal("N", 1.10)
    why = rejection_reason({"converged": True, "relaxed": ok, "min_distance_ratio": 0.514,
                            "n_steps": 68, "max_stress_gpa": 0.0096, "energy_per_atom": -1131.0124})
    assert why and "implausible energy" in why
    for e in (-25.6, -23.8, -1e16, 1e6):
        assert "implausible energy" in rejection_reason(
            {"converged": True, "relaxed": ok, "energy_per_atom": e})


def test_energy_far_from_the_dft_reference_is_rejected():
    ok = molecular_crystal("N", 1.10)
    # inside the absolute window but 8 eV/atom from DFT
    why = rejection_reason({"converged": True, "relaxed": ok, "energy_per_atom": -12.0, "e_dft": -4.0})
    assert why and "from the DFT reference" in why
    # the largest legitimate deviation in the whole results table is 3.90 eV/atom — it must survive
    assert rejection_reason({"converged": True, "relaxed": ok, "energy_per_atom": -6.857,
                             "e_dft": -2.958}) is None
    # substitution payloads carry the deviation in meV, not the reference
    assert "from the DFT reference" in rejection_reason(
        {"converged": True, "relaxed": ok, "energy_per_atom": -12.0, "energy_mev_vs_mp": -8000.0})


def test_energy_rule_applies_under_every_suite_key_name():
    ok = molecular_crystal("N", 1.10)
    for key in ("energy_per_atom", "e_mace"):
        assert "implausible energy" in rejection_reason({"converged": True, "relaxed": ok, key: -1131.0})


def test_recheck_keeps_the_stored_reason_and_adds_the_energy_rule():
    assert compare.recheck("not converged", {"energy_per_atom": -6.0}) == "not converged"
    assert compare.recheck(None, {"energy_per_atom": -6.0}) is None
    assert "implausible energy" in compare.recheck(None, {"e_mace": -23.8})


def test_one_shared_rejection_rule():
    """Every suite must reach the same function object, not its own copy of the rule."""
    from harness.suites import stability

    assert stability.rejection_reason is compare.rejection_reason
