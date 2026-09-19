# Round 4b — the `with_second_engine` production path on the round-4 draw

Generated 2026-09-19T00:30:24+00:00. Production engine MACE-MPA-0 medium (`c2480e74`), second engine MACE-MP-0 medium (`207ccc81`). **Exactly the 12,000 round-4 ids — no new structures, no new draw, no locked data.** Disagreement tolerance from the frozen bundle: `0.165255` eV/atom.

**Thresholds are fixed.** Every figure applies a threshold already in `data/calibration_bundle.json` to the population the production filter selects. Nothing is refitted, and no threshold, taxonomy or exclusion was changed.

Three populations, so the second engine's contribution is separable:

| path | filter |
|---|---|
| **A** single engine | weak elements + structure change (`max_trustworthy_hull=None`) — the footing the bundle was fitted on and round 4 reported |
| **B** + disagreement | A, plus a label refused when the two engines differ by more than the tolerance — what `with_second_engine` adds |
| **C** product | B, plus the >0.3 eV/atom refusal (`predict.MAX_TRUSTWORTHY_HULL_EV`) — the actual path `harness.predict` takes |

## 1. Second-engine coverage and disagreement

| family | drawn | engine-1 usable | engine-2 usable | **no 2nd-engine result** | disagreeing pairs | disagree rate | median gap | p90 gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| f-electron | 4,000 | 4,000 | 3,993 | **7** | 214 | 0.0535 | 0.0289 | 0.1157 |
| intermetallic | 4,000 | 4,000 | 4,000 | **0** | 82 | 0.0205 | 0.0276 | 0.0930 |
| pnictide | 4,000 | 4,000 | 4,000 | **0** | 160 | 0.0400 | 0.0353 | 0.1200 |

A row with **no second-engine result** passes the disagreement term untested: `abs(NaN) > tol` is False. That is production's real behaviour — `predict` warns that "the certified thresholds in use assume the disagreement check ran" and labels the candidate anyway — so it is reported, not silently folded in.

## 2. The three paths, fixed thresholds

| family | path | rule (stable / unstable) | fitted on n | n labelable | base rate | stable calls | precision | CP-lower | called unstable | NPV | CP-lower | recall | to DFT |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| f-electron | A single engine | -20 meV / +10 meV | 1,801 | 3,495 | 0.185 | 441 | 0.9388 | 0.8944 | 2,657 | 0.9868 | 0.9783 | 0.641 | 0.114 |
| f-electron | B + disagreement | -20 meV / +10 meV | 1,747 | 3,412 | 0.186 | 429 | 0.9441 | 0.9004 | 2,589 | 0.9865 | 0.9777 | 0.637 | 0.115 |
| f-electron | C + >0.3 refusal (product) | -20 meV / +10 meV | 1,747 | 3,130 | 0.203 | 429 | 0.9441 | 0.9004 | 2,307 | 0.9848 | 0.9750 | 0.637 | 0.126 |
| intermetallic | A single engine | none / +0 meV | 665 | 3,613 | 0.097 | 0 | - | - | 3,251 | 0.9843 | 0.9762 | 0.000 | 0.100 |
| intermetallic | B + disagreement | none / +0 meV | 645 | 3,547 | 0.099 | 0 | - | - | 3,186 | 0.9840 | 0.9757 | 0.000 | 0.102 |
| intermetallic | C + >0.3 refusal (product) | none / +0 meV | 645 | 3,073 | 0.114 | 0 | - | - | 2,712 | 0.9812 | 0.9715 | 0.000 | 0.117 |
| pnictide | A single engine | none / +50 meV | 210 | 3,637 | 0.139 | 0 | - | - | 2,502 | 0.9976 | 0.9927 | 0.000 | 0.312 |
| pnictide | B + disagreement | none / none | 202 | 3,501 | 0.144 | 0 | - | - | 0 | - | - | 0.000 | 1.000 |
| pnictide | C + >0.3 refusal (product) | none / none | 202 | 3,133 | 0.161 | 0 | - | - | 0 | - | - | 0.000 | 1.000 |

`-` in a precision column means the rule makes no stable call for that family, so every such candidate goes to DFT. Bounds are one-sided Clopper-Pearson at 0.95, Bonferroni-corrected over the 61-point grid.

## 3. What the disagreement term actually removes

If the second engine is earning its place, the rows it removes should be enriched in the errors the stable rule would otherwise have made.

| family | rows removed from A | of those, called stable by A's rule | of those, wrong | base rate of removed rows |
|---|---:|---:|---:|---:|
| f-electron | 83 | 12 | 3 | 0.120 |
| intermetallic | 66 | 0 | 0 | 0.015 |
| pnictide | 136 | 0 | 0 | 0.000 |

