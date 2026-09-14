# Pre-publication audit

Audit of this repository before it is made public on GitHub. **Nothing here was published, pushed, or
given a remote**, and no history was rewritten — every decision that is the owner's is listed at the
end, unmade.

Audited at commit `82a77c1` on branch `round2`; 28 commits across 2 branches (`main`, `round2`),
127 tracked files, 0 tags, 0 stash entries.

---

## 1. Credential and secret sweep

### Tools

Neither `gitleaks`, `trufflehog`, `detect-secrets`, `brew` nor `pipx` was installed on this machine.
Two scanners were obtained without touching the project's locked environment:

| tool | version | how | what it covered |
|:--|:--|:--|:--|
| **gitleaks** | 8.30.1 | binary release, run from a scratch directory | full git history (`--log-opts="--all --full-history"`) and the working tree |
| **detect-secrets** | 1.5.0 | `uv tool run` (isolated, not added to `uv.lock`) | available as a cross-check |
| bespoke Python sweep | — | 23 credential patterns + suspicious-filename rules | every object in the object database, and 34,035 working-tree files including caches |

### What was covered, explicitly

* **All 28 commits on all 2 branches**, not the first 50 or the current tip.
* **All 437 objects in the object database**, of which **277 are blobs** — this is a superset of
  "every file in every commit", because it includes objects no ref points at.
* **Unreachable / dangling blobs: 0.** Every blob is reachable from a ref, so nothing is hiding in a
  deleted branch.
* **Reflog: 58 entries reaching 28 distinct commits, all of which are already on refs** — the reflog
  can reach nothing the history scan missed.
* **Working tree: 34,035 files**, tracked *and* untracked, including `cache/` (428 MB of cached
  Materials Project responses), `cache/external/` (171 MB of WBM/MP data files), `results/`, `logs/`
  and `models/`.
* Patterns searched: OpenAI, Anthropic, Google/Gemini, **Hugging Face (`hf_…`)**, Cohere/Mistral/
  together.ai, GitHub PATs and App keys, AWS access keys, GCP service-account JSON, Azure account
  keys, Slack, Stripe, SendGrid, npm `_authToken`, PyPI tokens, `BEGIN … PRIVATE KEY` blocks, JWTs,
  database connection strings with embedded passwords, **URLs carrying `user:password@host`**,
  **tokens in query strings**, `MP_API_KEY` assigned a value, and generic
  `password|secret|client_secret|access_token|refresh_token = "…"` assignments.
* Filenames searched: `.env` and every `.env.*` flavour, `id_rsa`, `id_ed25519`, `id_ecdsa`, `*.pem`,
  `*.p12`, `*.pfx`, `*.keystore`, `*.jks`, `service-account*.json`, `terraform.tfvars`, `kubeconfig`,
  `.npmrc`, `.pypirc`, `.netrc`, `credentials`.

### Result: nothing to rotate, nothing to rewrite

**Git history (all refs, all objects, reachable and not): 0 secrets of any kind.**

| check | result |
|:--|:--|
| MP_API_KEY value anywhere in git history | **0 blobs** (searched by exact value, all 277 blobs) |
| MP_API_KEY value in the working tree | **1 file: `.env`** — gitignored, never tracked, never in history |
| `.env` (any flavour) in history | **no** — only `.env.example`, which holds empty placeholders |
| Hugging Face token (`hf_…`) anywhere | **none.** The gated eSEN checkpoint was fetched without leaving a token in the repo |
| private key blocks, cloud creds, PATs, JWTs, DB strings | **none** |
| URLs with embedded credentials or tokens in query strings | **none.** The Materials Project and figshare download URLs carry no credentials — MP auth is a header supplied by `MPRester`, and the figshare files are public `ndownloader` links |

**gitleaks reported exactly one finding in history, and it is a false positive.** Rule
`generic-api-key`, `tests/test_mp_data.py:16`, commit `7ff64b1`. The matched string is
`MP2020Compatibility` inside a code comment — a long mixed-case token that trips the generic entropy
rule. No action.

gitleaks' working-tree scan additionally flags ~40 strings inside `.uv-cache/` — vendored
`torch`, `huggingface_hub`, `pyarrow` and `hydra` source (`cpp_kernel_key`, `tgt_key_padding_mask`,
`HF_DEVICE_CODE_OAUTH_CLIENT_ID`, …). All false positives in third-party code, and `.uv-cache/` is
gitignored and never published.

### One thing I did that you should know about

While running the sweep, my own script printed a **13-character prefix of the live `MP_API_KEY`**
(`MP_API_KEY=` plus the first 13 of 32 characters) into the session transcript, because the pattern
matcher echoed a truncated match. The full key was never printed and never left `.env`.

* **Risk: low.** 19 of 32 characters are still unknown; brute force is not practical.
* **Recommendation anyway: rotate it.** It costs a minute, and the value of this audit is that you do
  not have to reason about how low "low" is. Rotation steps are in §7.

---

## 2. Personal and environment information

| check | result |
|:--|:--|
| absolute local paths (`/Users/…`, `/home/…`, `C:\Users\…`) in tracked files | **0 files** |
| email addresses inside tracked files | **none** |
| hostnames, machine names, `.local` addresses | **none** |
| private/local IP addresses | **none** |
| `config/launchd/` tracked | **no** — gitignored (it would contain absolute paths) |
| `logs/` tracked | **no** — gitignored |

Hardware descriptions that *are* published, and should stay: the report headers carry
`Apple M4 Max · macOS 26.6.2` and `config/compute*.json` carries `"chip": "Apple M4 Max"`,
`"model": "Mac16,6"`, core counts and memory. These are provenance — a reader cannot interpret a
runtime or a worker layout without them — and none of it identifies a person or a machine on a
network.

### Commit author identity — your decision, not mine

All **28 commits** (author *and* committer) carry the personal Gmail address currently in
`git config user.email`. Publishing makes that address public and permanently associated with the repository. Every commit also carries a
`Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` trailer.

**To use a GitHub noreply address for future commits** (nothing is rewritten):

1. On GitHub: *Settings → Emails →* tick **Keep my email addresses private**. GitHub shows you your
   noreply address, of the form `<id>+<username>@users.noreply.github.com`.
2. In this repository:
   ```bash
   git config user.email "<id>+<username>@users.noreply.github.com"
   ```
   (`git config --global user.email …` if you want it everywhere. Your global is currently unset, so
   only this repo's local config is in play.)

**What rewriting the 28 existing commits would cost.** It is possible
(`git filter-repo --mailmap`, or `--commit-callback`), but:

* every commit SHA changes, so anything that referenced an old SHA — including the SHAs quoted inside
  `reports/validation_report.md` (`commit 0a2c263`) and this audit — becomes wrong;
* it must happen **before** the first push, or every clone keeps the old history;
* the reports' internal provenance would have to be regenerated to match, which means re-running the
  report writers.

Since the repository has never been pushed, this is the only cheap moment to do it. **Not done — it
is your call.** A middle option: leave history as it is (the address is already in your public git
identity elsewhere) and only change the address going forward.

---

## 3. What ships and what does not

### Nothing large or private is tracked

| directory | tracked files | published? |
|:--|--:|:--|
| `results/` (1.0 GB) | **0** | no |
| `models/` (checkpoints) | **0** | no |
| `cache/` (599 MB: MP responses + WBM data files) | **0** | no |
| `logs/` | **0** | no |
| `config/launchd/` | **0** | no |
| `.envs/`, `.venv/`, `.tools/`, `.uv-cache/`, `.uv-python/` | **0** | no |

Tracked content is 127 files across `harness/` (41), `tests/` (27), `data/` (21), `reports/` (16),
`config/` (10), `scripts/` (4) plus the root files.

### Largest tracked files

| file | size | keep? |
|:--|--:|:--|
| `data/unseen_test_run.json` | 1.89 MB | see below |
| `data/auto_pairs.json` | 1.80 MB | yes — the pair set the reports are computed on |
| `data/auto_pairs_v1.json` | 1.31 MB | superseded round-1 pair set; keep only if you want the history |
| `data/unseen_test.json` | 0.35 MB | yes — the frozen, hashed test set |
| `data/polymorph_sets.json` | 0.29 MB | yes |
| `data/wbm_split.json` | 0.14 MB | yes — the calibration/test split, needed to verify the locked-set claim |

`data/unseen_test_run.json` is the raw output of the one-time unseen run: 325 predictions, each with
the relaxed structure as a CIF. It is the evidence that the set was opened exactly once and that the
reported numbers come from those predictions. It is worth publishing for that reason, and 1.89 MB is
not a burden.

### `results/results.parquet` — recommendation: publish it, uncompressed size is not the problem

`results/` is 1.0 GB, almost all of it SQLite (`results.sqlite` 592 MB, queue databases, snapshots).
None of it is tracked. But the exported table is small once recompressed:

| form | rows | columns | size |
|:--|--:|--:|--:|
| `results/results.parquet` as written today | 196,639 | 19 | 18.6 MB |
| same table, re-written with zstd | 196,639 | 19 | **8.82 MB** |
| …dropping the `settings` blob column | 196,639 | 18 | 8.36 MB |
| …dropping `settings` and `flags` | 196,639 | 17 | 6.94 MB |

The `structure` column is a human label (`"Si->Ge (mp-149 -> mp-32)"`), **not** a serialised
structure — nothing large is embedded. The size is dominated by two JSON blob columns, `settings`
(114 M characters, only 5,685 distinct values across 196,639 rows) and `flags`.

**Recommendation: commit the full table recompressed with zstd — 8.82 MB, well under the ~25 MB line,
no trimming and therefore no judgement calls about what a reader is allowed to check.** Dropping
`settings` saves 0.5 MB and costs reproducibility, which is a bad trade. A GitHub Release asset is
unnecessary at this size.

*(Not done — this adds a file to the repository, which is a publication decision. §7 has the command.)*

---
## 4. Licensing and attribution

Written up in full in **[`reports/licensing.md`](licensing.md)**. Summary:

| item | status |
|:--|:--|
| Materials Project data (CC BY 4.0) — we redistribute derived values in `data/` and `reports/` | ❌ **attribution was missing**; a NOTICE block is now in the README |
| WBM / Matbench Discovery (CC BY 4.0) — we redistribute ids only, not the data files | ❌ same gap, same fix |
| MPtrj (MIT) — never downloaded, never redistributed | ✅ |
| Experimental tables (Lucero 2012, Csonka 2009) — transcribed with citations | ✅ cited; the closest judgement call in the document, discussed in `licensing.md` §1.4 |
| Model checkpoints — URL + SHA-256 only, `models/` gitignored, gated eSEN not mirrored | ✅ |
| Dependencies — nothing vendored; **ASE is LGPL-2.1-or-later**, everything else permissive | ✅ for this repo; matters if the commercial product ever *bundles* ASE |
| A licence for this project's own code | ❌ **none chosen — yours to pick**, options in `licensing.md` §5 |

## 5. Honesty of the public claims

**The dated run directories are already not published.** `.gitignore` carries `reports/[0-9]*/`, so the
20 `reports/2026…/` directories are untracked and will not appear in the repository. The premise of
the request does not hold for the published set — but the tracked reports were checked individually
and stamped where needed.

| tracked report | vintage | action |
|:--|:--|:--|
| `validation_report.md`, `final_test.md`, `unseen_test.md`, `polymorph.md`, `guard_fix.md`, `leakage_check.md`, `phase3/*` | at or after the guard fix (`1ad6ba3`) | current — no stamp |
| `mace-mp-0-medium/validation_report.md` | post-guard (3,993 usable / 7 rejected — matches `guard_fix.md` §5b), but **not the production engine** | ✅ **banner added**: "This is not the production engine." |
| `phase0/phase0_report.md` | 2026-09-10, **predates the energy-plausibility guard** | ✅ **banner added**: superseded, do not quote as a current result, kept as the record of what Phase 0 fixed |
| `costs.md` | current, but every figure is conditional on placeholder costs | ✅ **warning added** naming the 1:1 placeholders |

Both banners are emitted by the **generators** (`harness/report.py`, `harness/phase0.py`,
`harness/costs.py`), not pasted into the files, so regenerating a report cannot silently drop them.
Verified: the banner appears on the baseline report and **not** on the production one, and
regenerating the production report changes nothing else.

**SevenNet-Omni.** `reports/phase3/screening.md` already carries the caveat inline, and
`reports/leakage_check.md` concludes "probably real but not certified … do not adopt this engine".
The README states the same and says it is not adopted. Nothing published implies more.

**README claims.** Every figure in the rewritten README is a pessimistic bound and links to the
report section it comes from. Checked line by line against `validation_report.md` §5/§9/§10,
`final_test.md`, `unseen_test.md` §4b/§5/§6/§7, `polymorph.md` and `leakage_check.md`.

## 6. Reproducibility — cloned and followed from scratch

The repository was cloned into a temporary directory with `git clone --no-local`, so the clone has
**no** `.env`, `cache/`, `models/`, `results/`, `logs/`, `.venv/` or `.tools/` — exactly what a
stranger gets.

| README step | result |
|:--|:--|
| 1. `python3 -m venv .tools && .tools/bin/pip install uv` | ✅ uv 0.12.13 |
| 2. `./uvw python install 3.12 && ./uvw sync` | ✅ resolved and installed from `uv.lock` |
| 3. `./uvw run pytest -m "not slow"` | ✅ **221 passed, 1 skipped** (the skip says "MP snapshot not downloaded") |

**Two real bugs were found by doing this, and both are fixed.**

1. **`pytest` (the full run) looked broken in a fresh clone**: 2 failures and 7 errors, all
   `MissingAPIKey` or missing weights. Honest exceptions, but indistinguishable from a broken
   repository. Added **`tests/conftest.py`**, which skips every `slow` test when the API key or the
   weights are absent and names the README step that is missing. A fresh clone now reports
   *"221 passed, 13 skipped"* instead of errors, and where setup *is* complete the slow tests still
   run.

2. **A test-isolation bug that was hiding a broken assertion.** `tests/test_registry.py` called
   `monkeypatch.delenv("HARNESS_MODEL")` and then `importlib.reload(config)`, which rebinds
   `config.ACTIVE_MODEL` **for the rest of the session** — discarding the engine the caller had
   selected. Because `test_registry` sorts before `test_smoke`, the full suite always ran the smoke
   test against the baseline engine, which made `tests/test_smoke.py::test_settings_recorded` pass
   despite hardcoding `"MACE-MP-0 medium"`. Running `pytest -m slow` alone (which deselects
   `test_registry`) exposed it. Fixed both ends: the registry tests now restore the caller's
   `HARNESS_MODEL`, and the smoke test asserts against the active registry entry.

   *This is exactly the class of defect a published repository should not ship: the full suite was
   green for the wrong reason.*

**Test counts after the fixes** — `pytest -m "not slow"` 223 passed; full run 235 passed with the
production engine, 232 passed / 3 skipped with the default; `pytest -m slow` 12 passed (was 1 failed).

## 7. Go / no-go checklist

### Blocking — nothing

No secret, key, token, private key or credentialed URL exists anywhere in the working tree, the
staged set, any branch, the reflog, or any of the 437 objects in the database. There is **nothing to
rotate and no reason to rewrite history**.

### Do before publishing (mine to hand you, yours to run)

| # | action | why |
|:--|:--|:--|
| 1 | **Choose a licence** and add `LICENSE`. Consider code Apache-2.0 + `data/` and `reports/` CC BY 4.0 | without one, "public" grants no reuse rights at all — `licensing.md` §5 |
| 2 | **Decide the commit email**: keep the personal address in the 28 existing commits, or rewrite before the first push | after the first push, rewriting stops helping — `publish_audit.md` §2 |
| 3 | **Rotate the Materials Project API key** | a 13-character prefix reached this session's transcript. Low risk; rotation is a minute. <https://next-gen.materialsproject.org/api> → regenerate, then update `.env` |
| 4 | **Decide whether to ship `results/results.parquet`** (8.82 MB recompressed, all 196,639 rows) | it lets a reader check every number; §3 has the command |
| 5 | **Review the new files and the two banners** | committed locally on `round2`; nothing pushed |

### Optional

| # | action |
|:--|:--|
| 6 | Install the preflight as a pre-commit hook (**not installed — asking first**): `ln -s ../../scripts/preflight_publish.sh .git/hooks/pre-commit` (it accepts `--staged`) |
| 7 | Install `gitleaks` locally so the preflight's history scan runs rather than reporting itself skipped |
| 8 | Drop `data/auto_pairs_v1.json` (1.31 MB, superseded round-1 pair set) if you do not want the history |
| 9 | Replace the two experimental CSVs with a reconstruct-from-paper script if you want zero transcription risk (costs reproducibility — `licensing.md` §1.4) |

### Verified clean — no action

* Secrets: all commits, all branches, all 437 objects, reflog, working tree, untracked files, caches.
* No absolute local paths, emails, hostnames or private IPs in tracked content.
* `results/` (1.0 GB), `models/`, `cache/` (599 MB), `logs/`, `config/launchd/`, `.envs/`, `.venv/`:
  zero tracked files.
* `.gitignore` hardened with key, certificate, database and scratch patterns; **no currently tracked
  file becomes ignored** by the additions.
* `scripts/preflight_publish.sh` added and **tested against planted secrets** — an Anthropic key, a
  Hugging Face token, a Postgres URL with a password and an absolute path were all caught, and the
  script returns to OK once they are removed.
* A fresh clone sets up and passes its fast tests from the README alone.

### What was deliberately not done

No remote was added, nothing was pushed, no visibility setting was touched, no history was rewritten,
no licence was chosen, no report was deleted, and the two experimental data files were left in place.

---

*Audit performed against commit `82a77c1`; its own changes are committed locally on `round2` and have not been pushed.*
