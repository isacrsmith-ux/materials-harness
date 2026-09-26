# Campaign 2026-09-24 — summary

Ran from **2026-09-24T19:37Z to 2026-09-26T19:46Z**, about **48.2 h** of wall clock. About **43 h** of that was AC runner compute: 44.9 h of runner steps, minus one 1 h 32 min battery pause (2026-09-25 19:43–21:15Z) and about 16 min lost to an OS-update reboot (~21:43Z). Driven unattended by `scripts/campaign_20260924.py` under the temporary launchd agent `com.materials-harness.campaign`. The nightly agent was restored byte-identical at the end, and the campaign agent unloaded itself.

## What ran

| phase | jobs | failed | wall | outcome |
|---|---:|---:|---:|---|
| 1 · f-electron held-out, production engine | 9,000 | 0 | 0.93 h | drained |
| 1 · f-electron held-out, second engine | 9,000 | 0 | 0.62 h | drained |
| 2 · OQMD v1.8 download, normalise, protostructures, stages 1–2 | — | — | ~0.3 h (+ 17 min download) | done |
| 3 · OQMD pilot, production engine | 500 | 0 | 0.15 h | drained |
| 3 · OQMD development, production engine | 93,559 | 0 | 17.6 h | drained |
| 3 · OQMD development, second engine | 94,059 | 0 | 25.6 h | drained (incl. pause + reboot) |
| 3 · development report | — | — | 0.5 h | committed `4bbbe76` |

## Verdicts and findings

- **f-electron held-out (pre-registered, tier 2): all four hypotheses PASS.** CP-lower @0.9875: EA1 0.9513, EA2 0.9840, EB1 0.9507, EB2 0.9835. No inconclusive trigger fired. Evidence commit `34c40d3`. The confirmation script is prepared, **not run** (`f7d6bec`).
- **OQMD stage 1:** 891,982 of 1,218,083 usable entries are independent of the MP 2023-01-10 snapshot and of WBM, including 13,734 fluorides.
- **OQMD stage 2:** on 47,490 materials present in both databases, the two hulls put the material on opposite sides at −20 / 0 / +10 / +30 meV for 0.2070 / 0.2553 / 0.1813 / 0.1317 of them.
- **OQMD held-out half:** 445,984 ids, **LOCKED, UNOPENED** (`cc8d40f`).
- **OQMD development (tier 1, licenses nothing):**
  - The unstable sides of the live rules hold on OQMD labels: NPV 0.971–0.998.
  - The two live **stable** rules do not: precision 0.389 (f-electron) and 0.519 (pnictide) on Path A.
  - A post-hoc check (`6d234d0`) shows this is mostly **not** a same-formula-sibling artefact. Convention and model cannot be separated with this data.
  - Development-tier unstable thresholds *look* certifiable for intermetallic, oxide, halide, chalcogenide, other and fluoride. No stable threshold looks certifiable for any of them.

## Things that went wrong, and what was done

1. **Commits blocked for about 3 h.** The driver wrote absolute paths into its state file, a runner checkpoint staged it, and the preflight pre-commit hook then refused every commit. As a result:
   - the f-electron evidence commit failed;
   - the lock, pilot and plan steps retried and treated "file exists" as "committed". **The OQMD lock and plan were written before queueing but committed after it.**

   The files are unchanged since they were written, and the late commits say so (`cc8d40f`, `f8369a5`, `4411d92`). Fixes: `5c59cc5` untracks and sanitises the state file; `6491460` makes a step still ensure its commit when the file exists.
2. **The first stage-2 figures were per OQMD entry.** Duplicate entries of one material inflated them. Regenerated per material (`ec56c06`) before commit.
3. **The development report's first split was degenerate** (99.7% of rows in one class). Replaced, before the full run, by the hull shift at each row's composition (`1db501c`).
4. **The per-system MP hull prefetch would have taken ~27 h.** Replaced by one bulk index validated against the product path on 60 systems (`e02d179`).
5. **An OS-update reboot reloaded the nightly agent**, because `launchctl bootout` does not persist. It was unloaded again by hand. It was harmless: the campaign runner held the queue lock, and only second-engine jobs were pending.
6. **An unrelated file from another project** appeared in `Claude outputs/`. It was left in place and git-ignored so a checkpoint cannot publish it.

## Refused or not done, and why

- **No change to `data/calibration_bundle.json`** (sha256 still `419c11514d6a5485…`). The f-electron confirmation needs its own decision.
- **Intermetallic not pre-registered or drawn.** Your decision #2 was "not in this campaign".
- **Pnictide and every other locked set untouched.**
- **No OQMD evaluation pre-registered**, and the held-out half was not opened.
- **Materials Project licence not re-read.** The terms page was behind a Cloudflare bot check, which was not bypassed; this is recorded in `docs/methodology/data_provenance.md`.
- **Stretch (post-2023 MP materials) skipped.** Phase 3 used the compute budget, and the result above makes a same-convention replication a lower priority than resolving the OQMD convention question.
- **Public export not extended.** It still covers round 4 only. Adding campaign aggregates needs its own id guard, because OQMD ids are plain integers the current guard does not catch.
