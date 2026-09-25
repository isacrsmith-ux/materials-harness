# OQMD against MP on the same materials — stage 2 (no ML)

Generated 2026-09-25T01:28:37+00:00. MP database version **2026.04.13** (152,426 GGA/GGA+U thermo documents retrieved 2026-09-24T22:24:24+00:00).

**47,490** materials are in both databases (54,881 OQMD entries; same reduced formula AND same protostructure label; one row per material: the lowest OQMD stability and the lowest MP decomposition enthalpy on that key). OQMD quantity: formation_energies.stability, 'standard' fit (signed; negative = below the hull of the other phases). MP quantity: thermo GGA_GGA+U decomposition_enthalpy (signed; MP2020-corrected). Both are signed, so the stable side can be compared at a negative threshold.

## The ceiling this sets

On the same materials the two databases put the material on **opposite sides** of the threshold this often: -20 meV: **0.2070**, +0 meV: **0.2553**, +10 meV: **0.1813**, +30 meV: **0.1317**. Mean absolute difference 64.2 meV/atom, median signed difference (OQMD − MP) +4.8 meV/atom, Spearman 0.705.

**This is a ceiling on what any OQMD evaluation of the harness can mean.** The harness's rules were certified against MP-convention labels. Where the two conventions disagree on a material's side, an OQMD 'error' is a convention difference, not a model failure, and an OQMD 'success' may be one too. An OQMD precision or NPV can therefore not be read as the rule's accuracy unless it is well clear of the disagreement rate at the matching threshold, and the development report splits these rows out for exactly that reason.

*Per OQMD entry instead of per material* the rates are higher (-20 meV: 0.2479, +0 meV: 0.3093, +10 meV: 0.1936, +30 meV: 0.1392), because OQMD's duplicate entries of a material sit slightly above its hull vertex.

*Near zero.* Of the 12,123 materials on opposite sides at exactly 0 meV, 4,689 have an OQMD value within 5 meV of zero and 676 have both values within 5 meV of zero: the 0 meV comparison is dominated by meV-scale differences at the hull, which is why the -20 and +10 meV rows are the ones that match the live rules.

## Side disagreement per family and threshold

| family | n | -20 meV | +0 meV | +10 meV | +30 meV | MAE (meV) | median OQMD−MP (meV) |
|---|---:|---:|---:|---:|---:|---:|---:|
| f-electron | 17,351 | 0.2168 | 0.2554 | 0.1973 | 0.1387 | 64.0 | +5.2 |
| intermetallic | 6,847 | 0.1919 | 0.2492 | 0.1577 | 0.1009 | 31.6 | +7.1 |
| oxide | 9,046 | 0.1781 | 0.2493 | 0.1979 | 0.1694 | 65.1 | +0.9 |
| halide | 4,396 | 0.2666 | 0.3387 | 0.2461 | 0.1856 | 118.1 | +7.2 |
| chalcogenide | 3,602 | 0.2335 | 0.2904 | 0.1727 | 0.1119 | 61.8 | +7.2 |
| pnictide | 3,155 | 0.1889 | 0.1861 | 0.0995 | 0.0666 | 88.5 | +8.3 |
| other | 3,093 | 0.1733 | 0.1966 | 0.0963 | 0.0627 | 35.9 | +4.7 |
| ALL | 47,490 | 0.2070 | 0.2553 | 0.1813 | 0.1317 | 64.2 | +4.8 |

## Agreement matrix, all families (rows OQMD bin, columns MP bin, eV/atom)

| OQMD \ MP | <0 | 0–0.025 | 0.025–0.1 | 0.1–0.3 | >0.3 |
|---|---:|---:|---:|---:|---:|
| <0 | 14,114 | 1,133 | 627 | 342 | 64 |
| 0–0.025 | 7,341 | 5,079 | 1,155 | 329 | 62 |
| 0.025–0.1 | 1,935 | 1,380 | 4,766 | 570 | 63 |
| 0.1–0.3 | 521 | 187 | 803 | 3,379 | 209 |
| >0.3 | 102 | 44 | 64 | 343 | 2,878 |

Per-family matrices are in `reports/oqmd_hull_disagreement.json`.
