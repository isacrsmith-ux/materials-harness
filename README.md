# materials-harness

A validation harness that checks whether the simulation engine behind a materials-discovery product
reproduces results that are already known, before anyone trusts it with new materials or pays for lab
tests. The engine under test is **MACE-MP-0 medium** (a machine-learned interatomic potential trained on
Materials Project PBE/PBE+U data), run through ASE on CPU in float64.

The harness answers four questions:

| Question | Suite | Compared against |
|---|---|---|
| Does the engine run and relax correctly at all? | `smoke` | Si → Ge vs Materials Project (MP) and experiment |
| If I substitute elements into a known structure, do I get the known target? | `substitution` | 50 MP parent→target pairs, 11 structure families |
| Does it call stable / unstable materials correctly? | `stability` | MP convex hulls (MP2020-corrected) |
| Does accuracy hold on materials it was *not* trained on? | `ood` | 300 random WBM structures (Matbench Discovery test set) |
| How close is it to *measured* reality? | `experimental` | 33 room-temperature lattice constants (Lucero et al. 2012) |
| Does it get stiffness right? | `bulk` | MP elastic bulk moduli (K_VRH) |

Results land in one table (`results/results.sqlite`, exported to `results/results.parquet`) — one row per
structure × test, every value tagged with provenance — and in `reports/validation_report.md`.

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

**WBM data for the `ood` suite** (59 MiB, md5-checked) goes in `cache/external/wbm/`:
`wbm/2023-12-13-wbm-summary.csv.gz` and `wbm/2022-10-19-wbm-init-structs.jsonl.gz` from the Matbench
Discovery data files, figshare doi:10.6084/m9.figshare.22715158. If the scripted download is refused
(figshare sometimes returns 403), download them in a browser and drop them there.

## Running

```bash
./uvw run python -m harness benchmark            # CPU/float64 vs MPS/float32 + worker layouts -> config/compute.json
./uvw run python -m harness run --suite smoke    # or substitution | stability | ood | experimental | bulk | all
./uvw run python -m harness report               # writes reports/validation_report.md (+ figures, parquet)
./uvw run pytest -m "not slow"                   # fast unit tests (no MACE, no network)
./uvw run pytest                                 # also the smoke test
```

* **Resumable.** Every job key ends in a *settings tag* — a hash of model file, device, dtype and relaxation
  settings. Reruns skip finished jobs; change any setting and everything reruns automatically instead of
  silently reusing stale numbers. `--retry-failed` reruns failures and timeouts.
* **Failures never crash a batch.** Per-structure wall-clock timeout (900 s) and step cap (500); failures,
  timeouts and rejected relaxations are logged and counted in the report.
* **Materials Project downloads are cached forever** in `cache/mp/` (exponential backoff on rate limits), so
  reruns never re-query the API.

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

## Layout

```
harness/            engine.py (MACE + relaxation), mp_data.py (cached MP access), compare.py (math),
                    store.py (SQLite), runner.py (process pool), curation.py, report.py, suites/*.py
data/               curated inputs: substitution pairs, experimental table, WBM sample ids
config/compute.json benchmark result and chosen compute layout
reports/            validation_report.md + figures/ (tracked, so the report renders from git)
tests/              unit tests (substitution, comparison, stability, OOD, bulk, guard, report) + smoke test
cache/ models/ results/ logs/   generated, gitignored (results.sqlite / results.parquet are rebuilt by rerunning)
```
