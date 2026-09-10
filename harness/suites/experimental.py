"""Experimental check: MACE lattice constants vs measured values.

Reference: Lucero, Henderson & Scuseria, J. Phys.: Condens. Matter 24, 145504 (2012),
doi:10.1088/0953-8984/24/14/145504 (arXiv:1111.4515), Table I — the SC40 set. Per its caption the
values are room-temperature experiment, no zero-point correction, except six (Table II) that are
uncorrected extrapolations to 0 K. Those six are scored separately; beta-GaN is not run because the
source's structure label is inconsistent with its single lattice constant.

Each solid is built in its prototype at the experimental lattice constant and relaxed with MACE.
Where MP has a PBE polymorph of the same prototype, PBE's own error is recorded too, so the
report can separate "MACE reproduces PBE" from "PBE itself overestimates (~1 %)".

Coverage gap (stated in the report): semiconductors / insulators only — no metals, one oxide (MgO,
0 K value). Space-relevant oxides and metals are not yet checked against experiment.
"""

from __future__ import annotations

import csv
import logging

import numpy as np
import pandas as pd
from pymatgen.core import Lattice, Structure

from harness import compare, mp_data, store
from harness.config import DATA_DIR, settings_tag
from harness.jobs import relax_job
from harness.runner import run_pool

log = logging.getLogger(__name__)

SUITE = "experimental"
TABLE = DATA_DIR / "experimental_lattice_constants.csv"
CITATION = ("Lucero, Henderson & Scuseria, J. Phys.: Condens. Matter 24, 145504 (2012), "
            "doi:10.1088/0953-8984/24/14/145504, Table I")
PROTOTYPE_SG = {"di": 227, "zb": 216, "rs": 225, "wu": 186}
WURTZITE_U = 0.375  # ideal internal parameter; relaxed by MACE
PBE_EXPECTED_OVERESTIMATE_PCT = 1.0  # typical PBE lattice-constant overestimate


def load_table() -> list[dict]:
    with TABLE.open() as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["a_exp"] = float(r["a_exp"])
        r["c_exp"] = float(r["c_exp"]) if r["c_exp"] else None
    return rows


def build(row: dict) -> Structure:
    """Prototype structure at the experimental lattice constant(s)."""
    from pymatgen.core import Composition

    els = sorted(Composition(row["formula"]).elements, key=lambda e: e.X)  # cation first
    a, kind = row["a_exp"], row["structure"]
    if kind == "di":
        return Structure.from_spacegroup(227, Lattice.cubic(a), [els[0].symbol], [[0, 0, 0]])
    if kind == "zb":
        return Structure.from_spacegroup(216, Lattice.cubic(a), [e.symbol for e in els], [[0, 0, 0], [0.25, 0.25, 0.25]])
    if kind == "rs":
        return Structure.from_spacegroup(225, Lattice.cubic(a), [e.symbol for e in els], [[0, 0, 0], [0.5, 0.5, 0.5]])
    if kind == "wu":
        if row["c_exp"] is None:
            raise ValueError(f"{row['material']}: wurtzite without c")
        return Structure.from_spacegroup(186, Lattice.hexagonal(a, row["c_exp"]), [e.symbol for e in els],
                                         [[1 / 3, 2 / 3, 0], [1 / 3, 2 / 3, WURTZITE_U]])
    raise ValueError(f"unknown structure type {kind}")


def mp_pbe_lattice(row: dict, proto: Structure) -> dict | None:
    """Lowest-hull MP PBE polymorph in the same prototype (anonymized StructureMatcher)."""
    try:
        cands = mp_data.pbe_candidates(row["formula"])
    except Exception as exc:  # noqa: BLE001
        log.warning("%s: MP lookup failed: %s", row["material"], exc)
        return None
    match = [c for c in cands if c["spacegroup_number"] == PROTOTYPE_SG[row["structure"]]
             and compare.same_prototype(proto, c["structure"])]
    if not match:
        return None
    best = min(match, key=lambda c: (c["energy_above_hull"] is None, c["energy_above_hull"] or 0.0))
    cell = compare.conventional_cell(best["structure"])
    return {"material_id": best["material_id"], "a": cell.a, "c": cell.c, "e_above_hull": best["energy_above_hull"],
            "functional": best["functional"], "task_id": best["task_id"]}


def _record(job: dict, res: dict) -> None:
    row, key = job["row"], job["job_key"]
    if res.get("status") != "ok":
        store.record_job(SUITE, key, res["status"], payload={"material": row["material"]},
                         error=res.get("error"), runtime_s=res.get("job_wall_s"))
        log.warning("%s %s: %s", row["material"], res["status"], res.get("error"))
        return
    relaxed = res["relaxed"]
    cell = compare.conventional_cell(relaxed)
    keeps_sg = cell.spacegroup == PROTOTYPE_SG[row["structure"]]
    pbe = job["pbe"]
    params = [("a", row["a_exp"], cell.a, pbe["a"] if pbe else None)]
    if row["structure"] == "wu":
        params.append(("c", row["c_exp"], cell.c, pbe["c"] if pbe else None))
    exp_src = f"{CITATION} [{'room temperature' if row['status'] == 'rt' else row['status']}]"
    flags = {"status": row["status"], "keeps_prototype_sg": keeps_sg, "sim_spacegroup": cell.spacegroup,
             "converged": res["converged"], "note": row["note"] or None}
    base = {"suite": SUITE, "job_key": key, "structure": f"{row['material']} ({row['structure']})",
            "formula": row["formula"], "family": row["structure"], "units": "Å", "flags": flags,
            "settings": res["metadata"], "runtime_s": res["wall_time_s"]}
    rows, out = [], {"material": row["material"], "formula": row["formula"], "structure": row["structure"],
                     "status": row["status"], "keeps_prototype_sg": keeps_sg, "converged": res["converged"],
                     "wall_time_s": res["wall_time_s"], "pbe_material_id": pbe["material_id"] if pbe else None}
    for p, exp, sim, pbe_val in params:
        err = compare.pct_error(sim, exp)
        rows.append({**base, "test": f"{p}_vs_experiment", "simulated_value": sim, "reference_value": exp,
                     "reference_provenance": "experimental", "reference_source": exp_src,
                     "error_abs": sim - exp, "error_pct": err})
        out[f"{p}_exp"], out[f"{p}_mace"], out[f"{p}_err_pct"] = exp, sim, err
        if pbe_val is not None:
            rows.append({**base, "test": f"{p}_vs_mp_pbe", "simulated_value": sim, "reference_value": pbe_val,
                         "reference_provenance": "mp_computed",
                         "reference_source": f"{pbe['material_id']} {pbe['functional']} (task {pbe['task_id']})",
                         "error_abs": sim - pbe_val, "error_pct": compare.pct_error(sim, pbe_val)})
            out[f"{p}_pbe"] = pbe_val
            out[f"{p}_pbe_err_pct"] = compare.pct_error(pbe_val, exp)
            out[f"{p}_mace_vs_pbe_pct"] = compare.pct_error(sim, pbe_val)
    store.record_results(rows)
    store.record_job(SUITE, key, "ok", payload={**out, "relaxed": relaxed}, settings=res["metadata"],
                     runtime_s=res["wall_time_s"])
    log.info("%-10s %s a %+6.2f%% vs exp%s  SG %s", row["material"], row["status"], out["a_err_pct"],
             f" (PBE {out['a_pbe_err_pct']:+.2f}%)" if "a_pbe_err_pct" in out else " (no MP PBE polymorph)",
             cell.spacegroup)


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    tag = settings_tag(compute["device"], compute["dtype"])
    rows = load_table()[: limit or None]
    done = store.completed_keys(SUITE, retry_failed=retry_failed)
    jobs = []
    for row in rows:
        key = f"{row['material']}:{row['structure']}@{tag}"
        if row["status"] == "ambiguous":
            log.warning("not run: %s — %s", row["material"], row["note"])
            store.record_job(SUITE, key, "skipped", payload={"material": row["material"], "status": "ambiguous"},
                             error=row["note"])
            continue
        if key in done:
            continue
        proto = build(row)
        jobs.append({"job_key": key, "row": row, "structure": proto, "pbe": mp_pbe_lattice(row, proto),
                     "device": compute["device"], "dtype": compute["dtype"]})
    log.info("%d experimental-check jobs to run", len(jobs))
    run_pool(relax_job, jobs, compute["workers"], compute["threads_per_worker"], on_result=_record)
    print_summary(tag)


def table(tag: str) -> pd.DataFrame:
    return pd.DataFrame([pl for pl in store.load_payloads(SUITE, tag=tag).values() if "a_err_pct" in pl])


def summarize(df: pd.DataFrame) -> dict:
    def stats(col):
        v = df[col].dropna().astype(float) if col in df else pd.Series(dtype=float)
        return (float(v.mean()), float(v.abs().mean()), len(v)) if len(v) else (float("nan"),) * 2 + (0,)

    return {"mace_vs_exp": stats("a_err_pct"), "pbe_vs_exp": stats("a_pbe_err_pct"),
            "mace_vs_pbe": stats("a_mace_vs_pbe_pct")}


def print_summary(tag: str) -> None:
    df = table(tag)
    if df.empty:
        print("No experimental-check results yet.")
        return
    print(f"\n=== EXPERIMENTAL CHECK (settings {tag}) — {CITATION} ===")
    for label, sub in [("room temperature (headline)", df[df.status == "rt"]),
                       ("0 K extrapolated (reported separately)", df[df.status == "zero_k"])]:
        s = summarize(sub)
        print(f"{label:<40} n={len(sub):>2}  a: MACE vs exp mean {s['mace_vs_exp'][0]:+.2f}% (MAE {s['mace_vs_exp'][1]:.2f}%)"
              f"  |  MP PBE vs exp mean {s['pbe_vs_exp'][0]:+.2f}% (n={s['pbe_vs_exp'][2]})"
              f"  |  MACE vs PBE mean {s['mace_vs_pbe'][0]:+.2f}%   [expected PBE overestimate ~+{PBE_EXPECTED_OVERESTIMATE_PCT:.0f}%]")
    lost = df[~df.keeps_prototype_sg]
    if len(lost):
        print("left the prototype symmetry:", lost.material.tolist())
    cols = ["material", "structure", "status", "a_exp", "a_mace", "a_err_pct", "a_pbe", "a_pbe_err_pct",
            "a_mace_vs_pbe_pct", "c_err_pct", "keeps_prototype_sg", "pbe_material_id"]
    print(df.sort_values("a_err_pct", key=abs, ascending=False)[[c for c in cols if c in df]]
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))
