# Pre-registration — a fresh pnictide held-out evaluation

Written 2026-09-19T01:36:53+00:00 at commit `742ed60`.

> **PRE-REGISTERED. The evaluation sample DOES NOT EXIST YET. Nothing has been drawn, queued, scored or opened. Drawing it is a separate, separately-approved step.**

## What is being tested

the shared-rule hypothesis for pnictide: that the FIXED thresholds stable = -20 meV/atom and unstable = +0 meV/atom satisfy the certification targets on genuinely unseen pnictide structures, under BOTH production paths (single engine and second-engine/disagreement), so that one shared rule table would serve both.

### Why

The active bundle's with_second_engine entry for pnictide is stable=None/unstable=None, fitted on 202 rows in 2026-09-12. Round 4b measured the consequence: when a second engine is supplied, 100% of pnictide candidates are routed to DFT (DFT share 1.000 against 0.3121 single-engine). Round 4 and round 4c fitted -20/+0 meV on 3,637 (Path A) and 3,501 (Path B) development rows and reached the SAME thresholds on both paths, with bounds 0.9128/0.9638 and 0.9128/0.9622. That is development evidence, fitted and scored on the same rows, and it is not validated. This evaluation is what would validate it.

## The thresholds under test (FIXED)

| | |
|---|---|
| stable | **-20 meV/atom** |
| unstable | **+0 meV/atom** |

The bundle's with_second_engine pnictide entry is none/none, so the bundle cannot be the authority for what is being tested. THIS DOCUMENT is the authority. The values above are fixed and are not recomputed, re-derived or refitted at any point.

For reference, the active bundle today: `without_second_engine` stable none / unstable +50 meV (n=210); `with_second_engine` **stable none / unstable none** (n=202).

## Family definition and precedence

`harness.confidence.family(), UNCHANGED - no round-2/3/4 overlay`, first match wins:

`f-electron -> intermetallic -> oxide -> halide -> chalcogenide -> pnictide -> other`

a formula reaching 'pnictide' in that chain: it contains an N/P/As/Sb/Bi pnictogen AND is NOT f-electron, NOT wholly metallic (intermetallic), NOT oxygen-bearing, NOT halogen-bearing and NOT chalcogen-bearing. Nitrides are included - nitride was REJECTED as a carve-out in round 2 and N stays in pnictide. No taxonomy change is proposed, tested or implied by this evaluation.

## Population

- **usable** — not rejected by the energy-plausibility guard; rejections counted and excluded
- **labelable** — usable AND surviving the weak-element and structure-change exclusions - the population calibration.fit() takes and the population production labels. LABELABLE IS AUTHORITATIVE (user ruling 2026-09-18). All-usable figures may be reported as a secondary diagnostic and can never change a verdict.
- weak elements: Be, Pm, Pu, Tc
- max trustworthy hull: None for both primary paths, matching the footing the thresholds were fitted on. The product's >0.3 eV/atom refusal (predict.MAX_TRUSTWORTHY_HULL_EV) is reported as a SECONDARY descriptive path C and cannot change any verdict.

## The two primary paths

| path | rule set | filter | disagreement |
|---|---|---|---|
| **A** | `without_second_engine` | weak elements + structure change | not applied |
| **B** | `with_second_engine` | A + engine disagreement | tol `0.165255` eV/atom |

A row with no usable second-engine result passes the disagreement term untested, because abs(NaN) > tol is False. This is production's actual behaviour and is PRE-REGISTERED as such. The count of such rows is reported. If they exceed 2% of Path-A labelable rows, Path B's hypotheses are INCONCLUSIVE.

Path C (the product's >0.3 eV/atom refusal) is reported as a descriptive secondary and can never change a verdict.

## Hypotheses

| id | path | side | threshold | metric | target | pass criterion |
|---|---|---|---|---|---:|---|
| **PA1** | A | stable | -20 meV/atom | precision of the 'likely stable' call | 0.9 | CP-lower @ 0.9875 >= 0.9 |
| **PA2** | A | unstable | +0 meV/atom | NPV of the 'likely unstable' call | 0.95 | CP-lower @ 0.9875 >= 0.95 |
| **PB1** | B | stable | -20 meV/atom | precision of the 'likely stable' call | 0.9 | CP-lower @ 0.9875 >= 0.9 |
| **PB2** | B | unstable | +0 meV/atom | NPV of the 'likely unstable' call | 0.95 | CP-lower @ 0.9875 >= 0.95 |

## Statistics and every correction applied

- bound: one-sided Clopper-Pearson lower bound. Never a bootstrap. The verdict is read from the bound, never from the point estimate.
- **primary confidence 0.9875** — Bonferroni over the 4 pre-registered hypotheses: 1 - 0.05/4
- secondary confidence 0.95 — uncorrected; reported alongside; CANNOT change a verdict
- **no grid correction**: The thresholds are FIXED by this document before the sample exists, so nothing is selected on the held-out data and there is no threshold-grid multiplicity to correct. The 61-fold grid Bonferroni that the DEVELOPMENT bounds paid does not apply here and must not be added.
- **no family multiplicity**: Only pnictide is tested. f-electron and intermetallic are on hold and are not part of this evaluation, so there is no family multiplicity. The 6-fold family x side multiplicity of the DEVELOPMENT fit is the reason this hypothesis is worth testing at all; it does not require a second correction on fresh data.

## Dependence audit — does testing A and B on the same structures change the procedure?

**Structural fact.** Path B is a strict SUBSET of Path A by construction: B = A minus the rows whose two engines disagree by more than the tolerance. The two tests are therefore nested and strongly positively dependent, not independent.

**Observed.** On the round-4 pnictide draw, B retained 3,501 of A's 3,637 rows (96.3%). The stable side made 306 calls with 12 errors on BOTH paths - the disagreement filter removed no stable call at all - and the unstable side had 82 errors on both. The two paths' test statistics were very nearly the same number.

**Resolution, fixed here and not revisited:**

1. Bonferroni is VALID under arbitrary dependence. It rests on Boole's inequality and assumes nothing about independence, so the nesting cannot invalidate it. Dependence costs power; it does not cost validity.
2. The promotion rule is CONJUNCTIVE - all four hypotheses must pass. That makes this an intersection-union test, for which testing each hypothesis at an uncorrected alpha already controls the type-I error of the conjunctive claim at alpha. A Bonferroni correction on top is therefore STRICTLY CONSERVATIVE.
3. Given 1 and 2, the conservative option is pre-registered as PRIMARY: each hypothesis is tested at confidence 0.9875. The effective number of independent tests is nearer 2 than 4 because of the nesting, which is a further reason the correction is conservative.
4. PRE-COMMITMENT: if a hypothesis passes at the uncorrected 0.95 but fails at the primary 0.9875, that is a FAIL. It is reported as a near-miss with both bounds shown and it does NOT support promotion. No attempt will be made, before or after seeing the data, to estimate an 'effective' correction from the observed overlap, to switch to the intersection-union justification, or to drop the correction. The choice is made here and is not revisited.

## Verdict definitions

- **PASS** — the primary-confidence lower bound is >= the target
- **FAIL** — the primary-confidence lower bound is < the target, INCLUDING the case where the point estimate is above the target. There is no 'ambiguous' verdict for a primary hypothesis. The word ambiguous is reserved for descriptive diagnostics and may never be applied to PA1/PA2/PB1/PB2.
- **INCONCLUSIVE** — the hypothesis could not be tested at all, for one of the pre-specified reasons in 'inconclusive_triggers'. An INCONCLUSIVE hypothesis is NOT a pass and NOT a fail; it blocks promotion exactly as a fail does.

### What makes a hypothesis INCONCLUSIVE

- `too_few_calls` — fewer than 20 calls on that side (confidence.MIN_SELECTED)
- `unusable_rows` — more than 2% of drawn ids produce no usable production-engine result (guard rejection, job failure or timeout). The evaluation is not rescued by retrying into a different rung.
- `missing_second_engine` — for Path B only: more than 2% of Path-A labelable rows lack a usable second-engine result
- `no_labelable_rows` — a path has zero labelable rows

## Sample size — derived, not assumed

Required structures, by hypothesis, powered against the development point estimate:

| hypothesis | target | assumed truth | calls per structure | 80% power | 90% power | 95% power |
|---|---:|---:|---:|---:|---:|---:|
| A stable | 0.9 | 0.9608 | 0.07650 | 2,353 | 2,876 | 3,530 |
| A unstable | 0.95 | 0.9740 | 0.78850 | 825 | 1,040 | 1,218 |
| B stable | 0.9 | 0.9608 | 0.07650 | 2,353 | 2,876 | 3,530 |
| B unstable | 0.95 | 0.9728 | 0.75450 | 922 | 1,180 | 1,432 |

At the primary confidence the binding hypothesis is the stable side: **2,876 structures for 90% power**, 3,530 for 95%.

### Chosen: **n = 3,500** of 5,432 eligible

3500 is chosen, not assumed. The binding hypothesis is the stable side, which converts only 0.0765 of drawn structures into calls. At the primary confidence, 90% power against the development point estimate requires 2,876 structures and 95% power requires 3,530. 3500 gives about 0.94 power on the binding hypothesis and about 1.00 on the other three, and leaves 1,932 candidates unspent for a replacement study. A 1,500-structure draw - the round-3 convention - would have given only 0.53 power on the binding hypothesis and was rejected for that reason.

### Expected calls, errors and power at n = 3,500

| hypothesis | expected calls | expected errors | max errors allowed | power |
|---|---:|---:|---:|---:|
| A stable | 268 | 10.5 | 15 | 0.935 |
| A unstable | 2,760 | 71.8 | 112 | 1.000 |
| B stable | 268 | 10.5 | 15 | 0.935 |
| B unstable | 2,641 | 71.8 | 107 | 1.000 |

### Sensitivity: if the truth were the pessimistic end of the development interval

| hypothesis | assumed truth | structures for 80% power |
|---|---:|---:|
| A stable | 0.9128 | 65,164 |
| A unstable | 0.9638 | 2,702 |
| B stable | 0.9128 | 65,164 |
| B unstable | 0.9622 | 3,645 |

**This study is powered against the DEVELOPMENT POINT ESTIMATE (0.9608 stable, 0.9740/0.9728 NPV). It is NOT powered against the pessimistic end of the development interval: if pnictide's true stable precision were 0.9128 - the development lower bound - establishing it against a 0.90 target would need roughly 65,000 structures, which the pool cannot supply and which no study should attempt for an effect that small. So a PASS means 'the thresholds behave as development suggested'. A PASS does NOT establish that true precision is comfortably above 0.90, and this document forbids claiming that it does. This is the same limit the fluoride follow-up analysis identified and it is stated in advance here.**

## The sample

- n = 3,500, drawn from 5,432 eligible candidates, leaving 1,932 unspent
- eligibility: a candidate is eligible ONLY if it has never participated in anything: not in the original WBM split (calibration or locked test), not in the round-1 oxide/halide split, not in the round-2 or round-3 splits, not in the round-4 draw, and therefore not in any fit, threshold selection, diagnostic, Path-B refit or prior evaluation. Enforced by id against round4._spent_ids() | round4.excluded_ids(), with every locked half's hash verified on the way.
- stratification: per-bin proportional over <0, 0-0.025, 0.025-0.1, 0.1-0.3, >0.3 eV/atom
- engines: both. The production engine mace-mpa-0-medium (cpu/float32, tag c2480e74) and the second engine mace-mp-0-medium (cpu/float64, tag 207ccc81) are run over the SAME drawn ids, because Path B cannot be scored without both.

Leakage guards:

- every id any earlier split or draw has used is excluded by id
- every candidate sharing a reduced formula with ANY of the six locked test halves is dropped, because WBM's unique_prototype dedups prototypes and not compositions
- per-bin proportional to the eligible pool's own hull-distance distribution, which matches the round-4 draw to within 0.0003 per bin, so the development call rates transfer

## Promotion rule

**Shared table.** ALL FOUR of PA1, PA2, PB1, PB2 must PASS at the primary confidence. Only then is the shared -20/+0 meV pnictide rule eligible for promotion to BOTH rule sets. Eligible is not the same as promoted: promotion remains a separate explicit decision by the user.

| outcome | consequence |
|---|---|
| all four PASS | Only then is the shared -20/+0 meV pnictide rule eligible for promotion to BOTH rule sets |
| A passes, B fails | NO PROMOTION, of either path. Because B is nested in A, this outcome means the rows the disagreement filter RETAINS carry disproportionate error - a surprising result needing explanation, not a licence to promote Path A alone. A Path-A-only promotion would require its own pre-registration and its own fresh held-out sample; this one is spent. |
| B passes, A fails | NO PROMOTION, of either path. Because B is nested in A, this means the rows the disagreement filter REMOVES carry disproportionate error, which would be evidence for SEPARATE tables. That is a post-hoc subgroup claim on this data and may not be acted on: it is recorded as a hypothesis for a future, separately pre-registered study. |
| any INCONCLUSIVE | NO PROMOTION. The inconclusive hypothesis is reported as inconclusive with its counts. A replacement evaluation needs a fresh pre-registration and fresh ids; approximately 1,932 eligible pnictide candidates would remain, which is why this design does not spend the whole pool. |
| all fail | NO PROMOTION. The development result is recorded as having failed to replicate. The with_second_engine pnictide defect then stands as a KNOWN defect with no validated fix, and that is reported as such rather than quietly left out of the summary. |

## Stop rules

- The sample is drawn ONCE and opened ONCE. data/pnictide_eval_log.json records the opening; the open command refuses while that file exists.
- No interim looks and no sequential testing. Every job completes, then the four hypotheses are scored in a single pass.
- If any hypothesis FAILS or is INCONCLUSIVE, stop: no other locked half is opened, no further pnictide sample is drawn, and no threshold is adjusted.
- f-electron and intermetallic remain on hold throughout. This evaluation says nothing about either and must not be reported as if it did.

## Forbidden once the sample is drawn

- REFITTING ANY THRESHOLD. The -20/+0 meV values are fixed by this document. Running certify, diagnose, best_bound or any grid search on the held-out rows is forbidden, for any purpose, including 'just to see'.
- changing the family definition, the precedence chain, the labelable definition, the weak element list, the structure-change exclusion or the disagreement tolerance
- changing the targets, the confidence, the correction, or which hypotheses are primary
- adding, dropping or reweighting hypotheses
- pooling these rows into any calibration set, now or later
- re-opening the sample, or drawing a second sample to append to it
- reporting the secondary 0.95 bound as the verdict
- describing a fitted development threshold as validated on the basis of a partial pass

## Chain of custody

1. This document is committed BEFORE the sample is drawn. Its sha256 is recorded in the opening log and verified against the file on disk at open time.
2. The draw writes data/wbm_split_pnictide_eval.json containing the id list and its sha256, and asserts disjointness from every prior split and every locked half by id. That file is committed before any job is queued.
3. The ids are reachable only through an accessor that raises PermissionError without unlock=True, and that verifies the recorded hash before returning anything.
4. Opening writes data/pnictide_eval_log.json recording: opened_at, harness commit, the sample's sha256, this document's sha256, the active bundle's sha256, and both engines' model keys, settings tags and checkpoint sha256 values.
5. The set is registered in data/locked_sets_registry.json with state and provenance.
6. Any mismatch between a recorded hash and the file on disk aborts the evaluation.

## If approved

draw the sample (its own approval), commit it, then run both engines over it, then score the four hypotheses once and report every one of them - passes and failures alike.

