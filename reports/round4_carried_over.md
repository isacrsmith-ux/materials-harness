# Round 4 — re-measuring the three carried-over families

Generated 2026-09-18T23:39:53+00:00. Engine MACE-MPA-0 medium, settings_tag `c2480e74`. Development only: **no locked half was opened, and none was reserved.** Nothing here writes a bundle, changes a threshold or promotes anything.

Draw: `data/wbm_split_round4.json`, created 2026-09-18T22:57:33+00:00, seed 20260920, all-ids sha256 `8e67815d048720beb50625ae211ab5e2c0cce5dbf0ec28cbd5d548cce1915e9a`. 42,473 prior ids and 11,874 locked test ids excluded by id; 4,977 further candidates dropped for sharing a reduced formula with a locked test id.

Certification is on **labelable** rows — usable, and surviving the weak-element and structure-change exclusions. That is the population `calibration.fit()` takes and the population production labels. All-usable figures follow as a secondary diagnostic only.

Round 4 ran one engine, so every figure corresponds to the bundle's `without_second_engine` rule set. The `with_second_engine` path is **not** evaluated here.

## 1. Population, and everything that was excluded

| family | drawn | guard-rejected | usable | not labelable | **labelable** | failed jobs | jobs not yet run |
|---|---:|---:|---:|---:|---:|---:|---:|
| f-electron | 4,000 | 0 | 4,000 | 505 | **3,495** | 0 | 0 |
| intermetallic | 4,000 | 0 | 4,000 | 387 | **3,613** | 0 | 0 |
| pnictide | 4,000 | 0 | 4,000 | 363 | **3,637** | 0 | 0 |

Guard rejections and non-labelable rows are excluded from certification and counted here; nothing was filtered out silently.

## 2. Certification on labelable rows — the authoritative result

| family | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall | stable lost | to DFT | stable-side verdict |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| **f-electron** | 3,495 | 0.185 | none | - | - | +0 meV | 0.9747 | 0.9640 | 0.000 | 0.110 | 0.196 | sample-size limited |
| **intermetallic** | 3,613 | 0.097 | -20 meV | 0.9780 | 0.9197 | -10 meV | 0.9658 | 0.9548 | 0.506 | 0.327 | 0.018 | certified |
| **pnictide** | 3,637 | 0.139 | -20 meV | 0.9608 | 0.9128 | +0 meV | 0.9740 | 0.9638 | 0.583 | 0.163 | 0.049 | certified |

`CP-lower` is the one-sided Clopper-Pearson bound at 0.95, Bonferroni-corrected over the 61-point threshold grid, so picking the best threshold keeps the guarantee. A threshold is certified only when that bound clears the target (0.90 precision, 0.95 NPV); the verdict is read from the bound, never the point estimate.

## 3. Stable-side diagnosis — sample-size limited or precision limited?

| family | best t | n selected | point | CP-lower | verdict | more calls needed | structures needed |
|---|---|---:|---:|---:|---|---:|---:|
| f-electron | -40 meV | 292 | 0.9521 | 0.8994 | sample-size limited | 308 | 3,687 |
| intermetallic | -40 meV | 87 | 1.0000 | 0.9216 | certified | - | - |
| pnictide | -30 meV | 236 | 0.9788 | 0.9308 | certified | - | - |

## 4. What this changes against the active bundle

The active v1 bundle's thresholds for these three families were fitted on the original 4,000-id calibration set. Both rule sets are shown; round 4 can only speak to the second.

| family | v1 with-2nd-engine | v1 without-2nd-engine | v1 n | round-4 n | round-4 stable t | round-4 unstable t |
|---|---|---|---:|---:|---|---|
| f-electron | -20 meV / +10 meV | -20 meV / +10 meV | 1,801 | 3,495 | none | +0 meV |
| intermetallic | none / +0 meV | none / +0 meV | 665 | 3,613 | -20 meV | -10 meV |
| pnictide | none / none | none / +50 meV | 210 | 3,637 | -20 meV | +0 meV |

Read as `stable / unstable`. `none` means the family has no rule on that side, so every candidate on that side is sent to DFT.

### Routing the same labelable rows two ways

Left: the active `without_second_engine` thresholds applied to the round-4 draw — what production does today on this population. Right: the round-4 certified thresholds. Same rows, same engine, same labelable filter; only the rule changes.

| family | rule | called stable | precision | CP-lower | called unstable | NPV | CP-lower | recall | to DFT |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| f-electron | v1 (today) | 441 | 0.9388 | 0.8944 | 2,657 | 0.9868 | 0.9783 | 0.641 | 0.114 |
| f-electron | round 4 | 0 | - | - | 2,809 | 0.9747 | 0.9640 | 0.000 | 0.196 |
| intermetallic | v1 (today) | 0 | - | - | 3,251 | 0.9843 | 0.9762 | 0.000 | 0.100 |
| intermetallic | round 4 | 182 | 0.9780 | 0.9197 | 3,365 | 0.9658 | 0.9548 | 0.506 | 0.018 |
| pnictide | v1 (today) | 0 | - | - | 2,502 | 0.9976 | 0.9927 | 0.000 | 0.312 |
| pnictide | round 4 | 306 | 0.9608 | 0.9128 | 3,154 | 0.9740 | 0.9638 | 0.583 | 0.049 |

## 4b. Are the two populations comparable? (read before section 4)

The active v1 thresholds were fitted on the original 4,000-id calibration set, which was stratified by hull bin across **all families at once**. The round-4 draw is stratified per-bin proportional to **each family's own share of the remaining pool**. These are therefore not the same population, and a precision difference between them can be composition rather than validity. Both compositions are given so the two can be told apart.

| family | set | n | base rate | <0 | 0–0.025 | 0.025–0.1 | 0.1–0.3 | >0.3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| f-electron | original (v1 fit) | 1,801 | 0.1866 | 0.187 | 0.112 | 0.310 | 0.299 | 0.092 |
| f-electron | round 4 | 3,495 | 0.1848 | 0.185 | 0.110 | 0.304 | 0.303 | 0.098 |
| intermetallic | original (v1 fit) | 665 | 0.0842 | 0.084 | 0.098 | 0.284 | 0.353 | 0.180 |
| intermetallic | round 4 | 3,613 | 0.0974 | 0.097 | 0.101 | 0.286 | 0.358 | 0.157 |
| pnictide | original (v1 fit) | 210 | 0.1286 | 0.129 | 0.095 | 0.276 | 0.371 | 0.129 |
| pnictide | round 4 | 3,637 | 0.1386 | 0.139 | 0.084 | 0.258 | 0.386 | 0.134 |

Where the base rates differ materially, treat section 4's left-hand column as *what the v1 rule does on the round-4 population*, not as a restatement of the v1 certification. The v1 certification stands on its own population and is not revised here.

## 5. All-usable footing — secondary diagnostic only

Not a certification basis. Retained because the gap between the two footings is itself a measurement of how much the structure-change and weak-element exclusions are doing.

| family | n | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall | to DFT |
|---|---:|---|---:|---:|---|---:|---:|---:|---:|
| f-electron | 4,000 | none | - | - | +0 meV | 0.9753 | 0.9654 | 0.000 | 0.200 |
| intermetallic | 4,000 | none | - | - | -10 meV | 0.9682 | 0.9581 | 0.000 | 0.066 |
| pnictide | 4,000 | -20 meV | 0.9534 | 0.9044 | +0 meV | 0.9756 | 0.9663 | 0.585 | 0.048 |

## 6a. Does the ACTIVE rule replicate on a fresh matched population?

For every family where v1 already has a stable-side rule, that rule is applied unchanged to both populations. The two samples are **never pooled**: pooling a fitting population with a fresh one yields a number that is neither, and would convert a failed replication into a tuned threshold. Same reasoning as the two fluoride R1 measurements.

**f-electron**, v1 rule stable -20 meV:

| sample | labelable | called stable | correct | point | CP-lower | clears 0.90? |
|---|---:|---:|---:|---:|---:|---|
| original (v1 fit population) | 1,801 | 206 | 199 | 0.9660 | 0.9063 | **yes** |
| round 4 (fresh, disjoint) | 3,495 | 441 | 414 | 0.9388 | 0.8944 | **no** |

Difference +0.0272 (SE 0.0188, z 1.45, two-sided p 0.148). The two samples are not statistically distinguishable — this note is descriptive and settles nothing.

**intermetallic** — v1 has no stable rule for this family to replicate

**pnictide** — v1 has no stable rule for this family to replicate

This is DEVELOPMENT data. It cannot revise the v1 certification, no threshold may be refitted to rescue a bound that fell, and nothing here is grounds for a change on its own.

## 6. What pool is left, and what it could support

| family | drawn here | left unspent and still eligible |
|---|---:|---:|
| f-electron | 4,000 | 101,134 |
| intermetallic | 4,000 | 33,707 |
| pnictide | 4,000 | 5,432 |

Every id drawn here is now spent and is **no longer eligible as independent held-out data**. The exact id sets and their sha256 hashes are in `data/wbm_split_round4.json`; per-family hashes are listed in section 7.

## 7. Provenance

| family | calibration ids | sha256 |
|---|---:|---|
| f-electron | 4,000 | `c00f2bfe4ac1257e5efecbdcd810a2f86be169466288f70781bcefa12c64e033` |
| intermetallic | 4,000 | `c92b8c1007087821fd257428ee2b9e46bce7535a88006186d39b68103bc5c6fd` |
| pnictide | 4,000 | `c6682a9575c60c56de4a63e85d03df5fe05f9d177a174f60eef176b64b6caf3b` |

All ids together: `8e67815d048720beb50625ae211ab5e2c0cce5dbf0ec28cbd5d548cce1915e9a`.

