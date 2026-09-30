"""Aerospace-durability Phase 0: can the harness's engines compute anything relevant to atomic-oxygen
erosion and radiation damage? Static test cases with published answers, one engine per process:

    HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/aerospace_phase0.py
    HARNESS_MODEL=mace-mp-0-medium  .venv/bin/python scripts/aerospace_phase0.py

Writes reports/aerospace_phase0/<engine>.json (computed values only). Reference values and their
provenance live in reports/aerospace_durability_feasibility.md, not here, so nothing in this file is a
literature number except the ZBL constants, read from docs.lammps.org/pair_zbl.html on 2026-09-29.

Every relaxation uses the harness's own engine loader and fmax (config.DEFAULT_RELAX.fmax).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from ase import Atoms, units
from ase.build import add_adsorbate, bulk, fcc111
from ase.constraints import FixAtoms
from ase.filters import FrechetCellFilter
from ase.optimize import BFGS

from harness import config
from harness.engine import get_calculator
from harness.zbl import universal

FMAX = config.DEFAULT_RELAX.fmax
MAX_STEPS = 2000
OUT = config.ROOT / "reports" / "aerospace_phase0"
CALC = None


def energy(atoms: Atoms, relax: str | None = None) -> tuple[float, dict]:
    """relax: None (single point), 'pos' (positions, fixed cell), 'cell' (positions + cell)."""
    atoms.calc = CALC
    info = {"n_atoms": len(atoms)}
    if relax:
        target = FrechetCellFilter(atoms) if relax == "cell" else atoms
        opt = BFGS(target, logfile=None)
        converged = opt.run(fmax=FMAX, steps=MAX_STEPS)
        info |= {"steps": opt.nsteps, "converged": bool(converged)}
    info["fmax_final"] = float(np.abs(atoms.get_forces()).max()) if len(atoms) > 1 else 0.0
    return float(atoms.get_potential_energy()), info


def al_defects() -> dict:
    """Vacancy and self-interstitial (<100> dumbbell, octahedral, tetrahedral) formation energies in fcc
    Al for n x n x n conventional supercells, both at the relaxed-bulk cell ('fixed_cell') and with the
    defect cell relaxed to zero pressure ('zero_pressure', the protocol of arXiv:1210.5489 Table I).
    Size convergence is part of the answer. Interstitials start on their ideal symmetric sites; BFGS
    keeps the symmetry, so 'drift' reports whether the site is even a saddle rather than a minimum."""
    prim = bulk("Al", "fcc", cubic=True)
    energy(prim, "cell")
    a0 = float(prim.cell.lengths()[0])
    out = {"a0_angstrom": a0, "by_mode": {}}
    for mode, relax in (("fixed_cell", "pos"), ("zero_pressure", "cell")):
        by_size = out["by_mode"][mode] = {}
        for n in (3, 4, 5, 6):
            sc = prim.repeat((n, n, n))
            e_bulk, _ = energy(sc.copy())
            N = len(sc)
            row = {"N": N}
            centre = int(np.argmin(np.linalg.norm(sc.positions - a0, axis=1)))  # lattice site at (a0, a0, a0)
            vac = sc.copy()
            del vac[centre]
            e, info = energy(vac, relax)
            row["vacancy"] = {"E_f_eV": e - (N - 1) / N * e_bulk, **info}
            # octahedral: cube-edge midpoint of the conventional cell; tetrahedral: (1/4,1/4,1/4)
            for name, frac in (("octahedral", (0.5, 0, 0)), ("tetrahedral", (0.25, 0.25, 0.25))):
                s = sc.copy()
                site = np.array(frac) * a0 + a0  # inside the supercell, away from the boundary
                s.append("Al")
                s.positions[-1] = site
                e, info = energy(s, relax)
                drift = float(np.linalg.norm(s.get_scaled_positions()[-1] @ sc.cell - site)) if relax == "cell" else \
                    float(np.linalg.norm(s.positions[-1] - site))
                row[name] = {"E_f_eV": e - (N + 1) / N * e_bulk, "interstitial_drift_angstrom": drift, **info}
            # <100> dumbbell: the lattice atom at (a0,a0,a0) replaced by a pair split along x
            s = sc.copy()
            s.positions[centre] = [a0 * 0.7, a0, a0]
            s.append("Al")
            s.positions[-1] = [a0 * 1.3, a0, a0]
            e, info = energy(s, relax)
            axis = s.get_distance(centre, len(s) - 1, mic=True, vector=True)
            row["dumbbell_100"] = {"E_f_eV": e - (N + 1) / N * e_bulk,
                                   "pair_separation_angstrom": float(np.linalg.norm(axis)),
                                   "pair_off_axis_angstrom": float(np.linalg.norm(axis[1:])), **info}
            by_size[str(N)] = row
    return out


def ag_oxygen() -> dict:
    """O at 0.25 ML on Ag(111): on-surface fcc hollow vs sub-surface octahedral, set up as in
    arXiv:cond-mat/0302122 (5-layer slab, 15 Å vacuum, O on one side, top three layers relaxed)."""
    prim = bulk("Ag", "fcc", cubic=True)
    energy(prim, "cell")
    a0 = float(prim.cell.lengths()[0])

    def slab():
        s = fcc111("Ag", size=(2, 2, 5), a=a0, vacuum=7.5)
        z = s.positions[:, 2]
        layers = np.unique(np.round(z, 3))
        s.set_constraint(FixAtoms(mask=z < layers[2] - 0.1))  # bottom two layers fixed
        return s, layers

    clean, layers = slab()
    e_clean, info_clean = energy(clean, "pos")
    d12 = float(layers[-1] - layers[-2])
    res = {"a0_angstrom": a0, "clean_slab": info_clean}
    for name, height in (("fcc_hollow", 1.2), ("subsurface_octa", -d12 / 2)):
        s, _ = slab()
        add_adsorbate(s, "O", height, "fcc")
        o = len(s) - 1
        start = s.positions[o].copy()
        n_nn = int((s.get_distances(o, range(o), mic=True) < 2.6).sum())
        e, info = energy(s, "pos")
        d = s.get_distances(o, range(o), mic=True)
        res[name] = {"E_total_eV": e, "start_neighbours_lt_2.6A": n_nn,
                     "final_neighbours_lt_2.6A": int((d < 2.6).sum()),
                     "o_displacement_angstrom": float(np.linalg.norm(s.positions[o] - start)),
                     "o_height_above_top_layer_angstrom": float(s.positions[o, 2] - layers[-1]), **info}
        res[name]["E_ad_vs_free_O_eV"] = None  # filled below
    e_o, _ = energy(Atoms("O", positions=[[0, 0, 0]], cell=[15, 15, 15], pbc=True))
    o2 = Atoms("O2", positions=[[0, 0, 0], [0, 0, 1.25]], cell=[15, 15, 15], pbc=True)
    e_o2, info_o2 = energy(o2, "pos")
    for name in ("fcc_hollow", "subsurface_octa"):
        res[name]["E_ad_vs_free_O_eV"] = -(res[name]["E_total_eV"] - e_clean - e_o)
    res["free_O_atom_eV"] = e_o
    res["O2"] = {"E_eV": e_o2, "bond_angstrom": float(o2.get_distance(0, 1)),
                 "binding_per_O_eV": e_o - e_o2 / 2, **info_o2}
    res["fcc_minus_octa_E_ad_eV"] = res["fcc_hollow"]["E_ad_vs_free_O_eV"] - res["subsurface_octa"]["E_ad_vs_free_O_eV"]
    return res


zbl = universal  # ZBL universal screened nuclear repulsion (LAMMPS pair_zbl constants), harness.zbl


def dimers() -> dict:
    """E(r) - E(two isolated atoms) for close-approach pairs, next to ZBL. MLIPs are fitted near
    equilibrium; this measures what they do where cascades and hyperthermal O impacts go."""
    r = np.round(np.concatenate([np.arange(0.2, 1.0, 0.1), np.arange(1.0, 3.01, 0.25)]), 3)
    Z = {"Al": 13, "O": 8, "Ag": 47}
    iso = {el: energy(Atoms(el, positions=[[0, 0, 0]], cell=[20, 20, 20], pbc=True))[0] for el in Z}
    out = {}
    for a, b in (("Al", "Al"), ("Al", "O"), ("Ag", "O"), ("Ag", "Ag")):
        e = []
        for d in r:
            at = Atoms(a + b, positions=[[0, 0, 0], [0, 0, d]], cell=[20, 20, 20], pbc=True)
            e.append(energy(at)[0] - iso[a] - iso[b])
        e = np.array(e)
        out[f"{a}-{b}"] = {"r_angstrom": r.tolist(), "E_mlip_eV": e.tolist(), "E_zbl_eV": zbl(Z[a], Z[b], r).tolist(),
                           "mlip_monotonic_repulsive_below_1A": bool(np.all(np.diff(e[r <= 1.0]) < 0))}
    return out


def main() -> None:
    global CALC
    compute = config.load_compute_config()
    CALC = get_calculator(compute["device"], compute["dtype"])
    t = time.time()
    res = {"engine": config.MODEL["key"], "checkpoint_sha256": config.MODEL["sha256"],
           "device": compute["device"], "dtype": compute["dtype"], "fmax_eV_per_A": FMAX,
           "al_defects": al_defects(), "ag_oxygen": ag_oxygen(), "dimers": dimers()}
    res["wall_s"] = round(time.time() - t, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{config.MODEL['key']}.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in ("engine", "wall_s")}))


if __name__ == "__main__":
    main()
