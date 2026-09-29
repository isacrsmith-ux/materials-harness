# HANDOFF

State transfer for the next session, written 2026-09-29 (UTC) at the end of the aerospace-durability
pivot. Every figure was recomputed from the repository at write time, not copied from conversation.
The two exceptions are marked *carried forward*.

This supersedes the 2026-09-26 handoff (commit `961b44b`). Its "Decisions", "Dead ends", "Known
issues" and "Environment" sections are carried forward below and extended. **None of its open decisions
(a)–(d) was taken.** They are still open, now as the paused stability-screening track.

**Start with the Verification block at the end.** If anything there disagrees with this document,
trust the repository.

---

## Goal — narrowed this phase

The harness still exists to measure whether a machine-learned interatomic potential can be trusted to
decide *"is this hypothetical material worth a DFT calculation or a lab attempt?"*.
`harness/predict.py` is unchanged: it returns `likely stable` / `likely unstable` / `send to DFT`,
each backed by a certified error rate.

**The phase decision:** narrow the product to one area, the **space-environment durability of
ultralight aerospace metals** (atomic-oxygen erosion and radiation-induced defects in LEO). This was
chosen over foams, lattices and fibre-metal laminates because durability is an atomic-scale question.
The pivot ran Phases 0–2 of its brief. Its headline answer is below. What happens next is open
decision 1.

## Evidence tiers (unchanged, still the thing to understand first)

| tier | meaning | what it licenses |
|---|---|---|
| **development / calibration** | thresholds selected on a population and scored on it | nothing |
| **pre-registered held-out** | protocol frozen and committed before the sample is opened; opened once | a production change, on an explicit decision |
| **production-adopted** | what `data/calibration_bundle.json` actually loads | the product's behaviour |

**Everything from the aerospace pivot is below tier 1 or at it.** The Phase 0 memo is a capability check
with no tier. The Phase 2 report is **development / descriptive, with no verdict**. Nothing in it could
license a production change.

---

## Current state of the product — unchanged by this phase

`data/calibration_bundle.json`: sha256 `419c11514d6a5485…`, `created_at 2026-09-12T20:21:45+00:00`,
one entry in `promotions[]` (pnictide), no `confirmations[]`. **Only f-electron and pnictide can return
`likely stable`.** No aerospace work touched the bundle, the registry or any locked set.

---

## What happened in the aerospace pivot (2026-09-28/29)

Four commits, all pushed. **`origin/main` = `8cb98f6`.** The push also published the whole 2026-09-24
campaign, which had never been pushed before.

| commit | what |
|---|---|
| `6411257` | Test-only fix: two campaign-driver tests assumed "now" was before `BUILD_DEADLINE` (2026-09-27) and started failing after it. |
| `bf17658` | **Phase 0** feasibility memo, `reports/aerospace_durability_feasibility.md` |
| `77f8bc4` | **Phase 1** evidence: flight data acquired with provenance (row data gitignored) |
| `8cb98f6` | **Phase 2** evidence: `reports/aerospace_durability_development.md/.json`, DEVELOPMENT / DESCRIPTIVE tier |

### Phase 0 — what the engines can and cannot compute

`scripts/aerospace_phase0.py` ran on both engines (outputs in `reports/aerospace_phase0/`). Reference values
were read from the primary sources on 2026-09-29.

| case | MPA-0 (production) | MP-0 (second) | reference |
|---|---:|---:|---|
| Al vacancy formation (864 atoms, zero pressure) | **0.678** | 0.479 | 0.67 PBE / DMC; experiment 0.66–0.67 (Hood et al., arXiv:1210.5489, Table I) |
| Al ⟨100⟩ dumbbell | 2.160 | 1.677 | 2.70 PBE, 2.94 DMC |
| octahedral − dumbbell / tetrahedral − dumbbell | **0.200 / 0.516** | 0.193 / 0.437 | 0.21 / 0.53 PBE |
| O on Ag(111), 0.25 ML: on-surface − sub-surface | **0.593** | 0.577 | 0.66 GGA (Li et al., arXiv:cond-mat/0302122) |
| O₂ binding per O | 3.142 | 2.763 | 3.16 GGA, 2.56 experiment |

- **Static, near-equilibrium energies are usable** on the production engine. Interstitial *absolute*
  energies carry a systematic −0.55 eV offset, so use relative energies.
- **Close approach is not usable on either engine.** Below about 1.25 Å the dimer energies are 2–15× too
  soft against ZBL. MP-0's Al–Al dimer goes *negative* between 0.5 and 0.9 Å, and both engines have
  non-monotonic regions.
- **Consequence:** collision cascades and hyperthermal O impacts need MD with a short-range-corrected
  potential (ZBL-blended, as in arXiv:1904.00360). The harness has neither.
- **Recommendation (a), restricted:** static quantities, production engine, descriptive tier. The dynamic
  half is returned to the user as (b).

### Phase 1 — the flight data is much thinner than the brief assumed

Sources, NTRS licence fields, sha256s and caveats are in `docs/methodology/data_provenance.md`
("Aerospace durability sources") and `NOTICE`.

| source | usable content |
|---|---|
| **LDEF A0171** (NTRS 19930001391) | 5 samples (Ag disk, Ag ribbon, Cu, Mo, Ti 75A): reactivity and accommodation. **No fluence, no Al.** Ti accommodation is ambiguous as printed, left null. |
| **EOIM-3 metals paper** (NTRS 19950021220, *not* in the brief) | 19 mass-change samples (Δm and Δm/A), incl. Al-Li 2090 and Weldalite. Fluence 2.2×10²⁰ atoms/cm². |
| EOIM-3 overview (NTRS 19950021216, the brief's source) | Describes single-crystal Ag/Cu at [100]/[111] and 60/120/200 °C, but gives **no numbers**. No retrieved document tabulates them. |
| the three "Los Alamos" reports | Coatings, BN/Si₃N₄, and a plasma-asher silver study at Auburn. **No metal flight data.** Their ground-vs-flight comparison is qualitative. |
| **MISSE** | **Blocked.** `materialsinspace.nasa.gov` does not resolve. MAPTIS needs registration, paid for non-NASA users since January 2026 (not registered). Public Glenn documents cover 630 samples, polymer- and coating-dominated. The metal fraction of MISSE is **unknown**. |

- **How values were read.** Every value was transcribed from scanned page images, because the OCR text
  layers drop cells.
- **The ingest check.** `scripts/aerospace_ingest.py` refuses to write unless:
  - the PDF hashes match;
  - the OCR, where it survives, agrees with the transcription (34 of 48 values confirmed);
  - EOIM-3 Δm/A = Δm / 0.71 cm² within print rounding (15/15).
- **Committed:** `reports/aerospace_phase1_ingest.json` — hashes, counts and checks. **No values.**

### Phase 2 — descriptive comparison, no verdict

`scripts/aerospace_phase2.py` computes the **oxide formation energy per O atom** for the 12 elements the
flight rows cover. It relaxes 35 MP-hull oxides on both engines (35/35 converged each), placed as mode (a)
places a candidate: MP2020 corrections and MP's shared O reference. `scripts/aerospace_phase2_report.py`
writes the report.

| engine | median \|engine − MP\| (eV/O) | max | outliers > 0.1 eV/O |
|---|---:|---:|---|
| MPA-0 | 0.018 | 0.329 | TiO, NiO, Ni₃O₄ |
| MP-0 | 0.033 | 0.391 | TiO, Ti₃O, Ti₂O, NiO, Li₂O₂ |

- **Two hard limits, stated in the report.** Formation energy is not a rate, and impact/cascade physics
  is left out entirely.
- **Defect energies are left out.** No flight source measures radiation damage.
- **Flight values stay out of the committed report,** per the brief's rule. The side-by-side table is
  regenerated into gitignored `cache/external/aerospace/development_side_by_side.md`.

---

## Locked / held-out sets (registry: 9 rows, all hashes verify) — unchanged

| set | n | status |
|---|---:|---|
| original WBM locked test | 4,000 | OPENED ONCE (2026-09-12) |
| oxide (round 1) | 2,000 | **UNOPENED** |
| halide (round 1) | 2,000 | OPENED ONCE (2026-09-18) |
| sulfide (round 2) | 874 | SEALED — retained, unavailable |
| chalcogenide residual (round 3) | 1,500 | **UNOPENED** |
| other residual (round 3) | 1,500 | **UNOPENED** |
| pnictide evaluation (round 4) | 3,500 | OPENED ONCE (2026-09-19) |
| f-electron evaluation | 4,500 | OPENED ONCE (2026-09-24) |
| **OQMD external held-out** | **445,984** | **LOCKED, UNOPENED** |

**Unspent WBM pool, fully guarded (recomputed 2026-09-29): 140,268.** By family:

| f-electron | intermetallic | other | oxide | chalcogenide | pnictide | halide |
|---:|---:|---:|---:|---:|---:|---:|
| 89,273 | 33,707 | 7,991 | 4,517 | 2,092 | 1,523 | 1,165 |

67,273 ids are spent. This is unchanged, because nothing was drawn.

**OQMD held-out available by family** (*carried forward* from 2026-09-26, not recomputed because the
half is locked):

| f-electron | intermetallic | oxide | chalcogenide | other | pnictide | halide |
|---:|---:|---:|---:|---:|---:|---:|
| 192,604 | 92,898 | 50,526 | 39,732 | 30,532 | 26,516 | 13,176 |

---

## Open decisions — nothing here is mine to make

### Aerospace pivot (from the end of `reports/aerospace_durability_development.md`)

1. **Engine or new tool?** Static energies are usable at a descriptive tier. Everything the flight data
   measures is kinetic or impact-driven. The real question needs MD with a short-range-corrected potential.
   **Not built; scoping it is your call.**
2. **MISSE:** arrange paid MAPTIS access, or drop it? Ingestion is not worth building without access.
3. **Which alloy first?**
   - **Single-crystal Ag/Cu:** has no numbers available.
   - **EOIM-3 Al-Li rows:** relevant, but give no composition, confound alloy with temperature, and have an
     unreconstructable Δm/A.
   - **EOIM-3 pure metals:** cleaner, but 7 of 15 Δm are within 2× the ±0.02 mg of zero.
4. **The paused stability-screening track** (decisions (a)–(d) below): resume in parallel, or stay parked?
   The aerospace work does not compete for compute.
5. **Commit flight values?** The sources are public-use NASA documents, and
   `reference_data/space_ao_erosion.csv` already commits MISSE-2 values. The brief's rule kept these
   gitignored.

### Paused stability-screening track (carried forward unchanged from 2026-09-26)

**(a) Record the f-electron confirmation?** All four hypotheses passed. Recording changes no threshold,
only status and provenance. Review `reports/felectron_confirmation_proposal.md`, then run
`scripts/record_felectron_confirmation.py --i-have-an-explicit-decision` as its own production commit and
update the bundle-sha invariant.

**(b) Intermetallic: pre-register or not.** The stable side's 4.5% call rate binds
(`reports/intermetallic_sizing.md`). OQMD development finds no certifiable stable threshold either.

**(c) Pre-register an OQMD held-out evaluation, and for which family?** Stage 2 caps what it can mean.
- **Unstable side.** Development suggests intermetallic, oxide, halide, chalcogenide or other would pass.
- **Stable side.** Do not use OQMD for stable-side claims until the convention question behind the
  0.389 / 0.519 precision is resolved.

**(d) Fluoride.** At the development tier only an unstable +0 meV threshold looks certifiable. The stable
fluoride question remains unanswered.

**Also for a decision:**
- extending the curated public export beyond round 4;
- refreshing `docs/methodology/evidence_tiers.md`.

---

## Decisions made (do not re-litigate)

Carried forward:
- Labelable rows are authoritative.
- Evidence commits are separate from production commits.
- Historical documents are not retconned.
- A pre-registration is pushed before its sample is drawn.
- Carve-outs need a validity deficit.
- The sulfide half is sealed, not deleted.
- A confirmation of a live rule goes in `confirmations[]`, not `promotions[]`.
- OQMD stage 2 is per material.
- OQMD development rows are split by the hull shift at the row's own composition.
- MP hull placement for bulk evaluations uses the validated bulk index.

New (aerospace pivot):
- **Aerospace flight data is ingested by a plain script, not a harness module.** It is a handful of PDFs,
  not an API.
- **Row-level flight values stay gitignored** until open decision 5 says otherwise.
- **The Phase 2 quantity is oxide formation energy per O on the MP-corrected convention, with MP's O
  reference.** The O reference is shared by every metal, so its GGA overbinding cannot reorder them.
- **Reference values are cited from the primary source, not a secondary table.** arXiv:1904.00360
  labels Hood et al.'s DMC-paper values "DFT"; the memo cites Hood et al. directly.

## Failed approaches / dead ends

Carried forward:
- the wholesale-cache trap in `ood.load_structures`;
- pin the engine;
- COD cannot be queried naively;
- NIST SRD is copyrighted;
- `bool(NaN)` is `True`;
- `oxi_state_guesses()` returns a tuple;
- compare routings, not populations;
- never `pkill -f <script>.py`;
- one runner per queue, one engine per runner;
- the runner pauses on battery;
- the runner's checkpoint sweeps in uncommitted files;
- margin is not effect size;
- a stricter correction can buy a tighter threshold;
- a held-out bound can exceed a development bound;
- use the bisection sizer;
- never write absolute paths into a tracked file;
- "file exists" is not "committed";
- `launchctl bootout` does not survive a reboot;
- the queue claims smallest cells first;
- per-system MP API fetching does not scale;
- the OQMD protostructure function needs Python ≥ 3.14;
- MP's terms page sits behind a Cloudflare bot check.

New:
- **The nightly checkpoint commits every changed path at 23:00 local** (`ops.checkpoint`, `git add -A`).
  Commit or keep work out of the tree before then.
- **MISSE via MAPTIS** is paid registration for non-NASA users, and `materialsinspace.nasa.gov` does not
  resolve. Do not re-search for free access.
- **NTRS scanned tables:** the OCR text layer drops cells. Extract the page image
  (`pypdf page.images` → PIL crop) and read it.
- **NTRS search:** hyphenated or long queries return nothing. Short keyword queries work
  (`EOIM+metals` found the EOIM-3 metals paper).
- **Tests pinned to a real date expire.** Pin deadlines inside the test (fixed in `6411257`).
- **`pdftoppm` is not installed.** Read PDFs with `./uvw run --with pypdf`.

## Known issues

- `docs/methodology/evidence_tiers.md` is still stale (pnictide "pre-registered but not run"). Refreshing
  it is a decision.
- **Local `results/results.parquet` is newer than the committed copy.** It has grown past the checkpoint's
  5 MB limit, so checkpoints leave it out.
- **gitleaks is not installed.** The preflight's full-history scan relies on its built-in patterns only.
- **The Phase 0 memo quotes 23 literature reference values** in its two results tables (value plus locator). If open decision
  5 reads the rule strictly, those would need the same treatment as flight values.
- **Regenerating the Phase 2 report dirties the tree.** `scripts/aerospace_phase2_report.py` writes a new
  timestamp into the `.md` and `.json`.
- Carried forward:
  - the curated public export covers round 4 only;
  - the OQMD label reconstruction matches the stored `stability` for 0.8343 of development rows;
  - `reports/round2_results.md` is on the all-usable footing;
  - `data/calibration_spec_v2.json` says "NOT yet executed";
  - the registry omits the MP unseen test (n = 325);
  - `scripts/round2_ledger.py` flags the authorised halide opening;
  - the public history contains ids of four unopened WBM halves;
  - 2 failed and 4 timed-out old jobs;
  - backups go to the same disk.

## Environment / configuration

- Apple M4 Max, 14 cores, 36 GB, CPU only, Darwin 27.0.
- `.venv/bin/python` (3.12) and `./uvw`.
- **`HARNESS_MODEL`:** unset means the *second* engine (`mace-mp-0-medium`). The production engine is
  `mace-mpa-0-medium`.
- **Per-engine precision:** MPA-0 runs float32 per `config/compute-mace-mpa-0-medium.json`; MP-0 runs
  float64.
- **Aerospace throughput:**

  | run | MPA-0 | MP-0 |
  |---|---:|---:|
  | Phase 0, incl. 864-atom supercells | 12 min | 18 min |
  | Phase 2, 35 oxides + 12 metals | 2.4 min | 3.3 min |

- **`cache/external/aerospace/`** (gitignored) holds:
  - `ntrs/`: 9 PDFs and their metadata;
  - `provenance/`: arXiv and LAMMPS captures, and the MAPTIS page;
  - `transcription.json`, `durability_rows.csv` and `development_side_by_side.md`.
- The runner is idle: the queue is 100% done and the lock holds a dead pid. The nightly agent is loaded
  and unchanged.

```bash
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/freeze_spec_v2.py   # rewrites the registry timestamp: git checkout it after
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m harness status
./uvw run --with pypdf python scripts/aerospace_ingest.py                     # rebuild the flight rows from the cached PDFs
bash scripts/preflight_publish.sh
```

---

## Verification

```bash
# 1. Repository: expect HEAD == origin/main
git status --porcelain && git log --oneline -1 && git fetch -q && git rev-parse HEAD origin/main

# 2. Tests: expect 344 passed with the env var
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q

# 3. Locked sets: expect 9 rows, all hashes ok; f-electron OPENED ONCE; OQMD LOCKED, UNOPENED
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/freeze_spec_v2.py && git checkout -- data/locked_sets_registry.json

# 4. The product: unchanged, one promotion, no confirmation recorded
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -c "
import json, hashlib; raw = open('data/calibration_bundle.json','rb').read(); b = json.loads(raw)
assert hashlib.sha256(raw).hexdigest().startswith('419c11514d6a5485')
assert b['created_at'] == '2026-09-12T20:21:45+00:00'
assert [p['family'] for p in b['promotions']] == ['pnictide'] and 'confirmations' not in b
print('bundle unchanged')"

# 5. Held-out states
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -c "
from harness import felectron_eval as FE, external_oqmd as X
assert FE.is_opened() and not X.is_opened()
for f in (FE.test_ids, X.heldout_ids):
    try: f(); raise SystemExit('LEAK')
    except PermissionError: pass
print('f-electron opened once; OQMD half locked and unopened')"

# 6. Aerospace: flight rows rebuild to the committed hash; no flight value in committed reports
./uvw run -q --with pypdf python scripts/aerospace_ingest.py | grep rows_sha256   # expect b1b352d8…
git diff --quiet reports/aerospace_phase1_ingest.json && echo "ingest report reproduced"

# 7. Agents and publication
launchctl print gui/$(id -u)/com.materials-harness.nightly | grep -m1 path
bash scripts/preflight_publish.sh
```

**Invariants. If any is false, stop and investigate.**

- `data/calibration_bundle.json` has sha256 `419c11514d6a5485…` until decision (a) is taken.
- `data/felectron_eval_log.json` exists and records `authorised_by: Isac Smith, 2026-09-24`.
- `data/oqmd_heldout_log.json` does **not** exist; `external_oqmd.heldout_ids()` raises without `unlock=True`.
- The registry has 9 rows and every recorded sha256 verifies.
- `confidence.FAMILIES` contains no `fluoride`; the taxonomy is unchanged.
- `data/calibration_spec_v2.json`'s sha256 still matches the value in `data/halide_test_log.json`.
- **New:** no committed file contains a row-level flight value. Check `reports/aerospace_durability_development.*`
  and `reports/aerospace_phase1_ingest.json`.
