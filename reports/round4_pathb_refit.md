# Round 4c — fitting both sides on the Path-B development population

Generated 2026-09-19T01:25:06+00:00. Production engine MACE-MPA-0 medium (`c2480e74`), second engine MACE-MP-0 medium (`207ccc81`), disagreement tolerance `0.165255` eV/atom. Exactly the 12,000 round-4 ids. No locked data, no new structures, no bundle written.

> **HYPOTHESIS-GENERATING DEVELOPMENT WORK.** Every threshold fitted here is fitted on development data and scored on the same development data. Nothing here is validated, nothing is production-ready, and no threshold below may be called certified in the sense a pre-registered held-out evaluation certifies one. Path-A and B-old results are preserved unchanged so the new fit can be compared against both.

Methodology is identical to the round-4 Path-A fits: `confidence.certify`, one-sided Clopper-Pearson, Bonferroni-corrected over the 61-point grid, verdict from the pessimistic end. Targets: precision 0.90, NPV 0.95.

## 0. Multiplicity, stated plainly

Round 4 selected 3 families x 2 sides = **6 thresholds** on Path A with only the grid correction applied. This refit selects the same 6 again, on a filtered subset of the same rows. **Neither fit corrects for that family-level multiplicity**, so the comparison is apples-to-apples but both sides of it are optimistic. Cumulatively the two rounds have made 12 threshold selections on overlapping rows. Section 4 repeats every verdict under an additional 6-fold Bonferroni correction.

## 1. Population and filter accounting

| family | drawn | guard-rej (e1/e2) | usable | not labelable | A | B | C | removed by disagreement | disagreement frac of A |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| f-electron | 4,000 | 0/7 | 4,000 | 0.126 | 3,495 | 3,412 | 3,130 | 83 | 0.0237 |
| intermetallic | 4,000 | 0/0 | 4,000 | 0.097 | 3,613 | 3,547 | 3,073 | 66 | 0.0183 |
| pnictide | 4,000 | 0/0 | 4,000 | 0.091 | 3,637 | 3,501 | 3,133 | 136 | 0.0374 |

`not labelable` is the fraction of usable rows the weak-element and structure-change exclusions remove before any threshold applies.

## 2. Full metric set, every family x every path

### f-electron

| path | fitted on n | n scored | stable t | stable calls | errors | precision | CP-lower | margin | unstable t | unstable calls | errors | NPV | CP-lower | margin | recall | to DFT |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| A (single engine, v1 table) | 1,801 | 3,495 | -20 meV | 441 | 27 | 0.9388 | 0.8944 | -0.0056 | +10 meV | 2,657 | 35 | 0.9868 | 0.9783 | +0.0283 | 0.641 | 0.114 |
| B-old (2nd engine, v1 table) | 1,747 | 3,412 | -20 meV | 429 | 24 | 0.9441 | 0.9004 | +0.0004 | +10 meV | 2,589 | 35 | 0.9865 | 0.9777 | +0.0277 | 0.637 | 0.115 |
| B-refit (2nd engine, fitted here) | 3,412 | 3,412 | -20 meV | 429 | 24 | 0.9441 | 0.9004 | +0.0004 | +0 meV | 2,740 | 71 | 0.9741 | 0.9631 | +0.0131 | 0.637 | 0.071 |

### intermetallic

| path | fitted on n | n scored | stable t | stable calls | errors | precision | CP-lower | margin | unstable t | unstable calls | errors | NPV | CP-lower | margin | recall | to DFT |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| A (single engine, v1 table) | 665 | 3,613 | none | 0 | 0 | - | - | - | +0 meV | 3,251 | 51 | 0.9843 | 0.9762 | +0.0262 | 0.000 | 0.100 |
| B-old (2nd engine, v1 table) | 645 | 3,547 | none | 0 | 0 | - | - | - | +0 meV | 3,186 | 51 | 0.9840 | 0.9757 | +0.0257 | 0.000 | 0.102 |
| B-refit (2nd engine, fitted here) | 3,547 | 3,547 | -20 meV | 181 | 4 | 0.9779 | 0.9193 | +0.0193 | -10 meV | 3,300 | 115 | 0.9652 | 0.9539 | +0.0039 | 0.504 | 0.019 |

### pnictide

| path | fitted on n | n scored | stable t | stable calls | errors | precision | CP-lower | margin | unstable t | unstable calls | errors | NPV | CP-lower | margin | recall | to DFT |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| A (single engine, v1 table) | 210 | 3,637 | none | 0 | 0 | - | - | - | +50 meV | 2,502 | 6 | 0.9976 | 0.9927 | +0.0427 | 0.000 | 0.312 |
| B-old (2nd engine, v1 table) | 202 | 3,501 | none | 0 | 0 | - | - | - | none | 0 | 0 | - | - | - | 0.000 | 1.000 |
| B-refit (2nd engine, fitted here) | 3,501 | 3,501 | -20 meV | 306 | 12 | 0.9608 | 0.9128 | +0.0128 | +0 meV | 3,018 | 82 | 0.9728 | 0.9622 | +0.0122 | 0.583 | 0.051 |

`margin` is CP-lower minus the target: positive clears, negative misses. A path with `none` on a side makes no call there, so those candidates go to DFT.

## 3. Three-way comparison

| family | A single engine | B-old (production today) | B-refit (development) |
|---|---|---|---|
| **f-electron** | -20 meV / +10 meV<br>DFT 0.114, recall 0.641 | -20 meV / +10 meV<br>DFT 0.115, recall 0.637 | -20 meV / +0 meV<br>DFT 0.071, recall 0.637 |
| **intermetallic** | none / +0 meV<br>DFT 0.100, recall 0.000 | none / +0 meV<br>DFT 0.102, recall 0.000 | -20 meV / -10 meV<br>DFT 0.019, recall 0.504 |
| **pnictide** | none / +50 meV<br>DFT 0.312, recall 0.000 | none / none<br>DFT 1.000, recall 0.000 | -20 meV / +0 meV<br>DFT 0.051, recall 0.583 |

Aggregate over the three families:

| path | rows scored | weighted DFT share | stable calls | unstable calls |
|---|---:|---:|---:|---:|
| A (single engine, v1 table) | 10,745 | 0.1763 | 441 | 8,410 |
| B-old (2nd engine, v1 table) | 10,460 | 0.4069 | 429 | 5,775 |
| B-refit (2nd engine, fitted here) | 10,460 | 0.0465 | 916 | 9,058 |

## 4. Sensitivity: the same fit under an additional 6-fold correction

Bonferroni over families x sides as well as the grid, i.e. the correction the primary fit (and round 4's Path-A fit) does NOT apply. A threshold that survives here is robust to the family-level multiplicity; one that does not was partly bought by it.

| family | primary stable / unstable | 6-fold-corrected stable / unstable | unchanged? |
|---|---|---|---|
| f-electron | -20 meV / +0 meV | none / +0 meV | **no** |
| intermetallic | -20 meV / -10 meV | -20 meV / -10 meV | yes |
| pnictide | -20 meV / +0 meV | -20 meV / +0 meV | yes |

## 5. For reference: B-refit thresholds under the full product path (C)

The >0.3 eV/atom refusal added on top. Reference only - it changes no verdict above.

| family | n scored | stable calls | precision | CP-lower | unstable calls | NPV | CP-lower | recall | to DFT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| f-electron | 3,130 | 429 | 0.9441 | 0.9004 | 2,458 | 0.9711 | 0.9589 | 0.637 | 0.078 |
| intermetallic | 3,073 | 181 | 0.9779 | 0.9193 | 2,826 | 0.9593 | 0.9463 | 0.504 | 0.021 |
| pnictide | 3,133 | 306 | 0.9608 | 0.9128 | 2,650 | 0.9691 | 0.9570 | 0.583 | 0.056 |

## 6. Like-for-like: round 4's own Path-A FIT vs this Path-B refit

Section 2's Path-A row applies thresholds fitted on a **different** population (the original 4,000-id split), so against it the refit is flattered - in-sample against out-of-sample. Round 4 also fitted Path A in-sample on these same rows. That is the only fair counterpart, and it is the comparison that answers whether the two paths need different rule tables.

| family | side | Path-A fit | its bound | Path-B refit | its bound | same threshold? |
|---|---|---|---:|---|---:|---|
| f-electron | stable | none | - | -20 meV | 0.9004 | **no** |
| f-electron | unstable | +0 meV | 0.9640 | +0 meV | 0.9631 | YES |
| intermetallic | stable | -20 meV | 0.9197 | -20 meV | 0.9193 | YES |
| intermetallic | unstable | -10 meV | 0.9548 | -10 meV | 0.9539 | YES |
| pnictide | stable | -20 meV | 0.9128 | -20 meV | 0.9128 | YES |
| pnictide | unstable | +0 meV | 0.9638 | +0 meV | 0.9622 | YES |

**5 of 6 selections are identical**, with bounds differing only in the third or fourth decimal. The disagreement filter does not change what can be fitted for these families - with one exception, f-electron's stable side, which Path A cannot fit at all and Path B fits by 0.0004 (and loses under the 6-fold correction of section 4).

## 7. What this means for the f-electron top-up

f-electron's Path-B stable side rests on 405/429 = 0.9441.

| correction standard | bound now | margin vs 0.90 | 80% power needs | 90% power needs |
|---|---:|---:|---:|---:|
| grid only (primary, as round 4) | 0.900359 | +0.000359 | ~1,781 structures | ~2,900 structures |
| grid x 6 (family-corrected) | 0.892556 | -0.007444 | ~3,320 structures | ~4,579 structures |

Under the family-corrected standard the Path-B 'rescue' **does not hold**: the bound is 0.8926, missing the target by 0.0074. So f-electron's stable side is unestablished on *both* paths once multiplicity is accounted for, and the two paths no longer disagree about it. The ~3,687-structure figure originally derived from the Path-A diagnosis sits between 80% and 90% power against this stricter standard, so it remains a reasonable size - but it is now answering ONE question for both paths rather than two.

## 8. Determinations

1. **Does B-refit fix the pnictide 100%-to-DFT defect?** Yes, completely: DFT share 1.000 -> 0.051, and pnictide gains a stable side it has never had. It survives the 6-fold correction unchanged. The `none / none` entry was a sample-size artefact of the n=202 fit.

2. **Does it materially improve on Path A, or merely become functional?** Materially, in aggregate - but see section 6 before crediting that to the second engine. The like-for-like comparison shows Path A fitted on the same rows reaches the same thresholds; most of the gain is re-measuring on thousands of rows instead of hundreds, not the disagreement filter.

3. **Does it change the top-up conclusion?** Yes. The Path-B rescue does not survive family correction, so the top-up now answers a single question for both paths rather than adjudicating between them. That makes it more informative, not less.

4. **One shared rule table, or separate Path-A / Path-B tables?** The evidence here points to **one shared table**. Five of six selections agree exactly and the sixth is a knife edge that fails under correction. Maintaining two tables would double the surface that has to be certified in order to encode a difference this small. Stated as a hypothesis, not a decision: it is untested out of sample.

None of the above is validated. Every threshold in this document is fitted and scored on the same development rows, which is the most optimistic estimate available, and no promotion, pre-registration or held-out evaluation follows from it automatically.

