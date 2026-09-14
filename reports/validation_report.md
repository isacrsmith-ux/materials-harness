# Validation report — MACE-MPA-0 medium

Generated 2026-09-12 17:51 UTC · commit `0a2c263` · settings tag `c2480e74` · model `mace-mpa-0-medium.model` · cpu/float32 · Apple M4 Max · macOS 26.6.2

Relaxation: FrechetCellFilter + BFGS, fmax 0.01 eV/Å, |stress| ≤ 0.01 GPa, ≤ 500 steps, fallback ladder on failure. Bins: energy above hull (eV/atom) — MP targets on the GGA/GGA+U hull, WBM against the MP hull (with a '<0' bin). Brackets: 95 % bootstrap intervals; verdicts from the pessimistic end.

## Verdict in plain language

* **Engine evaluated:** MACE-MPA-0 medium (`mace-mpa-0-medium`, cpu/float32). Engines are compared on identical structures in `reports/phase3/screening.md`; candidates, licences and measured speed in `reports/phase3/candidates.md`. All statements below use the pessimistic end of the 95 % interval.
* **Threshold:** call a new material stable when its predicted energy above hull is ≤ +0 meV/atom (cost-optimal on the calibration set at the placeholder costs). At that threshold **at least 80% of 'stable' calls are right** (point 83%) and at least 81% of truly stable materials are found (point 84%); 'unstable' calls are right at least 96.5% of the time. Precision verdict: use with caution.
* **Energy error on new materials, upper bound by true hull distance:** <0: ≤ 17 meV/atom (trustworthy); 0–0.025: ≤ 12 meV/atom (trustworthy); 0.025–0.1: ≤ 19 meV/atom (trustworthy); 0.1–0.3: ≤ 30 meV/atom (use with caution); >0.3: ≤ 97 meV/atom (not trustworthy).
* **Relaxation changes the structure** for 4% (<0), 3% (0–0.025), 5% (0.025–0.1), 10% (0.1–0.3), 15% (>0.3) of new materials; those results carry 4.6× the energy error of the rest (102 vs 22 meV/atom MAE) and should go to DFT, not to the lab.
* **Known materials that keep their structure, energy error upper bound (meV/atom):** ≤0.025: ≤ 7 (trustworthy); 0.025–0.1: ≤ 10 (trustworthy); 0.1–0.3: ≤ 23 (trustworthy); >0.3: ≤ 135 (not trustworthy).
* **Chemistries (new materials, ≥ 20 compounds):** error upper bound ≤ 30 meV/atom for Dy, Cu, Cs, Sn, Hf, K, Er, Pr, Pt, Ru, Ag, Li, Mg, Nd, Ga, La, Tb, Lu, Zn, Ac, Sm, Al, Gd, Hg; error lower bound > 60 meV/atom (not trustworthy) for Pu.
* **Hull construction for new materials:** relaxing every competing phase with the engine makes the hull-distance error **larger** by +1.9 [+0.8, +3.2] meV/atom per system than placing the engine's energy on the MP DFT hull (mode a). On new materials the error belongs to the new structure and does not cancel against the competitors; mode (a) is the better construction for the product, and it needs no competitor relaxations.
* **The locked WBM test set is reported separately in `reports/final_test.md`** (opened once, every threshold fitted on this calibration set).

### Compared with the previous scorecard

Previous: `mace-mp-0-medium` (settings `207ccc81`). **Settings differ.**

| metric                                                |   previous |   this run |
|:------------------------------------------------------|-----------:|-----------:|
| mp_same_structure_energy_mae_≤0.025                   |     12.701 |      6.498 |
| mp_same_structure_energy_mae_upper_≤0.025             |     15.240 |      7.355 |
| mp_same_structure_energy_mae_0.025–0.1                |     15.218 |      9.370 |
| mp_same_structure_energy_mae_upper_0.025–0.1          |     16.737 |     10.382 |
| mp_same_structure_energy_mae_0.1–0.3                  |     23.881 |     19.532 |
| mp_same_structure_energy_mae_upper_0.1–0.3            |     26.829 |     22.606 |
| mp_same_structure_energy_mae_>0.3                     |    119.598 |    109.773 |
| mp_same_structure_energy_mae_upper_>0.3               |    142.631 |    134.836 |
| wbm_energy_mae_<0                                     |     40.212 |     14.754 |
| wbm_energy_mae_upper_<0                               |     46.366 |     17.221 |
| wbm_energy_mae_0–0.025                                |     25.960 |     11.012 |
| wbm_energy_mae_upper_0–0.025                          |     30.458 |     12.346 |
| wbm_energy_mae_0.025–0.1                              |     41.863 |     16.491 |
| wbm_energy_mae_upper_0.025–0.1                        |     45.303 |     18.657 |
| wbm_energy_mae_0.1–0.3                                |     65.725 |     28.026 |
| wbm_energy_mae_upper_0.1–0.3                          |     69.216 |     30.150 |
| wbm_energy_mae_>0.3                                   |    124.278 |     84.332 |
| wbm_energy_mae_upper_>0.3                             |    135.925 |     96.679 |
| wbm_precision_opt                                     |      0.686 |      0.826 |
| wbm_precision_opt_lower                               |      0.642 |      0.795 |
| wbm_recall_opt                                        |      0.534 |      0.838 |
| wbm_f1_opt                                            |      0.600 |      0.832 |
| wbm_npv_opt                                           |      0.919 |      0.971 |
| wbm_threshold_opt_mev                                 |    -30.000 |      0.000 |
| wbm_f1_0                                              |      0.647 |      0.832 |
| wbm_precision_0                                       |      0.550 |      0.826 |
| wbm_daf_0                                             |      3.607 |      5.411 |
| mode_b_minus_a_abs_mev                                |      5.081 |      1.927 |
| mode_b_mae_<0                                         |     39.552 |     16.232 |
| mode_b_mae_0–0.025                                    |     29.514 |     10.594 |
| mode_b_mae_0.025–0.1                                  |     44.036 |     13.120 |
| mode_b_mae_0.1–0.3                                    |     76.714 |     40.393 |
| mode_b_mae_>0.3                                       |    124.636 |     99.032 |
| routing_n                                             |   3993.000 |   3998.000 |
| routing_likely stable                                 |      0.000 |    103.000 |
| routing_likely unstable                               |   1455.000 |   2162.000 |
| routing_send to DFT                                   |   2538.000 |   1733.000 |
| routing_NPV of 'likely unstable'                      |      0.980 |      0.985 |
| routing_share sent to DFT                             |      0.636 |      0.433 |
| routing_truly stable found as 'likely stable'         |      0.000 |      0.164 |
| routing_truly stable sent to DFT                      |      0.952 |      0.784 |
| routing_truly stable wrongly called 'likely unstable' |      0.048 |      0.052 |
| routing_stable_label_certified                        |      0.000 |      1.000 |
| bulk_mae_pct                                          |      8.601 |     11.923 |
| bulk_mae_pct_upper                                    |     12.035 |     16.807 |
| bulk_n                                                |     82.000 |     82.000 |

## 1. What was scored, and what was not

* **WBM split** (`data/wbm_split.json`, seed 20260911, made 2026-09-11 before any tuning): calibration 4,000 ids, locked test 4,000 ids (sha256 `31f0ad698a2c…`), both in the pool's hull-bin proportions. **Every stability decision, threshold and cost optimum below uses the calibration set only. The test set has not been run; it is evaluated once, at the very end.**
* WBM calibration: 3,998 usable relaxations, 2 rejected by the convergence / sanity guard (counted, not scored), 0 without a result yet.
* **MP substitution pairs:** 1,952 pairs sampled per target hull bin (design: {"per_bin": 500, "implausible_frac": 0.1, "metallic_frac": 0.3, "max_per_prototype": 5}); sampling shortfalls (cell ran out of candidates under the prototype cap): {'>0.3': {'metallic/plausible': 48}}.

Results rejected by the guard (not converged or unphysical), per bin — excluded from every statistic:

| bin       |   pairs |   ctrl rejected |   no usable substitution start |
|:----------|--------:|----------------:|-------------------------------:|
| ≤0.025    |     500 |               0 |                              0 |
| 0.025–0.1 |     500 |               0 |                              0 |
| 0.1–0.3   |     500 |               1 |                              0 |
| >0.3      |     452 |               5 |                              1 |

Failed or timed-out jobs at this settings tag: 3 ({'mode_b': 3}).

## 2. Known materials (Materials Project substitution pairs), by target hull distance

Energies in meV/atom against MP's uncorrected PBE/PBE+U energy; volume in % against the PBE cell. *Same structure* = the relaxed result still matches the MP target (StructureMatcher, default tolerances); *relaxed into a different structure* is a different failure and is never mixed into the first.

Every table pairs the MAE with its median |error| and its 10% trimmed mean (a symmetric trim of the absolute errors). Where the three disagree the cell is dominated by a few results, and only the MAE — the worst-case-honest statistic — sets the verdict. **excluded (guard)** counts the results the convergence / sanity / energy-plausibility guard rejected in that bin; they are in no average on the row.

**MP target relaxed with MACE (control):**

| bin       | ctrl outcome                       |   n |   excluded (guard, per bin) | energy MAE           | energy median |err|   | energy trimmed mean   | mean signed             | volume MAE %         | volume median %     | energy verdict (pessimistic)   |
|:----------|:-----------------------------------|----:|----------------------------:|:---------------------|:----------------------|:----------------------|:------------------------|:---------------------|:--------------------|:-------------------------------|
| ≤0.025    | relaxed into a different structure |   8 |                           0 | 12.6 [4.4, 20.9]     | 6.2 [2.5, 25.0]       | 12.6 [4.4, 20.9]      | -12.5 [-20.9, -4.4]     | 14.95 [5.16, 26.60]  | 7.41 [0.82, 35.86]  | trustworthy                    |
| ≤0.025    | same structure                     | 492 |                           0 | 6.5 [5.7, 7.4]       | 3.6 [3.2, 3.9]        | 4.5 [4.0, 5.1]        | +2.5 [+1.6, +3.5]       | 1.09 [0.94, 1.24]    | 0.64 [0.57, 0.70]   | trustworthy                    |
| 0.025–0.1 | relaxed into a different structure |  33 |                           0 | 25.0 [19.9, 30.1]    | 25.0 [13.9, 30.7]     | 24.3 [19.0, 29.3]     | -22.3 [-28.6, -15.8]    | 6.05 [3.75, 8.60]    | 2.49 [1.27, 4.34]   | use with caution               |
| 0.025–0.1 | same structure                     | 467 |                           0 | 9.4 [8.4, 10.4]      | 5.4 [4.9, 6.1]        | 7.2 [6.5, 8.0]        | -1.4 [-2.8, -0.1]       | 1.30 [1.14, 1.47]    | 0.72 [0.65, 0.79]   | trustworthy                    |
| 0.1–0.3   | relaxed into a different structure |  74 |                           1 | 66.9 [54.7, 79.3]    | 56.1 [35.9, 75.3]     | 60.1 [48.6, 73.1]     | -65.8 [-78.5, -53.4]    | 4.70 [3.54, 6.01]    | 2.97 [2.12, 3.90]   | not trustworthy                |
| 0.1–0.3   | same structure                     | 425 |                           1 | 19.5 [16.7, 22.6]    | 8.4 [7.4, 9.2]        | 12.4 [10.7, 14.5]     | -10.9 [-14.5, -7.8]     | 1.99 [1.75, 2.26]    | 1.17 [0.96, 1.36]   | trustworthy                    |
| >0.3      | relaxed into a different structure | 121 |                           5 | 579.1 [425.7, 750.2] | 215.6 [144.7, 325.3]  | 343.8 [241.8, 509.4]  | -578.3 [-749.3, -425.2] | 18.02 [13.24, 23.52] | 10.66 [7.89, 12.79] | not trustworthy                |
| >0.3      | same structure                     | 326 |                           5 | 109.8 [86.4, 134.8]  | 19.2 [13.0, 25.1]     | 56.2 [38.8, 76.3]     | -99.4 [-124.6, -74.6]   | 3.97 [3.28, 4.74]    | 1.92 [1.51, 2.14]   | not trustworthy                |

**Substituted parent relaxed — best of two starts (the product's use case):**

| bin       | sub best outcome                   |   n |   excluded (guard, per bin) | energy MAE           | energy median |err|   | energy trimmed mean   | mean signed             | volume MAE %         | volume median %    | energy verdict (pessimistic)   |
|:----------|:-----------------------------------|----:|----------------------------:|:---------------------|:----------------------|:----------------------|:------------------------|:---------------------|:-------------------|:-------------------------------|
| ≤0.025    | relaxed into a different structure |  10 |                           0 | 36.2 [6.3, 87.7]     | 6.3 [2.3, 25.2]       | 12.9 [4.0, 77.0]      | +15.6 [-17.0, +72.4]    | 13.36 [5.09, 22.73]  | 7.40 [0.36, 27.99] | not trustworthy                |
| ≤0.025    | same structure                     | 490 |                           0 | 6.5 [5.7, 7.3]       | 3.6 [3.1, 3.9]        | 4.6 [4.1, 5.1]        | +2.4 [+1.5, +3.4]       | 1.22 [0.95, 1.65]    | 0.63 [0.55, 0.69]  | trustworthy                    |
| 0.025–0.1 | relaxed into a different structure |  48 |                           0 | 36.0 [24.0, 54.4]    | 29.1 [14.1, 38.8]     | 27.2 [21.5, 34.1]     | -10.7 [-25.7, +10.4]    | 6.85 [5.06, 8.74]    | 3.91 [1.91, 7.02]  | use with caution               |
| 0.025–0.1 | same structure                     | 452 |                           0 | 17.3 [8.6, 34.0]     | 5.3 [4.9, 6.1]        | 7.1 [6.4, 7.9]        | +6.6 [-2.4, +23.3]      | 3.74 [1.13, 8.86]    | 0.71 [0.64, 0.79]  | use with caution               |
| 0.1–0.3   | relaxed into a different structure |  92 |                           0 | 64.3 [53.7, 76.2]    | 49.1 [37.9, 61.0]     | 56.4 [46.0, 69.0]     | -56.8 [-69.9, -44.5]    | 5.56 [4.32, 7.06]    | 3.40 [2.64, 4.11]  | not trustworthy                |
| 0.1–0.3   | same structure                     | 408 |                           0 | 20.1 [17.2, 23.2]    | 8.7 [7.6, 9.5]        | 12.8 [11.0, 15.0]     | -11.7 [-15.2, -8.6]     | 2.04 [1.80, 2.32]    | 1.20 [1.02, 1.42]  | trustworthy                    |
| >0.3      | relaxed into a different structure | 169 |                           1 | 503.4 [391.3, 630.5] | 218.8 [196.7, 301.6]  | 309.4 [245.1, 404.9]  | -501.1 [-628.8, -388.2] | 17.32 [12.84, 22.77] | 8.57 [6.78, 10.27] | not trustworthy                |
| >0.3      | same structure                     | 282 |                           1 | 124.5 [96.9, 153.2]  | 22.0 [13.9, 27.7]     | 66.0 [45.1, 89.3]     | -113.6 [-143.5, -85.6]  | 5.39 [4.35, 6.51]    | 2.22 [1.77, 2.73]  | not trustworthy                |

**Single point at the PBE structure** (model energy error with no relaxation in the way):

| bin       |   n |   excluded (guard, per bin) | energy MAE        | energy median |err|   | energy trimmed mean   | mean signed          | energy verdict (pessimistic)   |
|:----------|----:|----------------------------:|:------------------|:----------------------|:----------------------|:---------------------|:-------------------------------|
| ≤0.025    | 500 |                           0 | 6.7 [5.9, 7.6]    | 3.4 [3.0, 4.0]        | 4.6 [4.1, 5.2]        | +4.4 [+3.4, +5.4]    | trustworthy                    |
| 0.025–0.1 | 500 |                           0 | 8.8 [7.8, 9.8]    | 5.3 [4.7, 6.0]        | 6.6 [5.9, 7.3]        | +2.2 [+0.9, +3.4]    | trustworthy                    |
| 0.1–0.3   | 500 |                           0 | 13.2 [11.3, 15.1] | 6.6 [5.5, 7.9]        | 8.9 [7.8, 10.1]       | -0.0 [-2.2, +2.1]    | trustworthy                    |
| >0.3      | 452 |                           0 | 70.6 [54.9, 87.4] | 12.0 [10.6, 14.4]     | 25.0 [19.0, 35.0]     | -53.5 [-71.1, -37.2] | not trustworthy                |

**By chemistry class and swap plausibility** (substituted parent, best start):

| bin       | stratum          |   n |   excluded (guard) | energy MAE           | energy median |err|   | energy trimmed mean   | stays in target structure   |
|:----------|:-----------------|----:|-------------------:|:---------------------|:----------------------|:----------------------|:----------------------------|
| ≤0.025    | metallic         | 150 |                  0 | 5.5 [4.5, 6.5]       | 3.7 [2.8, 4.2]        | 4.3 [3.6, 5.2]        | 99%                         |
| ≤0.025    | compound         | 350 |                  0 | 7.8 [6.3, 9.8]       | 3.5 [3.1, 4.0]        | 4.8 [4.2, 5.6]        | 98%                         |
| ≤0.025    | plausible swap   | 450 |                  0 | 6.5 [5.7, 7.4]       | 3.5 [3.1, 3.9]        | 4.5 [4.0, 5.1]        | 98%                         |
| ≤0.025    | implausible swap |  50 |                  0 | 12.7 [5.9, 24.6]     | 4.6 [2.8, 7.2]        | 6.5 [4.2, 9.6]        | 96%                         |
| 0.025–0.1 | metallic         | 150 |                  0 | 33.9 [8.2, 82.7]     | 5.6 [4.6, 6.8]        | 6.7 [5.5, 8.4]        | 95%                         |
| 0.025–0.1 | compound         | 350 |                  0 | 12.7 [10.6, 15.7]    | 6.0 [5.3, 7.9]        | 8.9 [7.8, 10.3]       | 88%                         |
| 0.025–0.1 | plausible swap   | 450 |                  0 | 11.2 [9.9, 12.6]     | 6.0 [5.3, 7.1]        | 8.2 [7.3, 9.3]        | 90%                         |
| 0.025–0.1 | implausible swap |  50 |                  0 | 90.1 [9.3, 241.7]    | 5.2 [4.0, 11.3]       | 9.0 [5.8, 15.0]       | 92%                         |
| 0.1–0.3   | metallic         | 150 |                  0 | 31.5 [24.9, 39.0]    | 12.7 [9.1, 17.2]      | 20.4 [15.5, 27.4]     | 84%                         |
| 0.1–0.3   | compound         | 350 |                  0 | 26.8 [22.9, 30.8]    | 11.0 [8.9, 13.2]      | 18.4 [15.6, 21.8]     | 81%                         |
| 0.1–0.3   | plausible swap   | 450 |                  0 | 28.1 [24.3, 31.9]    | 11.2 [9.0, 13.1]      | 18.7 [15.9, 22.0]     | 82%                         |
| 0.1–0.3   | implausible swap |  50 |                  0 | 29.3 [19.6, 40.8]    | 20.0 [9.5, 25.9]      | 20.4 [13.8, 30.8]     | 82%                         |
| >0.3      | metallic         | 102 |                  0 | 169.3 [126.3, 213.2] | 46.4 [28.2, 53.8]     | 128.0 [84.7, 174.6]   | 93%                         |
| >0.3      | compound         | 349 |                  1 | 294.9 [234.0, 361.5] | 63.0 [44.1, 98.4]     | 145.8 [117.9, 180.8]  | 53%                         |
| >0.3      | plausible swap   | 401 |                  1 | 279.9 [230.3, 338.9] | 54.3 [46.9, 92.6]     | 146.4 [123.2, 175.6]  | 62%                         |
| >0.3      | implausible swap |  50 |                  0 | 159.2 [88.9, 241.8]  | 27.3 [10.9, 54.0]     | 89.0 [41.2, 156.0]    | 66%                         |

## 3. New materials (WBM calibration set), by hull distance against the MP hull

Energy error MACE − DFT (meV/atom, uncorrected), relaxed from WBM's unrelaxed structure:

| bin       | outcome                            |    n |   excluded (guard, per bin) | energy MAE           | energy median |err|   | energy trimmed mean   | mean signed            | energy verdict (pessimistic)   |
|:----------|:-----------------------------------|-----:|----------------------------:|:---------------------|:----------------------|:----------------------|:-----------------------|:-------------------------------|
| <0        | relaxed into a different structure |   23 |                           1 | 66.0 [29.4, 116.7]   | 25.6 [9.5, 52.3]      | 40.2 [20.5, 90.5]     | +33.7 [-8.3, +90.1]    | not trustworthy                |
| <0        | same structure                     |  587 |                           1 | 12.7 [11.5, 14.2]    | 7.3 [6.4, 8.1]        | 9.7 [8.8, 10.6]       | +3.8 [+2.1, +5.5]      | trustworthy                    |
| 0–0.025   | relaxed into a different structure |   12 |                           0 | 29.3 [12.2, 50.4]    | 10.4 [7.9, 41.1]      | 22.9 [9.2, 48.0]      | +15.8 [-5.9, +42.3]    | use with caution               |
| 0–0.025   | same structure                     |  404 |                           0 | 10.5 [9.3, 11.6]     | 6.6 [5.7, 7.7]        | 8.3 [7.4, 9.3]        | +0.5 [-1.0, +2.1]      | trustworthy                    |
| 0.025–0.1 | relaxed into a different structure |   61 |                           1 | 69.8 [45.7, 104.2]   | 39.3 [19.9, 56.6]     | 49.1 [35.4, 64.6]     | +31.9 [+2.9, +69.1]    | not trustworthy                |
| 0.025–0.1 | same structure                     | 1058 |                           1 | 13.4 [12.5, 14.3]    | 8.5 [7.9, 9.4]        | 10.7 [10.0, 11.4]     | -1.7 [-2.9, -0.5]      | trustworthy                    |
| 0.1–0.3   | relaxed into a different structure |  139 |                           0 | 73.0 [61.8, 85.0]    | 50.1 [40.2, 62.1]     | 62.2 [51.1, 73.5]     | -2.2 [-19.5, +15.0]    | not trustworthy                |
| 0.1–0.3   | same structure                     | 1196 |                           0 | 22.8 [21.3, 24.5]    | 14.6 [13.6, 16.1]     | 17.6 [16.6, 18.7]     | -9.5 [-11.5, -7.5]     | trustworthy                    |
| >0.3      | relaxed into a different structure |   76 |                           0 | 202.4 [155.4, 256.2] | 120.6 [90.0, 168.7]   | 160.4 [121.7, 213.8]  | -133.7 [-196.4, -75.2] | not trustworthy                |
| >0.3      | same structure                     |  442 |                           0 | 64.0 [54.6, 74.1]    | 27.1 [22.0, 30.5]     | 37.9 [32.4, 44.6]     | -48.9 [-59.3, -38.5]   | not trustworthy                |

Single point at WBM's DFT-relaxed structure:

| bin       |    n |   excluded (guard, per bin) | energy MAE        | energy median |err|   | energy trimmed mean   | mean signed          | energy verdict (pessimistic)   |
|:----------|-----:|----------------------------:|:------------------|:----------------------|:----------------------|:---------------------|:-------------------------------|
| <0        |  610 |                           1 | 13.7 [12.3, 15.2] | 8.2 [7.3, 8.9]        | 10.5 [9.5, 11.5]      | +6.3 [+4.6, +7.9]    | trustworthy                    |
| 0–0.025   |  416 |                           0 | 10.7 [9.5, 12.0]  | 6.7 [5.6, 7.7]        | 8.4 [7.4, 9.4]        | +3.5 [+2.0, +5.1]    | trustworthy                    |
| 0.025–0.1 | 1119 |                           1 | 13.2 [12.4, 14.1] | 8.5 [8.0, 9.2]        | 10.4 [9.8, 11.1]      | +2.3 [+1.2, +3.5]    | trustworthy                    |
| 0.1–0.3   | 1335 |                           0 | 20.2 [19.0, 21.4] | 13.6 [12.4, 14.7]     | 16.3 [15.4, 17.1]     | -1.8 [-3.4, -0.3]    | trustworthy                    |
| >0.3      |  518 |                           0 | 49.6 [42.1, 57.1] | 21.8 [19.6, 25.6]     | 30.2 [26.9, 34.0]     | -27.6 [-35.8, -19.4] | use with caution               |

## 4. Stability decisions on new materials (WBM calibration set only)

Positive class = stable (reference energy above the MP hull ≤ 0). A material is called stable when its predicted hull distance (DFT hull distance + MACE − DFT energy, the Matbench Discovery construction) is ≤ the decision threshold. NPV = how often an 'unstable' call is right; DAF = precision ÷ share of stable materials. Intervals: 95 % bootstrap; **the verdict column uses the lower bound.**

Share of stable materials in the calibration set: 0.153 (n=3,998).

| threshold                          |   called stable | precision         | recall            | F1                | NPV                  | DAF               | precision verdict (lower bound)   |
|:-----------------------------------|----------------:|:------------------|:------------------|:------------------|:---------------------|:------------------|:----------------------------------|
| +0 meV/atom (on-hull)              |             619 | 0.83 [0.80, 0.85] | 0.84 [0.81, 0.87] | 0.83 [0.81, 0.85] | 0.971 [0.965, 0.976] | 5.41 [5.06, 5.81] | use with caution                  |
| +0 meV/atom (cost-optimal)         |             619 | 0.83 [0.80, 0.85] | 0.84 [0.81, 0.87] | 0.83 [0.81, 0.85] | 0.971 [0.965, 0.976] | 5.41 [5.06, 5.81] | use with caution                  |
| −50 meV/atom (round-1 exploration) |             222 | 0.93 [0.90, 0.96] | 0.34 [0.30, 0.38] | 0.50 [0.46, 0.54] | 0.893 [0.883, 0.903] | 6.11 [5.67, 6.62] | trustworthy                       |

**Cost-based operating point.** Costs from `config/costs.json`: wasted lab test = 1.0, missed stable material = 1.0 (**placeholders — set real numbers**). Expected cost per screened candidate = (false positives × wasted-test cost + false negatives × missed-material cost) ÷ N, minimised over the threshold sweep. How the optimum moves with the cost ratio:

|   missed stable ÷ wasted lab test |   optimal threshold (meV/atom) |   precision |   recall |   expected cost per candidate |
|----------------------------------:|-------------------------------:|------------:|---------:|------------------------------:|
|                             0.250 |                        -10.000 |       0.902 |    0.710 |                         0.023 |
|                             0.500 |                        -10.000 |       0.902 |    0.710 |                         0.034 |
|                             1.000 |                          0.000 |       0.826 |    0.838 |                         0.052 |
|                             2.000 |                          0.000 |       0.826 |    0.838 |                         0.077 |
|                             4.000 |                         10.000 |       0.699 |    0.923 |                         0.108 |
|                            10.000 |                         20.000 |       0.599 |    0.961 |                         0.158 |

![Precision–recall, calibration set](figures/precision_recall.png)

Threshold sweep (calibration set):

|   threshold |   called_stable |   tp |   fp |   fn |   precision |   recall |    f1 |   npv |   daf |
|------------:|----------------:|-----:|-----:|-----:|------------:|---------:|------:|------:|------:|
|      -0.150 |              33 |   32 |    1 |  578 |       0.970 |    0.052 | 0.100 | 0.854 | 6.355 |
|      -0.100 |              76 |   71 |    5 |  539 |       0.934 |    0.116 | 0.207 | 0.863 | 6.123 |
|      -0.050 |             222 |  207 |   15 |  403 |       0.932 |    0.339 | 0.498 | 0.893 | 6.111 |
|       0.000 |             619 |  511 |  108 |   99 |       0.826 |    0.838 | 0.832 | 0.971 | 5.411 |
|       0.050 |            1490 |  603 |  887 |    7 |       0.405 |    0.989 | 0.574 | 0.997 | 2.652 |
|       0.100 |            2209 |  607 | 1602 |    3 |       0.275 |    0.995 | 0.431 | 0.998 | 1.801 |
|       0.150 |            2744 |  608 | 2136 |    2 |       0.222 |    0.997 | 0.363 | 0.998 | 1.452 |

**Where the calls go wrong, by TRUE hull distance** (share called stable at +0 meV/atom). Precision cannot be computed per true bin (all members share one label); this shows which unstable bins leak into 'stable' calls:

| true bin   |    n | called stable     | reads as            |
|:-----------|-----:|:------------------|:--------------------|
| <0         |  610 | 0.84 [0.81, 0.87] | recall              |
| 0–0.025    |  416 | 0.17 [0.14, 0.20] | false-positive rate |
| 0.025–0.1  | 1119 | 0.02 [0.01, 0.03] | false-positive rate |
| 0.1–0.3    | 1335 | 0.01 [0.00, 0.01] | false-positive rate |
| >0.3       |  518 | 0.02 [0.01, 0.03] | false-positive rate |

**How often a prediction is right, by PREDICTED hull distance** (the view a user has of a new candidate):

| PREDICTED bin   |    n | truly stable      |
|:----------------|-----:|:------------------|
| <0              |  619 | 0.83 [0.79, 0.85] |
| 0–0.025         |  436 | 0.18 [0.15, 0.22] |
| 0.025–0.1       | 1154 | 0.01 [0.01, 0.02] |
| 0.1–0.3         | 1338 | 0.00 [0.00, 0.00] |
| >0.3            |  451 | 0.00 [0.00, 0.01] |

## 5. Cross-check against the published Matbench Discovery numbers

Same model checkpoint (`mace-mpa-0-medium.model (v0.3.9)`), same hull-distance construction, threshold 0. Published: Matbench Discovery, models/mace/mace-mpa-0.yml (unique-prototype subset); their relaxation: FIRE, fmax 0.05 eV/Å, ≤ 500 steps, FrechetCellFilter. Ours: BFGS + FrechetCellFilter, fmax 0.01 eV/Å **and** |stress| ≤ 0.01 GPa, fallback ladder on failure.

| metric         |   Matbench Discovery (published) |   this harness (calibration set) | 95 % CI              | published value inside CI   |
|:---------------|---------------------------------:|---------------------------------:|:---------------------|:----------------------------|
| F1             |                            0.852 |                            0.832 | 0.832 [0.808, 0.853] | yes                         |
| DAF            |                            5.582 |                            5.411 | 5.411 [5.057, 5.809] | yes                         |
| precision      |                            0.853 |                            0.826 | 0.826 [0.795, 0.854] | yes                         |
| recall         |                            0.851 |                            0.838 | 0.838 [0.808, 0.866] | yes                         |
| accuracy       |                            0.954 |                            0.948 | 0.948 [0.941, 0.955] | yes                         |
| MAE (eV/atom)  |                            0.028 |                            0.028 | 0.028 [0.026, 0.030] | yes                         |
| RMSE (eV/atom) |                            0.073 |                            0.069 |                      |                             |
| R2             |                            0.842 |                            0.849 |                      |                             |

Where a published value lies outside our interval, the likely reasons are, in order: (1) our tighter relaxation (5× smaller force tolerance plus an explicit stress criterion) lets structures relax further, which lowers energies of high-energy structures and moves borderline calls; (2) sampling — ours is a 4,000-structure calibration set, theirs the full 215,488; (3) guard-rejected structures are excluded here and counted above.

## 6b. New materials in mode (b): every competing phase relaxed with the engine

297 WBM calibration systems (data/mode_b_sample.json: a fixed number per hull bin, one structure per chemical system). Reference = WBM DFT entry on the current MP GGA/GGA+U hull, MP2020 re-applied to every entry with this pymatgen (so it differs slightly from WBM's shipped hull distance). Mode (a): engine-relaxed target vs MP DFT phases. Mode (b): engine-relaxed target vs engine-relaxed MP phases within 0.1 eV/atom of the MP hull, against the reference on the same phases. Errors in meV/atom.

Status of the mode (b) hulls: complete: 241, scored: off-hull phases missing: 55, not scored: reference hull phase missing: 1.

| bin (reference)   |   systems | mode (a) MAE       | mode (a) median   | mode (a) trimmed   |   mode (b) scored | mode (b) MAE       | mode (b) median   | mode (b) trimmed   |   stand-in only (flagged) | mode (b) verdict (upper bound)   |
|:------------------|----------:|:-------------------|:------------------|:-------------------|------------------:|:-------------------|:------------------|:-------------------|--------------------------:|:---------------------------------|
| <0                |        58 | 15.5 [10.7, 21.7]  | 7.5 [5.4, 13.6]   | 10.9 [8.3, 15.4]   |                58 | 16.2 [11.5, 21.9]  | 8.6 [6.5, 12.0]   | 11.9 [9.2, 16.3]   |                         0 | trustworthy                      |
| 0–0.025           |        57 | 10.1 [7.8, 12.7]   | 7.9 [4.5, 9.8]    | 8.7 [6.6, 11.2]    |                57 | 10.6 [8.1, 13.2]   | 8.1 [5.5, 11.1]   | 9.1 [6.9, 11.8]    |                         0 | trustworthy                      |
| 0.025–0.1         |        61 | 10.7 [8.6, 13.3]   | 9.3 [5.5, 10.6]   | 9.1 [7.2, 11.7]    |                61 | 13.1 [10.2, 16.1]  | 8.9 [6.7, 13.6]   | 11.5 [8.7, 14.7]   |                         0 | trustworthy                      |
| 0.1–0.3           |        62 | 37.8 [25.1, 54.1]  | 17.8 [13.4, 24.1] | 24.6 [17.8, 34.6]  |                62 | 40.4 [27.7, 56.7]  | 18.1 [15.2, 28.5] | 27.6 [20.7, 37.5]  |                         0 | use with caution                 |
| >0.3              |        59 | 94.1 [59.6, 131.5] | 29.6 [23.7, 54.9] | 62.9 [37.6, 96.9]  |                58 | 99.0 [64.6, 139.9] | 30.9 [23.2, 55.7] | 67.8 [41.9, 105.3] |                         0 | not trustworthy                  |

Stable calls at 0 eV/atom on these systems (the sample over-represents stable materials by design — one bin in five is '<0' — so precision here is not the population precision of section 4):

| mode   |   scored | precision         | recall            | F1                | NPV                  |
|:-------|---------:|:------------------|:------------------|:------------------|:---------------------|
| a      |      297 | 0.82 [0.72, 0.92] | 0.81 [0.70, 0.91] | 0.82 [0.73, 0.89] | 0.954 [0.924, 0.979] |
| b      |      296 | 0.78 [0.68, 0.88] | 0.88 [0.79, 0.95] | 0.83 [0.75, 0.89] | 0.970 [0.945, 0.991] |

**Paired comparison** on systems scored in both modes (meV/atom; positive = mode (b) worse):

| bin       |   systems scored in both | |b| − |a| mean    | mode (b) closer   |   mean signed a |   mean signed b |
|:----------|-------------------------:|:------------------|:------------------|----------------:|----------------:|
| <0        |                       58 | +0.7 [-1.5, +2.9] | 52%               |             9.2 |             9.2 |
| 0–0.025   |                       57 | +0.5 [-0.9, +1.9] | 49%               |             0.1 |            -3.2 |
| 0.025–0.1 |                       61 | +2.4 [+0.6, +4.2] | 46%               |            -0.7 |            -6.0 |
| 0.1–0.3   |                       62 | +2.6 [+0.6, +4.6] | 40%               |            -1.4 |            -5.3 |
| >0.3      |                       58 | +3.4 [-0.5, +8.4] | 36%               |           -75.8 |           -80.7 |
| all       |                      296 | +1.9 [+0.8, +3.2] | 45%               |           -13.5 |           -17.0 |

## 6c. Confidence and routing (calibration set, 5-fold cross-validated)

Mondrian split-conformal bounds for the true hull distance, each one-sided at 90% (a 'stable' call uses only the upper bound, an 'unstable' call only the lower bound); groups = chemistry family × predicted hull bin (fallback to family, then all, below 40 members). Chosen over isotonic calibration because it guarantees coverage per group without assuming a monotone, well-behaved error — this model's error is biased and heavy-tailed (see `harness/confidence.py`). Coverage measured on held-out folds (targets: each bound ≥ 0.90, interval ≥ 0.80):

| family        |        n |   upper bound holds |   lower bound holds |   interval holds |   median width (eV/atom) |
|:--------------|---------:|--------------------:|--------------------:|-----------------:|-------------------------:|
| chalcogenide  |  260.000 |               0.904 |               0.900 |            0.804 |                    0.072 |
| f-electron    | 2036.000 |               0.901 |               0.903 |            0.804 |                    0.049 |
| halide        |  195.000 |               0.913 |               0.887 |            0.800 |                    0.085 |
| intermetallic |  733.000 |               0.909 |               0.906 |            0.814 |                    0.067 |
| other         |  301.000 |               0.900 |               0.900 |            0.801 |                    0.079 |
| oxide         |  234.000 |               0.889 |               0.906 |            0.795 |                    0.111 |
| pnictide      |  239.000 |               0.912 |               0.912 |            0.824 |                    0.083 |
| all           | 3998.000 |               0.903 |               0.903 |            0.806 |                    0.071 |

**Why the labels do not come from these bounds.** Routing on them was tried first: the bounds hold ~90 % of the time per group, yet only 97% of the candidates whose upper bound fell below 0 were truly stable — marginal coverage does not control the error rate among the candidates a rule selects. The labels therefore use per-family thresholds certified directly on that quantity (Learn-then-Test style): the loosest threshold whose 'stable' calls have precision ≥ 90%, and the most inclusive whose 'unstable' calls have NPV ≥ 95%, each with a one-sided Clopper–Pearson bound at 95% confidence, Bonferroni-corrected over the 61-point threshold grid. Families with fewer than 100 labelable calibration structures get no label (DFT).

Each held-out structure gets one label from rules fitted on the other folds: 'send to DFT' if it contains a known-weak element (MAE lower bound > 60 meV/atom, or fewer than 20 calibration compounds), if its relaxation left the starting structure, or if its prediction lies between the certified thresholds; otherwise 'likely stable' / 'likely unstable'. The second engine's disagreement signal is added once a second engine has run.

| quantity                                      |   certified thresholds (used) |   conformal bounds (rejected) |
|:----------------------------------------------|------------------------------:|------------------------------:|
| n                                             |                      3998.000 |                      3998.000 |
| likely stable                                 |                       103.000 |                       215.000 |
| likely unstable                               |                      2162.000 |                      2659.000 |
| send to DFT                                   |                      1733.000 |                      1124.000 |
| precision of 'likely stable'                  |                         0.971 |                         0.967 |
| NPV of 'likely unstable'                      |                         0.985 |                         0.990 |
| share sent to DFT                             |                         0.433 |                         0.281 |
| truly stable found as 'likely stable'         |                         0.164 |                         0.341 |
| truly stable sent to DFT                      |                         0.784 |                         0.615 |
| truly stable wrongly called 'likely unstable' |                         0.052 |                         0.044 |

Certified thresholds fitted on the whole calibration set (what the product would use): chalcogenide: stable ≤ —, unstable > — meV/atom (n=224); f-electron: stable ≤ -20, unstable > +10 meV/atom (n=1801); halide: stable ≤ —, unstable > — meV/atom (n=153); intermetallic: stable ≤ —, unstable > +0 meV/atom (n=665); other: stable ≤ —, unstable > +30 meV/atom (n=274); oxide: stable ≤ —, unstable > +30 meV/atom (n=189); pnictide: stable ≤ —, unstable > +50 meV/atom (n=210); weak elements: Be, Pm, Pu, Tc.

Why candidates were sent to DFT (a candidate can have several reasons): low confidence: between the certified thresholds: 1397, relaxation changed the structure: 361, known-weak chemistry: 179.

**How often a plain threshold-0 call is right, by chemistry family and predicted hull distance** (observed on the calibration set; the product shows this next to every prediction):

| family        | predicted bin   |   n | call     | call right        |
|:--------------|:----------------|----:|:---------|:------------------|
| chalcogenide  | 0.025–0.1       |  77 | unstable | 0.99 [0.96, 1.00] |
| chalcogenide  | 0.1–0.3         |  81 | unstable | 1.00 [1.00, 1.00] |
| chalcogenide  | 0–0.025         |  27 | unstable | 0.85 [0.70, 0.96] |
| chalcogenide  | <0              |  41 | stable   | 0.85 [0.73, 0.95] |
| chalcogenide  | >0.3            |  34 | unstable | 0.97 [0.91, 1.00] |
| f-electron    | 0.025–0.1       | 601 | unstable | 0.99 [0.98, 0.99] |
| f-electron    | 0.1–0.3         | 646 | unstable | 1.00 [0.99, 1.00] |
| f-electron    | 0–0.025         | 240 | unstable | 0.81 [0.76, 0.86] |
| f-electron    | <0              | 376 | stable   | 0.85 [0.81, 0.88] |
| f-electron    | >0.3            | 173 | unstable | 1.00 [1.00, 1.00] |
| halide        | 0.025–0.1       |  55 | unstable | 0.98 [0.95, 1.00] |
| halide        | 0.1–0.3         |  30 | unstable | 1.00 [1.00, 1.00] |
| halide        | 0–0.025         |  35 | unstable | 0.89 [0.79, 0.97] |
| halide        | <0              |  65 | stable   | 0.72 [0.62, 0.83] |
| halide        | >0.3            |  10 | unstable | 1.00 [1.00, 1.00] |
| intermetallic | 0.025–0.1       | 219 | unstable | 1.00 [0.99, 1.00] |
| intermetallic | 0.1–0.3         | 264 | unstable | 1.00 [1.00, 1.00] |
| intermetallic | 0–0.025         |  75 | unstable | 0.85 [0.77, 0.93] |
| intermetallic | <0              |  53 | stable   | 0.83 [0.72, 0.92] |
| intermetallic | >0.3            | 122 | unstable | 1.00 [1.00, 1.00] |
| other         | 0.025–0.1       |  65 | unstable | 0.97 [0.92, 1.00] |
| other         | 0.1–0.3         | 137 | unstable | 1.00 [1.00, 1.00] |
| other         | 0–0.025         |  17 | unstable | 0.59 [0.35, 0.82] |
| other         | <0              |  33 | stable   | 0.76 [0.61, 0.91] |
| other         | >0.3            |  49 | unstable | 1.00 [1.00, 1.00] |
| oxide         | 0.025–0.1       |  69 | unstable | 0.99 [0.96, 1.00] |
| oxide         | 0.1–0.3         |  86 | unstable | 1.00 [1.00, 1.00] |
| oxide         | 0–0.025         |  27 | unstable | 0.74 [0.56, 0.89] |
| oxide         | <0              |  23 | stable   | 0.78 [0.61, 0.94] |
| oxide         | >0.3            |  29 | unstable | 1.00 [1.00, 1.00] |
| pnictide      | 0.025–0.1       |  68 | unstable | 0.97 [0.93, 1.00] |
| pnictide      | 0.1–0.3         |  94 | unstable | 1.00 [1.00, 1.00] |
| pnictide      | 0–0.025         |  15 | unstable | 0.93 [0.80, 1.00] |
| pnictide      | <0              |  28 | stable   | 0.86 [0.75, 0.96] |
| pnictide      | >0.3            |  34 | unstable | 1.00 [1.00, 1.00] |

## 7. Errors by element and by magnetism

Error attributed to every element of a compound; elements in fewer than 20 compounds are counted, not shown. Sorted by the upper bound of the MAE.

**New materials (WBM calibration, relaxed energy):** 81 elements shown, 3 below the minimum count.

| element   |   n | MAE meV/atom        | mean signed           | verdict (upper bound)   |
|:----------|----:|:--------------------|:----------------------|:------------------------|
| Pu        | 102 | 104.4 [71.1, 141.2] | -80.3 [-120.3, -44.4] | not trustworthy         |
| Pa        |  23 | 51.7 [8.0, 133.3]   | -41.2 [-124.0, +4.1]  | not trustworthy         |
| Mn        | 242 | 55.0 [43.5, 68.6]   | -29.6 [-43.8, -17.0]  | not trustworthy         |
| Mo        |  40 | 42.2 [24.2, 68.3]   | -22.1 [-51.3, -0.9]   | not trustworthy         |
| Cl        | 101 | 45.6 [28.1, 68.3]   | -3.6 [-23.4, +18.7]   | not trustworthy         |
| I         |  77 | 37.8 [19.1, 65.5]   | -25.4 [-54.6, -5.6]   | not trustworthy         |
| Np        |  75 | 44.7 [29.2, 64.0]   | -21.6 [-44.0, -3.7]   | not trustworthy         |
| N         | 153 | 45.9 [31.9, 63.9]   | -9.2 [-27.4, +9.0]    | not trustworthy         |
| C         | 102 | 38.1 [23.8, 60.8]   | -19.8 [-42.4, -4.0]   | not trustworthy         |
| F         | 129 | 42.6 [28.5, 59.9]   | -18.6 [-37.0, -2.7]   | use with caution        |
| Ta        |  92 | 39.0 [26.6, 53.2]   | -11.1 [-27.8, +4.1]   | use with caution        |
| Yb        | 122 | 34.7 [22.5, 52.9]   | -0.7 [-13.9, +18.7]   | use with caution        |
| P         | 176 | 39.2 [28.1, 52.8]   | -17.5 [-32.3, -5.2]   | use with caution        |
| Cr        | 110 | 39.4 [29.1, 51.3]   | -14.4 [-27.9, -1.6]   | use with caution        |
| Fe        | 296 | 42.6 [34.9, 51.0]   | -26.4 [-35.5, -17.7]  | use with caution        |
| Rh        | 251 | 37.5 [27.4, 49.1]   | -20.2 [-32.4, -9.8]   | use with caution        |
| V         | 114 | 38.3 [29.6, 48.3]   | -20.6 [-31.8, -10.1]  | use with caution        |
| Pb        | 148 | 33.2 [21.7, 48.3]   | -19.0 [-34.7, -6.5]   | use with caution        |
| H         |  89 | 34.6 [25.0, 46.1]   | -17.4 [-30.3, -5.8]   | use with caution        |
| Os        |  78 | 30.6 [19.8, 46.1]   | -7.9 [-25.0, +4.8]    | use with caution        |
| Te        | 137 | 30.0 [19.6, 46.0]   | -11.6 [-28.6, +0.1]   | use with caution        |
| Sr        | 181 | 31.3 [20.0, 45.7]   | -13.6 [-28.1, -1.5]   | use with caution        |
| S         | 187 | 32.0 [22.5, 45.0]   | -13.5 [-27.2, -3.3]   | use with caution        |
| Ba        | 172 | 30.6 [19.8, 45.0]   | -13.1 [-27.7, -1.4]   | use with caution        |
| O         | 471 | 36.3 [30.1, 43.0]   | -12.4 [-19.8, -5.8]   | use with caution        |
| W         |  35 | 29.5 [19.2, 43.0]   | -6.1 [-22.9, +7.7]    | use with caution        |
| Bi        |  93 | 29.4 [20.0, 42.8]   | -12.5 [-27.1, -1.6]   | use with caution        |
| U         | 117 | 32.3 [23.8, 41.7]   | -7.0 [-17.2, +3.4]    | use with caution        |
| Rb        | 118 | 29.2 [19.1, 41.6]   | -18.3 [-31.7, -7.6]   | use with caution        |
| Ca        | 137 | 25.8 [16.4, 40.5]   | -8.9 [-23.8, +1.9]    | use with caution        |
| Eu        |  68 | 26.5 [17.0, 40.0]   | -2.8 [-17.4, +8.9]    | use with caution        |
| As        | 166 | 29.8 [22.4, 39.7]   | -4.4 [-14.7, +4.7]    | use with caution        |
| Sb        | 141 | 28.5 [20.6, 38.7]   | -5.9 [-16.4, +3.1]    | use with caution        |
| Ho        | 128 | 26.9 [18.6, 37.9]   | -8.9 [-20.9, +0.5]    | use with caution        |
| Si        | 260 | 29.0 [23.3, 36.4]   | -7.4 [-14.9, -0.3]    | use with caution        |
| Co        | 237 | 28.1 [22.2, 35.7]   | -9.7 [-17.3, -2.2]    | use with caution        |
| Tm        | 126 | 25.4 [17.0, 35.1]   | -13.3 [-24.0, -4.3]   | use with caution        |
| Se        | 154 | 24.2 [16.9, 33.9]   | +0.9 [-7.4, +11.2]    | use with caution        |
| Ce        | 129 | 24.9 [17.5, 33.8]   | +0.5 [-9.7, +9.0]     | use with caution        |
| Pd        | 226 | 25.6 [18.9, 33.8]   | -3.4 [-11.2, +4.8]    | use with caution        |
| Th        | 133 | 25.7 [19.2, 33.6]   | -6.9 [-15.0, +1.9]    | use with caution        |
| Na        |  96 | 22.1 [13.7, 33.6]   | +0.7 [-9.0, +13.1]    | use with caution        |
| Ni        | 312 | 24.9 [17.9, 33.1]   | -14.6 [-23.3, -7.1]   | use with caution        |
| Au        | 161 | 21.5 [14.3, 32.9]   | -10.2 [-22.5, -2.0]   | use with caution        |
| Tl        | 137 | 22.7 [14.6, 32.8]   | -1.6 [-10.8, +9.6]    | use with caution        |
| Ge        | 267 | 25.7 [20.1, 32.7]   | -9.1 [-16.7, -2.9]    | use with caution        |
| Nb        | 105 | 26.4 [21.1, 32.6]   | -7.2 [-14.6, +0.7]    | use with caution        |
| Y         | 125 | 23.9 [17.0, 32.5]   | -12.1 [-21.3, -4.7]   | use with caution        |
| Sc        | 129 | 23.1 [16.0, 32.4]   | -0.0 [-8.3, +10.1]    | use with caution        |
| B         | 154 | 27.9 [24.0, 32.3]   | -9.1 [-14.8, -3.2]    | use with caution        |
| Ir        | 173 | 24.9 [19.5, 31.6]   | -0.3 [-7.4, +6.9]     | use with caution        |
| Cd        | 132 | 21.4 [13.6, 31.2]   | -13.3 [-23.5, -4.8]   | use with caution        |
| Re        |  24 | 22.4 [15.2, 31.1]   | -3.8 [-14.9, +8.2]    | use with caution        |
| Ti        | 119 | 23.2 [16.8, 30.7]   | -10.2 [-18.4, -2.6]   | use with caution        |
| Br        |  89 | 23.1 [16.9, 30.4]   | -8.9 [-17.2, -1.2]    | use with caution        |
| Zr        | 126 | 23.9 [18.9, 30.2]   | -10.6 [-17.9, -4.5]   | use with caution        |
| In        | 287 | 24.4 [19.4, 30.2]   | -7.5 [-14.0, -1.5]    | use with caution        |
| Dy        | 123 | 22.3 [15.7, 29.6]   | -2.9 [-11.0, +4.8]    | trustworthy             |
| Cu        | 289 | 22.1 [16.1, 29.3]   | -12.8 [-20.5, -6.4]   | trustworthy             |
| Cs        | 110 | 21.9 [16.6, 28.2]   | -7.9 [-15.1, -1.5]    | trustworthy             |
| Sn        | 249 | 23.5 [19.3, 28.0]   | -12.4 [-17.6, -7.5]   | trustworthy             |
| Hf        | 104 | 22.0 [17.3, 27.7]   | -7.3 [-14.2, -0.9]    | trustworthy             |
| K         | 134 | 20.7 [15.2, 26.7]   | -6.8 [-13.7, -0.1]    | trustworthy             |
| Er        | 122 | 19.6 [14.3, 26.3]   | -2.6 [-9.0, +4.8]     | trustworthy             |
| Pr        | 129 | 20.0 [15.0, 26.3]   | -5.5 [-12.4, +0.8]    | trustworthy             |
| Pt        | 235 | 21.1 [16.6, 26.3]   | -7.0 [-12.6, -1.8]    | trustworthy             |
| Ru        | 173 | 21.5 [17.2, 26.3]   | -5.8 [-11.3, -0.7]    | trustworthy             |
| Ag        | 113 | 18.6 [12.1, 26.0]   | -0.2 [-7.5, +8.5]     | trustworthy             |
| Li        | 140 | 19.8 [14.5, 25.9]   | -4.4 [-11.5, +1.7]    | trustworthy             |
| Mg        | 194 | 19.7 [15.1, 25.1]   | -6.1 [-12.2, -0.8]    | trustworthy             |
| Nd        | 128 | 18.1 [13.1, 24.9]   | -0.6 [-6.4, +7.0]     | trustworthy             |
| Ga        | 267 | 18.1 [13.7, 24.8]   | -4.9 [-11.6, +0.1]    | trustworthy             |
| La        | 134 | 17.8 [13.0, 24.3]   | -1.9 [-8.9, +3.8]     | trustworthy             |
| Tb        | 144 | 18.8 [14.1, 24.0]   | -6.8 [-12.4, -1.4]    | trustworthy             |
| Lu        |  88 | 17.8 [13.0, 23.6]   | -6.8 [-13.3, -0.6]    | trustworthy             |
| Zn        | 222 | 18.7 [15.1, 22.9]   | -3.4 [-8.1, +1.0]     | trustworthy             |
| Ac        |  24 | 15.4 [9.6, 22.2]    | -0.9 [-9.8, +8.1]     | trustworthy             |
| Sm        | 118 | 17.5 [13.5, 22.2]   | -4.8 [-10.1, +0.8]    | trustworthy             |
| Al        | 317 | 17.8 [14.6, 21.8]   | -4.0 [-7.7, +0.5]     | trustworthy             |
| Gd        |  79 | 14.3 [10.1, 19.5]   | -0.8 [-6.6, +4.8]     | trustworthy             |
| Hg        |  79 | 14.4 [10.7, 18.8]   | -2.1 [-7.2, +2.9]     | trustworthy             |

**Known materials (MP pairs, control, same structure):** 69 elements shown, 16 below the minimum count.

| element   |   n | MAE meV/atom         | mean signed             | verdict (upper bound)   |
|:----------|----:|:---------------------|:------------------------|:------------------------|
| Gd        |  48 | 194.8 [126.5, 265.8] | -191.9 [-264.1, -122.9] | not trustworthy         |
| Zr        |  32 | 57.7 [10.4, 133.3]   | -49.3 [-128.6, -0.9]    | not trustworthy         |
| Pb        |  27 | 51.0 [7.0, 107.2]    | -46.2 [-103.5, -2.2]    | not trustworthy         |
| Ho        |  58 | 45.4 [4.2, 106.6]    | -41.3 [-102.8, +0.0]    | not trustworthy         |
| Eu        |  28 | 41.4 [9.5, 95.7]     | -33.8 [-89.3, -0.4]     | not trustworthy         |
| F         |  76 | 43.1 [13.9, 89.7]    | -29.6 [-76.5, +0.7]     | not trustworthy         |
| Ir        |  36 | 36.2 [8.4, 86.9]     | -23.3 [-76.4, +6.3]     | not trustworthy         |
| Mn        | 112 | 59.9 [37.7, 85.2]    | -51.5 [-77.2, -28.9]    | not trustworthy         |
| U         |  23 | 34.7 [10.8, 79.7]    | -16.5 [-64.4, +10.6]    | not trustworthy         |
| Cr        | 105 | 40.5 [15.9, 78.6]    | -28.3 [-67.0, -3.4]     | not trustworthy         |
| V         |  90 | 40.3 [18.5, 73.7]    | -32.0 [-67.3, -9.9]     | not trustworthy         |
| Ni        | 138 | 51.2 [32.0, 73.4]    | -36.3 [-59.8, -16.3]    | not trustworthy         |
| Ru        |  33 | 28.3 [5.0, 72.2]     | -20.5 [-65.1, +3.5]     | not trustworthy         |
| Co        | 143 | 49.9 [31.3, 70.1]    | -38.1 [-59.1, -19.1]    | not trustworthy         |
| Rh        |  34 | 31.7 [5.7, 68.5]     | -21.1 [-58.8, +5.7]     | not trustworthy         |
| P         |  88 | 40.6 [20.3, 65.2]    | -33.1 [-58.8, -12.4]    | not trustworthy         |
| W         |  74 | 30.3 [11.5, 60.2]    | -24.4 [-54.4, -5.4]     | not trustworthy         |
| Ag        |  38 | 27.2 [5.1, 59.5]     | -24.0 [-56.5, -1.4]     | use with caution        |
| Ce        |  49 | 32.9 [14.3, 57.6]    | -20.3 [-46.5, -0.3]     | use with caution        |
| Pt        |  28 | 26.6 [8.9, 55.5]     | -19.0 [-47.9, +0.1]     | use with caution        |
| Tl        |  22 | 23.0 [5.2, 55.1]     | -17.9 [-51.2, +1.1]     | use with caution        |
| Pd        |  40 | 21.5 [6.6, 48.9]     | -13.5 [-41.9, +2.4]     | use with caution        |
| La        |  64 | 27.5 [12.6, 48.8]    | -19.3 [-40.7, -3.5]     | use with caution        |
| Mo        |  65 | 27.2 [12.4, 48.4]    | -20.8 [-42.2, -5.6]     | use with caution        |
| Ga        |  68 | 29.2 [14.7, 47.9]    | -23.1 [-42.5, -8.3]     | use with caution        |
| O         | 630 | 35.4 [25.7, 46.8]    | -25.3 [-36.9, -15.6]    | use with caution        |
| Pr        |  51 | 19.7 [5.1, 46.7]     | -14.7 [-42.0, +0.6]     | use with caution        |
| Fe        | 157 | 31.9 [21.4, 45.0]    | -16.6 [-31.0, -5.5]     | use with caution        |
| Te        |  44 | 24.5 [11.6, 44.4]    | -14.0 [-34.7, +0.0]     | use with caution        |
| Er        |  50 | 19.1 [4.1, 43.3]     | -14.7 [-38.4, +0.7]     | use with caution        |
| Bi        |  81 | 23.1 [11.6, 42.3]    | -17.6 [-37.2, -5.6]     | use with caution        |
| Nd        |  67 | 26.0 [11.5, 42.3]    | -20.4 [-37.2, -5.5]     | use with caution        |
| Sn        |  71 | 20.8 [9.2, 42.1]     | -13.8 [-35.3, -1.3]     | use with caution        |
| Y         |  74 | 27.8 [16.3, 42.0]    | -20.1 [-35.6, -7.9]     | use with caution        |
| Li        | 122 | 24.8 [13.6, 39.0]    | -16.5 [-32.2, -4.9]     | use with caution        |
| Mg        | 271 | 26.8 [18.9, 36.4]    | -20.3 [-30.2, -12.1]    | use with caution        |
| Sr        |  70 | 21.3 [10.2, 35.6]    | -14.2 [-29.4, -2.3]     | use with caution        |
| As        |  23 | 18.8 [7.1, 34.1]     | -9.2 [-26.4, +4.6]      | use with caution        |
| C         |  61 | 17.3 [7.9, 33.0]     | -7.3 [-23.3, +3.1]      | use with caution        |
| Cu        | 135 | 17.5 [8.0, 30.9]     | -11.4 [-24.7, -1.6]     | use with caution        |
| Tb        |  48 | 17.1 [7.6, 29.6]     | -13.5 [-26.6, -3.2]     | trustworthy             |
| Sc        |  24 | 13.4 [4.0, 29.3]     | -1.6 [-18.4, +8.8]      | trustworthy             |
| Si        |  89 | 16.6 [8.7, 27.6]     | -8.6 [-19.8, -0.0]      | trustworthy             |
| Ca        |  70 | 17.1 [9.9, 25.8]     | -10.0 [-19.1, -2.2]     | trustworthy             |
| In        |  44 | 13.7 [5.3, 25.5]     | -8.6 [-20.7, +0.2]      | trustworthy             |
| Cl        |  35 | 14.2 [6.5, 24.2]     | -9.0 [-19.9, -0.6]      | trustworthy             |
| Os        |  21 | 13.6 [6.3, 23.6]     | -12.6 [-22.9, -4.9]     | trustworthy             |
| Rb        |  29 | 13.9 [6.2, 23.4]     | -6.0 [-16.5, +3.1]      | trustworthy             |
| Ti        | 103 | 14.2 [8.4, 23.3]     | -7.2 [-16.7, -0.8]      | trustworthy             |
| Na        |  44 | 15.2 [9.6, 22.6]     | -5.7 [-14.2, +1.1]      | trustworthy             |
| Al        | 101 | 12.2 [6.7, 21.9]     | -5.0 [-15.0, +1.1]      | trustworthy             |
| K         |  43 | 13.0 [6.6, 21.4]     | -5.4 [-14.1, +1.6]      | trustworthy             |
| Lu        |  21 | 11.1 [5.2, 19.7]     | -2.5 [-12.0, +4.8]      | trustworthy             |
| Ta        |  21 | 13.7 [8.1, 19.6]     | -3.6 [-11.5, +4.2]      | trustworthy             |
| Ba        |  88 | 14.3 [10.2, 19.5]    | -4.7 [-10.2, +0.0]      | trustworthy             |
| N         | 106 | 15.0 [11.6, 18.5]    | -4.9 [-9.0, -0.6]       | trustworthy             |
| Sm        |  48 | 11.1 [5.8, 17.4]     | -3.2 [-10.1, +2.8]      | trustworthy             |
| Zn        |  69 | 13.1 [10.0, 16.6]    | +2.4 [-2.0, +6.9]       | trustworthy             |
| Se        |  77 | 10.5 [5.8, 16.4]     | -3.1 [-9.5, +2.3]       | trustworthy             |
| Ge        |  55 | 10.0 [5.4, 16.4]     | -1.8 [-9.1, +3.5]       | trustworthy             |
| Tm        |  35 | 8.2 [3.7, 14.5]      | +2.5 [-2.7, +9.4]       | trustworthy             |
| Cd        |  33 | 7.8 [4.1, 13.4]      | +2.0 [-2.5, +8.8]       | trustworthy             |
| Nb        |  60 | 10.2 [7.7, 13.4]     | -5.7 [-9.6, -2.3]       | trustworthy             |
| B         |  65 | 8.1 [4.3, 13.3]      | -3.1 [-8.6, +1.1]       | trustworthy             |
| Cs        |  33 | 8.2 [4.5, 13.3]      | +0.7 [-5.1, +5.6]       | trustworthy             |
| Sb        |  66 | 9.5 [6.9, 12.8]      | -3.4 [-7.1, +0.1]       | trustworthy             |
| S         | 115 | 9.7 [7.1, 12.7]      | +0.2 [-3.2, +3.2]       | trustworthy             |
| Au        |  35 | 6.8 [4.8, 9.1]       | +1.3 [-2.1, +4.4]       | trustworthy             |
| Dy        |  68 | 5.8 [3.8, 8.7]       | -1.5 [-4.7, +0.9]       | trustworthy             |

**Magnetic vs non-magnetic (MP pairs; moment > 0.05 μB/site in the PBE calculation), control energy, same structure only:**

| bin       | mag                 |   n |   excluded (guard, per bin) | energy MAE           | energy median |err|   | energy trimmed mean   | mean signed             | energy verdict (pessimistic)   |
|:----------|:--------------------|----:|----------------------------:|:---------------------|:----------------------|:----------------------|:------------------------|:-------------------------------|
| ≤0.025    | magnetic in PBE     | 156 |                           0 | 10.8 [9.1, 12.7]     | 5.9 [4.7, 7.3]        | 8.6 [7.0, 10.5]       | +6.1 [+3.6, +8.5]       | trustworthy                    |
| ≤0.025    | non-magnetic in PBE | 336 |                           0 | 4.5 [3.8, 5.3]       | 2.8 [2.5, 3.4]        | 3.4 [3.0, 3.8]        | +0.8 [+0.1, +1.7]       | trustworthy                    |
| 0.025–0.1 | magnetic in PBE     | 220 |                           0 | 11.3 [9.7, 13.1]     | 7.4 [5.7, 8.2]        | 8.8 [7.6, 10.2]       | +0.2 [-2.1, +2.4]       | trustworthy                    |
| 0.025–0.1 | non-magnetic in PBE | 247 |                           0 | 7.6 [6.5, 8.9]       | 4.6 [3.9, 5.2]        | 5.8 [5.0, 6.8]        | -2.8 [-4.3, -1.4]       | trustworthy                    |
| 0.1–0.3   | magnetic in PBE     | 236 |                           1 | 22.8 [18.7, 27.1]    | 9.5 [8.3, 11.9]       | 15.0 [12.4, 18.4]     | -12.7 [-17.5, -7.8]     | trustworthy                    |
| 0.1–0.3   | non-magnetic in PBE | 189 |                           1 | 15.4 [12.0, 19.2]    | 7.1 [5.6, 8.8]        | 10.0 [8.1, 12.1]      | -8.6 [-12.7, -4.8]      | trustworthy                    |
| >0.3      | magnetic in PBE     | 174 |                           5 | 153.4 [118.9, 191.1] | 31.1 [20.0, 45.5]     | 103.5 [73.1, 137.5]   | -138.7 [-177.4, -103.1] | not trustworthy                |
| >0.3      | non-magnetic in PBE | 152 |                           5 | 59.9 [34.6, 88.5]    | 10.7 [7.7, 16.8]      | 19.2 [14.5, 30.5]     | -54.5 [-83.4, -29.1]    | not trustworthy                |

WBM entries carry no magnetic moments, so new materials cannot be split this way.

## 8. Worst cases

Likely causes by fixed rules, checked in this order: far above the hull, relaxed into a different structure, then chemistry.

| case                        | set        |   true e_hull |   energy error | likely cause                                                                                                                                                                                                                 |
|:----------------------------|:-----------|--------------:|---------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SrMn3 (wbm-1-29349)         | new (WBM)  |         1.286 |       -909.692 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; new composition/prototype (not in MPtrj)                                          |
| PaCI (wbm-3-11693)          | new (WBM)  |         0.782 |       -905.065 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; f-electron chemistry (Pa); new composition/prototype (not in MPtrj)               |
| Ca2SN2 (wbm-3-43639)        | new (WBM)  |         0.955 |       -866.874 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; new composition/prototype (not in MPtrj)                                          |
| YbNCl (wbm-2-29485)         | new (WBM)  |         0.067 |        861.680 | relaxed into a different structure; f-electron chemistry (Yb); new composition/prototype (not in MPtrj)                                                                                                                      |
| BaNiTeF (wbm-1-16705)       | new (WBM)  |         0.557 |       -859.382 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; +U transition-metal oxide/fluoride (Ni); new composition/prototype (not in MPtrj) |
| PuPAu (wbm-3-58223)         | new (WBM)  |         0.985 |       -809.495 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; f-electron chemistry (Pu); new composition/prototype (not in MPtrj)               |
| PuRhPb (wbm-3-61987)        | new (WBM)  |         0.669 |       -698.883 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; f-electron chemistry (Pu); new composition/prototype (not in MPtrj)                                                   |
| PuGaCu (wbm-3-20588)        | new (WBM)  |         0.697 |       -674.426 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; f-electron chemistry (Pu); new composition/prototype (not in MPtrj)                                                   |
| Ba2Ni3(AsO)2 (wbm-1-37417)  | new (WBM)  |         0.667 |       -600.470 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; +U transition-metal oxide/fluoride (Ni); new composition/prototype (not in MPtrj)                                     |
| PuMnRh4 (wbm-5-13450)       | new (WBM)  |         0.685 |       -560.027 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; f-electron chemistry (Pu); new composition/prototype (not in MPtrj)                                                   |
| LiMnVP2(HO5)2 (mp-aaadbebn) | known (MP) |         4.074 |      -3692.329 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; magnetic in the PBE calculation (MACE has no spin)                                |
| SrZnCu(PO4)2 (mp-aaacyopr)  | known (MP) |         3.647 |      -3593.948 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; +U transition-metal oxide/fluoride (Cu)                                           |
| SrZnCr(PO4)2 (mp-aaacygqn)  | known (MP) |         3.582 |      -3488.188 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; +U transition-metal oxide/fluoride (Cr)                                           |
| VPO4F (mp-aaabuoih)         | known (MP) |         3.622 |      -3447.970 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; magnetic in the PBE calculation (MACE has no spin)                                |
| SrMgV(PO4)2 (mp-aaadagpv)   | known (MP) |         3.516 |      -3406.447 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; +U transition-metal oxide/fluoride (V)                                            |
| Ti2N2O (mp-aaabwpjb)        | known (MP) |         3.798 |      -3402.360 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure                                                                                    |
| Li4WO5 (mp-aaabpngx)        | known (MP) |         3.578 |      -3319.270 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; magnetic in the PBE calculation (MACE has no spin)                                |
| SnPHO5 (mp-aaadcgmn)        | known (MP) |         3.171 |      -3162.828 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure                                                                                    |
| TiPHO5 (mp-aaabstxh)        | known (MP) |         3.349 |      -2906.740 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; magnetic in the PBE calculation (MACE has no spin)                                |
| Li2Mn5(PO4)4 (mp-aaabvhnr)  | known (MP) |         2.211 |      -2157.352 | far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model; relaxed into a different structure; magnetic in the PBE calculation (MACE has no spin)                                |

## 9. Lattice constants against experiment

Room-temperature and 0 K values include thermal and zero-point expansion; the Csonka set removes the zero-point anharmonic expansion, so it is the fair target for a static 0 K calculation. PBE overestimates by ~1 %, and MACE inherits that. **Coverage gap:** oxides are represented by MgO only, and no bcc transition metals (V, Nb, Ta, Mo, W, Fe) have a verified source in the harness yet. Results rejected by the guard: 0 (excluded from every average below).

| set                                             | class      |   n |   excluded (guard) |   MACE vs exp mean % |   MACE vs exp MAE % |   MACE vs exp median |%| |   MACE vs exp trimmed MAE % |   PBE vs exp mean % |   MACE − PBE mean % |
|:------------------------------------------------|:-----------|----:|-------------------:|---------------------:|--------------------:|-------------------------:|----------------------------:|--------------------:|--------------------:|
| room temperature (Lucero 2012)                  | non-metals |  33 |                  0 |                 1.22 |                1.23 |                     1.08 |                        1.17 |                1.23 |               -0.01 |
| 0 K extrapolated (Lucero 2012)                  | non-metals |   6 |                  0 |                 0.92 |                0.92 |                     0.88 |                        0.92 |                1.04 |               -0.12 |
| 0 K, zero-point expansion removed (Csonka 2009) | metals     |  14 |                  0 |                 1.93 |                2.16 |                     0.94 |                        1.15 |                0.83 |                1.09 |
| 0 K, zero-point expansion removed (Csonka 2009) | non-metals |  10 |                  0 |                 2.00 |                2.00 |                     1.76 |                        1.94 |                1.84 |                0.16 |

| material   | structure   | status       |   a_exp |   a_mace |   a_pbe |   a_err_pct |   a_pbe_err_pct |   a_mace_vs_pbe_pct |
|:-----------|:------------|:-------------|--------:|---------:|--------:|------------:|----------------:|--------------------:|
| Cs         | bcc         | zpae_removed |   6.039 |    7.026 |   6.110 |      16.345 |           1.176 |              14.992 |
| NaF        | rs          | zpae_removed |   4.579 |    4.741 |   4.696 |       3.537 |           2.561 |               0.952 |
| LiF        | rs          | zpae_removed |   3.964 |    4.100 |   4.083 |       3.431 |           3.013 |               0.406 |
| CdSe       | zb          | rt           |   6.052 |    6.235 |   6.213 |       3.023 |           2.658 |               0.356 |
| CdTe       | zb          | rt           |   6.480 |    6.654 |   6.629 |       2.678 |           2.300 |               0.369 |
| NaCl       | rs          | zpae_removed |   5.565 |    5.714 |   5.692 |       2.669 |           2.277 |               0.384 |
| Ag         | fcc         | zpae_removed |   4.056 |    4.162 |   4.161 |       2.602 |           2.578 |               0.024 |
| LiCl       | rs          | zpae_removed |   5.056 |    5.184 |   5.153 |       2.522 |           1.914 |               0.597 |
| InAs       | zb          | rt           |   6.058 |    6.195 |   6.181 |       2.267 |           2.038 |               0.224 |
| CdS        | zb          | rt           |   5.818 |    5.948 |   5.941 |       2.233 |           2.111 |               0.120 |
| Pd         | fcc         | zpae_removed |   3.875 |    3.960 |   3.957 |       2.182 |           2.118 |               0.063 |
| InSb       | zb          | rt           |   6.479 |    6.611 |   6.633 |       2.043 |           2.380 |              -0.330 |
| Pb         | fcc         | zpae_removed |   4.902 |    5.001 |   5.051 |       2.017 |           3.030 |              -0.983 |
| ZnTe       | zb          | rt           |   6.089 |    6.205 |   6.185 |       1.906 |           1.574 |               0.327 |
| InP        | zb          | rt           |   5.869 |    5.979 |   5.957 |       1.874 |           1.495 |               0.374 |
| K          | bcc         | zpae_removed |   5.212 |    5.309 |   5.262 |       1.855 |           0.962 |               0.885 |
| GaAs       | zb          | zpae_removed |   5.638 |    5.739 |   5.750 |       1.792 |           1.990 |              -0.193 |
| GaSb       | zb          | rt           |   6.096 |    6.203 |   6.219 |       1.752 |           2.019 |              -0.261 |
| MgO        | rs          | zpae_removed |   4.184 |    4.256 |   4.256 |       1.733 |           1.732 |               0.000 |
| GaAs       | zb          | zero_k       |   5.648 |    5.739 |   5.750 |       1.612 |           1.809 |              -0.193 |

## 10. Bulk modulus (curated known materials)

Birch–Murnaghan fits vs MP elastic K_VRH: MAE 11.9 [8.2, 16.8] % (n=82), median |err| 7.3 [4.2, 8.0] %, 10% trimmed mean 8.1 [6.2, 10.5] %; verdict use with caution (from the MAE's pessimistic bound). Not stratified by hull distance: every material is on or near the hull. EOS points rejected by the convergence / sanity / energy guard never enter a fit; a fit needs at least 7 usable points.

Exclusions, stated in full: 0 of 83 fits excluded for fit quality (RMS > 1.0 meV/atom or V0 outside the sampled range); 1 excluded for an impossible MP REFERENCE (K_VRH outside (0, 600] GPa — above diamond's ~443 GPa): K (mp-aaaaaacg): K_VRH 33,306 GPa next to K_Reuss 3.7 GPa. Keeping it the MAE is 13.0 [8.9, 18.2] % over n=83; that number measures MP's Voigt average, not this engine, which is why the verdict does not use it.

## 11. Runtime and job outcomes

| suite             |   structures |   median |   p90 |   total_h |
|:------------------|-------------:|---------:|------:|----------:|
| bulk              |           83 |      0.3 |   1.4 |       0.0 |
| experimental      |           63 |      0.1 |   0.3 |       0.0 |
| ood               |        12000 |      0.5 |   3.2 |       4.4 |
| stability         |         5558 |      0.9 |   8.8 |       8.8 |
| substitution      |           50 |      0.1 |   0.8 |       0.0 |
| substitution_auto |         7808 |      1.7 |  20.2 |      15.0 |

| suite             |   failed |    ok |   skipped |
|:------------------|---------:|------:|----------:|
| bulk              |        0 |    83 |        13 |
| experimental      |        0 |    63 |         1 |
| mode_b            |        3 |   297 |         0 |
| ood               |        0 | 12000 |         0 |
| stability         |        0 |  5558 |         0 |
| substitution      |        0 |    50 |         0 |
| substitution_auto |        0 |  7808 |         0 |

## Files

* `results/results.sqlite` — every job and result with provenance and settings
* `results/results.parquet` — the results table
* `data/wbm_split.json` — the calibration / locked-test split
* `figures/` and `scorecard.json` next to this report

