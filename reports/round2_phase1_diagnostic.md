# Round 2 — certification and diagnosis

Engine: MACE-MPA-0 medium, cpu/float32, settings_tag `c2480e74` (asserted at the start of every phase). Generated 2026-09-18T16:22:20+00:00.

Method is test 7's, unchanged: Clopper-Pearson one-sided bounds (never bootstrap), Bonferroni-corrected over the threshold grid so picking the best threshold keeps the guarantee, verdicts read from the pessimistic end, and guard rejections counted-and-excluded rather than dropped.

## Summary

| group | n requested | n usable | rejected (counted, excluded) | base rate | stable side | unstable side |
|---|---:|---:|---:|---:|---|---|
| sulfide@p1 | 500 | 500 | 0 | 0.144 | not certified | **+10 meV** |
| nitride@p1 | 500 | 500 | 0 | 0.092 | not certified | **+10 meV** |
| carbide@p1 | 500 | 500 | 0 | 0.102 | not certified | **+0 meV** |
| halide:fluoride | 1208 | 1208 | 0 | 0.248 | not certified | **+10 meV** |
| halide:nonfluoride | 2292 | 2292 | 0 | 0.224 | not certified | **+0 meV** |

## Diagnosis — sample-size limited or precision limited

`n structures needed` converts `n selected needed` by the group's own selection rate: it is how large the calibration set would have to be, not how many calls. A figure larger than WBM's whole 215,488-structure unique-prototype pool means the group is sample-size limited only in principle.

| group | side | target | best t | n selected | k | point | CP-lower | verdict | n selected needed | n structures needed | factor |
|---|---|---:|---|---:|---:|---:|---:|---|---:|---:|---:|
| sulfide@p1 | stable | 0.90 | -10 meV | 54 | 51 | 0.9444 | 0.7758 | sample-size limited | 415 | 3843 | 7.69 |
| sulfide@p1 | unstable | 0.95 | +30 meV | 360 | 359 | 0.9972 | 0.9740 | certified | - | - | - |
| nitride@p1 | stable | 0.90 | -10 meV | 35 | 34 | 0.9714 | 0.7602 | sample-size limited | 162 | 2315 | 4.63 |
| nitride@p1 | unstable | 0.95 | +80 meV | 350 | 350 | 1.0000 | 0.9799 | certified | - | - | - |
| carbide@p1 | stable | 0.90 | -30 meV | 29 | 29 | 1.0000 | 0.7827 | sample-size limited | 68 | 1173 | 2.34 |
| carbide@p1 | unstable | 0.95 | +30 meV | 415 | 415 | 1.0000 | 0.9830 | certified | - | - | - |
| halide:fluoride | stable | 0.90 | -20 meV | 219 | 192 | 0.8767 | 0.7926 | precision limited | - | - | - |
| halide:fluoride | unstable | 0.95 | +50 meV | 494 | 494 | 1.0000 | 0.9857 | certified | - | - | - |
| halide:nonfluoride | stable | 0.90 | -50 meV | 225 | 215 | 0.9556 | 0.8947 | sample-size limited | 252 | 2568 | 1.12 |
| halide:nonfluoride | unstable | 0.95 | +100 meV | 705 | 703 | 0.9972 | 0.9838 | certified | - | - | - |

### Stable side at the alternate 0.80 target (test 7's fallback)

| group | best t | n selected | point | CP-lower | certified at 0.80 |
|---|---|---:|---:|---:|---|
| sulfide@p1 | -10 meV | 54 | 0.9444 | 0.7758 | no |
| nitride@p1 | -10 meV | 35 | 0.9714 | 0.7602 | no |
| carbide@p1 | -30 meV | 29 | 1.0000 | 0.7827 | no |
| halide:fluoride | -20 meV | 219 | 0.8767 | 0.7926 | no |
| halide:nonfluoride | -50 meV | 225 | 0.9556 | 0.8947 | -10 meV |

## Routing impact of the certified 'likely unstable' threshold

A satisfied NPV target is not the same as keeping your discoveries: both columns belong to any proposal to route on these thresholds.

| group | threshold | share discarded without DFT | truly stable lost | (of) |
|---|---|---:|---:|---:|
| sulfide@p1 | +10 meV | 0.806 | 0.097 | 7 of 72 |
| nitride@p1 | +10 meV | 0.890 | 0.130 | 6 of 46 |
| carbide@p1 | +0 meV | 0.890 | 0.078 | 4 of 51 |
| halide:fluoride | +10 meV | 0.653 | 0.037 | 11 of 300 |
| halide:nonfluoride | +0 meV | 0.760 | 0.107 | 55 of 513 |

## Precision of the 'likely stable' call by TRUE hull-distance bin

At each group's certified stable threshold, or its best point threshold when nothing certified.

**sulfide@p1** (threshold -10 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 51 | 51 | 1.000 |
| 0–0.025 | 1 | 0 | 0.000 |
| 0.025–0.1 | 1 | 0 | 0.000 |
| 0.1–0.3 | 1 | 0 | 0.000 |
| >0.3 | 0 | 0 | - |

**nitride@p1** (threshold -10 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 34 | 34 | 1.000 |
| 0–0.025 | 1 | 0 | 0.000 |
| 0.025–0.1 | 0 | 0 | - |
| 0.1–0.3 | 0 | 0 | - |
| >0.3 | 0 | 0 | - |

**carbide@p1** (threshold -30 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 29 | 29 | 1.000 |
| 0–0.025 | 0 | 0 | - |
| 0.025–0.1 | 0 | 0 | - |
| 0.1–0.3 | 0 | 0 | - |
| >0.3 | 0 | 0 | - |

**halide:fluoride** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 192 | 192 | 1.000 |
| 0–0.025 | 7 | 0 | 0.000 |
| 0.025–0.1 | 13 | 0 | 0.000 |
| 0.1–0.3 | 5 | 0 | 0.000 |
| >0.3 | 2 | 0 | 0.000 |

**halide:nonfluoride** (threshold -50 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 215 | 215 | 1.000 |
| 0–0.025 | 4 | 0 | 0.000 |
| 0.025–0.1 | 2 | 0 | 0.000 |
| 0.1–0.3 | 4 | 0 | 0.000 |
| >0.3 | 0 | 0 | - |

