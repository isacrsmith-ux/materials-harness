"""Stability gate: energy above the PBE convex hull, MACE vs Materials Project.

For each substitution target, within its chemical system:
  reference  MP DFT only. All GGA/GGA+U entries re-corrected with MaterialsProject2020Compatibility
             (clean=True), hull recomputed here, so MP and MACE use identical correction logic.
  mode (a)   'mace_target': MACE energy of the substituted, relaxed target vs MP DFT competitors.
  mode (b)   'mace_all': MACE-relaxed energies for the target AND every competing phase within
             0.1 eV/atom of the MP hull (phases further above it cannot be on the hull and are
             left out of this hull).
MACE entries inherit run type / U values / POTCAR spec from the MP entry they stand in for, so
the same anion and +U corrections apply. The target's own MP material is removed from the
competitor set and replaced by the MACE entry; other polymorphs of the formula stay as competitors.
Energies are signed relative to the competitor hull; e_above_hull = max(signed, 0).
"""

from __future__ import annotations

import copy
import logging

import numpy as np
import pandas as pd
from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.core import Composition
from pymatgen.analysis.compatibility import MaterialsProject2020Compatibility
from pymatgen.entries.computed_entries import ComputedStructureEntry

from harness import compare, mp_data, store
from harness.config import LADDER_BUDGET_S, settings_tag
from harness.curation import resolve_pairs
from harness.jobs import run_job
from harness.platform_check import core_counts
from harness.runner import run_pool

log = logging.getLogger(__name__)

SUITE = "stability"
COMPETITOR_WINDOW = 0.1  # eV/atom
LARGE_CELL_ATOMS = 100  # competitor cells above this run in a threads-heavy pool
THRESHOLDS = (0.0, 0.1)  # eV/atom; "stable" means e_above_hull <= threshold
ON_HULL_TOL = 1e-6
# MP's API potcar_spec lacks summary stats, which pymatgen's POTCAR check needs; the prefetch
# diagnostic (logs/stability_prefetch.log) records how many entries each setting keeps.
CHECK_POTCAR = False


def material_id(entry) -> str:
    """Canonical (new-format) MP id of an entry.

    MP entries carry entry_id = EntryID(identifier='mp-aaaaaprp', suffix='GGA') — a dict after the
    JSON cache round-trip — while entry.data['material_id'] still holds the LEGACY id (e.g.
    'mp-10597'). Pair/target ids are new-format, so the entry_id identifier must win.
    """
    eid = entry.entry_id
    if isinstance(eid, dict) and eid.get("identifier"):
        return str(eid["identifier"])
    if getattr(eid, "identifier", None):
        return str(eid.identifier)
    eid = str(eid) if eid is not None else ""
    if eid.startswith("mace:"):
        return str(entry.data.get("material_id") or eid)
    for suffix in ("-GGA+U", "-GGA", "-R2SCAN", "-r2SCAN"):
        if eid.endswith(suffix):
            return eid[: -len(suffix)]
    return eid or str(entry.data.get("material_id"))


def chemsys_of(formula: str) -> str:
    return "-".join(sorted(e.symbol for e in Composition(formula).elements))


def _compat() -> MaterialsProject2020Compatibility:
    return MaterialsProject2020Compatibility(check_potcar=CHECK_POTCAR)


def process(entries: list) -> list:
    """Strip existing corrections and re-apply MP2020 to every entry, identically."""
    return _compat().process_entries(copy.deepcopy(entries), clean=True, inplace=True)


def mace_entry(mp_entry, structure, energy_per_atom: float, label: str) -> ComputedStructureEntry:
    """A MACE-energy entry that inherits the MP entry's calculation parameters for corrections."""
    keep = {k: v for k, v in mp_entry.data.items() if k in ("oxide_type", "oxidation_states", "run_type")}
    return ComputedStructureEntry(
        structure, energy_per_atom * len(structure), parameters=copy.deepcopy(mp_entry.parameters),
        data={**keep, "material_id": material_id(mp_entry), "source": "mace"}, entry_id=f"mace:{label}")


def signed_hull_energy(competitors: list, target) -> float:
    """Target energy relative to the hull of `competitors` (negative = below it)."""
    pd_ = PhaseDiagram(competitors)
    _, e = pd_.get_decomp_and_e_above_hull(target, allow_negative=True)
    return float(e)


def window_phases(processed: list, window: float = COMPETITOR_WINDOW) -> list:
    pd_ = PhaseDiagram(processed)
    return [e for e in processed if pd_.get_e_above_hull(e) <= window + 1e-9]


def _sub_energies(tag: str) -> dict[str, dict]:
    """Best substitution start per pair (current settings only): of the 'sub' and 'sub_rescaled'
    relaxations, the lowest-energy one that passes the convergence / sanity guard (else the lowest
    one, which evaluate_target will then reject). 'start' records which start won."""
    from harness.suites.substitution import SUB_STARTS, best_start

    by_pair: dict[str, dict] = {}
    for pl in store.load_payloads("substitution", tag=tag).values():
        if pl["kind"] in SUB_STARTS:
            by_pair.setdefault(pl["pair_id"], {})[pl["kind"]] = pl
    out = {}
    for pid, starts in by_pair.items():
        r = {}
        for k, pl in starts.items():
            r[f"{k}_E"], r[f"{k}_converged"] = pl["energy_per_atom"], rejection_reason(pl) is None
        # No usable start: hand over the lowest one so evaluate_target rejects it and the failure is recorded.
        win = best_start(r, SUB_STARTS) or min(starts, key=lambda k: starts[k]["energy_per_atom"])
        out[pid] = {**starts[win], "start": win, "n_starts": len(starts)}
    return out


def window_structures(pairs: list) -> dict:
    """material id -> MP (PBE) starting structure of every competing phase in any target's window."""
    out = {}
    for cs in sorted({chemsys_of(p["target_formula"]) for p in pairs}):
        for e in window_phases(process(mp_data.entries_in_chemsys(cs))):
            out.setdefault(material_id(e), e.structure)
    return out


def competitor_payloads(tag: str) -> dict[str, dict]:
    return {pl["material_id"]: pl for pl in store.load_payloads(SUITE, tag=tag).values()
            if "relaxed" in pl and "pair_id" not in pl}


def retry_jobs(pairs: list, compute: dict, tag: str, done: set | frozenset = frozenset()) -> list[dict]:
    """Fallback-ladder jobs (config.FALLBACK_LADDER) for every competitor relaxation the guard
    rejects that has not been through the ladder yet. The queue key is '<id>:ladder@<tag>'; the result
    replaces the competitor's payload under '<id>@<tag>' with every rung recorded."""
    todo = {mid: pl for mid, pl in competitor_payloads(tag).items() if rejection_reason(pl) and "ladder" not in pl}
    if not todo:
        return []
    starts = window_structures(pairs)
    jobs = []
    for mid, pl in sorted(todo.items()):
        key = f"{mid}:ladder@{tag}"
        if key in done:
            continue
        jobs.append({"job_key": key, "record_key": f"{mid}@{tag}", "job_fn": "ladder", "suite": SUITE,
                     "material_id": mid, "rung1": pl, "rung1_rejection": rejection_reason(pl),
                     "original": starts.get(mid, pl["relaxed"]),
                     "original_source": "MP PBE structure" if mid in starts else "rung-1 end point (MP start not found)",
                     "seed": compare.stable_seed(mid), "structure": pl["relaxed"], "budget_s": LADDER_BUDGET_S,
                     "device": compute["device"], "dtype": compute["dtype"]})
    return jobs


def _competitor_jobs(pairs: list, compute: dict, tag: str, done: set) -> tuple[list, dict]:
    """One relaxation per unique MP phase within the window of any target's chemical system."""
    jobs, by_chemsys = {}, {}
    for pair in pairs:
        cs = chemsys_of(pair["target_formula"])
        if cs in by_chemsys:
            continue
        processed = process(mp_data.entries_in_chemsys(cs))
        win = window_phases(processed)
        by_chemsys[cs] = [material_id(e) for e in win]
        for e in win:
            mid = material_id(e)
            key = f"{mid}@{tag}"
            if key in done or key in jobs:
                continue
            jobs[key] = {"job_key": key, "material_id": mid, "structure": e.structure,
                         "device": compute["device"], "dtype": compute["dtype"]}
    return sorted(jobs.values(), key=lambda j: -len(j["structure"])), by_chemsys


def _record_ladder(job: dict, res: dict) -> None:
    """Store a fallback-ladder result as the competitor's result; the rung-1 outcome and every rung stay
    in the payload. If the ladder job itself failed, rung 1 stays in place, marked as retried."""
    mid, rung1 = job["material_id"], job["rung1"]
    summary1 = {k: rung1.get(k) for k in ("energy_per_atom", "converged", "n_steps", "wall_time_s")} | {
        "rejection": job["rung1_rejection"]}
    if res.get("status") != "ok":
        payload = {**rung1, "rung": None, "ladder": [], "ladder_error": res.get("error"), "rung1": summary1}
        log.warning("competitor %s fallback ladder %s: %s", mid, res.get("status"), res.get("error"))
    else:
        payload = {"material_id": mid, "relaxed": res["relaxed"], "energy_per_atom": res["energy_per_atom"],
                   "converged": res["converged"], "n_steps": res["n_steps"], "wall_time_s": res["wall_time_s"],
                   "fmax_final": res.get("fmax_final"), "max_stress_gpa": res.get("max_stress_gpa"),
                   "min_distance_ratio": res.get("min_distance_ratio"), "n_atoms": len(res["relaxed"]),
                   "rung": res["rung"], "ladder": res["ladder"], "rung1": summary1,
                   "original_source": job.get("original_source")}
        log.info("competitor %s fallback ladder: %s", mid, f"converged on rung '{res['rung']}'" if res["rung"]
                 else "no rung converged — stays rejected")
    runtime = res.get("job_wall_s")
    store.record_job(SUITE, job["record_key"], "ok", payload=payload,
                     settings=(res.get("metadata") or {}) | {"fallback_ladder": True, "layout": job.get("layout")},
                     runtime_s=runtime)
    store.record_job(SUITE, job["job_key"], res.get("status", "failed"),
                     payload={"material_id": mid, "ladder_of": job["record_key"], "rung": payload.get("rung")},
                     error=res.get("error"), runtime_s=runtime)


def _record_competitor(job: dict, res: dict) -> None:
    if job.get("job_fn") == "ladder":
        _record_ladder(job, res)
        return
    if res.get("status") != "ok":
        log.warning("competitor %s %s: %s", job["material_id"], res.get("status"), res.get("error"))
        store.record_job(SUITE, job["job_key"], res["status"], payload={"material_id": job["material_id"]},
                         settings={"layout": job.get("layout"), "n_atoms": len(job["structure"])},
                         error=res.get("error"), runtime_s=res.get("job_wall_s"))
        return
    store.record_job(SUITE, job["job_key"], "ok",
                     payload={"material_id": job["material_id"], "relaxed": res["relaxed"],
                              "energy_per_atom": res["energy_per_atom"], "converged": res["converged"],
                              "n_steps": res["n_steps"], "wall_time_s": res["wall_time_s"],
                              "fmax_final": res.get("fmax_final"), "max_stress_gpa": res.get("max_stress_gpa"),
                              "min_distance_ratio": res.get("min_distance_ratio"), "n_atoms": len(res["relaxed"])},
                     settings=res["metadata"] | {"layout": job.get("layout")}, runtime_s=res["wall_time_s"])


def rejection_reason(m: dict) -> str | None:
    """Why a MACE relaxation must not be used as an energy (None = usable)."""
    if not m.get("converged"):
        return "not converged"
    ratio = m.get("min_distance_ratio")
    if ratio is None or not np.isfinite(ratio):
        ratio = compare.min_distance_ratio(m["relaxed"])
    if ratio < compare.UNPHYSICAL_DISTANCE_RATIO:
        return f"unphysical geometry (min d/r_cov = {ratio:.2f})"
    return None


def b_status_of(absent, absent_on_hull) -> str:
    if not absent:
        return "complete"
    if absent_on_hull:
        return "not scored: reference hull phase missing"
    return "scored: off-hull phases missing"


def evaluate_target(pair: dict, sub: dict, mace_competitors: dict[str, dict]) -> dict:
    reason = rejection_reason(sub)
    if reason:
        raise ValueError(f"MACE target relaxation unusable: {reason}")
    cs = chemsys_of(pair["target_formula"])
    raw = mp_data.entries_in_chemsys(cs)
    processed = process(raw)
    tid = pair["target_id"]
    mp_target = [e for e in processed if material_id(e) == tid]
    if not mp_target:
        raise KeyError(f"{tid} not among MP2020-processed entries of {cs}")
    mp_target = mp_target[0]
    competitors = [e for e in processed if material_id(e) != tid]

    # Reference: MP DFT target vs MP DFT competitors.
    ref_signed = signed_hull_energy(competitors, mp_target)

    # Mode (a): MACE target vs MP DFT competitors.
    raw_target = next(e for e in raw if material_id(e) == tid)
    a_entry = process([mace_entry(raw_target, sub["relaxed"], sub["energy_per_atom"], f"{pair['pair_id']}:sub")])
    if not a_entry:
        raise ValueError("MP2020 compatibility rejected the MACE target entry")
    a_signed = signed_hull_energy(competitors, a_entry[0])

    # Mode (b): MACE target vs MACE-relaxed competitors within the window.
    win_ids = {material_id(e) for e in window_phases(processed)}
    # The signed energy of a STABLE target depends on its nearest competitor, which may lie outside
    # the window (e.g. HfC: next polymorph +0.2 eV/atom). Compare mode (b) signed values against MP
    # restricted to the same window. e_above_hull is unaffected: hull phases are always in the window.
    ref_window_signed = signed_hull_energy([e for e in competitors if material_id(e) in win_ids], mp_target)
    raw_by_id = {material_id(e): e for e in raw}
    b_comp, missing, rejected = [], [], {}
    for mid in sorted(win_ids - {tid}):
        m = mace_competitors.get(mid)
        if m is None:
            missing.append(mid)
            continue
        reason = m["rejection"] if "rejection" in m else rejection_reason(m)
        if reason:
            rejected[mid] = reason
            continue
        b_comp.append(mace_entry(raw_by_id[mid], m["relaxed"], m["energy_per_atom"], mid))
    n_built = len(b_comp)
    b_comp = process(b_comp)
    compat_dropped = sorted({material_id(e) for e in b_comp} ^ {mid for mid in win_ids - {tid}
                                                               if mid not in missing and mid not in rejected})
    assert len(compat_dropped) == n_built - len(b_comp)
    # A mode (b) hull without one of the MP reference hull's own phases is not the same hull: such a
    # target is NOT scored (counted as unscored). Missing phases that are off the reference hull leave
    # a usable hull; the target is scored and flagged.
    absent = set(missing) | set(rejected) | set(compat_dropped)
    ref_hull_ids = {material_id(e) for e in PhaseDiagram(processed).stable_entries} - {tid}
    absent_on_hull = sorted(absent & ref_hull_ids)
    b_status = b_status_of(absent, absent_on_hull)
    try:
        b_signed = signed_hull_energy(b_comp, a_entry[0]) if b_comp and not absent_on_hull else float("nan")
    except ValueError as exc:  # e.g. an elemental endpoint failed to relax
        log.warning("%s mode (b) hull failed: %s", pair["pair_id"], exc)
        b_signed, b_status = float("nan"), f"not scored: hull construction failed ({exc})"
    # Reported SEPARATELY, never merged into mode (b): if every missing reference-hull phase has a usable
    # MACE polymorph of the same formula in the window, the hull built with that stand-in polymorph.
    b_sub_signed, b_sub_for = float("nan"), []
    if absent_on_hull and b_comp:
        have = {e.composition.reduced_formula for e in b_comp}
        if all(raw_by_id[m].composition.reduced_formula in have for m in absent_on_hull):
            try:
                b_sub_signed, b_sub_for = signed_hull_energy(b_comp, a_entry[0]), absent_on_hull
            except ValueError:
                pass

    spin_in_hull = any(set(Composition(raw_by_id[m].composition).chemical_system.split("-"))
                       & (compare.MAGNETIC_PRONE | compare.F_ELECTRON) for m in win_ids)
    return {
        "pair_id": pair["pair_id"], "target_id": tid, "chemsys": cs, "family": pair["family"],
        "n_entries": len(raw), "n_processed": len(processed), "n_window": len(win_ids),
        "n_window_missing": len(missing) + len(rejected) + len(compat_dropped),
        "missing": missing, "rejected": rejected, "compat_dropped": compat_dropped,
        "absent_on_ref_hull": absent_on_hull, "b_status": b_status,
        "b_sub_signed": b_sub_signed, "b_sub_e_hull": max(b_sub_signed, 0.0) if np.isfinite(b_sub_signed) else float("nan"),
        "b_substituted_for": b_sub_for,
        "sub_start": sub.get("start"), "sub_n_starts": sub.get("n_starts"),
        "mp_stored_e_hull": pair["target_e_above_hull"],
        "ref_signed": ref_signed, "ref_e_hull": max(ref_signed, 0.0), "ref_window_signed": ref_window_signed,
        "a_signed": a_signed, "a_e_hull": max(a_signed, 0.0),
        "b_signed": b_signed, "b_e_hull": max(b_signed, 0.0) if np.isfinite(b_signed) else float("nan"),
        "spin_caveat": bool(pair["flags"]["spin_caveat"]), "spin_in_hull": spin_in_hull,
        "space_relevant": pair["space_relevant"],
    }


def _record_target(ev: dict, pair: dict, tag: str, settings: dict) -> None:
    src = f"MP GGA/GGA+U entries in {ev['chemsys']} ({ev['n_processed']} after MP2020Compatibility), hull recomputed"
    base = {"suite": SUITE, "job_key": f"{pair['pair_id']}@{tag}", "structure": pair["pair_id"],
            "formula": pair["target_formula"], "family": pair["family"], "units": "eV/atom",
            "reference_provenance": "mp_computed", "reference_source": src,
            "flags": {**pair["flags"], "spin_in_hull": ev["spin_in_hull"], "n_window_missing": ev["n_window_missing"]},
            "settings": settings}
    rows = []
    for mode in ("a", "b"):
        sim = ev[f"{mode}_e_hull"]
        rows.append({**base, "test": f"mode_{mode}:e_above_hull", "simulated_value": sim, "reference_value": ev["ref_e_hull"],
                     "error_abs": sim - ev["ref_e_hull"] if np.isfinite(sim) else None})
        ref_key = "ref_signed" if mode == "a" else "ref_window_signed"
        rows.append({**base, "test": f"mode_{mode}:signed_hull_energy", "simulated_value": ev[f"{mode}_signed"],
                     "reference_value": ev[ref_key],
                     "error_abs": ev[f"{mode}_signed"] - ev[ref_key] if np.isfinite(ev[f"{mode}_signed"]) else None})
    store.record_results(rows)
    store.record_job(SUITE, base["job_key"], "ok", payload=ev, settings=settings)


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    tag = settings_tag(compute["device"], compute["dtype"])
    pairs = resolve_pairs()[: limit or None]
    subs = _sub_energies(tag)
    missing_sub = [p["pair_id"] for p in pairs if p["pair_id"] not in subs]
    if missing_sub:
        log.error("substitution results missing for %d pairs at settings %s — run `--suite substitution` first: %s",
                  len(missing_sub), tag, missing_sub[:5])
        pairs = [p for p in pairs if p["pair_id"] in subs]

    done = store.completed_keys(SUITE, retry_failed=retry_failed)
    jobs, by_chemsys = _competitor_jobs(pairs, compute, tag, done)
    n_window = len({m for ids in by_chemsys.values() for m in ids})
    log.info("mode (b): %d unique competing phases within %.2f eV/atom across %d chemical systems; %d to relax",
             n_window, COMPETITOR_WINDOW, len(by_chemsys), len(jobs))
    # Two tiers: the benchmarked layout suits small cells; big cells (zeolite-like SiO2 up to
    # 360 atoms) scale with threads and would otherwise hit the per-structure timeout.
    perf = core_counts()["performance"]
    big_workers = max(1, perf // 5)
    big_threads = max(1, perf // big_workers)
    tiers = [("small", [j for j in jobs if len(j["structure"]) <= LARGE_CELL_ATOMS],
              compute["workers"], compute["threads_per_worker"]),
             ("large", [j for j in jobs if len(j["structure"]) > LARGE_CELL_ATOMS], big_workers, big_threads)]
    for name, tier_jobs, workers, threads in tiers:
        if not tier_jobs:
            continue
        log.info("mode (b) %s cells: %d jobs on %d workers x %d threads", name, len(tier_jobs), workers, threads)
        for j in tier_jobs:
            j["layout"] = {"tier": name, "workers": workers, "threads_per_worker": threads}
        run_pool(run_job, tier_jobs, workers, threads, on_result=_record_competitor)

    retries = retry_jobs(pairs, compute, tag, done=done)
    if retries:
        log.info("fallback ladder for %d rejected competitor relaxations on %d workers x %d threads",
                 len(retries), big_workers, big_threads)
        run_pool(run_job, retries, big_workers, big_threads, on_result=_record_competitor)

    mace_comp = competitor_payloads(tag)
    for pl in mace_comp.values():  # evaluate the sanity guard once per competitor, not per target
        pl["rejection"] = rejection_reason(pl)
    bad = {mid: pl["rejection"] for mid, pl in mace_comp.items() if pl["rejection"]}
    log.warning("%d of %d competitor relaxations rejected for the mode (b) hull: %s", len(bad), len(mace_comp), bad)
    settings = {"device": compute["device"], "dtype": compute["dtype"], "settings_tag": tag,
                "competitor_window_ev": COMPETITOR_WINDOW, "compatibility": "MaterialsProject2020Compatibility(clean=True)",
                "check_potcar": CHECK_POTCAR}
    for pair in pairs:
        try:
            ev = evaluate_target(pair, subs[pair["pair_id"]], mace_comp)
        except Exception as exc:  # noqa: BLE001 — one bad chemical system must not stop the gate
            log.exception("stability evaluation failed for %s", pair["pair_id"])
            store.record_job(SUITE, f"{pair['pair_id']}@{tag}", "failed", error=f"{type(exc).__name__}: {exc}")
            continue
        _record_target(ev, pair, tag, settings)
    print_summary(tag)


# --- analysis ------------------------------------------------------------------------------------

def target_table(tag: str) -> pd.DataFrame:
    rows = [pl for key, pl in store.load_payloads(SUITE, tag=tag).items() if "pair_id" in pl]
    return pd.DataFrame(rows)


def metrics(df: pd.DataFrame, mode: str) -> dict:
    col = f"{mode}_e_hull"
    d = df[np.isfinite(df[col].astype(float))] if len(df) else df
    out = {"n": len(d), "n_unscored": len(df) - len(d),
           "mae_ev": compare.mae(d[col] - d["ref_e_hull"]) if len(d) else float("nan")}
    for thr in THRESHOLDS:
        m = compare.classification_metrics(d[col] <= thr + ON_HULL_TOL, d["ref_e_hull"] <= thr + ON_HULL_TOL)
        out[f"thr{thr}"] = m
    return out


def print_summary(tag: str) -> None:
    df = target_table(tag)
    if df.empty:
        print("No stability results yet.")
        return
    print("\n=== STABILITY GATE ===")
    print(f"reference consistency: max |recomputed MP e_hull - MP stored e_hull| = "
          f"{np.nanmax(np.abs(df.ref_e_hull - df.mp_stored_e_hull.astype(float))):.4f} eV/atom")
    for label, sub in [("ALL", df), ("no spin caveat", df[~df.spin_caveat & ~df.spin_in_hull]),
                       ("spin caveat (target or hull)", df[df.spin_caveat | df.spin_in_hull])]:
        for mode in ("a", "b"):
            m = metrics(sub, mode)
            cls = "  ".join(f"@{t}: P {m[f'thr{t}']['precision']:.2f} R {m[f'thr{t}']['recall']:.2f} "
                            f"Acc {m[f'thr{t}']['accuracy']:.2f}" for t in THRESHOLDS)
            print(f"{label:<30} mode ({mode}) n={m['n']:>2}  e_hull MAE {m['mae_ev'] * 1000:6.1f} meV/atom  {cls}")
    for mode, ref_key in (("a", "ref_signed"), ("b", "ref_window_signed")):
        err = (df[f"{mode}_signed"] - df[ref_key]).abs()
        print(f"signed hull energy MAE mode ({mode}) vs {ref_key}: {err.mean() * 1000:.1f} meV/atom")
    cols = ["pair_id", "family", "ref_e_hull", "a_e_hull", "b_e_hull", "ref_signed", "a_signed",
            "ref_window_signed", "b_signed", "n_window", "n_window_missing", "spin_caveat", "spin_in_hull"]
    print(df.sort_values("pair_id")[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
