"""Aerospace lit session Phase D support: where a head-on Al-on-Al collision turns around, for the proposed PKA ladder.

Two-body, free-dimer, equal masses, target at rest, so E_cm = E_PKA / 2. Compares the universal ZBL curve, the production
engine's own dimer, and the Stage 1 corrected dimer (V + S*(ZBL - V), harness.zbl). An indicative picture, not a lattice
calculation: in a crystal the neighbour is bound and energy transfer is smaller. Writes reports/drafts/aerospace_stage2_turning_points.json.

    HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/aerospace_stage2_turning_points.py
"""
import json

import numpy as np
from ase import Atoms
from harness import config
from harness.engine import get_calculator
from harness.zbl import universal, switch, switch_range
compute = config.load_compute_config()
calc = get_calculator(compute["device"], compute["dtype"])
def e(pos):
    a = Atoms("Al" * len(pos), positions=pos, cell=[20, 20, 20], pbc=True); a.calc = calc
    return float(a.get_potential_energy())
iso = e([[0, 0, 0]])
r = np.round(np.arange(0.50, 3.001, 0.01), 3)
V = np.array([e([[0, 0, 0], [0, 0, d]]) - 2 * iso for d in r])
Z = universal(13, 13, r)
ra, rb = switch_range(13, 13)
S = switch(r, ra, rb)[0]
Vc = V + S * (Z - V)
ladder = [10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36, 40, 50, 60, 80, 100]
def turning(Vcurve, ecm):
    # first r (coming in from large r) where V reaches ecm
    idx = np.where(Vcurve >= ecm)[0]
    idx = idx[idx > 0]
    # scan from large r downwards
    for i in range(len(r) - 1, 0, -1):
        if Vcurve[i - 1] >= ecm > Vcurve[i] or (Vcurve[i] >= ecm):
            if Vcurve[i] >= ecm: continue
            f = (ecm - Vcurve[i]) / (Vcurve[i - 1] - Vcurve[i]); return float(r[i] + f * (r[i - 1] - r[i]))
    return None
out = {"R_a": ra, "R_b": rb, "rows": []}
for E in ladder:
    ecm = E / 2  # equal masses, target at rest
    out["rows"].append({"E_PKA_eV": E, "E_cm_eV": ecm, "r_turn_zbl": turning(Z, ecm), "r_turn_engine": turning(V, ecm), "r_turn_corrected": turning(Vc, ecm),
                        "S_at_engine_turn": float(np.interp(turning(V, ecm), r, S)),
                        "dV_at_engine_turn_eV": float(np.interp(turning(V, ecm), r, S * (Z - V)))})
out["max_abs_dV_over_1.25_2.0_A"] = float(np.max(np.abs((S * (Z - V))[(r >= 1.25) & (r <= 2.0)])))
import pathlib
pathlib.Path(__file__).resolve().parents[1].joinpath("reports", "drafts", "aerospace_stage2_turning_points.json").write_text(json.dumps(out, indent=1) + "\n")
print("R_a,R_b", ra, rb)
for x in out["rows"]: print(x["E_PKA_eV"], *(f"{x[k]:.3f}" if x[k] else "None" for k in ("r_turn_zbl","r_turn_engine","r_turn_corrected","S_at_engine_turn","dV_at_engine_turn_eV")))
print("max |S(ZBL-V)| 1.25-2.0:", out["max_abs_dV_over_1.25_2.0_A"])
