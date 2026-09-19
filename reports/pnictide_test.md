# Pnictide held-out evaluation — the one-time result

Opened 2026-09-19T05:26:57+00:00 at commit `a82f149`. Evaluated 2026-09-19T06:04:07+00:00. Sample sha256 `f304bd2064e0cc92d20a13978f818816226265b3c24222901df1692205c08a71`, pre-registration sha256 `effe583b501cd0b7021481eeaf77ffec0c80fb48588f9510d9a222a99252852b` — both verified against the recorded values before any structure was queued, and the pre-registration verified again before scoring.

Every threshold, exclusion, hypothesis, target, confidence and correction was fixed in `reports/pnictide_evaluation_preregistration.md` and committed at `0826a39`, **before the sample was drawn**. Nothing was fitted on this sample. The scoring script contains no `certify`, `diagnose`, `best_bound` or grid-search code at all.

## Thresholds under test (fixed)

stable **-20 meV**, unstable **+0 meV**. These come from the round-4 and round-4c development fits and were frozen by the pre-registration. They are not re-derived here.

## Population

| | n |
|---|---:|
| drawn | 3,500 |
| usable (production engine) | 3,500 |
| unusable | **0** |
| guard-rejected, engine 1 / engine 2 | 0 / 1 |
| **labelable, Path A** | **3,176** |
| **labelable, Path B** | **3,066** |
| removed by the disagreement term | 110 |
| lacking a second-engine result | 0 |
| labelable, path C (descriptive) | 2,723 |

Pre-registered inconclusive triggers fired: **NONE**.

## The four pre-registered hypotheses

Primary confidence **0.9875** (Bonferroni over the four hypotheses). One-sided Clopper-Pearson. The verdict is read from the bound, never the point estimate.

| id | path | side | metric | calls | correct | errors | point | CP-lower (primary) | target | margin | verdict |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **PA1** | A | stable | precision | 275 | 263 | 12 | 0.9564 | **0.9201** | 0.9 | +0.0201 | **PASS** |
| **PA2** | A | unstable | NPV | 2,739 | 2,673 | 66 | 0.9759 | **0.9685** | 0.95 | +0.0185 | **PASS** |
| **PB1** | B | stable | precision | 273 | 261 | 12 | 0.9560 | **0.9196** | 0.9 | +0.0196 | **PASS** |
| **PB2** | B | unstable | NPV | 2,631 | 2,565 | 66 | 0.9749 | **0.9672** | 0.95 | +0.0172 | **PASS** |

**Overall: PASS** — the pre-registered rule is that all four must pass at the primary confidence.

The uncorrected 0.95 bounds are reported for completeness and **cannot change a verdict**: PA1 0.9303, PA2 0.9705, PB1 0.9298, PB2 0.9693.

## Against the pre-registered error budget

| id | expected calls | observed | expected errors | observed | max errors allowed | within budget |
|---|---:|---:|---:|---:|---:|---|
| PA1 | 268 | 275 | 10.5 | 12 | 15 | yes |
| PA2 | 2,760 | 2,739 | 71.8 | 66 | 112 | yes |
| PB1 | 268 | 273 | 10.5 | 12 | 15 | yes |
| PB2 | 2,641 | 2,631 | 71.8 | 66 | 107 | yes |

Call counts landed within about 3% of the sizing prediction, which is the clearest evidence that the development call rates transferred to a fresh sample as designed.

## Held-out against development, same fixed thresholds

| id | dev calls | dev point | dev bound | held-out calls | held-out point | held-out bound |
|---|---:|---:|---:|---:|---:|---:|
| PA1 | 306 | 0.9608 | 0.9128 | 275 | 0.9564 | 0.9201 |
| PA2 | 3,154 | 0.9740 | 0.9638 | 2,739 | 0.9759 | 0.9685 |
| PB1 | 306 | 0.9608 | 0.9128 | 273 | 0.9560 | 0.9196 |
| PB2 | 3,018 | 0.9728 | 0.9622 | 2,631 | 0.9749 | 0.9672 |

**Read the bounds carefully.** The held-out bounds are *higher* than the development bounds despite fewer calls, and that is not the held-out data being better. The development fits paid a Bonferroni correction over the 61-point threshold grid (level 0.99918) because a threshold was *selected* on them. This evaluation selected nothing, so it pays only the 4-fold correction over its hypotheses (level 0.9875), which is less stringent. The point estimates are the comparable quantity, and on the stable side the held-out point is slightly **lower** than development (0.9564 against 0.9608) — well within sampling noise.

Both paths produced **identical error counts** (12 on the stable side, 66 on the unstable side): the disagreement term removed 110 rows and not one of them was a call the rule got wrong. That independently reproduces what the development draw showed for pnictide, and is the strongest evidence in this document that the two paths behave the same.

## Path C — descriptive only, never a verdict

The product's >0.3 eV/atom refusal added on top:

| side | labelable | calls | errors | point | CP-lower |
|---|---:|---:|---:|---:|---:|
| stable | 2,723 | 273 | 12 | 0.9560 | 0.9196 |
| unstable | 2,723 | 2,288 | 66 | 0.9712 | 0.9623 |

## An incident during execution, recorded because it happened

The first attempt to drain the queue ran the runner under the **production** engine while both engines' jobs were queued. The runner refused all 7,000 second-engine jobs with `SettingsMismatch: queued under a different settings tag`. That guard exists because the round-1 calibration once silently ran on the wrong engine and produced a certification verdict that was wrong; here it caught an orchestration mistake instead of letting it through.

The 7,000 jobs were requeued and run under the correct engine. That is **not** the "retrying into a different rung" the pre-registration forbids: a rung is a different physical calculation substituted when one fails to converge, whereas these jobs were rejected at dispatch and performed no calculation at all. Re-running them was the first attempt at the same pre-registered settings. The production engine, to which the `unusable_rows` trigger is explicitly scoped, had zero failures throughout. Decisively, **no result had been scored when the repair was made**, so the decision could not have been influenced by the outcome — which is what the no-interim-looks rule protects.

## What this result does and does not establish

**Does.** The fixed thresholds stable -20 meV and unstable +0 meV meet their targets on 3,500 pnictide structures that had never participated in any fit, threshold selection, diagnostic, refit or prior evaluation. Both production paths pass. Under the pre-registered rule, the shared rule is therefore **eligible** for promotion to both rule sets.

**Does not.** Eligible is not promoted: promotion remains a separate explicit decision. And the limit stated in the pre-registration before any data existed still stands — this study was powered against the development *point* estimate. A pass means the thresholds behave as development suggested. It does **not** establish that true precision is comfortably above 0.90; had the truth been 0.9128, the development lower bound, establishing a deficit would have needed roughly 65,000 structures. Nothing here licenses that stronger claim.

**Says nothing about** f-electron or intermetallic, which were on hold throughout, or about any family other than pnictide, or about anything off WBM.

