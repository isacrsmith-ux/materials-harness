
# Materials Harness - round 4

Re-measuring the three families the product carried over untouched, scoring the second-engine production path, and pre-registering a held-out test. 19 September 2026. Engine MACE-MPA-0 medium (cpu/float32, tag c2480e74); second engine MACE-MP-0 medium (cpu/float64, tag 207ccc81).

> Everything in this document is DEVELOPMENT evidence. No locked evaluation set was opened. No threshold, taxonomy, exclusion, calibration bundle or frozen specification was changed. Nothing was promoted to production. The one held-out test described here has been pre-registered but NOT run: its sample does not exist yet.

## 1. What prompted this work

The harness answers one question: is a hypothetical material stable enough to be worth a DFT calculation or a lab attempt? It returns <b>likely stable</b>, <b>likely unstable</b> or <b>send to DFT</b>, and each label is meant to be backed by a certified error rate rather than a point estimate.

Rounds 2 and 3 extended certified coverage across the anion families and ended in a pre-registered halide evaluation. Three families were never touched by either round: <b>f-electron</b>, <b>intermetallic</b> and <b>pnictide</b>. They still carried thresholds fitted on 1,801, 665 and 210 labelable rows in September 2026. Reading the active bundle rather than the specification showed why that mattered: in the rule set the product uses when a second engine is available, only f-electron could return <b>likely stable</b> at all. Four of seven families returned <b>send to DFT</b> for every candidate.

A prior handoff recorded that the candidate pool was 'now largely spent'. Recomputing it found that true only for halide and the pooled children. After excluding every id any split had used and dropping every candidate sharing a reduced formula with a locked test id, <b>168,038 candidates remained</b> - including 105,134 f-electron, 37,707 intermetallic and 9,432 pnictide. The three weakest families in the product were the three with the most pool left. That is what made this round possible.

## 2. Round 4: the three carried-over families, re-measured

4,000 calibration structures were drawn per family from the unspent pool, per-bin proportional to each family's own hull-distance distribution, drawn sequentially against a shared taken-set. 42,473 prior ids and 11,874 locked test ids were excluded by id with every locked half's hash verified; 4,977 further candidates were dropped for sharing a reduced formula with a locked test id. All 24,000 jobs completed in 38.7 minutes with zero failures and zero guard rejections.

> No held-out half was reserved. Reserving one is a decision that belongs with a pre-registration, and this draw must not pre-empt it. 140,273 candidates were left unspent and still eligible. Every id drawn is recorded with its sha256 and is no longer eligible as independent held-out data.

| family | drawn | usable | not labelable | labelable | base rate | fitted on (old) | left unspent |
|---|---|---|---|---|---|---|---|
| f-electron | 4,000 | 4,000 | 505 | 3,495 | 0.185 | 1,747 | 101,134 |
| intermetallic | 4,000 | 4,000 | 387 | 3,613 | 0.097 | 645 | 33,707 |
| pnictide | 4,000 | 4,000 | 363 | 3,637 | 0.139 | 202 | 5,432 |

Guard rejections and non-labelable rows are counted and excluded, never dropped silently. Certification is on labelable rows - usable, and surviving the weak-element and structure-change exclusions. That is the population the product labels.

### 2.1 What the re-measurement found

| family | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall | to DFT | verdict |
|---|---|---|---|---|---|---|---|---|---|
| f-electron | none | nan | nan | +0 meV | 0.9747 | 0.9640 | 0.000 | 0.196 | sample-size limited |
| intermetallic | -20 meV | 0.9780 | 0.9197 | -10 meV | 0.9658 | 0.9548 | 0.506 | 0.018 | certified |
| pnictide | -20 meV | 0.9608 | 0.9128 | +0 meV | 0.9740 | 0.9638 | 0.583 | 0.049 | certified |

Bounds are one-sided Clopper-Pearson at 0.95, Bonferroni-corrected over the 61-point threshold grid so that picking the best threshold keeps the guarantee. The verdict is read from the bound, never from the point estimate.

<b>pnictide gained both sides.</b> From 210 rows and no stable rule to both sides fitted on 3,637 rows. DFT routing falls from 0.312 to 0.049 and recall of truly stable materials rises from 0 to 0.583.

<b>intermetallic gained a stable side</b> on 3,613 rows against the 665 its threshold came from. DFT routing falls from 0.100 to 0.018, recall from 0 to 0.506.

<b>f-electron lost its stable side.</b> No threshold certifies at n=3,495. This is the finding the round was least expecting and it is preserved as a finding.

### 2.2 The f-electron non-replication

f-electron is the only family that can currently return <b>likely stable</b> in production. Its live -20 meV rule was applied unchanged to both populations:

| sample | labelable | called stable | correct | point | CP-lower | clears 0.90? |
|---|---|---|---|---|---|---|
| original (the rule's own fitting population) | 1,801 | 206 | 199 | 0.9660 | 0.9063 | yes |
| round 4 (fresh, disjoint, matched) | 3,495 | 441 | 414 | 0.9388 | 0.8944 | no |

Difference +0.0272 (SE 0.0188, z 1.45, two-sided p 0.148): the two samples are <b>not statistically distinguishable</b>, and they are not pooled. Pooling a fitting population with a fresh one produces a number that is neither, and would convert a failed replication into a tuned threshold.

Read precisely, this is not evidence that the f-electron rule is invalid. It is evidence that the rule's certification was <b>marginal</b> - a bound of 0.9063 on 206 calls - and does not replicate as a certification on a matched sample twice the size. Structurally this is the same shape as the unresolved fluoride result: point estimate above target, corrected bound below, neither sample able to separate 0.90 from 0.94. The difference is that this rule is live.

### 2.3 The comparability check that had to be shown, not assumed

The v1 thresholds were fitted on a split stratified by hull bin across all families at once; the round-4 draw is stratified per-bin proportional to each family's own share of the remaining pool. A precision difference between them could therefore be composition rather than validity. Both compositions were computed:

| family | original base rate | round-4 base rate | largest bin-share gap |
|---|---|---|---|
| f-electron | 0.1866 | 0.1848 | 0.006 |
| intermetallic | 0.0842 | 0.0974 | 0.023 |
| pnictide | 0.1286 | 0.1386 | 0.018 |

The populations match closely, so the differences in 2.1 and 2.2 are not composition artefacts. The check was necessary regardless of how it came out.


## 3. Round 4b: the second-engine production path

Round 4 ran one engine, so it could only speak to the bundle's <b>without_second_engine</b> rule set. The product takes the <b>with_second_engine</b> path whenever a second engine is supplied, and that path adds a term round 4 could not evaluate: a candidate is refused a label when the two engines' predicted hull distances differ by more than the tolerance.

The same 12,000 structures were run on the second engine - no new draw, no new ids, no locked data. All 24,000 jobs completed, none failed. Because job keys carry the engine tag, the two engines' results cannot collide.

| family | engine-2 usable | no 2nd result | disagreeing pairs | disagree rate | median gap | p90 gap |
|---|---|---|---|---|---|---|
| f-electron | 3,993 | 7 | 214 | 0.0535 | 0.0289 | 0.1157 |
| intermetallic | 4,000 | 0 | 82 | 0.0205 | 0.0276 | 0.0930 |
| pnictide | 4,000 | 0 | 160 | 0.0400 | 0.0353 | 0.1200 |

Disagreement tolerance 0.165255 eV/atom, from the frozen bundle. A row with no second-engine result passes the disagreement term untested, because abs(NaN) > tol is False. That is the product's real behaviour - it warns that the thresholds assume the check ran, then labels the candidate anyway - so the count is reported rather than folded in. It is 7 rows of 12,000.

### 3.1 Supplying a second engine makes the product worse

| path | rows scored | weighted DFT share | stable calls | unstable calls |
|---|---|---|---|---|
| A single engine | 10,745 | 0.1763 | 441 | 8,410 |
| B-old, production today | 10,460 | 0.4069 | 429 | 5,775 |
| B-refit (section 4) | 10,460 | 0.0465 | 916 | 9,058 |

Adding a second engine's information <b>more than doubles</b> the share sent to DFT, from 0.1763 to 0.4069. That is perverse, and it is not the engines' fault: it is the with_second_engine rule table, whose entries for these families were fitted on 1,747, 645 and 202 rows and have never been re-measured.

### 3.2 pnictide has no rule at all on that path

The with_second_engine table gives pnictide <b>stable none / unstable none</b>, fitted on n=202. So every pnictide candidate is sent to DFT: a DFT share of <b>1.000</b> against 0.3121 on the single-engine path, and 2,502 routings away from DFT lost outright. This is the dominant term in 3.1, and it upgrades what an earlier audit had recorded as a documentation gap into a measured production defect.

### 3.3 The second engine rescues f-electron by 0.0004

| path | calls | correct | point | CP-lower | clears 0.90? | if one more were wrong |
|---|---|---|---|---|---|---|
| A single engine | 441 | 414 | 0.9388 | 0.8944 | no | 0.891612 |
| B + disagreement | 429 | 405 | 0.9441 | 0.9004 | yes | 0.897412 |

The disagreement term removes 83 rows, 12 of which the stable rule had called stable and 3 of those wrongly - a fourfold enrichment over the 6.1% base error rate of stable calls. The filter is doing real work. But it does it on 12 of 441 calls, and the resulting bound clears the target by 0.000359. One further error takes it to 0.8974. That is a knife edge, not a margin, and it is not described here as a certification that holds.


## 4. Round 4c: fitting the second-engine path, and what it settled

Round 4b established that the with_second_engine path is broken for pnictide but not whether it is <b>fixable</b> on its own footing. Only a fit on the Path-B population answers that, and the answer decides whether a future promotion would carry one shared rule table or two. Both sides were therefore fitted on the Path-B population for all three families, with the same methodology as the round-4 Path-A fits.

### 4.1 f-electron

| path | fitted n | scored | stable t | calls | err | precision | CP-low | margin | unstable t | calls | err | NPV | CP-low | margin | recall | DFT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 1,801 | 3,495 | -20 meV | 441 | 27 | 0.9388 | 0.8944 | -0.0056 | +10 meV | 2,657 | 35 | 0.9868 | 0.9783 | +0.0283 | 0.641 | 0.114 |
| B-old | 1,747 | 3,412 | -20 meV | 429 | 24 | 0.9441 | 0.9004 | +0.0004 | +10 meV | 2,589 | 35 | 0.9865 | 0.9777 | +0.0277 | 0.637 | 0.115 |
| B-refit | 3,412 | 3,412 | -20 meV | 429 | 24 | 0.9441 | 0.9004 | +0.0004 | +0 meV | 2,740 | 71 | 0.9741 | 0.9631 | +0.0131 | 0.637 | 0.071 |

### 4.2 intermetallic

| path | fitted n | scored | stable t | calls | err | precision | CP-low | margin | unstable t | calls | err | NPV | CP-low | margin | recall | DFT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 665 | 3,613 | none | 0 | 0 | nan | nan | +nan | +0 meV | 3,251 | 51 | 0.9843 | 0.9762 | +0.0262 | 0.000 | 0.100 |
| B-old | 645 | 3,547 | none | 0 | 0 | nan | nan | +nan | +0 meV | 3,186 | 51 | 0.9840 | 0.9757 | +0.0257 | 0.000 | 0.102 |
| B-refit | 3,547 | 3,547 | -20 meV | 181 | 4 | 0.9779 | 0.9193 | +0.0193 | -10 meV | 3,300 | 115 | 0.9652 | 0.9539 | +0.0039 | 0.504 | 0.019 |

### 4.3 pnictide

| path | fitted n | scored | stable t | calls | err | precision | CP-low | margin | unstable t | calls | err | NPV | CP-low | margin | recall | DFT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 210 | 3,637 | none | 0 | 0 | nan | nan | +nan | +50 meV | 2,502 | 6 | 0.9976 | 0.9927 | +0.0427 | 0.000 | 0.312 |
| B-old | 202 | 3,501 | none | 0 | 0 | nan | nan | +nan | none | 0 | 0 | nan | nan | +nan | 0.000 | 1.000 |
| B-refit | 3,501 | 3,501 | -20 meV | 306 | 12 | 0.9608 | 0.9128 | +0.0128 | +0 meV | 3,018 | 82 | 0.9728 | 0.9622 | +0.0122 | 0.583 | 0.051 |

### 4.4 The comparison that actually decides the rule-table question

The Path-A row above applies thresholds fitted on a <b>different</b> population, so against it the refit is flattered: in-sample against out-of-sample. Round 4 also fitted Path A in-sample on these same rows. That is the only fair counterpart.

| family | side | Path-A fit | its bound | Path-B refit | its bound | same? |
|---|---|---|---|---|---|---|
| f-electron | stable | none | - | -20 meV | 0.9004 | no |
| f-electron | unstable | +0 meV | 0.9640 | +0 meV | 0.9631 | YES |
| intermetallic | stable | -20 meV | 0.9197 | -20 meV | 0.9193 | YES |
| intermetallic | unstable | -10 meV | 0.9548 | -10 meV | 0.9539 | YES |
| pnictide | stable | -20 meV | 0.9128 | -20 meV | 0.9128 | YES |
| pnictide | unstable | +0 meV | 0.9638 | +0 meV | 0.9622 | YES |

<b>Five of six selections are identical</b>, with bounds differing only in the third or fourth decimal. The disagreement filter does not change what can be fitted for these families. Most of the apparent gain in 3.1 is measuring on thousands of rows instead of hundreds - not the second engine. The one exception is f-electron's stable side, which Path A cannot fit at all and Path B fits by 0.0004.

### 4.5 Multiplicity, reported rather than hidden

Round 4 selected 3 families x 2 sides = 6 thresholds on Path A with only the grid correction applied. The refit selects the same 6 again on a filtered subset of the same rows - 12 selections on overlapping rows, neither fit family-corrected. So the comparison is apples-to-apples but <b>both sides of it are optimistic</b>. Under an additional 6-fold Bonferroni:

| family | primary stable / unstable | 6-fold-corrected | unchanged? |
|---|---|---|---|
| f-electron | -20 meV / +0 meV | none / +0 meV | NO |
| intermetallic | -20 meV / -10 meV | -20 meV / -10 meV | yes |
| pnictide | -20 meV / +0 meV | -20 meV / +0 meV | yes |

> f-electron's stable threshold DISAPPEARS under the family correction: its bound falls from 0.900359 to 0.892556, a margin of -0.0074. The rescue reported in round 4b was partly bought by multiplicity and does not hold. intermetallic and pnictide are unchanged. The one place the correction mattered is the one place a positive result had been reported.


## 5. The pnictide pre-registration

pnictide is the cleanest case the project has produced: both sides fitted on 3,501-3,637 rows with margins of +0.0128 and +0.0122, reaching identical thresholds on both paths and under both correction standards, replacing an entry fitted on 202 rows that currently sends every pnictide candidate to DFT when a second engine is supplied. A protocol has therefore been frozen to test it on unseen data.

> The sample DOES NOT EXIST. The protocol was written and committed before any id was selected, which is the only order in which a pre-registration means anything. Drawing it is a separate decision.

| what is frozen | value |
|---|---|
| thresholds under test | stable -20 meV, unstable +0 meV, FIXED |
| family definition | confidence.family() unchanged; nitrides included |
| population | labelable; all-usable cannot change a verdict |
| hypotheses | PA1/PA2 (Path A) and PB1/PB2 (Path B), four primaries |
| targets | stable precision 0.90; unstable NPV 0.95 |
| primary confidence | 0.9875 = 1 - 0.05/4 (Bonferroni over 4) |
| grid correction | NONE - thresholds are fixed, nothing is selected on held-out data |
| family multiplicity | NONE - only pnictide is tested |
| sample size | n = 3,500 of 5,432 eligible |
| promotion rule | all four must PASS, or nothing is promoted |

### 5.1 Why 3,500 and not a convenient number

The binding hypothesis is the stable side, which converts only 0.0765 of drawn structures into calls. Required structures, powered against the development point estimate, at the primary confidence:

| hypothesis | target | assumed truth | calls/structure | 80% power | 90% power | 95% power |
|---|---|---|---|---|---|---|
| A stable | 0.9 | 0.9608 | 0.07650 | 2,353 | 2,876 | 3,530 |
| A unstable | 0.95 | 0.9740 | 0.78850 | 825 | 1,040 | 1,218 |
| B stable | 0.9 | 0.9608 | 0.07650 | 2,353 | 2,876 | 3,530 |
| B unstable | 0.95 | 0.9728 | 0.75450 | 922 | 1,180 | 1,432 |

| hypothesis | expected calls | expected errors | max errors allowed | power at n=3,500 |
|---|---|---|---|---|
| A stable | 268 | 10.5 | 15 | 0.935 |
| A unstable | 2,760 | 71.8 | 112 | 1.000 |
| B stable | 268 | 10.5 | 15 | 0.935 |
| B unstable | 2,641 | 71.8 | 107 | 1.000 |

3,500 gives about 0.94 power on the binding hypothesis and about 1.00 on the other three, and leaves 1,932 candidates unspent for a replacement study. A 1,500-structure draw - the convention the earlier rounds used - would have given power <b>0.53</b> on the binding hypothesis and was rejected for that reason.

> Stated in advance, not discovered afterwards: the study is powered against the development POINT estimate. If pnictide's true stable precision were 0.9128 - the development lower bound - establishing a deficit against a 0.90 target would need roughly 65,000 structures, which the pool cannot supply. A PASS therefore means the thresholds behave as development suggested. It does NOT establish that true precision is comfortably above 0.90, and the protocol forbids claiming that it does. This is the same limit the fluoride follow-up found.

### 5.2 The dependence question, resolved before any result exists

Path B is a strict <b>subset</b> of Path A: B is A minus the rows whose two engines disagree beyond the tolerance. The two tests are nested and strongly positively dependent, not independent - on development data B kept 96.3% of A's rows, and the stable side produced identical call and error counts on both paths. Testing both on the same structures therefore raises a real question about the multiplicity procedure, and it is answered in the protocol rather than after seeing results:

<b>1.</b> Bonferroni rests on Boole's inequality and assumes nothing about independence, so the nesting cannot invalidate it - dependence costs power, not validity. <b>2.</b> The promotion rule is conjunctive, which makes this an intersection-union test, where testing each hypothesis at an uncorrected alpha would already control the error of the conjunctive claim; a Bonferroni correction on top is therefore strictly conservative. <b>3.</b> The conservative option is pre-registered as primary anyway. <b>4.</b> A hypothesis passing at 0.95 but failing at 0.9875 is a <b>FAIL</b>, and no 'effective' correction will be estimated from the observed overlap, before or after seeing the data.

The protocol also fixes what happens in every branch: if A passes and B fails, or B passes and A fails, <b>nothing is promoted</b> in either case, because each outcome implies a subgroup claim that this data cannot support. An inconclusive hypothesis blocks promotion exactly as a failure does, and there is no 'ambiguous' verdict available for a primary hypothesis - a category that left the earlier fluoride result unresolved.


## 6. Integrity, reproducibility and what was deliberately not done

### 6.1 Locked-set state

Six held-out halves existed before this work and all six are untouched by it. The two that had been opened - the original WBM test in September 2026 and the halide half on 18 September - were not re-opened. The four unspent halves were confirmed to have zero results in the store, including the two that the ledger script does not cover. Round 4 created no new locked half, and its accessor raises rather than returning ids.

| locked half | n | state after this work |
|---|---|---|
| original WBM test | 4,000 | opened once, 2026-09-12; not re-opened |
| oxide (round 1) | 2,000 | UNOPENED, 0 results in store |
| halide (round 1) | 2,000 | opened once, 2026-09-18; not re-opened |
| sulfide (round 2) | 874 | SEALED, 0 results in store |
| chalcogenide residual (round 3) | 1,500 | UNOPENED, 0 results in store |
| other residual (round 3) | 1,500 | UNOPENED, 0 results in store |
| pnictide evaluation (round 4) | 3,500 | PRE-REGISTERED ONLY - does not exist |

### 6.2 A defect found by trying to reproduce the work

Re-running the round-4 analysis against the tree reproduced its report identically apart from the generated timestamp. That check found one real defect: the failure-accounting query read the job queue without filtering on engine tag, so once the second engine was queued over the same ids its in-flight jobs were counted as round-4 jobs that had not run. The column reported 7,468 / 8,000 / 8,000 instead of 0 / 0 / 0. It was fixed and the report re-verified. Accounting only - no measured quantity was affected - but it is recorded because the reproduction check is what caught it, not a test.

### 6.3 Deliberately not done

| not done | why |
|---|---|
| the f-electron top-up | still worth running at 3,320-4,579 structures, but it resolves a family whose stable side is unestablished on either path; pnictide has a measured defect with a measured fix and comes first |
| any promotion | every threshold here is fitted and scored on the same development rows - the most optimistic estimate available |
| an f-electron subfamily search | lanthanide against actinide would invite exactly the multiplicity that eleven oxide splits already demonstrated; it needs its own correction and its own pre-registration |
| intermetallic pre-registration | its unstable NPV margin is +0.0039, too thin to carry alongside pnictide without more thought |
| regenerating the round-2 report | the corrected locked-set ledger would flow into a historical deliverable and retroactively rewrite a table written 'as of' an earlier date; the staleness is recorded instead |

### 6.4 Provenance

| artefact | sha256 (first 32) |
|---|---|
| data/wbm_split_round4.json | 91d8f05bec7754e2104773245c74563d |
| reports/round4_carried_over.json | a3d38a8cb5710ca82e955e6848760515 |
| reports/round4_second_engine.json | 9e9f7950e86bc804f38bcf62b4aecacc |
| reports/round4_pathb_refit.json | adb6293f731984b846bcbaf17795a367 |
| data/pnictide_evaluation_preregistration.json | effe583b501cd0b7021481eeaf77ffec |
| data/calibration_bundle.json | 41395f1adb3377180e57915b1f8c97e4 |
| data/calibration_spec_v2.json | e021845162ead995d9c84e735b0eadaf |

The calibration bundle and frozen specification v2 appear here to show they are unchanged: the bundle still carries created_at 2026-09-12T20:21:45+00:00, confidence.FAMILIES still contains no fluoride, and the specification's sha256 still matches the value recorded in the halide opening log.

## 7. Where this leaves the product

Unchanged, and deliberately. The active bundle is byte-for-byte what it was; the taxonomy has not moved; specification v2 remains frozen and unpromoted; the fluoride carve-out remains unresolved. What has changed is what is known about the product's weakest corner.

Two families that could label nothing stable can be fitted to label a great deal - pnictide from 0 to 0.583 recall, intermetallic from 0 to 0.506 - and the ceiling that made f-electron the only labelling family was a sample-size artefact, not chemistry. Against that, the one family that did label has lost its certification on fresh data, and the path the product takes when a second engine is supplied is measurably worse than the path without one. None of these is validated. One of them is now pre-registered to be.

