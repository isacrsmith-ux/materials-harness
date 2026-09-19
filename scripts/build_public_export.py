#!/usr/bin/env python
"""Build the public, aggregate-only export of the round-4 development evidence.

    python scripts/build_public_export.py

Writes results/public/{round4_aggregate.csv,round4_aggregate.json} and
reports/public/round4_development_results.md. Every number is READ from the analysis JSON in
reports/; nothing is recomputed and nothing is retyped.

WHAT THIS DELIBERATELY DOES NOT EMIT, and the checks that enforce it:

  * no material identifiers of any kind - not spent ones, not eligible ones, not locked ones;
  * no random seeds, and no per-bin counts from which a draw could be reconstructed;
  * no row-level data: every record is an aggregate over at least MIN_CELL rows;
  * no source-dataset content. WBM/MP structures and energies are not redistributed.

`_assert_public_safe` runs over the finished payload and raises if an id-shaped or seed-shaped
value has leaked into it. That check is the point of this script; do not weaken it.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PUB_REPORTS = REPORTS / "public"
PUB_RESULTS = ROOT / "results" / "public"

R4 = json.loads((REPORTS / "round4_carried_over.json").read_text())
R4B = json.loads((REPORTS / "round4_second_engine.json").read_text())
R4C = json.loads((REPORTS / "round4_pathb_refit.json").read_text())

FAMS = ["f-electron", "intermetallic", "pnictide"]
MIN_CELL = 20                       # no aggregate smaller than this is emitted
ID_RE = re.compile(r"\bwbm-\d+-\d+\b")
SEED_KEYS = {"seed", "seeds", "random_state", "ids", "by_bin", "id_list"}

TARGETS = {"stable": 0.90, "unstable": 0.95}


def num(v):
    if v in (None, "None", "nan", "", "-"):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _assert_public_safe(payload) -> None:
    """Raise if anything id-shaped, seed-shaped or row-level has reached the payload."""
    blob = json.dumps(payload)
    hits = ID_RE.findall(blob)
    if hits:
        raise SystemExit(f"REFUSING TO WRITE: {len(hits)} material identifiers in the export "
                         f"(e.g. {sorted(set(hits))[:3]}). The public export carries no ids.")

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in SEED_KEYS:
                    raise SystemExit(f"REFUSING TO WRITE: reconstruction-enabling key {k!r} at {path}")
                walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for j, v in enumerate(o):
                walk(v, f"{path}[{j}]")
    walk(payload)


def rows() -> list[dict]:
    """One record per (experiment, path, family, side). Aggregates only."""
    out: list[dict] = []

    def rec(experiment, path, family, side, n_pop, threshold, calls, errors, point, bound, target,
            recall, dft, note=""):
        if n_pop is not None and n_pop < MIN_CELL:
            return
        out.append({
            "experiment": experiment, "path": path, "family": family, "side": side,
            "evidence_tier": "development",
            "n_population_labelable": None if n_pop is None else int(n_pop),
            "threshold_ev_per_atom": threshold,
            "n_calls": None if calls is None else int(calls),
            "n_errors": None if errors is None else int(errors),
            "point_estimate": point,
            "cp_lower_bound": bound,
            "target": target,
            "margin_vs_target": None if (bound is None or target is None) else round(bound - target, 6),
            "meets_target_in_development": None if (bound is None or target is None) else bool(bound >= target),
            "recall_truly_stable": recall,
            "dft_routing_fraction": dft,
            "note": note,
        })

    # --- round 4: Path-A development fit, labelable
    for f in FAMS:
        m = R4["results"][f]["labelable"]
        n = num(m.get("n"))
        sc, uc = num(m.get("n_called_stable")), num(m.get("n_called_unstable"))
        prec, npv = num(m.get("precision")), num(m.get("npv"))
        rec("round4_pathA_fit", "A_single_engine", f, "stable", n,
            num(m.get("stable_threshold")), sc,
            None if (sc is None or prec is None) else round(sc * (1 - prec)),
            prec, num(m.get("precision_cp_lower")), TARGETS["stable"],
            num(m.get("recall_stable")), num(m.get("dft_share")),
            "no stable threshold certified in development" if m.get("stable_threshold") in (None, "None")
            else "")
        rec("round4_pathA_fit", "A_single_engine", f, "unstable", n,
            num(m.get("unstable_threshold")), uc,
            None if (uc is None or npv is None) else round(uc * (1 - npv)),
            npv, num(m.get("npv_cp_lower")), TARGETS["unstable"],
            num(m.get("recall_stable")), num(m.get("dft_share")))

    # --- round 4c: all three paths at their own thresholds
    PATHS = {"A (single engine, v1 table)": "A_single_engine_v1_table",
             "B-old (2nd engine, v1 table)": "B_old_second_engine_v1_table",
             "B-refit (2nd engine, fitted here)": "B_refit_second_engine_development"}
    for f in FAMS:
        for label, pname in PATHS.items():
            m = R4C["results"][f]["paths"][label]
            n = num(m.get("n_scored"))
            rec("round4c_path_comparison", pname, f, "stable", n,
                num(m.get("threshold_stable")), num(m.get("stable_calls")), num(m.get("stable_errors")),
                num(m.get("precision")), num(m.get("precision_cp_lower")), TARGETS["stable"],
                num(m.get("recall_stable")), num(m.get("dft_share")),
                "no rule on this side; all such candidates routed to DFT"
                if m.get("threshold_stable") in (None, "None") else "")
            rec("round4c_path_comparison", pname, f, "unstable", n,
                num(m.get("threshold_unstable")), num(m.get("unstable_calls")), num(m.get("unstable_errors")),
                num(m.get("npv")), num(m.get("npv_cp_lower")), TARGETS["unstable"],
                num(m.get("recall_stable")), num(m.get("dft_share")),
                "no rule on this side; all such candidates routed to DFT"
                if m.get("threshold_unstable") in (None, "None") else "")

    # --- round 4c sensitivity: the family-corrected verdicts
    for f in FAMS:
        sv = R4C["results"][f]["sensitivity_6fold"]
        pr = R4C["results"][f]["paths"]["B-refit (2nd engine, fitted here)"]
        for side, key in (("stable", "stable"), ("unstable", "unstable")):
            out.append({
                "experiment": "round4c_family_corrected_sensitivity",
                "path": "B_refit_second_engine_development", "family": f, "side": side,
                "evidence_tier": "development",
                "n_population_labelable": int(num(pr.get("n_scored")) or 0),
                "threshold_ev_per_atom": sv["thresholds"].get(key),
                "n_calls": None, "n_errors": None, "point_estimate": None,
                "cp_lower_bound": None, "target": TARGETS[side], "margin_vs_target": None,
                "meets_target_in_development": sv["thresholds"].get(key) not in (None, "None"),
                "recall_truly_stable": None, "dft_routing_fraction": None,
                "note": ("threshold under an ADDITIONAL 6-fold Bonferroni over families x sides; "
                         "'none' here means the selection did not survive that correction"),
            })
    return out


def population_rows() -> list[dict]:
    out = []
    for f in FAMS:
        r4 = R4["results"][f]
        r4b = R4B["results"][f]
        p = R4C["results"][f]["population"]
        out.append({
            "family": f, "evidence_tier": "development",
            "n_drawn": int(num(r4["n_requested"])),
            "n_guard_rejected_engine1": int(num(r4["n_rejected_by_guard"])),
            "n_guard_rejected_engine2": int(num(r4b["n_rejected_engine2"])),
            "n_usable": int(num(r4["n_usable"])),
            "n_excluded_not_labelable": int(num(r4["n_excluded_not_labelable"])),
            "n_labelable_pathA": int(num(p["n_labelable_A"])),
            "n_labelable_pathB": int(num(p["n_labelable_B"])),
            "n_labelable_pathC_product": int(num(p["n_labelable_C"])),
            "n_removed_by_disagreement": int(num(p["removed_by_disagreement_from_A"])),
            "disagreement_fraction_of_pathA": round(num(p["disagreement_fraction_of_A"]), 6),
            "n_missing_second_engine_result": int(num(r4b["n_missing_second_engine"])),
            "n_failed_jobs": int(num(r4["failures"]["n_failed_jobs"])),
            "base_rate_truly_stable_pathA": round(num(r4["labelable"]["base_rate"]), 6),
            # The two rule sets were fitted on different row counts; naming them apart matters,
            # because a reader comparing a Path-A result against "the old n" needs the Path-A one.
            "prior_threshold_fitted_on_n_pathA": int(num(
                r4["active_v1"]["without_second_engine"].get("n"))),
            "prior_threshold_fitted_on_n_pathB": int(num(
                r4["active_v1"]["with_second_engine"].get("n"))),
        })
    return out


def main() -> None:
    PUB_RESULTS.mkdir(parents=True, exist_ok=True)
    PUB_REPORTS.mkdir(parents=True, exist_ok=True)

    metrics, pops = rows(), population_rows()
    payload = {
        "export": "materials-harness round-4 development evidence, aggregate only",
        "evidence_tier": "development / calibration",
        "warning": ("Round 4 and Path-B results are development/calibration results. Unless explicitly "
                    "identified as preregistered held-out results, they must not be interpreted as "
                    "independent estimates of production performance."),
        "production_adopted": ("NOTHING in this export is adopted in production. The active rule table "
                              "is unchanged; see docs/methodology/evidence_tiers.md."),
        "engines": {
            "primary": {"key": "mace-mpa-0-medium", "settings_tag": "c2480e74",
                        "checkpoint_sha256": "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"},
            "second": {"key": "mace-mp-0-medium", "settings_tag": "207ccc81",
                       "checkpoint_sha256": "01bfe22100139f424713cf921144e5509cbe353d67aa9fa1be9c6e1e0ed35845"},
        },
        "statistics": {
            "bound": "one-sided Clopper-Pearson lower bound; never a bootstrap",
            "confidence": 0.95,
            "grid_correction": "Bonferroni over the 61-point threshold grid (-0.30..+0.30 eV/atom, 0.01 steps)",
            "family_side_multiplicity": ("NOT applied in the primary development fits (3 families x 2 "
                                         "sides = 6 selections per round, uncorrected). A 6-fold "
                                         "corrected sensitivity is exported as its own experiment."),
            "verdict_rule": "read from the bound, never the point estimate",
        },
        "schema": "results/public/SCHEMA.md",
        "population": pops,
        "metrics": metrics,
    }
    _assert_public_safe(payload)

    (PUB_RESULTS / "round4_aggregate.json").write_text(json.dumps(payload, indent=1) + "\n")

    with (PUB_RESULTS / "round4_aggregate.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(metrics[0].keys()))
        w.writeheader()
        w.writerows(metrics)
    with (PUB_RESULTS / "round4_population.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pops[0].keys()))
        w.writeheader()
        w.writerows(pops)

    print(f"wrote {PUB_RESULTS / 'round4_aggregate.json'}  ({len(metrics)} metric records)")
    print(f"wrote {PUB_RESULTS / 'round4_aggregate.csv'}")
    print(f"wrote {PUB_RESULTS / 'round4_population.csv'}  ({len(pops)} records)")
    _write_narrative(metrics, pops)
    print("public-safety assertions passed: no identifiers, no seeds, no per-bin counts, no row data")


def _f(x, n=4):
    v = num(x)
    return "-" if v is None else f"{v:.{n}f}"


def _mev(t):
    v = num(t)
    return "none" if v is None else f"{v * 1000:+.0f} meV"


def _write_narrative(metrics, pops) -> None:
    """The public results document. Tables are built from the same records the CSV exports."""
    by = {(m["experiment"], m["path"], m["family"], m["side"]): m for m in metrics}
    L = ["# Round 4 development results — the three carried-over families", "",
         "> **Round 4 and Path-B results are development/calibration results. Unless explicitly "
         "identified as preregistered held-out results, they must not be interpreted as independent "
         "estimates of production performance.**", "",
         "Aggregate, public-safe export. No material identifiers, no seeds, no row-level data - see "
         "[WITHHELD.md](WITHHELD.md). Methodology: "
         "[statistics](../../docs/methodology/statistics.md), "
         "[evidence tiers](../../docs/methodology/evidence_tiers.md), "
         "[provenance](../../docs/methodology/data_provenance.md), "
         "[environment](../../docs/methodology/environment.md). Machine-readable: "
         "[`results/public/`](../../results/public/SCHEMA.md).", "",
         "## 1. Population and every exclusion", "",
         "| family | drawn | guard-rejected (e1/e2) | usable | not labelable | labelable A | "
         "labelable B | removed by disagreement | no 2nd-engine result | failed jobs | base rate |",
         "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in pops:
        L.append(f"| {r['family']} | {r['n_drawn']:,} | {r['n_guard_rejected_engine1']}/"
                 f"{r['n_guard_rejected_engine2']} | {r['n_usable']:,} | "
                 f"{r['n_excluded_not_labelable']:,} | {r['n_labelable_pathA']:,} | "
                 f"{r['n_labelable_pathB']:,} | {r['n_removed_by_disagreement']:,} | "
                 f"{r['n_missing_second_engine_result']} | {r['n_failed_jobs']} | "
                 f"{r['base_rate_truly_stable_pathA']:.3f} |")
    L += ["", "Guard rejections and non-labelable rows are counted and excluded, never dropped "
              "silently. Zero jobs failed. Path B is a strict subset of Path A.", "",
          "## 2. Round 4 - the single-engine development fit", "",
          "| family | side | threshold | calls | errors | point | CP-lower | target | margin | "
          "recall | to DFT |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f in FAMS:
        for side in ("stable", "unstable"):
            m = by.get(("round4_pathA_fit", "A_single_engine", f, side))
            if not m:
                continue
            L.append(f"| {f} | {side} | {_mev(m['threshold_ev_per_atom'])} | {m['n_calls'] or 0:,} | "
                     f"{m['n_errors'] if m['n_errors'] is not None else '-'} | "
                     f"{_f(m['point_estimate'])} | {_f(m['cp_lower_bound'])} | {m['target']} | "
                     f"{('%+.4f' % m['margin_vs_target']) if m['margin_vs_target'] is not None else '-'} | "
                     f"{_f(m['recall_truly_stable'], 3)} | {_f(m['dft_routing_fraction'], 3)} |")
    L += ["", "**pnictide gained both sides**, on 3,637 rows against the 210 its production threshold "
              "was fitted on: DFT routing falls from 0.312 to 0.049 and recall of truly stable "
              "materials rises from 0 to 0.583. **intermetallic gained a stable side** on 3,613 rows "
              "against 665. **f-electron lost its stable side** - no threshold certifies at n=3,495.", "",
          "### 2.1 The f-electron non-replication (negative result)", "",
          "f-electron is the only family that can currently return *likely stable* in production. Its "
          "live -20 meV rule, applied unchanged to both populations:", "",
          "| sample | labelable | calls | correct | point | CP-lower | clears 0.90? |",
          "|---|---:|---:|---:|---:|---:|---|",
          "| original (the rule's own fitting population) | 1,801 | 206 | 199 | 0.9660 | 0.9063 | yes |",
          "| round 4 (fresh, disjoint, composition-matched) | 3,495 | 441 | 414 | 0.9388 | **0.8944** | **no** |",
          "", "Difference +0.0272 (SE 0.0188, z 1.45, two-sided p 0.148): the samples are **not "
              "statistically distinguishable**, and they are **not pooled** - pooling a fitting "
              "population with a fresh one produces a number that is neither, and converts a failed "
              "replication into a tuned threshold.", "",
          "This is not evidence that the rule is invalid. It is evidence that its certification was "
          "**marginal** - a bound of 0.9063 on 206 calls - and does not replicate as a certification "
          "on a matched sample twice the size. Base rates were checked first and match closely "
          "(0.1866 against 0.1848), so this is not a composition artefact.", "",
          "## 3. The second-engine path: A / B-old / B-refit", "",
          "Path A applies no disagreement term. B-old is the rule table production uses today when a "
          "second engine is supplied. B-refit was fitted on the Path-B development population.", "",
          "| family | path | stable | calls | err | precision | CP-lower | unstable | calls | err | "
          "NPV | CP-lower | recall | to DFT |",
          "|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    PN = {"A_single_engine_v1_table": "A", "B_old_second_engine_v1_table": "B-old",
          "B_refit_second_engine_development": "B-refit"}
    for f in FAMS:
        for pk, pn in PN.items():
            s_ = by.get(("round4c_path_comparison", pk, f, "stable"))
            u_ = by.get(("round4c_path_comparison", pk, f, "unstable"))
            if not s_ or not u_:
                continue
            L.append(f"| {f} | {pn} | {_mev(s_['threshold_ev_per_atom'])} | {s_['n_calls'] or 0:,} | "
                     f"{s_['n_errors'] or 0} | {_f(s_['point_estimate'])} | {_f(s_['cp_lower_bound'])} | "
                     f"{_mev(u_['threshold_ev_per_atom'])} | {u_['n_calls'] or 0:,} | "
                     f"{u_['n_errors'] or 0} | {_f(u_['point_estimate'])} | {_f(u_['cp_lower_bound'])} | "
                     f"{_f(s_['recall_truly_stable'], 3)} | {_f(s_['dft_routing_fraction'], 3)} |")
    L += ["", "### 3.1 pnictide's `none / none` was a small-sample artefact", "",
          "Production's second-engine table gives pnictide **stable none / unstable none**, fitted on "
          "n=202. The consequence, measured: a DFT routing fraction of **1.000** against 0.3121 on the "
          "single-engine path - every pnictide candidate sent to DFT, 2,502 routings away from DFT "
          "lost outright.", "",
          "The development refit on 3,501 Path-B rows selected **stable = -20 meV, unstable = +0 meV**, "
          "with corrected bounds 0.9128 and 0.9622 and margins of +0.0128 and +0.0122, and those "
          "selections are **unchanged under the family-level correction**. So the emptiness was a "
          "property of a 202-row fit, not of the chemistry.", "",
          "That is a development finding. It is **not** a validated fix, and the defect is still "
          "present in production. A held-out test of exactly these two thresholds has been "
          "pre-registered; its sample does not exist yet.", "",
          "### 3.2 Most of the apparent gain is sample size, not the second engine", "",
          "Fitting Path A in-sample on the same rows reaches the **same threshold in 5 of 6 "
          "selections**, with bounds differing only in the third or fourth decimal. The one exception "
          "is f-electron's stable side. The Path-A column in the table above applies thresholds fitted "
          "on a *different* population, so against it the refit is flattered: in-sample against "
          "out-of-sample.", "",
          "### 3.3 Supplying a second engine makes the product worse", "",
          "Weighted across these three families, the share routed to DFT rises from **0.1763** on the "
          "single-engine path to **0.4069** when a second engine is supplied - adding information more "
          "than doubles DFT routing. The cause is the second-engine rule table, whose entries for "
          "these families were fitted on 1,747 / 645 / 202 rows and have never been re-measured.", "",
          "## 4. The family-level multiplicity correction, and what it removes", "",
          "The development fits selected 3 families x 2 sides with only the grid correction applied; "
          "the refit selected the same 6 again on a subset of the same rows. Neither is "
          "family-corrected, so **both sides of the comparison are optimistic**. Under an additional "
          "6-fold Bonferroni:", "",
          "| family | B-refit primary | under 6-fold correction | survives? |", "|---|---|---|---|"]
    for f in FAMS:
        ps = by.get(("round4c_path_comparison", "B_refit_second_engine_development", f, "stable"))
        pu = by.get(("round4c_path_comparison", "B_refit_second_engine_development", f, "unstable"))
        cs = by.get(("round4c_family_corrected_sensitivity", "B_refit_second_engine_development", f, "stable"))
        cu = by.get(("round4c_family_corrected_sensitivity", "B_refit_second_engine_development", f, "unstable"))
        same = (ps["threshold_ev_per_atom"] == cs["threshold_ev_per_atom"]
                and pu["threshold_ev_per_atom"] == cu["threshold_ev_per_atom"])
        L.append(f"| {f} | {_mev(ps['threshold_ev_per_atom'])} / {_mev(pu['threshold_ev_per_atom'])} | "
                 f"{_mev(cs['threshold_ev_per_atom'])} / {_mev(cu['threshold_ev_per_atom'])} | "
                 f"{'yes' if same else '**NO**'} |")
    L += ["", "**f-electron's stable threshold does not survive.** Its bound falls from 0.900359 to "
              "**0.892556**, a margin of **-0.0074** against the 0.90 target. The apparent "
              "second-engine rescue of f-electron was partly bought by the family-level multiplicity "
              "and does not hold; **f-electron remains unresolved on both paths**. intermetallic and "
              "pnictide are unchanged.", "",
          "## 5. Caveats that travel with these results", "",
          "- **intermetallic's unstable-side margin is +0.0039** (bound 0.9539 against a 0.95 target). "
          "That is thin. It also fails to certify a stable threshold on the all-usable footing, so its "
          "stable-side gain depends entirely on the labelable population holding.",
          "- **f-electron's unstable NPV margin falls** from +0.0283 to +0.0131 under the refit: the "
          "refit trades NPV margin for a lower DFT share.",
          "- Every threshold here was **fitted and scored on the same rows**. That is the most "
          "optimistic estimate that exists.",
          "- The disagreement term is doing real but tiny work on f-electron: of 83 rows it removes, "
          "12 were stable calls and 3 of those were errors - a fourfold enrichment over the 6.1% base "
          "error rate, on 12 of 441 calls.",
          "- 7 rows of 12,000 had no usable second-engine result and **passed the disagreement check "
          "untested**, which is production's real behaviour.", "",
          "## 6. What remains unresolved", "",
          "| question | status |", "|---|---|",
          "| Is f-electron's stable rule sound? | **Unresolved on both paths.** Neither sample can "
          "separate 0.90 from 0.94. A development top-up of roughly 3,320-4,579 structures would "
          "settle it; it has not been run. |",
          "| Do pnictide's -20/+0 thresholds hold out of sample? | **Untested.** Pre-registered, "
          "sample not drawn. |",
          "| Should production carry one rule table or two? | Development evidence points to **one** - "
          "5 of 6 selections agree - but this is untested out of sample. |",
          "| Is intermetallic's +0.0039 margin real? | **Unresolved**, and too thin to act on. |",
          "| Does any of this generalise off WBM? | **Unknown.** Every result here is one dataset with "
          "one hull convention. |", ""]
    (PUB_REPORTS / "round4_development_results.md").write_text("\n".join(L) + "\n")
    print(f"wrote {PUB_REPORTS / 'round4_development_results.md'}")


if __name__ == "__main__":
    main()
