"""Mode (b) on new materials: the target AND every competing phase relaxed with the same model.

This is how the product will work: a user's new candidate is placed on a convex hull built from Materials
Project phases, all relaxed with the engine. Sample: WBM CALIBRATION structures only, a fixed number per
hull bin, one structure per chemical system (data/mode_b_sample.json; the locked test set is never used).

For each sampled WBM structure, in its chemical system (MP GGA/GGA+U entries, MP2020 re-applied to every
entry with the same pymatgen, so DFT and model entries get identical corrections):
  reference   WBM DFT entry vs all MP DFT phases (recomputed here; WBM's shipped hull distance is also
              recorded — it uses the 2022 MP hull and pymatgen's MP2020 of that time)
  mode (a)    model-relaxed WBM structure vs all MP DFT phases
  mode (b)    model-relaxed WBM structure vs model-relaxed MP phases within COMPETITOR_WINDOW of the MP hull;
              compared with the reference restricted to the same window
Competitor relaxations are the stability suite's ('<mp id>@<settings tag>'), so a phase shared by many
systems — or already relaxed for the curated gate — is relaxed once per model. The same strict rule as the
curated gate applies: a system whose MP reference hull phase has no usable model relaxation is not scored in
mode (b); a stand-in polymorph result is recorded separately.
"""

from __future__ import annotations

import copy
import json
import logging
import random

import numpy as np
import pandas as pd
from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.core import Composition
from pymatgen.entries.computed_entries import ComputedStructureEntry

from harness import compare, mp_data, splits, store
from harness.config import DATA_DIR, settings_tag
from harness.suites import stability as st
from harness.suites.stability import COMPETITOR_WINDOW, material_id, process, rejection_reason, signed_hull_energy

log = logging.getLogger(__name__)

SUITE = "mode_b"
SAMPLE_FILE = DATA_DIR / "mode_b_sample.json"
PER_BIN = 60
SEED = 20260912


def make_sample(per_bin: int = PER_BIN, seed: int = SEED, path=SAMPLE_FILE) -> dict:
    """per_bin calibration structures per WBM hull bin, at most one per chemical system (fixed seed)."""
    from harness.suites import ood

    if path.is_file():
        return json.loads(path.read_text())
    cal = splits.calibration_ids()
    summ = ood.load_summary().set_index("material_id").loc[cal]
    rng = random.Random(seed)
    chosen, used = {}, set()
    for b in compare.HULL_BINS_WBM:
        ids = sorted(w for w, e in summ[splits.HULL_COL].items() if compare.hull_bin(e, below_zero_bin=True) == b)
        rng.shuffle(ids)
        picked = []
        for w in ids:
            cs = Composition(summ.loc[w, "formula"]).chemical_system
            if cs in used:
                continue
            used.add(cs)
            picked.append({"wbm_id": w, "chemsys": cs})
            if len(picked) == per_bin:
                break
        chosen[b] = picked
    out = {"seed": seed, "per_bin": per_bin, "source": "WBM calibration ids (data/wbm_split.json)",
           "method": "per hull bin, shuffled with random.Random(seed), first per_bin structures with an unused chemical system",
           "by_bin": chosen, "ids": [x["wbm_id"] for v in chosen.values() for x in v]}
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def chemsys_list(sample: dict) -> list[str]:
    return sorted({"-".join(sorted(x["chemsys"].split("-"))) for v in sample["by_bin"].values() for x in v})


def competitor_jobs(sample: dict, compute: dict, tag: str, done: set | frozenset = frozenset()) -> tuple[list[dict], dict]:
    """One relaxation per unique MP phase within the window of any sampled system (skipping finished ones)."""
    jobs, by_cs = {}, {}
    for cs in chemsys_list(sample):
        win = st.window_phases(process(mp_data.entries_in_chemsys(cs)))
        by_cs[cs] = [material_id(e) for e in win]
        for e in win:
            key = f"{material_id(e)}@{tag}"
            if key not in done and key not in jobs:
                jobs[key] = {"job_key": key, "material_id": material_id(e), "structure": e.structure, "suite": st.SUITE,
                             "device": compute["device"], "dtype": compute["dtype"]}
    return sorted(jobs.values(), key=lambda j: -len(j["structure"])), by_cs


def _entry_like(cse: ComputedStructureEntry, structure, energy_per_atom: float, label: str) -> ComputedStructureEntry:
    return ComputedStructureEntry(structure, energy_per_atom * len(structure), parameters=copy.deepcopy(cse.parameters),
                                  data={"source": label}, entry_id=label)


def evaluate(wid: str, cs: str, cse: ComputedStructureEntry, mace: dict, comps: dict, shipped: float) -> dict:
    raw = mp_data.entries_in_chemsys(cs)
    processed = process(raw)
    raw_by_id = {material_id(e): e for e in raw}
    dft = process([_entry_like(cse, cse.structure, cse.uncorrected_energy / cse.composition.num_atoms, f"wbm:{wid}")])
    mdl = process([_entry_like(cse, mace["relaxed"], mace["e_mace"], f"model:{wid}")])
    if not dft or not mdl:
        raise ValueError("MP2020 compatibility rejected the WBM entry")
    ref_signed = signed_hull_energy(processed, dft[0])
    a_signed = signed_hull_energy(processed, mdl[0])
    win_ids = {material_id(e) for e in st.window_phases(processed)}
    ref_window_signed = signed_hull_energy([e for e in processed if material_id(e) in win_ids], dft[0])
    b_comp, missing, rejected = [], [], {}
    for mid in sorted(win_ids):
        m = comps.get(mid)
        if m is None:
            missing.append(mid)
            continue
        why = rejection_reason(m, reference_per_atom=st._mp_energy_per_atom(raw_by_id[mid]))
        if why:
            rejected[mid] = why
            continue
        b_comp.append(st.mace_entry(raw_by_id[mid], m["relaxed"], m["energy_per_atom"], mid))
    n_built = len(b_comp)
    b_comp = process(b_comp)
    compat_dropped = n_built - len(b_comp)
    absent = set(missing) | set(rejected)
    on_hull = {material_id(e) for e in PhaseDiagram(processed).stable_entries}
    absent_on_hull = sorted(absent & on_hull)
    status = st.b_status_of(absent, absent_on_hull)
    b_signed = b_sub = float("nan")
    try:
        if b_comp and not absent_on_hull:
            b_signed = signed_hull_energy(b_comp, mdl[0])
        elif b_comp and all(raw_by_id[m].composition.reduced_formula in {e.composition.reduced_formula for e in b_comp}
                            for m in absent_on_hull):
            b_sub = signed_hull_energy(b_comp, mdl[0])
    except ValueError as exc:
        status = f"not scored: hull construction failed ({exc})"
    return {"wbm_id": wid, "chemsys": cs, "shipped_e_hull": shipped, "ref_signed": ref_signed, "ref_window_signed": ref_window_signed,
            "a_signed": a_signed, "b_signed": b_signed, "b_sub_signed": b_sub, "b_status": status, "n_window": len(win_ids),
            "missing": missing, "rejected": rejected, "compat_dropped": compat_dropped, "absent_on_ref_hull": absent_on_hull,
            "correction_dft": dft[0].correction / dft[0].composition.num_atoms,
            "e_mace": mace["e_mace"], "e_dft": cse.uncorrected_energy / cse.composition.num_atoms}


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    """Evaluate every sampled system whose target and competitors are available (competitor relaxations
    come from the queue: `prepare --mode-b`; anything missing is counted, never silently skipped)."""
    from harness.suites import ood

    tag = settings_tag(compute["device"], compute["dtype"])
    sample = make_sample()
    mace = {pl["wbm_id"]: pl for pl in store.load_payloads("ood", tag=tag).values() if "each_pred" in pl}
    cses = ood.load_entries(sample["ids"], ood.WBM_DIR / "mode_b_cse.json")
    summ = ood.load_summary().set_index("material_id")
    comps = st.competitor_payloads(tag)
    n_ok = n_fail = 0
    for b, items in sample["by_bin"].items():
        for x in items[: limit or None]:
            wid, cs = x["wbm_id"], "-".join(sorted(x["chemsys"].split("-")))
            key = f"{wid}@{tag}"
            m = mace.get(wid)
            # Re-evaluate the guard rather than trusting the reason stored when the job ran: the rule
            # is allowed to get stricter, and old payloads must be re-filtered without a re-run.
            why = m and compare.recheck(m.get("rejection"), m)
            if m is None or why:
                store.record_job(SUITE, key, "failed", payload={"wbm_id": wid, "bin": b},
                                 error="no usable model relaxation of the WBM structure" + (f" ({why})" if m else ""))
                n_fail += 1
                continue
            try:
                ev = evaluate(wid, cs, cses[wid], m, comps, float(summ.loc[wid, splits.HULL_COL]))
            except Exception as exc:  # noqa: BLE001 — one system must not stop the rest
                log.exception("mode (b) evaluation failed for %s", wid)
                store.record_job(SUITE, key, "failed", payload={"wbm_id": wid, "bin": b}, error=f"{type(exc).__name__}: {exc}")
                n_fail += 1
                continue
            ev["sample_bin"] = b
            store.record_job(SUITE, key, "ok", payload=ev, settings={"settings_tag": tag, "window_ev": COMPETITOR_WINDOW})
            n_ok += 1
    log.info("mode (b): %d systems evaluated, %d failed (counted)", n_ok, n_fail)


def table(tag: str) -> pd.DataFrame:
    df = pd.DataFrame([pl for pl in store.load_payloads(SUITE, tag=tag).values() if "ref_signed" in pl])
    if len(df):
        df["ref_e_hull"] = df.ref_signed.clip(lower=0)
        df["bin"] = df.ref_signed.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
        for mode in ("a", "b", "b_sub"):
            df[f"{mode}_err_mev"] = (df[f"{mode}_signed"] - df["ref_window_signed" if mode != "a" else "ref_signed"]) * 1000
    return df
