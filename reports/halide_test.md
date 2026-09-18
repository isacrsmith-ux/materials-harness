# Halide locked-half evaluation — the one-time result

Evaluated 2026-09-18T19:27:41+00:00. Opened 2026-09-18T19:12:05+00:00 at commit `4027b57`. Locked set sha256 `26a08e6a360a959740dfe0f975942dae8c35811118e02303de539c6e2c8a610e`, verified against the pre-registration before any structure was queued.

Every threshold, exclusion and criterion was fixed in `reports/halide_evaluation_preregistration.md` and committed before the half was opened. Nothing was fitted on this set.

## Population

| | n |
|---|---:|
| locked ids | 2,000 |
| usable (guard rejections counted and excluded) | 2,000 |
| rejected by the energy-plausibility guard | 0 |
| excluded as not labelable (weak element / structure change) | 341 |
| **labelable** | **1,659** |
| of which non-fluoride | 1,016 |
| of which fluoride | 643 |

## H1-H3, against the frozen criteria

Primary confidence 0.98333 (Bonferroni over the three hypotheses); ordinary 0.95 reported alongside. The verdict is taken from the primary, as pre-registered.

| id | population | calls | correct | errors | point | CP-lower (primary) | CP-lower (95%) | target | result |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **H1** | 1,016 | 157 | 153 | 4 | 0.9745 | **0.9324** | 0.9426 | 0.90 | **PASS** |
| **H2** | 1,016 | 771 | 753 | 18 | 0.9767 | **0.9621** | 0.9656 | 0.95 | **PASS** |
| **H3** | 643 | 428 | 423 | 5 | 0.9883 | **0.9715** | 0.9756 | 0.95 | **PASS** |

Against the pre-registered error budget:

| id | errors allowed | errors observed | calls expected | calls observed |
|---|---:|---:|---:|---:|
| H1 | 6 | 4 | 134 | 157 |
| H2 | 27 | 18 | 803 | 771 |
| H3 | 10 | 5 | 381 | 428 |

**Overall: PASS** — the pre-registered rule is that all three must pass at the primary confidence.

## R1 — rationale check (diagnostic, not pass/fail)

Does the pooled halide rule still show a precision deficit on fluorides, out of sample? This is the carve-out's entire justification.

| | |
|---|---|
| pooled halide stable threshold applied to fluorides | -20 meV/atom |
| calls | 107 |
| correct | 101 |
| errors | 6 |
| **point precision** | **0.9439** |
| two-sided 95% CI | [0.8819, 0.9791] |
| one-sided 95% lower bound | 0.8923 |
| on calibration | 0.8971 on 350 calls |
| pre-registered expectation | point precision below 0.90 |

**Ambiguous.** Point precision 0.9439 is at or above 0.90 but its lower bound (0.8923) does not clear 0.90, so the deficit is neither reproduced nor refuted on this sample.

## Post-hoc note on R1 (descriptive, not a pre-registered test)

The two R1 measurements are of the same pre-specified quantity on two disjoint samples:

| sample | calls | correct | point precision |
|---|---:|---:|---:|
| calibration fluorides | 350 | 314 | 0.8971 |
| held-out fluorides | 107 | 101 | 0.9439 |

Difference +0.0468 (SE 0.0275, z 1.70, two-sided p 0.089). The held-out sample carries 0.31x the calls of the calibration sample, because the halide locked half holds 643 labelable fluorides against the calibration draw's 1,888. No expected n for R1 was pre-registered, and with these counts the interval cannot separate 0.90 from 0.94.

This note characterises the ambiguity; it does not resolve it, and it changes no verdict. The pre-registered interpretation rule was met on neither branch: the deficit was not reproduced, and it was not refuted either.

