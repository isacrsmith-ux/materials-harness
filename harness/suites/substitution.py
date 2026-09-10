"""Substitution suite.

For every curated parent->target pair (same prototype, both in MP):
  sub          substitute elements into the parent's PBE structure, relax with MACE, compare to target.
  ctrl         relax the MP target's PBE structure directly with MACE (control).
  sub_rattled  like sub, but in a 2x2x2 supercell with a fixed-seed cell strain and atom rattle, so
               the relaxation is free to leave the target's symmetry (e.g. octahedral tilts).
ctrl separates "the model is off" (ctrl disagrees with MP) from "the substitution relaxed
somewhere else" (ctrl agrees, sub doesn't). Spin-affected systems are reported separately.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from harness import compare, mp_data, store
from harness.config import settings_tag
from harness.curation import load_dropped, parse_mapping, resolve_pairs
from harness.jobs import relax_job
from harness.runner import run_pool

log = logging.getLogger(__name__)

SUITE = "substitution"
KINDS = ("sub", "ctrl", "sub_rattled")
RATTLE = {"rattle_angstrom": 0.03, "strain": 0.01, "supercell": (2, 2, 2)}


def _ref_source(target: dict) -> str:
    return f"{target['material_id']} {target['functional']} ({target['thermo_type']} thermo, task {target['task_id']})"


def _record(job: dict, res: dict) -> None:
    pair, kind, key = job["pair"], job["kind"], job["job_key"]
    suite = job.get("suite", SUITE)  # "substitution_auto" for queue-generated pairs; same logic
    if res.get("status") != "ok":
        log.warning("%s failed: %s", key, res.get("error"))
        store.record_job(suite, key, res["status"], payload={"pair_id": pair["pair_id"], "kind": kind},
                         settings=job["settings"], error=res.get("error"), runtime_s=res.get("job_wall_s"))
        return
    target = mp_data.pbe_reference(pair["target_id"])
    relaxed = res["relaxed"]
    lat = compare.compare_lattices(relaxed, target["structure"])
    match = compare.relaxed_into_target(relaxed, target["structure"], allow_supercell=(kind == "sub_rattled"))
    e_mev = compare.energy_diff_mev(res["energy_per_atom"], target["uncorrected_energy_per_atom"])
    flags = {**pair["flags"], "converged": res["converged"], "n_steps": res["n_steps"],
             "max_stress_gpa": res["max_stress_gpa"]}
    src = _ref_source(target)
    base = {"suite": suite, "job_key": key, "structure": f"{pair['pair_id']} [{kind}]", "formula": pair["target_formula"],
            "family": pair["family"], "flags": flags, "settings": res["metadata"] | {"rattle": RATTLE if kind == "sub_rattled" else None},
            "runtime_s": res["wall_time_s"], "reference_provenance": "mp_computed", "reference_source": src}
    rows = []
    for p in ("a", "b", "c"):
        if lat.get(f"{p}_sim") is not None:
            rows.append({**base, "test": f"{kind}:{p}", "units": "Å", "simulated_value": lat[f"{p}_sim"],
                         "reference_value": lat[f"{p}_ref"], "error_abs": lat[f"{p}_sim"] - lat[f"{p}_ref"],
                         "error_pct": lat[f"{p}_pct_err"]})
    rows.append({**base, "test": f"{kind}:vol_per_atom", "units": "Å^3/atom", "simulated_value": lat["vol_per_atom_sim"],
                 "reference_value": lat["vol_per_atom_ref"],
                 "error_abs": lat["vol_per_atom_sim"] - lat["vol_per_atom_ref"], "error_pct": lat["vol_per_atom_pct_err"]})
    rows.append({**base, "test": f"{kind}:energy_per_atom", "units": "eV/atom", "simulated_value": res["energy_per_atom"],
                 "reference_value": target["uncorrected_energy_per_atom"], "error_abs": e_mev / 1000.0,
                 "reference_source": src + " uncorrected energy"})
    rows.append({**base, "test": f"{kind}:structure_match", "units": "bool", "simulated_value": float(match),
                 "reference_value": 1.0, "error_abs": float(match) - 1.0})
    rows.append({**base, "test": f"{kind}:spacegroup", "units": "SG number", "simulated_value": float(lat["sim_spacegroup"]),
                 "reference_value": float(lat["ref_spacegroup"])})
    store.record_results(rows)
    payload = {"pair_id": pair["pair_id"], "kind": kind, "relaxed": relaxed, "energy_per_atom": res["energy_per_atom"],
               "converged": res["converged"], "n_steps": res["n_steps"], "fmax_final": res["fmax_final"],
               "max_stress_gpa": res["max_stress_gpa"], "lattice": lat, "structure_match": match,
               "energy_mev_vs_mp": e_mev, "wall_time_s": res["wall_time_s"], "n_atoms": len(relaxed)}
    store.record_job(suite, key, "ok", payload=payload, settings=res["metadata"], runtime_s=res["wall_time_s"])
    log.info("%-26s %-11s vol %+6.2f%%  SG %3s  match=%s  dE %+7.1f meV/atom  steps %3d  σmax %.3f GPa  %.1fs",
             pair["pair_id"], kind, lat["vol_per_atom_pct_err"], lat["sim_spacegroup"], match, e_mev,
             res["n_steps"], res["max_stress_gpa"], res["wall_time_s"])


def start_structure(pair: dict, kind: str):
    if kind == "ctrl":
        return mp_data.pbe_reference(pair["target_id"])["structure"]
    parent = mp_data.pbe_reference(pair["parent_id"])
    sub = compare.substitute(parent["structure"], parse_mapping(pair["mapping"]))
    if kind == "sub_rattled":
        return compare.perturb(sub, seed=compare.stable_seed(pair["pair_id"]), **RATTLE)
    return sub


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    tag = settings_tag(compute["device"], compute["dtype"])
    pairs = resolve_pairs()
    log.info("%d curated pairs (%d dropped at curation — see data/substitution_dropped.json); settings tag %s",
             len(pairs), len(load_dropped()), tag)
    if limit:
        pairs = pairs[:limit]
    done = store.completed_keys(SUITE, retry_failed=retry_failed)
    settings = {"device": compute["device"], "dtype": compute["dtype"], "workers": compute["workers"],
                "threads_per_worker": compute["threads_per_worker"], "settings_tag": tag}
    jobs = []
    for pair in pairs:
        for kind in KINDS:
            key = f"{pair['pair_id']}:{pair['parent_id']}->{pair['target_id']}:{kind}@{tag}"
            if key in done:
                continue
            jobs.append({"job_key": key, "kind": kind, "pair": pair, "structure": start_structure(pair, kind),
                         "device": compute["device"], "dtype": compute["dtype"], "settings": settings})
    log.info("%d jobs to run (%d already complete)", len(jobs), len(KINDS) * len(pairs) - len(jobs))
    jobs.sort(key=lambda j: -len(j["structure"]))  # largest first so stragglers don't dominate the tail
    run_pool(relax_job, jobs, compute["workers"], compute["threads_per_worker"], on_result=_record)
    print_summary(tag)


# --- analysis (also used by the report) ---------------------------------------------------------

def pair_table(tag: str | None = None, suite: str = SUITE, pairs: list[dict] | None = None) -> pd.DataFrame:
    """One row per pair with sub / ctrl / sub_rattled metrics side by side (curated pairs by default;
    pass suite="substitution_auto" and the auto pair list for queue-generated pairs)."""
    pairs = {p["pair_id"]: p for p in (pairs if pairs is not None else resolve_pairs())}
    payloads = store.load_payloads(suite, tag=tag)
    jobs = store.load_table("jobs", suite)
    recs = {}
    for key, pl in payloads.items():
        pid, kind = pl["pair_id"], pl["kind"]
        r = recs.setdefault(pid, {})
        r[f"{kind}_vol_pct"] = pl["lattice"]["vol_per_atom_pct_err"]
        r[f"{kind}_max_lat_pct"] = pl["lattice"]["max_abs_lattice_pct_err"]
        r[f"{kind}_match"] = pl["structure_match"]
        r[f"{kind}_dE_mev"] = pl["energy_mev_vs_mp"]
        r[f"{kind}_E"] = pl["energy_per_atom"]
        r[f"{kind}_converged"] = pl["converged"]
        r[f"{kind}_steps"] = pl["n_steps"]
        r[f"{kind}_sg"] = pl["lattice"]["sim_spacegroup"]
        r[f"{kind}_wall_s"] = pl["wall_time_s"]
        r[f"{kind}_n_atoms"] = pl["n_atoms"]
        r[f"{kind}_max_stress_gpa"] = pl.get("max_stress_gpa")
    if not jobs.empty:
        failed = jobs[(jobs.status != "ok") & (jobs.job_key.str.endswith(f"@{tag}") if tag else True)]
        for _, f in failed.iterrows():
            pid, kind = f.job_key.split(":")[0], f.job_key.rsplit(":", 1)[-1].split("@")[0]
            recs.setdefault(pid, {})[f"{kind}_status"] = f"{f.status}: {f.error}"
    rows = []
    for pid, r in recs.items():
        p = pairs.get(pid, {})
        fl = p.get("flags", {})
        rows.append({"pair_id": pid, "family": p.get("family"), "target_id": p.get("target_id"),
                     "target_sg": p.get("target_sg"), "target_e_hull": p.get("target_e_above_hull"),
                     "space_relevant": p.get("space_relevant"), "spin_caveat": fl.get("spin_caveat"),
                     "magnetic": fl.get("magnetic"), "transition_metal": fl.get("transition_metal"),
                     "f_electron": fl.get("f_electron"), **r})
    df = pd.DataFrame(rows)
    if not df.empty and {"sub_E", "ctrl_E"} <= set(df.columns):
        df["sub_minus_ctrl_mev"] = (df["sub_E"] - df["ctrl_E"]) * 1000
        df["diagnosis"] = df.apply(_diagnose, axis=1)
    if not df.empty and {"sub_rattled_E", "ctrl_E"} <= set(df.columns):
        df["rattled_minus_ctrl_mev"] = (df["sub_rattled_E"] - df["ctrl_E"]) * 1000
        df["rattled_keeps_sg"] = df["sub_rattled_sg"] == df["target_sg"]
        df["rattled_diagnosis"] = df.apply(_diagnose_rattled, axis=1)
    return df


def _diagnose(r) -> str:
    if pd.isna(r.get("ctrl_match")) or pd.isna(r.get("sub_match")):
        return "incomplete"
    if not r["ctrl_match"]:
        return "model moves MP structure (model off)"
    if not r["sub_match"]:
        return "substitution relaxed elsewhere"
    return "ok (both match)"


RATTLE_DE_TOL_MEV = 1.0  # rattled run counts as "lower energy" only below ctrl by more than this


def _diagnose_rattled(r) -> str:
    if pd.isna(r.get("sub_rattled_match")) or pd.isna(r.get("ctrl_E")):
        return "incomplete"
    if r["sub_rattled_sg"] == r["target_sg"] and r["sub_rattled_match"]:
        return "returns to target structure"
    if r["rattled_minus_ctrl_mev"] < -RATTLE_DE_TOL_MEV:
        return f"distorts to lower energy (SG {r['sub_rattled_sg']})"
    return f"lower symmetry, not lower energy (SG {r['sub_rattled_sg']})"


def group_stats(df: pd.DataFrame) -> dict:
    def s(col):
        v = df[col].dropna().astype(float) if col in df else pd.Series(dtype=float)
        return float(np.mean(np.abs(v))) if len(v) else float("nan")

    def rate(col):
        return float(df[col].astype(float).mean()) if col in df and len(df) and df[col].notna().any() else float("nan")

    return {"n": len(df), "sub_vol_mae_pct": s("sub_vol_pct"), "ctrl_vol_mae_pct": s("ctrl_vol_pct"),
            "sub_lat_mae_pct": s("sub_max_lat_pct"), "ctrl_lat_mae_pct": s("ctrl_max_lat_pct"),
            "sub_match_rate": rate("sub_match"), "ctrl_match_rate": rate("ctrl_match"),
            "rattled_match_rate": rate("sub_rattled_match"), "rattled_keeps_sg_rate": rate("rattled_keeps_sg"),
            "ctrl_E_mae_mev": s("ctrl_dE_mev"), "sub_E_mae_mev": s("sub_dE_mev")}


def print_summary(tag: str | None = None) -> None:
    df = pair_table(tag)
    if df.empty:
        print("No substitution results yet.")
        return
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    fmt = lambda d: ("n={n:>2}  vol MAE sub {sub_vol_mae_pct:5.2f}% ctrl {ctrl_vol_mae_pct:5.2f}%  |  "
                     "lat MAE sub {sub_lat_mae_pct:5.2f}% ctrl {ctrl_lat_mae_pct:5.2f}%  |  "
                     "match sub {sub_match_rate:4.0%} ctrl {ctrl_match_rate:4.0%} rattled {rattled_match_rate:4.0%} "
                     "(keeps SG {rattled_keeps_sg_rate:4.0%})  |  E MAE ctrl {ctrl_E_mae_mev:6.1f} meV/atom").format(**d)
    print(f"\n=== SUBSTITUTION SUITE (settings {tag}) ===")
    for label, sub in [("ALL", df), ("no spin caveat", df[df.spin_caveat == False]),  # noqa: E712
                       ("spin caveat (magnetic / TM / f)", df[df.spin_caveat == True]),  # noqa: E712
                       ("space-relevant", df[df.space_relevant == True])]:  # noqa: E712
        print(f"{label:<32} {fmt(group_stats(sub))}")
    print("\nBy family:")
    for fam, sub in df.groupby("family"):
        print(f"  {fam:<18} {fmt(group_stats(sub))}")
    for col in ("diagnosis", "rattled_diagnosis"):
        if col in df:
            print(f"\n{col}:", df[col].value_counts().to_dict())
    cols = ["pair_id", "family", "spin_caveat", "target_e_hull", "sub_vol_pct", "ctrl_vol_pct", "sub_match", "ctrl_match",
            "sub_rattled_sg", "target_sg", "rattled_minus_ctrl_mev", "ctrl_dE_mev", "ctrl_steps", "ctrl_max_stress_gpa",
            "sub_converged", "ctrl_converged", "sub_rattled_converged", "diagnosis", "rattled_diagnosis"]
    print("\nPer pair (sorted by |sub vol error|):")
    print(df.reindex(df["sub_vol_pct"].abs().sort_values(ascending=False).index)[[c for c in cols if c in df]]
          .to_string(index=False, float_format=lambda x: f"{x:.2f}"))
