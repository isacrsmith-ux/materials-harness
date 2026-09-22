#!/usr/bin/env python
"""Write the pre-registration for the f-electron held-out evaluation. Refuses to overwrite.

    python scripts/prereg_felectron_eval.py

Writes data/felectron_evaluation_preregistration.json and
reports/felectron_evaluation_preregistration.md, then stops. It DRAWS NOTHING and OPENS NOTHING: no
f-electron held-out half exists, and creating one is a separate, separately-approved step.

What is under test is the LIVE production rule, unchanged: stable -20 meV, unstable +10 meV, on both
production paths. Those values are read from the active bundle and frozen here.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import binom

from harness import calibration as CAL, confidence as C
from harness.config import DATA_DIR, REPORTS_DIR

sys.path.insert(0, str(Path(__file__).parent))
from intermetallic_sizing import _kstar, _power_at, calls_needed  # noqa: E402  reuse the validated search

OUT_JSON = DATA_DIR / "felectron_evaluation_preregistration.json"
OUT_MD = REPORTS_DIR / "felectron_evaluation_preregistration.md"
FAMILY = "f-electron"
N_HYP = 4
PRIMARY_CONF = 1 - 0.05 / N_HYP          # 0.9875
SECONDARY_CONF = 0.95
N_DRAW = 4500
POOL = 96334
MIN_CALLS = C.MIN_SELECTED
MAX_UNUSABLE_FRAC = 0.02
DEV_N = 8800                             # the combined development population the rates come from

# Design inputs: the LIVE rule applied to the 8,800-structure combined development population.
# Fixed thresholds applied, not fitted. reports/felectron_topup.{md,json} and round 4.
DEV = {
    "EA1": {"path": "A", "side": "stable",   "threshold": -0.02, "target": C.TARGET_PRECISION,
            "calls": 963,  "correct": 913,  "rate": 963 / DEV_N,  "dev_bound_family_corrected": 0.917100},
    "EA2": {"path": "A", "side": "unstable", "threshold": 0.01,  "target": C.TARGET_NPV,
            "calls": 5902, "correct": 5836, "rate": 5902 / DEV_N, "dev_bound_family_corrected": 0.982948},
    "EB1": {"path": "B", "side": "stable",   "threshold": -0.02, "target": C.TARGET_PRECISION,
            "calls": 942,  "correct": 898,  "rate": 942 / DEV_N,  "dev_bound_family_corrected": 0.923122},
    "EB2": {"path": "B", "side": "unstable", "threshold": 0.01,  "target": C.TARGET_NPV,
            "calls": 5712, "correct": 5647, "rate": 5712 / DEV_N, "dev_bound_family_corrected": 0.982596},
}
for v in DEV.values():
    v["point"] = v["correct"] / v["calls"]
PESSIMISTIC = {"EA1": 0.9171, "EA2": 0.9829, "EB1": 0.9231, "EB2": 0.9826}


def budget(n_draw, conf):
    out = {}
    for h, d in DEV.items():
        n = int(round(n_draw * d["rate"]))
        ks = _kstar(n, d["target"], conf)
        out[h] = {"expected_calls": n, "expected_errors": round(n * (1 - d["point"]), 1),
                  "min_correct_to_pass": ks,
                  "max_errors_allowed": (n - ks) if ks is not None else None,
                  "power_at_dev_point": _power_at(n, d["point"], d["target"], conf)}
    return out


def sizing():
    tbl = {"by_confidence": {}, "pessimistic_sensitivity": {}}
    for cname, conf in (("primary", PRIMARY_CONF), ("secondary", SECONDARY_CONF)):
        tbl["by_confidence"][cname] = {}
        for h, d in DEV.items():
            row = {}
            for power in (0.80, 0.90, 0.95):
                n = calls_needed(d["point"], d["target"], conf, power)
                row[f"{power:.0%}"] = {"calls": n,
                                       "structures": int(math.ceil(n / d["rate"])) if n else None}
            tbl["by_confidence"][cname][h] = row
    for h, p in PESSIMISTIC.items():
        d = DEV[h]
        n = calls_needed(p, d["target"], PRIMARY_CONF, 0.80)
        tbl["pessimistic_sensitivity"][h] = {
            "assumed_truth": p, "calls": n,
            "structures": int(math.ceil(n / d["rate"])) if n else None,
            "within_pool": bool(n and math.ceil(n / d["rate"]) <= POOL)}
    return tbl


def build():
    bundle = json.loads(CAL.BUNDLE_FILE.read_text())
    live = {p: bundle["rules"][p]["thresholds"][FAMILY]
            for p in ("without_second_engine", "with_second_engine")}
    for p, e in live.items():
        if (e["stable"], e["unstable"]) != (-0.02, 0.01):
            raise SystemExit(f"ABORT - {p} f-electron rule is not the -20/+10 meV rule this document tests")
    topup = DATA_DIR / "felectron_topup_freeze.json"
    return {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness_commit": CAL.harness_commit(),
        "state": ("PRE-REGISTERED. No f-electron held-out half exists. Nothing has been drawn, queued, "
                  "scored or opened. Drawing the sample is a separate, separately-approved step."),
        "what_is_being_tested": (
            "the LIVE f-electron production rule, unchanged: stable = -20 meV/atom and "
            "unstable = +10 meV/atom, on BOTH production paths. This is a confirmation test of a rule "
            "already in production, not a proposal to change one."),
        "why": (
            "f-electron is the only family that could return 'likely stable' in production before the "
            "pnictide promotion, and its stable side has never been tested out of sample. Round 4 found "
            "no certifiable threshold at n=3,495 and the live rule's corrected bound was 0.8944; round 4b "
            "appeared to rescue it on the second-engine path; round 4c showed that rescue did not survive "
            "the family-level correction (0.892556). A frozen development top-up to n=8,800 then "
            "certified -20 meV on BOTH paths under the FULL family correction, bounds 0.9171 and 0.9231, "
            "with the two development cohorts statistically indistinguishable (p 0.232 / 0.219). That "
            "resolved the development question and left exactly one open: does it hold out of sample?"),
        "status_of_the_evidence_so_far": (
            "DEVELOPMENT ONLY. Every f-electron figure to date is fitted and scored on the same rows. "
            "No f-electron claim has ever been tested on held-out data. This evaluation would be the "
            "first."),
        "thresholds_under_test": {
            "stable_ev_per_atom": -0.02, "unstable_ev_per_atom": 0.01,
            "source": "the active bundle, data/calibration_bundle.json, unchanged since 2026-09-12",
            "active_bundle_sha256": hashlib.sha256(CAL.BUNDLE_FILE.read_bytes()).hexdigest(),
            "live_entries": live,
            "note": ("FIXED. Not recomputed, re-derived or refitted at any point. Note the development "
                     "work selected +0 meV for the unstable side while production carries +10 meV; this "
                     "evaluation tests the LIVE +10 meV value, because the question is whether the "
                     "product's rule holds, not whether a different rule would."),
        },
        "family_definition": {
            "function": "harness.confidence.family(), UNCHANGED",
            "precedence_chain": list(C.FAMILIES),
            "rule": "first match wins; f-electron is FIRST, so it takes precedence over every other family",
            "what_f_electron_means_here": (
                "a formula containing any element in compare.F_ELECTRON. Because f-electron heads the "
                "precedence chain, an f-electron oxide, halide or intermetallic is an f-electron here. No "
                "taxonomy change is proposed, tested or implied."),
        },
        "population": {
            "usable": "not rejected by the energy-plausibility guard; rejections counted and excluded",
            "labelable": ("usable AND surviving the weak-element and structure-change exclusions - the "
                          "population calibration.fit() takes and production labels. LABELABLE IS "
                          "AUTHORITATIVE; all-usable is a secondary diagnostic that can never change a verdict."),
            "weak_elements": sorted(CAL.load().weak_elements),
            "max_trustworthy_hull": ("None for both primary paths, matching the footing the rule was "
                                     "fitted on. The product's >0.3 eV/atom refusal is reported as a "
                                     "descriptive path C only."),
        },
        "paths": {
            "A": {"rule_set": "without_second_engine", "disagreement_term": "NOT applied"},
            "B": {"rule_set": "with_second_engine",
                  "disagreement_tol_ev": CAL.load().disagreement_tol,
                  "missing_second_engine_row_behaviour": (
                      "a row with no usable second-engine result passes the disagreement term untested, "
                      "because abs(NaN) > tol is False. This is production's actual behaviour and is "
                      "pre-registered as such; the count is reported. If such rows exceed 2% of Path-A "
                      "labelable rows, Path B's hypotheses are INCONCLUSIVE.")},
        },
        "hypotheses": {
            h: {"path": d["path"], "side": d["side"], "threshold_ev_per_atom": d["threshold"],
                "metric": ("precision of the 'likely stable' call" if d["side"] == "stable"
                           else "NPV of the 'likely unstable' call"),
                "target": d["target"],
                "pass": f"Clopper-Pearson lower bound at {PRIMARY_CONF} >= {d['target']}"}
            for h, d in DEV.items()},
        "targets": {"stable_precision": C.TARGET_PRECISION, "unstable_npv": C.TARGET_NPV},
        "statistics": {
            "bound": "one-sided Clopper-Pearson lower bound. Never a bootstrap. Verdict read from the bound.",
            "primary_confidence": PRIMARY_CONF,
            "primary_confidence_rule": f"Bonferroni over the {N_HYP} pre-registered hypotheses: 1 - 0.05/{N_HYP}",
            "secondary_confidence": SECONDARY_CONF,
            "secondary_rule": "uncorrected; reported alongside; CANNOT change a verdict",
            "no_grid_correction": (
                "The thresholds are FIXED by this document before the sample exists, so nothing is "
                f"selected on held-out data and there is no grid multiplicity. The {len(C.DEC_GRID)}-fold "
                "grid Bonferroni the development fits paid does not apply and must not be added."),
            "no_family_correction": (
                "Only f-electron is tested. The 6-fold family x side correction the development analysis "
                "applied was needed because round 4 SELECTED thresholds across families; this evaluation "
                "selects nothing."),
            "why_the_level_is_less_strict_than_development": (
                "The development analysis used level 0.999863 and this evaluation uses 0.9875, which is "
                "LESS strict. That is correct, not a weakening: the development level paid for searching "
                "a 61-point grid across 6 family x side selections. Here the threshold is given in "
                "advance, so the only multiplicity is the four hypotheses. A held-out bound being higher "
                "than a development bound at similar n is an expected consequence and must not be "
                "reported as the held-out data being 'better'."),
        },
        "dependence_audit": {
            "question": "does testing Path A and Path B on the same structures change the multiplicity procedure?",
            "structural_fact": ("Path B is a strict SUBSET of Path A: B is A minus rows whose two engines "
                                "disagree beyond tolerance. The tests are nested and strongly positively "
                                "dependent, not independent."),
            "observed_on_development_data": (
                "On the 8,800-structure development population B retained 7,504 of A's 7,719 rows "
                "(97.2%); the stable side made 963 and 942 calls with 50 and 44 errors."),
            "resolution": [
                "1. Bonferroni is VALID under arbitrary dependence - it rests on Boole's inequality and "
                "assumes nothing about independence. Nesting costs power, not validity.",
                "2. The promotion rule is CONJUNCTIVE (all four must pass), making this an "
                "intersection-union test, for which an uncorrected alpha would already control the "
                "conjunctive claim. The Bonferroni correction on top is STRICTLY CONSERVATIVE.",
                "3. The conservative option is pre-registered as primary regardless.",
                "4. PRE-COMMITMENT: a hypothesis passing at 0.95 but failing at 0.9875 is a FAIL, "
                "reported as a near-miss with both bounds shown. No 'effective' correction will be "
                "estimated from the observed overlap, before or after seeing the data.",
            ],
        },
        "verdict_definitions": {
            "PASS": "the primary-confidence lower bound is >= the target",
            "FAIL": ("the primary-confidence lower bound is < the target, INCLUDING when the point "
                     "estimate is above target. There is no 'ambiguous' verdict for a primary hypothesis."),
            "INCONCLUSIVE": ("the hypothesis could not be tested, for a pre-specified reason below. It is "
                             "NOT a pass and NOT a fail, and it blocks any conclusion exactly as a fail does."),
        },
        "inconclusive_triggers": {
            "too_few_calls": f"fewer than {MIN_CALLS} calls on that side",
            "unusable_rows": (f"more than {MAX_UNUSABLE_FRAC:.0%} of drawn ids produce no usable "
                              "production-engine result. Not rescued by retrying into a different rung."),
            "missing_second_engine": (f"Path B only: more than {MAX_UNUSABLE_FRAC:.0%} of Path-A labelable "
                                      "rows lack a usable second-engine result"),
            "no_labelable_rows": "a path has zero labelable rows",
        },
        "outcome_rule": {
            "all_four_pass": (
                "the live f-electron rule is CONFIRMED out of sample on both paths. Note what this does "
                "and does not license: it confirms a rule ALREADY IN PRODUCTION, so the correct action is "
                "to record the confirmation and the provenance in the bundle. It is NOT a licence to "
                "change any threshold, and no threshold would change."),
            "any_fail": (
                "the live f-electron rule has FAILED out of sample. This is the consequential branch and "
                "it is decided here, before any data exists: a failure does NOT automatically remove or "
                "loosen the rule. It is reported as a failure, the rule's status in the bundle is marked "
                "as held-out-failed, and any change to production requires its own separate decision with "
                "its own analysis of what the alternative would cost. Removing f-electron's stable side "
                "would leave the product with pnictide as its only stable-labelling family, which is a "
                "product decision, not a statistical one."),
            "any_inconclusive": (
                "no conclusion. Reported with counts. A replacement evaluation needs a fresh "
                f"pre-registration and fresh ids; roughly {POOL - N_DRAW:,} f-electron candidates would remain."),
            "asymmetry_acknowledged": (
                "This evaluation can confirm a live rule or impugn it, and those two outcomes have very "
                "different consequences for the product. That asymmetry is recorded now so that a failure "
                "cannot later be softened by arguing the test was too strict."),
        },
        "sample": {
            "n_draw": N_DRAW,
            "eligible_pool": POOL,
            "left_unspent_after_draw": POOL - N_DRAW,
            "no_existing_half": ("There is NO f-electron locked half. Round 4 deliberately reserved none. "
                                 "This evaluation requires a FRESH draw, and consumes none of the four "
                                 "unspent locked halves (oxide, sulfide, chalcogenide, other)."),
            "eligibility": (
                "a candidate is eligible ONLY if it has never participated in anything: not the original "
                "WBM split, not the round-1/2/3 splits, not the round-4 development draw, not the "
                "f-electron development top-up, and not the pnictide held-out sample. Enforced by id and "
                "by reduced formula against every locked half and every opened held-out set."),
            "stratification": "per-bin proportional over <0, 0-0.025, 0.025-0.1, 0.1-0.3, >0.3 eV/atom",
            "engines": ("both. Production mace-mpa-0-medium (cpu/float32, tag c2480e74) and second "
                        "mace-mp-0-medium (cpu/float64, tag 207ccc81) over the SAME drawn ids, because "
                        "Path B cannot be scored without both. One runner per engine: a runner executes "
                        "one settings tag, and violating that has already caused two incidents."),
        },
        "sizing": sizing(),
        "error_budget": {"primary": budget(N_DRAW, PRIMARY_CONF),
                         "secondary": budget(N_DRAW, SECONDARY_CONF)},
        "sizing_note": (
            f"{N_DRAW} is chosen, not assumed. The binding hypothesis is EA1, Path-A stable precision, "
            f"which converts only {DEV['EA1']['rate']:.5f} of drawn structures into calls; the unstable "
            "hypotheses need under 450 structures and are effectively free. At the primary confidence "
            "EA1 needs 3,482 structures for 90% power and 4,250 for 95%. At "
            f"{N_DRAW} every hypothesis has power >= 0.96 and "
            f"{POOL - N_DRAW:,} candidates remain unspent."),
        "power_honesty": (
            "Powered against the DEVELOPMENT POINT estimates (0.9481 / 0.9533 stable, 0.9888 / 0.9886 "
            "NPV). Unlike the fluoride and intermetallic cases, the pessimistic branch here is NOT "
            "hopeless: even at the development lower bounds the effect sizes stay comfortably above "
            "target, so the sensitivity analysis is feasible within the pool on all four hypotheses. "
            "That is a genuine difference from those studies and is the reason this one is worth running. "
            "A pass still means the rule behaves as development suggested; it does not establish that "
            "true precision is far above 0.90."),
        "stop_rules": [
            "The sample is drawn ONCE and opened ONCE. data/felectron_eval_log.json records the opening; "
            "the open command refuses while it exists.",
            "No interim looks and no sequential testing. Every job completes, then the four hypotheses "
            "are scored in a single pass.",
            "If any hypothesis FAILS or is INCONCLUSIVE, stop: no other locked half is opened, no further "
            "f-electron sample is drawn, and no threshold is adjusted in either direction.",
            "intermetallic remains on hold. pnictide is closed and its held-out set is never reopened or "
            "reused. This evaluation says nothing about either.",
        ],
        "forbidden_after_the_sample_is_drawn": [
            "REFITTING ANY THRESHOLD. The -20/+10 meV values are fixed. Running certify, diagnose, "
            "best_bound or any grid search on the held-out rows is forbidden for any purpose.",
            "changing the family definition, precedence, labelable definition, weak elements, "
            "structure-change exclusion, disagreement tolerance, targets, confidence or corrections",
            "adding, dropping or reweighting hypotheses",
            "pooling these rows into any calibration or development set, now or later",
            "re-opening the sample, or drawing a second sample to append to it",
            "reporting the secondary 0.95 bound as the verdict",
            "changing the live f-electron rule in EITHER direction as an automatic consequence",
        ],
        "chain_of_custody": [
            "1. This document is committed BEFORE the sample is drawn; its sha256 is recorded in the "
            "draw and verified again at open time and at scoring time.",
            "2. The draw writes data/wbm_split_felectron_eval.json with the id list and its sha256, and "
            "asserts disjointness from every prior split, draw and held-out set by id and by reduced "
            "formula. Committed before any job is queued.",
            "3. Ids are reachable only through an accessor that raises PermissionError without "
            "unlock=True and verifies the recorded hash.",
            "4. Opening writes data/felectron_eval_log.json recording opened_at, harness commit, the "
            "sample sha256, this document's sha256, the active bundle's sha256, and both engines' keys, "
            "settings tags and checkpoint sha256 values.",
            "5. The set is registered in data/locked_sets_registry.json, its state read from the opening "
            "log rather than asserted.",
            "6. Any hash mismatch aborts the evaluation.",
        ],
        "provenance_of_design_inputs": {
            "development_population": f"{DEV_N} ids: round-4 f-electron draw (4,000) + frozen top-up (4,800)",
            "topup_freeze": {"file": "data/felectron_topup_freeze.json",
                             "sha256": hashlib.sha256(topup.read_bytes()).hexdigest() if topup.is_file() else None},
            "reports": ["reports/felectron_topup.{md,json}", "reports/round4_carried_over.{md,json}",
                        "reports/round4_pathb_refit.{md,json}"],
            "note": ("the development observations are design inputs ONLY. They are not pooled with the "
                     "held-out sample, and no held-out threshold is derived from them."),
        },
    }


def main() -> None:
    if OUT_JSON.exists() or OUT_MD.exists():
        raise SystemExit("pre-registration already written; it is not editable after the fact")
    P = build()
    OUT_JSON.write_text(json.dumps(P, indent=1) + "\n")

    def mev(t):
        return f"{t * 1000:+.0f} meV/atom"

    L = ["# Pre-registration — the f-electron held-out evaluation", "",
         f"Written {P['created_at']} at commit `{P['harness_commit']}`.", "",
         f"> **{P['state']}**", "",
         "## What is being tested", "", P["what_is_being_tested"], "",
         "### Why", "", P["why"], "",
         f"**Status of the evidence so far.** {P['status_of_the_evidence_so_far']}", "",
         "## Thresholds under test (FIXED)", "", "| side | threshold |", "|---|---|",
         f"| stable | **{mev(-0.02)}** |", f"| unstable | **{mev(0.01)}** |", "",
         P["thresholds_under_test"]["note"], "",
         f"Active bundle sha256 `{P['thresholds_under_test']['active_bundle_sha256']}`.", "",
         "## Family definition and precedence", "",
         "`" + " -> ".join(P["family_definition"]["precedence_chain"]) + "`", "",
         P["family_definition"]["what_f_electron_means_here"], "",
         "## Population", "",
         f"- **labelable** — {P['population']['labelable']}",
         f"- weak elements: {', '.join(P['population']['weak_elements'])}",
         f"- max trustworthy hull: {P['population']['max_trustworthy_hull']}", "",
         "## Hypotheses", "",
         "| id | path | side | threshold | metric | target | pass criterion |",
         "|---|---|---|---|---|---:|---|"]
    for h, d in P["hypotheses"].items():
        L.append(f"| **{h}** | {d['path']} | {d['side']} | {mev(d['threshold_ev_per_atom'])} | "
                 f"{d['metric']} | {d['target']} | CP-lower @ {PRIMARY_CONF} >= {d['target']} |")
    L += ["", "## Statistics and every correction", "",
          f"- **primary confidence {PRIMARY_CONF}** — {P['statistics']['primary_confidence_rule']}",
          f"- secondary {SECONDARY_CONF} — {P['statistics']['secondary_rule']}",
          f"- **no grid correction** — {P['statistics']['no_grid_correction']}",
          f"- **no family correction** — {P['statistics']['no_family_correction']}", "",
          f"**{P['statistics']['why_the_level_is_less_strict_than_development']}**", "",
          "## Dependence audit", "",
          f"**Structural fact.** {P['dependence_audit']['structural_fact']}", "",
          f"**Observed.** {P['dependence_audit']['observed_on_development_data']}", "",
          "**Resolution, fixed here and not revisited:**", ""]
    L += list(P["dependence_audit"]["resolution"])
    L += ["", "## Verdicts", ""]
    for k, v in P["verdict_definitions"].items():
        L.append(f"- **{k}** — {v}")
    L += ["", "### Inconclusive triggers", ""]
    for k, v in P["inconclusive_triggers"].items():
        L.append(f"- `{k}` — {v}")
    L += ["", "## Outcome rule — decided before any data exists", "",
          f"**All four pass.** {P['outcome_rule']['all_four_pass']}", "",
          f"**Any fail.** {P['outcome_rule']['any_fail']}", "",
          f"**Any inconclusive.** {P['outcome_rule']['any_inconclusive']}", "",
          f"> {P['outcome_rule']['asymmetry_acknowledged']}", "",
          "## Sample size — derived, not assumed", "",
          "| hypothesis | target | assumed truth | calls/structure | 80% | 90% | 95% |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for h, d in DEV.items():
        r = P["sizing"]["by_confidence"]["primary"][h]
        L.append(f"| {h} {d['path']} {d['side']} | {d['target']} | {d['point']:.4f} | {d['rate']:.5f} | "
                 + " | ".join(f"{r[k]['structures']:,}" for k in ("80%", "90%", "95%")) + " |")
    L += ["", f"### Chosen: **n = {N_DRAW:,}** of {POOL:,} eligible", "", P["sizing_note"], "",
          "| hypothesis | expected calls | expected errors | max errors allowed | power |",
          "|---|---:|---:|---:|---:|"]
    for h, e in P["error_budget"]["primary"].items():
        L.append(f"| {h} | {e['expected_calls']:,} | {e['expected_errors']} | "
                 f"{e['max_errors_allowed']:,} | {e['power_at_dev_point']:.3f} |")
    L += ["", "### Sensitivity at the development lower bounds", "",
          "| hypothesis | assumed truth | structures for 80% power | within pool? |",
          "|---|---:|---:|---|"]
    for h, v in P["sizing"]["pessimistic_sensitivity"].items():
        L.append(f"| {h} | {v['assumed_truth']} | "
                 f"{(f'{v[chr(115)+chr(116)+chr(114)+chr(117)+chr(99)+chr(116)+chr(117)+chr(114)+chr(101)+chr(115)]:,}' if v['structures'] else 'not reachable')} | "
                 f"{'yes' if v['within_pool'] else '**no**'} |")
    L += ["", f"**{P['power_honesty']}**", "",
          "## The sample", "",
          f"- n = {N_DRAW:,} of {POOL:,} eligible, leaving {POOL - N_DRAW:,} unspent",
          f"- {P['sample']['no_existing_half']}",
          f"- eligibility: {P['sample']['eligibility']}",
          f"- stratification: {P['sample']['stratification']}",
          f"- engines: {P['sample']['engines']}", "",
          "## Stop rules", ""]
    L += [f"- {r}" for r in P["stop_rules"]]
    L += ["", "## Forbidden once the sample is drawn", ""]
    L += [f"- {r}" for r in P["forbidden_after_the_sample_is_drawn"]]
    L += ["", "## Chain of custody", ""]
    L += list(P["chain_of_custody"])
    L += ["", "## Provenance of the design inputs", "",
          f"{P['provenance_of_design_inputs']['development_population']}. "
          f"{P['provenance_of_design_inputs']['note']}", ""]
    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT_JSON}\nwrote {OUT_MD}")
    print(f"\nsha256 (json) {hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
