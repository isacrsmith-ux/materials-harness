#!/usr/bin/env python
"""Round 3 — do chalcogenide and 'other' still certify once their children are carved out?

Round 2 drew the children (sulfide, carbide) and never drew these parents, so the residuals could
only be measured on the 130 and 248 labelable rows the original 4,000-id calibration set happened to
hold. This uses the representative 4,000-structure draws of data/wbm_split_round3.json instead.

Three populations per parent, all on LABELABLE rows (the authoritative footing):

  residual      the parent after the carve-out - the new round-3 draw, on its own
  child         the carved-out family - the round-2 draw
  whole         the parent BEFORE the carve-out, reconstructed by subsampling the child draw down
                to its true share of the parent in the full WBM pool, so the mixture is the real
                one and Clopper-Pearson still sees integer counts

Reads only. Writes reports/round3_residual_parents.{md,json}. Opens nothing.

    python scripts/round3_residual.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from harness import calibration as CAL, confidence as C, metrics as M, round2, splits
from harness.config import REPORTS_DIR
from harness.suites import ood

import importlib.util as _u
_spec = _u.spec_from_file_location("_tax", "scripts/round2_taxonomy_decision.py")
_tax = _u.module_from_spec(_spec)
_spec.loader.exec_module(_tax)

OUT_MD = REPORTS_DIR / "round3_residual_parents.md"
OUT_JSON = REPORTS_DIR / "round3_residual_parents.json"
R3_CACHE = "round3_calibration_init_structs.json"
R2_CACHE = "round2_calibration_init_structs.json"
SEED = 20260919

CARVE = {"chalcogenide": "sulfide", "other": "carbide"}


def _table(ids, cache) -> pd.DataFrame:
    d = CAL.calibration_table(CAL.PRODUCTION_ENGINE, set(ids), init_cache=cache)
    n_rej = d.attrs.get("n_rejected", 0)
    d = d.assign(fam1=d.formula.map(C.family), fam3=d.formula.map(round2.family3),
                 stable=d.each_true <= M.ON_HULL_TOL)
    d.attrs["n_rejected"] = n_rej
    return d


def pool_shares() -> dict:
    """Each parent's true composition in the full WBM unique-prototype pool."""
    s = ood.load_summary()
    pool = s[(s["unique_prototype"] == True) & s[ood.REQUIRED].notna().all(axis=1)].copy()  # noqa: E712
    pool["fam1"] = [C.family(f) for f in pool.formula]
    sub = pool[pool.fam1.isin(CARVE)].copy()
    sub["fam3"] = [round2.family3(f) for f in sub.formula]
    return {p: {"total": int((sub.fam1 == p).sum()),
                "shares": (sub[sub.fam1 == p].fam3.value_counts(normalize=True)).to_dict()}
            for p in CARVE}


def build() -> dict:
    shares = pool_shares()
    out = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "engine": "MACE-MPA-0 medium cpu/float32, settings_tag c2480e74",
           "footing": ("labelable rows — bundle weak-element list + structure-change exclusion, no "
                       "second-engine term; the authoritative certification population"),
           "pool_shares": shares, "parents": {}}

    for parent, child in CARVE.items():
        resid = _table(round2.calibration_ids3(f"{parent}_residual"), R3_CACHE)
        kid = _table(round2.calibration_ids(child), R2_CACHE)
        kid = kid[kid.fam3 == child]

        r_lab = resid[_tax.labelable_mask(resid)]
        k_lab = kid[_tax.labelable_mask(kid)]

        # reconstruct the undivided parent at its true mixture
        sh = shares[parent]["shares"]
        w_r, w_c = sh.get(parent, 0.0), sh.get(child, 0.0)
        n_child = int(round(len(r_lab) * w_c / w_r)) if w_r else 0
        n_child = min(n_child, len(k_lab))
        whole = pd.concat([r_lab, k_lab.sample(n=n_child, random_state=SEED)], ignore_index=True)

        # head-to-head on ONE population: the reconstructed undivided parent, routed either with a
        # single pooled rule or with one rule per sub-family. Both rules are fitted on these same
        # rows, so both carry the same in-sample optimism and the comparison is fair.
        m_whole = _tax.certify_both(whole)
        m_res = _tax.certify_both(r_lab)
        m_kid = _tax.certify_both(k_lab)
        split_rules = {parent: m_res, child: m_kid}
        calls = []
        for r in whole.itertuples():
            th = split_rules[r.fam3]
            if th["stable_threshold"] is not None and r.each_pred <= th["stable_threshold"] + M.ON_HULL_TOL:
                calls.append("stable")
            elif th["unstable_threshold"] is not None and r.each_pred > th["unstable_threshold"] + M.ON_HULL_TOL:
                calls.append("unstable")
            else:
                calls.append(None)
        c = pd.Series(calls, index=whole.index)
        ns = int(whole.stable.sum())
        sel = c == "stable"
        lvl = 1 - (1 - C.CERT_CONF) / len(C.DEC_GRID)
        head_to_head = {
            "population": "the reconstructed undivided parent, at its true mixture",
            "n": len(whole), "n_truly_stable": ns,
            "pooled_one_rule": {k: m_whole[k] for k in
                                ("dft_share", "recall_stable", "stable_lost", "precision",
                                 "precision_cp_lower", "n_called_stable")},
            "split_two_rules": {
                "dft_share": float(c.isna().mean()),
                "recall_stable": float((sel & whole.stable).sum() / ns) if ns else float("nan"),
                "stable_lost": float(((c == "unstable") & whole.stable).sum() / ns) if ns else float("nan"),
                "precision": float(whole.stable[sel].mean()) if sel.any() else float("nan"),
                "precision_cp_lower": C.cp_lower(int(whole.stable[sel].sum()), int(sel.sum()), lvl) if sel.any() else float("nan"),
                "n_called_stable": int(sel.sum())},
        }

        out["parents"][parent] = {
            "head_to_head": head_to_head,
            "true_share_residual": w_r, "true_share_child": w_c,
            "n_drawn_residual": len(resid), "n_rejected_residual": int(resid.attrs["n_rejected"]),
            "n_labelable_residual": len(r_lab),
            "n_labelable_child": len(k_lab), "n_child_subsampled_for_whole": n_child,
            "whole_before_carveout": m_whole,
            "residual_after_carveout": m_res,
            "child": m_kid,
            "child_name": child,
            "old_residual_estimate": {
                "n_labelable": 130 if parent == "chalcogenide" else 248,
                "source": "original 4,000-id calibration set, reports/round2_taxonomy_decision.md"},
        }
    # The approved fluoride carve-out, judged by the SAME head-to-head test, so all three
    # carve-outs are decided on one criterion. The 6,300-structure halide draw is already a
    # representative whole-parent sample, so nothing needs reconstructing here.
    hal = pd.concat([_table(splits.family_calibration_ids("halide"), "oxide_halide_calibration_init_structs.json"),
                     _table(round2.calibration_ids(round2.HALIDE_TOPUP), R2_CACHE)], ignore_index=True)
    hal = hal[_tax.labelable_mask(hal)]
    from pymatgen.core import Composition
    # "subfam", not "sub": DataFrame.sub is subtraction, and attribute access silently returns it
    has_f = hal.formula.map(lambda x: "F" in {e.symbol for e in Composition(x).elements})
    hal = hal.assign(subfam=np.where(has_f, "fluoride", "halide"))
    m_whole = _tax.certify_both(hal)
    subs = {s: _tax.certify_both(g) for s, g in hal.groupby("subfam")}
    calls = []
    for r in hal.itertuples():
        th = subs[r.subfam]
        if th["stable_threshold"] is not None and r.each_pred <= th["stable_threshold"] + M.ON_HULL_TOL:
            calls.append("stable")
        elif th["unstable_threshold"] is not None and r.each_pred > th["unstable_threshold"] + M.ON_HULL_TOL:
            calls.append("unstable")
        else:
            calls.append(None)
    c = pd.Series(calls, index=hal.index)
    ns = int(hal.stable.sum())
    sel = c == "stable"
    lvl = 1 - (1 - C.CERT_CONF) / len(C.DEC_GRID)
    out["parents"]["halide"] = {
        "child_name": "fluoride", "true_share_residual": float((hal.subfam == "halide").mean()),
        "true_share_child": float((hal.subfam == "fluoride").mean()),
        "n_drawn_residual": int((hal.subfam == "halide").sum()), "n_rejected_residual": 0,
        "n_labelable_residual": int((hal.subfam == "halide").sum()),
        "n_labelable_child": int((hal.subfam == "fluoride").sum()),
        "n_child_subsampled_for_whole": int((hal.subfam == "fluoride").sum()),
        "whole_before_carveout": m_whole,
        "residual_after_carveout": subs["halide"], "child": subs["fluoride"],
        "old_residual_estimate": {"n_labelable": 115, "source": "original calibration set"},
        "note": ("no reconstruction needed: the 6,300-structure halide draw is already a "
                 "representative sample of the undivided parent"),
        "head_to_head": {
            "population": "the 6,300-structure halide draw, labelable rows",
            "n": len(hal), "n_truly_stable": ns,
            "pooled_one_rule": {k: m_whole[k] for k in
                                ("dft_share", "recall_stable", "stable_lost", "precision",
                                 "precision_cp_lower", "n_called_stable")},
            "split_two_rules": {
                "dft_share": float(c.isna().mean()),
                "recall_stable": float((sel & hal.stable).sum() / ns) if ns else float("nan"),
                "stable_lost": float(((c == "unstable") & hal.stable).sum() / ns) if ns else float("nan"),
                "precision": float(hal.stable[sel].mean()) if sel.any() else float("nan"),
                "precision_cp_lower": C.cp_lower(int(hal.stable[sel].sum()), int(sel.sum()), lvl) if sel.any() else float("nan"),
                "n_called_stable": int(sel.sum())}},
    }
    return out


def f(x, n=4):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return f"{x:.{n}f}"


def mev(t):
    return "-" if t is None else f"{t * 1000:+.0f} meV"


def row(label, m):
    return [label, str(m["n"]), f(m["base_rate"], 3),
            ("**" + mev(m["stable_threshold"]) + "**") if m["stable_threshold"] is not None else "none",
            f(m["precision"]), f(m["precision_cp_lower"]),
            ("**" + mev(m["unstable_threshold"]) + "**") if m["unstable_threshold"] is not None else "none",
            f(m["npv"]), f(m["npv_cp_lower"]), f(m["recall_stable"], 3),
            f(m["stable_lost"], 3), f(m["dft_share"], 3)]


def render(D: dict) -> str:
    L = ["# Round 3 — the residual parents, measured properly", "",
         f"Engine {D['engine']}. Generated {D['created_at']}. Footing: {D['footing']}.", "",
         "Round 2 drew sulfide and carbide but never drew chalcogenide or 'other', so what would be "
         "left of those parents after the carve-outs could only be read off the handful of rows the "
         "original calibration set happened to contain. These are representative 4,000-structure "
         "draws of the residuals themselves, from ids no earlier split has touched.", "",
         "**Nothing here is adopted and no locked half is opened.**", "",
         "## True composition of each parent in the WBM pool", "",
         "| parent | total in pool | residual share | child share |", "|---|---:|---:|---:|"]
    for p, r in D["parents"].items():
        tot = D["pool_shares"].get(p, {}).get("total")
        tot = f"{tot:,}" if tot else "(measured on the draw itself)"
        L.append(f"| {p} | {tot} | {r['true_share_residual']:.4f} | "
                 f"{r['child_name']} {r['true_share_child']:.4f} |")
    L += ["", "The 'whole' rows below reconstruct the undivided parent by subsampling the child draw "
              "down to that true share, so the mixture is the real one and every count stays an "
              "integer for Clopper-Pearson.", ""]
    for p, r in D["parents"].items():
        L += [f"## {p} (carving out {r['child_name']})", "",
              f"Residual draw: {r['n_drawn_residual']:,} structures, {r['n_rejected_residual']} rejected by "
              f"the guard (counted and excluded), {r['n_labelable_residual']:,} labelable. "
              f"Child draw: {r['n_labelable_child']:,} labelable, of which "
              f"{r['n_child_subsampled_for_whole']:,} are used to reconstruct the undivided parent.", "",
              f"The previous estimate of this residual rested on {r['old_residual_estimate']['n_labelable']} "
              f"labelable rows from the original calibration set.", "",
              "| population | n | base rate | stable t | precision | CP-lower | unstable t | NPV | "
              "CP-lower | recall | stable lost | to DFT |",
              "|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|"]
        L.append("| " + " | ".join(row("whole parent, before carve-out", r["whole_before_carveout"])) + " |")
        L.append("| " + " | ".join(row("residual parent, after carve-out", r["residual_after_carveout"])) + " |")
        L.append("| " + " | ".join(row(f"{r['child_name']} (the child)", r["child"])) + " |")
        h = r["head_to_head"]
        L += ["", "### Head to head, on one population", "",
              f"The reconstructed undivided parent ({h['n']:,} rows, {h['n_truly_stable']} truly "
              "stable), routed either with a single pooled rule or with one rule per sub-family. "
              "Both rule sets are fitted on these same rows, so the in-sample optimism is identical "
              "and only the structural difference remains.", "",
              "| routing | to DFT | n called stable | precision | CP-lower | recall (stable) | stable lost |",
              "|---|---:|---:|---:|---:|---:|---:|"]
        for label, key in (("one pooled rule (no carve-out)", "pooled_one_rule"),
                           ("two rules (carve-out)", "split_two_rules")):
            m = h[key]
            L.append(f"| {label} | {f(m['dft_share'],3)} | {m['n_called_stable']} | {f(m['precision'])} | "
                     f"{f(m['precision_cp_lower'])} | {f(m['recall_stable'],3)} | {f(m['stable_lost'],3)} |")
        L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    D = build()
    OUT_JSON.write_text(json.dumps(D, indent=1, default=float) + "\n")
    OUT_MD.write_text(render(D))
    print(render(D))
    print(f"written: {OUT_MD} and {OUT_JSON}")
