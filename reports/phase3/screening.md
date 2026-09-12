# Phase 3 — engine screening

Paired comparison on the fixed screening subset (`data/screening_subset.json`: 125 MP pairs per hull bin + 500 WBM calibration structures; the locked test set is not used). Ranked by the upper bound of the expected cost per screened candidate at each engine's cost-optimal threshold (costs in `config/costs.json`: wasted lab test 1.0, missed stable material 1.0), then by the lower bound of precision. Engines whose training data is not verified free of WBM ('compliant' ≠ True) may look better on WBM than they are; `reports/leakage_check.md` works through the evidence for SevenNet-Omni, the only such engine here, and it is not adopted on this ranking.

| model             | status                                            | setting     | compliant   | WBM done / rejected   |   cost-optimal threshold (meV/atom) | expected cost per candidate   | precision at that threshold   | recall            |   F1 at 0 |
|:------------------|:--------------------------------------------------|:------------|:------------|:----------------------|------------------------------------:|:------------------------------|:------------------------------|:------------------|----------:|
| SevenNet-Omni     | complete                                          | mps/float32 | unverified  | 500 / 0               |                               0.000 | 0.036 [0.020, 0.054]          | 0.86 [0.78, 0.93]             | 0.91 [0.84, 0.97] |     0.885 |
| MACE-MPA-0 medium | complete                                          | cpu/float32 | True        | 500 / 0               |                               0.000 | 0.050 [0.032, 0.070]          | 0.83 [0.75, 0.91]             | 0.84 [0.76, 0.92] |     0.837 |
| MACE-MP-0 medium  | complete                                          | cpu/float64 | True        | 500 / 1               |                             -30.000 | 0.102 [0.078, 0.128]          | 0.71 [0.60, 0.83]             | 0.53 [0.42, 0.64] |     0.671 |
| eSEN-30M-OAM      | incomplete (1/500 WBM, 51/500 pairs) — not ranked | cpu/float32 | True        | 1 / 0                 |                            -200.000 | 0.000 [0.000, 0.000]          | n/a                           | n/a               |   nan     |

Energy MAE (meV/atom) by hull bin — 'new' = WBM screening structures (relaxed energy), 'known' = MP pairs whose control stays in the target structure:

| model             | new <0            | new 0–0.025       | new 0.025–0.1     | new 0.1–0.3       | new >0.3             | new all           | known ≤0.025     | known 0.025–0.1   | known 0.1–0.3     | known >0.3          |
|:------------------|:------------------|:------------------|:------------------|:------------------|:---------------------|:------------------|:-----------------|:------------------|:------------------|:--------------------|
| SevenNet-Omni     | 6.7 [5.2, 8.6]    | 5.6 [3.9, 7.4]    | 11.0 [8.2, 14.2]  | 23.9 [17.6, 31.3] | 66.1 [33.0, 109.2]   | 21.2 [16.1, 27.4] | 4.8 [3.8, 5.9]   | 8.2 [6.6, 10.2]   | 12.1 [8.0, 17.4]  | 79.2 [41.9, 127.8]  |
| MACE-MPA-0 medium | 16.6 [10.9, 23.0] | 13.9 [8.6, 20.6]  | 17.2 [13.9, 21.0] | 33.0 [25.5, 41.2] | 87.0 [54.8, 126.0]   | 31.1 [25.7, 37.2] | 6.0 [4.7, 7.3]   | 9.4 [7.5, 11.5]   | 18.0 [13.2, 23.8] | 122.4 [69.0, 184.2] |
| MACE-MP-0 medium  | 44.2 [29.2, 61.8] | 23.8 [14.7, 38.8] | 37.7 [31.4, 44.4] | 63.9 [55.8, 72.6] | 142.4 [102.6, 187.8] | 59.6 [52.4, 67.5] | 11.1 [8.8, 13.8] | 13.4 [10.7, 16.6] | 17.4 [14.0, 21.4] | 144.6 [90.3, 208.7] |
| eSEN-30M-OAM      | n/a               | n/a               | n/a               | 11.3 [11.3, 11.3] | n/a                  | 11.3 [11.3, 11.3] | 6.1 [2.4, 11.3]  | 9.6 [4.8, 15.0]   | 4.8 [1.3, 9.1]    | 20.0 [9.1, 30.9]    |

