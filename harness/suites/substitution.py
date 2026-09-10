"""Substitution suite.

For every curated parent->target pair (same prototype, both in MP):
  sub  — substitute elements into the parent's PBE structure, relax with MACE, compare to target.
  ctrl — relax the MP target's PBE structure directly with MACE (control).
ctrl separates "the model is off" (ctrl disagrees with MP) from "the substitution relaxed
somewhere else" (ctrl agrees, sub doesn't). Spin-affected systems are reported separately.
"""

from __future__ import annotations

import logging

import pandas as pd

from harness import compare, mp_data, store
from harness.curation import load_dropped, resolve_pairs
from harness.jobs import relax_job
from harness.runner import run_pool

log = logging.getLogger(__name__)

SUITE = "substitution"
KINDS = ("sub", "ctrl")


def _ref_source(target: dict) -> str:
    return f"{target['material_id']} {target['functional']} ({target['thermo_type']} thermo, task {target['task_id']})"


def _record(job: dict, res: dict) -> None:
    pair, kind, key = job["pair"], job["kind"], job["job_key"]
    if res.get("status") != "ok":
        log.warning("%s failed: %s", key, res.get("error"))
        store.record_job(SUITE, key, res["status"], payload={"pair_id": pair["pair_id"], "kind": kind},
                         settings=job["settings"], error=res.get("error"), runtime_s=res.get("job_wall_s"))
        return
    target = mp_data.pbe_reference(pair["target_id"])
    relaxed = res["relaxed"]
    lat = compare.compare_lattices(relaxed, target["structure"])
    match = compare.relaxed_into_target(relaxed, target["structure"])
    e_mev = compare.energy_diff_mev(res["energy_per_atom"], target["uncorrected_energy_per_atom"])
    flags = {**pair["flags"], "converged": res["converged"], "n_steps": res["n_steps"]}
    src = _ref_source(target)
    base = {"suite": SUITE, "job_key": key, "structure": f"{pair['pair_id']} [{kind}]", "formula": pair["target_formula"],
            "family": pair["family"], "flags": flags, "settings": res["metadata"], "runtime_s": res["wall_time_s"],
            "reference_provenance": "mp_computed", "reference_source": src}
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
    store.record_results(rows)
    payload = {"pair_id": pair["pair_id"], "kind": kind, "relaxed": relaxed, "energy_per_atom": res["energy_per_atom"],
               "converged": res["converged"], "n_steps": res["n_steps"], "fmax_final": res["fmax_final"],
               "lattice": lat, "structure_match": match, "energy_mev_vs_mp": e_mev,
               "wall_time_s": res["wall_time_s"], "n_atoms": len(relaxed)}
    store.record_job(SUITE, key, "ok", payload=payload, settings=res["metadata"], runtime_s=res["wall_time_s"])
    log.info("%-26s %-4s vol %+6.2f%%  match=%s  dE %+7.1f meV/atom  steps %3d  %.1fs", pair["pair_id"], kind,
             lat["vol_per_atom_pct_err"], match, e_mev, res["n_steps"], res["wall_time_s"])


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    pairs = resolve_pairs()
    dropped = load_dropped()
    log.info("%d curated pairs (%d dropped at curation — see data/substitution_dropped.json)", len(pairs), len(dropped))
    if limit:
        pairs = pairs[:limit]
    done = store.completed_keys(SUITE, retry_failed=retry_failed)
    settings = {"device": compute["device"], "dtype": compute["dtype"], "workers": compute["workers"],
                "threads_per_worker": compute["threads_per_worker"]}
    jobs = []
    for pair in pairs:
        for kind in KINDS:
            key = f"{pair['pair_id']}:{pair['parent_id']}->{pair['target_id']}:{kind}"
            if key in done:
                continue
            if kind == "sub":
                parent = mp_data.pbe_reference(pair["parent_id"])
                structure = compare.substitute(parent["structure"], compare_mapping(pair))
            else:
                structure = mp_data.pbe_reference(pair["target_id"])["structure"]
            jobs.append({"job_key": key, "kind": kind, "pair": pair, "structure": structure,
                         "device": compute["device"], "dtype": compute["dtype"], "settings": settings})
    log.info("%d jobs to run (%d already complete)", len(jobs), 2 * len(pairs) - len(jobs))
    # Largest cells first so stragglers don't dominate the pool's tail.
    jobs.sort(key=lambda j: -len(j["structure"]))
    run_pool(relax_job, jobs, compute["workers"], compute["threads_per_worker"], on_result=_record)
    print_summary()


def compare_mapping(pair: dict) -> dict[str, str]:
    from harness.curation import parse_mapping

    return parse_mapping(pair["mapping"])


# --- analysis (also used by the report) ---------------------------------------------------------

def pair_table() -> pd.DataFrame:
    """One row per pair with sub and ctrl metrics side by side."""
    pairs = {p["pair_id"]: p for p in resolve_pairs()}
    payloads = store.load_payloads(SUITE)
    jobs = store.load_table("jobs", SUITE)
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
    failed = jobs[jobs.status != "ok"] if not jobs.empty else jobs
    for _, f in failed.iterrows():
        pid, kind = f.job_key.split(":")[0], f.job_key.rsplit(":", 1)[-1]
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
    return df


def _diagnose(r) -> str:
    if pd.isna(r.get("ctrl_match")) or pd.isna(r.get("sub_match")):
        return "incomplete"
    if not r["ctrl_match"]:
        return "model moves MP structure (model off)"
    if not r["sub_match"]:
        return "substitution relaxed elsewhere"
    return "ok (both match)"


def group_stats(df: pd.DataFrame) -> dict:
    import numpy as np

    def s(col):
        v = df[col].dropna().astype(float) if col in df else pd.Series(dtype=float)
        return float(np.mean(np.abs(v))) if len(v) else float("nan")

    return {"n": len(df), "sub_vol_mae_pct": s("sub_vol_pct"), "ctrl_vol_mae_pct": s("ctrl_vol_pct"),
            "sub_lat_mae_pct": s("sub_max_lat_pct"), "ctrl_lat_mae_pct": s("ctrl_max_lat_pct"),
            "sub_match_rate": float(df["sub_match"].mean()) if "sub_match" in df and len(df) else float("nan"),
            "ctrl_match_rate": float(df["ctrl_match"].mean()) if "ctrl_match" in df and len(df) else float("nan"),
            "ctrl_E_mae_mev": s("ctrl_dE_mev"), "sub_E_mae_mev": s("sub_dE_mev")}


def print_summary() -> None:
    df = pair_table()
    if df.empty:
        print("No substitution results yet.")
        return
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    fmt = lambda d: ("n={n:>2}  vol MAE sub {sub_vol_mae_pct:5.2f}% ctrl {ctrl_vol_mae_pct:5.2f}%  |  "
                     "lattice MAE sub {sub_lat_mae_pct:5.2f}% ctrl {ctrl_lat_mae_pct:5.2f}%  |  "
                     "match sub {sub_match_rate:4.0%} ctrl {ctrl_match_rate:4.0%}  |  "
                     "E MAE ctrl {ctrl_E_mae_mev:6.1f} meV/atom").format(**d)
    print("\n=== SUBSTITUTION SUITE ===")
    for label, sub in [("ALL", df), ("no spin caveat", df[df.spin_caveat == False]),  # noqa: E712
                       ("spin caveat (magnetic / TM / f)", df[df.spin_caveat == True]),  # noqa: E712
                       ("space-relevant", df[df.space_relevant == True])]:  # noqa: E712
        print(f"{label:<34} {fmt(group_stats(sub))}")
    print("\nBy family:")
    for fam, sub in df.groupby("family"):
        print(f"  {fam:<18} {fmt(group_stats(sub))}")
    print("\nDiagnosis counts:", df["diagnosis"].value_counts().to_dict() if "diagnosis" in df else {})
    cols = ["pair_id", "family", "spin_caveat", "target_e_hull", "sub_vol_pct", "ctrl_vol_pct", "sub_match",
            "ctrl_match", "sub_sg", "target_sg", "ctrl_dE_mev", "sub_minus_ctrl_mev", "sub_converged", "diagnosis"]
    print("\nPer pair (sorted by |sub vol error|):")
    print(df.reindex(df["sub_vol_pct"].abs().sort_values(ascending=False).index)[[c for c in cols if c in df]]
          .to_string(index=False, float_format=lambda x: f"{x:.2f}"))
