# Round 4 development results — the three carried-over families

> **Round 4 and Path-B results are development/calibration results. Unless explicitly identified as preregistered held-out results, they must not be interpreted as independent estimates of production performance.**

Aggregate, public-safe export. No material identifiers, no seeds, no row-level data - see [WITHHELD.md](WITHHELD.md). Methodology: [statistics](../../docs/methodology/statistics.md), [evidence tiers](../../docs/methodology/evidence_tiers.md), [provenance](../../docs/methodology/data_provenance.md), [environment](../../docs/methodology/environment.md). Machine-readable: [`results/public/`](../../results/public/SCHEMA.md).

## 1. Population and every exclusion

| family | drawn | guard-rejected (e1/e2) | usable | not labelable | labelable A | labelable B | removed by disagreement | no 2nd-engine result | failed jobs | base rate |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| f-electron | 4,000 | 0/7 | 4,000 | 505 | 3,495 | 3,412 | 83 | 7 | 0 | 0.185 |
| intermetallic | 4,000 | 0/0 | 4,000 | 387 | 3,613 | 3,547 | 66 | 0 | 0 | 0.097 |
| pnictide | 4,000 | 0/0 | 4,000 | 363 | 3,637 | 3,501 | 136 | 0 | 0 | 0.139 |

Guard rejections and non-labelable rows are counted and excluded, never dropped silently. Zero jobs failed. Path B is a strict subset of Path A.

## 2. Round 4 - the single-engine development fit

| family | side | threshold | calls | errors | point | CP-lower | target | margin | recall | to DFT |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| f-electron | stable | none | 0 | - | - | - | 0.9 | - | 0.000 | 0.196 |
| f-electron | unstable | +0 meV | 2,809 | 71 | 0.9747 | 0.9640 | 0.95 | +0.0140 | 0.000 | 0.196 |
| intermetallic | stable | -20 meV | 182 | 4 | 0.9780 | 0.9197 | 0.9 | +0.0197 | 0.506 | 0.018 |
| intermetallic | unstable | -10 meV | 3,365 | 115 | 0.9658 | 0.9548 | 0.95 | +0.0048 | 0.506 | 0.018 |
| pnictide | stable | -20 meV | 306 | 12 | 0.9608 | 0.9128 | 0.9 | +0.0128 | 0.583 | 0.049 |
| pnictide | unstable | +0 meV | 3,154 | 82 | 0.9740 | 0.9638 | 0.95 | +0.0138 | 0.583 | 0.049 |

**pnictide gained both sides**, on 3,637 rows against the 210 its production threshold was fitted on: DFT routing falls from 0.312 to 0.049 and recall of truly stable materials rises from 0 to 0.583. **intermetallic gained a stable side** on 3,613 rows against 665. **f-electron lost its stable side** - no threshold certifies at n=3,495.

### 2.1 The f-electron non-replication (negative result)

f-electron is the only family that can currently return *likely stable* in production. Its live -20 meV rule, applied unchanged to both populations:

| sample | labelable | calls | correct | point | CP-lower | clears 0.90? |
|---|---:|---:|---:|---:|---:|---|
| original (the rule's own fitting population) | 1,801 | 206 | 199 | 0.9660 | 0.9063 | yes |
| round 4 (fresh, disjoint, composition-matched) | 3,495 | 441 | 414 | 0.9388 | **0.8944** | **no** |

Difference +0.0272 (SE 0.0188, z 1.45, two-sided p 0.148): the samples are **not statistically distinguishable**, and they are **not pooled** - pooling a fitting population with a fresh one produces a number that is neither, and converts a failed replication into a tuned threshold.

This is not evidence that the rule is invalid. It is evidence that its certification was **marginal** - a bound of 0.9063 on 206 calls - and does not replicate as a certification on a matched sample twice the size. Base rates were checked first and match closely (0.1866 against 0.1848), so this is not a composition artefact.

## 3. The second-engine path: A / B-old / B-refit

Path A applies no disagreement term. B-old is the rule table production uses today when a second engine is supplied. B-refit was fitted on the Path-B development population.

| family | path | stable | calls | err | precision | CP-lower | unstable | calls | err | NPV | CP-lower | recall | to DFT |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| f-electron | A | -20 meV | 441 | 27 | 0.9388 | 0.8944 | +10 meV | 2,657 | 35 | 0.9868 | 0.9783 | 0.641 | 0.114 |
| f-electron | B-old | -20 meV | 429 | 24 | 0.9441 | 0.9004 | +10 meV | 2,589 | 35 | 0.9865 | 0.9777 | 0.637 | 0.115 |
| f-electron | B-refit | -20 meV | 429 | 24 | 0.9441 | 0.9004 | +0 meV | 2,740 | 71 | 0.9741 | 0.9631 | 0.637 | 0.071 |
| intermetallic | A | none | 0 | 0 | - | - | +0 meV | 3,251 | 51 | 0.9843 | 0.9762 | 0.000 | 0.100 |
| intermetallic | B-old | none | 0 | 0 | - | - | +0 meV | 3,186 | 51 | 0.9840 | 0.9757 | 0.000 | 0.102 |
| intermetallic | B-refit | -20 meV | 181 | 4 | 0.9779 | 0.9193 | -10 meV | 3,300 | 115 | 0.9652 | 0.9539 | 0.504 | 0.019 |
| pnictide | A | none | 0 | 0 | - | - | +50 meV | 2,502 | 6 | 0.9976 | 0.9927 | 0.000 | 0.312 |
| pnictide | B-old | none | 0 | 0 | - | - | none | 0 | 0 | - | - | 0.000 | 1.000 |
| pnictide | B-refit | -20 meV | 306 | 12 | 0.9608 | 0.9128 | +0 meV | 3,018 | 82 | 0.9728 | 0.9622 | 0.583 | 0.051 |

### 3.1 pnictide's `none / none` was a small-sample artefact

Production's second-engine table gives pnictide **stable none / unstable none**, fitted on n=202. The consequence, measured: a DFT routing fraction of **1.000** against 0.3121 on the single-engine path - every pnictide candidate sent to DFT, 2,502 routings away from DFT lost outright.

The development refit on 3,501 Path-B rows selected **stable = -20 meV, unstable = +0 meV**, with corrected bounds 0.9128 and 0.9622 and margins of +0.0128 and +0.0122, and those selections are **unchanged under the family-level correction**. So the emptiness was a property of a 202-row fit, not of the chemistry.

That is a development finding. It is **not** a validated fix, and the defect is still present in production. A held-out test of exactly these two thresholds has been pre-registered; its sample does not exist yet.

### 3.2 Most of the apparent gain is sample size, not the second engine

Fitting Path A in-sample on the same rows reaches the **same threshold in 5 of 6 selections**, with bounds differing only in the third or fourth decimal. The one exception is f-electron's stable side. The Path-A column in the table above applies thresholds fitted on a *different* population, so against it the refit is flattered: in-sample against out-of-sample.

### 3.3 Supplying a second engine makes the product worse

Weighted across these three families, the share routed to DFT rises from **0.1763** on the single-engine path to **0.4069** when a second engine is supplied - adding information more than doubles DFT routing. The cause is the second-engine rule table, whose entries for these families were fitted on 1,747 / 645 / 202 rows and have never been re-measured.

## 4. The family-level multiplicity correction, and what it removes

The development fits selected 3 families x 2 sides with only the grid correction applied; the refit selected the same 6 again on a subset of the same rows. Neither is family-corrected, so **both sides of the comparison are optimistic**. Under an additional 6-fold Bonferroni:

| family | B-refit primary | under 6-fold correction | survives? |
|---|---|---|---|
| f-electron | -20 meV / +0 meV | none / +0 meV | **NO** |
| intermetallic | -20 meV / -10 meV | -20 meV / -10 meV | yes |
| pnictide | -20 meV / +0 meV | -20 meV / +0 meV | yes |

**f-electron's stable threshold does not survive.** Its bound falls from 0.900359 to **0.892556**, a margin of **-0.0074** against the 0.90 target. The apparent second-engine rescue of f-electron was partly bought by the family-level multiplicity and does not hold; **f-electron remains unresolved on both paths**. intermetallic and pnictide are unchanged.

## 5. Caveats that travel with these results

- **intermetallic's unstable-side margin is +0.0039** (bound 0.9539 against a 0.95 target). That is thin. It also fails to certify a stable threshold on the all-usable footing, so its stable-side gain depends entirely on the labelable population holding.
- **f-electron's unstable NPV margin falls** from +0.0283 to +0.0131 under the refit: the refit trades NPV margin for a lower DFT share.
- Every threshold here was **fitted and scored on the same rows**. That is the most optimistic estimate that exists.
- The disagreement term is doing real but tiny work on f-electron: of 83 rows it removes, 12 were stable calls and 3 of those were errors - a fourfold enrichment over the 6.1% base error rate, on 12 of 441 calls.
- 7 rows of 12,000 had no usable second-engine result and **passed the disagreement check untested**, which is production's real behaviour.

## 6. What remains unresolved

| question | status |
|---|---|
| Is f-electron's stable rule sound? | **Unresolved on both paths.** Neither sample can separate 0.90 from 0.94. A development top-up of roughly 3,320-4,579 structures would settle it; it has not been run. |
| Do pnictide's -20/+0 thresholds hold out of sample? | **Untested.** Pre-registered, sample not drawn. |
| Should production carry one rule table or two? | Development evidence points to **one** - 5 of 6 selections agree - but this is untested out of sample. |
| Is intermetallic's +0.0039 margin real? | **Unresolved**, and too thin to act on. |
| Does any of this generalise off WBM? | **Unknown.** Every result here is one dataset with one hull convention. |

