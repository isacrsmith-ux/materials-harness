# Phase 0 — correctness audits: before / after

Settings tag `207ccc81` (unchanged: rung 1 of every relaxation is the same protocol as before). 'Before' = results snapshot `results/snapshots/before_phase0.sqlite` taken before any Phase 0 job ran. Hull-distance bins use the target's GGA/GGA+U energy above hull (eV/atom). Energies in meV/atom.

## 1. GGA vs GGA+U, training data, reference hull

* **Documents with both a GGA and a GGA+U entry: 0 of 6,792** cached GGA_GGA+U thermo documents; 0 materials with more than one run type among 3,976 cached chemical-system entries (the stability hulls). The old 'GGA first' rule therefore never fired: **0 results affected, numbers unchanged.** `mp_data.choose_run_type` now applies the MP2020 mixing rule explicitly (GGA+U for O/F compounds of Co, Cr, Fe, Mn, Mo, Ni, V, W; GGA otherwise) and logs every document where it has to choose.
* Single-entry documents whose run type differs from that rule: none.
* **Training data:** MACE-MP-0 reproduces MP's *uncorrected* GGA/GGA+U energies (MPtrj) — near-hull controls:

| functional   | MP2020 correction   |   n |   median |err| vs uncorrected (meV/atom) |   median |err| vs corrected (meV/atom) |
|:-------------|:--------------------|----:|-----------------------------------------:|---------------------------------------:|
| PBE          | zero                |  15 |                                      6.6 |                                    6.6 |
| PBE          | nonzero             | 331 |                                      4.4 |                                  383.1 |
| PBE+U        | nonzero             | 208 |                                      8.6 |                                  740.2 |

  Every energy comparison therefore uses uncorrected DFT energies, and every hull applies MaterialsProject2020Compatibility identically to MACE and DFT entries (unchanged).
* **Reference hull:** all references use the GGA/GGA+U hull (thermo type `GGA_GGA+U`), not MP's default r2SCAN-mixed hull. For the 2,000 auto-pair targets the two differ by > 25 meV/atom for 25 and would move 41 targets to another hull bin — so pair sampling (Phase 1) must also use the GGA/GGA+U values. The recomputed curated hulls reproduce MP's stored GGA/GGA+U e_above_hull to 0.00 meV/atom (n=50).
* **WBM corrections:** re-applying MaterialsProject2020Compatibility (this pymatgen) to the 2,000 sampled WBM DFT entries: 0 rejected, 27 differ from WBM's shipped per-atom correction by > 1 meV/atom (max 314.7 meV/atom; elements most involved {'Si': 12, 'Au': 12, 'Pt': 10, 'Sb': 7, 'Te': 3, 'Se': 2, 'Ba': 2, 'H': 2}; in 20 of them this pymatgen applies no correction where WBM's file has one — mostly intermetallics, i.e. which element is treated as the anion when an entry carries no oxidation states). Run type differs from the MP2020 rule for 0 entries; uncorrected energies match the summary to 0.000 meV/atom. The mode (a) construction uses the shipped correction on both sides, so it cancels; mode (b) (Phase 4) will use the recomputed one on every entry.

## 2. Same structure vs relaxed into a different structure

Species-aware StructureMatcher (pymatgen defaults, never loosened) between each relaxed result and the MP target. Energy/volume errors of results that stayed in the target structure measure the model; results that relaxed into a different structure are a different failure and are reported separately, never mixed in.

**Correction found while building this table:** the old analysis did not apply the convergence / sanity guard to substitution-suite results. The last report's auto-pair control (ctrl) numbers therefore averaged in relaxations that never converged (one substitution had collapsed to about −5.6×10⁹ eV/atom). They are now excluded from every error statistic and counted in the 'rejected (guard)' column. 'Before (as reported)' below is the old aggregation of the pre-Phase-0 data, unconverged results included.

**auto-generated pairs — MP target relaxed (ctrl), before (as reported, unconverged included):**

| bin       |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    |       1258 |                  0 |   10.44 |       6.07 |        3.44 |           0.46 |
| 0.025–0.1 |        466 |                  0 |   13.50 |       8.23 |        1.86 |           0.60 |
| 0.1–0.3   |        156 |                  0 |   30.91 |      10.48 |        8.75 |           1.69 |
| >0.3      |        120 |                  0 |  238.59 |      47.06 |       41.16 |           7.10 |

**auto-generated pairs — MP target relaxed (ctrl).** Guarded, outcomes mixed:

| bin       |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    |       1258 |                  0 |   10.44 |       6.07 |        3.44 |           0.46 |
| 0.025–0.1 |        466 |                  0 |   13.50 |       8.23 |        1.86 |           0.60 |
| 0.1–0.3   |        155 |                  1 |   29.17 |      10.39 |        8.68 |           1.69 |
| >0.3      |        110 |                 10 |  200.01 |      38.16 |       33.64 |           5.79 |

Guarded, separated by structure outcome:

| bin       | ctrl_outcome                       |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|:-----------------------------------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    | relaxed into a different structure |         39 |                  0 |   24.51 |       8.76 |       73.65 |           7.94 |
| ≤0.025    | same structure                     |       1219 |                  0 |    9.99 |       6.00 |        1.19 |           0.45 |
| 0.025–0.1 | relaxed into a different structure |         23 |                  0 |   17.14 |      12.70 |       15.07 |           8.24 |
| 0.025–0.1 | same structure                     |        443 |                  0 |   13.31 |       7.97 |        1.17 |           0.55 |
| 0.1–0.3   | rejected by guard                  |          0 |                  1 |  nan    |     nan    |      nan    |         nan    |
| 0.1–0.3   | relaxed into a different structure |         20 |                  0 |   69.10 |      35.24 |       47.99 |           5.82 |
| 0.1–0.3   | same structure                     |        135 |                  0 |   23.25 |       8.05 |        2.85 |           1.40 |
| >0.3      | rejected by guard                  |          0 |                 10 |  nan    |     nan    |      nan    |         nan    |
| >0.3      | relaxed into a different structure |         45 |                  0 |  322.96 |     156.75 |       67.75 |          21.83 |
| >0.3      | same structure                     |         65 |                  0 |  114.89 |      17.60 |       10.03 |           2.24 |

**auto-generated pairs — substituted parent, best start.** Guarded, outcomes mixed:

| bin       |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    |       1258 |                  0 |   10.44 |       6.12 |        3.57 |           0.47 |
| 0.025–0.1 |        466 |                  0 |   13.68 |       8.23 |        1.98 |           0.62 |
| 0.1–0.3   |        156 |                  0 |   29.77 |      10.48 |       10.65 |           1.76 |
| >0.3      |        118 |                  2 |  226.12 |      55.27 |       47.00 |           8.53 |

Guarded, separated by structure outcome:

| bin       | sub_best_outcome                   |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|:-----------------------------------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    | relaxed into a different structure |         48 |                  0 |   20.85 |       8.74 |       50.86 |           5.53 |
| ≤0.025    | same structure                     |       1210 |                  0 |   10.03 |       6.04 |        1.69 |           0.45 |
| 0.025–0.1 | relaxed into a different structure |         27 |                  0 |   18.56 |      12.70 |       14.90 |           7.04 |
| 0.025–0.1 | same structure                     |        439 |                  0 |   13.38 |       7.97 |        1.19 |           0.58 |
| 0.1–0.3   | relaxed into a different structure |         24 |                  0 |   71.11 |      39.40 |       53.35 |           5.78 |
| 0.1–0.3   | same structure                     |        132 |                  0 |   22.26 |       8.44 |        2.88 |           1.42 |
| >0.3      | rejected by guard                  |          0 |                  2 |  nan    |     nan    |      nan    |         nan    |
| >0.3      | relaxed into a different structure |         59 |                  0 |  328.00 |     174.47 |       82.60 |          25.71 |
| >0.3      | same structure                     |         59 |                  0 |  124.24 |      17.60 |       11.40 |           2.57 |

**curated pairs — MP target relaxed (ctrl).** Guarded, outcomes mixed:

| bin       |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    |         42 |                  0 |   32.81 |      15.66 |        0.39 |           0.30 |
| 0.025–0.1 |          6 |                  0 |    8.78 |       9.39 |        0.23 |           0.14 |
| 0.1–0.3   |          2 |                  0 |   17.84 |      17.84 |        0.35 |           0.35 |

Guarded, separated by structure outcome:

| bin       | ctrl_outcome   |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|:---------------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    | same structure |         42 |                  0 |   32.81 |      15.66 |        0.39 |           0.30 |
| 0.025–0.1 | same structure |          6 |                  0 |    8.78 |       9.39 |        0.23 |           0.14 |
| 0.1–0.3   | same structure |          2 |                  0 |   17.84 |      17.84 |        0.35 |           0.35 |

**curated pairs — substituted parent, best start.** Guarded, outcomes mixed:

| bin       |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    |         42 |                  0 |   32.81 |      15.66 |        0.39 |           0.30 |
| 0.025–0.1 |          6 |                  0 |    8.78 |       9.39 |        0.22 |           0.14 |
| 0.1–0.3   |          2 |                  0 |   17.84 |      17.84 |        0.35 |           0.35 |

Guarded, separated by structure outcome:

| bin       | sub_best_outcome   |   n scored |   rejected (guard) |   E MAE |   E median |   vol MAE % |   vol median % |
|:----------|:-------------------|-----------:|-------------------:|--------:|-----------:|------------:|---------------:|
| ≤0.025    | same structure     |         42 |                  0 |   32.81 |      15.66 |        0.39 |           0.30 |
| 0.025–0.1 | same structure     |          6 |                  0 |    8.78 |       9.39 |        0.22 |           0.14 |
| 0.1–0.3   | same structure     |          2 |                  0 |   17.84 |      17.84 |        0.35 |           0.35 |

## 3. Unconverged competing phases (mode (b) hulls)

Fallback ladder, same convergence criteria (fmax 0.01 eV/Å, |stress| ≤ 0.01 GPa) on every rung: FIRE from the rung-1 end point (≤ 1,500 steps), then a perturbed restart from the MP structure (BFGS, ≤ 1,000 steps).

| material    | formula   |   atoms | rung 1 (BFGS, 500 steps)   | fallback rungs                                                                  | outcome              |
|:------------|:----------|--------:|:---------------------------|:--------------------------------------------------------------------------------|:---------------------|
| mp-aaaaatej | O2        |       8 | not converged              | fire: not converged (1500 steps); perturbed_restart: not converged (1000 steps) | still rejected       |
| mp-aaacsvqv | Al        |     100 | not converged              | fire: converged (588 steps)                                                     | usable (rung 'fire') |
| mp-aaacsvsd | Zn        |     100 | not converged              | fire: converged (449 steps)                                                     | usable (rung 'fire') |
| mp-aaacsvwf | Zn        |     100 | not converged              | fire: converged (690 steps)                                                     | usable (rung 'fire') |
| mp-aaacsvxp | Al        |     100 | not converged              | fire: converged (83 steps)                                                      | usable (rung 'fire') |
| mp-aaacsvyq | V2O5      |     105 | not converged              | fire: converged (942 steps)                                                     | usable (rung 'fire') |
| mp-aaacsvzs | Zn        |     100 | not converged              | fire: converged (770 steps)                                                     | usable (rung 'fire') |
| mp-aaacswcw | Zn        |     100 | not converged              | fire: converged (913 steps)                                                     | usable (rung 'fire') |

**Per system:** 26 of 50 curated targets had or have competing phases missing from their mode (b) hull.

| target           | chemical system   | missing before                                                                            | missing after   | mode (b) status after                    | missing phases on the MP reference hull   |
|:-----------------|:------------------|:------------------------------------------------------------------------------------------|:----------------|:-----------------------------------------|:------------------------------------------|
| Al2O3->Cr2O3     | Cr-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| Al2O3->Fe2O3     | Fe-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| Al2O3->Ga2O3     | Ga-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| Al2O3->Ti2O3     | O-Ti              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| Al2O3->V2O3      | O-V               | mp-aaaaatej, mp-aaacsvyq                                                                  | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| CaF2->CeO2       | Ce-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| CaF2->HfO2       | Hf-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| CaF2->ThO2       | O-Th              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| GaN->AlN         | Al-N              | mp-aaacsvqv, mp-aaacsvxp                                                                  |                 | complete                                 |                                           |
| KMgF3->KZnF3     | F-K-Zn            | mp-aaacsvsd, mp-aaacsvwf, mp-aaacsvzs, mp-aaacswcw                                        |                 | complete                                 |                                           |
| Li2O->Na2O       | Na-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| MgAl2O4->CoAl2O4 | Al-Co-O           | mp-aaaaatej, mp-aaacsvqv, mp-aaacsvxp                                                     | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| MgAl2O4->MgCr2O4 | Cr-Mg-O           | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| MgAl2O4->MgGa2O4 | Ga-Mg-O           | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| MgAl2O4->ZnAl2O4 | Al-O-Zn           | mp-aaaaatej, mp-aaacsvqv, mp-aaacsvsd, mp-aaacsvwf, mp-aaacsvxp, mp-aaacsvzs, mp-aaacswcw | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| MgO->CaO         | Ca-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| MgO->NiO         | Ni-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| SrTiO3->BaTiO3   | Ba-O-Ti           | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| SrTiO3->CaTiO3   | Ca-O-Ti           | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| SrTiO3->KTaO3    | K-O-Ta            | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| SrTiO3->SrZrO3   | O-Sr-Zr           | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| TiO2->GeO2       | Ge-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| TiO2->SiO2       | O-Si              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| TiO2->SnO2       | O-Sn              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| ZnO->BeO         | Be-O              | mp-aaaaatej                                                                               | mp-aaaaatej     | not scored: reference hull phase missing | mp-aaaaatej                               |
| ZnS->ZnSe        | Se-Zn             | mp-aaacsvsd, mp-aaacsvwf, mp-aaacsvzs, mp-aaacswcw                                        |                 | complete                                 |                                           |

**Curated stability gate, before / after** (target energy = best substitution start; mode (b) scored only when the hull is complete or only off-hull phases are missing):

| run    | mode                             |   scored |   unscored |   e_hull MAE meV/atom |   accuracy@0 |   accuracy@0.1 |
|:-------|:---------------------------------|---------:|-----------:|----------------------:|-------------:|---------------:|
| before | a                                |       50 |          0 |                15.448 |        0.680 |          0.940 |
| before | b                                |       50 |          0 |                 4.352 |        0.860 |          1.000 |
| after  | a                                |       50 |          0 |                15.448 |        0.680 |          0.940 |
| after  | b                                |       27 |         23 |                 3.849 |        0.852 |          1.000 |
| after  | b + stand-in polymorph (flagged) |       50 |          0 |                 4.352 |        0.860 |          1.000 |

Target energies now come from the best substitution start ({'sub': 26, 'sub_rescaled': 24}). The last row is NOT mode (b): for 23 targets a reference-hull phase has no usable MACE relaxation, and a converged polymorph of the same formula stands in for it. It is shown so the cost of the strict rule is visible; the strict mode (b) row is the scored result.

## 4. Two substitution starts: parent volume vs predicted volume

Each substitution is relaxed from the parent's cell as is (unscaled) and from the same cell rescaled to a predicted volume (pymatgen RLS volume predictor with ionic radii, else atomic radii, else DLS bond lengths). The lowest-energy converged result is kept; which start won is recorded.

**auto-generated pairs** (ΔE in meV/atom between the two starts; 'same pairs' = pairs where both starts are usable, so the columns compare the same population):

| bin       |   pairs |   both starts usable |   tie (|ΔE| ≤ 1) |   rescaled lower by > 1 |   rescaled lower by > 10 |   unscaled lower by > 1 | same pairs — E MAE unscaled → best   | same pairs — vol MAE % unscaled → best   | same pairs — match unscaled → best   |   rescued (only rescaled usable) |   rescued — E MAE |   no usable start |
|:----------|--------:|---------------------:|-----------------:|------------------------:|-------------------------:|------------------------:|:-------------------------------------|:-----------------------------------------|:-------------------------------------|---------------------------------:|------------------:|------------------:|
| ≤0.025    |    1258 |                 1257 |             1247 |                       5 |                        1 |                       5 | 10.5 → 10.4                          | 3.32 → 3.57                              | 0.96 → 0.96                          |                                0 |             nan   |                 0 |
| 0.025–0.1 |     466 |                  465 |              454 |                       5 |                        1 |                       6 | 13.6 → 13.7                          | 1.85 → 1.96                              | 0.94 → 0.94                          |                                0 |             nan   |                 0 |
| 0.1–0.3   |     156 |                  155 |              151 |                       2 |                        1 |                       2 | 29.4 → 29.8                          | 10.73 → 10.71                            | 0.85 → 0.85                          |                                0 |             nan   |                 0 |
| >0.3      |     120 |                   97 |               78 |                       8 |                        7 |                      11 | 180.8 → 187.1                        | 35.84 → 40.04                            | 0.56 → 0.55                          |                                7 |             786.4 |                 2 |

**curated pairs** (ΔE in meV/atom between the two starts; 'same pairs' = pairs where both starts are usable, so the columns compare the same population):

| bin       |   pairs |   both starts usable |   tie (|ΔE| ≤ 1) |   rescaled lower by > 1 |   rescaled lower by > 10 |   unscaled lower by > 1 | same pairs — E MAE unscaled → best   | same pairs — vol MAE % unscaled → best   | same pairs — match unscaled → best   |   rescued (only rescaled usable) |   rescued — E MAE |   no usable start |
|:----------|--------:|---------------------:|-----------------:|------------------------:|-------------------------:|------------------------:|:-------------------------------------|:-----------------------------------------|:-------------------------------------|---------------------------------:|------------------:|------------------:|
| ≤0.025    |      42 |                   42 |               42 |                       0 |                        0 |                       0 | 32.8 → 32.8                          | 0.39 → 0.39                              | 1.00 → 1.00                          |                                0 |               nan |                 0 |
| 0.025–0.1 |       6 |                    6 |                6 |                       0 |                        0 |                       0 | 8.8 → 8.8                            | 0.22 → 0.22                              | 1.00 → 1.00                          |                                0 |               nan |                 0 |
| 0.1–0.3   |       2 |                    2 |                2 |                       0 |                        0 |                       0 | 17.8 → 17.8                          | 0.35 → 0.35                              | 1.00 → 1.00                          |                                0 |               nan |                 0 |

**Curated symmetry-broken (rattled) runs that do not simply return to the target** (meV/atom vs the relaxed MP structure):

| pair           | before                                            | after                                            | winning start        |
|:---------------|:--------------------------------------------------|:-------------------------------------------------|:---------------------|
| Al2O3->V2O3    | lower symmetry, not lower energy (SG 2) (-0.9)    | lower symmetry, not lower energy (SG 2) (-0.9)   | sub_rattled          |
| CaF2->HfO2     | distorts to lower energy (SG 14) (-65.4)          | distorts to lower energy (SG 14) (-65.4)         | sub_rattled          |
| Si->C          | lower symmetry, not lower energy (SG 65) (+182.5) | returns to target structure (+0.0)               | sub_rattled_rescaled |
| SrTiO3->BaTiO3 | distorts to lower energy (SG 38) (-9.3)           | distorts to lower energy (SG 38) (-9.3)          | sub_rattled          |
| SrTiO3->CaTiO3 | distorts to lower energy (SG 62) (-63.5)          | distorts to lower energy (SG 62) (-63.5)         | sub_rattled_rescaled |
| SrTiO3->KTaO3  | lower symmetry, not lower energy (SG 160) (-0.3)  | lower symmetry, not lower energy (SG 160) (-0.3) | sub_rattled_rescaled |
| SrTiO3->SrZrO3 | distorts to lower energy (SG 62) (-49.5)          | distorts to lower energy (SG 62) (-49.5)         | sub_rattled_rescaled |

## Added: energy at the DFT geometry (single point)

MACE energy evaluated at the MP PBE structure without relaxing. Where the relaxed control lands in a different structure, the single point still measures the model's energy error at the DFT geometry.

| bin       | ctrl outcome                       |    n | single point at PBE structure: MAE / median   | after relaxation (ctrl): MAE / median   |
|:----------|:-----------------------------------|-----:|:----------------------------------------------|:----------------------------------------|
| ≤0.025    | relaxed into a different structure |   39 | 12.8 / 9.4                                    | 24.5 / 8.8                              |
| ≤0.025    | same structure                     | 1219 | 10.6 / 6.6                                    | 10.0 / 6.0                              |
| 0.025–0.1 | relaxed into a different structure |   23 | 13.6 / 8.0                                    | 17.1 / 12.7                             |
| 0.025–0.1 | same structure                     |  443 | 12.9 / 8.1                                    | 13.3 / 8.0                              |
| 0.1–0.3   | relaxed into a different structure |   20 | 16.2 / 7.9                                    | 69.1 / 35.2                             |
| 0.1–0.3   | same structure                     |  135 | 22.8 / 10.2                                   | 23.2 / 8.1                              |
| >0.3      | relaxed into a different structure |   45 | 32.1 / 13.2                                   | 323.0 / 156.8                           |
| >0.3      | same structure                     |   65 | 100.7 / 16.2                                  | 114.9 / 17.6                            |

## Added: WBM — MACE-relaxed vs DFT-relaxed structure

1,996 usable WBM relaxations (existing sample) compared with WBM's DFT-relaxed structures (species-aware StructureMatcher, defaults): 203 relaxed into a different structure. Energies (MACE − DFT, meV/atom) by hull bin and outcome:

| bin (WBM, vs MP hull)   | outcome                            |   n |   E MAE |   E median |   mean signed |
|:------------------------|:-----------------------------------|----:|--------:|-----------:|--------------:|
| <0                      | same structure                     | 290 |    35.1 |       17.4 |           6.8 |
| <0                      | relaxed into a different structure |  21 |    81.8 |       48.1 |          -1.3 |
| 0–0.025                 | same structure                     | 178 |    29.2 |       14.1 |          -3.6 |
| 0–0.025                 | relaxed into a different structure |  16 |    58.7 |       25.3 |           3.1 |
| 0.025–0.1               | same structure                     | 555 |    36.8 |       25.2 |         -20.2 |
| 0.025–0.1               | relaxed into a different structure |  39 |    81.7 |       44.2 |           4.1 |
| 0.1–0.3                 | same structure                     | 571 |    61.0 |       45.9 |         -41.1 |
| 0.1–0.3                 | relaxed into a different structure |  76 |    89.5 |       70.5 |         -50.8 |
| >0.3                    | same structure                     | 199 |   103.7 |       70.4 |         -77.9 |
| >0.3                    | relaxed into a different structure |  51 |   208.3 |      185.1 |        -148.7 |

