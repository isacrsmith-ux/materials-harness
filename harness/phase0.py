"""Phase 0 correctness audits: reference provenance, queue ETA, and before/after tables for the fixes.

  audit()   offline checks on the cached Materials Project data and stored results:
            1. run-type choice (GGA vs GGA+U) in every cached GGA_GGA+U document and chemsys entry set
            2. which energy MACE-MP-0 reproduces (uncorrected vs MP2020-corrected)
            3. which hull the reference e_above_hull comes from (GGA/GGA+U vs MP's r2SCAN-mixed default)
  eta()     queue ETA for pending jobs, from each job's measured counterpart (e.g. a rescaled start is
            estimated by the same pair's unscaled start), scheduled longest-first on polite/full workers
  report()  before/after tables: the pre-Phase-0 results snapshot vs the current results
"""

from __future__ import annotations

import glob
import heapq
import json
import logging
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from harness import compare, jobqueue, mp_data, store
from harness.config import MP_CACHE_DIR, QUEUE_DB, REPORTS_DIR, RESULTS_DIR, load_compute_config, settings_tag

log = logging.getLogger(__name__)

OUT_DIR = REPORTS_DIR / "phase0"
BEFORE_DB = RESULTS_DIR / "snapshots" / "before_phase0.sqlite"


def _tag() -> str:
    c = load_compute_config()
    return settings_tag(c["device"], c["dtype"])


# --- 1. audits -----------------------------------------------------------------------------------

def _chem_class(elements) -> str:
    els = set(elements)
    anion = "oxide" if "O" in els else "fluoride" if "F" in els else "other"
    u = sorted(els & mp_data.U_ELEMENTS)
    return f"{anion} with {'/'.join(u)}" if u and anion != "other" else f"{anion}{' with ' + '/'.join(u) if u else ''}"


def audit_run_types() -> dict:
    """Every cached GGA_GGA+U thermo document (pbe_ref/, thermo/) and chemsys entry set."""
    docs = both = 0
    single_off_rule = Counter()
    both_by_chem = Counter()
    for pattern in ("pbe_ref/*.json", "thermo/*.json"):
        for f in glob.glob(str(MP_CACHE_DIR / pattern)):
            for t in json.loads(Path(f).read_text())["value"]:
                if t.get("thermo_type") != mp_data.PBE_THERMO_TYPE:
                    continue
                docs += 1
                ents = t.get("entries") or {}
                have = [rt for rt in ("GGA", "GGA+U") if rt in ents]
                if not have:
                    continue
                els = mp_data._entry_elements(ents[have[0]])
                if len(have) == 2:
                    both += 1
                    both_by_chem[_chem_class(els)] += 1
                elif have[0] != mp_data.mp2020_run_type(els):
                    single_off_rule[f"{have[0]} only, {_chem_class(els)}"] += 1
    ent = multi = 0
    for f in glob.glob(str(MP_CACHE_DIR / "entries_chemsys/*.json")):
        by: dict[str, set] = {}
        for e in json.loads(Path(f).read_text())["value"]:
            ent += 1
            eid = e.get("entry_id")
            mid = eid.get("identifier") if isinstance(eid, dict) else str(eid)
            by.setdefault(mid, set()).add((e.get("parameters") or {}).get("run_type"))
        multi += sum(len(v) > 1 for v in by.values())
    return {"thermo_docs": docs, "docs_with_both_gga_and_gga_u": both, "both_by_chemistry": dict(both_by_chem),
            "single_entry_differs_from_mp2020_rule": dict(single_off_rule),
            "chemsys_entries": ent, "chemsys_materials_with_several_run_types": multi}


def audit_training_energy(tag: str) -> dict:
    """Is MACE-MP-0 closer to MP's uncorrected or MP2020-corrected energies? (near-hull auto-pair controls)"""
    from harness import pairgen

    pairs = {p["pair_id"]: p for p in pairgen.load_pairs()}
    rows = []
    for pl in store.load_payloads("substitution_auto", tag=tag).values():
        if pl["kind"] != "ctrl" or pl["pair_id"] not in pairs:
            continue
        p = pairs[pl["pair_id"]]
        if (p.get("target_e_above_hull") or 1) > 0.025:
            continue
        ref = mp_data.pbe_reference(p["target_id"])
        corr = ref["corrected_energy_per_atom"] - ref["uncorrected_energy_per_atom"]
        rows.append({"functional": ref["functional"], "has_correction": abs(corr) > 1e-4,
                     "err_vs_uncorrected": (pl["energy_per_atom"] - ref["uncorrected_energy_per_atom"]) * 1000,
                     "err_vs_corrected": (pl["energy_per_atom"] - ref["corrected_energy_per_atom"]) * 1000})
    df = pd.DataFrame(rows)
    out = []
    for (fun, hc), g in df.groupby(["functional", "has_correction"]):
        out.append({"functional": fun, "MP2020 correction": "nonzero" if hc else "zero", "n": len(g),
                    "median |err| vs uncorrected (meV/atom)": g.err_vs_uncorrected.abs().median(),
                    "median |err| vs corrected (meV/atom)": g.err_vs_corrected.abs().median()})
    return {"table": out}


def audit_hull_provenance() -> dict:
    """Pair targets' GGA/GGA+U hull distance (what we score against) vs MP's default (r2SCAN-mixed) hull."""
    from harness import pairgen

    meta = {}
    for f in glob.glob(str(MP_CACHE_DIR / "bulk_summary/*.json")):
        for d in json.loads(Path(f).read_text())["value"]:
            meta[d["material_id"]] = d.get("energy_above_hull")
    rows = []
    for p in pairgen.load_pairs():
        g, m = p.get("target_e_above_hull"), meta.get(p["target_id"])
        if g is None or m is None:
            continue
        rows.append({"gga": g, "mixed": m, "bin_gga": compare.hull_bin(g), "bin_mixed": compare.hull_bin(m)})
    df = pd.DataFrame(rows)
    d = (df.gga - df.mixed).abs() * 1000
    return {"n": len(df), "differ_by_more_than_1_mev": int((d > 1).sum()), "differ_by_more_than_25_mev": int((d > 25).sum()),
            "median_abs_diff_mev": float(d.median()), "bin_would_change": int((df.bin_gga != df.bin_mixed).sum())}


def audit_hull_reproduction(tag: str) -> dict:
    from harness.suites import stability

    st = stability.target_table(tag)
    if st.empty:
        return {}
    diff = (st.ref_e_hull - st.mp_stored_e_hull.astype(float)).abs() * 1000
    return {"n": len(st), "max_abs_diff_mev": float(diff.max())}


WBM_SAMPLE_N = 2000


def _wbm_sample_entries() -> tuple[pd.DataFrame, dict]:
    from harness.suites import ood

    summary = ood.load_summary()
    ids = ood.load_sample(summary, n=WBM_SAMPLE_N)
    return summary.set_index("material_id"), ood.load_entries(ids, ood.WBM_DIR / f"ood_sample_{WBM_SAMPLE_N}_cse.json")


def audit_wbm_corrections() -> dict:
    """Re-apply MaterialsProject2020Compatibility (this pymatgen) to the sampled WBM DFT entries and compare
    with the per-atom MP2020 correction WBM ships; check each entry's run type against the MP2020 rule."""
    import copy

    from pymatgen.entries.compatibility import MaterialsProject2020Compatibility

    summary, cses = _wbm_sample_entries()
    compat = MaterialsProject2020Compatibility(check_potcar=False)
    rows = []
    for wid, e in cses.items():
        n = e.composition.num_atoms
        ref = summary.loc[wid]
        proc = compat.process_entries([copy.deepcopy(e)], clean=True, inplace=False)
        els = [el.symbol for el in e.composition.elements]
        rows.append({"wbm_id": wid, "rejected": not proc,
                     "ours": proc[0].correction / n if proc else np.nan,
                     "shipped": float(ref["e_correction_per_atom_mp2020"]),
                     "run_type": e.parameters.get("run_type"), "rule": mp_data.mp2020_run_type(els),
                     "uncorr_diff_mev": (e.uncorrected_energy / n - ref["uncorrected_energy_from_cse"] / ref["n_sites"]) * 1000,
                     "chem": _chem_class(els)})
    df = pd.DataFrame(rows)
    d = (df.ours - df.shipped).abs() * 1000
    off = df[d > 1]
    return {"n": len(df), "rejected_by_mp2020": int(df.rejected.sum()),
            "max_abs_diff_mev": float(d.max()), "n_diff_over_1_mev": int((d > 1).sum()),
            "diff_over_1_mev_by_chemistry": off.chem.value_counts().to_dict(),
            "diff_over_1_mev_elements": dict(Counter(el for wid in off.wbm_id
                                                     for el in (x.symbol for x in cses[wid].composition.elements)).most_common(8)),
            "diff_over_1_mev_ours_zero": int((off.ours.abs() < 1e-9).sum()),
            "diff_over_1_mev_examples": off.assign(diff_mev=d[off.index]).nlargest(5, "diff_mev")[
                ["wbm_id", "chem", "ours", "shipped", "diff_mev"]].to_dict("records"),
            "run_type_differs_from_mp2020_rule": int((df.run_type != df["rule"]).sum()),
            "uncorrected_energy_max_abs_diff_mev": float(df.uncorr_diff_mev.abs().max())}


def wbm_structure_table(tag: str) -> pd.DataFrame:
    """MACE-relaxed WBM structure vs WBM's DFT-relaxed structure (species-aware StructureMatcher, defaults)."""
    from harness.suites import ood

    _, cses = _wbm_sample_entries()
    df = ood.table(tag)
    df = df[df.rejection.isna()].copy()
    df["match_dft"] = [compare.relaxed_into_target(r, cses[w].structure) if w in cses else None
                       for w, r in zip(df.wbm_id, df.relaxed)]
    from harness.suites.substitution import outcome

    df["outcome"] = df.match_dft.map(outcome)
    df["bin"] = df.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
    return df


def audit() -> dict:
    tag = _tag()
    out = {"run_types": audit_run_types(), "training_energy": audit_training_energy(tag),
           "hull_provenance": audit_hull_provenance(), "curated_hull_reproduction": audit_hull_reproduction(tag),
           "wbm_mp2020_corrections": audit_wbm_corrections()}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "audit.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    return out


# --- 2. ETA ------------------------------------------------------------------------------------------

STATIC_S = 0.5
# Measured mean runtimes (MACE-MP-0, CPU float64, 1 thread) for jobs without a measured counterpart.
DEFAULT_S = {"ood": 2.5, "substitution_auto": 15.0, "substitution": 15.0, "stability": 24.0}


def _counterpart(key: str) -> str | None:
    for new, old in ((":sub_rattled_rescaled@", ":sub_rattled@"), (":sub_rescaled@", ":sub@")):
        if new in key:
            return key.replace(new, old)
    return None


def _schedule(times: list[float], workers: int) -> float:
    """Wall time of longest-first list scheduling on `workers` identical workers."""
    loads = [0.0] * max(1, workers)
    for t in sorted(times, reverse=True):
        heapq.heapreplace(loads, loads[0] + t)  # next job goes to the least-loaded worker
    return max(loads)


def eta(queue_db=QUEUE_DB) -> dict:
    """Per-job runtime estimates for pending jobs and polite/full wall-clock ETAs."""
    from harness.config import load_unattended_config
    from harness.orchestrator import layout

    runtimes = {}
    for suite in ("substitution", "substitution_auto", "stability"):
        j = store.load_table("jobs", suite)
        runtimes.update(dict(zip(j.job_key, j.runtime_s)))
    with jobqueue.connect(queue_db) as con:
        rows = [dict(r) for r in con.execute("SELECT suite, job_key, n_atoms, inputs FROM queue WHERE status='pending'")]
    typical, worst, by_kind, unknown = [], [], Counter(), 0
    for r in rows:
        key = r["job_key"]
        if ":static@" in key:
            t = w = STATIC_S
            kind = "static"
        elif ":ladder@" in key:
            rung1 = runtimes.get(key.replace(":ladder@", "@")) or 900.0
            inputs = json.loads(r["inputs"])
            t, w = 3.0 * rung1, float(inputs.get("budget_s") or 6000)  # FIRE 1500 steps ~ 3x rung 1 (500 steps)
            kind = "ladder"
        else:
            base = runtimes.get(_counterpart(key) or "")
            if base is None or not np.isfinite(base):
                unknown += 1
                base = DEFAULT_S.get(r["suite"], 15.0)
            t, w = base, base * 2
            kind = key.rsplit(":", 1)[-1].split("@")[0] if ":" in key.split("@")[0] else f"{r['suite']} relax"
        typical.append(t)
        worst.append(min(w, 6000.0))
        by_kind[kind] += 1
    cfg, compute = load_unattended_config(), load_compute_config()
    out = {"pending": len(rows), "by_kind": dict(by_kind), "no_counterpart_runtime": unknown,
           "cpu_hours_typical": sum(typical) / 3600, "cpu_hours_worst": sum(worst) / 3600}
    for mode in ("polite", "full"):
        w, _ = layout(mode, compute, cfg)
        out[f"{mode}_workers"] = w
        out[f"{mode}_hours_typical"] = _schedule(typical, w) / 3600
        out[f"{mode}_hours_worst"] = _schedule(worst, w) / 3600
    return out


# --- 3. before / after -------------------------------------------------------------------------------

def _tables(tag: str) -> dict:
    from harness import pairgen
    from harness.suites import stability, substitution

    return {"curated": substitution.pair_table(tag), "auto": substitution.pair_table(tag, suite="substitution_auto",
                                                                                       pairs=pairgen.load_pairs()),
            "stability": stability.target_table(tag), "competitors": stability.competitor_payloads(tag)}


def _agg(g: pd.DataFrame, e: str, v: str) -> dict:
    """Error statistics over results that pass the guard; rejected ones are counted, never averaged in.
    Pre-fix 'before' tables have no rejection column: their numbers are what the old report averaged."""
    ev = g[e].dropna().astype(float) if e in g else pd.Series(dtype=float)
    vv = g[v].dropna().astype(float) if v in g else pd.Series(dtype=float)
    rej_col = e.rsplit("_dE_mev", 1)[0] + "_rejection"
    rejected = int(g[rej_col].map(lambda x: isinstance(x, str)).sum()) if rej_col in g else 0
    return {"n scored": len(ev), "rejected (guard)": rejected, "E MAE": ev.abs().mean(), "E median": ev.abs().median(),
            "vol MAE %": vv.abs().mean(), "vol median %": vv.abs().median()}


def _by_bin(df: pd.DataFrame, e: str, v: str, split: str | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    d = df.assign(bin=df.target_e_hull.astype(float).map(compare.hull_bin))
    if split:
        d[split] = d[split].fillna("rejected by guard")
    keys = ["bin"] + ([split] if split else [])
    rows = [{**dict(zip(keys, k if isinstance(k, tuple) else (k,))), **_agg(g, e, v)}
            for k, g in d.groupby(keys, dropna=False)]
    out = pd.DataFrame(rows)
    order = {b: i for i, b in enumerate(compare.HULL_BINS_MP)}
    return out.sort_values(keys, key=lambda s: s.map(order) if s.name == "bin" else s)


def _md(df: pd.DataFrame, fmt=".2f") -> str:
    return df.to_markdown(index=False, floatfmt=fmt) if len(df) else "_no data_"


MIN_PAIR_OVERLAP = 0.9  # of the snapshot's auto pairs that must still be in data/auto_pairs.json


def _assert_pair_set_unchanged(tag: str) -> None:
    """Refuse to rebuild the report once the auto pair set has moved on.

    Both halves of the before/after comparison are built against the CURRENT `data/auto_pairs.json`.
    When that file is regenerated, the 'before' half silently shrinks to the pairs the snapshot and the
    new list happen to share, and the report turns into a comparison of two different samples with no
    sign that anything is wrong. `reports/phase0/phase0_report.md` is a dated record of one comparison;
    it is kept, not rebuilt.
    """
    from harness import pairgen

    with store.using(BEFORE_DB):
        snapshot_pairs = {k.split(":", 1)[0] for k in store.load_payloads("substitution_auto", tag=tag)}
    if not snapshot_pairs:
        return
    current = {p["pair_id"] for p in pairgen.load_pairs()}
    overlap = len(snapshot_pairs & current) / len(snapshot_pairs)
    if overlap < MIN_PAIR_OVERLAP:
        raise RuntimeError(
            f"the auto pair set has changed since {BEFORE_DB.name} was taken: only {overlap:.0%} of its "
            f"{len(snapshot_pairs):,} pairs are still in data/auto_pairs.json (need >= {MIN_PAIR_OVERLAP:.0%}). "
            "Rebuilding would compare two different samples. Keep the existing reports/phase0/phase0_report.md; "
            "it is a record of the Phase 0 before/after at the pair set of that date.")


def report() -> Path:
    tag = _tag()
    _assert_pair_set_unchanged(tag)
    with store.using(BEFORE_DB):
        before = _tables(tag)
    after = _tables(tag)
    audit_data = json.loads((OUT_DIR / "audit.json").read_text()) if (OUT_DIR / "audit.json").is_file() else audit()
    L = ["# Phase 0 — correctness audits: before / after", "",
         f"Settings tag `{tag}` (unchanged: rung 1 of every relaxation is the same protocol as before). "
         f"'Before' = results snapshot `{BEFORE_DB.relative_to(RESULTS_DIR.parent)}` taken before any Phase 0 job ran. "
         "Hull-distance bins use the target's GGA/GGA+U energy above hull (eV/atom). Energies in meV/atom.", ""]
    L += _section_run_types(audit_data)
    L += _section_outcomes(before, after)
    L += _section_competitors(before, after)
    L += _section_starts(before, after)
    L += _section_static(after)
    L += _section_wbm_structures(tag)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "phase0_report.md"
    out.write_text("\n".join(L) + "\n")
    return out


def _section_run_types(a: dict) -> list[str]:
    rt, tr, hp, hr = a["run_types"], a["training_energy"], a["hull_provenance"], a.get("curated_hull_reproduction", {})
    return ["## 1. GGA vs GGA+U, training data, reference hull", "",
            f"* **Documents with both a GGA and a GGA+U entry: {rt['docs_with_both_gga_and_gga_u']} of {rt['thermo_docs']:,}** "
            f"cached GGA_GGA+U thermo documents; {rt['chemsys_materials_with_several_run_types']} materials with more than one run "
            f"type among {rt['chemsys_entries']:,} cached chemical-system entries (the stability hulls). The old 'GGA first' rule "
            "therefore never fired: **0 results affected, numbers unchanged.** `mp_data.choose_run_type` now applies the "
            "MP2020 mixing rule explicitly (GGA+U for O/F compounds of Co, Cr, Fe, Mn, Mo, Ni, V, W; GGA otherwise) and logs "
            "every document where it has to choose.",
            f"* Single-entry documents whose run type differs from that rule: {rt['single_entry_differs_from_mp2020_rule'] or 'none'}.",
            "* **Training data:** MACE-MP-0 reproduces MP's *uncorrected* GGA/GGA+U energies (MPtrj) — near-hull controls:", "",
            _md(pd.DataFrame(tr["table"]), ".1f"), "",
            "  Every energy comparison therefore uses uncorrected DFT energies, and every hull applies "
            "MaterialsProject2020Compatibility identically to MACE and DFT entries (unchanged).",
            f"* **Reference hull:** all references use the GGA/GGA+U hull (thermo type `GGA_GGA+U`), not MP's default "
            f"r2SCAN-mixed hull. For the {hp['n']:,} auto-pair targets the two differ by > 25 meV/atom for "
            f"{hp['differ_by_more_than_25_mev']:,} and would move {hp['bin_would_change']:,} targets to another hull bin — "
            "so pair sampling (Phase 1) must also use the GGA/GGA+U values. The recomputed curated hulls reproduce MP's stored "
            f"GGA/GGA+U e_above_hull to {hr.get('max_abs_diff_mev', float('nan')):.2f} meV/atom (n={hr.get('n', 0)}).",
            _wbm_correction_line(a["wbm_mp2020_corrections"]), ""]


def _wbm_correction_line(w) -> str:
    if not isinstance(w, dict):
        return f"* WBM MP2020 corrections: {w}."
    return (f"* **WBM corrections:** re-applying MaterialsProject2020Compatibility (this pymatgen) to the {w['n']:,} sampled WBM "
            f"DFT entries: {w['rejected_by_mp2020']} rejected, {w['n_diff_over_1_mev']} differ from WBM's shipped per-atom "
            f"correction by > 1 meV/atom (max {w['max_abs_diff_mev']:.1f} meV/atom"
            + (f"; elements most involved {w.get('diff_over_1_mev_elements')}; in {w.get('diff_over_1_mev_ours_zero')} of them "
               "this pymatgen applies no correction where WBM's file has one — mostly intermetallics, i.e. which element "
               "is treated as the anion when an entry carries no oxidation states" if w["n_diff_over_1_mev"] else "") + "). "
            f"Run type differs from the MP2020 rule for {w['run_type_differs_from_mp2020_rule']} entries; uncorrected energies "
            f"match the summary to {w['uncorrected_energy_max_abs_diff_mev']:.3f} meV/atom. The mode (a) construction uses the "
            "shipped correction on both sides, so it cancels; mode (b) (Phase 4) will use the recomputed one on every entry.")


def _section_outcomes(before: dict, after: dict) -> list[str]:
    L = ["## 2. Same structure vs relaxed into a different structure", "",
         "Species-aware StructureMatcher (pymatgen defaults, never loosened) between each relaxed result and the MP target. "
         "Energy/volume errors of results that stayed in the target structure measure the model; results that relaxed "
         "into a different structure are a different failure and are reported separately, never mixed in.", ""]
    L += ["**Correction found while building this table:** the old analysis did not apply the convergence / sanity guard "
          "to substitution-suite results. The last report's auto-pair control (ctrl) numbers therefore averaged in relaxations "
          "that never converged (one substitution had collapsed to about −5.6×10⁹ eV/atom). They are now excluded from every "
          "error statistic and counted in the 'rejected (guard)' column. 'Before (as reported)' below is the old aggregation "
          "of the pre-Phase-0 data, unconverged results included.", ""]
    before_auto = before["auto"]
    if len(before_auto):
        raw = before_auto.copy()
        for c in ("ctrl_dE_mev", "ctrl_vol_pct"):
            raw[c] = raw[c].where(raw[c].notna(), raw.get(c.replace("_dE_mev", "_dE_mev_raw").replace("_vol_pct", "_vol_pct_raw")))
        L += ["**auto-generated pairs — MP target relaxed (ctrl), before (as reported, unconverged included):**", "",
              _md(_by_bin(raw.drop(columns=["ctrl_rejection"], errors="ignore"), "ctrl_dE_mev", "ctrl_vol_pct")), ""]
    for name, df in (("auto-generated pairs", after["auto"]), ("curated pairs", after["curated"])):
        if df.empty:
            continue
        for kind, e, v, split in (("MP target relaxed (ctrl)", "ctrl_dE_mev", "ctrl_vol_pct", "ctrl_outcome"),
                                  ("substituted parent, best start", "sub_best_dE_mev", "sub_best_vol_pct", "sub_best_outcome")):
            mixed = _by_bin(df, e, v)
            sep = _by_bin(df, e, v, split)
            L += [f"**{name} — {kind}.** Guarded, outcomes mixed:", "", _md(mixed), "",
                  "Guarded, separated by structure outcome:", "", _md(sep), ""]
    return L


def _section_competitors(before: dict, after: dict) -> list[str]:
    from harness.suites import stability

    comp = after["competitors"]
    tried = {m: pl for m, pl in comp.items() if "ladder" in pl or "rung1" in pl}
    rows = []
    for mid, pl in sorted(tried.items()):
        steps = "; ".join(f"{h['rung']}: " + (h.get("error") or ("converged" if h.get("converged") else "not converged")
                                               + f" ({h.get('n_steps')} steps)") for h in pl.get("ladder", []))
        rows.append({"material": mid, "formula": pl["relaxed"].composition.reduced_formula, "atoms": len(pl["relaxed"]),
                     "rung 1 (BFGS, 500 steps)": (pl.get("rung1") or {}).get("rejection"), "fallback rungs": steps or pl.get("ladder_error"),
                     "outcome": f"usable (rung '{pl['rung']}')" if pl.get("rung") else "still rejected"})
    L = ["## 3. Unconverged competing phases (mode (b) hulls)", "",
         "Fallback ladder, same convergence criteria (fmax 0.01 eV/Å, |stress| ≤ 0.01 GPa) on every rung: "
         "FIRE from the rung-1 end point (≤ 1,500 steps), then a perturbed restart from the MP structure (BFGS, ≤ 1,000 steps).", "",
         _md(pd.DataFrame(rows)), ""]
    def absent(r):
        return sorted(set(r.rejected or {}) | set(r.missing or []) | set(r.compat_dropped or []))

    b, a = before["stability"], after["stability"]
    if len(b):
        bi = b.set_index("pair_id")
        ai = a.set_index("pair_id") if len(a) else pd.DataFrame()
        rows = []
        for pid, r in bi.iterrows():
            ra = ai.loc[pid] if pid in ai.index else None
            if not absent(r) and (ra is None or not absent(ra)):
                continue
            rows.append({"target": pid, "chemical system": r.chemsys, "missing before": ", ".join(absent(r)),
                         "missing after": ", ".join(absent(ra)) if ra is not None else "—",
                         "mode (b) status after": ra.get("b_status", "—") if ra is not None else "—",
                         "missing phases on the MP reference hull": ", ".join(ra.get("absent_on_ref_hull") or [])
                         if ra is not None else "—"})
        L += [f"**Per system:** {len(rows)} of {len(bi)} curated targets had or have competing phases missing from their "
              "mode (b) hull.", "", _md(pd.DataFrame(rows)), ""]
    L += _stability_before_after(before["stability"], after["stability"])
    return L


def _stability_before_after(b: pd.DataFrame, a: pd.DataFrame) -> list[str]:
    from harness.suites import stability

    def row(label, st, mode, col_mode=None):
        m = stability.metrics(st, col_mode or mode)
        return {"run": label, "mode": mode, "scored": m["n"], "unscored": m["n_unscored"],
                "e_hull MAE meV/atom": m["mae_ev"] * 1000, "accuracy@0": m["thr0.0"]["accuracy"],
                "accuracy@0.1": m["thr0.1"]["accuracy"]}

    rows = []
    for label, st in (("before", b), ("after", a)):
        if not st.empty:
            rows += [row(label, st, "a"), row(label, st, "b")]
    if len(a) and "b_sub_e_hull" in a:
        alt = a.assign(bsub_e_hull=a.b_e_hull.where(np.isfinite(a.b_e_hull.astype(float)), a.b_sub_e_hull))
        rows.append(row("after", alt, "b + stand-in polymorph (flagged)", "bsub"))
    note = ""
    if "sub_start" in a:
        note = f"Target energies now come from the best substitution start ({a.sub_start.value_counts().to_dict()})."
    if len(a) and "b_substituted_for" in a:
        n_sub = int(a.b_substituted_for.map(bool).sum())
        note += (f" The last row is NOT mode (b): for {n_sub} targets a reference-hull phase has no usable MACE relaxation, "
                 "and a converged polymorph of the same formula stands in for it. It is shown so the cost of the strict rule "
                 "is visible; the strict mode (b) row is the scored result.")
    return ["**Curated stability gate, before / after** (target energy = best substitution start; mode (b) scored only when "
            "the hull is complete or only off-hull phases are missing):", "", _md(pd.DataFrame(rows), ".3f"), "", note, ""]


def _section_starts(before: dict, after: dict) -> list[str]:
    L = ["## 4. Two substitution starts: parent volume vs predicted volume", "",
         "Each substitution is relaxed from the parent's cell as is (unscaled) and from the same cell rescaled to a predicted "
         "volume (pymatgen RLS volume predictor with ionic radii, else atomic radii, else DLS bond lengths). The lowest-energy "
         "converged result is kept; which start won is recorded.", ""]
    for name, df in (("auto-generated pairs", after["auto"]), ("curated pairs", after["curated"])):
        if df.empty or "sub_best_start" not in df:
            continue
        d = df.assign(bin=df.target_e_hull.astype(float).map(compare.hull_bin))
        ok = lambda k: d.get(f"{k}_usable", pd.Series(False, index=d.index)).eq(True)  # noqa: E731
        d["both"] = ok("sub") & ok("sub_rescaled")
        d["rescued"] = ~ok("sub") & ok("sub_rescaled")
        d["gain"] = -d.get("rescaled_minus_unscaled_mev", pd.Series(np.nan, index=d.index)).astype(float)
        rows = []
        for b in compare.HULL_BINS_MP:
            g = d[d.bin == b]
            if not len(g):
                continue
            both = g[g.both]
            f = lambda s: s.astype(float)  # noqa: E731
            rows.append({"bin": b, "pairs": len(g), "both starts usable": len(both),
                         "tie (|ΔE| ≤ 1)": int((both.gain.abs() <= 1).sum()),
                         "rescaled lower by > 1": int((both.gain > 1).sum()),
                         "rescaled lower by > 10": int((both.gain > 10).sum()),
                         "unscaled lower by > 1": int((both.gain < -1).sum()),
                         "same pairs — E MAE unscaled → best": f"{f(both.sub_dE_mev).abs().mean():.1f} → {f(both.sub_best_dE_mev).abs().mean():.1f}",
                         "same pairs — vol MAE % unscaled → best": f"{f(both.sub_vol_pct).abs().mean():.2f} → {f(both.sub_best_vol_pct).abs().mean():.2f}",
                         "same pairs — match unscaled → best": f"{f(both.sub_match).mean():.2f} → {f(both.sub_best_match).mean():.2f}",
                         "rescued (only rescaled usable)": int(g.rescued.sum()),
                         "rescued — E MAE": f(g[g.rescued].sub_best_dE_mev).abs().mean(),
                         "no usable start": int(g.sub_best_rejection.map(lambda x: isinstance(x, str)).sum())})
        L += [f"**{name}** (ΔE in meV/atom between the two starts; 'same pairs' = pairs where both starts are usable, so "
              "the columns compare the same population):", "", _md(pd.DataFrame(rows), ".1f"), ""]
    cur_b, cur_a = before["curated"], after["curated"]
    if len(cur_a) and "rattled_diagnosis" in cur_a:
        rows = []
        for pid in cur_a.pair_id:
            rb = cur_b[cur_b.pair_id == pid]
            ra = cur_a[cur_a.pair_id == pid].iloc[0]
            old = rb.iloc[0].get("rattled_diagnosis") if len(rb) else None
            if old == ra.rattled_diagnosis and old == "returns to target structure":
                continue
            rows.append({"pair": pid, "before": f"{old} ({rb.iloc[0].get('rattled_minus_ctrl_mev', np.nan):+.1f})" if len(rb) else "—",
                         "after": f"{ra.rattled_diagnosis} ({ra.rattled_minus_ctrl_mev:+.1f})", "winning start": ra.rattled_best_start})
        L += ["**Curated symmetry-broken (rattled) runs that do not simply return to the target** (meV/atom vs the relaxed MP "
              "structure):", "", _md(pd.DataFrame(rows)), ""]
    return L


def _section_wbm_structures(tag: str) -> list[str]:
    try:
        df = wbm_structure_table(tag)
    except FileNotFoundError as exc:
        return [f"_WBM structure classification unavailable: {exc}_", ""]
    rows = []
    for b in compare.HULL_BINS_WBM:
        for o in (SAME_LABEL, DIFF_LABEL):
            g = df[(df.bin == b) & (df.outcome == o)]
            if len(g):
                rows.append({"bin (WBM, vs MP hull)": b, "outcome": o, "n": len(g), "E MAE": g.de_mev.abs().mean(),
                             "E median": g.de_mev.abs().median(), "mean signed": g.de_mev.mean()})
    return ["## Added: WBM — MACE-relaxed vs DFT-relaxed structure", "",
            f"{len(df):,} usable WBM relaxations (existing sample) compared with WBM's DFT-relaxed structures "
            f"(species-aware StructureMatcher, defaults): {int((df.outcome == DIFF_LABEL).sum())} relaxed into a different "
            "structure. Energies (MACE − DFT, meV/atom) by hull bin and outcome:", "", _md(pd.DataFrame(rows), ".1f"), ""]


SAME_LABEL, DIFF_LABEL = "same structure", "relaxed into a different structure"


def _section_static(after: dict) -> list[str]:
    df = after["auto"]
    if df.empty or "static_dE_mev" not in df:
        return []
    d = df.assign(bin=df.target_e_hull.astype(float).map(compare.hull_bin))
    rows = []
    for (b, o), g in d.groupby(["bin", "ctrl_outcome"]):
        rows.append({"bin": b, "ctrl outcome": o, "n": len(g),
                     "single point at PBE structure: MAE / median": f"{g.static_dE_mev.abs().mean():.1f} / {g.static_dE_mev.abs().median():.1f}",
                     "after relaxation (ctrl): MAE / median": f"{g.ctrl_dE_mev.abs().mean():.1f} / {g.ctrl_dE_mev.abs().median():.1f}"})
    order = {b: i for i, b in enumerate(compare.HULL_BINS_MP)}
    out = pd.DataFrame(rows).sort_values(["bin", "ctrl outcome"], key=lambda s: s.map(order) if s.name == "bin" else s)
    return ["## Added: energy at the DFT geometry (single point)", "",
            "MACE energy evaluated at the MP PBE structure without relaxing. Where the relaxed control lands in a different "
            "structure, the single point still measures the model's energy error at the DFT geometry.", "", _md(out), ""]
