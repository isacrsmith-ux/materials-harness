# HANDOFF

State transfer for the next session. Written 2026-09-17 describing the repository as of commit
`062ae50` on `main` — the last substantive commit, pushed, CI green, working tree clean. Every
figure here was recomputed from the repository at write time, not copied from conversation; the
commands embedded below were run verbatim and produce the output they claim.

Start by running the **Verification** block at the end. If anything there disagrees with this
document, trust the repository and treat this file as stale.

---

## Goal

**The project.** A validation harness that measures whether a machine-learned interatomic potential
(MLIP) can be trusted to decide *"is this hypothetical material stable enough to be worth a DFT
calculation or a lab attempt?"* The deliverable is not a benchmark score — it is a product
(`harness/predict.py`) that takes a parent material plus an element substitution and returns
`likely stable` / `likely unstable` / `send to DFT`, with each label backed by a statistically
certified error rate rather than a point estimate.

**What is being worked on now.** Two strands, both at a natural stopping point:

1. **Extending certified coverage to oxides and halides.** The harness's headline precision was
   measured on WBM, which is 53 % f-electron — and f-electron was the only chemistry family that
   could certify a "likely stable" threshold at all. What Materials Project actually adds is
   oxides and halides, where nothing was certified, so 82 % of real candidates were routed to DFT
   by default. A new 7,500-structure calibration task was built and run to fix that.
2. **A citable experimental reference-data collection** (`reference_data/`) for property suites to
   be validated later — elastic constants, thermal expansion, phonons, space-environment data.

**What finished looks like.** For strand 1: certified per-family thresholds for oxide and halide
frozen into `data/calibration_bundle.json`, validated once against their locked test halves, and a
measurable drop in the share of real candidates sent to DFT. For strand 2: enough traceable
experimental data to validate the property suites without a circular dependency on DFT.

---

## Current State

### Working and complete

* **The product and its evidence base.** Ten tests are run and reported; `reports/test_results.pdf`
  (13 pp) consolidates all of them with each section naming its source report. The locked WBM test
  was opened once (2026-09-12) and both targets held out of sample: precision 0.960 [0.93, 0.98]
  against a 0.90 target, NPV 0.988 against 0.95.
* **The oxide/halide calibration has RUN on the production engine.** 15,000 jobs (7,500
  relaxations + 7,500 statics), 0 job failures, settings tag `c2480e74`. Verified present:
  oxide 3,994 usable rows, halide 3,500.
* **`reference_data/`** — 48 room-temperature oxide lattice constants (COD, each with its own DOI
  and stated uncertainty), 41 atomic-oxygen erosion yields (NASA/TM-2006-214482), a 30-row shared
  key table, JSON Schemas, a validating loader, and 24 tests. `python reference_data/loader.py`
  passes.
* **Publication hygiene.** Apache-2.0 for code, CC BY 4.0 for `data/`, `reports/`,
  `reference_data/` data. Preflight and CI both green.
* **Test suite: 275 passed, 3 skipped.**

### Partially complete — this is the live decision

The oxide/halide calibration has been **run and analysed but NOT frozen into the product.**
`data/calibration_bundle.json` is untouched (created 2026-09-12) and still records
`oxide {stable: None, unstable: None, n: 185}` and `halide {stable: None, unstable: None, n: 143}`.

Recomputed from the repository at write time, production engine:

| family | n | stable side | unstable side | stable-side ceiling |
|---|---:|---|---|---|
| oxide | 3,994 | **not certified** | **+0 meV**, NPV 0.9781, CP-lower 0.9692 | point precision **0.8750** at −20 meV (CP-lower 0.8005) |
| halide | 3,500 | **not certified** | **+0 meV**, NPV 0.9644, CP-lower 0.9516 | point precision **0.9401** at −70 meV (CP-lower 0.8803) |

**The two families fail the stable side for different reasons, and this is the key finding:**

* **Halide is sample-size limited — fixable.** Its true precision (0.9401) is already *above* the
  0.90 target; only the Clopper-Pearson bound falls short. It needs ~492 selected stable calls
  against the 267 available, i.e. **~1.8× more halide calibration structures** (~6,300 vs 3,500).
  The pool held 10,095 halides, so the data exists.
* **Oxide is precision limited — not fixable with more data.** Point precision peaks at 0.8750,
  below target, so the bound converges under 0.90 regardless of n. It certifies at a 0.80 target
  (t = −20 meV); 0.85 does not certify.

The unstable side certifies for both, which is real progress (oxide and halide previously certified
nothing). Routing impact: 88.1 % of oxide and 74.7 % of halide candidates become discardable
without DFT.

### Not working / unresolved

* **Outgassing data is blocked.** NASA's database is behind reCAPTCHA (not bypassed, deliberately);
  the printed RP-1124 editions are scans whose data tables OCR to noise. `reference_data/SOURCES.md`
  records exactly which columns a manual export needs. **Waiting on a human export.**
* **Datasets 1–3 of the reference collection are not started** — elastic constants, thermal
  expansion, heat capacity/phonons. See Next Steps for the sourcing position on each.
* **`cost_dft = 0.02`** in `config/costs.json` has no sourced denominator (what one synthesis +
  characterisation attempt costs). Do not quote it as established; report conclusions across
  0.005–0.1.
* **The > 0.3 eV/atom refusal rule** rests on a structure-finding sample of n = 16. Expanding it is
  flagged open work in `harness/predict.py`.

### Architectural decisions already made (do not re-litigate)

* **Production engine: MACE-MPA-0 medium** (cpu/float32, tag `c2480e74`). MACE-MP-0 medium
  (cpu/float64, tag `207ccc81`) is the **second engine, used only for the disagreement signal.**
  eSEN-30M-OAM is more accurate but ~9× slower (≈ a week per full run on this machine).
  SevenNet-Omni is not adopted — ~1 % of its training data carries no documented WBM filter.
* **Mode (a) hull construction**: place the engine's energy on the DFT hull rather than relaxing
  every competitor. Measured: mode (b) makes hull-distance error *worse* by 1.9 [0.8, 3.2] meV/atom.
* **Certified per-family thresholds, not conformal bounds.** Conformal marginal coverage does not
  control the error rate among the candidates a rule *selects*, which is what a lab budget depends
  on. See the comment block at `harness/confidence.py:145`.
* **Clopper-Pearson, never bootstrap**, for any rate whose sample could be all-correct — a bootstrap
  collapses to [1.00, 1.00] on an error-free sample and was caught producing a false verdict.
* **Verdicts are read from the pessimistic end of the interval**, never the point estimate.
* **Rejected results are counted and excluded, never dropped**, so exclusions cannot quietly
  improve a mean.
* **Materials Project is deliberately NOT used as reference data** in `reference_data/` — it is
  DFT-computed and the engine trains on MP, so it would measure agreement with the training
  distribution. MP ids appear only as join keys.

---

## Files Touched

Recent work, newest first. Unchanged core modules (`harness/engine.py`, `runner.py`, `store.py`,
`jobqueue.py`, …) are not listed.

### The oxide/halide calibration task

| File | What it does / why it matters |
|---|---|
| `data/wbm_split_oxide_halide.json` | The split. oxide 4,000 cal + 2,000 locked test; halide 3,500 + 2,000. **Made once, never regenerate.** Leakage guards: 8,000 prior ids excluded, 655 dropped for sharing a reduced formula with a locked-test id. Both test halves sha256-verified. |
| `harness/splits.py` | Added `family_excluded_ids()` — returns locked test ids for **exclusion only**, never outcomes, each family's hash verified. `family_test_ids()` still raises `PermissionError` without `unlock=True`. |
| `harness/orchestrator.py` | Added `build_family_calibration_jobs()`; parameterised `build_wbm_calibration_jobs()` with `ids/init_cache/cse_cache/strict` (defaults preserve the original path exactly, pinned by a test). Refuses to enqueue if any id intersects the four locked halves. |
| `harness/__main__.py` | `prepare --family-calibration` flag. |
| `tests/test_family_calibration.py` | 10 tests: locked-id leakage, hash tampering, duplicate ids, the cache-reuse trap, and that the original calibration path is unmoved. |
| `cache/external/wbm/oxide_halide_calibration_{init_structs,cse}.json` | Extracted structures/CSEs for the 7,500. **Gitignored.** Distinct filenames on purpose — see Dead Ends. |

### The reference-data collection (`reference_data/`)

| File | What it does / why it matters |
|---|---|
| `loader.py` | Loads + validates every table. Recomputes each SI value from the source's printed value and factor, so a value left in source units is rejected rather than loaded. Refuses any row whose `source_key` is not in `SOURCES.md`. |
| `lattice_constants.csv` | 48 RT oxide determinations, each with its own DOI, stated uncertainty, space group *with cell setting*, and temperature **or** an explicit `not_stated_in_source`. |
| `space_ao_erosion.csv` | 41 MISSE 2 PEACE erosion yields. `is_lower_bound` marks the 6 the source printed with `>`; `is_fluence_witness` marks the 2 Kapton H rows that are circular. |
| `materials.csv` | Shared key table, keyed `formula\|space-group symbol`. 29 of 30 phases carry an MP id as a **join key only**. |
| `extract/*.py` | One extractor per source; re-running reproduces the CSVs byte-identically. |
| `schema/*.json` | Per-table JSON Schema incl. `si_units` and `unit_pairs` (SI col, original col, units col, factor). |
| `SOURCES.md` | Every source with licence and commercial-use status, **and the sources attempted and rejected**, so the same dead ends are not re-explored. |
| `COVERAGE.md` | Counts, overlap with the substitution suite, the experimental-spread cross-check, ranked gaps. Regenerate with `extract/coverage_report.py`. |
| `raw/` | Vendored public-domain sources (NASA memorandum + COD caches) so the build reproduces offline. Excluded from this project's licence grants. |

### Reporting and publication hygiene

| File | What it does / why it matters |
|---|---|
| `reports/test_results.pdf` | 13-page consolidation of all ten tests plus the two audits. |
| `reports/build_test_results_pdf.py` | Regenerates it. `reportlab` is deliberately **not** a project dependency — supplied by `uvw run --with`. |
| `scripts/preflight_publish.sh` | §4b excludes binary blobs (and says how many); **§4c decodes every tracked PDF** and scans its real text, streams and metadata. Negative-tested. |
| `.gitattributes` | Marks PDFs and other binaries as binary. Without it git classes an ASCII85 PDF as text and `git grep -I` matches noise inside compressed streams. |
| `.gitleaks.toml` | Two narrowly-scoped literal allowlists, each with its reason. Never allowlists a file, path or rule. |
| `.github/workflows/secret-scan.yml` | Installs gitleaks **and uv** (uv is needed for §4c), then runs preflight; second job scans full history. |
| `NOTICE`, `README.md`, `reference_data/LICENSE` | Licence split incl. `reference_data/`; NOTICE states plainly that two public-domain sources *are* vendored. |

---

## Environment / Configuration

* **Machine:** Apple M4 Max, 14 cores, 36 GB, macOS. CPU only — MPS cannot run float64 for MACE.
* **Python env:** `.venv/bin/python` (3.12). Project-local uv wrapper `./uvw` execs
  `.tools/bin/uv` and keeps caches inside the project. `.tools/` is **gitignored**, so a fresh
  clone has the wrapper but not the binary — CI installs uv to that exact path.
* **Ephemeral dependencies:** `pypdf`, `fonttools` and `reportlab` are NOT project dependencies.
  Use `./uvw run --with <pkg> --no-project python ...`.
* **Environment variable NAMES only** (values live in `.env`, which is gitignored and never
  tracked): `MP_API_KEY`, `HARNESS_MODEL`, `HARNESS_BACKUP_DIR`, `HARNESS_NOTIFY`,
  `HARNESS_POWER_OVERRIDE`, `HARNESS_PYTHON`, `NTFY_TOPIC`, `NTFY_SERVER`.
* **`HARNESS_MODEL` is the one to remember.** Unset, `config.MODEL` defaults to
  **`mace-mp-0-medium`** — the *second* engine. Production work must set
  `HARNESS_MODEL=mace-mpa-0-medium`.
* **Compute config is per model:** float32 gives 5 workers × 2 threads; float64 gives 10 × 1.
* **CI:** one workflow, `secret scan`, two jobs. Green at `062ae50`. `gh` CLI is authenticated.
* **Branches:** work on `main`. `round2` is fully superseded (0 commits not on main); **the user
  said explicitly: do not merge round2.**

### Commands

```bash
python -m harness status                      # queue progress, ETA, failures
python -m harness prepare --family-calibration --skip-pairs   # queue the family task
python -m harness unattended --mode full      # drain the queue
python reference_data/loader.py               # validate every reference table
bash scripts/preflight_publish.sh             # full publication check
.venv/bin/python -m pytest tests/ reference_data/tests/ -q
```

---

## Decisions Made

* **Oxide/halide was run as a NEW calibration task**, drawn only from pool ids the original split
  never touched, rather than re-using or extending the existing calibration set. This keeps the
  original results valid and the new test halves genuinely held out.
* **Experimental-only reference data.** MP elasticity was reachable and deliberately excluded as
  near-circular; `harness/suites/bulk.py` already covers that comparison and tags it
  `reference_provenance: "mp_computed"`.
* **A missing measurement temperature is recorded, never assumed.** 34 of 48 lattice rows carry
  `not_stated_in_source`. Crystallographic cells are usually ambient, but "usually" is not a
  citation.
* **Cell setting is part of a phase's identity.** Group on the full Hermann-Mauguin symbol
  (`R -3 c :H` vs `R -3 c :R`), never the space-group number — corundum's *a* is 4.75 Å in one and
  5.12 Å in the other.
* **Historical audit findings are preserved, not tidied.** `reports/licensing.md` keeps its
  "at audit" state and `reports/publish_audit.md` keeps the personal-email exposure and its
  remediation in full. The PDF shows "at audit" against "current verified" rather than restating
  closed gaps as open.
* **Do not rewrite published history for a false positive.** Allowlist the literal instead.

---

## Failed Approaches / Dead Ends

* **Do not re-run the calibration without pinning the engine.** The first 15,000-job run went to
  MACE-MP-0 because `HARNESS_MODEL` was unset, and still reported "0 failed". On that weaker engine
  halide's precision ceiling looked like 0.8313 and the conclusion would have been that *neither*
  family could ever certify. **A certification verdict cannot be generalised across engines.**
  Verify before draining: every pending `job_key` should end `@c2480e74`.
* **`ood.load_structures(ids, cache_file=...)` returns the cache file WHOLESALE and ignores `ids`
  when the file exists.** Reusing a populated filename for a different id set silently returns the
  wrong structures, logs the misses at WARNING only, and enqueues nothing — measured: 0 jobs, which
  looks exactly like success. Always use a fresh filename; `strict=True` now makes it an error.
* **COD cannot be queried naively.** Raw formula matching returned 100 rows of which 52 were
  contaminated, in four distinct ways: its structured pressure field is **null even for explicit
  diamond-anvil studies** (only the title reveals them); compression and in-situ heating series
  masquerade as repeat measurements; formula matching pulls in other compounds (a SiO₂ hit was a
  zeolite); doped samples sit under the parent formula (the first Al₂O₃ hit is ruby). The filters in
  `extract/cod_oxides.py` encode all four.
* **Renaming a constant to `CITATION_KEY` does not clear gitleaks** — the rule keys on the
  identifier containing `KEY`. Tested against 8.30.1: of `SOURCE_KEY`, `CITATION_KEY`,
  `CITATION_ID`, `SOURCE_REF`, `CITATION_SLUG`, `SOURCE_TAG`, `CITATION`, `BIB_REF`, only the two
  containing `KEY` are flagged. `CITATION_ID` is in use.
* **`gitleaks dir` is not what CI runs.** It scans the filesystem ignoring gitignore and reports
  ~250 findings from `.env` and vendored `.uv-cache` source. CI runs `gitleaks git`.
* **Do not text-scan binary blobs for secrets.** It is noisy *and* incomplete: it matched three
  chance runs in PDF streams while missing a genuine address inside a compressed stream.
* **Sources that are unreachable, already tried:** the Duffy Princeton single-crystal elasticity
  database (403 to both fetch and curl), Zenodo (403), the NASA outgassing database (reCAPTCHA),
  and RP-1124 in both printed editions (scans, OCR unusable).
* **NIST Standard Reference Data is copyrighted** under 15 U.S.C. §290e despite being free to read
  — the Chemistry WebBook is SRD 69, "All rights reserved". Individual facts are not copyrightable
  but the compilation is. Store cited values, never bulk tables, and mark those rows
  non-redistributable. No NIST SRD data is used in any shipped table.

---

## Known Issues

* **The oxide/halide results are analysed but not frozen.** Nothing in the product uses them yet.
  This is deliberate, pending the decision in Next Steps — not an oversight.
* **A satisfied NPV target is not the same as keeping your discoveries.** At the certified unstable
  thresholds, oxide discards 88.1 % of candidates and still loses **17.3 %** of all truly stable
  oxides (77 of 446); halide loses 11.4 % (93 of 813). Quote both numbers whenever the threshold is
  proposed for routing.
* **5 guard rejections** across the 7,500 (all "not converged"). The rejected set **differs by
  engine**, so convergence failure is engine-specific rather than intrinsic to those structures.
* **Backups land on the same physical disk as the project** — the backup script warns on every run.
  Set `HARNESS_BACKUP_DIR` to an external drive.
* **gitleaks is not installed locally**; §6 of the preflight reports that and CI does the real
  scan. To run it locally, fetch the 8.30.1 release binary.
* **Unverified:** whether MACE-MPA-0's oxide precision ceiling would move under a different
  relaxation setting or a hull built differently. Only the default path has been measured.

---

## Next Steps

1. **Put the oxide/halide decision to the user. This is the first action and it is a policy
   question, not a tuning one.** The data is in hand; what is missing is a choice:
   * **Halide** — collect ~2,800 more calibration structures (~1.8×) to certify the stable side at
     0.90. The pool supports it. Worth doing if "likely stable" coverage for halides matters.
   * **Oxide** — cannot certify at 0.90 at any n. Either accept **unstable-side-only** routing for
     oxides, or lower the stable-side target to **0.80** for that family specifically. Lowering a
     target that was frozen and published is a decision the user must make explicitly — note that
     `cost_missed_stable = 0.11` in `config/costs.json` is *derived from* the 0.90 target, so
     moving one without the other makes them inconsistent.

   Reproduce the numbers first:
   ```bash
   .venv/bin/python -c "
   from harness import calibration as CAL, confidence as C, metrics as M, splits
   IC='oxide_halide_calibration_init_structs.json'
   for fam in ('oxide','halide'):
       d=CAL.calibration_table(CAL.PRODUCTION_ENGINE,set(splits.family_calibration_ids(fam)),init_cache=IC)
       d=d.assign(stable=d.each_true<=M.ON_HULL_TOL)
       print(fam, len(d),
             'stable:', C.certify(d.each_pred,d.stable,C.TARGET_PRECISION,'stable'),
             'unstable:', C.certify(d.each_pred,d.stable,C.TARGET_NPV,'unstable'))"
   ```

2. **Only after that decision**, refit and freeze. `harness/calibration.py:build()` currently reads
   the *original* split; extending it to the family split is unwritten work. `build()` refuses to
   overwrite `data/calibration_bundle.json` without `force=True` — **do not force without the
   user's explicit word.**

3. **Do not open the four locked test halves** until the thresholds are frozen and the user
   approves the one-time evaluation. `family_test_ids()` requires `unlock=True`; nothing in the
   repository passes it.

4. **If the user supplies the outgassing export**, drop it in `reference_data/raw/` and write an
   extractor against the real file shape. The required columns are listed in `SOURCES.md`.

5. **Reference-data strands still open**, in tractability order: metals lattice constants at room
   temperature (the existing 14 metals are all 0 K/ZPAE-corrected — a gap the original brief did
   not name); thermal expansion (NIST cryogenic DB covers 43 materials, mostly alloys and polymers,
   and stops at 300 K); heat capacity/phonons; elastic constants (hardest — expect 15–30 materials
   from individual open-access papers, not 40–60).

6. **Housekeeping if idle:** expand the n = 16 structure-finding sample behind the > 0.3 eV/atom
   refusal rule; source a denominator for `cost_dft`; set `HARNESS_BACKUP_DIR` off-disk.

---

## Verification

Run these before trusting anything, and after any change:

```bash
# 1. Repository state — expect: clean, in sync with origin/main
git status --porcelain && git log --oneline -1 && git fetch -q && git rev-parse HEAD origin/main

# 2. Tests — expect: 275 passed, 3 skipped
.venv/bin/python -m pytest tests/ reference_data/tests/ -q

# 3. Reference data — expect: lattice_constants 48, materials 30, space_ao_erosion 41
.venv/bin/python reference_data/loader.py

# 4. Publication checks — expect: PREFLIGHT OK, both PDFs "clean" in section 4c
bash scripts/preflight_publish.sh

# 5. Queue — expect: 0 pending, runner not running
python -m harness status
```

**Invariants that must hold.** If any of these is false, stop and investigate before doing anything
else:

* `data/calibration_bundle.json` still has `created_at: 2026-09-12...` and records
  `oxide {stable: None, unstable: None, n: 185}` — the new results are **not** frozen in.
* Both family test halves report `locked: true` and their recorded sha256 verifies:
  ```bash
  .venv/bin/python -c "
  import json,hashlib
  s=json.load(open('data/wbm_split_oxide_halide.json'))
  for f in ('oxide','halide'):
      t=s['families'][f]['test']
      print(f, t['n'], t['locked'], hashlib.sha256(','.join(t['ids']).encode()).hexdigest()==t['sha256'])"
  ```
* The family calibration has results under the **production** tag:
  oxide 3,994 and halide 3,500 usable rows via
  `CAL.calibration_table(CAL.PRODUCTION_ENGINE, ..., init_cache="oxide_halide_calibration_init_structs.json")`.
* Regenerating `reference_data/space_ao_erosion.csv` produces a byte-identical file
  (`git diff --stat` shows nothing).

**Rebuilding the results PDF** (only if reports change):
```bash
./uvw run --with reportlab --no-project python reports/build_test_results_pdf.py
```
Then re-run the preflight — §4c decodes every tracked PDF and will fail on a real address or local
path inside one.
