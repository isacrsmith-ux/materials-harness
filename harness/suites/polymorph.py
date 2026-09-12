"""Polymorph ranking: which form of a composition wins.

A scientist rarely asks "is this exact structure stable" — they ask "which form of this composition
wins". That is a different question from every other suite here, and a harder one: the forms share a
composition, so the answer depends entirely on energy *differences* of tens of meV/atom, with no hull
and no reference structure to hide behind.

Set: Materials Project compositions with three or more known polymorphs inside a 0.2 eV/atom window,
deduplicated by StructureMatcher on the PBE structures (MP holds the same structure more than once,
e.g. under different magnetic settings). Every form is relaxed with the production engine from its own
MP PBE structure; energies per atom are directly comparable within a composition, so no hull, no
corrections and no reference cell enter the ranking. MP's uncorrected GGA/GGA+U energies are the
truth; the MP2020 correction per atom is identical for every polymorph of one composition, so it
cancels out of every difference reported here.

Scored per composition:
  ground state first   the engine's lowest-energy form is the DFT ground state (ties in the DFT
                       energies count as a hit for any of the tied forms)
  Spearman rho         correlation of the engine's ordering with DFT's, over all usable forms
  gap error            (dE_model - dE_DFT) for each form measured from the DFT ground state
  forms collapsed      how often the relaxation drove two distinct MP forms into the same structure,
                       which makes the ranking of those two meaningless whatever the energies say

In-distribution caveat, stated in the report: these are known MP materials and the engine trained on
MPtrj, so this measures ranking skill on material it has seen. `reports/unseen_test.md` is the test
that holds out the target.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict

import numpy as np
import pandas as pd
from pymatgen.core import Composition

from harness import compare, mp_data, store
from harness.config import DATA_DIR, settings_tag
from harness.jobs import relax_job
from harness.runner import run_pool

log = logging.getLogger(__name__)

SUITE = "polymorph"
SETS_FILE = DATA_DIR / "polymorph_sets.json"
WINDOW_EV = 0.2        # every form within this of the composition's lowest form
MIN_FORMS = 3
MAX_FORMS = 8          # a composition with hundreds of MP entries would swamp the set
MAX_ATOMS = 40         # the cap the pair sampler and the unseen set use
N_COMPOSITIONS = 300
SEED = 20260912
TIE_TOL_EV = 1e-6      # DFT energies this close count as tied


# --- the set ---------------------------------------------------------------------------------------

def _dedupe(forms: list[dict]) -> tuple[list[dict], int]:
    """Drop MP entries whose PBE structure is one we already have (same structure, different entry)."""
    kept: list[dict] = []
    for f in sorted(forms, key=lambda f: f["e_dft_per_atom"]):
        if any(compare.relaxed_into_target(f["structure"], k["structure"]) for k in kept):
            continue
        kept.append(f)
    return kept, len(forms) - len(kept)


def build(n_compositions: int = N_COMPOSITIONS, window: float = WINDOW_EV, min_forms: int = MIN_FORMS,
          max_forms: int = MAX_FORMS, max_atoms: int = MAX_ATOMS, seed: int = SEED,
          path=SETS_FILE, force: bool = False) -> dict:
    """Choose and freeze the polymorph sets (fixed-seed random sample; no stratification to bias)."""
    import random

    if path.is_file() and not force:
        log.info("polymorph sets already chosen — reusing %s", path)
        return json.loads(path.read_text())
    hull = mp_data.bulk_gga_hull()
    by_formula: dict[str, list] = defaultdict(list)
    for d in mp_data.bulk_summary(max_atoms):
        if d["material_id"] in hull and d["nsites"] <= max_atoms:
            by_formula[Composition(d["composition_reduced"]).reduced_formula].append(
                {**d, "e_hull": hull[d["material_id"]]})
    eligible = []
    for formula, ms in by_formula.items():
        lo = min(m["e_hull"] for m in ms)
        within = [m for m in ms if m["e_hull"] - lo <= window + 1e-9]
        if min_forms <= len(within) <= max_forms:
            eligible.append((formula, within, lo))
    rng = random.Random(seed)
    rng.shuffle(eligible)
    sets, dropped = [], defaultdict(int)
    # Bulk-prefetch in one pass over the front of the shuffled list: one API request per 500 materials
    # instead of one per composition (see mp_data.prefetch_pbe).
    lookahead = int(n_compositions * 1.4) + 50
    mp_data.prefetch_pbe({m["material_id"] for _, ms, _ in eligible[:lookahead] for m in ms})
    for position, (formula, ms, lo) in enumerate(eligible):
        if len(sets) >= n_compositions:
            break
        if position == lookahead:  # the first pass was not enough; fetch the next block
            mp_data.prefetch_pbe({m["material_id"] for _, ms2, _ in eligible[lookahead:lookahead * 2] for m in ms2})
        forms = []
        for m in ms:
            try:
                ref = mp_data.pbe_reference(m["material_id"])
            except KeyError:
                dropped["no PBE (GGA/GGA+U) reference"] += 1
                continue
            forms.append({"material_id": m["material_id"], "sg_number": m["sg_number"],
                          "n_atoms": len(ref["structure"]), "structure": ref["structure"],
                          "e_dft_per_atom": ref["uncorrected_energy_per_atom"],
                          "mp_e_above_hull": m["e_hull"], "theoretical": bool(m.get("theoretical"))})
        forms, n_dup = _dedupe(forms)
        dropped["duplicate structure in MP"] += n_dup
        if len(forms) < min_forms:
            dropped[f"fewer than {min_forms} distinct forms after dedupe"] += 1
            continue
        lows = sorted(f["e_dft_per_atom"] for f in forms)
        sets.append({
            "formula": formula, "n_forms": len(forms), "composition_e_hull": lo,
            "hull_bin": compare.hull_bin(lo), "chem_class": "metallic" if all(
                e.is_metal for e in Composition(formula).elements) else "compound",
            "dft_gap_mev": (lows[1] - lows[0]) * 1000.0,
            "dft_spread_mev": (lows[-1] - lows[0]) * 1000.0,
            "forms": [{k: v for k, v in f.items() if k != "structure"} for f in forms],
        })
        if len(sets) % 25 == 0:
            log.info("polymorph sets: %d/%d chosen (last: %s, %d forms)", len(sets), n_compositions, formula, len(forms))
    doc = {"created_at": pd.Timestamp.utcnow().isoformat(), "seed": seed,
           "design": {"window_ev": window, "min_forms": min_forms, "max_forms": max_forms,
                      "max_atoms": max_atoms, "n_requested": n_compositions,
                      "sampling": "fixed-seed random draw from every eligible composition; no stratification"},
           "eligible_compositions": len(eligible), "n": len(sets),
           "n_relaxations": int(sum(s["n_forms"] for s in sets)),
           "dropped": dict(dropped), "sets": sets}
    path.write_text(json.dumps(doc, indent=1, default=str) + "\n")
    return doc


def load(path=SETS_FILE) -> dict:
    return json.loads(path.read_text())


# --- running ---------------------------------------------------------------------------------------

def build_jobs(doc: dict, compute: dict, done: set | frozenset = frozenset()) -> list[dict]:
    tag = settings_tag(compute["device"], compute["dtype"])
    jobs = []
    for s in doc["sets"]:
        for f in s["forms"]:
            key = f"{s['formula']}:{f['material_id']}@{tag}"
            if key in done:
                continue
            jobs.append({"job_key": key, "formula": s["formula"], "material_id": f["material_id"],
                         "structure": mp_data.pbe_reference(f["material_id"])["structure"],
                         "e_dft_per_atom": f["e_dft_per_atom"], "sg_number": f["sg_number"],
                         "device": compute["device"], "dtype": compute["dtype"],
                         "settings": {"device": compute["device"], "dtype": compute["dtype"], "settings_tag": tag}})
    return jobs


def _record(job: dict, res: dict) -> None:
    key = job["job_key"]
    if res.get("status") != "ok":
        log.warning("%s %s: %s", key, res.get("status"), res.get("error"))
        store.record_job(SUITE, key, res["status"], payload={"formula": job["formula"],
                                                             "material_id": job["material_id"]},
                         settings=job["settings"], error=res.get("error"), runtime_s=res.get("job_wall_s"))
        return
    relaxed = res["relaxed"]
    e_mev = compare.energy_diff_mev(res["energy_per_atom"], job["e_dft_per_atom"])
    rejection = compare.rejection_reason(res, reference_per_atom=job["e_dft_per_atom"])
    lat = compare.compare_lattices(relaxed, job["structure"])
    payload = {"formula": job["formula"], "material_id": job["material_id"], "relaxed": relaxed,
               "energy_per_atom": res["energy_per_atom"], "e_dft_per_atom": job["e_dft_per_atom"],
               "energy_mev_vs_mp": e_mev, "converged": res["converged"], "n_steps": res["n_steps"],
               "min_distance_ratio": res.get("min_distance_ratio"), "max_stress_gpa": res["max_stress_gpa"],
               "rejection": rejection, "sg_number": job["sg_number"], "sg_relaxed": lat["sim_spacegroup"],
               "kept_structure": bool(compare.relaxed_into_target(relaxed, job["structure"])),
               "vol_pct": lat["vol_per_atom_pct_err"], "n_atoms": len(relaxed), "wall_time_s": res["wall_time_s"]}
    store.record_results([{"suite": SUITE, "job_key": key, "structure": f"{job['formula']} [{job['material_id']}]",
                           "formula": job["formula"], "family": f"SG {job['sg_number']}", "units": "eV/atom",
                           "test": "polymorph:energy_per_atom", "simulated_value": res["energy_per_atom"],
                           "reference_value": job["e_dft_per_atom"], "error_abs": e_mev / 1000.0,
                           "reference_provenance": "mp_computed",
                           "reference_source": f"{job['material_id']} uncorrected GGA/GGA+U energy",
                           "flags": {"converged": res["converged"], "rejection": rejection,
                                     "kept_structure": payload["kept_structure"]},
                           "settings": res["metadata"], "runtime_s": res["wall_time_s"]}])
    store.record_job(SUITE, key, "ok", payload=payload, settings=res["metadata"], runtime_s=res["wall_time_s"])


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    doc = build()
    if limit:
        doc = {**doc, "sets": doc["sets"][:limit]}
    tag = settings_tag(compute["device"], compute["dtype"])
    done = store.completed_keys(SUITE, retry_failed=retry_failed)
    jobs = build_jobs(doc, compute, done)
    jobs.sort(key=lambda j: -len(j["structure"]))
    log.info("polymorph: %d compositions, %d relaxations to run (%d already done); settings %s",
             len(doc["sets"]), len(jobs), sum(s["n_forms"] for s in doc["sets"]) - len(jobs), tag)
    run_pool(relax_job, jobs, compute["workers"], compute["threads_per_worker"], on_result=_record)
    print_summary(tag)


# --- analysis ----------------------------------------------------------------------------------------

def table(tag: str | None = None) -> pd.DataFrame:
    """One row per relaxed form, with the guard re-applied on read (compare.recheck)."""
    rows = []
    for pl in store.load_payloads(SUITE, tag=tag).values():
        if "energy_per_atom" not in pl:
            continue
        rows.append({**{k: v for k, v in pl.items() if k != "relaxed"},
                     "rejection": compare.recheck(pl.get("rejection"), pl,
                                                  reference_per_atom=pl.get("e_dft_per_atom")),
                     "relaxed": pl["relaxed"]})
    return pd.DataFrame(rows)


def _collapsed(forms: pd.DataFrame) -> int:
    """Pairs of distinct MP forms that the relaxation drove into the same structure."""
    rel = list(forms.relaxed)
    return sum(compare.relaxed_into_target(rel[i], rel[j])
               for i in range(len(rel)) for j in range(i + 1, len(rel)))


def rank(df: pd.DataFrame, doc: dict | None = None) -> pd.DataFrame:
    """One row per composition: did the engine pick the DFT ground state, and how well did it order?"""
    from scipy.stats import spearmanr

    doc = doc or load()
    meta = {s["formula"]: s for s in doc["sets"]}
    rows = []
    for formula, g in df.groupby("formula"):
        n_all = len(g)
        usable = g[g.rejection.isna()].copy()
        s = meta.get(formula, {})
        row = {"formula": formula, "n_forms_mp": s.get("n_forms"), "n_relaxed": n_all,
               "n_usable": len(usable), "n_rejected": n_all - len(usable),
               "hull_bin": s.get("hull_bin"), "chem_class": s.get("chem_class"),
               "dft_gap_mev": s.get("dft_gap_mev"), "dft_spread_mev": s.get("dft_spread_mev")}
        if len(usable) < MIN_FORMS:
            row["status"] = f"not scored: only {len(usable)} usable forms (need {MIN_FORMS})"
            rows.append(row)
            continue
        usable = usable.sort_values("e_dft_per_atom")
        e_dft = usable.e_dft_per_atom.to_numpy(float)
        e_mod = usable.energy_per_atom.to_numpy(float)
        true_min, model_pick = e_dft.min(), int(np.argmin(e_mod))
        row |= {
            "status": "scored",
            "ground_state_first": bool(e_dft[model_pick] - true_min <= TIE_TOL_EV),
            "spearman": float(spearmanr(e_dft, e_mod).statistic) if len(usable) > 2 else float("nan"),
            "gap_err_mev": [float(((e_mod[i] - e_mod[0]) - (e_dft[i] - e_dft[0])) * 1000) for i in range(1, len(e_dft))],
            "dft_gap_usable_mev": float((e_dft[1] - e_dft[0]) * 1000),
            "forms_collapsed": _collapsed(usable),
            "kept_structure_rate": float(usable.kept_structure.mean()),
            "picked": usable.material_id.iloc[model_pick], "truth": usable.material_id.iloc[0],
        }
        rows.append(row)
    return pd.DataFrame(rows)


def print_summary(tag: str | None = None) -> None:
    df = table(tag)
    if df.empty:
        print("No polymorph results yet.")
        return
    r = rank(df)
    scored = r[r.status == "scored"]
    print(f"\n=== POLYMORPH RANKING (settings {tag}) — {len(scored)} compositions scored, "
          f"{len(r) - len(scored)} not scored, {int(df.rejection.notna().sum())} relaxations rejected ===")
    if not len(scored):
        return
    gaps = [x for v in scored.gap_err_mev for x in v]
    print(f"ground state ranked first: {scored.ground_state_first.mean():.0%}  |  "
          f"mean Spearman rho: {scored.spearman.mean():.2f}  |  "
          f"gap MAE: {np.mean(np.abs(gaps)):.1f} meV/atom (median {np.median(np.abs(gaps)):.1f})  |  "
          f"compositions with two forms collapsed into one: {(scored.forms_collapsed > 0).mean():.0%}")


# --- report ------------------------------------------------------------------------------------------

def _gap_bin(mev: float) -> str:
    """How hard the ranking is: the DFT gap between the two lowest forms."""
    if mev is None or not np.isfinite(mev):
        return "unknown"
    return "≤10" if mev <= 10 else "10–50" if mev <= 50 else "50–200" if mev <= 200 else ">200"


GAP_BINS = ("≤10", "10–50", "50–200", ">200")


def _rate_row(g: pd.DataFrame, label_col: str, label, boot) -> dict:
    gaps = [x for v in g.gap_err_mev for x in v]
    return {label_col: label, "n": len(g),
            "ground state first": boot(g.ground_state_first.astype(float), "mean", "{:.2f}"),
            "Spearman ρ": boot(g.spearman.dropna(), "mean", "{:.2f}"),
            "gap MAE": boot(gaps, "mae"), "median |gap err|": boot(gaps, "median_abs"),
            "trimmed mean": boot(gaps, "trimmed")}


def report(tag: str | None = None, out=None) -> str:
    from harness import metrics as M
    from harness.config import ACTIVE_MODEL, MODELS, REPORTS_DIR, ROOT
    from harness.report import VERDICT_RULES, verdict_ci

    doc = load()
    tag = tag or settings_tag(*[json.loads((ROOT / "config" / f"compute-{ACTIVE_MODEL}.json").read_text())[k]
                                for k in ("device", "dtype")])
    df = table(tag)
    r = rank(df, doc)
    scored = r[r.status == "scored"]
    stats = {"mean": M.MEAN, "mae": M.MAE, "median_abs": M.MEDIAN_ABS, "trimmed": M.TRIMMED_MAE}

    def boot(x, stat="mae", fmt="{:.1f}"):
        x = list(x)
        return M.fmt_ci(M.boot_ci(x, stats[stat]), fmt) if len(x) else "—"

    def ci(x, stat="mae"):
        x = list(x)
        return M.boot_ci(x, stats[stat]) if len(x) else (float("nan"),) * 3

    gaps_all = [x for v in scored.gap_err_mev for x in v]
    hit_ci = ci(scored.ground_state_first.astype(float), "mean")
    rho_ci = ci(scored.spearman.dropna(), "mean")
    gap_ci = ci(gaps_all, "mae")
    scored = scored.assign(gap_bin=scored.dft_gap_usable_mev.map(_gap_bin))
    by_gap = pd.DataFrame([_rate_row(g, "DFT gap to the runner-up (meV/atom)", b, boot)
                           for b in GAP_BINS if (scored.gap_bin == b).any()
                           for g in [scored[scored.gap_bin == b]]])
    by_hull = pd.DataFrame([_rate_row(g, "composition hull bin", b, boot)
                            for b in compare.HULL_BINS_MP if (scored.hull_bin == b).any()
                            for g in [scored[scored.hull_bin == b]]])
    by_class = pd.DataFrame([_rate_row(g, "chemistry", b, boot)
                             for b in ("metallic", "compound") if (scored.chem_class == b).any()
                             for g in [scored[scored.chem_class == b]]])
    not_scored = r[r.status != "scored"]
    collapsed = float((scored.forms_collapsed > 0).mean()) if len(scored) else float("nan")
    kept = float(scored.kept_structure_rate.mean()) if len(scored) else float("nan")
    d = doc["design"]

    L = [f"# Polymorph ranking — {MODELS[ACTIVE_MODEL]['name']}", "",
         f"Generated from settings tag `{tag}`. {len(scored)} Materials Project compositions scored, "
         f"{len(not_scored)} not scored, {int(df.rejection.notna().sum())} of {len(df)} relaxations rejected by the "
         f"guard (counted, never averaged in). Brackets: 95 % bootstrap intervals; verdicts from the pessimistic "
         f"end, as everywhere else in this project.", "",
         "## The question", "",
         "A scientist rarely asks *is this exact structure stable* — they ask *which form of this composition "
         "wins*. That question has no hull and no reference cell in it: the forms share a composition, so the "
         "answer is decided entirely by energy differences of tens of meV/atom. MP2020 corrections are identical "
         "for every polymorph of one composition and cancel out of every number below; MP's uncorrected GGA/GGA+U "
         "energies are the truth, which is what the engine was trained to reproduce.", "",
         "## The set", "",
         f"* MP compositions with {d['min_forms']}–{d['max_forms']} known polymorphs inside a "
         f"{d['window_ev']:.1f} eV/atom window, cells ≤ {d['max_atoms']} atoms.",
         f"* {doc['eligible_compositions']:,} compositions are eligible; {doc['n']} were drawn at random "
         f"(seed {doc['seed']}, {d['sampling']}), giving {doc['n_relaxations']} relaxations.",
         "* Deduplicated with StructureMatcher on the PBE structures — MP holds the same structure more than "
         f"once (different magnetic settings, different tasks). Dropped at curation: "
         + ", ".join(f"{k}: {v}" for k, v in doc["dropped"].items()) + ".",
         "* Every form is relaxed from its own MP PBE structure with the production engine.", "",
         "## Headline", "", "| quantity | value | verdict |", "|:--|:--|:--|",
         f"| ground state ranked first | {boot(scored.ground_state_first.astype(float), 'mean', '{:.2f}')} "
         f"| **{verdict_ci('ground_state_hit_rate', hit_ci)}** |",
         f"| Spearman ρ of the full ordering (mean over compositions) | {boot(scored.spearman.dropna(), 'mean', '{:.2f}')} "
         f"| **{verdict_ci('spearman', rho_ci)}** |",
         f"| error on the energy gaps from the ground state | {boot(gaps_all)} meV/atom "
         f"| **{verdict_ci('gap_mae_mev', gap_ci)}** |",
         f"| … median \\|error\\| / 10 % trimmed mean | {boot(gaps_all, 'median_abs')} / {boot(gaps_all, 'trimmed')} meV/atom | — |", "",
         f"A composition here has {scored.n_usable.mean():.1f} usable forms on average, so picking the ground "
         f"state at random would be right about {1 / scored.n_usable.mean():.0%} of the time.", "",
         "## Where it is right and where it is not", "",
         "**By how hard the ranking is** — the DFT gap between the ground state and the runner-up. A 5 meV/atom "
         "gap is below this engine's own error on new materials, so getting it right there is close to a coin "
         "flip by construction.", "", by_gap.to_markdown(index=False), "",
         "**By the composition's distance from the hull**", "", by_hull.to_markdown(index=False), "",
         "**By chemistry**", "", by_class.to_markdown(index=False), "",
         "## What the relaxation did to the forms", "",
         f"* In {collapsed:.0%} of scored compositions, the relaxation drove two distinct MP forms into the **same** "
         f"structure. Their relative ranking is meaningless whatever the energies say, and a product that reports "
         f"an ordering without saying this is reporting noise as a result.",
         f"* {kept:.0%} of relaxed forms still match the MP structure they started from (species-aware "
         f"StructureMatcher, default tolerances). The rest moved somewhere else — sometimes onto another form of "
         f"the same composition, which is the line above.", ""]
    if len(not_scored):
        L += [f"* {len(not_scored)} compositions are **not scored**: "
              + ", ".join(f"{k} ({v})" for k, v in not_scored.status.value_counts().items()) + ".", ""]
    L += ["## Caveats", "",
          "* **These are known materials.** The engine trained on MPtrj, which is built from Materials Project, so "
          "this measures ranking skill on material it has seen. `reports/unseen_test.md` is the test that holds "
          "the target out; this one does not.",
          "* **No spin.** The engine has no explicit magnetism, and MP polymorph sets frequently differ by magnetic "
          "ordering. Where deduplication left two forms that DFT distinguishes only by spin, the engine cannot "
          "tell them apart in principle.",
          "* **Ties.** DFT energies within 1 µeV/atom count as tied, and a tie counts as a hit for any tied form.",
          f"* `config/costs.json` still holds 1:1 placeholder costs; nothing here is optimised against them.", ""]
    out = out or REPORTS_DIR / "polymorph.md"
    out.write_text("\n".join(L) + "\n")
    return str(out.relative_to(ROOT))
