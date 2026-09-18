# Coverage report

Generated 2026-09-17 by `extract/coverage_report.py`. Every count below comes from loading the shipped tables through `loader.py`, so it cannot drift from what is actually in the CSVs.

## Materials per property

| Property | Table | Rows | Distinct materials | Distinct phases | Status |
|---|---|---:|---:|---:|---|
| Lattice constants (oxides, RT) | `lattice_constants.csv` | 48 | 22 | 30 | complete |
| Atomic oxygen erosion | `space_ao_erosion.csv` | 41 | 39 | n/a | complete |
| Outgassing (TML/CVCM/WVR) | — | 0 | 0 | n/a | **blocked** — see SOURCES.md |
| Elastic constants | — | 0 | 0 | n/a | not started |
| Thermal expansion | — | 0 | 0 | n/a | not started |
| Heat capacity / phonons | — | 0 | 0 | n/a | not started |

Shared key table `materials.csv`: 30 phases, 29 carrying a Materials Project id as a join key.

## Temperature provenance

| Temperature | Rows |
|---|---:|
| not_stated_in_source | 34 |
| recorded_cell | 12 |
| recorded_diffraction | 2 |

The brief asked for room-temperature values. Most crystallographic determinations state no measurement temperature at all, and those rows carry `not_stated_in_source` rather than an assumed 293 K. **Only the 14 rows with a recorded temperature are safe for thermal work**; the rest are safe only for comparisons where a ~1e-5/K expansion coefficient over an unknown ambient range is tolerable.

## Cross-check: spread between independent determinations

This is the floor on useful simulation accuracy. Where two independent experiments of the same phase disagree by *x*, chasing accuracy below *x* is not measurable.

Rows flagged `low_precision` or `implausible_precision` are excluded, and grouping keys on the **cell setting**, not the space-group number (see SOURCES.md).

| Material | Setting | n | mean a (Å) | spread (ppm) | spread (%) |
|---|---|---:|---:|---:|---:|
| Al2O3 | `R -3 c :H` | 4 | 4.75701 | 1366 | 0.137 |
| CaO | `F m -3 m` | 2 | 4.81406 | 1388 | 0.139 |
| MgO | `F m -3 m` | 3 | 4.21318 | 1564 | 0.156 |
| MnO | `F m -3 m` | 2 | 4.44500 | 450 | 0.045 |
| NiO | `F m -3 m` | 2 | 4.16920 | 384 | 0.038 |
| Sc2O3 | `I a -3` | 3 | 9.84417 | 1991 | 0.199 |
| SiO2 | `P 32 2 1` | 2 | 4.91333 | 383 | 0.038 |
| SnO2 | `P 42/m n m` | 5 | 4.73676 | 486 | 0.049 |

**Median spread 926 ppm (0.093 %), worst 1991 ppm (0.199 %), over 8 phases with two or more determinations.**

So for oxide lattice constants the experimental floor is roughly 0.09 %. A simulation targeting 1 % sits comfortably above it; targeting better than ~0.1 % is chasing noise between experiments.

## Overlap with the substitution suite

`data/substitution_candidates.csv` holds 72 distinct materials across 11 families, of which 30 are oxides.

| Family | Oxides in family | Covered here | Missing |
|---|---:|---:|---|
| corundum | 6 | 3 | Ga2O3, Ti2O3, V2O3 |
| fluorite | 5 | 1 | CeO2, Li2O, Na2O, ThO2 |
| perovskite | 5 | 1 | CaTiO3, KTaO3, SrTiO3, SrZrO3 |
| rocksalt | 3 | 3 | — |
| rutile | 4 | 3 | GeO2 |
| spinel | 5 | 0 | CoAl2O4, MgAl2O4, MgCr2O4, MgGa2O4, ZnAl2O4 |
| wurtzite | 2 | 1 | BeO |

**12 of 30 substitution-suite oxides now have an experimental room-temperature lattice constant**: Al2O3, BaTiO3, CaO, Cr2O3, Fe2O3, HfO2, MgO, NiO, SiO2, SnO2, TiO2, ZnO.

## The gap this fills

The project's existing experimental lattice set (`experimental_lattice_constants.csv` plus `experimental_csonka2009.csv`) covers 57 materials, of which the oxides are: MgO.

The brief described that set as covering neither metals nor oxides. Half of that is right. It covers **14 elemental metals** (Ag, Al, Ba, Ca, Cs, Cu, K, Li, Na, Pb, Pd, Rb, Rh, Sr) via the Csonka set, but only **one oxide**, MgO. So the oxide gap was real and is what this table fills; the metals gap was not.

There is a second gap underneath, which the brief did not name: every existing metal value is a **0 K or low-temperature** figure with zero-point anharmonic expansion subtracted, not a room-temperature one. The project currently has no room-temperature experimental lattice constant for any metal.

## Biggest remaining gaps, ranked

1. **Outgassing data — blocked.** The NASA database is behind a reCAPTCHA and the printed RP-1124 editions are scans whose data tables OCR to noise. Needs a manual export.
2. **Elastic constants — not started, and the hardest.** The authoritative compilations (Simmons & Wang; Landolt-Börnstein) are copyrighted print handbooks, and the open Duffy database returns 403. Expect 15–30 materials from individual papers, not the 40–60 targeted.
3. **Thermal expansion and heat capacity — not started.** NIST's cryogenic database covers 43 materials but is mostly engineering alloys and polymers: no SiC, AlN, GaN, MgO or ZrO2, and its fits stop at 300 K, short of the +120 °C LEO limit.
4. **Room-temperature metals.** Not covered by this table (oxides only) and not by the existing 0 K set.
5. **Ternary oxides.** Only SrTiO3 and BaTiO3 here; the substitution suite's perovskite and spinel families are largely uncovered.
6. **Temperature provenance.** 34 of 48 lattice rows have no stated temperature. Narrowing these means reading each original paper.

## Licence posture

| Table | Source | Licence | Commercial redistribution |
|---|---|---|---|
| `lattice_constants.csv` | COD | CC0 1.0 | **Yes** (acknowledge original authors) |
| `space_ao_erosion.csv` | NASA/TM-2006-214482 | US Gov, public domain | **Yes** |
| `materials.csv` | derived + MP ids | CC BY 4.0 (MP ids) | Yes, with attribution |

No NIST Standard Reference Data is used in any shipped table. When datasets 2 and 3 land they will be, and those rows will be cite-only and marked non-redistributable — NIST SRD is copyrighted under 15 U.S.C. §290e despite being free to read.

