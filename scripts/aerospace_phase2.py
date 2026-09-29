"""Aerospace-durability Phase 2, compute step: oxide formation energy per O atom for every metal the
flight data covers, on the harness's own convention. One engine per process:

    HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/aerospace_phase2.py
    HARNESS_MODEL=mace-mp-0-medium  .venv/bin/python scripts/aerospace_phase2.py

For metal M, every M-O binary oxide on the MP GGA/GGA+U hull (MP2020-corrected, `hull.process`) is
relaxed with the engine and turned into a corrected entry exactly as mode (a) does (`hull.mace_entry`);
the metal's MP ground state is relaxed too. Then, per oxide MxOy,

    dE_f / O = [E_engine,corr(MxOy) - x * e_engine(M) - y * mu_O] / y

with mu_O the MP-corrected O reference of the same hull. mu_O is shared by every metal, so its error
(GGA's O2 overbinding, feasibility memo section 2) shifts all metals equally and cannot reorder them.
MP's own value is computed the same way from MP's energies, for contrast.

Why this quantity: Phase 0 (reports/aerospace_durability_feasibility.md) allowed bulk oxide formation
energies on the MP-corrected convention, production engine; this is the thermodynamic driving force for
oxidation, the one static quantity with a direct line to AO mass change. It is not a rate.

Writes reports/aerospace_phase2/<engine>.json (computed values only; no flight data).
"""

from __future__ import annotations

import json
import time

from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.core import Element

from harness import config, hull, mp_data
from harness.engine import relax

# Every element in the flight rows (reports/aerospace_phase1_ingest.json 'materials'); Al and Li stand
# in for the two Al-Li alloys, whose compositions the source does not give.
METALS = ["Ag", "Cu", "Mo", "Ti", "Au", "Ni", "Nb", "Ta", "W", "V", "Al", "Li"]
OUT = config.ROOT / "reports" / "aerospace_phase2"


def run_metal(m: str, device: str, dtype: str) -> dict:
    entries = hull.process(mp_data.entries_in_chemsys(f"{m}-O"))
    pd = PhaseDiagram(entries)
    mu_o = pd.el_refs[Element("O")].energy_per_atom
    metal_ref = pd.el_refs[Element(m)]
    oxides = [e for e in pd.stable_entries if len(e.composition.elements) == 2]
    flag = ""
    if not oxides:  # no stable binary oxide: take the least-unstable one, flagged
        binaries = [e for e in entries if len(e.composition.elements) == 2]
        oxides = [min(binaries, key=pd.get_e_above_hull)]
        flag = f"no {m}-O oxide on the MP hull; least-unstable used (e_above_hull " \
               f"{pd.get_e_above_hull(oxides[0]):.3f} eV/atom)"

    r_m = relax(metal_ref.structure, device=device, dtype=dtype)
    res = {"mu_O_mp_eV": mu_o, "metal": {"material_id": hull.material_id(metal_ref), "converged": r_m.converged,
                                          "e_engine_eV_per_atom": r_m.energy_per_atom}, "oxides": [], "flag": flag}
    for e in oxides:
        comp = e.composition
        x, y = comp[Element(m)], comp[Element("O")]
        mp_per_o = pd.get_form_energy(e) / y
        row = {"material_id": hull.material_id(e), "formula": comp.reduced_formula, "n_atoms": len(e.structure),
               "e_above_hull_mp": pd.get_e_above_hull(e), "dEf_per_O_mp_eV": mp_per_o}
        try:
            r = relax(e.structure, device=device, dtype=dtype)
            ce = hull.process([hull.mace_entry(e, r.structure, r.energy_per_atom, row["material_id"])])[0]
            eng = (ce.energy - x * r_m.energy_per_atom - y * mu_o) / y
            row |= {"converged": r.converged, "dEf_per_O_engine_eV": eng, "engine_minus_mp_eV": eng - mp_per_o,
                    "mp2020_correction_eV": ce.correction}
        except Exception as exc:  # recorded, never silently dropped
            row |= {"converged": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
        res["oxides"].append(row)
    ok = [o for o in res["oxides"] if o.get("converged") and r_m.converged]
    res["most_negative_mp"] = min(res["oxides"], key=lambda o: o["dEf_per_O_mp_eV"])["formula"]
    if ok:
        best = min(ok, key=lambda o: o["dEf_per_O_engine_eV"])
        res["most_negative_engine"] = {"formula": best["formula"], "dEf_per_O_eV": best["dEf_per_O_engine_eV"]}
    res["most_negative_mp_value_eV"] = min(o["dEf_per_O_mp_eV"] for o in res["oxides"])
    return res


def main() -> None:
    compute = config.load_compute_config()
    dev, dt = compute["device"], compute["dtype"]
    t = time.time()
    out = {"engine": config.MODEL["key"], "checkpoint_sha256": config.MODEL["sha256"], "device": dev, "dtype": dt,
           "settings_tag": config.settings_tag(dev, dt), "relax": config.DEFAULT_RELAX.as_dict(), "metals": {}}
    for m in METALS:
        out["metals"][m] = run_metal(m, dev, dt)
        print(m, json.dumps({k: out["metals"][m].get(k) for k in ("most_negative_mp", "most_negative_engine", "flag")}))
    out["wall_s"] = round(time.time() - t, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{config.MODEL['key']}.json").write_text(json.dumps(out, indent=1, default=float) + "\n")


if __name__ == "__main__":
    main()
