# OQMD overlap — stage 1 of the external-validation design

Generated 2026-09-24T22:22:08+00:00 from the pinned OQMD v1.8 dump, sha256 66c3f1b752d4043b579e84485fe6c8e1913af52f41fc1a949c598e94b6646333. Every number is computed from that dump; no row is redistributed (row-level flags stay in gitignored `cache/external/oqmd/`).

**What 'independent' means here.** An OQMD entry is independent when its reduced formula appears neither in the Matbench Discovery MP snapshot of 2023-01-10 (n=154,718, sha256 `046814c1c556e0e5…`), a proven superset of MPtrj and so of both engines' MP training data, nor in WBM (n=256,963). A protostructure label includes the elements, so a protostructure match implies a formula match: the protostructure columns say how many overlaps are *the same material*, and they are what stage 2 compares. Alexandria (the primary engine's other training source) is not checked here and cannot be, without redistributing it; see the caveat below.

## Filters

| step | entries |
|---|---:|
| entries in dump | 1,407,285 |
| entries with a standard fit label | 1,259,568 |
| has structure | 1,259,560 |
| and converged | 1,259,560 |
| and ordered | 1,259,560 |
| and le 40 atoms | 1,218,083 |
| usable | 1,218,083 |
| structures written | 1,218,083 |

## Overlap and the independent pool, per family

| family | usable | same formula in MP snapshot | same formula in WBM only | same protostructure as an MP material | same protostructure as a WBM entry | **independent** | independent, anonymous prototype seen in MP |
|---|---:|---:|---:|---:|---:|---:|---:|
| f-electron | 509,062 | 53,649 | 70,203 | 20,529 | 35,297 | **385,210** | 282,572 |
| intermetallic | 264,193 | 35,836 | 42,560 | 8,756 | 19,178 | **185,797** | 161,765 |
| oxide | 141,566 | 27,445 | 13,068 | 10,516 | 6,056 | **101,053** | 62,196 |
| halide | 45,132 | 12,378 | 6,400 | 5,074 | 4,922 | **26,354** | 18,522 |
| chalcogenide | 102,393 | 11,792 | 11,134 | 4,199 | 4,341 | **79,467** | 40,265 |
| pnictide | 72,679 | 10,392 | 9,252 | 3,585 | 4,730 | **53,035** | 37,508 |
| other | 83,058 | 10,642 | 11,350 | 3,678 | 5,161 | **61,066** | 50,112 |
| ALL | 1,218,083 | 162,134 | 163,967 | 56,337 | 79,685 | **891,982** | 652,940 |

### Independent pool by OQMD hull-distance bin (eV/atom)

| family | <0 | 0–0.025 | 0.025–0.1 | 0.1–0.3 | >0.3 |
|---|---:|---:|---:|---:|---:|
| f-electron | 25,927 | 46,065 | 45,960 | 75,114 | 192,144 |
| intermetallic | 7,882 | 8,667 | 13,980 | 34,294 | 120,974 |
| oxide | 3,190 | 5,196 | 16,879 | 33,376 | 42,412 |
| halide | 2,700 | 4,112 | 7,223 | 6,738 | 5,581 |
| chalcogenide | 2,713 | 5,901 | 14,418 | 35,502 | 20,933 |
| pnictide | 3,097 | 3,609 | 5,052 | 11,588 | 29,689 |
| other | 3,014 | 3,317 | 4,980 | 11,357 | 38,398 |
| ALL | 48,523 | 76,867 | 108,492 | 207,969 | 450,131 |

Independent **fluorides** (any compound containing F, any family): **13,734**; by bin <0: 1,419, 0–0.025: 1,531, 0.025–0.1: 3,430, 0.1–0.3: 4,027, >0.3: 3,327.

## Labeller check

Protostructure labels come from `get_protostructure_label` at matbench-discovery@71633e8bdfdfd41d56d64b1d777e5686d9eda3ec (Python 3.14, ephemeral env). The MP and WBM labels they are compared with were computed by Matbench Discovery with an earlier version of the same function. On 2,000 WBM structures labelled both ways, the labels agree for **1,784** (0.8920). Disagreement makes protostructure matches *under*-count, never over-count; the formula-based independence filter does not depend on labels at all.

## Caveats

* Independence is from the engines' **MP** training data (via the MPtrj superset) and from WBM. The primary engine is also trained on sAlex (subsampled Alexandria). Alexandria is not used or downloaded, so an OQMD composition that also occurs in Alexandria is not detected here. That residual risk applies to the production engine only, not the second engine (MPtrj only).
* OQMD's labels come from OQMD's own DFT protocol and hull. What that does to a label is measured in stage 2 (`reports/oqmd_hull_disagreement.md`), not assumed.
