# Track 2 — f-electron development top-up

Generated 2026-09-21T23:36:50+00:00. Plan and candidate ids frozen 2026-09-21T21:35:43+00:00, **before any outcome was computed**; this analysis implements that freeze and nothing else.

> **DEVELOPMENT EVIDENCE ONLY.** Thresholds here are fitted and scored on the same rows - the most optimistic estimate available. This cannot change the live f-electron production rule in either direction, and no locked set was opened.

## Population

| | n |
|---|---:|
| round-4 development draw (already spent) | 4,000 |
| frozen top-up | 4,800 |
| **combined** | **8,800** |
| usable (production engine) | 8,800 |
| unusable | 0 |
| guard-rejected, engine 1 / engine 2 | 0 / 22 |
| lacking a second-engine result | 22 |
| labelable, Path A | 7,719 |
| labelable, Path B | 7,504 |

## PRIMARY — does a stable threshold certify under the FULL family correction?

Bonferroni over the 61-point grid **and** the 6 family x side selections round 4 made: level **0.999863**. This is the pre-specified criterion.

| hypothesis | path | certified threshold | calls | errors | point | CP-lower | clears 0.90? |
|---|---|---|---:|---:|---:|---:|---|
| **F1** | A single engine | -20 meV | 963 | 50 | 0.948079 | **0.917100** | **YES** |
| **F2** | B second engine | -20 meV | 942 | 44 | 0.953291 | **0.923122** | **YES** |

## SECONDARY — the same question under the grid-only standard

Level 0.999180, the standard round 4 used. Reported for comparability; the freeze states explicitly that this is **not** the criterion.

| hypothesis | path | certified threshold | calls | errors | point | CP-lower |
|---|---|---|---:|---:|---:|---:|
| F1 | A single engine | -20 meV | 963 | 50 | 0.948079 | 0.921671 |
| F2 | B second engine | -10 meV | 1,153 | 80 | 0.930616 | 0.903949 |

## The LIVE production rule (-20 meV) on the enlarged population

Descriptive. The live rule is not under test here and is not changed by this document.

| path | calls | errors | point | CP-lower (family-corrected) | CP-lower (grid-only) |
|---|---:|---:|---:|---:|---:|
| A single engine | 963 | 50 | 0.948079 | **0.917100** | 0.921671 |
| B second engine | 942 | 44 | 0.953291 | **0.923122** | 0.927601 |

## Do the two development cohorts agree?

The combined point estimate is higher than round 4's was, so the two cohorts have to be compared before the combined bound is trusted. If the top-up rows were materially easier, the combined figure would be a mixture rather than a better-powered estimate of the same quantity.

| path | cohort | calls | errors | point | labelable | base rate |
|---|---|---:|---:|---:|---:|---:|
| A | round4 | 441 | 27 | 0.9388 | 3,495 | 0.1848 |
| A | topup | 522 | 23 | 0.9559 | 4,224 | 0.1842 |
| B | round4 | 429 | 24 | 0.9441 | 3,412 | 0.1864 |
| B | topup | 513 | 20 | 0.9610 | 4,092 | 0.1882 |

Path A: difference +0.0172 (SE 0.0144, z +1.20, two-sided p 0.232).
Path B: difference +0.0170 (SE 0.0138, z +1.23, two-sided p 0.219).

The cohorts are **not** statistically distinguishable on either path, and their hull-bin compositions and base rates agree to within 0.002. So the combined estimate is a better-powered measurement of the same quantity, not a mixture - and the reason the bound now clears is that the call count roughly doubled, not that the top-up rows were easier.

## Why Path B's grid-only row shows a looser threshold

Under the grid-only standard Path B certifies at **-10 meV**, a looser threshold than the **-20 meV** it certifies at under the stricter family-corrected standard. That is not an inconsistency: `certify` returns the *loosest* threshold whose bound clears the target, and at the stricter level -10 meV no longer clears, so it falls back to -20 meV. A stricter correction buying a tighter threshold is the expected behaviour.

