# Round 2 — certification and diagnosis

Engine: MACE-MPA-0 medium, cpu/float32, settings_tag `c2480e74` (asserted at the start of every phase). Generated 2026-09-18T10:19:06+00:00.

Method is test 7's, unchanged: Clopper-Pearson one-sided bounds (never bootstrap), Bonferroni-corrected over the threshold grid so picking the best threshold keeps the guarantee, verdicts read from the pessimistic end, and guard rejections counted-and-excluded rather than dropped.

## Summary

| group | n requested | n usable | rejected (counted, excluded) | base rate | stable side | unstable side |
|---|---:|---:|---:|---:|---|---|
| halide | 3500 | 3500 | 0 | 0.232 | not certified | **+0 meV** |
| halide_topup | 2800 | 2800 | 0 | 0.238 | not certified | **+0 meV** |
| halide_combined | 6300 | 6300 | 0 | 0.235 | **-70 meV** | **+0 meV** |
| halide_combined:fluoride | 2241 | 2241 | 0 | 0.250 | not certified | **+10 meV** |
| halide_combined:nonfluoride | 4059 | 4059 | 0 | 0.226 | **-20 meV** | **+0 meV** |

## Diagnosis — sample-size limited or precision limited

`n structures needed` converts `n selected needed` by the group's own selection rate: it is how large the calibration set would have to be, not how many calls. A figure larger than WBM's whole 215,488-structure unique-prototype pool means the group is sample-size limited only in principle.

| group | side | target | best t | n selected | k | point | CP-lower | verdict | n selected needed | n structures needed | factor |
|---|---|---:|---|---:|---:|---:|---:|---|---:|---:|---:|
| halide | stable | 0.90 | -70 meV | 267 | 251 | 0.9401 | 0.8803 | sample-size limited | 530 | 6948 | 1.99 |
| halide | unstable | 0.95 | +100 meV | 1009 | 1007 | 0.9980 | 0.9887 | certified | - | - | - |
| halide_topup | stable | 0.90 | -60 meV | 243 | 231 | 0.9506 | 0.8909 | sample-size limited | 322 | 3711 | 1.33 |
| halide_topup | unstable | 0.95 | +120 meV | 713 | 713 | 1.0000 | 0.9901 | certified | - | - | - |
| halide_combined | stable | 0.90 | -70 meV | 480 | 453 | 0.9437 | 0.9028 | certified | - | - | - |
| halide_combined | unstable | 0.95 | +100 meV | 1843 | 1840 | 0.9984 | 0.9928 | certified | - | - | - |
| halide_combined:fluoride | stable | 0.90 | -70 meV | 175 | 158 | 0.9029 | 0.8133 | sample-size limited | 108789 | 1393121 | 621.65 |
| halide_combined:fluoride | unstable | 0.95 | +60 meV | 847 | 846 | 0.9988 | 0.9889 | certified | - | - | - |
| halide_combined:nonfluoride | stable | 0.90 | -70 meV | 305 | 295 | 0.9672 | 0.9217 | certified | - | - | - |
| halide_combined:nonfluoride | unstable | 0.95 | +100 meV | 1259 | 1257 | 0.9984 | 0.9909 | certified | - | - | - |

### Stable side at the alternate 0.80 target (test 7's fallback)

| group | best t | n selected | point | CP-lower | certified at 0.80 |
|---|---|---:|---:|---:|---|
| halide | -70 meV | 267 | 0.9401 | 0.8803 | -10 meV |
| halide_topup | -60 meV | 243 | 0.9506 | 0.8909 | -10 meV |
| halide_combined:fluoride | -70 meV | 175 | 0.9029 | 0.8133 | -30 meV |

## Routing impact of the certified 'likely unstable' threshold

A satisfied NPV target is not the same as keeping your discoveries: both columns belong to any proposal to route on these thresholds.

| group | threshold | share discarded without DFT | truly stable lost | (of) |
|---|---|---:|---:|---:|
| halide | +0 meV | 0.747 | 0.114 | 93 of 813 |
| halide_topup | +0 meV | 0.740 | 0.108 | 72 of 666 |
| halide_combined | +0 meV | 0.744 | 0.112 | 165 of 1479 |
| halide_combined:fluoride | +10 meV | 0.644 | 0.045 | 25 of 561 |
| halide_combined:nonfluoride | +0 meV | 0.759 | 0.102 | 94 of 918 |

## Precision of the 'likely stable' call by TRUE hull-distance bin

At each group's certified stable threshold, or its best point threshold when nothing certified.

**halide** (threshold -70 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 251 | 251 | 1.000 |
| 0–0.025 | 4 | 0 | 0.000 |
| 0.025–0.1 | 5 | 0 | 0.000 |
| 0.1–0.3 | 6 | 0 | 0.000 |
| >0.3 | 1 | 0 | 0.000 |

**halide_topup** (threshold -60 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 231 | 231 | 1.000 |
| 0–0.025 | 2 | 0 | 0.000 |
| 0.025–0.1 | 5 | 0 | 0.000 |
| 0.1–0.3 | 4 | 0 | 0.000 |
| >0.3 | 1 | 0 | 0.000 |

**halide_combined** (threshold -70 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 453 | 453 | 1.000 |
| 0–0.025 | 5 | 0 | 0.000 |
| 0.025–0.1 | 10 | 0 | 0.000 |
| 0.1–0.3 | 10 | 0 | 0.000 |
| >0.3 | 2 | 0 | 0.000 |

**halide_combined:fluoride** (threshold -70 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 158 | 158 | 1.000 |
| 0–0.025 | 2 | 0 | 0.000 |
| 0.025–0.1 | 7 | 0 | 0.000 |
| 0.1–0.3 | 6 | 0 | 0.000 |
| >0.3 | 2 | 0 | 0.000 |

**halide_combined:nonfluoride** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 582 | 582 | 1.000 |
| 0–0.025 | 18 | 0 | 0.000 |
| 0.025–0.1 | 14 | 0 | 0.000 |
| 0.1–0.3 | 6 | 0 | 0.000 |
| >0.3 | 0 | 0 | - |

