"""Substitution suite.

For every curated parent->target pair (same prototype, both in MP):
  sub                   substitute elements into the parent's PBE structure (parent's volume), relax with
                        MACE, compare to target.
  sub_rescaled          the same substituted structure rescaled to a predicted volume first
                        (compare.rescale_to_predicted_volume); a second start, never a replacement.
  ctrl                  relax the MP target's PBE structure directly with MACE (control).
  static                single-point MACE energy AT the MP target's PBE structure: model energy error
                        with no relaxation in the way.
  sub_rattled(_rescaled) like sub(_rescaled), in a 2x2x2 supercell with a fixed-seed cell strain and
                        atom rattle, so the relaxation is free to leave the target's symmetry.
Of several starts for the same substitution, the lowest-energy usable (converged) result is kept as
'sub_best' / 'rattled_best', and which start won is recorded.
ctrl separates "the model is off" (ctrl disagrees with MP) from "the substitution relaxed
somewhere else" (ctrl agrees, sub doesn't). Every relaxed result is classified as "same structure"
or "relaxed into a different structure" (species-aware StructureMatcher vs the target, default
tolerances) and the two are reported separately.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from harness import compare, mp_data, store
from harness.config import settings_tag
from harness.curation import load_dropped, parse_mapping, resolve_pairs
from harness.jobs import run_job
from harness.runner import run_pool

log = logging.getLogger(__name__)

SUITE = "substitution"
KINDS = ("sub", "sub_rescaled", "ctrl", "static", "sub_rattled", "sub_rattled_rescaled")
SUB_STARTS = ("sub", "sub_rescaled")
RATTLED_STARTS = ("sub_rattled", "sub_rattled_rescaled")
RATTLE = {"rattle_angstrom": 0.03, "strain": 0.01, "supercell": (2, 2, 2)}
SAME, DIFFERENT = "same structure", "relaxed into a different structure"
BEST_FIELDS = ("vol_pct", "max_lat_pct", "match", "dE_mev", "E", "converged", "sg", "n_atoms", "steps")
# Values of a relaxation the convergence / physical-sanity guard rejects are moved to "<col>_raw" and
# blanked in the metric columns, so no aggregate can include them; "<kind>_rejection" says why (counted).
GUARDED_FIELDS = ("vol_pct", "max_lat_pct", "match", "dE_mev", "E")


def job_fn(kind: str) -> str:
    return "static" if kind == "static" else "relax"


def outcome(match) -> str | None:
    """Structure outcome of a relaxed result from its StructureMatcher flag (None if missing)."""
    if match is None or (isinstance(match, float) and np.isnan(match)):
        return None
    return SAME if bool(match) else DIFFERENT


def _ref_source(target: dict) -> str:
    return f"{target['material_id']} {target['functional']} ({target['thermo_type']} thermo, task {target['task_id']})"


def retry_jobs(suite: str, pairs: list[dict], compute: dict, tag: str, done: set | frozenset = frozenset()) -> list[dict]:
    """Fallback-ladder jobs (config.FALLBACK_LADDER) for relaxations the guard rejects that have not been
    through the ladder. Queue key '<key>:ladder@<tag>'; the result replaces the payload under '<key>@<tag>'."""
    from harness.config import LADDER_BUDGET_S
    from harness.suites.stability import rejection_reason

    pmap = {p["pair_id"]: p for p in pairs}
    settings = {"device": compute["device"], "dtype": compute["dtype"], "settings_tag": tag}
    jobs = []
    for key, pl in store.load_payloads(suite, tag=tag).items():
        if pl["kind"] == "static" or "ladder" in pl or pl["pair_id"] not in pmap:
            continue
        why = rejection_reason(pl)
        lkey = key.replace(f"@{tag}", f":ladder@{tag}")
        if not why or lkey in done:
            continue
        original, info = start_structure(pmap[pl["pair_id"]], pl["kind"])
        jobs.append({"job_key": lkey, "record_key": key, "job_fn": "ladder", "kind": pl["kind"], "suite": suite,
                     "pair": pmap[pl["pair_id"]], "rung1": pl, "rung1_rejection": why, "original": original,
                     "seed": compare.stable_seed(key), "structure": pl["relaxed"], "start_info": info,
                     "budget_s": LADDER_BUDGET_S, "settings": settings, "device": compute["device"], "dtype": compute["dtype"]})
    return jobs


def _ladder_summary(job: dict) -> dict:
    r1 = job["rung1"]
    return {k: r1.get(k) for k in ("energy_per_atom", "converged", "n_steps", "wall_time_s")} | {"rejection": job["rung1_rejection"]}


def _record_ladder(job: dict, res: dict) -> None:
    """Record a fallback-ladder result under the original key (rung 1 and every rung kept in the payload);
    if the ladder job itself failed, rung 1 stays, marked as retried. Plus a bookkeeping row for the queue."""
    suite = job.get("suite", SUITE)
    if res.get("status") == "ok":
        _record({**job, "job_key": job["record_key"], "job_fn": job_fn(job["kind"]),
                 "payload_extra": {"rung": res.get("rung"), "ladder": res.get("ladder", []), "rung1": _ladder_summary(job)}}, res)
    else:
        store.record_job(suite, job["record_key"], "ok", payload={**job["rung1"], "rung": None, "ladder": [],
                                                                   "ladder_error": res.get("error"), "rung1": _ladder_summary(job)},
                         settings=job.get("settings"))
    store.record_job(suite, job["job_key"], res.get("status", "failed"),
                     payload={"pair_id": job["pair"]["pair_id"], "kind": "ladder", "ladder_of": job["record_key"],
                              "rung": res.get("rung")}, error=res.get("error"), runtime_s=res.get("job_wall_s"))


def _record(job: dict, res: dict) -> None:
    if job.get("job_fn") == "ladder":
        _record_ladder(job, res)
        return
    pair, kind, key = job["pair"], job["kind"], job["job_key"]
    suite = job.get("suite", SUITE)  # "substitution_auto" for queue-generated pairs; same logic
    if res.get("status") != "ok":
        log.warning("%s failed: %s", key, res.get("error"))
        store.record_job(suite, key, res["status"], payload={"pair_id": pair["pair_id"], "kind": kind},
                         settings=job["settings"], error=res.get("error"), runtime_s=res.get("job_wall_s"))
        return
    target = mp_data.pbe_reference(pair["target_id"])
    src = _ref_source(target)
    e_mev = compare.energy_diff_mev(res["energy_per_atom"], target["uncorrected_energy_per_atom"])
    base = {"suite": suite, "job_key": key, "structure": f"{pair['pair_id']} [{kind}]", "formula": pair["target_formula"],
            "family": pair["family"], "reference_provenance": "mp_computed", "reference_source": src}
    if kind == "static":
        store.record_results([{**base, "test": "static:energy_per_atom", "units": "eV/atom", "flags": pair["flags"],
                               "settings": res["metadata"], "runtime_s": res.get("wall_time_s"),
                               "simulated_value": res["energy_per_atom"],
                               "reference_value": target["uncorrected_energy_per_atom"], "error_abs": e_mev / 1000.0,
                               "reference_source": src + " uncorrected energy, MACE single point at the PBE structure"}])
        store.record_job(suite, key, "ok", payload={"pair_id": pair["pair_id"], "kind": kind,
                                                    "energy_per_atom": res["energy_per_atom"], "energy_mev_vs_mp": e_mev,
                                                    "wall_time_s": res.get("wall_time_s")},
                         settings=res["metadata"], runtime_s=res.get("wall_time_s"))
        return
    relaxed = res["relaxed"]
    lat = compare.compare_lattices(relaxed, target["structure"])
    match = compare.relaxed_into_target(relaxed, target["structure"], allow_supercell=kind.startswith("sub_rattled"))
    start_info = job.get("start_info") or {}
    flags = {**pair["flags"], "converged": res["converged"], "n_steps": res["n_steps"],
             "max_stress_gpa": res["max_stress_gpa"], "structure_outcome": outcome(match),
             "start_method": start_info.get("method"), "start_volume_factor": start_info.get("volume_factor")}
    base |= {"flags": flags, "runtime_s": res["wall_time_s"],
             "settings": res["metadata"] | {"rattle": RATTLE if kind.startswith("sub_rattled") else None,
                                            "start": start_info or None}}
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
               "structure_outcome": outcome(match), "energy_mev_vs_mp": e_mev, "wall_time_s": res["wall_time_s"],
               "n_atoms": len(relaxed), "start_info": start_info or None, **job.get("payload_extra", {})}
    store.record_job(suite, key, "ok", payload=payload, settings=res["metadata"], runtime_s=res["wall_time_s"])
    log.info("%-26s %-20s vol %+6.2f%%  SG %3s  match=%s  dE %+7.1f meV/atom  steps %3d  σmax %.3f GPa  %.1fs",
             pair["pair_id"], kind, lat["vol_per_atom_pct_err"], lat["sim_spacegroup"], match, e_mev,
             res["n_steps"], res["max_stress_gpa"], res["wall_time_s"])


def start_structure(pair: dict, kind: str):
    """(starting structure, start info) for one job kind."""
    if kind in ("ctrl", "static"):
        return mp_data.pbe_reference(pair["target_id"])["structure"], {"method": "MP PBE structure"}
    parent = mp_data.pbe_reference(pair["parent_id"])
    sub = compare.substitute(parent["structure"], parse_mapping(pair["mapping"]))
    info = {"method": "parent volume (unscaled)", "volume_factor": 1.0}
    if kind.endswith("_rescaled"):
        sub, info = compare.rescale_to_predicted_volume(sub, parent["structure"])
    if kind.startswith("sub_rattled"):
        return compare.perturb(sub, seed=compare.stable_seed(pair["pair_id"]), **RATTLE), info
    return sub, info


def build_jobs(pairs: list[dict], kinds, compute: dict, suite: str = SUITE, done: set | frozenset = frozenset()) -> list[dict]:
    tag = settings_tag(compute["device"], compute["dtype"])
    settings = {"device": compute["device"], "dtype": compute["dtype"], "settings_tag": tag}
    jobs = []
    for pair in pairs:
        for kind in kinds:
            key = f"{pair['pair_id']}:{pair['parent_id']}->{pair['target_id']}:{kind}@{tag}"
            if key in done:
                continue
            s, info = start_structure(pair, kind)
            jobs.append({"job_key": key, "kind": kind, "pair": pair, "structure": s, "start_info": info,
                         "job_fn": job_fn(kind), "suite": suite, "device": compute["device"], "dtype": compute["dtype"],
                         "settings": settings})
    return jobs


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    tag = settings_tag(compute["device"], compute["dtype"])
    pairs = resolve_pairs()
    log.info("%d curated pairs (%d dropped at curation — see data/substitution_dropped.json); settings tag %s",
             len(pairs), len(load_dropped()), tag)
    if limit:
        pairs = pairs[:limit]
    done = store.completed_keys(SUITE, retry_failed=retry_failed)
    jobs = build_jobs(pairs, KINDS, compute, done=done)
    for j in jobs:
        j["settings"] |= {"workers": compute["workers"], "threads_per_worker": compute["threads_per_worker"]}
    log.info("%d jobs to run (%d already complete)", len(jobs), len(KINDS) * len(pairs) - len(jobs))
    jobs.sort(key=lambda j: -len(j["structure"]))  # largest first so stragglers don't dominate the tail
    run_pool(run_job, jobs, compute["workers"], compute["threads_per_worker"], on_result=_record)
    print_summary(tag)


# --- analysis (also used by the report) ---------------------------------------------------------

def _usable(r, k) -> bool:
    v = r.get(f"{k}_usable", r.get(f"{k}_converged"))
    return bool(v is True or v == 1)


def best_start(r, starts) -> str | None:
    """Of several starts for one substitution, the lowest-energy usable one (converged and physical —
    '<kind>_usable', else '<kind>_converged'). None if no start is usable: an unusable result is never
    promoted to 'best'; the caller counts it."""
    pool = [k for k in starts if pd.notna(r.get(f"{k}_E")) and _usable(r, k)]
    return min(pool, key=lambda k: r[f"{k}_E"]) if pool else None


def _add_best(r: dict, starts, prefix: str) -> None:
    win = best_start(r, starts)
    n_starts = sum(pd.notna(r.get(f"{k}_E")) or pd.notna(r.get(f"{k}_E_raw")) for k in starts)
    r[f"{prefix}_start"] = win
    r[f"{prefix}_n_starts"] = n_starts
    r[f"{prefix}_rejection"] = None if win or not n_starts else "no usable start"
    for f in BEST_FIELDS:
        r[f"{prefix}_{f}"] = r.get(f"{win}_{f}") if win else None


def pair_table(tag: str | None = None, suite: str = SUITE, pairs: list[dict] | None = None) -> pd.DataFrame:
    """One row per pair with every start / ctrl / static metric side by side, plus the best start
    (curated pairs by default; pass suite="substitution_auto" and the auto pair list for queue pairs)."""
    from harness.suites.stability import rejection_reason

    pairs = {p["pair_id"]: p for p in (pairs if pairs is not None else resolve_pairs())}
    payloads = store.load_payloads(suite, tag=tag)
    jobs = store.load_table("jobs", suite)
    recs = {}
    for key, pl in payloads.items():
        pid, kind = pl["pair_id"], pl["kind"]
        if kind == "ladder":  # queue bookkeeping row; the result itself lives under the original key
            continue
        r = recs.setdefault(pid, {})
        if kind == "static":
            r["static_E"], r["static_dE_mev"] = pl["energy_per_atom"], pl["energy_mev_vs_mp"]
            continue
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
        info = pl.get("start_info") or {}
        if info.get("volume_factor") is not None:
            r[f"{kind}_volume_factor"] = info["volume_factor"]
            r[f"{kind}_start_method"] = info.get("method")
        reason = rejection_reason(pl)
        r[f"{kind}_usable"], r[f"{kind}_rejection"] = reason is None, reason
        if reason:
            for f in GUARDED_FIELDS:
                r[f"{kind}_{f}_raw"], r[f"{kind}_{f}"] = r[f"{kind}_{f}"], None
    if not jobs.empty:
        failed = jobs[(jobs.status != "ok") & (jobs.job_key.str.endswith(f"@{tag}") if tag else True)]
        for _, f in failed.iterrows():
            pid, kind = f.job_key.split(":")[0], f.job_key.rsplit(":", 1)[-1].split("@")[0]
            recs.setdefault(pid, {})[f"{kind}_status"] = f"{f.status}: {f.error}"
    rows = []
    for pid, r in recs.items():
        p = pairs.get(pid, {})
        fl = p.get("flags", {})
        _add_best(r, SUB_STARTS, "sub_best")
        _add_best(r, RATTLED_STARTS, "rattled_best")
        rows.append({"pair_id": pid, "family": p.get("family"), "target_id": p.get("target_id"),
                     "target_formula": p.get("target_formula"), "mapping": p.get("mapping"),
                     "target_sg": p.get("target_sg"), "target_e_hull": p.get("target_e_above_hull"),
                     "space_relevant": p.get("space_relevant"), "spin_caveat": fl.get("spin_caveat"),
                     "magnetic": fl.get("magnetic"), "transition_metal": fl.get("transition_metal"),
                     "f_electron": fl.get("f_electron"), **r})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col, src in (("ctrl_outcome", "ctrl_match"), ("sub_best_outcome", "sub_best_match"),
                     ("rattled_best_outcome", "rattled_best_match")):
        if src in df:
            df[col] = df[src].map(outcome)
    if {"sub_E", "sub_rescaled_E"} <= set(df.columns):
        df["rescaled_minus_unscaled_mev"] = (df["sub_rescaled_E"].astype(float) - df["sub_E"].astype(float)) * 1000
    if {"sub_best_E", "ctrl_E"} <= set(df.columns):
        df["sub_minus_ctrl_mev"] = (df["sub_best_E"].astype(float) - df["ctrl_E"].astype(float)) * 1000
    if {"sub_match", "ctrl_match"} & set(df.columns):
        df["diagnosis"] = df.apply(_diagnose, axis=1)
    if {"rattled_best_E", "ctrl_E"} <= set(df.columns) and df["rattled_best_E"].notna().any():
        df["rattled_minus_ctrl_mev"] = (df["rattled_best_E"].astype(float) - df["ctrl_E"].astype(float)) * 1000
        df["rattled_keeps_sg"] = df["rattled_best_sg"] == df["target_sg"]
        df["rattled_diagnosis"] = df.apply(_diagnose_rattled, axis=1)
    return df


def _diagnose(r) -> str:
    if isinstance(r.get("ctrl_rejection"), str):
        return f"control rejected ({r['ctrl_rejection']})"
    if isinstance(r.get("sub_best_rejection"), str):
        return "substitution rejected (no usable start)"
    sub_match = r.get("sub_best_match") if pd.notna(r.get("sub_best_match")) else r.get("sub_match")
    if pd.isna(r.get("ctrl_match")) or pd.isna(sub_match):
        return "incomplete"
    if not r["ctrl_match"]:
        return "model moves MP structure (model off)"
    if not sub_match:
        return "substitution relaxed elsewhere"
    return "ok (both match)"


RATTLE_DE_TOL_MEV = 1.0  # rattled run counts as "lower energy" only below ctrl by more than this


def _diagnose_rattled(r) -> str:
    if pd.isna(r.get("rattled_best_match")) or pd.isna(r.get("ctrl_E")):
        return "incomplete"
    if r["rattled_best_sg"] == r["target_sg"] and r["rattled_best_match"]:
        return "returns to target structure"
    if r["rattled_minus_ctrl_mev"] < -RATTLE_DE_TOL_MEV:
        return f"distorts to lower energy (SG {r['rattled_best_sg']})"
    return f"lower symmetry, not lower energy (SG {r['rattled_best_sg']})"


def group_stats(df: pd.DataFrame) -> dict:
    def s(col):
        v = df[col].dropna().astype(float) if col in df else pd.Series(dtype=float)
        return float(np.mean(np.abs(v))) if len(v) else float("nan")

    def rate(col):
        return float(df[col].astype(float).mean()) if col in df and len(df) and df[col].notna().any() else float("nan")

    return {"n": len(df), "sub_vol_mae_pct": s("sub_vol_pct"), "ctrl_vol_mae_pct": s("ctrl_vol_pct"),
            "sub_best_vol_mae_pct": s("sub_best_vol_pct"),
            "sub_lat_mae_pct": s("sub_max_lat_pct"), "ctrl_lat_mae_pct": s("ctrl_max_lat_pct"),
            "sub_match_rate": rate("sub_match"), "ctrl_match_rate": rate("ctrl_match"),
            "sub_best_match_rate": rate("sub_best_match"),
            "rattled_match_rate": rate("rattled_best_match"), "rattled_keeps_sg_rate": rate("rattled_keeps_sg"),
            "ctrl_E_mae_mev": s("ctrl_dE_mev"), "sub_E_mae_mev": s("sub_dE_mev"),
            "sub_best_E_mae_mev": s("sub_best_dE_mev"), "static_E_mae_mev": s("static_dE_mev")}


def print_summary(tag: str | None = None) -> None:
    df = pair_table(tag)
    if df.empty:
        print("No substitution results yet.")
        return
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    fmt = lambda d: ("n={n:>2}  vol MAE sub {sub_vol_mae_pct:5.2f}% best {sub_best_vol_mae_pct:5.2f}% ctrl {ctrl_vol_mae_pct:5.2f}%  |  "
                     "match sub {sub_match_rate:4.0%} best {sub_best_match_rate:4.0%} ctrl {ctrl_match_rate:4.0%} "
                     "rattled {rattled_match_rate:4.0%}  |  E MAE ctrl {ctrl_E_mae_mev:6.1f} static {static_E_mae_mev:6.1f} "
                     "meV/atom").format(**d)
    print(f"\n=== SUBSTITUTION SUITE (settings {tag}) ===")
    for label, sub in [("ALL", df), ("no spin caveat", df[df.spin_caveat == False]),  # noqa: E712
                       ("spin caveat (magnetic / TM / f)", df[df.spin_caveat == True])]:  # noqa: E712
        print(f"{label:<32} {fmt(group_stats(sub))}")
    for col in ("ctrl_outcome", "sub_best_outcome", "sub_best_start", "diagnosis", "rattled_diagnosis"):
        if col in df:
            print(f"{col}:", df[col].value_counts().to_dict())
    cols = ["pair_id", "family", "target_e_hull", "sub_vol_pct", "sub_best_vol_pct", "sub_best_start", "ctrl_vol_pct",
            "sub_best_match", "ctrl_match", "rattled_best_sg", "target_sg", "rattled_minus_ctrl_mev", "ctrl_dE_mev",
            "static_dE_mev", "diagnosis", "rattled_diagnosis"]
    print("\nPer pair (sorted by |best sub vol error|):")
    order = df["sub_best_vol_pct"].astype(float).abs().sort_values(ascending=False).index
    print(df.reindex(order)[[c for c in cols if c in df]].to_string(index=False, float_format=lambda x: f"{x:.2f}"))
