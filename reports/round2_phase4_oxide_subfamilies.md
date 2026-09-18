# Round 2 — certification and diagnosis

Engine: MACE-MPA-0 medium, cpu/float32, settings_tag `c2480e74` (asserted at the start of every phase). Generated 2026-09-18T03:56:48+00:00.

Method is test 7's, unchanged: Clopper-Pearson one-sided bounds (never bootstrap), Bonferroni-corrected over the threshold grid so picking the best threshold keeps the guarantee, verdicts read from the pessimistic end, and guard rejections counted-and-excluded rather than dropped.

## Summary

| group | n requested | n usable | rejected (counted, excluded) | base rate | stable side | unstable side |
|---|---:|---:|---:|---:|---|---|
| oxide | 4000 | 3994 | 6 | 0.112 | not certified | **+0 meV** |
| oxide:tm | 3153 | 3153 | 6 | 0.105 | not certified | **-10 meV** |
| oxide:maingroup | 841 | 841 | 6 | 0.136 | not certified | **+0 meV** |
| oxide:multi_tm | 871 | 871 | 6 | 0.096 | not certified | **+0 meV** |
| oxide:single_tm | 3123 | 3123 | 6 | 0.116 | not certified | **+0 meV** |
| oxide:mixed_valence | 1266 | 1266 | 6 | 0.087 | not certified | **-10 meV** |
| oxide:single_valence | 2728 | 2728 | 6 | 0.123 | not certified | **+0 meV** |
| oxide:ox_le2 | 371 | 371 | 6 | 0.092 | not certified | **+10 meV** |
| oxide:ox_3 | 642 | 642 | 6 | 0.072 | not certified | **+0 meV** |
| oxide:ox_4 | 793 | 793 | 6 | 0.107 | not certified | **+0 meV** |
| oxide:ox_ge5 | 854 | 854 | 6 | 0.193 | not certified | **+10 meV** |

## Diagnosis — sample-size limited or precision limited

| group | side | target | best t | n selected | k | point | CP-lower | verdict | n selected needed | factor |
|---|---|---:|---|---:|---:|---:|---:|---|---:|---:|
| oxide | stable | 0.90 | -20 meV | 272 | 238 | 0.8750 | 0.8005 | precision limited | - | - |
| oxide | unstable | 0.95 | +60 meV | 2495 | 2489 | 0.9976 | 0.9927 | certified | - | - |
| oxide:tm | stable | 0.90 | -20 meV | 218 | 185 | 0.8486 | 0.7591 | precision limited | - | - |
| oxide:tm | unstable | 0.95 | +100 meV | 1575 | 1573 | 0.9987 | 0.9927 | certified | - | - |
| oxide:maingroup | stable | 0.90 | -20 meV | 54 | 53 | 0.9815 | 0.8380 | sample-size limited | 110 | 2.04 |
| oxide:maingroup | unstable | 0.95 | +50 meV | 530 | 528 | 0.9962 | 0.9786 | certified | - | - |
| oxide:multi_tm | stable | 0.90 | +0 meV | 81 | 68 | 0.8395 | 0.6783 | precision limited | - | - |
| oxide:multi_tm | unstable | 0.95 | +60 meV | 566 | 566 | 1.0000 | 0.9875 | certified | - | - |
| oxide:single_tm | stable | 0.90 | -30 meV | 177 | 157 | 0.8870 | 0.7941 | precision limited | - | - |
| oxide:single_tm | unstable | 0.95 | +50 meV | 2058 | 2052 | 0.9971 | 0.9911 | certified | - | - |
| oxide:mixed_valence | stable | 0.90 | -30 meV | 52 | 49 | 0.9423 | 0.7681 | sample-size limited | 467 | 8.98 |
| oxide:mixed_valence | unstable | 0.95 | +60 meV | 922 | 920 | 0.9978 | 0.9876 | certified | - | - |
| oxide:single_valence | stable | 0.90 | -20 meV | 200 | 174 | 0.8700 | 0.7799 | precision limited | - | - |
| oxide:single_valence | unstable | 0.95 | +50 meV | 1706 | 1702 | 0.9977 | 0.9912 | certified | - | - |
| oxide:ox_le2 | stable | 0.90 | -10 meV | 28 | 21 | 0.7500 | 0.4383 | precision limited | - | - |
| oxide:ox_le2 | unstable | 0.95 | +10 meV | 294 | 294 | 1.0000 | 0.9761 | certified | - | - |
| oxide:ox_3 | stable | 0.90 | -20 meV | 33 | 24 | 0.7273 | 0.4409 | precision limited | - | - |
| oxide:ox_3 | unstable | 0.95 | +40 meV | 497 | 494 | 0.9940 | 0.9735 | certified | - | - |
| oxide:ox_4 | stable | 0.90 | -20 meV | 42 | 42 | 1.0000 | 0.8443 | sample-size limited | 68 | 1.62 |
| oxide:ox_4 | unstable | 0.95 | +20 meV | 620 | 619 | 0.9984 | 0.9849 | certified | - | - |
| oxide:ox_ge5 | stable | 0.90 | -20 meV | 97 | 87 | 0.8969 | 0.7662 | precision limited | - | - |
| oxide:ox_ge5 | unstable | 0.95 | +50 meV | 431 | 431 | 1.0000 | 0.9836 | certified | - | - |

### Stable side at the alternate 0.80 target (test 7's fallback)

| group | best t | n selected | point | CP-lower | certified at 0.80 |
|---|---|---:|---:|---:|---|
| oxide | -20 meV | 272 | 0.8750 | 0.8005 | -20 meV |
| oxide:tm | -20 meV | 218 | 0.8486 | 0.7591 | no |
| oxide:maingroup | -20 meV | 54 | 0.9815 | 0.8380 | -10 meV |
| oxide:multi_tm | +0 meV | 81 | 0.8395 | 0.6783 | no |
| oxide:single_tm | -30 meV | 177 | 0.8870 | 0.7941 | no |
| oxide:mixed_valence | -30 meV | 52 | 0.9423 | 0.7681 | no |
| oxide:single_valence | -20 meV | 200 | 0.8700 | 0.7799 | no |
| oxide:ox_le2 | -10 meV | 28 | 0.7500 | 0.4383 | no |
| oxide:ox_3 | -20 meV | 33 | 0.7273 | 0.4409 | no |
| oxide:ox_4 | -20 meV | 42 | 1.0000 | 0.8443 | -20 meV |
| oxide:ox_ge5 | -20 meV | 97 | 0.8969 | 0.7662 | no |

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

**oxide:tm** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 185 | 185 | 1.000 |
| 0–0.025 | 4 | 0 | 0.000 |
| 0.025–0.1 | 11 | 0 | 0.000 |
| 0.1–0.3 | 6 | 0 | 0.000 |
| >0.3 | 12 | 0 | 0.000 |

**oxide:maingroup** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 53 | 53 | 1.000 |
| 0–0.025 | 0 | 0 | - |
| 0.025–0.1 | 0 | 0 | - |
| 0.1–0.3 | 0 | 0 | - |
| >0.3 | 1 | 0 | 0.000 |

**oxide:multi_tm** (threshold +0 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 68 | 68 | 1.000 |
| 0–0.025 | 6 | 0 | 0.000 |
| 0.025–0.1 | 1 | 0 | 0.000 |
| 0.1–0.3 | 3 | 0 | 0.000 |
| >0.3 | 3 | 0 | 0.000 |

**oxide:single_tm** (threshold -30 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 157 | 157 | 1.000 |
| 0–0.025 | 1 | 0 | 0.000 |
| 0.025–0.1 | 5 | 0 | 0.000 |
| 0.1–0.3 | 4 | 0 | 0.000 |
| >0.3 | 10 | 0 | 0.000 |

**oxide:mixed_valence** (threshold -30 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 49 | 49 | 1.000 |
| 0–0.025 | 0 | 0 | - |
| 0.025–0.1 | 0 | 0 | - |
| 0.1–0.3 | 0 | 0 | - |
| >0.3 | 3 | 0 | 0.000 |

**oxide:single_valence** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 174 | 174 | 1.000 |
| 0–0.025 | 3 | 0 | 0.000 |
| 0.025–0.1 | 7 | 0 | 0.000 |
| 0.1–0.3 | 6 | 0 | 0.000 |
| >0.3 | 10 | 0 | 0.000 |

**oxide:ox_le2** (threshold -10 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 21 | 21 | 1.000 |
| 0–0.025 | 0 | 0 | - |
| 0.025–0.1 | 2 | 0 | 0.000 |
| 0.1–0.3 | 3 | 0 | 0.000 |
| >0.3 | 2 | 0 | 0.000 |

**oxide:ox_3** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 24 | 24 | 1.000 |
| 0–0.025 | 0 | 0 | - |
| 0.025–0.1 | 0 | 0 | - |
| 0.1–0.3 | 2 | 0 | 0.000 |
| >0.3 | 7 | 0 | 0.000 |

**oxide:ox_4** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 42 | 42 | 1.000 |
| 0–0.025 | 0 | 0 | - |
| 0.025–0.1 | 0 | 0 | - |
| 0.1–0.3 | 0 | 0 | - |
| >0.3 | 0 | 0 | - |

**oxide:ox_ge5** (threshold -20 meV)

| true hull bin | n selected | n correct | precision |
|---|---:|---:|---:|
| <0 | 87 | 87 | 1.000 |
| 0–0.025 | 3 | 0 | 0.000 |
| 0.025–0.1 | 6 | 0 | 0.000 |
| 0.1–0.3 | 1 | 0 | 0.000 |
| >0.3 | 0 | 0 | - |

