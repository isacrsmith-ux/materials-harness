# Round 2 — certification and diagnosis

Engine: MACE-MPA-0 medium, cpu/float32, settings_tag `c2480e74` (asserted at the start of every phase). Generated 2026-09-18T09:58:19+00:00.

Method is test 7's, unchanged: Clopper-Pearson one-sided bounds (never bootstrap), Bonferroni-corrected over the threshold grid so picking the best threshold keeps the guarantee, verdicts read from the pessimistic end, and guard rejections counted-and-excluded rather than dropped.

## Summary

| group | n requested | n usable | rejected (counted, excluded) | base rate | stable side | unstable side |
|---|---:|---:|---:|---:|---|---|
| sulfide | 4000 | 4000 | 0 | 0.128 | not certified | **-10 meV** |
| nitride | 2423 | 2423 | 0 | 0.092 | not certified | **-10 meV** |
| carbide | 1876 | 1876 | 0 | 0.099 | **-20 meV** | **-10 meV** |

## Diagnosis — sample-size limited or precision limited

`n structures needed` converts `n selected needed` by the group's own selection rate: it is how large the calibration set would have to be, not how many calls. A figure larger than WBM's whole 215,488-structure unique-prototype pool means the group is sample-size limited only in principle.

| group | side | target | best t | n selected | k | point | CP-lower | verdict | n selected needed | n structures needed | factor |
|---|---|---:|---|---:|---:|---:|---:|---|---:|---:|---:|
| sulfide | stable | 0.90 | -90 meV | 101 | 98 | 0.9703 | 0.8747 | sample-size limited | 162 | 6416 | 1.60 |
| sulfide | unstable | 0.95 | +90 meV | 1993 | 1992 | 0.9995 | 0.9953 | certified | - | - | - |
| nitride | stable | 0.90 | -40 meV | 71 | 70 | 0.9859 | 0.8745 | sample-size limited | 91 | 3106 | 1.28 |
| nitride | unstable | 0.95 | +120 meV | 1432 | 1429 | 0.9979 | 0.9907 | certified | - | - | - |
| carbide | stable | 0.90 | -30 meV | 97 | 97 | 1.0000 | 0.9294 | certified | - | - | - |
| carbide | unstable | 0.95 | +50 meV | 1521 | 1521 | 1.0000 | 0.9953 | certified | - | - | - |

### Stable side at the alternate 0.80 target (test 7's fallback)

| group | best t | n selected | point | CP-lower | certified at 0.80 |
|---|---|---:|---:|---:|---|
| sulfide | -90 meV | 101 | 0.9703 | 0.8747 | -10 meV |
| nitride | -40 meV | 71 | 0.9859 | 0.8745 | -10 meV |

## Routing impact of the certified 'likely unstable' threshold

A satisfied NPV target is not the same as keeping your discoveries: both columns belong to any proposal to route on these thresholds.

| group | threshold | share discarded without DFT | truly stable lost | (of) |
|---|---|---:|---:|---:|
| sulfide | -10 meV | 0.897 | 0.269 | 137 of 510 |
| nitride | -10 meV | 0.934 | 0.351 | 78 of 222 |
| carbide | -10 meV | 0.922 | 0.247 | 46 of 186 |

## Precision of the 'likely stable' call by TRUE hull-distance bin

At each group's certified stable threshold, or its best point threshold when nothing certified.

**sulfide** (threshold -90 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 98 | 98 | 1.000 |
| 0–0.025 | 0 | 0 | - |
| 0.025–0.1 | 3 | 0 | 0.000 |
| 0.1–0.3 | 0 | 0 | - |
| >0.3 | 0 | 0 | - |

**nitride** (threshold -40 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 70 | 70 | 1.000 |
| 0–0.025 | 0 | 0 | - |
| 0.025–0.1 | 1 | 0 | 0.000 |
| 0.1–0.3 | 0 | 0 | - |
| >0.3 | 0 | 0 | - |

**carbide** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 117 | 117 | 1.000 |
| 0–0.025 | 2 | 0 | 0.000 |
| 0.025–0.1 | 0 | 0 | - |
| 0.1–0.3 | 0 | 0 | - |
| >0.3 | 0 | 0 | - |

