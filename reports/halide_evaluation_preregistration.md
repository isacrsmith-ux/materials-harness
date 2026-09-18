# Pre-registration — halide held-out evaluation

**PRE-REGISTERED. The halide locked half has NOT been opened.**

Written 2026-09-18T18:39:22+00:00 at commit `dad450c`. This document is committed before the locked half is opened and is not edited afterwards. Nothing in producing it read, queried, summarised or unlocked the held-out data: its size and hash come from the split's public metadata, and every rate below comes from the calibration fit.

## What is being tested

the fluoride carve-out of specification v2, and the two halide-side thresholds it produces. This is the only taxonomy change being adopted.

| | |
|---|---|
| locked set | halide locked test (round 1) |
| n | 2,000 |
| sha256 | `26a08e6a360a959740dfe0f975942dae8c35811118e02303de539c6e2c8a610e` |
| source | `data/wbm_split_oxide_halide.json` |
| accessor | `splits.family_test_ids('halide', unlock=True)` |
| status before opening | UNOPENED |
| specification under test | `data/calibration_spec_v2.json` v2 |
| taxonomy | f-electron -> intermetallic -> oxide -> fluoride -> halide -> chalcogenide -> pnictide -> other |
| population | labelable |

## Statistics, fixed in advance

- **Bound.** one-sided Clopper-Pearson lower bound. Deliberately NOT the bootstrap that harness.final_eval.evaluate() used for the v1 test: a bootstrap collapses to [1.00, 1.00] on an error-free sample and this project has already caught it producing a false verdict. This is the same bound the thresholds were certified with.
- **No grid correction.** the thresholds are FIXED before the half is opened, so there is no threshold grid to search and no Bonferroni correction over a grid. The correction below is over the three hypotheses instead.
- **Primary confidence 0.98333** — Bonferroni over the 3 pre-registered hypotheses: 1 - 0.05/3.
- **Secondary confidence 0.95** — uncorrected, reported alongside; the verdict is taken from the primary.

## The three pre-registered hypotheses

Each is stated as a criterion on the held-out labelable rows. The thresholds are fixed now and are not refitted.

| id | family | side | threshold | target | criterion |
|---|---|---|---|---:|---|
| **H1** | halide | stable precision | -20 meV | 0.90 | Clopper-Pearson lower bound at 0.98333 >= 0.90 |
| **H2** | halide | unstable NPV | +0 meV | 0.95 | Clopper-Pearson lower bound at 0.98333 >= 0.95 |
| **H3** | fluoride | unstable NPV | +10 meV | 0.95 | Clopper-Pearson lower bound at 0.98333 >= 0.95 |

**Pass rule.** ALL THREE hypotheses must pass at the primary confidence. The evaluation passes only if every one of H1, H2 and H3 has its Clopper-Pearson lower bound at or above its target on the held-out labelable rows.

## Power and error budget

The expected call counts and error budgets below are derived from the calibration draw and are for sizing only; the criteria are applied to whatever the held-out data gives. They show the test is powered, and also that it is not generously powered: H1 expects 4 errors against a budget of 6, and H2 expects 24 against 27. A near-miss is a real possibility even if the thresholds are sound, and would be reported as a miss.

| id | calibration rate | expected calls | expected errors | max errors to pass | min rate to pass | slack |
|---|---:|---:|---:|---:|---:|---:|
| H1 | 0.9667 | 134 | 4 | 6 | 0.9552 | 2 |
| H2 | 0.9695 | 803 | 24 | 27 | 0.9664 | 3 |
| H3 | 0.9825 | 381 | 7 | 10 | 0.9738 | 3 |

Note that H1's minimum passing rate (0.9552) is far above its 0.90 target. That is not a moved goalpost: it is what a Clopper-Pearson bound on roughly 134 calls requires in order to *confirm* 0.90. A held-out half of 2,000 halides yields only that many 'likely stable' calls.

## Rationale check (diagnostic, not pass/fail)

**R1 — does the pooled halide rule still show a precision deficit on fluorides, out of sample? This is the carve-out's whole justification.**

- Procedure: apply the pooled halide stable threshold of -20 meV/atom to the held-out FLUORIDE rows and report point precision with a two-sided 95% Clopper-Pearson interval
- On calibration: point precision 0.8971 on 350 calls (CP-lower 0.8366), below the 0.90 target
- Pre-registered expectation: point precision below 0.90
- **Interpretation rule:** if the held-out point precision is at or above 0.90 AND its lower bound clears 0.90, the carve-out's justification is NOT reproduced out of sample, and adoption must be revisited even if H1-H3 all pass. This outcome is to be reported prominently, not buried.

## Stop rule

If the evaluation fails, NO further locked half is opened, the fluoride carve-out is withdrawn, specification v2 is not promoted, and data/calibration_bundle.json (v1) remains the active bundle unchanged. The remaining halves cannot rescue a change whose sole justification has failed out of sample, and opening them to look for a better story is exactly the behaviour this pre-registration exists to prevent.

## Forbidden once the half is open

- changing any threshold, the taxonomy, the population definition or any exclusion rule
- changing the target, the confidence level, the bound or the pass rule
- re-opening the half, or opening a second half before this one's result is reported
- reporting a miss as anything other than a miss
- dropping any row for any reason other than the pre-registered exclusion rules; guard rejections are counted and excluded, never dropped

## Procedure, when approved

1. Write data/halide_test_log.json recording the opening, its timestamp, the set's sha256 and the spec version under test. Refuse if it already exists.
2. splits.family_test_ids('halide', unlock=True); verify the hash matches the pre-registered one above before anything is queued.
3. Enqueue relaxation + static for all 2,000 ids under the production engine (settings_tag c2480e74), asserted as in every other phase.
4. Apply the v2 exclusion rules to produce the labelable held-out rows.
5. Apply the FIXED thresholds. Compute H1, H2, H3 and R1. No fitting of any kind.
6. Report each hypothesis with its pre-registered criterion quoted before its result.

## Approval

This protocol requires explicit approval before step 1 is run. Until then the halide half stays closed, `splits.family_test_ids('halide')` keeps raising `PermissionError`, and `data/calibration_bundle.json` (v1) remains the active bundle.

