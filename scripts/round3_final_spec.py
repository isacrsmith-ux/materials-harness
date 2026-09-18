#!/usr/bin/env python
"""The final proposed taxonomy, thresholds and evaluation protocol. Read-only; adopts nothing.

Decision criterion, applied identically to all three carve-outs:

    A child is carved out of its parent ONLY IF the parent's pooled rule has a genuine PRECISION
    deficit on the child - point precision below target on the child's own rows. A loose confidence
    bound on a small subgroup is not a deficit, and carving out makes it worse rather than better,
    because the child then has to certify on fewer selected calls than it had inside the parent.

That criterion separates validity from statistical power, which is the same distinction test 7 drew
between precision-limited and sample-size limited, applied one level down to subgroups.

Writes reports/round3_final_spec.{md,json}. Does not touch data/calibration_bundle.json and does not
open any locked half.

    python scripts/round3_final_spec.py
"""

from __future__ import annotations

import importlib.util as _u
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pymatgen.core import Composition

from harness import calibration as CAL, confidence as C, metrics as M, round2, splits
from harness.config import REPORTS_DIR

_spec = _u.spec_from_file_location("_tax", "scripts/round2_taxonomy_decision.py")
_tax = _u.module_from_spec(_spec)
_spec.loader.exec_module(_tax)

OUT_MD = REPORTS_DIR / "round3_final_spec.md"
OUT_JSON = REPORTS_DIR / "round3_final_spec.json"
SEED = 20260919
LVL = 1 - (1 - C.CERT_CONF) / len(C.DEC_GRID)


def tab(ids, cache) -> pd.DataFrame:
    d = CAL.calibration_table(CAL.PRODUCTION_ENGINE, set(ids), init_cache=cache)
    n_rej = d.attrs.get("n_rejected", 0)
    d = d.assign(stable=d.each_true <= M.ON_HULL_TOL, fam3=d.formula.map(round2.family3))
    d.attrs["n_rejected"] = n_rej
    return d


def has_f(df) -> pd.Series:
    return df.formula.map(lambda x: "F" in {e.symbol for e in Composition(x).elements})


def subgroup_check(child: pd.DataFrame, t: float) -> dict:
    """Does the parent's pooled threshold hold on the child's own rows?"""
    sel = child.each_pred <= t + M.ON_HULL_TOL
    n, k = int(sel.sum()), int(child.stable[sel].sum())
    point = k / n if n else float("nan")
    return {"parent_threshold": t, "n_child": len(child), "n_called_stable": n, "n_correct": k,
            "point_precision": point, "cp_lower": C.cp_lower(k, n, LVL) if n else float("nan"),
            "genuine_deficit": bool(np.isfinite(point) and point < C.TARGET_PRECISION),
            "verdict": ("carve out - the pooled rule is genuinely wrong on this chemistry"
                        if np.isfinite(point) and point < C.TARGET_PRECISION else
                        "keep pooled - no precision deficit; a loose subgroup bound is a power "
                        "problem that carving out makes worse")}


def build() -> dict:
    b = CAL.load()
    halide = pd.concat([tab(splits.family_calibration_ids("halide"), "oxide_halide_calibration_init_structs.json"),
                        tab(round2.calibration_ids(round2.HALIDE_TOPUP), "round2_calibration_init_structs.json")],
                       ignore_index=True)
    halide = halide[_tax.labelable_mask(halide)]
    flu = halide[has_f(halide)]
    hal_res = halide[~has_f(halide)]

    oxide = tab(splits.family_calibration_ids("oxide"), "oxide_halide_calibration_init_structs.json")
    oxide_lab = oxide[_tax.labelable_mask(oxide)]

    R3 = json.loads((REPORTS_DIR / "round3_residual_parents.json").read_text())
    pops, subchecks = {}, {}
    for parent, child in (("chalcogenide", "sulfide"), ("other", "carbide")):
        r = tab(round2.calibration_ids3(f"{parent}_residual"), "round3_calibration_init_structs.json")
        k = tab(round2.calibration_ids(child), "round2_calibration_init_structs.json")
        r, k = r[_tax.labelable_mask(r)], k[_tax.labelable_mask(k)]
        k = k[k.fam3 == child]
        sh = R3["parents"][parent]
        n_child = min(int(round(len(r) * sh["true_share_child"] / sh["true_share_residual"])), len(k))
        whole = pd.concat([r, k.sample(n=n_child, random_state=SEED)], ignore_index=True)
        pops[parent] = whole
        m = _tax.certify_both(whole)
        subchecks[child] = subgroup_check(k, m["stable_threshold"]) | {"parent": parent}

    m_hal = _tax.certify_both(halide)
    subchecks["fluoride"] = subgroup_check(flu, m_hal["stable_threshold"]) | {"parent": "halide"}

    # the final taxonomy: family() with fluoride inserted before halide, nothing else changed
    final = {
        "fluoride": {"population": "halide draw, F-bearing rows", "df": flu,
                     "provenance": "round 2 halide draw (6,300), labelable rows", "status": "certified"},
        "halide": {"population": "halide draw, non-F rows", "df": hal_res,
                   "provenance": "round 2 halide draw (6,300), labelable rows", "status": "certified"},
        "oxide": {"population": "round-1 oxide draw", "df": oxide_lab,
                  "provenance": "round 1 oxide draw (4,000), labelable rows", "status": "certified"},
        "chalcogenide": {"population": "reconstructed undivided parent", "df": pops["chalcogenide"],
                         "provenance": "round-3 residual draw (4,000) + round-2 sulfide draw, mixed at the "
                                       "pool's true 0.6212 / 0.3750 ratio", "status": "provisional"},
        "other": {"population": "reconstructed undivided parent", "df": pops["other"],
                  "provenance": "round-3 residual draw (4,000) + round-2 carbide draw, mixed at the "
                                "pool's true 0.8921 / 0.1079 ratio", "status": "provisional"},
    }
    thresholds = {}
    for fam, spec in final.items():
        m = _tax.certify_both(spec["df"])
        thresholds[fam] = {k: v for k, v in m.items()}
        thresholds[fam].update({"provenance": spec["provenance"], "status": spec["status"],
                                "population": spec["population"]})

    carried = {}
    for fam in ("f-electron", "intermetallic", "pnictide"):
        th = b.raw["rules"]["without_second_engine"]["thresholds"].get(fam)
        carried[fam] = {"stable_threshold": th["stable"], "unstable_threshold": th["unstable"],
                        "n": th["n"], "provenance": "frozen bundle, 2026-09-12; NOT re-measured in round 2 or 3",
                        "status": "carried over"}

    return {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "engine": "MACE-MPA-0 medium cpu/float32, settings_tag c2480e74",
            "footing": "labelable rows (weak-element + structure-change exclusions, no second engine)",
            "targets": {"precision": C.TARGET_PRECISION, "npv": C.TARGET_NPV,
                        "confidence": C.CERT_CONF, "bound": "one-sided Clopper-Pearson, Bonferroni over the grid"},
            "subgroup_checks": subchecks, "thresholds": thresholds, "carried_over": carried}


def f(x, n=4):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return f"{x:.{n}f}"


def mev(t):
    return "-" if t is None else f"{t * 1000:+.0f} meV"


def render(D: dict) -> str:
    t = D["targets"]
    L = ["# Final proposed taxonomy, thresholds and evaluation protocol", "",
         f"Engine {D['engine']}. Generated {D['created_at']}. Footing: **{D['footing']}**. "
         f"Targets: precision >= {t['precision']}, NPV >= {t['npv']}, read from a one-sided "
         f"Clopper-Pearson lower bound at confidence {t['confidence']}, Bonferroni-corrected over "
         "the threshold grid. Verdicts are read from the bound, never the point estimate.", "",
         "**This is a proposal. `data/calibration_bundle.json` is untouched and every locked half is "
         "closed. Nothing here may be adopted without explicit approval.**", "",
         "## 1. The decision criterion, and why it is not the routing comparison", "",
         "The obvious test - route one population with a pooled rule and with per-subfamily rules, "
         "and keep whichever routes better - **rejects all three carve-outs**, because pooling "
         "always buys statistical power and a split always spends it. That test is wrong on its own, "
         "and the reason is the same one that made this project use group-conditional certification "
         "in the first place: a guarantee that holds marginally over a mixture need not hold inside "
         "it.", "",
         "So the criterion is validity first, power second:", "",
         "> A child is carved out **only if** the parent's pooled rule has a genuine precision "
         "deficit on the child - point precision below target on the child's own rows. A loose "
         "confidence bound on a small subgroup is a power problem, not a validity problem, and "
         "carving out makes it worse rather than better.", "",
         "That is test 7's precision-limited / sample-size-limited distinction, applied one level "
         "down to subgroups.", "",
         "## 2. The subgroup test, all three carve-outs", "",
         "| child | parent | parent's pooled stable t | n child | called stable | correct | point precision | CP-lower | genuine deficit |",
         "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for child, s in D["subgroup_checks"].items():
        L.append(f"| {child} | {s['parent']} | {mev(s['parent_threshold'])} | {s['n_child']} | "
                 f"{s['n_called_stable']} | {s['n_correct']} | **{f(s['point_precision'])}** | "
                 f"{f(s['cp_lower'])} | {'**YES**' if s['genuine_deficit'] else 'no'} |")
    L += ["", "Only fluoride fails. Under halide's pooled -20 meV rule, 350 fluorides are labelled "
              "'likely stable' at a true precision of 0.8971 - **below the 0.90 the product "
              "promises**. Sulfide and carbide sit at 0.9448 and 0.9826 under their parents' rules; "
              "their bounds are loose only because 290 and 115 calls is not many, and splitting them "
              "off leaves them with fewer still.", ""]

    L += ["## 3. The final proposed taxonomy", "",
          "`confidence.family()` with **one** change: fluoride inserted immediately before halide. "
          "Everything else is exactly as it is today.", "",
          "```",
          "f-electron -> intermetallic -> oxide -> FLUORIDE -> halide -> chalcogenide -> pnictide -> other",
          "```", "",
          "| proposed | change | why |", "|---|---|---|",
          "| fluoride | **NEW** | the only carve-out with a genuine precision deficit under its parent |",
          "| halide | narrowed to non-fluoride | consequence of the above |",
          "| sulfide | **not adopted** | no deficit under chalcogenide (0.9448); splitting costs recall 0.575 -> 0.545 |",
          "| carbide | **not adopted** | no deficit under 'other' (0.9826, bound 0.9043); splitting collapses residual recall 0.547 -> 0.220 |",
          "| nitride | **rejected** | user decision; and it removes pnictide's only certified threshold (+50 meV, bound 0.9515 -> nothing at n=166) |",
          "| oxide, chalcogenide, pnictide, other, f-electron, intermetallic | unchanged | - |", ""]

    L += ["## 4. Proposed thresholds", "",
          "| family | status | n | base rate | stable t | precision | CP-lower | unstable t | NPV | "
          "CP-lower | recall | stable lost | to DFT | provenance |",
          "|---|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---|"]
    for fam, m in D["thresholds"].items():
        L.append(f"| **{fam}** | {m['status']} | {m['n']} | {f(m['base_rate'],3)} | "
                 f"{('**'+mev(m['stable_threshold'])+'**') if m['stable_threshold'] is not None else 'none'} | "
                 f"{f(m['precision'])} | {f(m['precision_cp_lower'])} | "
                 f"{('**'+mev(m['unstable_threshold'])+'**') if m['unstable_threshold'] is not None else 'none'} | "
                 f"{f(m['npv'])} | {f(m['npv_cp_lower'])} | {f(m['recall_stable'],3)} | "
                 f"{f(m['stable_lost'],3)} | {f(m['dft_share'],3)} | {m['provenance']} |")
    L += ["", "Carried over from the frozen bundle, **not re-measured in round 2 or round 3**:", "",
          "| family | n | stable t | unstable t | provenance |", "|---|---:|---|---|---|"]
    for fam, m in D["carried_over"].items():
        L.append(f"| {fam} | {m['n']} | {mev(m['stable_threshold'])} | {mev(m['unstable_threshold'])} | "
                 f"{m['provenance']} |")
    L += ["", "> **The proposed bundle would be of mixed provenance.** Four families would carry "
              "thresholds fitted on round-2/3 data at n in the thousands; three would carry 2026-09-12 "
              "thresholds fitted on a few hundred rows. That is not a reason to reject it - the new "
              "numbers are strictly better evidenced than what they replace - but it must be recorded "
              "in the bundle, and the carried-over families remain the weakest part of the product.", ""]

    L += ["## 5. What is certified, what is provisional, what is rejected", "",
          "### Certified on calibration data", "",
          "| conclusion | evidence |", "|---|---|",
          "| fluoride has a genuine precision deficit under halide's rule | 350 calls, point 0.8971 vs target 0.90 |",
          "| non-fluoride halide certifies both sides | n=3,247; stable -20 meV bound 0.9296, unstable +0 meV bound 0.9572 |",
          "| fluoride certifies the unstable side only | n=1,888; +10 meV, bound 0.9671; no stable threshold at any t |",
          "| oxide has no stable-side path | n=3,994 usable across 11 subfamily splits; nothing at 0.90 |",
          "| chalcogenide certifies both sides undivided | reconstructed n=5,708; stable -20 meV bound 0.9224 |",
          "| 'other' certifies both sides undivided | reconstructed n=3,935; stable -20 meV bound 0.9031 |",
          "| multi-start disagreement rises to 0.509 above 0.3 eV/atom | 1,000 candidates, 3 starts each |", "",
          "### Provisional - certified, but on a reconstructed or single-footing population", "",
          "| conclusion | why provisional |", "|---|---|",
          "| chalcogenide and 'other' thresholds | fitted on a mixture reconstructed from two draws, not one draw of the family |",
          "| every threshold in this document | fitted and scored on calibration rows; in-sample by construction |",
          "| carbide's own stable threshold (-20 meV, bound 0.9043) | flips to not certifying when carbides from other draws are pooled in |",
          "| the labelable footing itself | ruled authoritative, but never yet validated out of sample |", "",
          "### Rejected", "",
          "| conclusion | reason |", "|---|---|",
          "| the nitride carve-out | user decision; removes pnictide's only certified threshold |",
          "| the sulfide carve-out | no precision deficit under chalcogenide (0.9448) |",
          "| the carbide carve-out | no precision deficit under 'other' (0.9826) |",
          "| 'sulfide needs ~6,416 more structures' (round 2, section 15) | artefact of the all-usable footing; it certifies on labelable rows |",
          "| 'halide certifies at -70 meV' (round 2, section 14) | all-usable footing; -20 meV on labelable rows |",
          "| routing efficiency as the carve-out criterion | rejects all three carve-outs including the valid one |", ""]

    L += ["## 6. Proposed evaluation protocol", "",
          "To be frozen **before** any locked half is opened, and not changed afterwards.", "",
          "1. **Freeze** the taxonomy of section 3 and the thresholds of section 4 into "
          "`data/calibration_bundle.json`, recording per-family provenance and the labelable footing. "
          "This is the only write, and it needs explicit approval.",
          "2. **Pre-register the pass criterion**, per family and per side: the held-out precision "
          "(or NPV) lower bound must clear the same target the threshold was certified against - "
          "0.90 and 0.95 - with the same one-sided Clopper-Pearson bound. No re-tuning after the "
          "half is opened; a miss is reported as a miss.",
          "3. **Open in this order**, one at a time, each opened once and never re-opened:", "",
          "| order | locked half | n | what it settles |", "|---:|---|---:|---|",
          "| 1 | halide (round 1) | 2,000 | the fluoride carve-out and both halide-side thresholds - the only adopted change |",
          "| 2 | oxide (round 1) | 2,000 | that oxide's unstable-only routing holds out of sample |",
          "| 3 | chalcogenide residual (round 3) | 1,500 | the provisional chalcogenide threshold |",
          "| 4 | 'other' residual (round 3) | 1,500 | the provisional 'other' threshold |",
          "| - | sulfide (round 2) | 874 | **do not open.** Sulfide is not being adopted as a family; its half has nothing to settle under this taxonomy |",
          "| - | original WBM test | 4,000 | already opened once, 2026-09-12; never again |", "",
          "4. **Stop rule.** If the halide half misses, nothing else is opened and the taxonomy "
          "change is withdrawn - the remaining halves cannot rescue a change whose only justification "
          "has failed out of sample.",
          "5. **Report** each opening as its own numbered section, with the pre-registered criterion "
          "quoted before the result.", "",
          "## 7. What still needs approval", "",
          "| # | decision | recommendation |", "|---|---|---|",
          "| 1 | Adopt the fluoride carve-out and the two halide-side thresholds | yes - the only change with a measured validity failure behind it |",
          "| 2 | Adopt the re-measured oxide, chalcogenide and 'other' thresholds | yes, marked provisional - they replace thresholds fitted on 185-274 rows |",
          "| 3 | Leave sulfide, carbide and nitride pooled in their parents | yes |",
          "| 4 | Write the frozen bundle | needs your word; nothing has been written |",
          "| 5 | Open the halide half first, under the section-6 protocol | needs your word |",
          "| 6 | The sulfide locked half | recommend leaving it closed indefinitely; it has nothing to settle unless sulfide is revisited as a family |", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    D = build()
    OUT_JSON.write_text(json.dumps(D, indent=1, default=float) + "\n")
    OUT_MD.write_text(render(D))
    print(f"written: {OUT_MD} and {OUT_JSON}")
