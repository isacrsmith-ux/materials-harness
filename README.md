# materials-harness

A validation harness that checks whether the simulation engine behind a materials-discovery product
reproduces results that are already known, before anyone trusts it with new materials or pays for lab
tests. The engine under test is **MACE-MP-0 medium** (a machine-learned interatomic potential trained on
Materials Project PBE/PBE+U data), run through ASE on CPU in float64.

The harness answers four questions:

| Question | Suite | Compared against |
|---|---|---|
| Does the engine run and relax correctly at all? | `smoke` | Si → Ge vs Materials Project (MP) and experiment |
| If I substitute elements into a known structure, do I get the known target? | `substitution` | 50 curated MP parent→target pairs, 11 structure families, plus up to 2,000 auto-generated pairs (unattended queue) |
| Does it call stable / unstable materials correctly? | `stability` | MP convex hulls (MP2020-corrected) |
| Does accuracy hold on materials it was *not* trained on? | `ood` | random WBM structures (Matbench Discovery test set): 300 in `run`, 2,000 in the unattended queue |
| How close is it to *measured* reality? | `experimental` | 33 room-temperature lattice constants (Lucero et al. 2012) |
| Does it get stiffness right? | `bulk` | MP elastic bulk moduli (K_VRH) |

Results land in one table (`results/results.sqlite`, exported to `results/results.parquet`) — one row per
structure × test, every value tagged with provenance — and in a report per engine:

| report | engine |
|:--|:--|
| `reports/validation_report.md` | **MACE-MPA-0 medium — the engine the product would ship** |
| `reports/final_test.md` | MACE-MPA-0 on the locked WBM test set (opened once) |
| `reports/mace-mp-0-medium/validation_report.md` | MACE-MP-0 medium, the round-1 baseline |
| `reports/phase3/screening.md`, `candidates.md` | all engines on identical structures |
| `reports/leakage_check.md` | whether SevenNet-Omni's screening win survives a WBM-leakage check |
| `reports/guard_fix.md` | the energy-plausibility guard: before/after numbers |

The top level is the production engine only. `python -m harness report` writes the report for whichever
engine `HARNESS_MODEL` selects, so the baseline is regenerated with
`python -m harness report --out reports/mace-mp-0-medium`.

## The prediction layer — the product

The suites above are benchmarks. The **product** is one call: one candidate from a scientist, one
decision back.

```bash
python -m harness predict --parent mp-aaacfzaj --substitute La:Dy [--json]
```

`harness/predict.py` builds the candidate, relaxes it through the same fallback ladder the calibration
results went through, places its energy on the Materials Project hull (mode (a)), and returns a label —
`likely stable` / `likely unstable` / **`needs DFT`** — with the observed hit rate for that chemistry
family and predicted hull bin, the reasons it routed that way, the relaxed structure, its properties and
full provenance. Every threshold comes from `data/calibration_bundle.json`, frozen once from the WBM
calibration set (`python -m harness calibrate`); nothing is fitted per call.

**The contract, the refusal rules and a worked example are in [`docs/predict.md`](docs/predict.md).**

## Setup (macOS, Apple Silicon)

Everything lives inside this folder: uv, the Python interpreter, the virtualenv, caches and model weights.

```bash
# 1. project-local uv (nothing installed outside this folder)
python3 -m venv .tools && .tools/bin/pip install uv
# 2. Python 3.12 + locked dependencies (uv.lock)
./uvw python install 3.12
./uvw sync
# 3. model weights (44 MB, SHA-256 pinned in harness/config.py)
mkdir -p models && curl -L -o models/2023-12-03-mace-128-L1_epoch-199.model \
  https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/2023-12-03-mace-128-L1_epoch-199.model
# 4. Materials Project API key (never committed, never printed)
cp .env.example .env   # then paste your key after MP_API_KEY=
```

`./uvw` is a thin wrapper that pins uv's cache and managed Pythons to this folder. The harness refuses to
run under Rosetta (`platform.machine()` must be `arm64`) and detects core counts at runtime.

**WBM data for the `ood` suite** (146 MiB, md5-checked) goes in `cache/external/wbm/`:
`wbm/2023-12-13-wbm-summary.csv.gz`, `wbm/2022-10-19-wbm-init-structs.jsonl.gz` and
`wbm/2022-10-19-wbm-computed-structure-entries.jsonl.gz` (86.5 MB, md5 `655b7a9c…`; DFT-relaxed structures and
run parameters, used for the MP2020-correction audit and the MACE-vs-DFT structure classification) from the
Matbench Discovery data files, figshare doi:10.6084/m9.figshare.22715158. If the scripted download is refused
(figshare sometimes returns 403), download them in a browser and drop them there.

## Running

```bash
./uvw run python -m harness benchmark            # CPU/float64 vs MPS/float32 + worker layouts -> config/compute.json
./uvw run python -m harness run --suite smoke    # or substitution | stability | ood | experimental | bulk | all
./uvw run python -m harness report               # writes reports/validation_report.md for HARNESS_MODEL (+ figures, parquet)
./uvw run python -m harness predict --parent mp-2657 --substitute Ti:Zr    # the product: one candidate -> one decision
./uvw run pytest -m "not slow"                   # fast unit tests (no MACE, no network)
./uvw run pytest                                 # also the smoke test
```

* **Resumable.** Every job key ends in a *settings tag* — a hash of model file, device, dtype and relaxation
  settings. Reruns skip finished jobs; change any setting and everything reruns automatically instead of
  silently reusing stale numbers. `--retry-failed` reruns failures and timeouts.
* **Failures never crash a batch.** Per-structure wall-clock timeout (900 s) and step cap (500); failures,
  timeouts and rejected relaxations are logged and counted in the report.
* **Fallback ladder** (`config.FALLBACK_LADDER`) for stability competitors the guard rejects: FIRE from the end
  point (≤ 1,500 steps), then a perturbed restart from the MP structure (BFGS, ≤ 1,000 steps). The convergence
  criteria are identical on every rung; every rung is recorded. A target whose mode (b) hull still lacks one of
  the MP reference hull's own phases is **not scored** (counted as unscored); missing off-hull phases are flagged.
* **Two substitution starts.** `sub` relaxes the substituted parent cell as is; `sub_rescaled` first rescales it to
  a predicted volume (pymatgen RLS volume predictor: ionic radii, else atomic radii, else DLS bond lengths). The
  lowest-energy converged start is kept (`sub_best`) and the winner recorded. `static` is a single-point energy at
  the MP PBE structure. Every relaxed result is labelled *same structure* or *relaxed into a different structure*
  (species-aware StructureMatcher vs the target) and the two are reported separately.
* **Reference provenance.** Energies are compared with MP's *uncorrected* GGA/GGA+U energies (what MACE-MP-0 was
  trained on); hulls apply MaterialsProject2020Compatibility identically to MACE and DFT entries; hull distances
  come from the GGA/GGA+U hull, never MP's r2SCAN-mixed default. Where a document has both GGA and GGA+U
  entries, `mp_data.choose_run_type` picks the one MP2020 mixing accepts. `python -m harness phase0 audit`
  re-checks all of this against the caches.
* **Materials Project downloads are cached forever** in `cache/mp/` (exponential backoff on rate limits), so
  reruns never re-query the API.

## Unattended runs (in the background or overnight)

```bash
./uvw run python -m harness prepare        # once: bulk-download + cache MP/WBM inputs, generate pairs, fill the queue
#   --curated-kinds sub_rescaled,static     also queue curated-pair kinds;  --competitor-retries  queue the fallback ladder
./uvw run python -m harness phase0 eta     # ETA of pending jobs from each job's measured counterpart (polite / full)
./run_unattended.sh                        # polite mode (default): leaves 2 performance cores free while you work
./run_unattended.sh full                   # all performance cores (overnight)
./run_unattended.sh full --stop-at 07:00   # finish running jobs and exit at 7 AM
./uvw run python -m harness status         # progress, ETA, mode, running/paused, failures grouped by error type
./uvw run python -m harness stop           # graceful: finish running jobs, then exit
```

* **Scale** (`config/unattended.json`): up to `max_pairs` (2,000) auto-generated substitution pairs — MP
  materials with ≤ `max_atoms` (40) atoms that share a prototype (anonymized StructureMatcher on the PBE
  structures) and differ by exactly one element; oxides, nitrides, carbides and fluorides first, round-robin
  across prototypes; magnetic and f-electron targets tagged — plus `ood_sample` (2,000) WBM structures. Each
  pair runs `sub` and `ctrl`; add `sub_rattled` to `auto_pair_kinds` for the symmetry-broken supercell run
  (8× the atoms). `prepare` downloads and caches everything once (chunked, resumable, rate-limit backoff), so
  the runner itself never needs the network. None of this changes the validation logic, tolerances or metrics.
* **`run_unattended.sh`** starts the runner with `nohup`, wrapped in `caffeinate -ims`, logging to
  `logs/<timestamp>.log`. Closing the terminal does not stop it.
* **Crash-safe queue** (`results/queue.sqlite`): one row per job with status, attempts, runtime, error, model
  and settings, timestamps. After a killed process, a reboot or a crash, just start it again: jobs left
  "running" go back to pending and finished jobs are never redone. A failed or timed-out job is retried once,
  then kept as failed with its error. A watchdog restarts a hung worker pool.
* **Modes**: polite = benchmarked layout minus 2 performance cores (8 workers × 1 thread on this Mac, lowered
  priority); full = all performance cores (10 × 1).
* **Battery**: `pmset -g batt` is checked every 5 minutes. On battery the runner finishes the jobs in progress,
  pauses, and resumes automatically on AC. Note that `caffeinate -i` still keeps the Mac from idle-sleeping while
  it is paused, so it will keep using battery until you stop it or plug in.
* **Lid**: `caffeinate` does **not** prevent sleep when the lid is closed. Keep the lid open for unattended runs
  unless an external display (plus power and a keyboard/mouse) is connected. If the Mac does sleep, the runner
  freezes and continues on wake; a relaxation that timed out across the sleep is retried without penalty.
* **Notifications**: a macOS notification when a run finishes, pauses for battery, or more than 10 % of jobs
  fail. Optional phone push via [ntfy.sh](https://ntfy.sh): set `NTFY_TOPIC` in `.env` (off when empty; use a
  long random topic — anyone who knows it can read the messages).
* **Reports**: a partial report every 100 completed jobs in `reports/<run>/partial/`; the final report in
  `reports/<run>/validation_report.md` with `scorecard.json` and a comparison against the previous run's
  scorecard.
* **Nightly schedule (optional, not installed)**: a launchd user agent starts `full` mode at 23:00 and stops
  gracefully by 07:00 (times in `config/unattended.json`). `./uvw run python -m harness schedule` shows it;
  `./scripts/install_schedule.sh` installs it and `./scripts/uninstall_schedule.sh` removes it. If the Mac is
  asleep at the start time, launchd starts the run at the next wake.

## Engine settings (recorded with every simulated value)

| Setting | Value | Why |
|---|---|---|
| Model | MACE-MP-0 medium, `2023-12-03-mace-128-L1_epoch-199.model`, SHA-256 pinned | mace-torch ≥ 0.3.10 silently defaults to MACE-MPA-0; we never use the default |
| Device / dtype | CPU / float64 | MPS cannot run this model: MACE casts per-atom energies to float64 (`mace/modules/models.py`), which MPS lacks. See `config/compute.json`. |
| Parallelism | 10 workers × 1 thread (from the benchmark on this Mac); cells > 100 atoms on 2 × 5 | workers × threads ≈ performance cores |
| Relaxation | FrechetCellFilter + BFGS, fmax 0.01 eV/Å **and** max \|stress\| ≤ 0.01 GPa, ≤ 500 steps | the filter alone lets small cells stop with ~0.2 GPa residual stress |
| Sanity guard | reject any relaxation with an atom pair closer than 0.5 × the covalent-radius sum, or unconverged | a solid-O₂ relaxation once collapsed to 0.07 Å at −1.2×10¹¹ eV/atom |

## How to read the scores

**Provenance.** Every reference value is one of `mp_computed` (Materials Project DFT — always the PBE/PBE+U
`GGA_GGA+U` data, never the r2SCAN data MP's summary endpoint now serves), `experimental` (with citation and
temperature label), or `wbm_computed` (WBM DFT). Every simulated value is `simulated` with its full settings.

**What "good" looks like.**

* *Lattice parameters / volume vs MP* — measures how faithfully MACE reproduces the DFT it was trained on.
  Errors of a few tenths of a percent are good.
* *Lattice constants vs experiment* — PBE itself overestimates lattice constants by ~1 %, so a MACE error of
  ~+1 % is **expected** and is the functional's fault, not the model's. The report shows MACE, PBE and
  their difference side by side.
* *Energy vs MP (meV/atom)* — raw MACE vs MP's *uncorrected* PBE energy. Tens of meV/atom is typical; some
  elements (W, Cr, Ge, Fe₂O₃…) are off by 100–200 meV/atom.
* *Energy above hull* — how far a material sits above the most stable mix of competing phases. Mode (a) puts
  a MACE energy among MP DFT competitors; mode (b) computes every phase within 0.1 eV/atom with MACE (errors
  cancel, so it tracks MP better). "Stable" is scored at 0 and 0.1 eV/atom.
* *Out-of-distribution (WBM)* — the honest number for genuinely new materials. It is always reported next to,
  never merged with, the in-distribution score. Expect it to be worse.
* *Spin caveat* — MACE has no explicit magnetism. Magnetic, transition-metal and f-electron systems are
  flagged and reported separately; treat their numbers with extra caution.
* *Rattled substitution* — the same substitution in a symmetry-broken supercell. "Distorts to lower energy"
  can be physically correct (cubic CaTiO₃ → Pnma); "trapped higher" is a genuine failure mode.

## Round-2 evaluation design

* **Hull-distance bins everywhere.** ≤0.025, 0.025–0.1, 0.1–0.3, >0.3 eV/atom (MP targets on the GGA/GGA+U hull;
  WBM against the MP hull, with an extra <0 bin). Every metric is reported per bin with its median next to its mean
  and a 95 % bootstrap interval (`harness/metrics.py`); verdicts use the **pessimistic end** of the interval.
* **WBM calibration / locked test split** (`data/wbm_split.json`, `harness/splits.py`): made once, before any tuning.
  Calibration = the round-1 2,000-structure sample (already used for threshold exploration, so it may not enter the
  test set) + 2,000 new; test = 4,000 fresh; both in the pool's bin proportions. `splits.test_ids()` is locked; the
  report refuses to run if a test id has a result. The test set is evaluated once, at the end.
* **Stratified substitution pairs** (`pairgen.generate_stratified`, `config/unattended.json` → `stratified`): ~500
  per target bin, 30 % metallic targets, a labelled 10 % implausible-swap stratum (Hautier 2011 substitution model
  for ionic swaps, Pettifor distance where no ionic species exist), ≤ 5 pairs per prototype. Shortfalls are recorded.
* **Experiment:** Lucero 2012 (semiconductors/insulators) plus Csonka 2009 Table II (14 metals + 10 others, zero-point
  expansion removed). No bcc transition metals or oxides beyond MgO yet — stated in the report.
* **Stability decisions** (report §4) on the calibration set only: precision, recall, F1, NPV, discovery acceleration,
  a threshold sweep with precision–recall curve, and the cost-optimal threshold for the costs in `config/costs.json`
  (placeholders — set real numbers), with a sensitivity table.
* **Mode (b) on new materials** (`harness/suites/mode_b.py`, `prepare --mode-b`): 60 calibration systems per bin; all
  competing MP phases relaxed with the engine, cached by material id and settings tag (shared phases relaxed once).
* **Confidence and routing** (`harness/confidence.py`, `harness/routing.py`): conformal bounds are shown as the
  uncertainty; labels ('likely stable' / 'likely unstable' / 'send to DFT') use per-family thresholds **certified**
  on precision / NPV (Clopper–Pearson, Bonferroni over the threshold grid) because marginal conformal coverage did not
  control precision among selected candidates. DFT is a stub (`routing.FileQueueDFT`).
* **Model registry** (`config.MODELS`, env `HARNESS_MODEL`): each model's key enters the settings tag; the baseline keeps
  `207ccc81`. Models with conflicting dependencies run from their own venv (`MODELS[key]["env"]`).

## Layout

```
harness/            predict.py (THE PRODUCT), calibration.py (the frozen calibration bundle),
                    hull.py (MP hull placement, shared by the suites and the product),
                    routing.py + confidence.py (labels, thresholds, conformal bounds),
                    engine.py (MACE + relaxation), mp_data.py (cached MP access), compare.py (math),
                    store.py (SQLite), runner.py (process pool), curation.py, report.py, suites/*.py,
                    pairgen.py (auto pairs), jobqueue.py + orchestrator.py (unattended runs),
                    power.py, notify.py, schedule.py (launchd)
docs/               predict.md — the product's contract, refusal rules and a worked example
data/               curated inputs: substitution pairs, experimental table, WBM sample ids, auto_pairs.json,
                    calibration_bundle.json (the product's frozen thresholds)
config/             compute.json (benchmark layout), unattended.json (queue/scale/schedule settings)
run_unattended.sh   background launcher (nohup + caffeinate); scripts/ install/uninstall the nightly agent
reports/            validation_report.md (production engine) + figures/; mace-mp-0-medium/ (baseline);
                    final_test.md, leakage_check.md, guard_fix.md, costs.md, phase0/, phase3/; <run>/ per unattended run
tests/              unit tests (substitution, comparison, stability, OOD, bulk, guard, report) + smoke test
cache/ models/ results/ logs/   generated, gitignored (results.sqlite / results.parquet are rebuilt by rerunning)
```
