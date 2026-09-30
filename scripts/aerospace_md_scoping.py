"""Measurements behind reports/aerospace_md_scoping.md (the scoping of an MD tool with a ZBL-corrected
potential). Nothing is built here; this only measures what the scoping document states:

  1. which engine checkpoints already carry MACE's built-in ZBL term (`pair_repulsion`), and its
     constants as stored in the checkpoint;
  2. MPA-0's Phase 0 dimer energies split into that built-in ZBL term and the learned remainder, next to
     the universal ZBL (constants from docs.lammps.org/pair_zbl.html, via scripts/aerospace_phase0.zbl);
  3. the energy of an O atom at the orbital speed stated in NTRS 19890003221 (p. 1) and the head-on
     closest approach it reaches on Al and Ag;
  4. MPA-0 force-call time and peak memory on CPU for Al supercells.

    HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/aerospace_md_scoping.py

Writes reports/aerospace_md_scoping.json.
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time
import warnings

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from aerospace_phase0 import zbl  # noqa: E402  (universal ZBL, LAMMPS constants)

from harness import config  # noqa: E402

OUT = config.ROOT / "reports" / "aerospace_md_scoping.json"
PAIRS = {"Al-Al": (13, 13), "Al-O": (13, 8), "Ag-O": (47, 8), "Ag-Ag": (47, 47)}
R_SHOW = (0.3, 0.5, 0.8, 1.0, 1.25)
ORBITAL_SPEED_M_S = 8000.0  # NTRS 19890003221, p. 1: "a spacecraft traveling at 8 km/sec"
BENCH_REPEATS = (5, 8, 10)  # conventional-cell repeats: 500, 2048, 4000 atoms (4000 peaks near 27 GB)


def checkpoint_zbl(key: str) -> dict:
    import torch
    warnings.filterwarnings("ignore")
    m = torch.load(str(config.model_path(key)), map_location="cpu", weights_only=False)
    if not getattr(m, "pair_repulsion", False):
        return {"pair_repulsion": False}
    z = m.pair_repulsion_fn
    return {"pair_repulsion": True, "c": [float(x) for x in z.c], "a_prefactor": float(z.a_prefactor),
            "a_exp": float(z.a_exp), "envelope_p": int(z.p)}


def mace_zbl(z1: int, z2: int, r: np.ndarray, k: dict) -> np.ndarray:
    """The checkpoint's own ZBL term, as mace.modules.radial.ZBLBasis computes it (pair energy)."""
    import torch
    from ase.data import covalent_radii
    from mace.modules.radial import PolynomialCutoff
    c = k["c"]
    a = k["a_prefactor"] * 0.529 / (z1 ** k["a_exp"] + z2 ** k["a_exp"])
    x = r / a
    phi = c[0] * np.exp(-3.2 * x) + c[1] * np.exp(-0.9423 * x) + c[2] * np.exp(-0.4028 * x) + c[3] * np.exp(-0.2016 * x)
    env = PolynomialCutoff.calculate_envelope(torch.tensor(r), torch.tensor(covalent_radii[z1] + covalent_radii[z2]),
                                              k["envelope_p"]).numpy()
    return 14.3996 * z1 * z2 / r * phi * env


def decomposition(k: dict) -> dict:
    ph0 = json.loads((config.ROOT / "reports" / "aerospace_phase0" / "mace-mpa-0-medium.json").read_text())["dimers"]
    out = {}
    for pair, (z1, z2) in PAIRS.items():
        r = np.array(ph0[pair]["r_angstrom"])
        tot = np.array(ph0[pair]["E_mlip_eV"])
        mz = mace_zbl(z1, z2, r, k)
        uz = zbl(z1, z2, r)
        out[pair] = [{"r": float(r[i]), "universal_zbl": float(uz[i]), "mace_zbl_term": float(mz[i]),
                      "model_total": float(tot[i]), "learned_part": float(tot[i] - mz[i]),
                      "universal_over_mace_zbl": float(uz[i] / mz[i]) if mz[i] > 0 else None}
                     for i in (int(np.argmin(abs(r - x))) for x in R_SHOW)]
    return out


def impact() -> dict:
    from ase import units
    from ase.data import atomic_masses, atomic_numbers
    m = lambda el: atomic_masses[atomic_numbers[el]]  # noqa: E731
    e_lab = 0.5 * m("O") * units._amu * ORBITAL_SPEED_M_S ** 2 / units._e
    ph0 = json.loads((config.ROOT / "reports" / "aerospace_phase0" / "mace-mpa-0-medium.json").read_text())["dimers"]
    out = {"orbital_speed_m_s": ORBITAL_SPEED_M_S, "E_lab_eV": e_lab, "targets": {}}
    for tgt in ("Al", "Ag"):
        e_cm = e_lab * m(tgt) / (m(tgt) + m("O"))
        d = ph0[f"{tgt}-O"]
        r, ez, em = (np.array(d[k]) for k in ("r_angstrom", "E_zbl_eV", "E_mlip_eV"))
        cross = [float(np.interp(e_cm, [em[i + 1], em[i]], [r[i + 1], r[i]]))
                 for i in range(len(r) - 1) if (em[i] - e_cm) * (em[i + 1] - e_cm) <= 0]
        out["targets"][tgt] = {"E_cm_eV": e_cm, "closest_approach_universal_zbl_A": float(np.interp(e_cm, ez[::-1], r[::-1])),
                               "closest_approach_mpa0_dimer_A": max(cross) if cross else None}
    return out


def bench_one(n: int) -> dict:
    """Run in a child process so each size's peak memory is its own."""
    code = f"""
import json, resource, time, warnings, logging; warnings.filterwarnings('ignore'); logging.disable(logging.WARNING)
from ase.build import bulk
from harness import config
from harness.engine import get_calculator
cc = config.load_compute_config(); calc = get_calculator(cc['device'], cc['dtype'])
at = bulk('Al', 'fcc', cubic=True).repeat(({n},{n},{n})); at.rattle(0.02, seed=1); at.calc = calc
at.get_forces(); ts = []
for _ in range(3):
    at.positions += 0.001; t = time.perf_counter(); at.get_forces(); ts.append(time.perf_counter() - t)
print(json.dumps({{'n_atoms': len(at), 's_per_force_call': min(ts), 'device': cc['device'], 'dtype': cc['dtype'],
                  'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}))
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                       env={**os.environ, "HARNESS_MODEL": "mace-mpa-0-medium"})
    d = json.loads(r.stdout.strip().splitlines()[-1])
    d["us_per_atom_step"] = 1e6 * d["s_per_force_call"] / d["n_atoms"]
    d["peak_rss_gb"] = d.pop("peak_rss_bytes") / 1e9  # macOS reports ru_maxrss in bytes
    return d


def main() -> None:
    zbl_terms = {k: checkpoint_zbl(k) for k in ("mace-mpa-0-medium", "mace-mp-0-medium")}
    t = time.time()
    res = {"checkpoint_zbl": zbl_terms,
           "mpa0_dimer_decomposition": decomposition(zbl_terms["mace-mpa-0-medium"]),
           "ao_impact": impact(),
           "throughput_mpa0": [bench_one(n) for n in BENCH_REPEATS],
           "machine_memory_gb": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9}
    res["wall_s"] = round(time.time() - t, 1)
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res["throughput_mpa0"], indent=1), json.dumps(res["ao_impact"], indent=1))


if __name__ == "__main__":
    main()
