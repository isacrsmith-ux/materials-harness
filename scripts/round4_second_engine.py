#!/usr/bin/env python
"""Round 4b: the with_second_engine production path, on exactly the round-4 ids.

    python scripts/round4_second_engine.py reports/round4_second_engine.md

Round 4 ran ONE engine, so it could only speak to the bundle's `without_second_engine` rule set.
`harness.predict` takes the `with_second_engine` path whenever a second engine is supplied, and that
path adds a term round 4 could not evaluate: a candidate is refused a label when the two engines'
predicted hull distances differ by more than `disagreement_tol_ev`.

This scores that path on the SAME 12,000 structures - no new draw, no new ids, no locked data.

THRESHOLDS ARE FIXED. Every number here applies a threshold already in the frozen bundle, on the
population the production filter selects. Nothing is refitted: refitting on the filtered population
would be a new fit and is a separate decision.

Three populations per family, so the second engine's effect can be separated from everything else:

  A  single engine, certification footing      max_trustworthy_hull=None, no disagreement term
  B  + the disagreement term                   what `with_second_engine` actually adds
  C  + the >0.3 eV/atom refusal                the full product path (predict.MAX_TRUSTWORTHY_HULL_EV)

A is round 4's existing result, recomputed here so the comparison is on identical rows.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from harness import calibration as CAL, confidence as C, metrics as M, predict as P, round4, routing as R

sys.path.insert(0, str(Path(__file__).parent))
from round2_taxonomy_decision import route_metrics  # noqa: E402
from round4_analyse import _fmt, _mev  # noqa: E402

R4_CACHE = "round4_calibration_init_structs.json"


def joined(fam: str) -> pd.DataFrame:
    """Production-engine rows for one family with the second engine's prediction attached as pred_2.

    Rows with no usable second-engine result keep pred_2 = NaN. That is deliberate and mirrors
    production: predict warns that the disagreement check did not run and then applies the
    with_second_engine thresholds anyway. routing.labelable's `abs(NaN) > tol` is False, so such a row
    passes the disagreement term untested. The count is reported rather than hidden.
    """
    ids = set(round4.calibration_ids(fam))
    d1 = CAL.calibration_table(CAL.PRODUCTION_ENGINE, ids, init_cache=R4_CACHE)
    n_rej_1 = d1.attrs.get("n_rejected", 0)
    d2 = CAL.calibration_table(CAL.SECOND_ENGINE, ids, init_cache=R4_CACHE)
    n_rej_2 = d2.attrs.get("n_rejected", 0)
    second = d2.set_index("wbm_id").each_pred
    d = d1.assign(fam=d1.formula.map(C.family), stable=d1.each_true <= M.ON_HULL_TOL,
                  pred_2=d1.wbm_id.map(second))
    d.attrs.update({"n_requested": len(ids), "n_rejected_engine1": n_rej_1,
                    "n_rejected_engine2": n_rej_2, "n_second_engine_rows": len(d2)})
    return d


def populations(d: pd.DataFrame) -> dict[str, pd.Series]:
    """The three labelable masks, built from the bundle's own policy objects."""
    b = CAL.load()
    pol_a = b.policy(with_second_engine=False, max_trustworthy_hull=None)
    pol_b = b.policy(with_second_engine=True, max_trustworthy_hull=None)
    pol_c = b.policy(with_second_engine=True, max_trustworthy_hull=P.MAX_TRUSTWORTHY_HULL_EV)
    return {"A single engine": R.labelable(d, pol_a),
            "B + disagreement": R.labelable(d, pol_b),
            "C + >0.3 refusal (product)": R.labelable(d, pol_c)}


def analyse(fam: str) -> dict:
    d = joined(fam)
    b = CAL.load()
    rules = {"A single engine": b.rule(False).thresholds.get(fam, {}),
             "B + disagreement": b.rule(True).thresholds.get(fam, {}),
             "C + >0.3 refusal (product)": b.rule(True).thresholds.get(fam, {})}
    masks = populations(d)

    tol = b.disagreement_tol
    gap = (d.each_pred - d.pred_2).abs()
    out = {
        "family": fam,
        "n_requested": d.attrs["n_requested"],
        "n_rejected_engine1": d.attrs["n_rejected_engine1"],
        "n_rejected_engine2": d.attrs["n_rejected_engine2"],
        "n_usable_engine1": len(d),
        "n_second_engine_rows": d.attrs["n_second_engine_rows"],
        "n_missing_second_engine": int(d.pred_2.isna().sum()),
        "disagreement_tol_ev": tol,
        "n_disagree": int((gap > tol).sum()),
        "disagree_rate_of_usable": float((gap > tol).mean()),
        "gap_median_ev": float(gap.median()),
        "gap_p90_ev": float(gap.quantile(0.90)),
        "paths": {},
    }
    for label, mask in masks.items():
        sub = d[mask]
        t = rules[label]
        m = route_metrics(sub, t.get("stable"), t.get("unstable")) if len(sub) else {}
        out["paths"][label] = {
            "n_labelable": int(mask.sum()),
            "threshold_stable": t.get("stable"), "threshold_unstable": t.get("unstable"),
            "threshold_fitted_on_n": t.get("n"),
            "base_rate": float(sub.stable.mean()) if len(sub) else float("nan"),
            **m,
        }
    # How many rows the disagreement term alone removes from A, and were they the errors?
    a, bm = masks["A single engine"], masks["B + disagreement"]
    dropped = d[a & ~bm]
    ts = rules["A single engine"].get("stable")
    out["dropped_by_disagreement"] = {
        "n": len(dropped),
        "n_called_stable_under_A": int((dropped.each_pred <= ts + M.ON_HULL_TOL).sum()) if ts is not None else 0,
        "n_of_those_wrong": int((~dropped.stable[(dropped.each_pred <= ts + M.ON_HULL_TOL)]).sum())
        if ts is not None else 0,
        "base_rate": float(dropped.stable.mean()) if len(dropped) else float("nan"),
    }
    return out


def report(out_md: Path) -> dict:
    fams = round4.groups()
    res = {f: analyse(f) for f in fams}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    b = CAL.load()
    tol = b.disagreement_tol

    L = ["# Round 4b — the `with_second_engine` production path on the round-4 draw", "",
         f"Generated {now}. Production engine MACE-MPA-0 medium (`c2480e74`), second engine "
         f"MACE-MP-0 medium (`207ccc81`). **Exactly the 12,000 round-4 ids — no new structures, no new "
         f"draw, no locked data.** Disagreement tolerance from the frozen bundle: "
         f"`{tol:.6f}` eV/atom.", "",
         "**Thresholds are fixed.** Every figure applies a threshold already in "
         "`data/calibration_bundle.json` to the population the production filter selects. Nothing is "
         "refitted, and no threshold, taxonomy or exclusion was changed.", "",
         "Three populations, so the second engine's contribution is separable:", "",
         "| path | filter |", "|---|---|",
         "| **A** single engine | weak elements + structure change (`max_trustworthy_hull=None`) — "
         "the footing the bundle was fitted on and round 4 reported |",
         "| **B** + disagreement | A, plus a label refused when the two engines differ by more than "
         "the tolerance — what `with_second_engine` adds |",
         "| **C** product | B, plus the >0.3 eV/atom refusal (`predict.MAX_TRUSTWORTHY_HULL_EV`) — "
         "the actual path `harness.predict` takes |", ""]

    L += ["## 1. Second-engine coverage and disagreement", "",
          "| family | drawn | engine-1 usable | engine-2 usable | **no 2nd-engine result** | "
          "disagreeing pairs | disagree rate | median gap | p90 gap |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f in fams:
        r = res[f]
        L.append(f"| {f} | {r['n_requested']:,} | {r['n_usable_engine1']:,} | "
                 f"{r['n_second_engine_rows']:,} | **{r['n_missing_second_engine']:,}** | "
                 f"{r['n_disagree']:,} | {_fmt(r['disagree_rate_of_usable'],4)} | "
                 f"{_fmt(r['gap_median_ev'],4)} | {_fmt(r['gap_p90_ev'],4)} |")
    L += ["", "A row with **no second-engine result** passes the disagreement term untested: "
              "`abs(NaN) > tol` is False. That is production's real behaviour — `predict` warns that "
              "\"the certified thresholds in use assume the disagreement check ran\" and labels the "
              "candidate anyway — so it is reported, not silently folded in.", ""]

    L += ["## 2. The three paths, fixed thresholds", "",
          "| family | path | rule (stable / unstable) | fitted on n | n labelable | base rate | "
          "stable calls | precision | CP-lower | called unstable | NPV | CP-lower | recall | to DFT |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f in fams:
        for label, m in res[f]["paths"].items():
            if not m.get("n_labelable"):
                continue
            L.append(f"| {f} | {label} | {_mev(m['threshold_stable'])} / {_mev(m['threshold_unstable'])} | "
                     f"{_fmt(m['threshold_fitted_on_n'])} | {m['n_labelable']:,} | "
                     f"{_fmt(m['base_rate'],3)} | {m.get('n_called_stable',0):,} | "
                     f"{_fmt(m.get('precision'))} | {_fmt(m.get('precision_cp_lower'))} | "
                     f"{m.get('n_called_unstable',0):,} | {_fmt(m.get('npv'))} | "
                     f"{_fmt(m.get('npv_cp_lower'))} | {_fmt(m.get('recall_stable'),3)} | "
                     f"{_fmt(m.get('dft_share'),3)} |")
    L += ["", "`-` in a precision column means the rule makes no stable call for that family, so every "
              "such candidate goes to DFT. Bounds are one-sided Clopper-Pearson at 0.95, "
              f"Bonferroni-corrected over the {len(C.DEC_GRID)}-point grid.", ""]

    L += ["## 3. What the disagreement term actually removes", "",
          "If the second engine is earning its place, the rows it removes should be enriched in the "
          "errors the stable rule would otherwise have made.", "",
          "| family | rows removed from A | of those, called stable by A's rule | of those, wrong | "
          "base rate of removed rows |", "|---|---:|---:|---:|---:|"]
    for f in fams:
        dd = res[f]["dropped_by_disagreement"]
        L.append(f"| {f} | {dd['n']:,} | {dd['n_called_stable_under_A']:,} | {dd['n_of_those_wrong']:,} | "
                 f"{_fmt(dd['base_rate'],3)} |")
    L += [""]

    out_md.write_text("\n".join(L) + "\n")
    out_md.with_suffix(".json").write_text(json.dumps(
        {"generated_at": now, "disagreement_tol_ev": tol, "results": res},
        indent=1, default=lambda o: None if (isinstance(o, float) and not math.isfinite(o)) else str(o)) + "\n")
    print(f"wrote {out_md}\nwrote {out_md.with_suffix('.json')}")
    return res


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    report(Path(sys.argv[1]))
