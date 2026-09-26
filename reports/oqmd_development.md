# OQMD development results

> **DEVELOPMENT / CALIBRATION TIER (licenses nothing).** Every number here is scored on the rows it describes. Nothing in this report is a held-out result, and nothing here changes `data/calibration_bundle.json`. The OQMD held-out half is locked and unopened.

Generated 2026-09-26T19:46:48+00:00 over the frozen plan (sha256 `fd7a459839b1fb4e…`, 94,059 structures). Usable with a production-engine prediction on MP's hull: **93,602**; missing a second-engine prediction: 310. Unusable, by reason: no MP hull 294, guard 163.

**How to read this.** The prediction is the product's own: the engine's relaxed energy placed on the Materials Project GGA/GGA+U hull with MP2020 corrections (mode (a)), the material's own formula removed from MP. The label is OQMD's hull distance on OQMD's hull. Where those two hulls disagree about the competing phases, a 'wrong' call is a convention difference, not a model error. Every table is therefore split by the **hull shift** at the row's own composition: OQMD's formation-energy hull minus MP's (MP2020), the row's own formula excluded from both. For a material with the same formation energy in both conventions the two labels differ by exactly that shift, so the rows where the hulls agree within 25 meV are the ones on which 'the rule fails' can be told apart from 'the hulls disagree'. Counts: hulls disagree (|shift| > 25 meV) 57,117, hulls agree (|shift| <= 25 meV) 36,648, no hull 294. Median shift +6.5 meV, mean |shift| 68.6 meV. The construction is checked by rebuilding OQMD's own label from it: 0.7049 of 93,765 rows reproduce OQMD's stability within 1 meV (0.8343 within 5 meV).

## Live production rules, Path A (no second engine) — labelable 76,094

| family | n | OQMD stable share | rule (stable / unstable) | stable calls | precision | CP95 (descriptive) | unstable calls | NPV | CP95 (descriptive) |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| f-electron | 3,735 | 0.073 | -20/+10 | 298 | 0.3893 | 0.3421 | 3044 | 0.9875 | 0.9837 |
| intermetallic | 20,059 | 0.045 | none/+0 | — | — | — | 18777 | 0.9902 | 0.9889 |
| oxide | 13,504 | 0.040 | none/+30 | — | — | — | 11650 | 0.9957 | 0.9946 |
| halide | 10,191 | 0.094 | none/none | — | — | — | — | — | — |
| chalcogenide | 11,967 | 0.038 | none/none | — | — | — | — | — | — |
| pnictide | 4,188 | 0.064 | -20/+0 | 212 | 0.5189 | 0.4601 | 3831 | 0.9776 | 0.9732 |
| other | 12,450 | 0.052 | none/+30 | — | — | — | 10862 | 0.9982 | 0.9973 |

### Path A, split by hull shift (precision S / NPV U; calls in brackets)

| family | hulls agree (|shift| ≤ 25 meV) | hulls disagree (|shift| > 25 meV) | no hull |
|---|---|---|---|
| f-electron | n=1,781: S 0.618 (34); U 0.995 (1582) | n=1,954: S 0.360 (264); U 0.979 (1462) | n=0: S — (0); U — (0) |
| intermetallic | n=15,200: U 0.991 (14598) | n=4,859: U 0.989 (4179) | n=0: U — (0) |
| oxide | n=1,420: U 0.996 (1275) | n=12,084: U 0.996 (10375) | n=0: U — (0) |
| halide | n=1,091: no rule | n=9,100: no rule | n=0: no rule |
| chalcogenide | n=321: no rule | n=11,646: no rule | n=0: no rule |
| pnictide | n=1,917: S 0.729 (48); U 0.985 (1813) | n=2,271: S 0.457 (164); U 0.971 (2018) | n=0: S — (0); U — (0) |
| other | n=9,196: U 0.999 (8456) | n=3,254: U 0.996 (2406) | n=0: U — (0) |

## Live production rules, Path B (with second engine) — labelable 69,610

| family | n | OQMD stable share | rule (stable / unstable) | stable calls | precision | CP95 (descriptive) | unstable calls | NPV | CP95 (descriptive) |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| f-electron | 3,433 | 0.078 | -20/+10 | 295 | 0.3864 | 0.3391 | 2746 | 0.9862 | 0.9819 |
| intermetallic | 18,473 | 0.049 | none/+0 | — | — | — | 17192 | 0.9893 | 0.9879 |
| oxide | 12,389 | 0.044 | none/none | — | — | — | — | — | — |
| halide | 9,393 | 0.101 | none/none | — | — | — | — | — | — |
| chalcogenide | 11,211 | 0.040 | none/none | — | — | — | — | — | — |
| pnictide | 3,719 | 0.072 | -20/+0 | 212 | 0.5189 | 0.4601 | 3362 | 0.9744 | 0.9695 |
| other | 10,992 | 0.059 | none/+30 | — | — | — | 9409 | 0.9980 | 0.9970 |

### Path B, split by hull shift (precision S / NPV U; calls in brackets)

| family | hulls agree (|shift| ≤ 25 meV) | hulls disagree (|shift| > 25 meV) | no hull |
|---|---|---|---|
| f-electron | n=1,619: S 0.618 (34); U 0.994 (1420) | n=1,814: S 0.356 (261); U 0.977 (1326) | n=0: S — (0); U — (0) |
| intermetallic | n=13,980: U 0.990 (13378) | n=4,493: U 0.987 (3814) | n=0: U — (0) |
| oxide | n=1,188: no rule | n=11,201: no rule | n=0: no rule |
| halide | n=959: no rule | n=8,434: no rule | n=0: no rule |
| chalcogenide | n=294: no rule | n=10,917: no rule | n=0: no rule |
| pnictide | n=1,704: S 0.729 (48); U 0.983 (1600) | n=2,015: S 0.457 (164); U 0.967 (1762) | n=0: S — (0); U — (0) |
| other | n=8,027: U 0.999 (7287) | n=2,965: U 0.996 (2122) | n=0: U — (0) |

## Does a threshold *look* certifiable? (development tier, Path A)

`certify` over the 61-point grid with a 12-fold family x side correction (bound level 0.999932). A threshold found here was **selected on these rows**; it is a hypothesis for a pre-registration, not a result. Held-out sizing uses 0.9875 (four hypotheses) and 80% power, at the development point estimate and, pessimistically, at the development lower bound.

| group | n | side | threshold | calls | point | corrected bound | held-out n (80%, at point) | held-out n (80%, at bound) |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| intermetallic | 20,059 | stable | none | — | — | — | — | — |
| intermetallic | 20,059 | unstable | -90 meV | 20022 | 0.9558 | 0.9501 | 12723 | None |
| oxide | 13,504 | stable | none | — | — | — | — | — |
| oxide | 13,504 | unstable | -300 meV | 13492 | 0.9597 | 0.9528 | 4627 | 55264 |
| halide | 10,191 | stable | none | — | — | — | — | — |
| halide | 10,191 | unstable | +0 meV | 8161 | 0.9683 | 0.9602 | 1464 | 4990 |
| chalcogenide | 11,967 | stable | none | — | — | — | — | — |
| chalcogenide | 11,967 | unstable | -300 meV | 11958 | 0.9626 | 0.9556 | 2620 | 14047 |
| other | 12,450 | stable | none | — | — | — | — | — |
| other | 12,450 | unstable | -50 meV | 12232 | 0.9581 | 0.9508 | 6536 | None |
| fluoride (any family) | 3,491 | stable | none | — | — | — | — | — |
| fluoride (any family) | 3,491 | unstable | +0 meV | 2833 | 0.9689 | 0.9546 | 1330 | 25513 |

Held-out OQMD entries available per family (locked half): chalcogenide 39,732, f-electron 192,604, halide 13,176, intermetallic 92,898, other 30,532, oxide 50,526, pnictide 26,516.

## Fluorides

Fluorides in the development draw: 4,810; usable 4,781; labelable on Path A 3,491. The 'fluoride (any family)' row above answers whether OQMD gives enough independent fluorides to size the study that `reports/fluoride_followup_power.md` says WBM cannot: compare its held-out n with the independent fluoride count in `reports/oqmd_overlap.md`, half of which is locked.

## What this does not do

It does not certify anything, change any threshold, or open the held-out half. Every bound is descriptive. A future OQMD held-out test would need its own pre-registration, fixed thresholds and the hull-consistency caveat built in.
