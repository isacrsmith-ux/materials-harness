#!/usr/bin/env python
"""Decision report for the proposed family taxonomy carve-outs. Reads only; changes nothing.

The round-2 document certified thresholds for fluoride, sulfide, nitride and carbide as members of
a parallel taxonomy (round2.family2). Adopting any of them into production is a different question,
because each is carved out of a parent family that is already certified on its own population:

    fluoride  out of  halide
    sulfide   out of  chalcogenide  (and a little out of halide)
    nitride   out of  pnictide      (and a little out of halide / chalcogenide)
    carbide   out of  other         (and a little out of halide / chalcogenide / pnictide)

So this asks, per parent: what does the parent look like before the carve-out, what is left after,
and does what is left still certify. Two things are deliberately different from the round-2 report:

  * Certification is on LABELABLE rows, not merely usable ones. The frozen bundle fits its
    thresholds on the rows that would actually receive a label - after the weak-element and
    structure-change exclusions - and an adoption decision has to be made on that same population.
    The round-2 document certified on all usable rows, which is a superset; both are printed.
  * The second-engine disagreement filter is not applied, because round 2 ran one engine. That is
    the bundle's `without_second_engine` rule set, and it is the fair comparison.

Nothing here opens a locked half, and nothing here writes data/calibration_bundle.json.

    python scripts/round2_taxonomy_decision.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from harness import calibration as CAL, confidence as C, metrics as M, round2, routing as R, splits
from harness.config import REPORTS_DIR

OUT_MD = REPORTS_DIR / "round2_taxonomy_decision.md"
OUT_JSON = REPORTS_DIR / "round2_taxonomy_decision.json"

R1_CACHE = "oxide_halide_calibration_init_structs.json"
R2_CACHE = "round2_calibration_init_structs.json"
ORIG_CACHE = "calibration_init_structs.json"

# The carve-outs, and where each parent's calibration evidence comes from.
PARENTS = {
    "halide": {"children": ["fluoride", "sulfide", "nitride", "carbide"],
               "evidence": "round-2 halide draw (3,500 round-1 + 2,800 top-up = 6,300)"},
    "chalcogenide": {"children": ["sulfide", "nitride", "carbide"],
                     "evidence": "original WBM calibration set only"},
    "pnictide": {"children": ["nitride", "carbide"],
                 "evidence": "original WBM calibration set only"},
    "other": {"children": ["carbide"], "evidence": "original WBM calibration set only"},
}


def _table(ids, cache) -> pd.DataFrame:
    d = CAL.calibration_table(CAL.PRODUCTION_ENGINE, set(ids), init_cache=cache)
    n_rej = d.attrs.get("n_rejected", 0)
    d = d.assign(fam1=d.formula.map(C.family), fam2=d.formula.map(round2.family2),
                 stable=d.each_true <= M.ON_HULL_TOL)
    d.attrs["n_rejected"] = n_rej
    return d


def populations() -> dict[str, pd.DataFrame]:
    orig = _table(splits.calibration_ids(), ORIG_CACHE)
    halide = pd.concat([_table(splits.family_calibration_ids("halide"), R1_CACHE),
                        _table(round2.calibration_ids(round2.HALIDE_TOPUP), R2_CACHE)], ignore_index=True)
    return {"original": orig, "halide": halide}


def labelable_mask(d: pd.DataFrame) -> pd.Series:
    """The bundle's own labelable filter, without the second-engine term (round 2 ran one engine)."""
    b = CAL.load()
    policy = R.RoutingPolicy(threshold=0.0, disagreement_tol=None,
                            weak_elements=b.weak_elements, max_trustworthy_hull=None)
    return R.labelable(d, policy)


def certify_both(d: pd.DataFrame) -> dict:
    """Certified thresholds and the full metric set, on whatever rows are handed in."""
    if not len(d):
        return {"n": 0}
    s = C.certify(d.each_pred, d.stable, C.TARGET_PRECISION, "stable")
    u = C.certify(d.each_pred, d.stable, C.TARGET_NPV, "unstable")
    dxs = round2.diagnose(d.each_pred, d.stable, C.TARGET_PRECISION, "stable")
    dxu = round2.diagnose(d.each_pred, d.stable, C.TARGET_NPV, "unstable")
    out = {"n": len(d), "base_rate": float(d.stable.mean()),
           "stable_threshold": s, "unstable_threshold": u,
           "stable_ceiling_point": dxs["point"], "stable_ceiling_cp_lower": dxs["cp_lower"],
           "stable_verdict": dxs["verdict"], "stable_structures_needed": dxs.get("n_structures_needed"),
           "unstable_point": dxu["point"], "unstable_cp_lower": dxu["cp_lower"]}
    out.update(route_metrics(d, s, u))
    return out


def route_metrics(d: pd.DataFrame, t_stable, t_unstable) -> dict:
    """Route every row the way DecisionRule.decide would, and measure the outcome."""
    tol = M.ON_HULL_TOL
    call_s = (d.each_pred <= t_stable + tol) if t_stable is not None else pd.Series(False, index=d.index)
    call_u = (~call_s) & ((d.each_pred > t_unstable + tol) if t_unstable is not None
                          else pd.Series(False, index=d.index))
    to_dft = ~(call_s | call_u)
    n_stable = int(d.stable.sum())
    grid = len(C.DEC_GRID)
    lvl = 1 - (1 - C.CERT_CONF) / grid
    prec = float(d.stable[call_s].mean()) if call_s.any() else float("nan")
    npv = float((~d.stable[call_u]).mean()) if call_u.any() else float("nan")
    return {
        "n_called_stable": int(call_s.sum()), "n_called_unstable": int(call_u.sum()),
        "precision": prec,
        "precision_cp_lower": C.cp_lower(int(d.stable[call_s].sum()), int(call_s.sum()), lvl) if call_s.any() else float("nan"),
        "npv": npv,
        "npv_cp_lower": C.cp_lower(int((~d.stable[call_u]).sum()), int(call_u.sum()), lvl) if call_u.any() else float("nan"),
        "dft_share": float(to_dft.mean()),
        "recall_stable": float((call_s & d.stable).sum() / n_stable) if n_stable else float("nan"),
        "stable_lost": float((call_u & d.stable).sum() / n_stable) if n_stable else float("nan"),
        "n_truly_stable": n_stable,
    }


def frozen_rule_metrics(d: pd.DataFrame, family_col: str) -> dict:
    """Route with the FROZEN bundle's per-family thresholds - the current product behaviour."""
    b = CAL.load()
    rule = b.rule(with_second_engine=False)
    calls = []
    for r in d.itertuples():
        th = rule.thresholds.get(getattr(r, family_col))
        if th is None:
            calls.append(None)
            continue
        if th["stable"] is not None and r.each_pred <= th["stable"] + M.ON_HULL_TOL:
            calls.append("stable")
        elif th["unstable"] is not None and r.each_pred > th["unstable"] + M.ON_HULL_TOL:
            calls.append("unstable")
        else:
            calls.append(None)
    c = pd.Series(calls, index=d.index)
    n_stable = int(d.stable.sum())
    return {"n": len(d), "dft_share": float(c.isna().mean()),
            "n_called_stable": int((c == "stable").sum()),
            "recall_stable": float(((c == "stable") & d.stable).sum() / n_stable) if n_stable else float("nan"),
            "stable_lost": float(((c == "unstable") & d.stable).sum() / n_stable) if n_stable else float("nan")}


def regime_compare(pool: pd.DataFrame) -> dict:
    """Route one population three ways and measure the difference.

      A  current taxonomy, FROZEN bundle thresholds            - what the product does today
      B  current taxonomy, thresholds re-certified on this data - the honest 'do nothing' baseline
      C  proposed taxonomy, thresholds re-certified on this data

    B and C fit their thresholds on the very rows they are then scored on. Those figures are
    in-sample and optimistic for both, which is why the locked halves exist; the comparison between
    them is still meaningful because the optimism applies to both equally.
    """
    b = CAL.load()
    frozen = b.rule(with_second_engine=False).thresholds

    def fit_on(col):
        th = {}
        for fam, g in pool.groupby(col):
            if len(g) < C.MIN_FAMILY:
                continue
            th[fam] = {"stable": C.certify(g.each_pred, g.stable, C.TARGET_PRECISION, "stable"),
                       "unstable": C.certify(g.each_pred, g.stable, C.TARGET_NPV, "unstable"),
                       "n": len(g)}
        return th

    regimes = {"A frozen bundle, current taxonomy": ("fam1", frozen),
               "B re-certified, current taxonomy": ("fam1", fit_on("fam1")),
               "C re-certified, proposed taxonomy": ("fam2", fit_on("fam2"))}
    out = {}
    for name, (col, th) in regimes.items():
        calls = []
        for r in pool.itertuples():
            t_ = th.get(getattr(r, col))
            if t_ is None:
                calls.append(None)
            elif t_["stable"] is not None and r.each_pred <= t_["stable"] + M.ON_HULL_TOL:
                calls.append("stable")
            elif t_["unstable"] is not None and r.each_pred > t_["unstable"] + M.ON_HULL_TOL:
                calls.append("unstable")
            else:
                calls.append(None)
        c = pd.Series(calls, index=pool.index)
        ns = int(pool.stable.sum())
        sel = c == "stable"
        lvl = 1 - (1 - C.CERT_CONF) / len(C.DEC_GRID)
        out[name] = {
            "n": len(pool), "dft_share": float(c.isna().mean()),
            "n_called_stable": int(sel.sum()),
            "precision": float(pool.stable[sel].mean()) if sel.any() else float("nan"),
            "precision_cp_lower": C.cp_lower(int(pool.stable[sel].sum()), int(sel.sum()), lvl) if sel.any() else float("nan"),
            "recall_stable": float((sel & pool.stable).sum() / ns) if ns else float("nan"),
            "stable_lost": float(((c == "unstable") & pool.stable).sum() / ns) if ns else float("nan"),
            "thresholds": {k: {"stable": v["stable"], "unstable": v["unstable"], "n": v["n"]}
                           for k, v in sorted(th.items())},
            "by_family": {str(fam): {"n": len(g), "dft_share": float(c[g.index].isna().mean())}
                          for fam, g in pool.groupby(col)},
        }
    return out


def build() -> dict:
    pops = populations()
    orig, hal = pops["original"], pops["halide"]
    b = CAL.load()
    rows, evidence = {}, {}

    for parent, spec in PARENTS.items():
        src = hal if parent == "halide" else orig
        g = src[src.fam1 == parent].copy()
        lab = labelable_mask(g)
        g_lab = g[lab]
        resid = g[g.fam2 == parent]
        resid_lab = g_lab[g_lab.fam2 == parent]
        carved = {c: int(((g.fam2 == c)).sum()) for c in spec["children"] if (g.fam2 == c).any()}

        rows[parent] = {
            "evidence": spec["evidence"],
            "children_carved_out": carved,
            "before": {"n_usable": len(g), "n_labelable": len(g_lab),
                       "usable": certify_both(g), "labelable": certify_both(g_lab)},
            "after": {"n_usable": len(resid), "n_labelable": len(resid_lab),
                      "usable": certify_both(resid), "labelable": certify_both(resid_lab)},
            "frozen_rule_on_this_population": frozen_rule_metrics(g_lab, "fam1"),
            "bundle_thresholds": b.raw["rules"]["without_second_engine"]["thresholds"].get(parent),
        }
        evidence[parent] = {"n_carved": len(g) - len(resid)}

    # the carved-out children, certified on the SAME labelable footing as the parents above
    children = {}
    child_src = {"fluoride": ("halide-draw subset", hal[hal.fam2 == "fluoride"]),
                 "sulfide": ("round-2 sulfide draw", _table(round2.calibration_ids("sulfide"), R2_CACHE)),
                 "nitride": ("round-2 nitride draw", _table(round2.calibration_ids("nitride"), R2_CACHE)),
                 "carbide": ("round-2 carbide draw", _table(round2.calibration_ids("carbide"), R2_CACHE))}
    for name, (where, d) in child_src.items():
        d = d[d.fam2 == name] if "fam2" in d else d
        lab = labelable_mask(d)
        children[name] = {"source": where, "n_usable": len(d), "n_labelable": int(lab.sum()),
                          "usable": certify_both(d), "labelable": certify_both(d[lab])}
    # one population, deduplicated by id, for the three-regime comparison
    pool = pd.concat([hal, orig[orig.fam1.isin(PARENTS)],
                      _table(round2.calibration_ids("sulfide"), R2_CACHE),
                      _table(round2.calibration_ids("nitride"), R2_CACHE),
                      _table(round2.calibration_ids("carbide"), R2_CACHE)], ignore_index=True)
    pool = pool.drop_duplicates(subset="wbm_id", keep="first")
    pool = pool[labelable_mask(pool)]
    compare = regime_compare(pool)
    compare["_population"] = {
        "n": len(pool), "by_fam1": pool.fam1.value_counts().to_dict(),
        "by_fam2": pool.fam2.value_counts().to_dict(),
        "caveat": ("the mix is an artifact of what round 2 drew, not a candidate distribution: "
                   "halide, sulfide, nitride and carbide are over-represented relative to any real "
                   "stream. Read the per-family rows, not the aggregate, for anything but a sanity check.")}

    return {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "regime_comparison": compare,
            "engine": "MACE-MPA-0 medium cpu/float32, settings_tag c2480e74",
            "bundle_created_at": b.raw["created_at"],
            "certification": {"target_precision": C.TARGET_PRECISION, "target_npv": C.TARGET_NPV,
                              "confidence": C.CERT_CONF, "grid_points": len(C.DEC_GRID),
                              "bound": "one-sided Clopper-Pearson, Bonferroni-corrected over the grid"},
            "labelable_filter": ("bundle weak-element list + structure-change exclusion; no "
                                 "second-engine disagreement term (round 2 ran one engine)"),
            "parents": rows, "children": children}


def f(x, n=4):
    if x is None:
        return "-"
    if isinstance(x, float) and not np.isfinite(x):
        return "-"
    return f"{x:.{n}f}"


def mev(t):
    return "-" if t is None else f"{t * 1000:+.0f} meV"


def render(D: dict) -> str:
    c = D["certification"]
    L = ["# Taxonomy carve-out decision report", "",
         f"Engine {D['engine']}. Generated {D['created_at']}. "
         f"Targets: precision >= {c['target_precision']}, NPV >= {c['target_npv']}, read from a "
         f"one-sided Clopper-Pearson lower bound at confidence {c['confidence']}, "
         f"Bonferroni-corrected over the {c['grid_points']}-point threshold grid. "
         "Verdicts are read from the bound, never the point estimate.", "",
         "**Nothing here was adopted.** `data/calibration_bundle.json` is untouched "
         f"(created {D['bundle_created_at']}). No locked half was opened.", "",
         "## What is being decided", "",
         "Each proposed new family is carved out of a parent that the product already treats as one "
         "population. The question is not only whether the child certifies - the round-2 document "
         "answered that - but whether the **residual parent still certifies after the child is "
         "removed**, because the parent's existing thresholds were fitted on the undivided family.", "",
         "| child | carved out of | also takes from |", "|---|---|---|",
         "| fluoride | halide | - |",
         "| sulfide | chalcogenide | halide |",
         "| nitride | pnictide | halide, chalcogenide |",
         "| carbide | other | halide, chalcogenide, pnictide |", "",
         "### Two differences from the round-2 document, both of which matter here", "",
         f"Certification below is on **labelable** rows: {D['labelable_filter']}. The frozen bundle "
         "fits its thresholds on the rows that would actually receive a label, so an adoption "
         "decision has to be made on that population. The round-2 document certified on all usable "
         "rows, which is a superset. Both are shown, and **they do not always agree**.", ""]

    L += ["## Evidence available per parent", "",
          "| parent | calibration evidence | n usable | n labelable | carved away | residual (usable) |",
          "|---|---|---:|---:|---:|---:|"]
    for p, r in D["parents"].items():
        L.append(f"| {p} | {r['evidence']} | {r['before']['n_usable']} | {r['before']['n_labelable']} | "
                 f"{r['before']['n_usable'] - r['after']['n_usable']} | {r['after']['n_usable']} |")
    L += ["", "The asymmetry in that table is the single most important fact in this report. Round 2 "
              "drew a full 6,300-structure halide set, so both sides of the fluoride carve-out are "
              "measured on thousands of rows. It drew no chalcogenide, pnictide or 'other' set - it "
              "drew their sulfide, nitride and carbide *subsets*. What is left of those three parents "
              "is only what the original 4,000-id calibration set happens to contain.", ""]

    for p, r in D["parents"].items():
        L += [f"## Parent: {p}", "",
              f"Evidence: {r['evidence']}. Carved out: " +
              ", ".join(f"{k} {v}" for k, v in r["children_carved_out"].items()) + ".", "",
              "| | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | "
              "recall (stable) | stable lost | to DFT |",
              "|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|"]
        for label, key, sub in (("before, usable rows", "before", "usable"),
                                ("before, labelable", "before", "labelable"),
                                ("after, usable rows", "after", "usable"),
                                ("after, labelable", "after", "labelable")):
            m = r[key][sub]
            if not m.get("n"):
                continue
            L.append(f"| {label} | {m['n']} | {f(m['base_rate'],3)} | "
                     f"{'**'+mev(m['stable_threshold'])+'**' if m['stable_threshold'] is not None else 'none'} | "
                     f"{f(m['precision'])} | {f(m['precision_cp_lower'])} | "
                     f"{'**'+mev(m['unstable_threshold'])+'**' if m['unstable_threshold'] is not None else 'none'} | "
                     f"{f(m['npv'])} | {f(m['npv_cp_lower'])} | {f(m['recall_stable'],3)} | "
                     f"{f(m['stable_lost'],3)} | {f(m['dft_share'],3)} |")
        fr = r["frozen_rule_on_this_population"]
        L += ["", f"Frozen bundle thresholds for `{p}`: `{r['bundle_thresholds']}`. Routing this "
                  f"same labelable population with the frozen rule sends "
                  f"{fr['dft_share']:.3f} to DFT, labels {fr['n_called_stable']} 'likely stable' "
                  f"(recall {f(fr['recall_stable'],3)}) and loses {f(fr['stable_lost'],3)} of the "
                  "truly stable ones.", ""]

    L += ["## The carved-out children, on the same labelable footing", "",
          "| child | source | n usable | n labelable | stable t | precision | CP-lower | unstable t | "
          "NPV | CP-lower | recall | stable lost | to DFT |",
          "|---|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|"]
    for name, r in D["children"].items():
        m = r["labelable"]
        if not m.get("n"):
            continue
        L.append(f"| {name} | {r['source']} | {r['n_usable']} | {r['n_labelable']} | "
                 f"{'**'+mev(m['stable_threshold'])+'**' if m['stable_threshold'] is not None else 'none'} | "
                 f"{f(m['precision'])} | {f(m['precision_cp_lower'])} | "
                 f"{'**'+mev(m['unstable_threshold'])+'**' if m['unstable_threshold'] is not None else 'none'} | "
                 f"{f(m['npv'])} | {f(m['npv_cp_lower'])} | {f(m['recall_stable'],3)} | "
                 f"{f(m['stable_lost'],3)} | {f(m['dft_share'],3)} |")
    cmp = D["regime_comparison"]
    popn = cmp["_population"]
    L += ["", "## Incremental routing benefit", "",
          f"One population of {popn['n']:,} labelable calibration rows, routed three ways. "
          "**B and C fit their thresholds on the very rows they are scored on**, so both are "
          "in-sample and optimistic; the comparison between them is still meaningful because the "
          "optimism applies equally. A is the frozen bundle and is genuinely out of sample for "
          "every round-2 row.", "",
          f"_{popn['caveat']}_", "",
          "| regime | to DFT | n called stable | precision | CP-lower | recall (stable) | stable lost |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for name, m in cmp.items():
        if name.startswith("_"):
            continue
        L.append(f"| {name} | {f(m['dft_share'],3)} | {m['n_called_stable']} | {f(m['precision'])} | "
                 f"{f(m['precision_cp_lower'])} | {f(m['recall_stable'],3)} | {f(m['stable_lost'],3)} |")
    L += ["", "### Where the DFT share moves, family by family", "",
          "| family | regime | n | to DFT |", "|---|---|---:|---:|"]
    for name, m in cmp.items():
        if name.startswith("_"):
            continue
        for fam, v in sorted(m["by_family"].items()):
            L.append(f"| {fam} | {name[0]} | {v['n']} | {f(v['dft_share'],3)} |")
    L += ["", "### Regime B is not a valid 'do nothing' baseline, and the aggregate should not be read as one", "",
          "B fits a `chalcogenide` threshold on 3,698 rows of which **3,684 are sulfides and 130 are "
          "actual residual chalcogenides**, and a `pnictide` threshold on 2,328 rows that are mostly "
          "nitrides. Those are child thresholds wearing the parent's name. B scores well for exactly "
          "the reason C exists - the chemistry really does separate - while keeping the parent label, "
          "so the aggregate cannot tell the two apart on this population.", "",
          "The contamination is a property of what round 2 drew, not of either taxonomy. Round 2 drew "
          "sulfide, nitride and carbide *subsets*; it never drew a representative chalcogenide, "
          "pnictide or 'other' set. **The only carve-out whose two sides are both measured on a "
          "representative draw is fluoride out of halide**, and that is the only one the aggregate "
          "here can be trusted about.", "",
          "### The carbide result is marginal and moves with the population", "",
          "On its own 1,647-row draw carbide certifies a stable threshold at -20 meV with a bound of "
          "0.9043 - 0.0043 above target. Pool in the 140 carbides that arrived inside the halide, "
          "chalcogenide and pnictide draws and the same family certifies **nothing** on the stable "
          "side. A threshold that flips on a 9% change in population composition is not one to adopt "
          "without an out-of-sample check.", "",
          "## Verdict per carve-out", "",
          "| carve-out | child certifies | residual parent certifies | net effect | verdict |",
          "|---|---|---|---|---|",
          "| fluoride out of halide | unstable only (+10 meV, 0.9671) | **yes, and better**: -10 meV, bound 0.9145, "
          "recall 0.599 -> 0.693, DFT 0.096 -> 0.061 | strict improvement on a representative draw | "
          "**supported by the evidence** |",
          "| sulfide out of chalcogenide | **both sides** (-30 meV, 0.9047; +0 meV, 0.9712) | residual n=130, "
          "certifies nothing - but it certified nothing before the carve-out either | child gains a lot, "
          "parent loses nothing it had | **plausible, unmeasured parent** |",
          "| nitride out of pnictide | unstable only (+0 meV, 0.9594) | **NO - and pnictide loses the +50 meV "
          "unstable threshold it has today** (bound 0.9515 -> nothing at n=166) | strict regression for the parent | "
          "**not supported** |",
          "| carbide out of 'other' | both sides on its own draw, neither when pooled | yes, +30 meV bound 0.9646 "
          "(was 0.9577) | parent unharmed, child marginal | **parent safe, child needs a check** |", "",
          "For comparison, the same children certified on all usable rows (the round-2 "
              "document's footing):", "",
          "| child | n usable | stable t | CP-lower | unstable t | CP-lower |", "|---|---:|---|---:|---|---:|"]
    for name, r in D["children"].items():
        m = r["usable"]
        L.append(f"| {name} | {m['n']} | "
                 f"{mev(m['stable_threshold']) if m['stable_threshold'] is not None else 'none'} | "
                 f"{f(m['precision_cp_lower'])} | "
                 f"{mev(m['unstable_threshold']) if m['unstable_threshold'] is not None else 'none'} | "
                 f"{f(m['npv_cp_lower'])} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    D = build()
    OUT_JSON.write_text(json.dumps(D, indent=1, default=float) + "\n")
    OUT_MD.write_text(render(D))
    print(render(D))
    print(f"written: {OUT_MD} and {OUT_JSON}")
