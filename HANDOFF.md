# HANDOFF

State transfer for the next session, written 2026-10-07 local (2026-10-08 UTC) at the end of the aerospace literature-and-data session.
Every figure was recomputed from the repository at write time, not copied from conversation. The exceptions are marked *carried forward*.

This supersedes the 2026-09-29 handoff (commit `cbc2a36`) and folds in what it predates: the MD scoping, aerospace Stage 1, and this session. Its "Decisions",
"Dead ends", "Known issues" and "Environment" sections are carried forward below and extended. **None of the paused stability-track decisions (a)-(d) was taken.**

**Start with the Verification block at the end.** If anything there disagrees with this document, trust the repository.

---

## Goal (unchanged since the aerospace pivot)

The harness exists to measure whether a machine-learned interatomic potential can be trusted to decide *"is this hypothetical material worth a DFT calculation or a lab attempt?"*.
`harness/predict.py` is unchanged. The product was narrowed to the **space-environment durability of ultralight aerospace metals** (atomic-oxygen erosion and radiation damage in LEO).

## Evidence tiers (unchanged)

| tier | meaning | what it licenses |
|---|---|---|
| **development / calibration** | thresholds selected on a population and scored on it | nothing |
| **pre-registered held-out** | protocol frozen and committed before the sample is opened; opened once | a production change, on an explicit decision |
| **production-adopted** | what `data/calibration_bundle.json` actually loads | the product's behaviour |

**Everything aerospace is below tier 1 or at it.** This session's reports are **development / descriptive, no verdict**. The Stage 2 file is a *draft*, not a pre-registration.

## Current state of the product (unchanged)

`data/calibration_bundle.json`: sha256 `419c11514d6a5485…`, `created_at 2026-09-12T20:21:45+00:00`, one entry in `promotions[]` (pnictide), no `confirmations[]`.
**Only f-electron and pnictide can return `likely stable`.** The registry (sha256 `d33efcc3…`), every locked set and `harness/predict.py` are untouched.

---

## What happened since the last handoff

### Stage 1 and the MD scoping (2026-09-29/30, commits `4101b42`, `59e8840`, `7f327b3`)

- **Scoping** (`reports/aerospace_md_scoping.md`): "add ZBL" is not the fix, because MPA-0 already has MACE's own ZBL term, 4-7x weaker than universal ZBL. AO erosion and radiation cascades are
  different problems and only the second needs ZBL. Full cascades are out of reach on this machine (6.6 MB per atom); 500-atom E_d and impact studies are feasible at 0.54 s per force call.
- **Stage 1** (`harness/zbl.py`, `reports/aerospace_stage1.md`): a pairwise correction that subtracts the engine's own dimer curve and adds universal ZBL, switched over 0.40-0.70 of the covalent-radius sum.
  **2 of 3 gates pass; gate 2 FAILED** at its 1 meV tolerance (5.4 meV on `al_defects/zero_pressure/864/tetrahedral`). The diagnosis: float32 run-to-run noise of the engine itself (engine alone vs Phase 0: 4.88 meV;
  14 of 40 values bit-identical between plain and corrected runs). **The recorded verdict stays FAIL.**

### This session: five phases and a stretch (7 commits, `4962c72` to `05be1e2`)

| phase | commit | result |
|---|---|---|
| **A** ingest | `4962c72` | six more NTRS flight sources; 105 new rows (153 total) |
| **B** Cu vs fluence | `9ef7cf6` | `reports/aerospace_cu_fluence.md/.json` |
| **C** vacancy population | `7de7a22` | `reports/aerospace_vacancy_population.md/.json` and per-engine runs |
| **D** Stage 2 draft, **E** MAPTIS plan | `bfbc9df` | `reports/drafts/aerospace_stage2_preregistration_DRAFT.md`, `docs/methodology/maptis_query_plan.md` |
| stretch | `0dedf28` | `reports/aerospace_tphase_stretch.md` (read, no engine data point) |
| cleanup | `4c3cc26`, `05be1e2` | scrubbed three printed values from my own code/test/aggregate; one-page summary; leak-check script |

The one-page summary is `reports/aerospace_lit_summary.md`.

**Phase 0 (verification) found:** HEAD was 6 nightly checkpoint commits ahead of `origin/main` (they change only `results/summary.json`). The suite ran **350 passed**, equal to the old 344 plus the 6 tests in
`tests/test_zbl.py`. `aerospace_ingest.py` rebuilt the Phase 1 rows to `b1b352d8…`. Stage 1 files matched their commits.

**Discrepancies between the brief and the primary sources (all recorded in `docs/methodology/data_provenance.md`):**

1. **NTRS 19930011567 is not a second version of the Raikar paper.** It is NASA CR-192306, a grant report that encloses a copy. The paper (19930019095) is the archival one.
2. **NTRS 20080033099 has no document**: an abstract, no PDF, licence `OTHER`, no per-tray exposure table. Dropped. The cross-walk target the brief wanted does not exist on NTRS.
3. **NIST `hdl:11256/102` did not resolve** (HTTP 500 and 404). The paper's own appendix tables (CC BY 3.0) were used instead.
4. **The "recommended 25 eV" for Al could not be traced:** its refs 63 and 66 are a textbook and an ASTM standard, both paywalled. The primary Al electron-irradiation papers (APS abstract pages) say 16 eV.
5. de Rooij has **4 thickness points, 3 with a readable fluence** (E02's exponent is printed "09"), not 5-7. The brief's Willenshofer paper is in a **2026** issue (received 2025-07-14).
6. The Lewis EOIM-3 memorandum is a **different set of samples** from the MSFC EOIM-3 paper already ingested, with a different detection limit (0.1 mg against +-0.02 mg).

### Phase A: the flight rows

- **153 rows from 6 sources:** mass_change 60 (20 are upper bounds), surface_composition 44, optical_property 18, oxide_thickness 17, film_thickness 4, accommodation 5, reactivity 5; exposure_only 0.
- **Schema:** `quantity_kind`, `is_upper_bound`, `detection_limit`, `specimen_id`, `oxide_phase`, `extra_json`. Rows pool only within one (kind, quantity, unit), never measured with upper bound (`assert_poolable`).
- **Hashes:** `phase1_rows_sha256` `b1b352d8…` (the original 48 rows, still byte-identical and now pinned in the script) and `rows_sha256` `aece8651…` (all 153, in `durability_rows_v2.csv`).
- **Checks that gate the write:** hashes; row-by-row OCR agreement (64 of 65 Lewis rows; 1 garbled, image unambiguous); Raikar's own Pilling-Bedworth relation; Table II averages; MISSE-6 printed deltas; CR-192306 carries the same numbers.
  Three source inconsistencies are recorded, not fixed.

### Phase B: Cu oxide against fluence

- n is 3-5; the two LDEF sources are **not the same hardware** and are not independent on the fluence scale. The stated law has **no printed constants**.
- The one-parameter forms fail; the two-parameter forms cannot be told apart. The EOIM-3 null set is **weak evidence**: an oxide as thick as LDEF's Cu holds about 41x less mass than the Lewis 0.1 mg limit.
- The harness gives static energies, not rates. **It cannot predict this growth.**

### Phase C: vacancy formation against 78 PBE values (Angsten et al. 2014)

| engine | median \|engine - ref\| (eV) | max | pairs over 0.2 eV |
|---|---:|---|---:|
| MPA-0 (production) | **0.095** | 0.653 (fcc Er) | 14 |
| MP-0 (second) | 0.189 (median signed -0.17) | 2.272 (fcc Os) | 38 |

The reference is PBE DFT, not experiment. The six named elements: MPA-0 median 0.083 eV, MP-0 0.078 (Ti -0.67). Migration barriers (single-image constrained saddle, **not NEB**) cost 4 s per element on MPA-0.

### Phases D, E and the stretch

- **Stage 2 draft:** compare a sampled minimum with the measured 16 eV, not the 25 eV convention; the ZBL swap is nearly inert for E_PKA up to 36 eV, so Stage 2 tests the engine's own wall; pilot 9.0-13.5 h (over the 2 h gate), with a 27-minute calibration first.
  Al is not in Nordlund's arc-dpa table. CascadesDB could not be read.
- **MAPTIS plan:** written from a 2013 NTRS presentation that says nothing about cost or terms. Under about 30 usable rows, drop MISSE.
- **T-phase:** Materials Project has no Mg32(Zn,Al)49, so nothing was relaxed.

---

## Locked / held-out sets (registry: 9 rows, all hashes verify) (unchanged, re-verified this session)

| set | n | status |
|---|---:|---|
| original WBM locked test | 4,000 | OPENED ONCE (2026-09-12) |
| oxide (round 1) | 2,000 | **UNOPENED** |
| halide (round 1) | 2,000 | OPENED ONCE (2026-09-18) |
| sulfide (round 2) | 874 | SEALED, unused under the current taxonomy |
| chalcogenide residual (round 3) | 1,500 | **UNOPENED** |
| other residual (round 3) | 1,500 | **UNOPENED** |
| pnictide evaluation (round 4) | 3,500 | OPENED ONCE (2026-09-19) |
| f-electron evaluation | 4,500 | OPENED ONCE (2026-09-24) |
| **OQMD external held-out** | **445,984** | **LOCKED, UNOPENED** |

**Unspent WBM pool, fully guarded: 140,268** (*carried forward*; no file under `data/` changed since `cbc2a36`, so nothing was drawn). By family: f-electron 89,273, intermetallic 33,707, other 7,991, oxide 4,517,
chalcogenide 2,092, pnictide 1,523, halide 1,165. **OQMD held-out by family** (*carried forward*, the half is locked): f-electron 192,604, intermetallic 92,898, oxide 50,526, chalcogenide 39,732, other 30,532, pnictide 26,516, halide 13,176.
**The local OQMD copy contains the locked half. Do not query it for anything.**

---

## Open decisions: nothing here is mine to make

1. **Stage 2: freeze the draft pre-registration and run it, or stop?**
   - The reference is unsettled (measured 16 eV against the 25 eV convention); the draft recommends 16 eV and a +-4 eV tolerance, and lists what you would fix at freeze (section 11 of the draft).
   - The pilot is 9.0-13.5 h of single-process time, over the 2 h gate, needs resumable run machinery and competes with the nightly runner. A 27-minute calibration (3 runs) is the only thing proposed before a freeze.
   - It tests radiation-damage physics, which no flight data in hand measures; and in this regime it tests the engine's own repulsive wall, not the ZBL swap.
2. **Gate 2 re-specification** (Stage 1 open decision 1). The FAIL stands. The draft says how it is handled if you do not decide; if you do, the re-specified gate runs first.
3. **Commit flight values** (decision 5, still not taken)? There are now 153 rows from US-Government public-use documents (one source, MISSE-6, is `PUBLIC_USE_PERMITTED`). The committed reports carry aggregates, and
   `scripts/aerospace_flight_leak_check.py` guards the rule. Two things to know: aggregates (maxima, ratios) are committed, and the Phase 1 provenance quotes the one ambiguous cell.
4. **MAPTIS: pay and run the query plan, or drop MISSE?** Unknown: whether your account is live, what it costs, and the terms. The plan reads those first and drops MISSE under about 30 usable rows. MISSE-6 already gives 8 metal-class samples with fluence.
5. **Is Cu2O against fluence still the first target, given Phase B?** n is 3-5, the sources are not independent, there are no printed constants, Raikar's point disagrees with the strips, and the harness cannot predict rates.
   Options: keep it as a descriptive reference; fetch the *Oxidation of Metals* paper (publisher-copyrighted) for more points; or choose another target.
6. **The paused stability-screening track (a)-(d): resume or stay parked?** Unchanged below.

### Paused stability-screening track (*carried forward unchanged* from 2026-09-26)

**(a) Record the f-electron confirmation?** All four hypotheses passed. Recording changes no threshold, only status and provenance. Review `reports/felectron_confirmation_proposal.md`, then run
`scripts/record_felectron_confirmation.py --i-have-an-explicit-decision` as its own production commit and update the bundle-sha invariant.
**(b) Intermetallic: pre-register or not.** The stable side's 4.5% call rate binds (`reports/intermetallic_sizing.md`). OQMD development finds no certifiable stable threshold either.
**(c) Pre-register an OQMD held-out evaluation, and for which family?** Unstable side: intermetallic, oxide, halide, chalcogenide or other would pass in development. Stable side: do not use OQMD until the convention question behind the 0.389 / 0.519 precision is resolved.
**(d) Fluoride.** At the development tier only an unstable +0 meV threshold looks certifiable.
**Also for a decision:** extending the curated public export beyond round 4; refreshing `docs/methodology/evidence_tiers.md`.

---

## Decisions made (do not re-litigate)

Carried forward:
- Labelable rows are authoritative. Evidence commits are separate from production commits. Historical documents are not retconned. A pre-registration is pushed before its sample is drawn.
- Carve-outs need a validity deficit. The sulfide half is sealed, not deleted. A confirmation of a live rule goes in `confirmations[]`. OQMD stage 2 is per material. OQMD development rows are split by the hull shift at the row's own composition.
- MP hull placement for bulk evaluations uses the validated bulk index.
- Aerospace flight data is ingested by a plain script, not a harness module. Row-level flight values stay gitignored until open decision 3 says otherwise.
- The Phase 2 quantity is oxide formation energy per O on the MP-corrected convention. Reference values are cited from the primary source, not a secondary table.

New this session:
- **Cu2O against fluence is the working first target**, chosen by Isac on 2026-10-07, development tier, revisitable (open decision 5).
- **Rows of different `quantity_kind` or quantity are never pooled, and detection limits are stored as upper bounds, never as zeros.**
- **No bot check is bypassed.** A source behind one is recorded as unread.
- **OQMD is not consulted by the aerospace track** (its local copy holds the locked half).
- **The E_d comparison quantity is a sampled minimum against the measured onset**; the 25 eV figure is a convention, not a verdict criterion (draft).
- **Every number in a report is computed or asserted from a file at write time**, and printed flight values do not appear in code, tests or aggregates (the leak check enforces it).

## Failed approaches / dead ends

Carried forward: the wholesale-cache trap in `ood.load_structures`; pin the engine; COD cannot be queried naively; NIST SRD is copyrighted; `bool(NaN)` is `True`; `oxi_state_guesses()` returns a tuple;
compare routings, not populations; never `pkill -f <script>.py`; one runner per queue, one engine per runner; the runner pauses on battery; the runner's checkpoint sweeps in uncommitted files; margin is not effect size;
a stricter correction can buy a tighter threshold; a held-out bound can exceed a development bound; use the bisection sizer; never write absolute paths into a tracked file; "file exists" is not "committed";
`launchctl bootout` does not survive a reboot; the queue claims smallest cells first; per-system MP API fetching does not scale; the OQMD protostructure function needs Python 3.14 or later; MP's terms page sits behind a Cloudflare check;
the nightly checkpoint commits every changed path at 23:00 local; MISSE via MAPTIS is paid for non-NASA users and `materialsinspace.nasa.gov` does not resolve; scanned NTRS tables need the page image, not the OCR layer;
NTRS search needs short keywords; tests pinned to a real date expire; `pdftoppm` is not installed, so use `./uvw run --with pypdf`.

New:
- **Behind bot challenges or paywalls (not bypassed):** Wiley, ScienceDirect and ORNL pages, the IOP PDF endpoint, IAEA CascadesDB (403 and 402), MDPI direct, OpenKIM item pages intermittently (503 once). OSTI's PDF answered 429 "too many concurrent downloads".
- **What does work, openly:** Europe PMC's full-text XML API for open-access papers; NTRS `api/citations/<id>`; APS abstract pages; Springer/Nature article and table pages; author copies on university sites; DOI pages for open-access IOP articles (HTML only).
- **The shell blocks `sleep`**; `curl` needs `--compressed` for some sites (OpenKIM returns gzip).
- **`harness.zbl.switch()` returns `(S, dS/dr)`**, and `universal()` returns the energy only.
- **A leak check on short numbers is useless** (DFT and printed values coincide); the committed check searches long strings only (5+ characters, or exponent forms).
- **MP has no T-phase; the pre-existing IDs are the new `mp-aaa…` style.**
- NTRS `stiType: ABSTRACT` with `downloadsAvailable: false` means there is no document to ingest.

## Known issues

- `docs/methodology/evidence_tiers.md` is still stale (pnictide "pre-registered but not run"). Refreshing it is a decision.
- **Local `results/results.parquet` is newer than the committed copy** and has grown past the checkpoint's 5 MB limit, so checkpoints leave it out. The tree always shows it modified.
- **gitleaks is not installed.** The preflight's full-history scan relies on its built-in patterns only.
- **The Phase 0 memo quotes 23 literature values**, and the Phase 1 code and provenance quote the one ambiguous Ti 75A print and three print-form examples. If open decision 3 reads the rule strictly, those need the same treatment.
- **Regenerating the Phase 2, Phase B or Phase C report dirties the tree** (each writes a new timestamp).
- **Committed aggregates can coincide with a printed value** (a maximum, a ratio). The control maximum that did was removed this session; others are derived ratios and counts.
- **Migration barriers are a rough screen.** 4 (MPA-0) and 7 (MP-0) came out negative, which is the method failing on unstable hosts; large positive differences remain.
- **Stage 2's turning points are two-body free-dimer estimates**, not lattice calculations.
- **The Lewis AES percentages** do not say what they are relative to, and the Tungsten and Molybdenum cells are identical as printed.
- Carried forward: the curated public export covers round 4 only; the OQMD label reconstruction matches the stored `stability` for 0.8343 of development rows; `reports/round2_results.md` is on the all-usable footing;
  `data/calibration_spec_v2.json` says "NOT yet executed"; the registry omits the MP unseen test (n = 325); `scripts/round2_ledger.py` flags the authorised halide opening; the public history contains ids of four unopened WBM halves;
  2 failed and 4 timed-out old jobs; backups go to the same disk.

## Environment / configuration

- Apple M4 Max, 14 cores, 36 GB, CPU only, Darwin 27.0. `.venv/bin/python` (3.12) and `./uvw`.
- **`HARNESS_MODEL`:** unset means the *second* engine (`mace-mp-0-medium`). The production engine is `mace-mpa-0-medium`. MPA-0 runs float32; MP-0 float64.
- **The nightly agent** `com.materials-harness.nightly` is loaded, unchanged and not running; the queue is empty, so each night it only checkpoints. Nothing was enqueued this session, and the aerospace scripts run directly.
- **Aerospace throughput:** Phase 0 and Phase 2 as before (12 / 18 min and 2.4 / 3.3 min for MPA-0 / MP-0). Phase C: the 78-pair population with migration took **638 s (MPA-0)** and **1,012 s (MP-0)**, two processes at 6 threads each.
  MPA-0: 0.54 s per force call at 500 atoms (`reports/aerospace_md_scoping.json`).
- **`cache/external/aerospace/`** (gitignored): `ntrs/` (16 PDFs and API captures), `transcription.json` and `transcription_v2.json`, `durability_rows.csv` (the original 48, unchanged) and `durability_rows_v2.csv` (153),
  `development_side_by_side.md`, `cu_fluence_side_by_side.md` (values and fitted constants), and `angsten/`, `ed/`, `comparators/`, `tphase/`, `provenance/`.

```bash
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/freeze_spec_v2.py   # rewrites the registry timestamp: git checkout it after
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m harness status
./uvw run --with pypdf python scripts/aerospace_ingest.py                     # rebuild the flight rows from the cached PDFs
.venv/bin/python scripts/aerospace_flight_leak_check.py                       # no printed flight value in committed files
bash scripts/preflight_publish.sh
```

---

## Verification

```bash
# 1. Repository: after the push, expect HEAD == origin/main, with only results/results.parquet modified
git status --porcelain && git log --oneline -1 && git fetch -q && git rev-parse HEAD origin/main

# 2. Tests: expect 352 passed with the env var (344 + 6 test_zbl + 2 test_aerospace_ingest)
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

# 6. Aerospace: the original rows and the full table both rebuild; the report reproduces; no printed flight value is committed
./uvw run -q --with pypdf python scripts/aerospace_ingest.py | grep -E '"(phase1_)?rows_sha256"'   # expect b1b352d8… and aece8651…
git diff --quiet reports/aerospace_phase1_ingest.json && echo "ingest report reproduced"
.venv/bin/python scripts/aerospace_flight_leak_check.py                                           # expect exit 0

# 7. Agents and publication
launchctl print gui/$(id -u)/com.materials-harness.nightly | grep -m1 path
bash scripts/preflight_publish.sh
```

**Invariants. If any is false, stop and investigate.**

- `data/calibration_bundle.json` has sha256 `419c11514d6a5485…` until decision (a) is taken.
- `data/locked_sets_registry.json` has sha256 `d33efcc36d221daa…` and every recorded set hash verifies (9 rows).
- `data/felectron_eval_log.json` exists and records `authorised_by: Isac Smith, 2026-09-24`.
- `data/oqmd_heldout_log.json` does **not** exist; `external_oqmd.heldout_ids()` raises without `unlock=True`.
- `confidence.FAMILIES` contains no `fluoride`; the taxonomy is unchanged.
- `data/calibration_spec_v2.json`'s sha256 still matches the value in `data/halide_test_log.json`.
- **No committed file contains a printed flight value** (`scripts/aerospace_flight_leak_check.py` exits 0).
- **The flight rows rebuild:** `phase1_rows_sha256` `b1b352d8…` and `rows_sha256` `aece8651…`.
- **The Stage 2 file stays a draft** until Isac freezes it: `reports/drafts/aerospace_stage2_preregistration_DRAFT.md` is titled DRAFT, NOT FROZEN, and no E_d MD has been run.
- **Gate 2's recorded verdict is FAIL** (`reports/aerospace_stage1.json`, `all_gates_pass: false`).
