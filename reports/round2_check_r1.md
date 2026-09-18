# Round 2 — certification and diagnosis

Engine: MACE-MPA-0 medium, cpu/float32, settings_tag `c2480e74` (asserted at the start of every phase). Generated 2026-09-18T03:36:33+00:00.

Method is test 7's, unchanged: Clopper-Pearson one-sided bounds (never bootstrap), Bonferroni-corrected over the threshold grid so picking the best threshold keeps the guarantee, verdicts read from the pessimistic end, and guard rejections counted-and-excluded rather than dropped.

## Summary

| group | n requested | n usable | rejected (counted, excluded) | base rate | stable side | unstable side |
|---|---:|---:|---:|---:|---|---|
| oxide | 4000 | 3994 | 6 | 0.112 | not certified | **+0 meV** |
| halide | 3500 | 3500 | 0 | 0.232 | not certified | **+0 meV** |

## Diagnosis — sample-size limited or precision limited

| group | side | target | best t | n selected | k | point | CP-lower | verdict | n selected needed | factor |
|---|---|---:|---|---:|---:|---:|---:|---|---:|---:|
| oxide | stable | 0.90 | -20 meV | 272 | 238 | 0.8750 | 0.8005 | precision limited | - | - |
| oxide | unstable | 0.95 | +60 meV | 2495 | 2489 | 0.9976 | 0.9927 | certified | 139 | 0.06 |
| halide | stable | 0.90 | -70 meV | 267 | 251 | 0.9401 | 0.8803 | sample-size limited | 530 | 1.99 |
| halide | unstable | 0.95 | +100 meV | 1009 | 1007 | 0.9980 | 0.9887 | certified | 139 | 0.14 |

### Stable side at the alternate 0.80 target (test 7's fallback)

| group | best t | n selected | point | CP-lower | certified at 0.80 |
|---|---|---:|---:|---:|---|
| oxide | -20 meV | 272 | 0.8750 | 0.8005 | -20 meV |
| halide | -70 meV | 267 | 0.9401 | 0.8803 | -10 meV |

## Precision of the 'likely stable' call by TRUE hull-distance bin

At each group's certified stable threshold, or its best point threshold when nothing certified.

**oxide** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 238 | 238 | 1.000 |
| 0–0.025 | 4 | 0 | 0.000 |
| 0.025–0.1 | 11 | 0 | 0.000 |
| 0.1–0.3 | 6 | 0 | 0.000 |
| >0.3 | 13 | 0 | 0.000 |

**halide** (threshold -70 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 251 | 251 | 1.000 |
| 0–0.025 | 4 | 0 | 0.000 |
| 0.025–0.1 | 5 | 0 | 0.000 |
| 0.1–0.3 | 6 | 0 | 0.000 |
| >0.3 | 1 | 0 | 0.000 |

