# Follow-up: how large would an independent fluoride study have to be?

Generated 2026-09-18T22:22:46+00:00. **Uses no locked data and opens nothing.** The two historical fluoride results are treated as fixed evidence and used only as design inputs: they are not pooled, and no threshold is refitted. The rule under study is the pooled halide -20 meV/atom threshold exactly as it stands.

## The question

is fluoride's true precision under the POOLED halide -20 meV rule below 0.90 (a validity deficit, carve out) or at/above it (no deficit, keep pooled)?

| evidence | calls | correct | point precision | source |
|---|---:|---:|---:|---|
| calibration | 350 | 314 | 0.8971 | spec v2 fit on the 6,300-structure halide calibration draw, labelable rows |
| held out | 107 | 101 | 0.9439 | R1 of the halide locked-half evaluation, 2026-09-18 |

These straddle the 0.90 target and neither excludes the other. **They are preserved as they are.** Pooling them would produce a number that is neither a calibration estimate nor a held-out one, and would quietly turn a failed replication into a tuned threshold.

## Sizing

One-sided Clopper-Pearson at 0.95, target 0.9. 'Certify' means the lower bound clears 0.90 - the pooled rule is shown to be sound on fluoride. 'Establish a deficit' means the upper bound falls below 0.90 - the carve-out's premise is shown to be real. Structures are calls divided by the observed yield (0.830 labelable x 0.1664 calls per labelable fluoride).

| true precision | certify @80% | @90% | structures @80% | establish deficit @80% | @90% | structures @80% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.8000 | - | - | - | 79 | 121 | 573 |
| 0.8400 | - | - | - | 216 | 287 | 1,565 |
| 0.8600 | - | - | - | 439 | 581 | 3,181 |
| 0.8800 | - | - | - | 1,784 | 2,360 | 12,925 |
| 0.8971 | - | - | - | 67,656 | 102,898 | 490,137 |
| 0.9200 | 1,348 | 1,784 | 9,766 | - | - | - |
| 0.9439 | 287 | 381 | 2,080 | - | - | - |
| 0.9600 | 140 | 187 | 1,015 | - | - | - |

Read the two halves of that table against each other. Near 0.90 both columns explode: at a true precision of 0.8971 - the calibration estimate - establishing a deficit is hopeless, because the effect size is 0.0029. **If fluoride's true precision really is 0.897, no feasible study can prove it, and none should: a rule that is 0.3 points short of its promise is not what the carve-out was for.** The carve-out is only worth its cost if the true value is meaningfully below target, and that is the row to size against.

## What the remaining pool can actually support

WBM's unique-prototype pool has **429 unspent fluoride candidates** after every split's exclusions and the reduced-formula leakage guard. At the observed yield that is about **59 stable calls** - fewer than the 107 the held-out half already produced, and far fewer than the 350 on calibration.

| if the truth is | power to certify | power to establish a deficit |
|---|---:|---:|
| 0.8971 (calibration estimate) | 0.013 | 0.037 |
| 0.9439 (held-out estimate) | 0.149 | 0.000 |
| 0.86 (a deficit worth acting on) | 0.001 | 0.196 |

**The remaining WBM pool cannot settle this question at any power worth having.** An independent fluoride evaluation of useful size has to come from somewhere else - a targeted DFT campaign on fluorides, or a non-WBM source such as Alexandria or new MP additions, with its own pre-registration and its own held-out half.

## The cost of the carve-out, stated plainly

The fluoride carve-out **reduces recall and increases DFT routing**. It has never been a routing improvement and was never adopted as one; on the calibration halide draw, splitting fluoride out moves:

| | pooled (no carve-out) | carved out | change |
|---|---:|---:|---|
| share sent to DFT | 0.096 | 0.192 | **doubles** |
| recall of truly stable | 0.599 | 0.338 | **falls 44%** |
| 'likely stable' calls | 771 | 421 | -45% |

Out of sample the same direction shows in the two pre-registered results, by arithmetic on figures already reported and with no further analysis of the held-out set: H1 made **157** 'likely stable' calls on non-fluoride halides, and R1 shows the pooled rule would have made **107** more on the fluorides. So the carve-out costs **107 of 264 labels, 40.5%**, on the held-out half.

> **Therefore: adopt the fluoride carve-out only if a fluoride-specific validity deficit is established with adequate evidence.** The cost is certain, immediate and large; the benefit is a precision guarantee that the held-out data did not confirm. A carve-out that throws away two fifths of a family's labels has to be paid for by a demonstrated failure of the pooled rule, not by a calibration-set point estimate that did not replicate.

## Status

| | |
|---|---|
| H1-H3 | validated on the locked half; preserved as the primary result |
| fluoride taxonomy decision | **unresolved** - the calibration deficit did not reproduce on the held-out point estimate, and the held-out sample was too small to certify the pooled rule at 0.90 either |
| production taxonomy | unchanged; `confidence.family()` has no fluoride |
| active bundle | v1, `data/calibration_bundle.json`, unmodified |
| specification v2 | frozen, not promoted |
| locked sets | five closed; the halide half opened once and reported |

