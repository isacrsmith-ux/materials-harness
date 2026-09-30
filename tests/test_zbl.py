"""harness.zbl: the pairwise ZBL correction. Model-free: a Morse potential stands in for the engine."""

import numpy as np
import pytest
from ase import Atoms
from ase.build import bulk
from ase.calculators.morse import MorsePotential

from harness import zbl


def engine():
    return MorsePotential(epsilon=0.3, r0=2.8, rho0=4.0, rcut1=4.0, rcut2=5.0)


@pytest.fixture(scope="module")
def calc():
    return zbl.corrected(engine(), ["Al"])


def dimer_energy(c, r):
    a = Atoms("Al2", positions=[[0, 0, 0], [0, 0, r]], cell=[20] * 3, pbc=True)
    a.calc = c
    return a.get_potential_energy()


def test_universal_derivative_matches_finite_difference():
    r, h = np.linspace(0.2, 3.0, 30), 1e-6
    _, d = zbl.universal_with_derivative(13, 8, r)
    fd = (zbl.universal(13, 8, r + h) - zbl.universal(13, 8, r - h)) / (2 * h)
    assert np.allclose(d, fd, rtol=1e-6)


def test_switch_is_one_then_zero_and_its_derivative_is_right():
    s, _ = zbl.switch(np.array([0.1, 1.0, 2.0, 3.0]), 1.0, 2.0)
    assert s.tolist() == [1.0, 1.0, 0.0, 0.0]
    r, h = np.linspace(1.05, 1.95, 19), 1e-6
    _, ds = zbl.switch(r, 1.0, 2.0)
    fd = (zbl.switch(r + h, 1.0, 2.0)[0] - zbl.switch(r - h, 1.0, 2.0)[0]) / (2 * h)
    assert np.allclose(ds, fd, atol=1e-6)


def test_dimer_is_zbl_inside_r_a_and_the_engine_outside_r_b(calc):
    r_a, r_b = zbl.switch_range(13, 13)
    bare = engine()
    for r in np.linspace(0.1, r_a - 0.01, 8):
        assert dimer_energy(calc, r) == pytest.approx(float(zbl.universal(13, 13, r)), rel=1e-6)
    for r in (r_b + 0.01, r_b + 0.5, 2.8):
        assert dimer_energy(calc, r) == pytest.approx(dimer_energy(bare, r), abs=1e-9)


def close_pair_cell():
    a = bulk("Al", "fcc", a=4.05, cubic=True).repeat((2, 2, 2))
    a.positions[1] = a.positions[0] + [0.9, 0.3, 0.2]  # one pair deep in the switching range
    a.rattle(0.05, seed=3)
    return a


def test_forces_match_finite_differences(calc):
    a = close_pair_cell()
    a.calc = calc
    f = a.get_forces()
    h = 1e-5
    for idx in (0, 1, 5):
        for k in range(3):
            p = a.copy(); p.calc = calc; p.positions[idx, k] += h
            m = a.copy(); m.calc = calc; m.positions[idx, k] -= h
            fd = -(p.get_potential_energy() - m.get_potential_energy()) / (2 * h)
            assert f[idx, k] == pytest.approx(fd, rel=1e-4, abs=1e-4)


def test_stress_matches_finite_difference_strain(calc):
    a = close_pair_cell()
    a.calc = calc
    s = a.get_stress(voigt=False)
    h, v = 1e-6, a.get_volume()
    for i, j in ((0, 0), (1, 1), (0, 1)):
        eps = np.zeros((3, 3)); eps[i, j] = eps[j, i] = h
        e = []
        for sign in (1, -1):
            b = a.copy(); b.calc = calc
            b.set_cell(a.cell @ (np.eye(3) + sign * eps), scale_atoms=True)
            e.append(b.get_potential_energy())
        fd = (e[0] - e[1]) / (2 * h) / v / (2 if i != j else 1)
        assert s[i, j] == pytest.approx(fd, rel=1e-4, abs=1e-6)


def test_no_correction_at_equilibrium(calc):
    a = bulk("Al", "fcc", a=4.05, cubic=True).repeat((2, 2, 2))
    a.calc = calc
    bare = a.copy(); bare.calc = engine()
    assert a.get_potential_energy() == pytest.approx(bare.get_potential_energy(), abs=1e-12)
