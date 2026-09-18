#!/usr/bin/env python
"""Write the PRE-REGISTERED protocol for the halide held-out evaluation.

Written and committed BEFORE the locked half is opened. Nothing in this file reads, queries,
summarises or unlocks the halide test set: it takes the set's size and hash from the split's public
metadata and every rate from the CALIBRATION fit, and from those alone derives what the held-out
result would have to look like to pass.

Run once. Refuses to overwrite, because a pre-registration that can be edited after the fact is not
a pre-registration.

    python scripts/prereg_halide_eval.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from harness import calibration as CAL, confidence as C, splits
from harness.config import DATA_DIR, REPORTS_DIR

OUT_MD = REPORTS_DIR / "halide_evaluation_preregistration.md"
OUT_JSON = DATA_DIR / "halide_evaluation_preregistration.json"

N_HYP = 3
CONF_PRIMARY = 1 - (1 - C.CERT_CONF) / N_HYP   # Bonferroni over the three pre-registered tests
CONF_SECONDARY = C.CERT_CONF

# Observed on the 6,300-structure halide CALIBRATION draw, labelable rows. Used only to size the
# test and to state an error budget; the criteria themselves are evaluated on whatever the held-out
# data actually gives.
LAB_FRAC = 5135 / 6300
NONF_FRAC = 3247 / 5135
POOLED_HALIDE_T = -0.02   # the v1-style pooled rule, for the rationale check


def max_errors(n: int, target: float, conf: float) -> int:
    for e in range(0, n + 1):
        if C.cp_lower(n - e, n, conf) < target:
            return e - 1
    return n


def build() -> dict:
    spec = json.loads((DATA_DIR / "calibration_spec_v2.json").read_text())
    reg = json.loads((DATA_DIR / "locked_sets_registry.json").read_text())
    half = next(s for s in reg["sets"] if s["name"] == "halide locked test (round 1)")
    th = spec["thresholds"]
    hal, flu = th["halide"], th["fluoride"]

    n_nonf = half["n"] * LAB_FRAC * NONF_FRAC
    n_flu = half["n"] * LAB_FRAC * (1 - NONF_FRAC)

    hyps = []
    for name, family, side, target, pop, sel_rate, rate in (
        ("H1", "halide", "stable precision", C.TARGET_PRECISION, n_nonf,
         hal["n_called_stable"] / hal["n_labelable"], hal["stable_precision"]),
        ("H2", "halide", "unstable NPV", C.TARGET_NPV, n_nonf,
         hal["n_called_unstable"] / hal["n_labelable"], hal["unstable_npv"]),
        ("H3", "fluoride", "unstable NPV", C.TARGET_NPV, n_flu,
         flu["n_called_unstable"] / flu["n_labelable"], flu["unstable_npv"]),
    ):
        n_exp = int(round(pop * sel_rate))
        e_allow = max_errors(n_exp, target, CONF_PRIMARY)
        hyps.append({
            "id": name, "family": family, "side": side, "target": target,
            "threshold": hal["stable"] if name == "H1" else (hal["unstable"] if name == "H2" else flu["unstable"]),
            "calibration_rate": rate,
            "expected_n_calls": n_exp,
            "expected_errors": int(round(n_exp * (1 - rate))),
            "max_errors_to_pass": e_allow,
            "min_observed_rate_to_pass": (n_exp - e_allow) / n_exp if n_exp else None,
            "cp_lower_at_expected": C.cp_lower(n_exp - int(round(n_exp * (1 - rate))), n_exp, CONF_PRIMARY),
            "slack_errors": e_allow - int(round(n_exp * (1 - rate))),
        })

    return {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness_commit": CAL.harness_commit(),
        "state": "PRE-REGISTERED. The halide locked half has NOT been opened.",
        "what_is_being_tested": (
            "the fluoride carve-out of specification v2, and the two halide-side thresholds it "
            "produces. This is the only taxonomy change being adopted."),
        "locked_set": {"name": half["name"], "n": half["n"], "sha256": half["sha256"],
                       "source_file": half["source_file"], "status_before": half["status"],
                       "accessor": "splits.family_test_ids('halide', unlock=True)"},
        "spec_under_test": {"file": "data/calibration_spec_v2.json", "spec_version": 2,
                            "taxonomy": spec["taxonomy"]["chain"],
                            "population": spec["population"]["name"]},
        "statistics": {
            "bound": ("one-sided Clopper-Pearson lower bound. Deliberately NOT the bootstrap that "
                      "harness.final_eval.evaluate() used for the v1 test: a bootstrap collapses to "
                      "[1.00, 1.00] on an error-free sample and this project has already caught it "
                      "producing a false verdict. This is the same bound the thresholds were "
                      "certified with."),
            "no_grid_correction": ("the thresholds are FIXED before the half is opened, so there is "
                                   "no threshold grid to search and no Bonferroni correction over a "
                                   "grid. The correction below is over the three hypotheses instead."),
            "primary_confidence": CONF_PRIMARY,
            "primary_confidence_rule": f"Bonferroni over the {N_HYP} pre-registered hypotheses: 1 - 0.05/{N_HYP}",
            "secondary_confidence": CONF_SECONDARY,
            "secondary_rule": "uncorrected, reported alongside; the verdict is taken from the primary",
        },
        "hypotheses": hyps,
        "pass_rule": ("ALL THREE hypotheses must pass at the primary confidence. The evaluation "
                      "passes only if every one of H1, H2 and H3 has its Clopper-Pearson lower bound "
                      "at or above its target on the held-out labelable rows."),
        "rationale_check": {
            "id": "R1", "kind": "diagnostic, NOT pass/fail",
            "question": ("does the pooled halide rule still show a precision deficit on fluorides, "
                         "out of sample? This is the carve-out's whole justification."),
            "procedure": (f"apply the pooled halide stable threshold of {POOLED_HALIDE_T*1000:+.0f} "
                          "meV/atom to the held-out FLUORIDE rows and report point precision with a "
                          "two-sided 95% Clopper-Pearson interval"),
            "calibration_result": "point precision 0.8971 on 350 calls (CP-lower 0.8366), below the 0.90 target",
            "prereg_expectation": "point precision below 0.90",
            "interpretation_rule": ("if the held-out point precision is at or above 0.90 AND its "
                                    "lower bound clears 0.90, the carve-out's justification is NOT "
                                    "reproduced out of sample, and adoption must be revisited even "
                                    "if H1-H3 all pass. This outcome is to be reported prominently, "
                                    "not buried."),
        },
        "stop_rule": (
            "If the evaluation fails, NO further locked half is opened, the fluoride carve-out is "
            "withdrawn, specification v2 is not promoted, and data/calibration_bundle.json (v1) "
            "remains the active bundle unchanged. The remaining halves cannot rescue a change whose "
            "sole justification has failed out of sample, and opening them to look for a better "
            "story is exactly the behaviour this pre-registration exists to prevent."),
        "forbidden_after_opening": [
            "changing any threshold, the taxonomy, the population definition or any exclusion rule",
            "changing the target, the confidence level, the bound or the pass rule",
            "re-opening the half, or opening a second half before this one's result is reported",
            "reporting a miss as anything other than a miss",
            "dropping any row for any reason other than the pre-registered exclusion rules; guard "
            "rejections are counted and excluded, never dropped",
        ],
        "procedure_when_approved": [
            "1. Write data/halide_test_log.json recording the opening, its timestamp, the set's "
            "sha256 and the spec version under test. Refuse if it already exists.",
            "2. splits.family_test_ids('halide', unlock=True); verify the hash matches the "
            "pre-registered one above before anything is queued.",
            "3. Enqueue relaxation + static for all 2,000 ids under the production engine "
            "(settings_tag c2480e74), asserted as in every other phase.",
            "4. Apply the v2 exclusion rules to produce the labelable held-out rows.",
            "5. Apply the FIXED thresholds. Compute H1, H2, H3 and R1. No fitting of any kind.",
            "6. Report each hypothesis with its pre-registered criterion quoted before its result.",
        ],
        "sizing_note": (
            "The expected call counts and error budgets below are derived from the calibration draw "
            "and are for sizing only; the criteria are applied to whatever the held-out data gives. "
            "They show the test is powered, and also that it is not generously powered: H1 expects "
            "4 errors against a budget of 6, and H2 expects 24 against 27. A near-miss is a real "
            "possibility even if the thresholds are sound, and would be reported as a miss."),
    }


def render(D: dict) -> str:
    s, L = D["statistics"], []
    L += ["# Pre-registration — halide held-out evaluation", "",
          f"**{D['state']}**", "",
          f"Written {D['created_at']} at commit `{D['harness_commit']}`. This document is committed "
          "before the locked half is opened and is not edited afterwards. Nothing in producing it "
          "read, queried, summarised or unlocked the held-out data: its size and hash come from the "
          "split's public metadata, and every rate below comes from the calibration fit.", "",
          "## What is being tested", "",
          D["what_is_being_tested"], "",
          "| | |", "|---|---|",
          f"| locked set | {D['locked_set']['name']} |",
          f"| n | {D['locked_set']['n']:,} |",
          f"| sha256 | `{D['locked_set']['sha256']}` |",
          f"| source | `{D['locked_set']['source_file']}` |",
          f"| accessor | `{D['locked_set']['accessor']}` |",
          f"| status before opening | {D['locked_set']['status_before']} |",
          f"| specification under test | `{D['spec_under_test']['file']}` v{D['spec_under_test']['spec_version']} |",
          f"| taxonomy | {' -> '.join(D['spec_under_test']['taxonomy'])} |",
          f"| population | {D['spec_under_test']['population']} |", "",
          "## Statistics, fixed in advance", "",
          f"- **Bound.** {s['bound']}",
          f"- **No grid correction.** {s['no_grid_correction']}",
          f"- **Primary confidence {s['primary_confidence']:.5f}** — {s['primary_confidence_rule']}.",
          f"- **Secondary confidence {s['secondary_confidence']}** — {s['secondary_rule']}.", "",
          "## The three pre-registered hypotheses", "",
          "Each is stated as a criterion on the held-out labelable rows. The thresholds are fixed "
          "now and are not refitted.", "",
          "| id | family | side | threshold | target | criterion |", "|---|---|---|---|---:|---|"]
    for h in D["hypotheses"]:
        t = h["threshold"]
        L.append(f"| **{h['id']}** | {h['family']} | {h['side']} | "
                 f"{'-' if t is None else f'{t*1000:+.0f} meV'} | {h['target']:.2f} | "
                 f"Clopper-Pearson lower bound at {s['primary_confidence']:.5f} >= {h['target']:.2f} |")
    L += ["", f"**Pass rule.** {D['pass_rule']}", "",
          "## Power and error budget", "", D["sizing_note"], "",
          "| id | calibration rate | expected calls | expected errors | max errors to pass | "
          "min rate to pass | slack |", "|---|---:|---:|---:|---:|---:|---:|"]
    for h in D["hypotheses"]:
        L.append(f"| {h['id']} | {h['calibration_rate']:.4f} | {h['expected_n_calls']} | "
                 f"{h['expected_errors']} | {h['max_errors_to_pass']} | "
                 f"{h['min_observed_rate_to_pass']:.4f} | {h['slack_errors']} |")
    L += ["", "Note that H1's minimum passing rate (0.9552) is far above its 0.90 target. That is not "
              "a moved goalpost: it is what a Clopper-Pearson bound on roughly 134 calls requires in "
              "order to *confirm* 0.90. A held-out half of 2,000 halides yields only that many "
              "'likely stable' calls.", "",
          "## Rationale check (diagnostic, not pass/fail)", ""]
    r = D["rationale_check"]
    L += [f"**{r['id']} — {r['question']}**", "",
          f"- Procedure: {r['procedure']}",
          f"- On calibration: {r['calibration_result']}",
          f"- Pre-registered expectation: {r['prereg_expectation']}",
          f"- **Interpretation rule:** {r['interpretation_rule']}", "",
          "## Stop rule", "", D["stop_rule"], "",
          "## Forbidden once the half is open", ""]
    L += [f"- {x}" for x in D["forbidden_after_opening"]]
    L += ["", "## Procedure, when approved", ""]
    L += D["procedure_when_approved"]
    L += ["", "## Approval", "",
          "This protocol requires explicit approval before step 1 is run. Until then the halide half "
          "stays closed, `splits.family_test_ids('halide')` keeps raising `PermissionError`, and "
          "`data/calibration_bundle.json` (v1) remains the active bundle.", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    if OUT_MD.exists() or OUT_JSON.exists():
        raise SystemExit("pre-registration already written; it is not editable after the fact")
    D = build()
    OUT_JSON.write_text(json.dumps(D, indent=1, default=str) + "\n")
    OUT_MD.write_text(render(D))
    print(f"written: {OUT_MD}\nwritten: {OUT_JSON}")
