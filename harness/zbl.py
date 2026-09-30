"""Short-range ZBL correction for an MLIP (aerospace track, Stage 1 of reports/aerospace_md_scoping.md).

Not used by the product (`harness.predict`) or any validation suite; nothing here changes a settings tag.

The engine's short-range energy is replaced, pair by pair, with the universal ZBL screened repulsion:

    E = E_engine + sum_{pairs i<j} S(r_ij) * [ZBL(r_ij) - V_engine(r_ij)]

V_engine is the engine's own isolated-dimer curve for that species pair, E(dimer at r) - E(atom) - E(atom),
tabulated once at construction. For an isolated dimer the result is exactly ZBL wherever S = 1, and the
engine untouched wherever S = 0. In a condensed phase the subtraction is dimer-level only: the engine's
many-body energy of a close pair is not exactly V_engine(r). That is the known ceiling of a pairwise
correction (option A); the per-atom blend (option B) or fine-tuning (option C) remove it.

S is 1 below R_a and 0 above R_b, joined by the C2 polynomial -6u^5 + 15u^4 - 10u^3 + 1 (arXiv:1904.00360
eq. 4), with R_a, R_b scaled per species pair by the sum of covalent radii (FRAC_A, FRAC_B), so an O-O pair
switches off well before the O2 bond while a heavy-metal pair switches later.

ZBL constants: docs.lammps.org/pair_zbl.html, read 2026-09-29 (reports/aerospace_durability_feasibility.md).
"""

from __future__ import annotations

from itertools import combinations_with_replacement

import numpy as np
from ase import Atoms, units
from ase.calculators.calculator import Calculator, all_changes
from ase.data import atomic_numbers, covalent_radii
from ase.neighborlist import neighbor_list
from scipy.interpolate import CubicSpline

# Switching range as fractions of r_cov,i + r_cov,j. Calibration knobs, not physics: chosen so no pair in
# any Phase 0 / Phase 2 relaxed structure lies inside R_b (checked by scripts/aerospace_stage1.py).
FRAC_A = 0.40
FRAC_B = 0.70
TABLE_R_MIN = 0.05  # Å; below this the engine's dimer curve is held at its last tabulated value
TABLE_STEP = 0.005  # Å
_K = units._e / (4 * np.pi * units._eps0) * 1e10  # e^2 / (4 pi eps0) in eV·Å
_C = np.array([0.18175, 0.50986, 0.28022, 0.02817])
_B = np.array([3.19980, 0.94229, 0.40290, 0.20162])


def universal(z1: int, z2: int, r):
    """ZBL pair energy (eV) at distance r (Å)."""
    return universal_with_derivative(z1, z2, r)[0]


def universal_with_derivative(z1: int, z2: int, r):
    r = np.asarray(r, dtype=float)
    a = 0.46850 / (z1 ** 0.23 + z2 ** 0.23)
    e = np.exp(-np.multiply.outer(r / a, _B))  # (..., 4)
    phi, dphi = e @ _C, -(e * _B) @ _C / a
    pre = _K * z1 * z2
    return pre * phi / r, pre * (dphi / r - phi / r ** 2)


def switch(r, r_a: float, r_b: float):
    """S(r) and dS/dr: 1 below r_a, 0 above r_b, C2-smooth in between."""
    r = np.asarray(r, dtype=float)
    u = np.clip((r - r_a) / (r_b - r_a), 0.0, 1.0)
    s = -6 * u ** 5 + 15 * u ** 4 - 10 * u ** 3 + 1
    ds = (-30 * u ** 4 + 60 * u ** 3 - 30 * u ** 2) / (r_b - r_a)
    return s, np.where((u > 0) & (u < 1), ds, 0.0)


def switch_range(z1: int, z2: int) -> tuple[float, float]:
    rc = covalent_radii[z1] + covalent_radii[z2]
    return FRAC_A * rc, FRAC_B * rc


class ZBLCorrection(Calculator):
    """The correction term alone. Use `corrected(engine, elements)` for engine + correction."""

    implemented_properties = ["energy", "free_energy", "forces", "stress"]

    def __init__(self, engine: Calculator, elements, **kw):
        super().__init__(**kw)
        zs = sorted({atomic_numbers[e] if isinstance(e, str) else int(e) for e in elements})
        self.tables = {}
        iso = {z: _single_point(engine, Atoms(numbers=[z], positions=[[0, 0, 0]], cell=[20] * 3, pbc=True)) for z in zs}
        for z1, z2 in combinations_with_replacement(zs, 2):
            r_a, r_b = switch_range(z1, z2)
            r = np.arange(TABLE_R_MIN, r_b + 10 * TABLE_STEP, TABLE_STEP)
            v = np.array([_single_point(engine, Atoms(numbers=[z1, z2], positions=[[0, 0, 0], [0, 0, d]],
                                                      cell=[20] * 3, pbc=True)) for d in r]) - iso[z1] - iso[z2]
            if not np.all(np.isfinite(v)):
                raise ValueError(f"engine dimer curve for Z={z1},{z2} is not finite on [{r[0]}, {r[-1]}] Å")
            self.tables[(z1, z2)] = (r_a, r_b, CubicSpline(r, v))
        self.r_cut = max(t[1] for t in self.tables.values())

    def pair_energy(self, z1: int, z2: int, r):
        """S * (ZBL - V_engine) and its r-derivative, for one species pair."""
        r_a, r_b, spl = self.tables[tuple(sorted((z1, z2)))]
        rr = np.maximum(r, spl.x[0])
        v, dv = spl(rr), np.where(r > spl.x[0], spl(rr, 1), 0.0)
        z, dz = universal_with_derivative(z1, z2, r)
        s, ds = switch(r, r_a, r_b)
        return s * (z - v), ds * (z - v) + s * (dz - dv)

    def calculate(self, atoms=None, properties=("energy",), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        n = len(self.atoms)
        i, j, d, D = neighbor_list("ijdD", self.atoms, self.r_cut)
        zn = self.atoms.numbers
        e_pair, de = np.zeros(len(i)), np.zeros(len(i))
        lo, hi = np.minimum(zn[i], zn[j]), np.maximum(zn[i], zn[j])
        for z1, z2 in {(int(a), int(b)) for a, b in zip(lo, hi)}:
            m = (lo == z1) & (hi == z2)
            e_pair[m], de[m] = self.pair_energy(z1, z2, d[m])
        # the full neighbour list counts each pair twice
        energy = 0.5 * e_pair.sum()
        f_vec = (0.5 * de / np.where(d > 0, d, 1.0))[:, None] * D  # dE/dr_ij along the bond, per ordered pair
        forces = np.zeros((n, 3))
        np.add.at(forces, i, f_vec)
        np.add.at(forces, j, -f_vec)
        self.results["energy"] = self.results["free_energy"] = float(energy)
        self.results["forces"] = forces
        if self.atoms.cell.rank == 3:
            virial = -np.einsum("pa,pb->ab", f_vec, D)
            s = -virial / self.atoms.get_volume()
            self.results["stress"] = np.array([s[0, 0], s[1, 1], s[2, 2], s[1, 2], s[0, 2], s[0, 1]])
        else:
            self.results["stress"] = np.zeros(6)


def corrected(engine: Calculator, elements):
    """engine + ZBL correction, as one ASE calculator."""
    from ase.calculators.mixing import SumCalculator
    return SumCalculator([engine, ZBLCorrection(engine, elements)])


def _single_point(calc, atoms) -> float:
    atoms.calc = calc
    return float(atoms.get_potential_energy())
