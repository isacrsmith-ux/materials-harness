# materials-harness

**Can a machine-learned interatomic potential be trusted to decide which materials are worth a lab test?**
This repository is the attempt to answer that honestly, and to say clearly where the answer is no.

The engine under test is **MACE-MPA-0 medium**, run through ASE on CPU. Around it sits a validation
harness — nine suites, a locked test set opened once, and a product layer that refuses to answer when
the evidence does not support an answer.

Every number below is the **pessimistic end of a 95 % interval**, which is the convention throughout
the reports. Each links to the section it comes from.

---

## The scorecard

### What it does well

| question | answer | where |
|:--|:--|:--|
| Does it reproduce the published benchmark? | **Yes.** F1 0.832 [0.808, 0.853] against Matbench Discovery's 0.852; DAF, precision, recall, accuracy and MAE all contain the published value | [validation_report §5](reports/validation_report.md) |
| Energy error on materials it has never seen, when the structure is right | **7–14 meV/atom** by hull bin — *trustworthy* up to 0.1 eV/atom above the hull | [validation_report](reports/validation_report.md), [unseen_test §6](reports/unseen_test.md) |
| Does it agree with *measured* lattice constants? | **1.2 % MAE** on 33 room-temperature non-metals — indistinguishable from PBE itself (−0.01 % difference), i.e. the model reproduces its training theory, and the theory's own error dominates | [validation_report §9](reports/validation_report.md) |
| On the locked test set, are its 'stable' calls right? | **precision 0.96 [0.93, 0.98]**, NPV 0.988 [0.984, 0.993], opened once | [final_test](reports/final_test.md) |

### What it does not

| question | answer | where |
|:--|:--|:--|
| Is the energy trustworthy far above the hull? | **No.** Above 0.3 eV/atom the error bound is 97 meV/atom — *not trustworthy* for any engine tested. The product refuses to label there | [validation_report](reports/validation_report.md) |
| Does the precision survive on the chemistry users actually bring? | **Not established.** On 325 real Materials Project materials the engine never trained on, precision is 1.00 but on only 22 calls — [0.85, 1.00], which cannot be told apart from the WBM result either way | [unseen_test §7](reports/unseen_test.md) |
| Does it find the right structure? | **81 % [77, 85]** overall, and **38 %** above 0.3 eV/atom. Measured for the first time in `unseen_test`; the benchmark numbers say nothing about it | [unseen_test §5](reports/unseen_test.md) |
| Can it rank the polymorphs of a composition? | **Ground state first 69 % [63, 74]**, Spearman ρ 0.66 — *use with caution*. When the two lowest forms are within 10 meV/atom it drops to 0.55, near chance | [polymorph](reports/polymorph.md) |
| Bulk moduli? | **11.9 % MAE [8.2, 16.8]** vs MP's K_VRH — *use with caution* | [validation_report §10](reports/validation_report.md) |
| Is the best-scoring engine on our screening the one to adopt? | **No.** SevenNet-Omni screens better, but ~1 % of its training data carries no documented WBM filter. The evidence says the win is *probably real but not certified*; it is **not adopted** | [leakage_check](reports/leakage_check.md) |

### The finding that matters most

Scoring 325 real MP materials end to end through the product — parent prototype plus a substitution,
never the answer's own DFT cell — the share of candidates sent to DFT goes **41 % → 82 %**.

Not because the engine got worse: energy accuracy is as good or better than on the benchmark. Because
the certified decision thresholds are per chemistry family, and **the benchmark's chemistry is not the
user's**. WBM is 53 % f-electron — the only family in which a 'likely stable' threshold could be
certified at all — while what Materials Project actually adds is 48 % oxide, where nothing is
certified on either side. ([unseen_test §4b](reports/unseen_test.md))

---

## How the numbers were kept honest

* **A locked test set, opened once.** 8,000 WBM structures were split into calibration and test
  (`data/wbm_split.json`, seeded, stratified by hull bin) **before any tuning**. Every threshold,
  bound and cost optimum was fitted on calibration only. The test half was hashed, never touched, and
  evaluated exactly once — `data/final_test_log.json` records when. The same discipline applies to
  `data/unseen_test.json`.
* **Stratify, never filter.** Every metric is reported per hull-distance bin. Nothing is dropped to
  improve an average.
* **Nothing dropped silently.** Unconverged, failed, timed-out and physically impossible results are
  counted and named in the report that excludes them. One converged relaxation with an energy of
  −1131 eV/atom was corrupting whole cells of the tables; finding it, fixing it, and publishing the
  before/after is [guard_fix](reports/guard_fix.md).
* **Verdicts from the pessimistic bound**, and for rates that could come out perfect, Clopper–Pearson
  rather than a bootstrap — a bootstrap of 22-out-of-22 returns [1.00, 1.00], which is an artifact of
  the estimator, not evidence.
* **Costs are placeholders.** `config/costs.json` holds 1:1 values. Any number derived from them says
  so where it appears ([costs](reports/costs.md)); the decision thresholds are certified
  precision/NPV targets, not cost optima.

---

## The product: one candidate, one decision

The suites are a benchmark. The product is a single call.

```bash
python -m harness predict --parent mp-aaacfzaj --substitute La:Dy
```

```
candidate       DyCuPb  (6 atoms, SG 194, hexagonal)
decision        LIKELY UNSTABLE
hull distance   +50 meV/atom (predicted, mode (a))
second engine   +29 meV/atom (MACE-MP-0 medium)
confidence      a plain 'unstable' call for f-electron in the 0.025–0.1 predicted bin was right
                99% of the time [98%, 99%] on 601 calibration structures
why
  - prediction > certified unstable threshold +10 meV/atom (f-electron)
```

**It returns `needs DFT` rather than guess** when the predicted hull distance is above 0.3 eV/atom,
when the relaxation left its starting structure, on the known-weak elements (Be, Pm, Pu, Tc), when the
prediction falls between the certified thresholds or in a chemistry family with none, when the two
engines disagree by more than 165 meV/atom, or when Materials Project has no reference hull for the
chemistry. On the benchmark that is 41 % of candidates; on real chemistry, 82 %.

Contract, refusal rules and a worked example: **[docs/predict.md](docs/predict.md)**.

---

## Setup

macOS on Apple Silicon. Everything installs inside this folder.

```bash
# 1. project-local uv, Python and dependencies
python3 -m venv .tools && .tools/bin/pip install uv
./uvw python install 3.12 && ./uvw sync

# 2. model weights (44 MB; SHA-256 pinned in harness/config.py, verified on every load)
mkdir -p models && curl -L -o models/2023-12-03-mace-128-L1_epoch-199.model \
  https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/2023-12-03-mace-128-L1_epoch-199.model

# 3. Materials Project API key — never committed, never printed
cp .env.example .env   # then paste your key after MP_API_KEY=
```

```bash
./uvw run pytest -m "not slow"   # 222 pass; no API key, no weights, no network needed
                                 # (1 skips until the MP snapshot is cached — harness/unseen.py names it)
./uvw run pytest                 # adds the smoke test — needs steps 2 and 3, skips with a reason otherwise
```

The production engine (MACE-MPA-0) and the WBM data files are larger downloads; see
[docs/predict.md](docs/predict.md) and `harness/suites/ood.py` for the exact URLs and checksums. Run
`./scripts/preflight_publish.sh` before publishing a fork.

## Usage

```bash
./uvw run python -m harness predict --parent mp-2657 --substitute Ti:Zr   # the product
./uvw run python -m harness run --suite all        # the suites (resumable)
./uvw run python -m harness report                 # rebuild reports/validation_report.md
./uvw run python -m harness unseen report          # the unseen-materials test
./uvw run python -m harness polymorph report       # polymorph ranking
```

`HARNESS_MODEL` selects the engine; every job key ends in a hash of model, device, dtype and
relaxation settings, so changing any of them re-runs rather than silently reusing stale numbers.
Longer-running work goes through a queue (`python -m harness prepare`, then `unattended`) — see
`harness/orchestrator.py`.

## Daily routine

```bash
./uvw run python -m harness standup            # one screen: progress + ETA, what finished since last time,
                                               # failures by type, mode/paused, disk, metrics that moved
./uvw run python -m harness standup --verify   # ...plus: both databases open cleanly, queue reconciles with results
```

* **Every morning: `standup`.** Read a new error type under *Failures*, or any metric that moved more
  than 5 % (`standup_metric_threshold` in `config/unattended.json`), before starting more work. Add
  `--verify` weekly, and always after a crash, a power cut or a restore.
* **At the end of a phase** the runner does this itself when a queue drains: `checkpoint` (a local
  git commit of code, reports, `results/schema.sql` and `results/summary.json`, with run ID, model,
  settings tag, job counts and headline metrics in the message; files over 5 MB stay out; nothing is
  pushed), then a backup. By hand: `python -m harness checkpoint "what changed"` (`--dry-run` first).
* **Backups:** `./scripts/backup.sh` writes to `HARNESS_BACKUP_DIR` from `.env`, or `backups/`
  (gitignored). It warns if that is the same physical disk as the project, which the default is:
  point it at an external drive. Every archive is re-read after writing; the newest of each of the
  last 7 days and 4 weeks are kept. Nightly timer (07:30, `schedule.backup`):
  `./scripts/install_schedule.sh backup`, removed with `./scripts/uninstall_schedule.sh backup`.
* **Restore:** `./scripts/restore.sh backups/harness-<stamp>.tar.gz <empty dir>` checks the archive
  checksum, every file against the manifest and every database's integrity, with macOS built-ins only.

## Layout

```
harness/     predict.py (the product), calibration.py (frozen thresholds), hull.py, routing.py,
             confidence.py, engine.py, suites/*.py, report.py, orchestrator.py
data/        frozen inputs: pair sets, the WBM split, the unseen test set, the calibration bundle
reports/     validation_report.md + final_test.md, unseen_test.md, polymorph.md, guard_fix.md,
             leakage_check.md, costs.md, licensing.md, publish_audit.md
docs/        predict.md — the product's contract
results/     results.parquet — the full results table (197,783 rows), plus its data dictionary
```

`cache/`, `models/` and `logs/` are generated and gitignored, as is the rest of `results/` (~1 GB of
SQLite job stores); nothing third-party is redistributed here.

**`results/results.parquet` is committed** — 6.9 MB, zstd, every row behind every number in
`reports/`, so a reader can recompute any table rather than take it on trust.
[results/README.md](results/README.md) is its data dictionary: every column, its units, its
provenance fields, and how to join it back to the tables in
[reports/validation_report.md](reports/validation_report.md).

**Future regenerated versions of `results.parquet` will be attached as GitHub Release assets rather
than recommitted**, so repository history does not grow by ~7 MB on every run. The committed copy is
the one the published reports were computed from.

---

## Round 4: the carried-over families (development evidence)

> **Round 4 and Path-B results are development/calibration results. Unless explicitly identified as
> preregistered held-out results, they must not be interpreted as independent estimates of production
> performance.**

**The experiment.** Three chemistry families — `f-electron`, `intermetallic` and `pnictide` — still
carried decision thresholds fitted on 1,801, 665 and 210 rows. Nothing in two prior rounds had
touched them, and in the rule set the product uses when a second engine is available, only
`f-electron` could return *likely stable* at all. 4,000 fresh development structures were drawn per
family from the never-used pool, then the same 12,000 structures were run again on the second engine
so the disagreement-filtered path could be scored too. 48,000 jobs, zero failures.

**What was learned.**

- **pnictide's empty second-engine rule was a small-sample artefact.** Production gives it
  `stable none / unstable none` from a 202-row fit, which routes **100%** of pnictide candidates to
  DFT. Refitting on 3,501 rows selects `stable = −20 meV`, `unstable = +0 meV` — bounds 0.9128 and
  0.9622 — and those selections survive the family-level correction.
- **Supplying a second engine makes the product worse**, more than doubling the share sent to DFT
  (0.1763 → 0.4069) across these families. Adding information should not cost routing; the cause is a
  stale rule table, not the engines.
- **Most of the apparent gain is sample size, not the second engine.** Fitting the single-engine path
  on the same rows reaches the same threshold in **5 of 6** selections.
- **f-electron lost its stable certification** on a fresh, composition-matched draw: the live rule's
  corrected bound is 0.8944 against a 0.90 target. An apparent second-engine rescue **does not
  survive** the family-level multiplicity correction (bound 0.892556, margin −0.0074).
- **intermetallic gained a stable side** but its unstable margin is only **+0.0039** — flagged, not
  banked.

**What remains unresolved.** Whether f-electron's stable rule is sound (unresolved on *both* paths —
neither sample separates 0.90 from 0.94). Whether pnictide's thresholds hold out of sample (a held-out
test is **pre-registered but not run**; its sample does not exist). Whether one shared rule table or
two is right. Whether any of it generalises off WBM. **Nothing here is adopted in production** — the
active bundle is unchanged, and the pnictide defect is still present.

**Reproducing the published aggregates.**

```bash
python -m harness models fetch mace-mpa-0-medium && python -m harness models fetch mace-mp-0-medium
python -m harness data fetch wbm                      # Matbench Discovery, doi:10.6084/m9.figshare.22715158

HARNESS_MODEL=mace-mpa-0-medium python scripts/round4.py enqueue        # primary engine
HARNESS_MODEL=mace-mp-0-medium  python scripts/round4.py enqueue-second # second engine
./run_unattended.sh full                                                # drain the queue

HARNESS_MODEL=mace-mpa-0-medium python scripts/round4_analyse.py       reports/round4_carried_over.md
HARNESS_MODEL=mace-mpa-0-medium python scripts/round4_second_engine.py reports/round4_second_engine.md
HARNESS_MODEL=mace-mpa-0-medium python scripts/round4_pathb_refit.py   reports/round4_pathb_refit.md
python scripts/build_public_export.py                                   # regenerates results/public/
```

The draw itself (`scripts/round4.py split`) is made once and refuses to regenerate; its committed id
list is what the above reproduces against.

| where | what |
|---|---|
| [`reports/public/round4_development_results.md`](reports/public/round4_development_results.md) | the results, with every negative finding |
| [`results/public/`](results/public/SCHEMA.md) | machine-readable aggregates + documented schema |
| [`docs/methodology/`](docs/methodology/) | statistics, evidence tiers, provenance, environment |
| [`reports/public/WITHHELD.md`](reports/public/WITHHELD.md) | what is deliberately not published, and why |

---

## Data sources and attribution

This project builds on data published by others. Every number in `reports/` is derived from one of
these sources; none of the underlying datasets or model checkpoints is redistributed here — the setup
steps fetch them from their original homes. Full detail, including the licence of every dependency, is
in **[reports/licensing.md](reports/licensing.md)**.

- **Materials Project** — structures, energies and convex hulls, licensed
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Files under `data/` and the tables in
  `reports/` contain values derived from Materials Project data; they are adaptations, and any further
  redistribution must keep this notice.
  A. Jain *et al.*, "Commentary: The Materials Project: A materials genome approach to accelerating
  materials innovation", *APL Materials* **1**, 011002 (2013). doi:10.1063/1.4812323

- **WBM dataset** — H.-C. Wang, S. Botti, M. A. L. Marques, "Predicting stable crystalline compounds
  using chemical similarity", *npj Computational Materials* **7**, 12 (2021).

- **Matbench Discovery** — benchmark and data files, licensed
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). J. Riebesell *et al.*, *Nature Machine
  Intelligence* (2025), arXiv:2308.14920. Data files: doi:10.6084/m9.figshare.22715158.
  `data/mbd_published.json` additionally reproduces published leaderboard metrics from the
  matbench-discovery repository, which is licensed **MIT** (© 2022 Janosh Riebesell); that notice is
  in [NOTICE](NOTICE).

- **MPtrj** — the training set of the engine under test (not used or redistributed here).
  B. Deng *et al.*, *Nature Machine Intelligence* **5**, 1031 (2023). doi:10.6084/m9.figshare.23713842

- **Experimental lattice constants**, transcribed with citations in the file headers:
  R. A. Lucero, T. M. Henderson, G. E. Scuseria, *J. Phys.: Condens. Matter* **24**, 145504 (2012),
  Table I; and G. I. Csonka, J. P. Perdew *et al.*, *Phys. Rev. B* **79**, 155107 (2009), Table II.

- **Interatomic potentials** — MACE-MP-0 and MACE-MPA-0 (MIT), SevenNet-Omni (MIT), eSEN-30M-OAM
  (code MIT; checkpoint under the OMat24 licence, gated on Hugging Face). Checkpoints are downloaded
  by the user and pinned by SHA-256 in `harness/config.py`; none is mirrored here.

Changes were made: all values in `reports/` are computed by this harness from the above sources and
are not the sources' own published numbers.

## Contributing

`./scripts/install_hooks.sh` installs a pre-commit secret scan (~0.7 s per commit; bypass a single
commit with `git commit --no-verify`). Hooks are not cloned, so the same checks run in CI on every
push and pull request via `.github/workflows/secret-scan.yml`, which needs no secret to run. Details
in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Licence

This repository is published under a split licence, because the code and the data are different
kinds of thing and came from different places.

| what | licence | file |
|:--|:--|:--|
| **Code** — `harness/`, `tests/`, `scripts/`, `config/`, root files | **Apache-2.0** | [LICENSE](LICENSE) |
| **Code** — `reference_data/loader.py`, `reference_data/extract/`, `reference_data/tests/` | **Apache-2.0** | [LICENSE](LICENSE) |
| **`data/`** | **CC BY 4.0** | [data/LICENSE](data/LICENSE) |
| **`reports/`** | **CC BY 4.0** | [reports/LICENSE](reports/LICENSE) |
| **`reference_data/`** — CSV tables, `schema/`, prose | **CC BY 4.0** | [reference_data/LICENSE](reference_data/LICENSE) |
| **`results/results.parquet`** | **CC BY 4.0** | [results/README.md](results/README.md) |

Copyright 2026 Isac Smith. Apache-2.0 was chosen over MIT for its express patent grant and its
NOTICE mechanism; CC BY 4.0 matches what the input datasets already are, so the data can be reused
on the same terms it reached us on.

**The CC BY 4.0 grants cover only material this project generated.** Three files in `data/` are
third-party material, are excluded from those grants, and keep their own terms:

- `data/experimental_lattice_constants.csv` — Lucero *et al.* (2012) Table I, © IOP Publishing
- `data/experimental_csonka2009.csv` — Csonka *et al.* (2009) Table II, © American Physical Society
- `data/mbd_published.json` — matbench-discovery model metadata, MIT, © 2022 Janosh Riebesell

`reference_data/raw/` is likewise excluded — it vendors two **public-domain** sources verbatim so
the reference-data build reproduces offline: NASA/TM-2006-214482 (a US Government work) and cached
Crystallography Open Database responses (CC0). Neither is under any grant this project makes; see
[reference_data/LICENSE](reference_data/LICENSE).

[data/README.md](data/README.md) states file by file which data is which, and why each carve-out is
a carve-out. [NOTICE](NOTICE) carries the full attribution block that must travel with any
redistribution. [reports/licensing.md](reports/licensing.md) has the underlying analysis, including
the licence of every dependency.
