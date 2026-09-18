# HANDOFF

State transfer for the next session. Written 2026-09-18 describing the repository as of commit
`ca58fd2` on `main`. Every figure here was recomputed from the repository at write time, not copied
from conversation.

This supersedes the 2026-09-17 handoff (which described commit `062ae50`). That document's
"Environment / Configuration" and "Dead Ends" sections are still true and are carried forward below;
its "Next Steps" are all done.

**Start by running the Verification block at the end.** If anything there disagrees with this
document, trust the repository.

---

## Goal

**The project.** A validation harness that measures whether a machine-learned interatomic potential
can be trusted to decide *"is this hypothetical material stable enough to be worth a DFT calculation
or a lab attempt?"* The deliverable is `harness/predict.py`, which returns `likely stable` /
`likely unstable` / `send to DFT`, each label backed by a certified error rate rather than a point
estimate.

**What this session did.** Extended certified coverage beyond oxide and halide, then put the
resulting taxonomy proposal through a full adoption review ending in a pre-registered held-out
evaluation. 55,000 relaxation + static jobs across six runs, all on the production engine.

**Where it stopped.** The one proposed taxonomy change (fluoride) passed its held-out thresholds but
its *justification* did not replicate. Nothing was adopted. The product is byte-for-byte what it was
at `062ae50`.

---

## Current State

### The product is UNCHANGED and that is deliberate

* `data/calibration_bundle.json` (v1, `created_at 2026-09-12T20:21:45+00:00`) is untouched and is
  still what `harness.predict` loads.
* `harness/confidence.py:family()` is unchanged — **there is no fluoride family in production.**
* `data/calibration_spec_v2.json` is a **frozen specification, not an active bundle.** It is
  promoted only on explicit approval, which has not been given.
* Test suite: **278 passed** with `HARNESS_MODEL=mace-mpa-0-medium` (275 passed + 3 skipped without it — the golden test only runs in-process on the production engine). Preflight OK. CI green.

### What was measured (all on MACE-MPA-0, tag `c2480e74`)

New calibration draws, all disjoint from every earlier split and from each other:

| draw | calibration | locked test |
|---|---:|---:|
| halide top-up (round 2) | 2,800 | — (round 1's 2,000 serves halide) |
| sulfide (round 2) | 4,000 | 874 |
| nitride (round 2) | 2,423 | 0 (pool exhausted) |
| carbide (round 2) | 1,876 | 0 (pool exhausted) |
| chalcogenide residual (round 3) | 4,000 | 1,500 |
| other residual (round 3) | 4,000 | 1,500 |

Headline results, **on labelable rows** (see the footing note below):

* **halide now certifies both sides.** Stable −20 meV, bound 0.9025 at n=5,135. Round 1 certified
  nothing on the stable side; test 7 predicted this family was sample-size limited and it was.
* **oxide still has no stable-side path** — eleven subfamily splits searched, nothing at 0.90, and
  nothing at 0.80 under a split-multiplicity correction.
* **sulfide, nitride, carbide all certify the unstable side.** Sulfide and carbide also certify the
  stable side on labelable rows.
* **Multi-start disagreement** (1,000 candidates, 3 starts each) rises from 0.056 in the 0–0.025
  bin to **0.509 above 0.3 eV/atom** — a second, independent confirmation of the >0.3 refusal rule,
  which previously rested on n=16.
* **Failure retry** (3,044 candidates): 4 of 6 hard failures recovered, 2 genuine engine limits;
  111 of 204 multi-start disagreements resolved by best-of; only 4.1% of 2,890 "left its start"
  cases resolved — see Dead Ends, that metric does not mean on WBM what it means on substitutions.

### The live question: the fluoride carve-out is UNRESOLVED

Only one taxonomy change was ever proposed for adoption: **fluoride carved out of halide.** It was
approved on *validity* grounds — on calibration, the pooled halide −20 meV rule labelled fluorides
at a point precision of **0.8971**, below the 0.90 the product promises.

The halide locked half was opened once, under a committed pre-registration, on 2026-09-18T19:12:05Z.

| | result |
|---|---|
| H1 halide stable precision | 157 calls, 4 errors, 0.9745, CP-lower **0.9324** ≥ 0.90 — **PASS** |
| H2 halide unstable NPV | 771 calls, 18 errors, 0.9767, CP-lower **0.9621** ≥ 0.95 — **PASS** |
| H3 fluoride unstable NPV | 428 calls, 5 errors, 0.9883, CP-lower **0.9715** ≥ 0.95 — **PASS** |
| R1 rationale check | **the deficit did not reproduce**: 0.9439 on 107 calls, CI [0.8819, 0.9791] |

So the thresholds validated and the reason for the change did not. Under the pre-registered rule R1
is **ambiguous** — neither reproduced (point ≥ 0.90) nor formally contradicted (bound < 0.90).

**The follow-up power analysis says this cannot be settled from WBM.** Only **429** unspent fluoride
candidates remain after every exclusion — about 59 stable calls, fewer than the 107 already spent.
Power from that remnant is 0.20 to establish a deficit even if the truth is 0.86. And if the truth
really is 0.8971, establishing a deficit needs ~490,000 structures, because the effect size is
0.0029 — which is the honest answer that no study should be run at all for a rule 0.3 points short.

**The carve-out's cost is certain and large:** it doubles the DFT share (0.096 → 0.192), cuts recall
44% (0.599 → 0.338), and on the held-out half costs 107 of 264 "likely stable" labels (40.5%). It
should be adopted only if a fluoride-specific deficit is established with adequate evidence, from a
targeted DFT campaign or a non-WBM source with its own pre-registration.

### Not done / open

* Nothing is frozen into the product. Five locked halves remain closed.
* `f-electron`, `intermetallic` and `pnictide` still carry 2026-09-12 thresholds fitted on
  210–1,801 rows. They are the weakest part of the product and were not re-measured.
* `chalcogenide` and `other` thresholds are **provisional** — fitted on a mixture reconstructed from
  two draws at the pool's true ratio, not on one draw of the family. They must never be described as
  held-out certified.
* Everything in spec v2 is in-sample except the three halide-side hypotheses above.

---

## The footing distinction — read this before touching any threshold

**A threshold means different things on "usable" and "labelable" rows, and the difference is large.**

* **usable** — not rejected by the energy-plausibility guard.
* **labelable** — usable, *and* surviving the weak-element and structure-change exclusions. This is
  the population `calibration.fit()` is documented to take and the frozen bundle was fitted on.

**Labelable is authoritative for certification** (user ruling, 2026-09-18). All-usable figures are
retained as a secondary diagnostic of engine behaviour, and `reports/round2_results.md` carries a
correction section explaining which of its numbers are on which footing. Two conclusions in that
document are superseded:

| | all usable | labelable |
|---|---|---|
| halide stable | −70 meV, recall 0.306 | **−20 meV, recall 0.599** |
| sulfide stable | "not certified, needs ~6,416 structures" | **certifies at −30 meV, bound 0.9047** |

The structure-changed rows the product already refuses to label were what dragged both down.

---

## Files Touched

### The round-2 / round-3 work

| File | What it does / why it matters |
|---|---|
| `harness/round2.py` | `family2()` (round-2 taxonomy, includes nitride), `family3()` (the taxonomy actually proposed: fluoride in, nitride out), both round-2 and round-3 splits, `diagnose()` / `best_bound()` / `n_needed()`. **`diagnose` selects the ceiling by the CP bound, not the point estimate** — that is what reproduces test 7 exactly. |
| `harness/orchestrator.py` | `build_round2_jobs`, `build_round3_jobs`. Both build jobs for the WHOLE draw then filter, so the cache files always hold every id (see the wholesale-cache trap). Both assert every locked half disjoint before enqueueing. |
| `harness/jobs.py` | `perturbed_restart_job` — the fallback ladder's perturbed rung alone, for candidates whose rung 1 already converged and whose question is about the basin, not convergence. |
| `data/wbm_split_round2.json` | halide top-up + sulfide/nitride/carbide. **Made once.** Groups drawn *sequentially* against a shared taken-set. |
| `data/wbm_split_round3.json` | chalcogenide and "other" residual draws. **Made once.** Same guards. |
| `data/calibration_spec_v2.json` | The frozen specification: taxonomy, thresholds, population definition, exclusion rules, per-family provenance and status, calibration id-set hashes. **Written once; do not regenerate.** |
| `data/locked_sets_registry.json` | Every held-out set, its hash, provenance and state. **Regenerated on demand** — it reads the halide opening log rather than asserting a state, so it cannot go stale. |
| `data/halide_evaluation_preregistration.json`, `reports/halide_evaluation_preregistration.md` | The pre-registration, committed at `4027b57` before the half was opened. **Never edit.** |
| `data/halide_test_log.json` | The opening record. Its existence is what makes `scripts/halide_eval.py open` refuse. **Never delete.** |

### Scripts (all read-only unless stated)

| Script | Purpose |
|---|---|
| `scripts/round2.py` | Phase driver. `assert-engine` aborts on a wrong `HARNESS_MODEL`; negative-tested. Enqueues phases 1–3, round 3, retries. |
| `scripts/round2_analyse.py` | Certification + diagnosis per group; `--splits=N` adds a split-multiplicity correction. Emits `.md` and `.json`. |
| `scripts/round2_multistart.py` | Phase 5. `recompute` re-derives from saved starts without re-running anything. |
| `scripts/round2_retry.py` | Phase 6. One dispatching pool, slowest jobs first. |
| `scripts/round2_summarise.py` | Phase 5/6 summary tables. |
| `scripts/round2_ledger.py` | Verifies the locked-set ledger rather than asserting it. |
| `scripts/round2_taxonomy_decision.py` | The carve-out decision report; holds `labelable_mask()` and `certify_both()`, reused by the round-3 scripts. |
| `scripts/round3_residual.py` | Residual-parent measurement and the head-to-head routing comparison. |
| `scripts/round3_final_spec.py` | The final proposed taxonomy / thresholds / protocol. |
| `scripts/freeze_spec_v2.py` | Writes the frozen spec (once) and the registry (regenerable). |
| `scripts/prereg_halide_eval.py` | Writes the pre-registration. Refuses to overwrite. |
| `scripts/halide_eval.py` | **The one-time evaluation.** `open` refuses while the log exists. |
| `scripts/fluoride_power.py` | The follow-up sizing analysis. Uses no locked data. |
| `reports/build_round2_report.py` | Builds `reports/round2_results.{md,pdf}` — sections 13–18, continuing the existing document (which ends at **12**, not 10). |

### Gitignored caches this work created

`cache/external/wbm/{round2,round3}_calibration_{init_structs,cse}.json`,
`cache/external/wbm/halide_test_{init_structs,cse}.json`. Distinct filenames on purpose.

---

## Environment / Configuration

Unchanged from the previous handoff, and still true:

* **Machine:** Apple M4 Max, 14 cores, 36 GB, macOS. CPU only.
* **Python env:** `.venv/bin/python` (3.12); project-local `./uvw` wrapper; `.tools/` is gitignored.
* **Ephemeral deps:** `pypdf`, `fonttools`, `reportlab` via `./uvw run --with <pkg> --no-project`.
* **`HARNESS_MODEL` is the one to remember.** Unset, it defaults to `mace-mp-0-medium` — the
  *second* engine. Production work must set `HARNESS_MODEL=mace-mpa-0-medium`.
* **Real throughput is ~0.2–0.3 s per job**, not the 9.8 s/relaxation in section 1 of the results
  PDF (that is the engine-screening benchmark on larger cells). 16,000 jobs drain in ~38 min.
  **But a perturbed or compressed START costs ~15× a WBM initial structure** — phase 5 took 3.3 h
  for 2,000 relaxations and phase 6 took 4.8 h for 3,044.
* **CI:** one workflow, `secret scan`, two jobs. gitleaks is not installed locally; CI runs it.

### Commands

```bash
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/round2.py assert-engine
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/round2_ledger.py
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m harness status
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q
bash scripts/preflight_publish.sh
```

---

## Decisions Made (do not re-litigate)

* **Labelable rows are authoritative for certification**; all-usable is a secondary diagnostic.
* **The carve-out criterion is validity, not routing efficiency.** A child is carved out only where
  the parent's pooled rule has a genuine *precision deficit* on the child — point precision below
  target — not merely a loose bound on a small subgroup. Routing efficiency was considered and
  rejected: it rejects all three carve-outs *including the valid one*, because pooling always buys
  statistical power and a split always spends it.
* **Adopted (pending held-out confirmation, now unresolved):** fluoride out of halide.
* **Rejected:** nitride (removes pnictide's only certified threshold), sulfide (no deficit, 0.9448),
  carbide (no deficit, 0.9826).
* **The sulfide locked half is SEALED, not closed.** Its ids, hash and provenance are retained; it
  is unavailable to the present analysis and available to a future separately pre-registered
  question. Do not delete it.
* **`family()` is not changed until v2 is promoted.** Inserting fluoride now would leave it with no
  entry in v1's threshold table and silently stop the product labelling fluorides.

---

## Failed Approaches / Dead Ends

Carried forward from the previous handoff (all still true): the wholesale-cache trap in
`ood.load_structures`; never re-run a calibration without pinning the engine; COD cannot be queried
naively; `gitleaks dir` is not what CI runs; NIST SRD is copyrighted; the unreachable sources list.

New this session:

* **A `None` round-trips through a pandas column as `NaN`, and `bool(NaN)` is `True`.** This cost
  two silent wrong tables: it excluded the calibration relaxation from all 1,000 multi-start
  comparisons, and it routed every phase-6 retry to the wrong ladder rung. Nothing raised; both
  produced plausible-looking output. Every read of a rejection now goes through an `_nn()` helper.
* **`Composition.oxi_state_guesses()` returns a TUPLE**, so `== []` never matches. The mixed-valence
  split silently matched zero oxides.
* All three were caught by **reading a count that could not be right** (0 mixed-valence oxides,
  0 candidates with 3 usable starts, 0 perturbed restarts) — not by any guard.
* **Comparing populations instead of routing one population two ways.** The first taxonomy decision
  report compared the *residual* parent against the *whole* parent and never asked what happens to
  the carved-out rows. That reversed the fluoride recommendation when corrected. The same error
  invalidates the "regime B" baseline, whose `chalcogenide` threshold was fitted on 3,698 rows of
  which 3,684 were sulfides.
* **`pkill -f <script>.py` matches any watcher whose own command line contains that string** — it
  killed two background waiters. Demonstrated, not assumed.
* **Running a small batch of pathological jobs as a separate pool before a large batch.** Six ladder
  jobs at up to 5,400 s each held 3,038 perturbed restarts for nearly two hours. Use one dispatching
  pool, slowest first.
* **"Relaxation left its start" does not mean on WBM what it means on substitutions.** A WBM initial
  structure is a pre-DFT elemental-substitution guess, not a claimed minimum, so leaving it is
  expected. Only 4.1% of 2,890 such cases stay put on a perturbed restart. Test 4 measured this
  against a known DFT-relaxed target, where leaving really is a failure. For a candidate with no
  known target, use **multi-start disagreement** instead.
* **The pool is finite and is now largely spent.** Sulfide would need ~6,416 calibration structures
  against 4,874 available; nitride ~3,106 against 2,423; an independent fluoride study needs
  thousands and 429 remain. Check availability *before* planning a draw.

---

## Known Issues

* **`reports/round2_results.md` sections 13–18 are on the all-usable footing.** The correction
  section says so and gives the labelable figures, but the tables themselves were not rewritten.
* **`reports/round2_check_r1.md`** is a scratch reproduction check, not a deliverable.
* Backups still land on the same physical disk; the backup script warns on every run.
* 2 failed and 4 timed-out jobs remain in the queue from earlier sessions (`substitution_auto`,
  `stability`). Unrelated to this work.
* The `chalcogenide` / `other` thresholds depend on a reconstructed mixture; a single representative
  whole-parent draw was never made for either.

---

## Next Steps

1. **The fluoride decision is the user's and is genuinely open.** The options are: (a) drop the
   carve-out and keep halide pooled — the held-out point estimate supports this and it costs
   nothing; (b) commission a non-WBM fluoride study per `reports/fluoride_followup_power.md`;
   (c) adopt anyway on the calibration estimate — **not recommended**, it spends 40% of the
   family's labels on an unreplicated result.
2. **Everything else in spec v2 is adoptable without fluoride.** halide (pooled), oxide,
   chalcogenide and "other" all have thresholds fitted on thousands of rows, replacing ones fitted
   on 143–274. That is a strict evidence improvement and needs no taxonomy change at all. It would
   still need its own pre-registered held-out evaluation — the oxide and round-3 halves exist for
   exactly that, in the order given in `reports/round3_final_spec.md` §6.
3. **If v2 is promoted:** change `family()`, write the new bundle, and keep v1 on disk. Do not
   `force` over `data/calibration_bundle.json`.
4. **Re-measure f-electron, intermetallic and pnictide.** They carry the oldest, thinnest thresholds
   in the product and nothing in two rounds has touched them.
5. **Reference-data strands** from the previous handoff are all still open and untouched.

---

## Verification

```bash
# 1. Repository — expect: clean, ca58fd2 or later, in sync with origin
git status --porcelain && git log --oneline -1 && git fetch -q && git rev-parse HEAD origin/main

# 2. Tests — expect: 278 passed WITH the env var, 275 passed + 3 skipped without it
#    (the 3 are test_predict.py's golden test, which only runs in-process on the production engine)
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q

# 3. Locked sets — expect: original WBM and halide OPENED ONCE, sulfide SEALED, three UNOPENED
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/freeze_spec_v2.py

# 4. The product is unchanged
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -c "
import json; from harness import confidence as C
b = json.load(open('data/calibration_bundle.json'))
assert b['created_at'] == '2026-09-12T20:21:45+00:00', 'bundle v1 was modified'
assert 'fluoride' not in C.FAMILIES, 'family() was changed'
print('v1 active and unmodified; no fluoride in production')"

# 5. The halide half cannot be re-opened
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/halide_eval.py open   # must refuse

# 6. Publication — expect: PREFLIGHT OK
bash scripts/preflight_publish.sh
```

**Invariants. If any is false, stop and investigate:**

* `data/calibration_bundle.json` still has `created_at: 2026-09-12T20:21:45+00:00`.
* `confidence.FAMILIES` does not contain `fluoride`.
* `data/halide_test_log.json` exists, records `opened_at 2026-09-18T19:12:05+00:00`, and its
  recorded `specification.sha256` still matches `data/calibration_spec_v2.json` on disk.
* `splits.test_ids()`, `splits.family_test_ids('oxide')`, `round2.test_ids('sulfide')` and both
  `round2.test_ids3(...)` all raise `PermissionError`.
* Every locked half's recorded sha256 verifies (`scripts/round2_ledger.py`).
