# Final evaluation on the locked WBM test set — MACE-MPA-0 medium (second engine for disagreement: MACE-MP-0 medium)

Opened once (2026-09-12T03:33:29+00:00); every rule fitted on the calibration set only. 3,999 usable test relaxations, 1 rejected by the guard (counted). Disagreement tolerance 166 meV/atom (95th percentile on calibration).

## Routing (the complete system)

| quantity                                      |    value |
|:----------------------------------------------|---------:|
| n                                             | 3999.000 |
| likely stable                                 |  224.000 |
| likely unstable                               | 2149.000 |
| send to DFT                                   | 1626.000 |
| precision of 'likely stable'                  |    0.960 |
| NPV of 'likely unstable'                      |    0.988 |
| share sent to DFT                             |    0.407 |
| truly stable found as 'likely stable'         |    0.352 |
| truly stable sent to DFT                      |    0.607 |
| truly stable wrongly called 'likely unstable' |    0.041 |

'Likely stable' precision on test: 0.96 [0.93, 0.98] (target 90%); 'likely unstable' NPV: 0.988 [0.984, 0.993] (target 95%).

## Plain threshold (cost-optimal on calibration: +0 meV/atom)

precision 0.84 [0.81, 0.87], recall 0.86 [0.84, 0.89], F1 0.85 [0.83, 0.87], NPV 0.975 [0.970, 0.980], DAF 5.51 [5.16, 5.90].

## Energy error by hull bin (test)

| bin       |    n | energy MAE         | median |err|      |
|:----------|-----:|:-------------------|:------------------|
| <0        |  611 | 15.3 [13.0, 18.5]  | 8.1 [7.1, 9.2]    |
| 0–0.025   |  416 | 11.0 [9.7, 12.5]   | 6.7 [5.9, 7.6]    |
| 0.025–0.1 | 1120 | 14.1 [13.3, 15.1]  | 9.3 [8.6, 10.1]   |
| 0.1–0.3   | 1334 | 30.2 [27.6, 32.9]  | 16.4 [15.6, 17.7] |
| >0.3      |  518 | 86.7 [73.0, 103.1] | 32.9 [27.9, 37.9] |

