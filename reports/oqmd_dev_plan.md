# OQMD development plan — frozen before the full draw was queued

Frozen 2026-09-24T23:33:34+00:00. **DEVELOPMENT / CALIBRATION - licenses nothing.** The OQMD held-out half is locked (`data/oqmd_split.json`) and nothing here reads it.

## Pilot (production engine, 500 development structures)

| jobs | ok | failed | median s | mean s | p95 s |
|---:|---:|---:|---:|---:|---:|
| 500 | 500 | 0 | 0.59 | 3.07 | 12.44 |

The **mean** is used for sizing: the median understates a relaxation-heavy queue (HANDOFF).

## Arithmetic

* second / production engine mean job time = 2.09 / 1.76 = **1.185** (Phase-1 f-electron held-out jobs (runtime only; no outcome is read); n = 9,000 / 9,000)
* 5 workers: wall hours per structure = 3.07 s / 5 / 3600 = 1.703e-04 h (production), x (1 + 1.185) = 3.721e-04 h (both engines)
* budget 35.0 h / 3.721e-04 h = **94,058** structures
* development pool = 445,998; chosen = **94,059** (capped by budget); estimated 35.0 h of AC compute for both engines

## Weights and allocation

Weighted toward the families that cannot say *likely stable*; f-electron and pnictide at a small descriptive share, as a cross-convention check of the two live stable rules. Weights are capped by availability and the surplus redistributed over the uncapped families. Within halide, fluorides take up to 60% of the allocation (WBM cannot settle the fluoride question). Within a family, draws are proportional to the OQMD stability-bin mix of that family's development pool.

| family | weight | drawn |
|---|---:|---:|
| intermetallic | 0.25 | 23,789 |
| oxide | 0.2 | 19,031 |
| halide | 0.15 | 13,178 |
| chalcogenide | 0.15 | 14,274 |
| other | 0.15 | 14,273 |
| f-electron | 0.05 | 4,758 |
| pnictide | 0.05 | 4,756 |

Fluorides in the draw: **4,810**.

Ids: n = 94,059, sha256 `fd7a459839b1fb4e934e4cad3d0d43b009b599a85d740d95c91d021a538337cd` (in `data/oqmd_dev_plan.json`). The 500 pilot ids are included, not extra.
