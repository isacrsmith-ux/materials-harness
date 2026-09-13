# Cost-based operating point — MACE-MPA-0 medium

Costs supplied: a wasted lab test = **1**, a missed stable material = **1** (ratio 1:1). Computed on the 3,998 usable WBM **calibration** structures; the locked test set is not re-optimised against.

> **These are the 1:1 placeholders in `config/costs.json`, not real costs.** Every threshold and every expected-cost figure on this page is conditional on them. The plateau below says how much that matters: inside it, the exact costs do not change the answer. Supply your real numbers and re-run `python -m harness costs` before quoting anything here.

## Answer

* **Threshold: +0 meV/atom.**
* Anything from **-5 to +0 meV/atom** costs within 2% of the optimum — inside that range the exact cost numbers do not change the answer.
* At that threshold: precision 0.83 [0.80, 0.85], recall 0.84 [0.81, 0.87], NPV 0.971 [0.965, 0.976], DAF 5.41 [5.06, 5.81].
* 619 of 3,998 candidates called stable; 108 of those are wrong and 99 stable materials are missed.
* Expected cost 0.0518 per candidate screened.

## What your costs imply about precision

Minimising expected cost means calling a candidate stable when its probability of being stable exceeds `cost_fp / (cost_fp + cost_fn)` = **0.50**. Read the other way: the routing layer's 90% precision target is itself a cost claim — it assumes a wasted lab test is 9× worse than missing a stable material. If that is not your view, the target should move, not just the threshold.

## Sensitivity

How the optimum moves as a missed material gets more expensive relative to a wasted test:

|   missed ÷ wasted test |   optimal threshold (meV/atom) | as-good-as-optimal range (meV/atom)   |   precision |   recall |   implied precision floor |   expected cost per candidate |
|-----------------------:|-------------------------------:|:--------------------------------------|------------:|---------:|--------------------------:|------------------------------:|
|                  0.100 |                        -35.000 | -35 … -35                             |       0.942 |    0.454 |                     0.909 |                         0.013 |
|                  0.250 |                        -15.000 | -20 … -10                             |       0.915 |    0.639 |                     0.800 |                         0.023 |
|                  0.500 |                        -10.000 | -10 … -10                             |       0.902 |    0.710 |                     0.667 |                         0.034 |
|                  1.000 |                          0.000 | -5 … +0                               |       0.826 |    0.838 |                     0.500 |                         0.052 |
|                  2.000 |                          0.000 | +0 … +5                               |       0.826 |    0.838 |                     0.333 |                         0.077 |
|                  4.000 |                         10.000 | +10 … +10                             |       0.699 |    0.923 |                     0.200 |                         0.108 |
|                 10.000 |                         20.000 | +20 … +20                             |       0.599 |    0.961 |                     0.091 |                         0.158 |
|                 25.000 |                         30.000 | +30 … +30                             |       0.527 |    0.975 |                     0.038 |                         0.227 |
|                100.000 |                         45.000 | +45 … +45                             |       0.434 |    0.989 |                     0.010 |                         0.372 |

## Method

Expected cost per screened candidate = (false positives × wasted-test cost + false negatives × missed-material cost) ÷ N, minimised over thresholds from -300 to +300 meV/atom in 5 meV/atom steps. Intervals are 95 % bootstrap. Re-run with `python -m harness costs --fp <n> --fn <n>`.

