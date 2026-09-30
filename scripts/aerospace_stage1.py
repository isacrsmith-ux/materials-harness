"""Aerospace Stage 1 validation: the pairwise ZBL swap (harness/zbl.py) on the production engine, scored
against the gates in reports/aerospace_md_scoping.md section 6. Tolerances are fixed here, before any run:

  gate 1  dimers (Al-Al, Al-O, Ag-O, Ag-Ag, O-O): equal to universal ZBL within 1e-6 relative below R_a, and
          strictly decreasing in r everywhere below R_b (no spurious attraction left in the core);
  gate 2  near-equilibrium invariance: every Phase 0 energy (reports/aerospace_phase0/mace-mpa-0-medium.json,
          al_defects and ag_oxygen) reproduced within 1 meV with the correction on;
  gate 3  switching range: no pair in any Phase 2 structure (MP ground states of the 12 metals and their 35
          hull oxides) lies inside its R_b, so near-equilibrium chemistry cannot feel the correction.

    HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/aerospace_stage1.py

Writes reports/aerospace_stage1.json. Gate 1 and 3 take minutes; gate 2 re-runs Phase 0 (about 12 min).
"""

from __future__ import annotations

import json
import sys
import time
from itertools import combinations_with_replacement
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.data import atomic_numbers, chemical_symbols

sys.path.insert(0, str(Path(__file__).parent))
import aerospace_phase0 as P0  # noqa: E402

from harness import config, zbl  # noqa: E402
from harness.engine import get_calculator  # noqa: E402

TOL_ZBL_REL = 1e-6
TOL_INVARIANCE_EV = 1e-3
DIMER_PAIRS = [("Al", "Al"), ("Al", "O"), ("Ag", "O"), ("Ag", "Ag"), ("O", "O")]
OUT = config.ROOT / "reports" / "aerospace_stage1.json"


def gate1(calc) -> dict:
    out = {}
    for a, b in DIMER_PAIRS:
        z1, z2 = atomic_numbers[a], atomic_numbers[b]
        r_a, r_b = zbl.switch_range(z1, z2)
        r = np.arange(0.1, r_b, 0.01)
        e = []
        for d in r:
            at = Atoms(a + b, positions=[[0, 0, 0], [0, 0, d]], cell=[20] * 3, pbc=True)
            at.calc = calc
            e.append(at.get_potential_energy())
        iso = 0.0
        for el in (a, b):
            at = Atoms(el, positions=[[0, 0, 0]], cell=[20] * 3, pbc=True)
            at.calc = calc
            iso += at.get_potential_energy()
        e = np.array(e) - iso
        core = r < r_a
        rel = np.abs(e[core] / zbl.universal(z1, z2, r[core]) - 1)
        rises = r[1:][np.diff(e) >= 0]
        out[f"{a}-{b}"] = {"R_a": r_a, "R_b": r_b, "max_rel_dev_from_zbl_below_R_a": float(rel.max()),
                           "strictly_decreasing_below_R_b": bool(len(rises) == 0),
                           "r_where_energy_rises": [round(float(x), 3) for x in rises]}
    ok = all(v["max_rel_dev_from_zbl_below_R_a"] <= TOL_ZBL_REL and v["strictly_decreasing_below_R_b"]
             for v in out.values())
    return {"pass": ok, "pairs": out}


def leaves(d, prefix=""):
    """Every numeric energy leaf of a Phase 0 result, keyed by its path."""
    if isinstance(d, dict):
        for k, v in d.items():
            yield from leaves(v, f"{prefix}/{k}")
    elif isinstance(d, float) and any(s in prefix for s in ("E_f_eV", "E_ad", "E_total_eV", "binding", "E_eV",
                                                            "free_O_atom", "fcc_minus_octa")):
        yield prefix, d


def gate2(calc) -> dict:
    ref = json.loads((config.ROOT / "reports" / "aerospace_phase0" / "mace-mpa-0-medium.json").read_text())
    P0.CALC = calc
    new = {"al_defects": P0.al_defects(), "ag_oxygen": P0.ag_oxygen()}
    r = dict(leaves({k: ref[k] for k in new}))
    n = dict(leaves(new))
    diffs = {k: abs(n[k] - r[k]) for k in r}
    worst = max(diffs, key=diffs.get)
    return {"pass": diffs[worst] <= TOL_INVARIANCE_EV, "n_values": len(diffs), "max_abs_diff_eV": diffs[worst],
            "worst": worst}


def gate3() -> dict:
    from pymatgen.analysis.phase_diagram import PhaseDiagram
    from harness import hull, mp_data
    metals = json.loads((config.ROOT / "reports" / "aerospace_phase2" / "mace-mpa-0-medium.json").read_text())["metals"]
    closest, n_struct = {}, 0
    for m in metals:
        pd = PhaseDiagram(hull.process(mp_data.entries_in_chemsys(f"{m}-O")))
        for e in pd.stable_entries:
            s = e.structure
            n_struct += 1
            for i, j, d in _pairs(s):
                z1, z2 = sorted((s[i].specie.Z, s[j].specie.Z))
                key = f"{chemical_symbols[z1]}-{chemical_symbols[z2]}"
                if d < closest.get(key, (np.inf,))[0]:
                    closest[key] = (d, zbl.switch_range(z1, z2)[1], hull.material_id(e))
    inside = {k: v for k, v in closest.items() if v[0] < v[1]}
    tight = min(closest, key=lambda k: closest[k][0] / closest[k][1])
    return {"pass": not inside, "n_structures": n_struct, "n_species_pairs": len(closest),
            "pairs_inside_R_b": {k: {"d": v[0], "R_b": v[1], "material_id": v[2]} for k, v in inside.items()},
            "tightest_margin": {"pair": tight, "d": closest[tight][0], "R_b": closest[tight][1],
                                "d_over_R_b": closest[tight][0] / closest[tight][1], "material_id": closest[tight][2]}}


def _pairs(s):
    i, j, _, d = s.get_neighbor_list(3.0)
    keep = i < j
    return zip(i[keep], j[keep], d[keep])


def main() -> None:
    if config.MODEL["key"] != "mace-mpa-0-medium":
        raise SystemExit("Stage 1 is scoped to the production engine: HARNESS_MODEL=mace-mpa-0-medium")
    cc = config.load_compute_config()
    t = time.time()
    engine = get_calculator(cc["device"], cc["dtype"])
    calc = zbl.corrected(engine, ["Al", "Ag", "O"])
    res = {"engine": config.MODEL["key"], "checkpoint_sha256": config.MODEL["sha256"], "dtype": cc["dtype"],
           "frac_a": zbl.FRAC_A, "frac_b": zbl.FRAC_B, "tolerances": {"zbl_rel": TOL_ZBL_REL, "invariance_eV": TOL_INVARIANCE_EV},
           "table_build_s": round(time.time() - t, 1)}
    res["gate3_switching_range"] = gate3()
    print("gate 3", res["gate3_switching_range"]["pass"], flush=True)
    res["gate1_dimers"] = gate1(calc)
    print("gate 1", res["gate1_dimers"]["pass"], flush=True)
    res["gate2_invariance"] = gate2(calc)
    print("gate 2", res["gate2_invariance"]["pass"], flush=True)
    res["all_gates_pass"] = all(res[k]["pass"] for k in ("gate1_dimers", "gate2_invariance", "gate3_switching_range"))
    res["wall_s"] = round(time.time() - t, 1)
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("gate")}, indent=1))


if __name__ == "__main__":
    main()
