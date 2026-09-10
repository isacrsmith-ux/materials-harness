"""Smoke test: Si (mp-149) -> Ge substitution, relaxed with MACE, vs MP Ge and experiment."""

from __future__ import annotations

import logging

from harness import compare, engine, mp_data, store
from harness.config import DEFAULT_RELAX

log = logging.getLogger(__name__)

SUITE = "smoke"
PARENT_ID = "mp-149"
DIAMOND_SG = 227

# Experimental reference for this one check was supplied in the task spec (~5.658 Å) and is
# NOT yet tied to a citation. The experimental suite (phase 4) replaces it with a cited value.
GE_EXPERIMENTAL_A = {"value": 5.658, "source": "task spec (~5.658 Å, room temperature)", "verified": False}

# Pass/fail thresholds, fixed up front:
#  - vs MP (the data MACE was trained to reproduce): 1 % on a.
#  - vs experiment: PBE overestimates Ge's lattice constant by ~1.5-2 %, so 2.5 % is the
#    "consistent with PBE" bound — it is a sanity bound, not an accuracy claim.
TOL_VS_MP_PCT = 1.0
TOL_VS_EXP_PCT = 2.5


def run_smoke(device: str = "cpu", dtype: str = "float64", record: bool = True) -> dict:
    # PBE (GGA) data only — MP's summary endpoint serves r2SCAN for Si/Ge now (see mp_data).
    parent = mp_data.pbe_reference(PARENT_ID)
    target = mp_data.ground_state("Ge", spacegroup_number=DIAMOND_SG)
    log.info("parent %s = %s (%s, %s); target %s (Ge, SG %s, %s, PBE e_hull=%s)", PARENT_ID, parent["material_id"],
             parent["formula"], parent["functional"], target["material_id"], target["spacegroup_number"],
             target["functional"], target["energy_above_hull"])

    start = compare.substitute(parent["structure"], {"Si": "Ge"})
    res = engine.relax(start, DEFAULT_RELAX, device, dtype)

    lat = compare.compare_lattices(res.structure, target["structure"])
    a_sim = lat.get("a_sim") or compare.conventional_cell(res.structure).a
    a_mp = lat.get("a_ref") or compare.conventional_cell(target["structure"]).a
    out = {
        "parent_id": PARENT_ID,
        "parent_canonical_id": parent["material_id"],
        "target_id": target["material_id"],
        "target_functional": target["functional"],
        "target_thermo_type": target["thermo_type"],
        "target_task_id": target["task_id"],
        "target_e_above_hull": target["energy_above_hull"],
        "converged": res.converged,
        "n_steps": res.n_steps,
        "fmax_final": res.fmax_final,
        "wall_time_s": res.wall_time_s,
        "sim_spacegroup": lat["sim_spacegroup"],
        "a_sim": a_sim,
        "a_mp": a_mp,
        "a_exp": GE_EXPERIMENTAL_A["value"],
        "a_pct_err_vs_mp": compare.pct_error(a_sim, a_mp),
        "a_pct_err_vs_exp": compare.pct_error(a_sim, GE_EXPERIMENTAL_A["value"]),
        "mp_pct_err_vs_exp": compare.pct_error(a_mp, GE_EXPERIMENTAL_A["value"]),
        "vol_per_atom_pct_err_vs_mp": lat["vol_per_atom_pct_err"],
        "energy_per_atom_sim": res.energy_per_atom,
        "energy_per_atom_mp_uncorrected": target["uncorrected_energy_per_atom"],
        "energy_mev_vs_mp": compare.energy_diff_mev(res.energy_per_atom, target["uncorrected_energy_per_atom"]),
        "relaxed_into_target": compare.relaxed_into_target(res.structure, target["structure"]),
        "settings": res.metadata,
    }
    if record:
        _record(out, res)
    return out


def _record(out: dict, res) -> None:
    from harness.config import settings_tag

    key = f"{PARENT_ID}:Si->Ge:{out['target_id']}@{settings_tag(out['settings']['device'], out['settings']['dtype'])}"
    label = f"Si->Ge ({PARENT_ID} -> {out['target_id']})"
    base = {"suite": SUITE, "job_key": key, "structure": label, "formula": "Ge", "family": "elemental-diamond",
            "flags": compare.system_flags(["Ge"]), "settings": out["settings"], "runtime_s": out["wall_time_s"]}
    mp_src = (f"{out['target_id']} {out['target_functional']} "
              f"({out['target_thermo_type']} thermo, task {out['target_task_id']})")
    rows = [
        {**base, "test": "a_vs_mp", "units": "Å", "simulated_value": out["a_sim"], "reference_value": out["a_mp"],
         "reference_provenance": "mp_computed", "reference_source": mp_src,
         "error_abs": out["a_sim"] - out["a_mp"], "error_pct": out["a_pct_err_vs_mp"]},
        {**base, "test": "a_vs_experiment", "units": "Å", "simulated_value": out["a_sim"],
         "reference_value": out["a_exp"], "reference_provenance": "experimental",
         "reference_source": GE_EXPERIMENTAL_A["source"] + (" [verified]" if GE_EXPERIMENTAL_A["verified"] else " [UNVERIFIED]"),
         "error_abs": out["a_sim"] - out["a_exp"], "error_pct": out["a_pct_err_vs_exp"]},
        {**base, "test": "energy_per_atom", "units": "eV/atom", "simulated_value": out["energy_per_atom_sim"],
         "reference_value": out["energy_per_atom_mp_uncorrected"], "reference_provenance": "mp_computed",
         "reference_source": f"{mp_src} uncorrected energy",
         "error_abs": out["energy_per_atom_sim"] - out["energy_per_atom_mp_uncorrected"], "error_pct": None},
    ]
    store.record_results(rows)
    store.record_job(SUITE, key, "ok", payload={**{k: v for k, v in out.items() if k != "settings"},
                                                "relaxed_structure": res.structure},
                     settings=out["settings"], runtime_s=out["wall_time_s"])


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    # The smoke test always runs (it's one structure) and always uses CPU/float64, per spec.
    out = run_smoke("cpu", "float64")
    ok_mp = abs(out["a_pct_err_vs_mp"]) <= TOL_VS_MP_PCT
    ok_exp = abs(out["a_pct_err_vs_exp"]) <= TOL_VS_EXP_PCT
    print(
        f"\nSMOKE  Si({PARENT_ID}) -> Ge, MP target {out['target_id']}\n"
        f"  converged={out['converged']} in {out['n_steps']} steps, {out['wall_time_s']:.2f} s, "
        f"relaxed SG {out['sim_spacegroup']}, matches MP structure: {out['relaxed_into_target']}\n"
        f"  a(MACE) = {out['a_sim']:.4f} Å | a(MP PBE) = {out['a_mp']:.4f} Å | a(exp) = {out['a_exp']:.3f} Å (unverified)\n"
        f"  MACE vs MP:  {out['a_pct_err_vs_mp']:+.2f} %  [{'PASS' if ok_mp else 'FAIL'} ≤{TOL_VS_MP_PCT}%]\n"
        f"  MACE vs exp: {out['a_pct_err_vs_exp']:+.2f} %  [{'PASS' if ok_exp else 'FAIL'} ≤{TOL_VS_EXP_PCT}%]"
        f"   (MP PBE itself vs exp: {out['mp_pct_err_vs_exp']:+.2f} %)\n"
        f"  E/atom MACE - MP(uncorrected) = {out['energy_mev_vs_mp']:+.1f} meV/atom\n"
    )
