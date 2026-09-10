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
