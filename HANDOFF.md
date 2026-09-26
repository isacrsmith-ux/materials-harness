# HANDOFF

State transfer for the next session, written 2026-09-26 at the end of the 2026-09-24 campaign. Every
figure was recomputed from the repository at write time, not copied from conversation.

This supersedes the 2026-09-22 handoff (commit `2fbe8c9`). Its "Decisions", "Dead ends" and
"Environment" sections are carried forward below and extended. Its open decision #1 (the f-electron
test) and #4 (external validation, stages 1–2) are done.

**Start with the Verification block at the end.** If anything there disagrees with this document,
trust the repository. The campaign's one-page account is `reports/campaign_20260924_summary.md`.

---

## Goal

A validation harness that measures whether a machine-learned interatomic potential can be trusted to
decide *"is this hypothetical material worth a DFT calculation or a lab attempt?"*. The deliverable is
`harness/predict.py`. It returns `likely stable` / `likely unstable` / `send to DFT`, each backed by a
**certified** error rate rather than a point estimate.

## Evidence tiers (unchanged, still the thing to understand first)

| tier | meaning | what it licenses |
|---|---|---|
| **development / calibration** | thresholds selected on a population and scored on it | nothing |
| **pre-registered held-out** | protocol frozen and committed before the sample is opened; opened once | a production change, on an explicit decision |
| **production-adopted** | what `data/calibration_bundle.json` actually loads | the product's behaviour |

Three held-out evaluations have now been run: **halide** (2026-09-18), **pnictide** (2026-09-19) and
**f-electron** (2026-09-24). `docs/methodology/evidence_tiers.md` is **stale** (see Known issues).

---

## Current state of the product — unchanged by this campaign

`data/calibration_bundle.json`: sha256 `419c11514d6a5485…`, `created_at 2026-09-12T20:21:45+00:00`,
one entry in `promotions[]` (pnictide), no `confirmations[]`. Thresholds are unchanged from the
2026-09-22 handoff table. **Only f-electron and pnictide can return `likely stable`.**

---

## What happened in the 2026-09-24 campaign

### f-electron held-out evaluation — all four hypotheses PASS (tier 2)

- **Opening:** once, at 2026-09-24T19:37:44Z, authorised by Isac Smith on 2026-09-24 (`fe639de`).
- **Scoring:** once, at 21:11:35Z, at the fixed live thresholds −20 / +10 meV (evidence commit `34c40d3`, `reports/felectron_test.md`).
- **Population:** 4,500 drawn, all usable; 3,942 labelable on Path A, 3,847 on Path B. No inconclusive trigger fired.

| id | calls | errors | point | CP-lower @0.9875 | verdict |
|---|---:|---:|---:|---:|---|
| EA1 A stable | 481 | 13 | 0.9730 | 0.9513 | PASS |
| EA2 A unstable | 3,020 | 33 | 0.9891 | 0.9840 | PASS |
| EB1 B stable | 475 | 13 | 0.9726 | 0.9507 | PASS |
| EB2 B unstable | 2,933 | 33 | 0.9887 | 0.9835 | PASS |

Call counts came in within 2.2% of the pre-registered 492 / 3,018 / 482 / 2,921. The held-out bounds
exceed the development bounds (0.9171 / 0.9231) because this test paid only a 4-fold correction, not
the 61 × 6 grid-and-family correction; that is **not** better data.

The pre-registered branch `all_four_pass` says to *record* the confirmation, changing no threshold. That
is prepared and **not run**: `scripts/record_felectron_confirmation.py` refuses without
`--i-have-an-explicit-decision`, and `reports/felectron_confirmation_proposal.md` explains it (`f7d6bec`).

### OQMD external validation, stages 1–2 (no ML) — `4043d5e`

- **Source.** OQMD v1.8 dump (February 2026), licensed CC BY 4.0 as read on oqmd.org on 2026-09-24,
  sha256 `66c3f1b7…` (size and md5 match the published values). Parsed from the MySQL dump without a
  server by `harness/external_oqmd.py`. Nothing raw is committed.
- **Stage 1** (`reports/oqmd_overlap.md`):
  - 1,218,083 usable entries (converged, ordered, ≤ 40 atoms, labelled);
  - **891,982** of them are independent by reduced formula of the MP 2023-01-10 snapshot (an MPtrj superset) and of WBM, including **13,734 fluorides**;
  - the protostructure labeller (matbench-discovery `71633e8b`, ephemeral Python 3.14 env) agrees with WBM's published labels on 0.8920 of 2,000 structures.
  - **Caveat:** Alexandria (sAlex, part of the primary engine's training data) is not checked.
- **Stage 2** (`reports/oqmd_hull_disagreement.md`). On **47,490** materials present in both databases, OQMD's hull and MP's (MP2020 GGA/GGA+U, database version 2026.04.13) put the material on opposite sides at −20 / 0 / +10 / +30 meV for **0.2070 / 0.2553 / 0.1813 / 0.1317** of them. **That is the ceiling on what any OQMD evaluation can mean.**

### OQMD development tier — licenses nothing (`4bbbe76`, `6d234d0`)

- **Lock.** 445,984 held-out ids are locked and **unopened** (`cc8d40f`), registered, formula-guarded against every protected WBM set.
- **Draw.** The frozen plan covers 94,059 development structures (`4411d92`), sized from a 500-structure pilot to about 35 h of compute across both engines.
- **Runs.** Both engines ran over all of them with 0 failures; 93,602 are usable.
- **Prediction.** The product's own mode (a): engine energy on MP's hull, with the row's own formula removed.
- **The live unstable rules hold on OQMD labels:** NPV 0.971–0.998 per family, both paths.
- **The live stable rules do not.** On Path A, f-electron −20 meV has precision **0.389** (298 calls) and pnictide −20 meV **0.519** (212 calls). Even where the two hulls agree within 25 meV at the row's composition, precision is 0.618 (34 calls) and 0.729 (48).
- **Post-hoc check** (`reports/oqmd_development_posthoc.md`). Scoring against OQMD's hull of other compositions only raises precision just to 0.420 and 0.557, so this is **not** mainly a same-formula-sibling artefact. Convention and model **cannot be separated with this data**. Unmeasured candidates include the candidate's own formation-energy convention and OQMD's f-in-core lanthanide potentials. This does not impugn the WBM held-out confirmations, which tested the rules on the labels they were certified against.
- **Development-tier certifiability** (12-fold family × side correction): an unstable threshold *looks* certifiable for intermetallic, oxide, halide, chalcogenide, other and fluoride. **No stable threshold looks certifiable for any of them.**

### Incidents (details in the campaign summary)

- **Commits blocked for about 3 h.** Commits were refused because the driver's state file held absolute paths. The OQMD lock and plan were written before queueing but **committed after** it; the late commits say so. Fixed in `5c59cc5` and `6491460`.
- **OS-update reboot on 2026-09-25.** The campaign resumed by itself, but the reboot **reloaded the nightly agent** (bootout does not persist).
- **An unrelated project's file** appeared in `Claude outputs/`. It was git-ignored and left untouched.

---

## Locked / held-out sets (registry: 9 rows, all hashes verify)

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

**Unspent WBM pool, fully guarded (recomputed 2026-09-26): 140,268.** By family: f-electron 89,273,
intermetallic 33,707, other 7,991, oxide 4,517, chalcogenide 2,092, pnictide 1,523, halide 1,165.
67,273 ids are spent. This is identical to the 2026-09-22 figure, because this campaign drew nothing
from WBM (the f-electron sample was already counted). Rerun the recompute before sizing any draw.

**OQMD held-out available by family:** f-electron 192,604, intermetallic 92,898, oxide 50,526,
chalcogenide 39,732, other 30,532, pnictide 26,516, halide 13,176.

---

## Open decisions — nothing here is mine to make

**(a) Record the f-electron confirmation?** The evidence says all four hypotheses pass. The action changes no threshold, only status and provenance. Review `reports/felectron_confirmation_proposal.md`, then run the script as its own production commit and update the bundle-sha invariant.

**(b) Intermetallic: pre-register or not.** Unchanged since 2026-09-22 (`reports/intermetallic_sizing.md`): the stable side's 4.5% call rate binds. New input: OQMD development finds no certifiable stable threshold for intermetallic either.

**(c) Pre-register an OQMD held-out evaluation, and for which family?** Stage 2 caps what it can mean.
- **Unstable side.** Development suggests any of intermetallic / oxide / halide / chalcogenide / other would pass. Held-out sizes needed at 80% power are 12,723 / 4,627 / 1,464 / 2,620 / 6,536 structures at the development point estimate, and far more at the lower bound. The locked half has enough.
- **Stable side.** Do **not** use OQMD for stable-side claims until the convention question behind the 0.389 / 0.519 precision is resolved, most cleanly with a small MP-settings DFT campaign on a sample of those very candidates.

**(d) Fluoride.** OQMD has 13,734 independent fluorides (about half locked). At the development tier only an unstable +0 meV threshold looks certifiable. At 80% power a held-out test would need 1,330 structures at the point estimate and 25,513 at the lower bound, against 6,928 locked fluorides. The stable fluoride question WBM could not settle remains unanswered, and OQMD's convention problem applies to it too.

Also for a decision: whether to extend the curated public export beyond round 4, and whether to refresh `docs/methodology/evidence_tiers.md` (see Known issues).

---

## Decisions made (do not re-litigate)

Carried forward:
- Labelable rows are authoritative.
- Evidence commits are separate from production commits.
- Historical documents are not retconned.
- A pre-registration is pushed before its sample is drawn.
- Carve-outs need a validity deficit.
- The sulfide half is sealed, not deleted.

New:
- **A confirmation of a live rule is recorded in `confirmations[]`, not `promotions[]`.** Nothing is promoted when the rule is already live.
- **OQMD stage 2 is per material, not per OQMD entry** (one row per formula + protostructure).
- **OQMD development rows are split by the hull shift at the row's own composition,** not by a chemical-subsystem flag, which was degenerate.
- **MP hull placement for bulk evaluations uses the validated bulk index** (`scripts/oqmd_phase3.py mp-bulk`). It must reproduce `hull.mp_competitors` exactly on cached systems, or the report refuses to use it.

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
- use the bisection sizer.

New:
- **Never write absolute paths into a tracked file.** The pre-commit hook scans the whole index, so one staged file blocks every commit. Run state belongs in gitignored files.
- **"File exists" is not "committed".** A step that retries after a failed commit must retry the commit.
- **`launchctl bootout` does not survive a reboot.** Everything in `~/Library/LaunchAgents` reloads at login. An unattended campaign that unloads the nightly agent must re-unload it on every invocation.
- **The queue claims smallest cells first** (`ORDER BY priority` = n_atoms). Early throughput overstates the run. Size from a random pilot's **mean**, not the observed rate.
- **Per-system MP API fetching does not scale** (about 2,300 systems per hour). Use the bulk index.
- **The OQMD protostructure function is not on PyPI** and needs Python ≥ 3.14. Use `./uvw run --python 3.14 --with "matbench-discovery @ git+…@71633e8b"`.
- **MP's terms page sits behind a Cloudflare bot check.** Do not try to bypass it; record it as not re-read.

## Known issues

- `docs/methodology/evidence_tiers.md` still says pnictide is "pre-registered but not run" and the bundle is unchanged since 2026-09-12. It is public and stale. Refreshing it is a decision, not something done unattended.
- The curated public export (`reports/public/`, `results/public/`) covers round 4 only. Its id guard matches WBM ids only; OQMD entry ids are plain integers.
- `results/results.parquet` has grown past the checkpoint's 5 MB limit, so checkpoints no longer update the tracked copy. The committed file is older than the local one.
- The OQMD label reconstruction (formation energy minus the OQMD hull built here) matches OQMD's stored `stability` within 5 meV for 0.8343 of development rows. Some stored labels predate later OQMD entries.
- Carried forward:
  - `reports/round2_results.md` is on the all-usable footing;
  - `data/calibration_spec_v2.json` is frozen and says "NOT yet executed";
  - the registry omits the MP unseen test (n = 325);
  - `scripts/round2_ledger.py` flags the authorised halide opening;
  - the public history contains ids of four unopened WBM halves;
  - 2 failed and 4 timed-out old jobs;
  - backups go to the same disk.

## Environment / configuration

- Apple M4 Max, 14 cores, 36 GB, CPU only; macOS was updated to Darwin 27.0 during the campaign.
- `.venv/bin/python` (3.12) and `./uvw`. Ephemeral deps come via `./uvw run --with`; Python 3.14 is only for the protostructure labeller.
- **`HARNESS_MODEL`:** unset means the *second* engine (`mace-mp-0-medium`, tag `207ccc81`). The production engine is `mace-mpa-0-medium`, tag `c2480e74`.
- **Throughput measured this campaign.** f-electron WBM: 9,000 jobs in 0.93 h (production) and 0.62 h (second). OQMD development: 94,059 structures in 17.6 h (production) and about 23.8 h of AC time (second).
- `cache/external/oqmd/` holds about 21 GB of dump plus intermediates, all gitignored. `cache/external/mp/` holds the bulk index.
- The nightly agent is loaded again and unchanged. The campaign agent is gone.

```bash
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/freeze_spec_v2.py
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m harness status
bash scripts/preflight_publish.sh
```

---

## Verification

```bash
# 1. Repository
git status --porcelain && git log --oneline -1 && git fetch -q && git rev-parse HEAD origin/main

# 2. Tests: expect 344 passed with the env var
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python -m pytest tests/ reference_data/tests/ -q

# 3. Locked sets: expect 9 rows, all hashes ok; f-electron OPENED ONCE; OQMD LOCKED, UNOPENED
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/freeze_spec_v2.py

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

# 6. Agents and publication
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
