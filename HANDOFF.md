# HANDOFF

State transfer for the next session. Written 2026-09-22 describing the repository at commit
`a184156` on `main`. Every figure was recomputed from the repository at write time, not copied from
conversation.

This supersedes the 2026-09-18 handoff (commit `ca58fd2`). Its "Environment", "Dead Ends" and
"Decisions" sections are carried forward below and extended; its "Next Steps" are done or overtaken.

**Start with the Verification block at the end.** If anything there disagrees with this document,
trust the repository.

---

## Goal

A validation harness measuring whether a machine-learned interatomic potential can be trusted to
decide *"is this hypothetical material worth a DFT calculation or a lab attempt?"* The deliverable is
`harness/predict.py`, returning `likely stable` / `likely unstable` / `send to DFT`, each backed by a
**certified** error rate rather than a point estimate.

---

## The one thing to understand first: evidence tiers

Conflating these is the failure mode the whole project exists to avoid. `docs/methodology/evidence_tiers.md`
is the public statement of it.

| tier | meaning | what it licenses |
|---|---|---|
| **development / calibration** | thresholds selected on a population and scored on it | nothing. The most optimistic estimate that exists |
| **pre-registered held-out** | protocol frozen and committed *before* the sample is opened; opened once | a production change, on an explicit decision |
| **production-adopted** | what `data/calibration_bundle.json` actually loads | the product's behaviour |

Two held-out evaluations have ever been run: **halide** (2026-09-18) and **pnictide** (2026-09-19).
A third, **f-electron**, is pre-registered and drawn but **not opened**.

---

## Current state of the product

`data/calibration_bundle.json`, `created_at 2026-09-12T20:21:45+00:00` (the fit date, preserved),
`modified_at 2026-09-19T23:14:38+00:00`, sha256 `419c11514d6a5485…`.

**One family has ever been promoted: pnictide.** Everything else is as it was on 2026-09-12.

| family | `without_second_engine` | `with_second_engine` |
|---|---|---|
| f-electron | −20 / +10 meV (n=1801) | −20 / +10 meV (n=1747) |
| intermetallic | none / +0 meV (n=665) | none / +0 meV (n=645) |
| oxide | none / +30 meV (n=189) | none / none (n=185) |
| halide | none / none (n=153) | none / none (n=143) |
| chalcogenide | none / none (n=224) | none / none (n=214) |
| **pnictide** | **−20 / +0 meV (n=3637)** | **−20 / +0 meV (n=3501)** |
| other | none / +30 meV (n=274) | none / +30 meV (n=263) |

Read as `stable / unstable`. `none` means no rule on that side, so every such candidate goes to DFT.
Both pnictide entries carry `status: PREREGISTERED HELD-OUT CONFIRMED` and the bundle's top-level
`promotions[]` records the full provenance. The pre-promotion bundle is preserved at
`data/calibration_bundle_pre_pnictide.json`, so any claim that "nothing else changed" is diffable
rather than arguable.

**Only two families can return `likely stable` at all: f-electron and pnictide.** That is the
product's binding constraint and the reason the open work is shaped the way it is.

---

## What happened since the last handoff

### Round 4 — the three carried-over families re-measured

`f-electron`, `intermetallic` and `pnictide` still carried thresholds fitted on 1,801 / 665 / 210
rows. 4,000 fresh development structures were drawn per family (`data/wbm_split_round4.json`), then
the same 12,000 were run again on the second engine. 48,000 jobs, zero failures.
Reports: `reports/round4_carried_over.md`, `round4_second_engine.md`, `round4_pathb_refit.md`,
and the 9-page `round4_results.pdf`.

* **pnictide** gained both sides on 3,637 rows.
* **intermetallic** gained a stable side on 3,613 rows; its unstable margin is only **+0.0039**.
* **f-electron LOST its stable certification** — the live rule's corrected bound was 0.8944.
* **Supplying a second engine made the product worse**: weighted DFT share 0.1763 → 0.4069, because
  the `with_second_engine` pnictide entry was `none/none` from a 202-row fit and sent **100%** of
  pnictides to DFT.
* The Path-B refit reached the **same threshold in 5 of 6 selections**, so one shared rule table is
  indicated, not two. Most of the apparent gain was sample size, not the second engine.

### Pnictide — pre-registered, evaluated, promoted

Pre-registration `data/pnictide_evaluation_preregistration.json` (sha256 `effe583b…`, commit
`0826a39`) committed **before** the 3,500-id sample was drawn. Opened once, 2026-09-19T05:26:57Z.

| id | path | side | counts | point | CP-lower @0.9875 | verdict |
|---|---|---|---|---:|---:|---|
| PA1 | A | stable | 263/275 | 0.9564 | 0.9201 | **PASS** |
| PA2 | A | unstable | 2673/2739 | 0.9759 | 0.9685 | **PASS** |
| PB1 | B | stable | 261/273 | 0.9560 | 0.9196 | **PASS** |
| PB2 | B | unstable | 2565/2631 | 0.9749 | 0.9672 | **PASS** |

All four inside their pre-registered error budgets; call counts within ~3% of the sizing prediction.
Promoted in a **separate** commit (`ffad866`) from the evidence commit (`33b9d61`).
`reports/pnictide_test.md`, `reports/pnictide_promotion_impact.md`.

**Pnictide is closed.** Do not reopen or reuse its held-out set, and do not do further pnictide
fitting, unless a regression or genuinely new independent evidence gives a reason.

### f-electron — development question resolved, held-out question open

A **frozen** development top-up (plan and ids committed at `3e15a07` *before* any outcome was
computed) added 4,800 structures to round 4's 4,000. At n=8,800 the live −20 meV threshold certifies
on **both** paths under the **full** family correction (grid × 6): bounds **0.9171** (A) and
**0.9231** (B). The two development cohorts are statistically indistinguishable (p 0.232 / 0.219)
with bin compositions agreeing to 0.002, so this is a better-powered measurement, not a mixture.
`reports/felectron_topup.md`.

That resolved the *development* question and left exactly one open: does it hold out of sample?

### f-electron held-out — pre-registered and DRAWN, not opened

* Pre-registration `data/felectron_evaluation_preregistration.json`, sha256 `d3995f66…`,
  commit `37886a8`, **pushed before the draw**.
* Sample `data/wbm_split_felectron_eval.json`, **n=4,500**, sha256 `43a675a7…`, commit `a184156`.
* Under test: the **LIVE** rule, stable −20 meV **and** unstable +10 meV, both paths. Four
  hypotheses EA1/EA2/EB1/EB2 at confidence 0.9875.
* Pre-specified power 0.961 / 1.000 / 0.988 / 1.000.
* **Consumes no earlier locked half** — round 4 reserved no f-electron half, so this is a fresh draw.

**Nothing has been queued or scored.** `data/felectron_eval_log.json` does not exist.

### Public export

`reports/public/`, `results/public/`, `docs/methodology/` — aggregate-only, no identifiers, no seeds,
no row-level data, enforced by assertions in `scripts/build_public_export.py`. The repository is
**public** (`isacrsmith-ux/materials-harness`).

---

## Locked / held-out sets

| set | n | status |
|---|---:|---|
| original WBM locked test | 4,000 | OPENED ONCE (2026-09-12) |
| oxide (round 1) | 2,000 | **UNOPENED** |
| halide (round 1) | 2,000 | OPENED ONCE (2026-09-18) |
| sulfide (round 2) | 874 | SEALED — retained, unavailable |
| chalcogenide residual (round 3) | 1,500 | **UNOPENED** |
| other residual (round 3) | 1,500 | **UNOPENED** |
| pnictide evaluation (round 4) | 3,500 | OPENED ONCE (2026-09-19) |
| **f-electron evaluation** | **4,500** | **DRAWN, UNOPENED** |

All hashes verify. **9 accessors refuse without `unlock=True`.** The registry
(`data/locked_sets_registry.json`) reads each state from its opening log rather than asserting it,
so it cannot go stale — `scripts/freeze_spec_v2.py` regenerates it.

**Unspent, leakage-guarded pool: 140,268** — f-electron 89,273, intermetallic 33,707, other 7,991,
oxide 4,517, chalcogenide 2,092, pnictide 1,523, halide 1,165. 67,273 ids are spent.

> **Three different "remaining" numbers exist and they do not conflict.** For f-electron:
> **93,307** excludes spent ids only; **89,273** also drops candidates sharing a reduced formula with
> any protected set; **91,834** is what `wbm_split_felectron_eval.json` recorded, because at draw time
> its own 4,500 ids were not yet protected and so did not contribute to the formula guard.
> **Use 89,273** — the fully guarded figure — when sizing any future draw. Rerun the recompute rather
> than trusting a stored count, since the guarded number shrinks every time a set is drawn.

---

## Open decisions — nothing here is mine to make

1. **Open the f-electron sample and score EA1/EA2/EB1/EB2.** Drawn and waiting. Queue both engines
   over the 4,500 ids (one runner per engine — see Dead Ends), then score once. The pre-registration
   fixes the outcome branches in advance: **a FAIL does not automatically remove or loosen the live
   rule**, because doing so would leave pnictide as the only stable-labelling family, which is a
   product judgement, not a statistical one.
2. **Intermetallic: pre-register or not.** Sizing is done (`reports/intermetallic_sizing.md`):
   n=3,500 gives ≥0.96 power on all four hypotheses. But the binding constraint is the *stable*
   side's 4.5% call rate, not the thin +0.0039 unstable margin — and at a true stable precision of
   0.9200 (the development bound) certification would need ~43,500 structures, more than the entire
   remaining pool. A failure would therefore be ambiguous. That asymmetry belongs in the
   pre-registration if one is written.
3. **Fluoride remains unresolved** and WBM cannot settle it (`reports/fluoride_followup_power.md`).
4. **External validation is untouched.** `docs/methodology/external_validation_design.md` assesses
   candidate sources. The key finding: **Alexandria is training data for the primary engine**
   (`MPtrj + sAlex`), so it cannot serve as independent validation. OQMD is the strongest public
   candidate; a targeted DFT campaign is the only route to the claims nothing public supports.

---

## Decisions made (do not re-litigate)

* **Labelable rows are authoritative for certification**; all-usable is a secondary diagnostic.
* **Evidence commits are separate from production commits.** Pnictide did this and it should stay
  the pattern.
* **Historical documents are not retconned.** `reports/validation_report.md` §6c still records
  pnictide's superseded +50 meV rule, and `test_the_published_reports_are_not_retconned` enforces it.
  The same reasoning kept `round2_results.{md,pdf}` from being regenerated when the corrected ledger
  would have rewritten a table written "as of" an earlier date.
* **A pre-registration must be pushed before the sample is drawn.** `scripts/draw_felectron_eval.py`
  enforces it; the pnictide draw could not.
* **Carve-outs need a validity deficit, not routing efficiency.** Sulfide, carbide, nitride stay
  pooled.
* **The sulfide half is SEALED, not deleted.**

---

## Failed approaches / dead ends

Carried forward and still true: the wholesale-cache trap in `ood.load_structures`; never re-run a
calibration without pinning the engine; COD cannot be queried naively; NIST SRD is copyrighted;
`bool(NaN)` is `True` and a `None` round-trips through pandas as `NaN`;
`Composition.oxi_state_guesses()` returns a tuple; comparing populations instead of routing one
population two ways; `pkill -f <script>.py` kills watchers; one dispatching pool, slowest first.

New this session:

* **One runner per queue, one engine per runner. This cost two incidents.** During the pnictide
  evaluation a runner started under the production engine refused 7,000 second-engine jobs with
  `SettingsMismatch`. During the f-electron top-up a still-alive production-engine runner held the
  fcntl lock, so the second-engine runner never started — and `run_unattended.sh` surfaces that
  *only* as a missing log file. Both were caught before damage. `scripts/felectron_topup_run.py`
  now inspects the **runner state**, not just pending job tags, which is what the first fix missed.
* **The runner pauses on battery** and dispatches nothing until AC returns. It looks like a hang.
* **The unattended runner auto-commits a checkpoint on finish** and sweeps whatever is uncommitted
  into it. Source written during a run lands in a checkpoint rather than a descriptive commit. Do
  not rewrite those; they are valid records.
* **Margin is not effect size.** Intermetallic's +0.0039 unstable margin looked like the binding
  constraint and is not: its effect size is 0.0152 and its call rate 82%. The stable side's 4.5%
  call rate binds instead.
* **A stricter correction can buy a *tighter* threshold.** `certify` returns the loosest threshold
  whose bound clears, so under a stricter level a looser threshold stops clearing and it falls back.
  Not a bug.
* **A held-out bound can exceed a development bound at similar n.** Development pays a 61-fold grid
  Bonferroni because a threshold was *selected*; a held-out test of a *fixed* threshold pays none.
  This is expected and must not be reported as the held-out data being "better".
* **The sizing search was O(n²) in beta quantiles** and made sensitivity sweeps intractable.
  `scripts/intermetallic_sizing.py` bisects on the monotone bound; reuse that, not the older loops.

---

## Known issues

* `reports/round2_results.md` §§13–18 are on the all-usable footing; its correction section gives the
  labelable figures. Its "Locked and unopened" table predates the halide opening. **Deliberately not
  regenerated** — see Decisions.
* `data/calibration_spec_v2.json` still says the evaluation procedure is "NOT yet executed". It is
  frozen and its sha256 is attested by `data/halide_test_log.json`, so it **must not be edited**.
* The locked-set registry omits the MP "unseen test" (`data/unseen_test.json`, n=325, opened
  2026-09-12) despite claiming to list every held-out set. Known gap, never fixed.
* `scripts/round2_ledger.py` covers only four halves and flags the *authorised* halide opening as
  `*** A LOCKED SET WAS TOUCHED ***`. Prefer `scripts/freeze_spec_v2.py`.
* **The repository is public and its history contains the ids of four unopened halves** (oxide,
  sulfide, chalcogenide, other). Documented in `reports/public/WITHHELD.md`; predates this work and
  cannot be undone by curation.
* 2 failed + 4 timed-out jobs from earlier sessions (`substitution_auto`, `stability`). Unrelated.
* Backups land on the same physical disk; the backup script warns each run.

---

## Environment / configuration

* **Machine:** Apple M4 Max, 14 cores, 36 GB, macOS. CPU only.
* **Python:** `.venv/bin/python` (3.12); project-local `./uvw`; `.tools/` gitignored.
* **Ephemeral deps:** `pypdf`, `fonttools`, `reportlab` via `./uvw run --with <pkg> --no-project`.
* **`HARNESS_MODEL` is the one to remember.** Unset it defaults to `mace-mp-0-medium`, the *second*
  engine. Production work must set `HARNESS_MODEL=mace-mpa-0-medium` (tag `c2480e74`); the second
  engine is `mace-mp-0-medium` at cpu/float64 (tag `207ccc81`).
* **Throughput:** the round-4 draw did 24,000 jobs in 38.7 min (~10 jobs/s). f-electron cells are
  slower. The status line's ETA divides by *median* job runtime and badly underestimates a
  relaxation-heavy queue. A perturbed or compressed start costs ~15× a WBM initial structure.
* **CI:** one workflow, `secret scan`, two jobs. gitleaks is not installed locally; CI runs it over
  all commits on all branches.

### Commands

```bash
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/freeze_spec_v2.py     # regenerates the registry
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m harness status
bash scripts/preflight_publish.sh
```

---

## Verification

```bash
# 1. Repository — expect a184156 or later; one commit ahead of origin unless pushed
git status --porcelain && git log --oneline -1 && git fetch -q && git rev-parse HEAD origin/main

# 2. Tests — expect 314 passed with the env var
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q

# 3. Locked sets — expect 8 rows, all hashes ok, f-electron DRAWN/UNOPENED
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/freeze_spec_v2.py

# 4. The product carries exactly one promotion
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -c "
import json; b = json.load(open('data/calibration_bundle.json'))
assert b['created_at'] == '2026-09-12T20:21:45+00:00'
assert [p['family'] for p in b['promotions']] == ['pnictide']
for p in ('with_second_engine', 'without_second_engine'):
    e = b['rules'][p]['thresholds']['pnictide']
    assert (e['stable'], e['unstable']) == (-0.02, 0.0), p
print('pnictide promoted in both rule sets; nothing else')"

# 5. The f-electron sample is drawn and NOT opened
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -c "
from harness import felectron_eval as FE
assert not FE.is_opened(), 'the f-electron sample has been opened'
try: FE.test_ids(); raise SystemExit('LEAK')
except PermissionError: pass
print('f-electron: drawn, locked, unopened')"

# 6. Publication
bash scripts/preflight_publish.sh
```

**Invariants. If any is false, stop and investigate.**

* `data/calibration_bundle.json` has `created_at 2026-09-12T20:21:45+00:00` and exactly one entry in
  `promotions[]`, for pnictide.
* `confidence.FAMILIES` contains no `fluoride`; the taxonomy is unchanged.
* `data/calibration_spec_v2.json`'s sha256 still matches the value in `data/halide_test_log.json`.
* `data/halide_test_log.json` and `data/pnictide_eval_log.json` exist; `data/felectron_eval_log.json`
  does **not**.
* All nine locked accessors raise `PermissionError` without `unlock=True`.
* Every locked half's recorded sha256 verifies.
