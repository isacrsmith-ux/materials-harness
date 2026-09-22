# Pre-registration — the f-electron held-out evaluation

Written 2026-09-22T01:17:50+00:00 at commit `5231b94`.

> **PRE-REGISTERED. No f-electron held-out half exists. Nothing has been drawn, queued, scored or opened. Drawing the sample is a separate, separately-approved step.**

## What is being tested

the LIVE f-electron production rule, unchanged: stable = -20 meV/atom and unstable = +10 meV/atom, on BOTH production paths. This is a confirmation test of a rule already in production, not a proposal to change one.

### Why

f-electron is the only family that could return 'likely stable' in production before the pnictide promotion, and its stable side has never been tested out of sample. Round 4 found no certifiable threshold at n=3,495 and the live rule's corrected bound was 0.8944; round 4b appeared to rescue it on the second-engine path; round 4c showed that rescue did not survive the family-level correction (0.892556). A frozen development top-up to n=8,800 then certified -20 meV on BOTH paths under the FULL family correction, bounds 0.9171 and 0.9231, with the two development cohorts statistically indistinguishable (p 0.232 / 0.219). That resolved the development question and left exactly one open: does it hold out of sample?

**Status of the evidence so far.** DEVELOPMENT ONLY. Every f-electron figure to date is fitted and scored on the same rows. No f-electron claim has ever been tested on held-out data. This evaluation would be the first.

## Thresholds under test (FIXED)

| side | threshold |
|---|---|
| stable | **-20 meV/atom** |
| unstable | **+10 meV/atom** |

FIXED. Not recomputed, re-derived or refitted at any point. Note the development work selected +0 meV for the unstable side while production carries +10 meV; this evaluation tests the LIVE +10 meV value, because the question is whether the product's rule holds, not whether a different rule would.

Active bundle sha256 `419c11514d6a54854584258375eadab6b2be0c449e955125799fc51df2310288`.

## Family definition and precedence

`f-electron -> intermetallic -> oxide -> halide -> chalcogenide -> pnictide -> other`

a formula containing any element in compare.F_ELECTRON. Because f-electron heads the precedence chain, an f-electron oxide, halide or intermetallic is an f-electron here. No taxonomy change is proposed, tested or implied.

## Population

- **labelable** — usable AND surviving the weak-element and structure-change exclusions - the population calibration.fit() takes and production labels. LABELABLE IS AUTHORITATIVE; all-usable is a secondary diagnostic that can never change a verdict.
- weak elements: Be, Pm, Pu, Tc
- max trustworthy hull: None for both primary paths, matching the footing the rule was fitted on. The product's >0.3 eV/atom refusal is reported as a descriptive path C only.

## Hypotheses

| id | path | side | threshold | metric | target | pass criterion |
|---|---|---|---|---|---:|---|
| **EA1** | A | stable | -20 meV/atom | precision of the 'likely stable' call | 0.9 | CP-lower @ 0.9875 >= 0.9 |
| **EA2** | A | unstable | +10 meV/atom | NPV of the 'likely unstable' call | 0.95 | CP-lower @ 0.9875 >= 0.95 |
| **EB1** | B | stable | -20 meV/atom | precision of the 'likely stable' call | 0.9 | CP-lower @ 0.9875 >= 0.9 |
| **EB2** | B | unstable | +10 meV/atom | NPV of the 'likely unstable' call | 0.95 | CP-lower @ 0.9875 >= 0.95 |

## Statistics and every correction

- **primary confidence 0.9875** — Bonferroni over the 4 pre-registered hypotheses: 1 - 0.05/4
- secondary 0.95 — uncorrected; reported alongside; CANNOT change a verdict
- **no grid correction** — The thresholds are FIXED by this document before the sample exists, so nothing is selected on held-out data and there is no grid multiplicity. The 61-fold grid Bonferroni the development fits paid does not apply and must not be added.
- **no family correction** — Only f-electron is tested. The 6-fold family x side correction the development analysis applied was needed because round 4 SELECTED thresholds across families; this evaluation selects nothing.

**The development analysis used level 0.999863 and this evaluation uses 0.9875, which is LESS strict. That is correct, not a weakening: the development level paid for searching a 61-point grid across 6 family x side selections. Here the threshold is given in advance, so the only multiplicity is the four hypotheses. A held-out bound being higher than a development bound at similar n is an expected consequence and must not be reported as the held-out data being 'better'.**

## Dependence audit

**Structural fact.** Path B is a strict SUBSET of Path A: B is A minus rows whose two engines disagree beyond tolerance. The tests are nested and strongly positively dependent, not independent.

**Observed.** On the 8,800-structure development population B retained 7,504 of A's 7,719 rows (97.2%); the stable side made 963 and 942 calls with 50 and 44 errors.

**Resolution, fixed here and not revisited:**

1. Bonferroni is VALID under arbitrary dependence - it rests on Boole's inequality and assumes nothing about independence. Nesting costs power, not validity.
2. The promotion rule is CONJUNCTIVE (all four must pass), making this an intersection-union test, for which an uncorrected alpha would already control the conjunctive claim. The Bonferroni correction on top is STRICTLY CONSERVATIVE.
3. The conservative option is pre-registered as primary regardless.
4. PRE-COMMITMENT: a hypothesis passing at 0.95 but failing at 0.9875 is a FAIL, reported as a near-miss with both bounds shown. No 'effective' correction will be estimated from the observed overlap, before or after seeing the data.

## Verdicts

- **PASS** — the primary-confidence lower bound is >= the target
- **FAIL** — the primary-confidence lower bound is < the target, INCLUDING when the point estimate is above target. There is no 'ambiguous' verdict for a primary hypothesis.
- **INCONCLUSIVE** — the hypothesis could not be tested, for a pre-specified reason below. It is NOT a pass and NOT a fail, and it blocks any conclusion exactly as a fail does.

### Inconclusive triggers

- `too_few_calls` — fewer than 20 calls on that side
- `unusable_rows` — more than 2% of drawn ids produce no usable production-engine result. Not rescued by retrying into a different rung.
- `missing_second_engine` — Path B only: more than 2% of Path-A labelable rows lack a usable second-engine result
- `no_labelable_rows` — a path has zero labelable rows

## Outcome rule — decided before any data exists

**All four pass.** the live f-electron rule is CONFIRMED out of sample on both paths. Note what this does and does not license: it confirms a rule ALREADY IN PRODUCTION, so the correct action is to record the confirmation and the provenance in the bundle. It is NOT a licence to change any threshold, and no threshold would change.

**Any fail.** the live f-electron rule has FAILED out of sample. This is the consequential branch and it is decided here, before any data exists: a failure does NOT automatically remove or loosen the rule. It is reported as a failure, the rule's status in the bundle is marked as held-out-failed, and any change to production requires its own separate decision with its own analysis of what the alternative would cost. Removing f-electron's stable side would leave the product with pnictide as its only stable-labelling family, which is a product decision, not a statistical one.

**Any inconclusive.** no conclusion. Reported with counts. A replacement evaluation needs a fresh pre-registration and fresh ids; roughly 91,834 f-electron candidates would remain.

> This evaluation can confirm a live rule or impugn it, and those two outcomes have very different consequences for the product. That asymmetry is recorded now so that a failure cannot later be softened by arguing the test was too strict.

## Sample size — derived, not assumed

| hypothesis | target | assumed truth | calls/structure | 80% | 90% | 95% |
|---|---:|---:|---:|---:|---:|---:|
| EA1 A stable | 0.9 | 0.9481 | 0.10943 | 2,696 | 3,482 | 4,250 |
| EA2 A unstable | 0.95 | 0.9888 | 0.67068 | 332 | 376 | 419 |
| EB1 B stable | 0.9 | 0.9533 | 0.10705 | 2,168 | 2,878 | 3,336 |
| EB2 B unstable | 0.95 | 0.9886 | 0.64909 | 343 | 389 | 433 |

### Chosen: **n = 4,500** of 96,334 eligible

4500 is chosen, not assumed. The binding hypothesis is EA1, Path-A stable precision, which converts only 0.10943 of drawn structures into calls; the unstable hypotheses need under 450 structures and are effectively free. At the primary confidence EA1 needs 3,482 structures for 90% power and 4,250 for 95%. At 4500 every hypothesis has power >= 0.96 and 91,834 candidates remain unspent.

| hypothesis | expected calls | expected errors | max errors allowed | power |
|---|---:|---:|---:|---:|
| EA1 | 492 | 25.5 | 34 | 0.961 |
| EA2 | 3,018 | 33.7 | 124 | 1.000 |
| EB1 | 482 | 22.5 | 33 | 0.988 |
| EB2 | 2,921 | 33.2 | 119 | 1.000 |

### Sensitivity at the development lower bounds

| hypothesis | assumed truth | structures for 80% power | within pool? |
|---|---:|---:|---|
| EA1 | 0.9171 | 25,158 | yes |
| EA2 | 0.9829 | 461 | yes |
| EB1 | 0.9231 | 14,013 | yes |
| EB2 | 0.9826 | 477 | yes |

**Powered against the DEVELOPMENT POINT estimates (0.9481 / 0.9533 stable, 0.9888 / 0.9886 NPV). Unlike the fluoride and intermetallic cases, the pessimistic branch here is NOT hopeless: even at the development lower bounds the effect sizes stay comfortably above target, so the sensitivity analysis is feasible within the pool on all four hypotheses. That is a genuine difference from those studies and is the reason this one is worth running. A pass still means the rule behaves as development suggested; it does not establish that true precision is far above 0.90.**

## The sample

- n = 4,500 of 96,334 eligible, leaving 91,834 unspent
- There is NO f-electron locked half. Round 4 deliberately reserved none. This evaluation requires a FRESH draw, and consumes none of the four unspent locked halves (oxide, sulfide, chalcogenide, other).
- eligibility: a candidate is eligible ONLY if it has never participated in anything: not the original WBM split, not the round-1/2/3 splits, not the round-4 development draw, not the f-electron development top-up, and not the pnictide held-out sample. Enforced by id and by reduced formula against every locked half and every opened held-out set.
- stratification: per-bin proportional over <0, 0-0.025, 0.025-0.1, 0.1-0.3, >0.3 eV/atom
- engines: both. Production mace-mpa-0-medium (cpu/float32, tag c2480e74) and second mace-mp-0-medium (cpu/float64, tag 207ccc81) over the SAME drawn ids, because Path B cannot be scored without both. One runner per engine: a runner executes one settings tag, and violating that has already caused two incidents.

## Stop rules

- The sample is drawn ONCE and opened ONCE. data/felectron_eval_log.json records the opening; the open command refuses while it exists.
- No interim looks and no sequential testing. Every job completes, then the four hypotheses are scored in a single pass.
- If any hypothesis FAILS or is INCONCLUSIVE, stop: no other locked half is opened, no further f-electron sample is drawn, and no threshold is adjusted in either direction.
- intermetallic remains on hold. pnictide is closed and its held-out set is never reopened or reused. This evaluation says nothing about either.

## Forbidden once the sample is drawn

- REFITTING ANY THRESHOLD. The -20/+10 meV values are fixed. Running certify, diagnose, best_bound or any grid search on the held-out rows is forbidden for any purpose.
- changing the family definition, precedence, labelable definition, weak elements, structure-change exclusion, disagreement tolerance, targets, confidence or corrections
- adding, dropping or reweighting hypotheses
- pooling these rows into any calibration or development set, now or later
- re-opening the sample, or drawing a second sample to append to it
- reporting the secondary 0.95 bound as the verdict
- changing the live f-electron rule in EITHER direction as an automatic consequence

## Chain of custody

1. This document is committed BEFORE the sample is drawn; its sha256 is recorded in the draw and verified again at open time and at scoring time.
2. The draw writes data/wbm_split_felectron_eval.json with the id list and its sha256, and asserts disjointness from every prior split, draw and held-out set by id and by reduced formula. Committed before any job is queued.
3. Ids are reachable only through an accessor that raises PermissionError without unlock=True and verifies the recorded hash.
4. Opening writes data/felectron_eval_log.json recording opened_at, harness commit, the sample sha256, this document's sha256, the active bundle's sha256, and both engines' keys, settings tags and checkpoint sha256 values.
5. The set is registered in data/locked_sets_registry.json, its state read from the opening log rather than asserted.
6. Any hash mismatch aborts the evaluation.

## Provenance of the design inputs

8800 ids: round-4 f-electron draw (4,000) + frozen top-up (4,800). the development observations are design inputs ONLY. They are not pooled with the held-out sample, and no held-out threshold is derived from them.

