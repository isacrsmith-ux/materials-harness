# Phase 3 — engine screening

Paired comparison on the fixed screening subset (`data/screening_subset.json`: 125 MP pairs per hull bin + 500 WBM calibration structures; the locked test set is not used). Ranked by the upper bound of the expected cost per screened candidate at each engine's cost-optimal threshold (costs in `config/costs.json`: wasted lab test 1.0, missed stable material 1.0), then by the lower bound of precision. Engines whose training data is not verified free of WBM ('compliant' ≠ True) may look better on WBM than they are.

| model             | status                                               | setting     | compliant   | WBM done / rejected   |   cost-optimal threshold (meV/atom) | expected cost per candidate   | precision at that threshold   | recall            |   F1 at 0 |
|:------------------|:-----------------------------------------------------|:------------|:------------|:----------------------|------------------------------------:|:------------------------------|:------------------------------|:------------------|----------:|
| MACE-MPA-0 medium | complete                                             | cpu/float32 | True        | 500 / 0               |                               0.000 | 0.050 [0.032, 0.070]          | 0.83 [0.75, 0.91]             | 0.84 [0.76, 0.92] |     0.837 |
| MACE-MP-0 medium  | complete                                             | cpu/float64 | True        | 500 / 1               |                             -30.000 | 0.102 [0.078, 0.128]          | 0.71 [0.60, 0.83]             | 0.53 [0.42, 0.64] |     0.671 |
| eSEN-30M-OAM      | incomplete (1/500 WBM, 51/500 pairs) — not ranked    | cpu/float32 | True        | 1 / 0                 |                            -200.000 | 0.000 [0.000, 0.000]          | n/a                           | n/a               |   nan     |
| SevenNet-Omni     | incomplete (359/500 WBM, 441/500 pairs) — not ranked | mps/float32 | unverified  | 359 / 0               |                               0.000 | 0.042 [0.022, 0.061]          | 0.86 [0.77, 0.94]             | 0.90 [0.82, 0.97] |     0.878 |

Energy MAE (meV/atom) by hull bin — 'new' = WBM screening structures (relaxed energy), 'known' = MP pairs whose control stays in the target structure:

| model             | new <0            | new 0–0.025       | new 0.025–0.1     | new 0.1–0.3       | new >0.3             | new all           | known ≤0.025     | known 0.025–0.1   | known 0.1–0.3     | known >0.3          |
|:------------------|:------------------|:------------------|:------------------|:------------------|:---------------------|:------------------|:-----------------|:------------------|:------------------|:--------------------|
| MACE-MPA-0 medium | 16.6 [10.9, 23.0] | 13.9 [8.6, 20.6]  | 17.2 [13.9, 21.0] | 33.0 [25.5, 41.2] | 87.0 [54.8, 126.0]   | 31.1 [25.7, 37.2] | 6.0 [4.7, 7.3]   | 9.4 [7.5, 11.5]   | 18.0 [13.2, 23.8] | 122.4 [69.0, 184.2] |
| MACE-MP-0 medium  | 44.2 [29.2, 61.8] | 23.8 [14.7, 38.8] | 37.7 [31.4, 44.4] | 63.9 [55.8, 72.6] | 142.4 [102.6, 187.8] | 59.6 [52.4, 67.5] | 11.1 [8.8, 13.8] | 13.4 [10.7, 16.6] | 17.4 [14.0, 21.4] | 144.6 [90.3, 208.7] |
| eSEN-30M-OAM      | n/a               | n/a               | n/a               | 11.3 [11.3, 11.3] | n/a                  | 11.3 [11.3, 11.3] | 6.1 [2.4, 11.3]  | 9.6 [4.8, 15.0]   | 4.8 [1.3, 9.1]    | 20.0 [9.1, 30.9]    |
| SevenNet-Omni     | 7.1 [5.2, 9.4]    | 5.2 [3.4, 7.3]    | 12.0 [8.5, 16.1]  | 25.0 [17.7, 34.0] | 100.1 [43.7, 171.2]  | 23.5 [16.7, 31.5] | 4.9 [3.8, 6.2]   | 8.3 [6.6, 10.3]   | 12.2 [7.6, 18.3]  | 89.9 [45.1, 142.2]  |

