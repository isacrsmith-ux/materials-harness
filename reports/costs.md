# Cost-based operating point — MACE-MPA-0 medium

Costs supplied: a wasted lab test = **1**, a missed stable material = **0.11** (ratio 0.11:1). Computed on the 3,998 usable WBM **calibration** structures; the locked test set is not re-optimised against.

## Where these coefficients come from

**These three numbers are not the same kind of number.** One is a definition, one is derived from a policy choice, and one is an order-of-magnitude estimate. Read this before quoting any figure on this page.

* **`cost_false_positive` = 1** — NORMALIZATION BASELINE. Fixed at 1.0 by definition, not measured: it is the unit the other two are expressed in. Changing it alone means nothing; only the ratios carry information.
* **`cost_missed_stable` = 0.11** — POLICY-DERIVED, NOT EMPIRICAL. 0.11 is the ratio implied by the routing layer's frozen 90% precision target (confidence.TARGET_PRECISION): a cost-optimal rule calls a candidate stable when P(stable) > cost_fp/(cost_fp+cost_fn), so a 0.90 floor implies cost_missed_stable/cost_fp = (1-0.90)/0.90 = 1/9. It is chosen for consistency with a target that was already certified and published, NOT because the value of a missed stable material has been measured. No empirical study backs this number.
* **`cost_dft` = 0.02** — ESTIMATED COMPUTE-TO-EXPERIMENT RATIO. NOT EMPIRICALLY ESTABLISHED. The numerator is measured: one engine screen is 1.67 s/candidate mean over 25,011 ood jobs, and a DFT relaxation of a comparable cell at MP-standard GGA/GGA+U settings is ~10^2-10^3 core-hours. The DENOMINATOR -- what one synthesis + characterization attempt actually costs -- has no defensible source in this project, so the ratio is an order-of-magnitude estimate only. Do not present 0.02 as established until that denominator is sourced. Conclusions that depend on it should be reported across 0.005-0.1.
* cost_dft does NOT enter the expected-cost minimisation (metrics.expected_cost uses cost_false_positive and cost_missed_stable only). It exists to price routing-to-DFT decisions such as the >0.3 eV/atom refusal, which the threshold sweep does not model.
* Sweep for the report's sensitivity table, centred on the proposed 0.11 so no conclusion rests on that single assumption. 0.11 is the policy-consistent point; 1.0 is the old placeholder, kept for comparison.

Because `cost_missed_stable` is policy-derived rather than measured, the sensitivity table below is the part of this page to trust: it shows what changes, and what does not, across ratios from 0.05 to 2.

## Answer

* **Threshold: -35 meV/atom.**
* Anything from **-35 to -35 meV/atom** costs within 2% of the optimum — inside that range the exact cost numbers do not change the answer.
* At that threshold: precision 0.94 [0.91, 0.97], recall 0.45 [0.42, 0.49], NPV 0.910 [0.901, 0.919], DAF 6.18 [5.75, 6.67].
* 294 of 3,998 candidates called stable; 17 of those are wrong and 333 stable materials are missed.
* Expected cost 0.0134 per candidate screened.

## What your costs imply about precision

Minimising expected cost means calling a candidate stable when its probability of being stable exceeds `cost_fp / (cost_fp + cost_fn)` = **0.90**. Read the other way: the routing layer's 90% precision target is itself a cost claim — it assumes a wasted lab test is 9× worse than missing a stable material. If that is not your view, the target should move, not just the threshold.

## Sensitivity

How the optimum moves as a missed material gets more expensive relative to a wasted test:

|   missed ÷ wasted test |   optimal threshold (meV/atom) | as-good-as-optimal range (meV/atom)   |   precision |   recall |   implied precision floor |   expected cost per candidate |
|-----------------------:|-------------------------------:|:--------------------------------------|------------:|---------:|--------------------------:|------------------------------:|
|                  0.050 |                       -130.000 | -140 … -130                           |       0.978 |    0.074 |                     0.952 |                         0.007 |
|                  0.110 |                        -35.000 | -35 … -35                             |       0.942 |    0.454 |                     0.901 |                         0.013 |
|                  0.250 |                        -15.000 | -20 … -10                             |       0.915 |    0.639 |                     0.800 |                         0.023 |
|                  0.500 |                        -10.000 | -10 … -10                             |       0.902 |    0.710 |                     0.667 |                         0.034 |
|                  1.000 |                          0.000 | -5 … +0                               |       0.826 |    0.838 |                     0.500 |                         0.052 |
|                  2.000 |                          0.000 | +0 … +5                               |       0.826 |    0.838 |                     0.333 |                         0.077 |

## Method

Expected cost per screened candidate = (false positives × wasted-test cost + false negatives × missed-material cost) ÷ N, minimised over thresholds from -300 to +300 meV/atom in 5 meV/atom steps. Intervals are 95 % bootstrap. Re-run with `python -m harness costs --fp <n> --fn <n>`.

