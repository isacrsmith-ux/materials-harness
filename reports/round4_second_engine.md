# Round 4b — the `with_second_engine` production path on the round-4 draw

Generated 2026-09-19T00:33:44+00:00. Production engine MACE-MPA-0 medium (`c2480e74`), second engine MACE-MP-0 medium (`207ccc81`). **Exactly the 12,000 round-4 ids — no new structures, no new draw, no locked data.** Disagreement tolerance from the frozen bundle: `0.165255` eV/atom.

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

## 4. What this shows

### 4.1 Supplying a second engine makes the product WORSE across these three families

| | labelable | weighted DFT share |
|---|---:|---:|
| A single engine | 10,745 | 0.1763 |
| C product (2nd engine supplied) | 9,336 | 0.4165 |

Adding a second engine's information more than doubles the share sent to DFT. That is perverse, and it is not the engines' fault: it is the `with_second_engine` rule table, whose entries for these families were fitted on 1,747 / 645 / 202 rows in 2026-09-12 and have never been re-measured.

### 4.2 pnictide has NO rule at all on the with_second_engine path

`with_second_engine` gives pnictide `stable: none / unstable: none` (fitted on n=202). So every pnictide candidate is sent to DFT: DFT share **1.0000** against **0.3121** on the single-engine path — 2,502 routings away from DFT lost outright.

This is the dominant term in 4.1. Round 4 measured that pnictide certifies **both** sides on 3,637 single-engine labelable rows (-20 / +0 meV, bounds 0.9128 / 0.9638), so the emptiness is a sample-size artefact of the original fit, not a property of the chemistry. Whether it is also fixable *on the with-second-engine footing* is NOT answered here: that needs a fit on the path-B population, which would be a refit and was not performed.

### 4.3 The second engine rescues f-electron's stable rule by 0.0004

| path | calls | correct | point | CP-lower | clears 0.90? | if one more call were wrong |
|---|---:|---:|---:|---:|---|---:|
| A single engine | 441 | 414 | 0.9388 | **0.894441** | **no** | 0.891612 |
| B + disagreement | 429 | 405 | 0.9441 | **0.900359** | **yes** | 0.897412 |

The disagreement term removes 83 rows, 12 of which the stable rule had called stable, 3 of those wrongly - a 4x enrichment in errors over the 6.1% base error rate of stable calls. The filter is doing real work. But it is doing it on 12 of 441 calls, and the resulting bound clears the target by **0.000359**. One further error takes it to 0.8974. That is not a margin; it is a knife edge, and it should not be described as a certification that holds.

### 4.4 intermetallic is unaffected and still labels nothing stable

v1 has no intermetallic stable rule on either path, so the second engine changes nothing except to send slightly more to DFT (0.100 -> 0.117). The 66 rows its disagreement term removes contain 0 stable calls and have a base rate of 0.015 - it is removing rows that were heading to an unstable call anyway.

### 4.5 Scope

Development evidence on development data. Nothing here is a held-out result, no threshold was refitted, and no change to the bundle, taxonomy or exclusions is adopted or implied by this document.

