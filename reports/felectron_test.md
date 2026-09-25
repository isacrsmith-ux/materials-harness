# f-electron held-out evaluation — the one-time result

Opened 2026-09-24T19:37:44+00:00 at commit `1aa315a`, **authorised by Isac Smith, 2026-09-24**. Evaluated 2026-09-24T21:11:35+00:00. Sample sha256 `43a675a7b4d67d44a18c0ed35b5a12f5d27b3f09452fc55556aa2f27aa348445`, pre-registration sha256 `d3995f66d562efd9893137e95a200ef103bc9a7e01ba3d7620356e7c7aafd4d2` — both verified in full before any structure was queued, and again before scoring. Active bundle sha256 at scoring `419c11514d6a54854584258375eadab6b2be0c449e955125799fc51df2310288`.

Every threshold, exclusion, hypothesis, target, confidence and correction was fixed in `reports/felectron_evaluation_preregistration.md`, committed at `37886a8` and **pushed before the sample was drawn**. Nothing was fitted on this sample. `scripts/felectron_eval.py` contains no `certify`, `diagnose`, `best_bound` or grid-search code.

## Thresholds under test (fixed)

The LIVE production rule: stable **-20 meV**, unstable **+10 meV**, on both paths. Not re-derived here.

## Population

| | n |
|---|---:|
| drawn | 4,500 |
| usable (production engine) | 4,500 |
| unusable | **0** |
| guard-rejected, engine 1 / engine 2 | 0 / 13 |
| **labelable, Path A** | **3,942** |
| **labelable, Path B** | **3,847** |
| removed by the disagreement term | 95 |
| lacking a second-engine result | 10 |
| labelable, path C (descriptive) | 3,516 |

Pre-registered inconclusive triggers fired: **NONE**.

## The four pre-registered hypotheses

Primary confidence **0.9875** (Bonferroni over the four hypotheses). One-sided Clopper-Pearson. The verdict is read from the primary bound, never the point estimate or the 0.95 bound.

| id | path | side | calls | correct | errors | point | CP-lower @0.9875 | CP-lower @0.95 | target | verdict |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **EA1** | A | stable | 481 | 468 | 13 | 0.9730 | **0.9513** | 0.9574 | 0.9 | **PASS** |
| **EA2** | A | unstable | 3,020 | 2,987 | 33 | 0.9891 | **0.9840** | 0.9854 | 0.95 | **PASS** |
| **EB1** | B | stable | 475 | 462 | 13 | 0.9726 | **0.9507** | 0.9568 | 0.9 | **PASS** |
| **EB2** | B | unstable | 2,933 | 2,900 | 33 | 0.9887 | **0.9835** | 0.9850 | 0.95 | **PASS** |

**Overall: PASS** — the pre-registered rule is that all four must pass at the primary confidence.

## Against the pre-registered expectations

| id | expected calls | observed | ratio | expected errors | observed | max errors allowed | within budget |
|---|---:|---:|---:|---:|---:|---:|---|
| EA1 | 492 | 481 | 0.978 | 25.5 | 13 | 34 | yes |
| EA2 | 3,018 | 3,020 | 1.001 | 33.7 | 33 | 124 | yes |
| EB1 | 482 | 475 | 0.985 | 22.5 | 13 | 33 | yes |
| EB2 | 2,921 | 2,933 | 1.004 | 33.2 | 33 | 119 | yes |

## Held-out bound against development bound

The development bounds at n=8,800 were **0.9171** (A) and **0.9231** (B) on the stable side. The held-out bounds are 0.9513 (EA1) and 0.9507 (EB1). **A held-out bound is expected to exceed a development bound at similar n, and that is not the held-out data being better.** The development level (0.999863) paid for searching a 61-point grid across 6 family x side selections; this evaluation selected nothing and pays only the 4-fold correction (0.9875). The point estimates are the comparable quantity.

## Dependence

Path B is a strict subset of Path A (A minus rows whose engines disagree beyond tolerance), so the tests are nested and positively dependent. As pre-registered: Bonferroni is valid under arbitrary dependence, the conjunctive rule makes it strictly conservative, and no 'effective' correction was estimated from the observed overlap. Here B retained 3,847 of A's 3,942 labelable rows.

## Path C — descriptive only, never a verdict

| side | labelable | calls | errors | point | CP-lower @0.9875 |
|---|---:|---:|---:|---:|---:|
| stable | 3,516 | 475 | 13 | 0.9726 | 0.9507 |
| unstable | 3,516 | 2,602 | 33 | 0.9873 | 0.9815 |

## The pre-registered outcome branch that applies (quoted verbatim)

`outcome_rule.all_four_pass`:

> the live f-electron rule is CONFIRMED out of sample on both paths. Note what this does and does not license: it confirms a rule ALREADY IN PRODUCTION, so the correct action is to record the confirmation and the provenance in the bundle. It is NOT a licence to change any threshold, and no threshold would change.

> This evaluation can confirm a live rule or impugn it, and those two outcomes have very different consequences for the product. That asymmetry is recorded now so that a failure cannot later be softened by arguing the test was too strict.

## What this does not do

No threshold was changed and `data/calibration_bundle.json` is untouched by this evaluation. Recording a confirmation (if any) is a separate production commit on an explicit decision. This result says nothing about intermetallic, pnictide or any family other than f-electron, or about anything off WBM.
