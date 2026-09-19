#!/usr/bin/env python
"""Write the pre-registration for a fresh pnictide held-out evaluation. Refuses to overwrite.

    python scripts/prereg_pnictide_eval.py

Writes data/pnictide_evaluation_preregistration.{json} and
reports/pnictide_evaluation_preregistration.md, then stops. It DRAWS NOTHING and OPENS NOTHING: the
evaluation sample does not exist until a separate, separately-approved step creates it.

The thresholds under test are frozen in this document, not read from the bundle: the active bundle's
with_second_engine entry for pnictide is `none / none`, which is the defect this evaluation exists to
test a fix for.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
from scipy.stats import binom

from harness import calibration as CAL, confidence as C
from harness.config import DATA_DIR, REPORTS_DIR

OUT_JSON = DATA_DIR / "pnictide_evaluation_preregistration.json"
OUT_MD = REPORTS_DIR / "pnictide_evaluation_preregistration.md"

N_HYP = 4                       # A-stable, A-unstable, B-stable, B-unstable
PRIMARY_CONF = 1 - 0.05 / N_HYP          # 0.9875
SECONDARY_CONF = 0.95
N_DRAW = 3500
POOL_ELIGIBLE = 5432
MIN_CALLS = C.MIN_SELECTED       # 20; below this a side is INCONCLUSIVE, not a pass or a fail
MAX_UNUSABLE_FRAC = 0.02

T_STABLE, T_UNSTABLE = -0.02, 0.0

# Development rates, from the round-4 pnictide draw (4,000 structures). Design inputs only.
DEV = {
    "A stable":   {"rate": 306 / 4000,  "truth": 0.960784, "target": C.TARGET_PRECISION,
                   "dev_calls": 306,  "dev_errors": 12, "dev_bound": 0.9127943399138314},
    "A unstable": {"rate": 3154 / 4000, "truth": 0.974001, "target": C.TARGET_NPV,
                   "dev_calls": 3154, "dev_errors": 82, "dev_bound": 0.9638281795801172},
    "B stable":   {"rate": 306 / 4000,  "truth": 0.960784, "target": C.TARGET_PRECISION,
                   "dev_calls": 306,  "dev_errors": 12, "dev_bound": 0.9127943399138314},
    "B unstable": {"rate": 3018 / 4000, "truth": 0.972830, "target": C.TARGET_NPV,
                   "dev_calls": 3018, "dev_errors": 82, "dev_bound": 0.9622070964334437},
}
PESSIMISTIC = {"A stable": 0.9128, "A unstable": 0.9638, "B stable": 0.9128, "B unstable": 0.9622}


def calls_needed(p_true, target, conf, power, cap=40000):
    for n in range(20, cap, 5):
        ks = next((k for k in range(n + 1) if C.cp_lower(k, n, conf) >= target), None)
        if ks is not None and 1 - binom.cdf(ks - 1, n, p_true) >= power:
            return n
    return None


def budget(n_draw: int, conf: float) -> dict:
    out = {}
    for h, d in DEV.items():
        n = int(round(n_draw * d["rate"]))
        ks = next((k for k in range(n + 1) if C.cp_lower(k, n, conf) >= d["target"]), None)
        out[h] = {
            "expected_calls": n,
            "expected_errors": round(n * (1 - d["truth"]), 1),
            "min_correct_to_pass": ks,
            "max_errors_allowed": (n - ks) if ks is not None else None,
            "power_at_dev_point": float(1 - binom.cdf(ks - 1, n, d["truth"])) if ks is not None else 0.0,
        }
    return out


def sizing() -> dict:
    tbl = {}
    for cname, conf in (("primary", PRIMARY_CONF), ("secondary", SECONDARY_CONF)):
        tbl[cname] = {}
        for h, d in DEV.items():
            row = {}
            for power in (0.80, 0.90, 0.95):
                n = calls_needed(d["truth"], d["target"], conf, power)
                row[f"{power:.0%}"] = {"calls": n,
                                       "structures": int(np.ceil(n / d["rate"])) if n else None}
            tbl[cname][h] = row
    pess = {}
    for h, p in PESSIMISTIC.items():
        n = calls_needed(p, DEV[h]["target"], PRIMARY_CONF, 0.80)
        pess[h] = {"assumed_truth": p, "calls": n,
                   "structures": int(np.ceil(n / DEV[h]["rate"])) if n else None}
    return {"by_confidence": tbl, "pessimistic_sensitivity": pess}


def build() -> dict:
    bundle_sha = hashlib.sha256(CAL.BUNDLE_FILE.read_bytes()).hexdigest()
    dev_a = REPORTS_DIR / "round4_carried_over.json"
    dev_b = REPORTS_DIR / "round4_pathb_refit.json"
    return {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness_commit": CAL.harness_commit(),
        "state": ("PRE-REGISTERED. The evaluation sample DOES NOT EXIST YET. Nothing has been drawn, "
                  "queued, scored or opened. Drawing it is a separate, separately-approved step."),
        "what_is_being_tested": (
            "the shared-rule hypothesis for pnictide: that the FIXED thresholds stable = -20 meV/atom "
            "and unstable = +0 meV/atom satisfy the certification targets on genuinely unseen pnictide "
            "structures, under BOTH production paths (single engine and second-engine/disagreement), "
            "so that one shared rule table would serve both."),
        "why": (
            "The active bundle's with_second_engine entry for pnictide is stable=None/unstable=None, "
            "fitted on 202 rows in 2026-09-12. Round 4b measured the consequence: when a second engine "
            "is supplied, 100% of pnictide candidates are routed to DFT (DFT share 1.000 against 0.3121 "
            "single-engine). Round 4 and round 4c fitted -20/+0 meV on 3,637 (Path A) and 3,501 (Path B) "
            "development rows and reached the SAME thresholds on both paths, with bounds 0.9128/0.9638 "
            "and 0.9128/0.9622. That is development evidence, fitted and scored on the same rows, and it "
            "is not validated. This evaluation is what would validate it."),
        "thresholds_under_test": {
            "stable_ev_per_atom": T_STABLE,
            "unstable_ev_per_atom": T_UNSTABLE,
            "frozen_here_not_read_from_bundle": (
                "The bundle's with_second_engine pnictide entry is none/none, so the bundle cannot be "
                "the authority for what is being tested. THIS DOCUMENT is the authority. The values "
                "above are fixed and are not recomputed, re-derived or refitted at any point."),
            "provenance": {
                "path_A_fit": "reports/round4_carried_over.{md,json}, pnictide labelable, n=3,637",
                "path_B_fit": "reports/round4_pathb_refit.{md,json}, B-refit, n=3,501",
                "path_A_fit_sha256": hashlib.sha256(dev_a.read_bytes()).hexdigest() if dev_a.is_file() else None,
                "path_B_fit_sha256": hashlib.sha256(dev_b.read_bytes()).hexdigest() if dev_b.is_file() else None,
            },
            "active_bundle_sha256": bundle_sha,
            "active_bundle_entries_for_reference": {
                "without_second_engine": {"stable": None, "unstable": 0.05, "n": 210},
                "with_second_engine": {"stable": None, "unstable": None, "n": 202},
            },
        },
        "family_definition": {
            "function": "harness.confidence.family(), UNCHANGED - no round-2/3/4 overlay",
            "precedence_chain": list(C.FAMILIES),
            "rule": "first match wins",
            "what_pnictide_means_here": (
                "a formula reaching 'pnictide' in that chain: it contains an N/P/As/Sb/Bi pnictogen AND "
                "is NOT f-electron, NOT wholly metallic (intermetallic), NOT oxygen-bearing, NOT "
                "halogen-bearing and NOT chalcogen-bearing. Nitrides are included - nitride was "
                "REJECTED as a carve-out in round 2 and N stays in pnictide. No taxonomy change is "
                "proposed, tested or implied by this evaluation."),
        },
        "population": {
            "usable": "not rejected by the energy-plausibility guard; rejections counted and excluded",
            "labelable": (
                "usable AND surviving the weak-element and structure-change exclusions - the population "
                "calibration.fit() takes and the population production labels. LABELABLE IS "
                "AUTHORITATIVE (user ruling 2026-09-18). All-usable figures may be reported as a "
                "secondary diagnostic and can never change a verdict."),
            "weak_elements": sorted(CAL.load().weak_elements),
            "structure_change_exclusion": "routing.RoutingPolicy.route_structure_change=True",
            "max_trustworthy_hull": (
                "None for both primary paths, matching the footing the thresholds were fitted on. The "
                "product's >0.3 eV/atom refusal (predict.MAX_TRUSTWORTHY_HULL_EV) is reported as a "
                "SECONDARY descriptive path C and cannot change any verdict."),
        },
        "paths": {
            "A": {"name": "single engine", "rule_set": "without_second_engine",
                  "filter": "weak elements + structure change",
                  "disagreement_term": "NOT applied"},
            "B": {"name": "second engine supplied", "rule_set": "with_second_engine",
                  "filter": "A, plus refuse a label when |pred_engine1 - pred_engine2| > tol",
                  "disagreement_tol_ev": CAL.load().disagreement_tol,
                  "second_engine": "mace-mp-0-medium, cpu/float64, tag 207ccc81",
                  "missing_second_engine_row_behaviour": (
                      "A row with no usable second-engine result passes the disagreement term untested, "
                      "because abs(NaN) > tol is False. This is production's actual behaviour and is "
                      "PRE-REGISTERED as such. The count of such rows is reported. If they exceed 2% of "
                      "Path-A labelable rows, Path B's hypotheses are INCONCLUSIVE.")},
            "C": {"name": "product path", "status": "SECONDARY, descriptive only, never a verdict"},
        },
        "targets": {"stable_precision": C.TARGET_PRECISION, "unstable_npv": C.TARGET_NPV},
        "statistics": {
            "bound": ("one-sided Clopper-Pearson lower bound. Never a bootstrap. The verdict is read "
                      "from the bound, never from the point estimate."),
            "primary_confidence": PRIMARY_CONF,
            "primary_confidence_rule": f"Bonferroni over the {N_HYP} pre-registered hypotheses: 1 - 0.05/{N_HYP}",
            "secondary_confidence": SECONDARY_CONF,
            "secondary_rule": "uncorrected; reported alongside; CANNOT change a verdict",
            "no_grid_correction": (
                "The thresholds are FIXED by this document before the sample exists, so nothing is "
                "selected on the held-out data and there is no threshold-grid multiplicity to correct. "
                f"The {len(C.DEC_GRID)}-fold grid Bonferroni that the DEVELOPMENT bounds paid does not "
                "apply here and must not be added."),
            "no_family_multiplicity": (
                "Only pnictide is tested. f-electron and intermetallic are on hold and are not part of "
                "this evaluation, so there is no family multiplicity. The 6-fold family x side "
                "multiplicity of the DEVELOPMENT fit is the reason this hypothesis is worth testing at "
                "all; it does not require a second correction on fresh data."),
        },
        "dependence_audit": {
            "question": "does testing Path A and Path B on the SAME structures change the multiplicity procedure?",
            "structural_fact": (
                "Path B is a strict SUBSET of Path A by construction: B = A minus the rows whose two "
                "engines disagree by more than the tolerance. The two tests are therefore nested and "
                "strongly positively dependent, not independent."),
            "observed_dependence_on_development_data": (
                "On the round-4 pnictide draw, B retained 3,501 of A's 3,637 rows (96.3%). The stable "
                "side made 306 calls with 12 errors on BOTH paths - the disagreement filter removed no "
                "stable call at all - and the unstable side had 82 errors on both. The two paths' test "
                "statistics were very nearly the same number."),
            "resolution": [
                "1. Bonferroni is VALID under arbitrary dependence. It rests on Boole's inequality and "
                "assumes nothing about independence, so the nesting cannot invalidate it. Dependence "
                "costs power; it does not cost validity.",
                "2. The promotion rule is CONJUNCTIVE - all four hypotheses must pass. That makes this "
                "an intersection-union test, for which testing each hypothesis at an uncorrected alpha "
                "already controls the type-I error of the conjunctive claim at alpha. A Bonferroni "
                "correction on top is therefore STRICTLY CONSERVATIVE.",
                "3. Given 1 and 2, the conservative option is pre-registered as PRIMARY: each hypothesis "
                "is tested at confidence 0.9875. The effective number of independent tests is nearer 2 "
                "than 4 because of the nesting, which is a further reason the correction is conservative.",
                "4. PRE-COMMITMENT: if a hypothesis passes at the uncorrected 0.95 but fails at the "
                "primary 0.9875, that is a FAIL. It is reported as a near-miss with both bounds shown "
                "and it does NOT support promotion. No attempt will be made, before or after seeing the "
                "data, to estimate an 'effective' correction from the observed overlap, to switch to the "
                "intersection-union justification, or to drop the correction. The choice is made here "
                "and is not revisited.",
            ],
        },
        "hypotheses": {
            "PA1": {"path": "A", "side": "stable", "population": "Path-A labelable pnictide",
                    "threshold": T_STABLE, "metric": "precision of the 'likely stable' call",
                    "target": C.TARGET_PRECISION,
                    "pass": f"Clopper-Pearson lower bound at {PRIMARY_CONF:.4f} >= {C.TARGET_PRECISION}"},
            "PA2": {"path": "A", "side": "unstable", "population": "Path-A labelable pnictide",
                    "threshold": T_UNSTABLE, "metric": "NPV of the 'likely unstable' call",
                    "target": C.TARGET_NPV,
                    "pass": f"Clopper-Pearson lower bound at {PRIMARY_CONF:.4f} >= {C.TARGET_NPV}"},
            "PB1": {"path": "B", "side": "stable", "population": "Path-B labelable pnictide",
                    "threshold": T_STABLE, "metric": "precision of the 'likely stable' call",
                    "target": C.TARGET_PRECISION,
                    "pass": f"Clopper-Pearson lower bound at {PRIMARY_CONF:.4f} >= {C.TARGET_PRECISION}"},
            "PB2": {"path": "B", "side": "unstable", "population": "Path-B labelable pnictide",
                    "threshold": T_UNSTABLE, "metric": "NPV of the 'likely unstable' call",
                    "target": C.TARGET_NPV,
                    "pass": f"Clopper-Pearson lower bound at {PRIMARY_CONF:.4f} >= {C.TARGET_NPV}"},
        },
        "verdict_definitions": {
            "PASS": "the primary-confidence lower bound is >= the target",
            "FAIL": ("the primary-confidence lower bound is < the target, INCLUDING the case where the "
                     "point estimate is above the target. There is no 'ambiguous' verdict for a primary "
                     "hypothesis. The word ambiguous is reserved for descriptive diagnostics and may "
                     "never be applied to PA1/PA2/PB1/PB2."),
            "INCONCLUSIVE": ("the hypothesis could not be tested at all, for one of the pre-specified "
                             "reasons in 'inconclusive_triggers'. An INCONCLUSIVE hypothesis is NOT a "
                             "pass and NOT a fail; it blocks promotion exactly as a fail does."),
        },
        "inconclusive_triggers": {
            "too_few_calls": f"fewer than {MIN_CALLS} calls on that side (confidence.MIN_SELECTED)",
            "unusable_rows": (f"more than {MAX_UNUSABLE_FRAC:.0%} of drawn ids produce no usable "
                              "production-engine result (guard rejection, job failure or timeout). The "
                              "evaluation is not rescued by retrying into a different rung."),
            "missing_second_engine": (f"for Path B only: more than {MAX_UNUSABLE_FRAC:.0%} of Path-A "
                                      "labelable rows lack a usable second-engine result"),
            "no_labelable_rows": "a path has zero labelable rows",
        },
        "promotion_rule": {
            "shared_table": ("ALL FOUR of PA1, PA2, PB1, PB2 must PASS at the primary confidence. Only "
                             "then is the shared -20/+0 meV pnictide rule eligible for promotion to BOTH "
                             "rule sets. Eligible is not the same as promoted: promotion remains a "
                             "separate explicit decision by the user."),
            "anything_else": "no promotion of any kind follows from this evaluation.",
            "outcome_A_pass_B_fail": (
                "NO PROMOTION, of either path. Because B is nested in A, this outcome means the rows the "
                "disagreement filter RETAINS carry disproportionate error - a surprising result needing "
                "explanation, not a licence to promote Path A alone. A Path-A-only promotion would "
                "require its own pre-registration and its own fresh held-out sample; this one is spent."),
            "outcome_B_pass_A_fail": (
                "NO PROMOTION, of either path. Because B is nested in A, this means the rows the "
                "disagreement filter REMOVES carry disproportionate error, which would be evidence for "
                "SEPARATE tables. That is a post-hoc subgroup claim on this data and may not be acted "
                "on: it is recorded as a hypothesis for a future, separately pre-registered study."),
            "outcome_any_inconclusive": (
                "NO PROMOTION. The inconclusive hypothesis is reported as inconclusive with its counts. "
                "A replacement evaluation needs a fresh pre-registration and fresh ids; approximately "
                f"{POOL_ELIGIBLE - N_DRAW:,} eligible pnictide candidates would remain, which is why "
                "this design does not spend the whole pool."),
            "outcome_all_fail": (
                "NO PROMOTION. The development result is recorded as having failed to replicate. The "
                "with_second_engine pnictide defect then stands as a KNOWN defect with no validated "
                "fix, and that is reported as such rather than quietly left out of the summary."),
        },
        "sample": {
            "n_draw": N_DRAW,
            "eligible_pool": POOL_ELIGIBLE,
            "left_unspent_after_draw": POOL_ELIGIBLE - N_DRAW,
            "eligibility": (
                "a candidate is eligible ONLY if it has never participated in anything: not in the "
                "original WBM split (calibration or locked test), not in the round-1 oxide/halide split, "
                "not in the round-2 or round-3 splits, not in the round-4 draw, and therefore not in "
                "any fit, threshold selection, diagnostic, Path-B refit or prior evaluation. Enforced by "
                "id against round4._spent_ids() | round4.excluded_ids(), with every locked half's hash "
                "verified on the way."),
            "leakage_guards": [
                "every id any earlier split or draw has used is excluded by id",
                "every candidate sharing a reduced formula with ANY of the six locked test halves is "
                "dropped, because WBM's unique_prototype dedups prototypes and not compositions",
                "per-bin proportional to the eligible pool's own hull-distance distribution, which "
                "matches the round-4 draw to within 0.0003 per bin, so the development call rates transfer",
            ],
            "stratification": "per-bin proportional over " + ", ".join(
                ["<0", "0-0.025", "0.025-0.1", "0.1-0.3", ">0.3"]) + " eV/atom",
            "engines": ("both. The production engine mace-mpa-0-medium (cpu/float32, tag c2480e74) and "
                        "the second engine mace-mp-0-medium (cpu/float64, tag 207ccc81) are run over the "
                        "SAME drawn ids, because Path B cannot be scored without both."),
        },
        "sizing": sizing(),
        "error_budget": {"primary": budget(N_DRAW, PRIMARY_CONF),
                         "secondary": budget(N_DRAW, SECONDARY_CONF)},
        "sizing_note": (
            f"{N_DRAW} is chosen, not assumed. The binding hypothesis is the stable side, which converts "
            f"only {DEV['A stable']['rate']:.4f} of drawn structures into calls. At the primary "
            f"confidence, 90% power against the development point estimate requires 2,876 structures and "
            f"95% power requires 3,530. {N_DRAW} gives about 0.94 power on the binding hypothesis and "
            f"about 1.00 on the other three, and leaves {POOL_ELIGIBLE - N_DRAW:,} candidates unspent "
            "for a replacement study. A 1,500-structure draw - the round-3 convention - would have given "
            "only 0.53 power on the binding hypothesis and was rejected for that reason."),
        "power_honesty": (
            "This study is powered against the DEVELOPMENT POINT ESTIMATE (0.9608 stable, 0.9740/0.9728 "
            "NPV). It is NOT powered against the pessimistic end of the development interval: if "
            "pnictide's true stable precision were 0.9128 - the development lower bound - establishing "
            "it against a 0.90 target would need roughly 65,000 structures, which the pool cannot "
            "supply and which no study should attempt for an effect that small. So a PASS means 'the "
            "thresholds behave as development suggested'. A PASS does NOT establish that true precision "
            "is comfortably above 0.90, and this document forbids claiming that it does. This is the "
            "same limit the fluoride follow-up analysis identified and it is stated in advance here."),
        "stop_rules": [
            "The sample is drawn ONCE and opened ONCE. data/pnictide_eval_log.json records the opening; "
            "the open command refuses while that file exists.",
            "No interim looks and no sequential testing. Every job completes, then the four hypotheses "
            "are scored in a single pass.",
            "If any hypothesis FAILS or is INCONCLUSIVE, stop: no other locked half is opened, no "
            "further pnictide sample is drawn, and no threshold is adjusted.",
            "f-electron and intermetallic remain on hold throughout. This evaluation says nothing about "
            "either and must not be reported as if it did.",
        ],
        "forbidden_after_the_sample_is_drawn": [
            "REFITTING ANY THRESHOLD. The -20/+0 meV values are fixed by this document. Running certify, "
            "diagnose, best_bound or any grid search on the held-out rows is forbidden, for any purpose, "
            "including 'just to see'.",
            "changing the family definition, the precedence chain, the labelable definition, the weak "
            "element list, the structure-change exclusion or the disagreement tolerance",
            "changing the targets, the confidence, the correction, or which hypotheses are primary",
            "adding, dropping or reweighting hypotheses",
            "pooling these rows into any calibration set, now or later",
            "re-opening the sample, or drawing a second sample to append to it",
            "reporting the secondary 0.95 bound as the verdict",
            "describing a fitted development threshold as validated on the basis of a partial pass",
        ],
        "chain_of_custody": [
            "1. This document is committed BEFORE the sample is drawn. Its sha256 is recorded in the "
            "opening log and verified against the file on disk at open time.",
            "2. The draw writes data/wbm_split_pnictide_eval.json containing the id list and its "
            "sha256, and asserts disjointness from every prior split and every locked half by id. That "
            "file is committed before any job is queued.",
            "3. The ids are reachable only through an accessor that raises PermissionError without "
            "unlock=True, and that verifies the recorded hash before returning anything.",
            "4. Opening writes data/pnictide_eval_log.json recording: opened_at, harness commit, the "
            "sample's sha256, this document's sha256, the active bundle's sha256, and both engines' "
            "model keys, settings tags and checkpoint sha256 values.",
            "5. The set is registered in data/locked_sets_registry.json with state and provenance.",
            "6. Any mismatch between a recorded hash and the file on disk aborts the evaluation.",
        ],
        "procedure_when_approved": [
            "draw the sample (its own approval), commit it, then run both engines over it, then score "
            "the four hypotheses once and report every one of them - passes and failures alike.",
        ],
    }


def main() -> None:
    if OUT_JSON.exists() or OUT_MD.exists():
        raise SystemExit("pre-registration already written; it is not editable after the fact")
    P = build()
    OUT_JSON.write_text(json.dumps(P, indent=1) + "\n")

    def mev(t):
        return f"{t * 1000:+.0f} meV/atom"

    L = ["# Pre-registration — a fresh pnictide held-out evaluation", "",
         f"Written {P['created_at']} at commit `{P['harness_commit']}`.", "",
         f"> **{P['state']}**", "",
         "## What is being tested", "", P["what_is_being_tested"], "", "### Why", "", P["why"], "",
         "## The thresholds under test (FIXED)", "",
         f"| | |", "|---|---|",
         f"| stable | **{mev(T_STABLE)}** |", f"| unstable | **{mev(T_UNSTABLE)}** |",
         "", P["thresholds_under_test"]["frozen_here_not_read_from_bundle"], "",
         "For reference, the active bundle today: `without_second_engine` stable none / unstable "
         "+50 meV (n=210); `with_second_engine` **stable none / unstable none** (n=202).", "",
         "## Family definition and precedence", "",
         f"`{P['family_definition']['function']}`, first match wins:", "",
         "`" + " -> ".join(P["family_definition"]["precedence_chain"]) + "`", "",
         P["family_definition"]["what_pnictide_means_here"], "",
         "## Population", "",
         f"- **usable** — {P['population']['usable']}",
         f"- **labelable** — {P['population']['labelable']}",
         f"- weak elements: {', '.join(P['population']['weak_elements'])}",
         f"- max trustworthy hull: {P['population']['max_trustworthy_hull']}", "",
         "## The two primary paths", "",
         "| path | rule set | filter | disagreement |", "|---|---|---|---|",
         f"| **A** | `without_second_engine` | weak elements + structure change | not applied |",
         f"| **B** | `with_second_engine` | A + engine disagreement | "
         f"tol `{P['paths']['B']['disagreement_tol_ev']:.6f}` eV/atom |", "",
         P["paths"]["B"]["missing_second_engine_row_behaviour"], "",
         "Path C (the product's >0.3 eV/atom refusal) is reported as a descriptive secondary and can "
         "never change a verdict.", "",
         "## Hypotheses", "",
         "| id | path | side | threshold | metric | target | pass criterion |",
         "|---|---|---|---|---|---:|---|"]
    for hid, h in P["hypotheses"].items():
        L.append(f"| **{hid}** | {h['path']} | {h['side']} | {mev(h['threshold'])} | {h['metric']} | "
                 f"{h['target']} | CP-lower @ {PRIMARY_CONF:.4f} >= {h['target']} |")
    L += ["", "## Statistics and every correction applied", "",
          f"- bound: {P['statistics']['bound']}",
          f"- **primary confidence {PRIMARY_CONF:.4f}** — {P['statistics']['primary_confidence_rule']}",
          f"- secondary confidence {SECONDARY_CONF} — {P['statistics']['secondary_rule']}",
          f"- **no grid correction**: {P['statistics']['no_grid_correction']}",
          f"- **no family multiplicity**: {P['statistics']['no_family_multiplicity']}", "",
          "## Dependence audit — does testing A and B on the same structures change the procedure?", "",
          f"**Structural fact.** {P['dependence_audit']['structural_fact']}", "",
          f"**Observed.** {P['dependence_audit']['observed_dependence_on_development_data']}", "",
          "**Resolution, fixed here and not revisited:**", ""]
    L += [f"{r}" for r in P["dependence_audit"]["resolution"]]
    L += ["", "## Verdict definitions", ""]
    for k, v in P["verdict_definitions"].items():
        L.append(f"- **{k}** — {v}")
    L += ["", "### What makes a hypothesis INCONCLUSIVE", ""]
    for k, v in P["inconclusive_triggers"].items():
        L.append(f"- `{k}` — {v}")
    L += ["", "## Sample size — derived, not assumed", "",
          "Required structures, by hypothesis, powered against the development point estimate:", "",
          "| hypothesis | target | assumed truth | calls per structure | 80% power | 90% power | 95% power |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for h, d in DEV.items():
        row = P["sizing"]["by_confidence"]["primary"][h]
        L.append(f"| {h} | {d['target']} | {d['truth']:.4f} | {d['rate']:.5f} | "
                 f"{row['80%']['structures']:,} | {row['90%']['structures']:,} | {row['95%']['structures']:,} |")
    L += ["", f"At the primary confidence the binding hypothesis is the stable side: **2,876 structures "
              f"for 90% power**, 3,530 for 95%.", "",
          f"### Chosen: **n = {N_DRAW:,}** of {POOL_ELIGIBLE:,} eligible", "",
          P["sizing_note"], "",
          "### Expected calls, errors and power at n = " + f"{N_DRAW:,}", "",
          "| hypothesis | expected calls | expected errors | max errors allowed | power |",
          "|---|---:|---:|---:|---:|"]
    for h, e in P["error_budget"]["primary"].items():
        L.append(f"| {h} | {e['expected_calls']:,} | {e['expected_errors']} | "
                 f"{e['max_errors_allowed']:,} | {e['power_at_dev_point']:.3f} |")
    L += ["", "### Sensitivity: if the truth were the pessimistic end of the development interval", "",
          "| hypothesis | assumed truth | structures for 80% power |", "|---|---:|---:|"]
    for h, v in P["sizing"]["pessimistic_sensitivity"].items():
        L.append(f"| {h} | {v['assumed_truth']} | "
                 f"{(f'{v[chr(115)+chr(116)+chr(114)+chr(117)+chr(99)+chr(116)+chr(117)+chr(114)+chr(101)+chr(115)]:,}') if v['structures'] else 'not reachable'} |")
    L += ["", f"**{P['power_honesty']}**", "",
          "## The sample", "",
          f"- n = {N_DRAW:,}, drawn from {POOL_ELIGIBLE:,} eligible candidates, leaving "
          f"{POOL_ELIGIBLE - N_DRAW:,} unspent",
          f"- eligibility: {P['sample']['eligibility']}",
          f"- stratification: {P['sample']['stratification']}",
          f"- engines: {P['sample']['engines']}", "", "Leakage guards:", ""]
    L += [f"- {g}" for g in P["sample"]["leakage_guards"]]
    L += ["", "## Promotion rule", "",
          f"**Shared table.** {P['promotion_rule']['shared_table']}", "",
          "| outcome | consequence |", "|---|---|",
          f"| all four PASS | {P['promotion_rule']['shared_table'].split('. ')[1]} |",
          f"| A passes, B fails | {P['promotion_rule']['outcome_A_pass_B_fail']} |",
          f"| B passes, A fails | {P['promotion_rule']['outcome_B_pass_A_fail']} |",
          f"| any INCONCLUSIVE | {P['promotion_rule']['outcome_any_inconclusive']} |",
          f"| all fail | {P['promotion_rule']['outcome_all_fail']} |", "",
          "## Stop rules", ""]
    L += [f"- {r}" for r in P["stop_rules"]]
    L += ["", "## Forbidden once the sample is drawn", ""]
    L += [f"- {r}" for r in P["forbidden_after_the_sample_is_drawn"]]
    L += ["", "## Chain of custody", ""]
    L += [f"{r}" for r in P["chain_of_custody"]]
    L += ["", "## If approved", "", P["procedure_when_approved"][0], ""]
    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT_JSON}\nwrote {OUT_MD}")
    print(f"\nsha256 (json) {hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()}")
    print(f"sha256 (md)   {hashlib.sha256(OUT_MD.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
