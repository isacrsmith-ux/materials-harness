#!/usr/bin/env python
"""POST-HOC development diagnostic (written after reading reports/oqmd_development.md): are the live
stable rules' low precision on OQMD labels a same-formula-sibling artefact? Recomputes Path-A stable-call
precision for f-electron and pnictide under OQMD's own label and under a WBM-style label (formation
energy minus OQMD's hull of OTHER compositions). Development tier; changes nothing.

    python scripts/oqmd_posthoc_stable_calls.py reports/oqmd_development_posthoc.json
"""
import json
import sys

import pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import oqmd_phase3 as P
from harness import calibration as CAL, routing as R, confidence as C, metrics as M

if __name__ == "__main__":
    plan = set(json.load(open("data/oqmd_dev_plan.json"))["ids"]["ids"])
    ov = pd.read_parquet("cache/external/oqmd/overlap.parquet")
    d = ov[ov.entry_id.isin(plan) & ov.family.isin(["f-electron", "pnictide"])].copy()
    ids = set(d.entry_id)
    a = P._predictions("c2480e74", ids)
    d["each_pred"] = d.entry_id.map(lambda i: a.get(i, (None,))[0])
    d["structure_changed"] = d.entry_id.map(lambda i: a.get(i, (None, None))[1])
    d = d[d.each_pred.notna()].copy(); d["each_pred"] = d.each_pred.astype(float)
    sh = P._hull_shifts(d.formula)
    d["h_oq"] = d.formula.map(lambda f: sh[f][1])
    d["label_oqmd"] = d.stability <= M.ON_HULL_TOL                  # OQMD's own: vs every OQMD phase
    d["label_other"] = (d.delta_e - d.h_oq) <= M.ON_HULL_TOL        # WBM-style: vs OTHER compositions only
    allde = pd.read_parquet("cache/external/oqmd/entries.parquet", columns=["formula", "delta_e"])
    lowest = allde.groupby("formula").delta_e.min()
    d["lower_sibling"] = d.delta_e > d.formula.map(lowest) + 1e-6
    pol = CAL.load().policy(with_second_engine=False, max_trustworthy_hull=None)
    L = d[R.labelable(d, pol)]
    out = {}
    for fam in ("f-electron", "pnictide"):
        g = L[(L.family == fam) & (L.each_pred <= -0.02 + M.ON_HULL_TOL)]
        err = g[~g.label_oqmd]
        k2 = int(g.label_other.sum())
        out[fam] = {"stable_calls": len(g), "precision_oqmd_label": round(g.label_oqmd.mean(), 4),
                    "precision_other_compositions_label": round(g.label_other.mean(), 4),
                    "cp95_other": round(C.cp_lower(k2, len(g), 0.95), 4),
                    "errors": len(err), "errors_with_lower_same_formula_oqmd_entry": int(err.lower_sibling.sum()),
                    "errors_wrong_even_vs_other_compositions": int((~err.label_other).sum())}
    print(json.dumps(out, indent=1))
    json.dump(out, open(sys.argv[1], "w"), indent=1)
