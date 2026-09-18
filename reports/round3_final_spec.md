# Final proposed taxonomy, thresholds and evaluation protocol

Engine MACE-MPA-0 medium cpu/float32, settings_tag c2480e74. Generated 2026-09-18T18:32:32+00:00. Footing: **labelable rows (weak-element + structure-change exclusions, no second engine)**. Targets: precision >= 0.9, NPV >= 0.95, read from a one-sided Clopper-Pearson lower bound at confidence 0.95, Bonferroni-corrected over the threshold grid. Verdicts are read from the bound, never the point estimate.

**This is a proposal. `data/calibration_bundle.json` is untouched and every locked half is closed. Nothing here may be adopted without explicit approval.**

## 1. The decision criterion, and why it is not the routing comparison

The obvious test - route one population with a pooled rule and with per-subfamily rules, and keep whichever routes better - **rejects all three carve-outs**, because pooling always buys statistical power and a split always spends it. That test is wrong on its own, and the reason is the same one that made this project use group-conditional certification in the first place: a guarantee that holds marginally over a mixture need not hold inside it.

So the criterion is validity first, power second:

> A child is carved out **only if** the parent's pooled rule has a genuine precision deficit on the child - point precision below target on the child's own rows. A loose confidence bound on a small subgroup is a power problem, not a validity problem, and carving out makes it worse rather than better.

That is test 7's precision-limited / sample-size-limited distinction, applied one level down to subgroups.

## 2. The subgroup test, all three carve-outs

| child | parent | parent's pooled stable t | n child | called stable | correct | point precision | CP-lower | genuine deficit |
|---|---|---|---:|---:|---:|---:|---:|---|
| sulfide | chalcogenide | -20 meV | 3402 | 290 | 274 | **0.9448** | 0.8895 | no |
| carbide | other | -20 meV | 1647 | 115 | 113 | **0.9826** | 0.9043 | no |
| fluoride | halide | -20 meV | 1888 | 350 | 314 | **0.8971** | 0.8366 | **YES** |

Only fluoride fails. Under halide's pooled -20 meV rule, 350 fluorides are labelled 'likely stable' at a true precision of 0.8971 - **below the 0.90 the product promises**. Sulfide and carbide sit at 0.9448 and 0.9826 under their parents' rules; their bounds are loose only because 290 and 115 calls is not many, and splitting them off leaves them with fewer still.

## 3. The final proposed taxonomy

`confidence.family()` with **one** change: fluoride inserted immediately before halide. Everything else is exactly as it is today.

```
f-electron -> intermetallic -> oxide -> FLUORIDE -> halide -> chalcogenide -> pnictide -> other
```

| proposed | change | why |
|---|---|---|
| fluoride | **NEW** | the only carve-out with a genuine precision deficit under its parent |
| halide | narrowed to non-fluoride | consequence of the above |
| sulfide | **not adopted** | no deficit under chalcogenide (0.9448); splitting costs recall 0.575 -> 0.545 |
| carbide | **not adopted** | no deficit under 'other' (0.9826, bound 0.9043); splitting collapses residual recall 0.547 -> 0.220 |
| nitride | **rejected** | user decision; and it removes pnictide's only certified threshold (+50 meV, bound 0.9515 -> nothing at n=166) |
| oxide, chalcogenide, pnictide, other, f-electron, intermetallic | unchanged | - |

## 4. Proposed thresholds

| family | status | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall | stable lost | to DFT | provenance |
|---|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| **fluoride** | certified | 1888 | 0.268 | none | - | - | **+10 meV** | 0.9825 | 0.9671 | 0.000 | 0.042 | 0.365 | round 2 halide draw (6,300), labelable rows |
| **halide** | certified | 3247 | 0.215 | **-20 meV** | 0.9667 | 0.9296 | **+0 meV** | 0.9695 | 0.9572 | 0.584 | 0.110 | 0.092 | round 2 halide draw (6,300), labelable rows |
| **oxide** | certified | 3310 | 0.123 | none | - | - | **+0 meV** | 0.9765 | 0.9663 | 0.000 | 0.167 | 0.125 | round 1 oxide draw (4,000), labelable rows |
| **chalcogenide** | provisional | 5708 | 0.152 | **-20 meV** | 0.9577 | 0.9224 | **+0 meV** | 0.9733 | 0.9652 | 0.575 | 0.149 | 0.062 | round-3 residual draw (4,000) + round-2 sulfide draw, mixed at the pool's true 0.6212 / 0.3750 ratio |
| **other** | provisional | 3935 | 0.103 | **-20 meV** | 0.9609 | 0.9031 | **-10 meV** | 0.9645 | 0.9538 | 0.547 | 0.319 | 0.019 | round-3 residual draw (4,000) + round-2 carbide draw, mixed at the pool's true 0.8921 / 0.1079 ratio |

Carried over from the frozen bundle, **not re-measured in round 2 or round 3**:

| family | n | stable t | unstable t | provenance |
|---|---:|---|---|---|
| f-electron | 1801 | -20 meV | +10 meV | frozen bundle, 2026-09-12; NOT re-measured in round 2 or 3 |
| intermetallic | 665 | - | +0 meV | frozen bundle, 2026-09-12; NOT re-measured in round 2 or 3 |
| pnictide | 210 | - | +50 meV | frozen bundle, 2026-09-12; NOT re-measured in round 2 or 3 |

> **The proposed bundle would be of mixed provenance.** Four families would carry thresholds fitted on round-2/3 data at n in the thousands; three would carry 2026-09-12 thresholds fitted on a few hundred rows. That is not a reason to reject it - the new numbers are strictly better evidenced than what they replace - but it must be recorded in the bundle, and the carried-over families remain the weakest part of the product.

## 5. What is certified, what is provisional, what is rejected

### Certified on calibration data

| conclusion | evidence |
|---|---|
| fluoride has a genuine precision deficit under halide's rule | 350 calls, point 0.8971 vs target 0.90 |
| non-fluoride halide certifies both sides | n=3,247; stable -20 meV bound 0.9296, unstable +0 meV bound 0.9572 |
| fluoride certifies the unstable side only | n=1,888; +10 meV, bound 0.9671; no stable threshold at any t |
| oxide has no stable-side path | n=3,994 usable across 11 subfamily splits; nothing at 0.90 |
| chalcogenide certifies both sides undivided | reconstructed n=5,708; stable -20 meV bound 0.9224 |
| 'other' certifies both sides undivided | reconstructed n=3,935; stable -20 meV bound 0.9031 |
| multi-start disagreement rises to 0.509 above 0.3 eV/atom | 1,000 candidates, 3 starts each |

### Provisional - certified, but on a reconstructed or single-footing population

| conclusion | why provisional |
|---|---|
| chalcogenide and 'other' thresholds | fitted on a mixture reconstructed from two draws, not one draw of the family |
| every threshold in this document | fitted and scored on calibration rows; in-sample by construction |
| carbide's own stable threshold (-20 meV, bound 0.9043) | flips to not certifying when carbides from other draws are pooled in |
| the labelable footing itself | ruled authoritative, but never yet validated out of sample |

### Rejected

| conclusion | reason |
|---|---|
| the nitride carve-out | user decision; removes pnictide's only certified threshold |
| the sulfide carve-out | no precision deficit under chalcogenide (0.9448) |
| the carbide carve-out | no precision deficit under 'other' (0.9826) |
| 'sulfide needs ~6,416 more structures' (round 2, section 15) | artefact of the all-usable footing; it certifies on labelable rows |
| 'halide certifies at -70 meV' (round 2, section 14) | all-usable footing; -20 meV on labelable rows |
| routing efficiency as the carve-out criterion | rejects all three carve-outs including the valid one |

## 6. Proposed evaluation protocol

To be frozen **before** any locked half is opened, and not changed afterwards.

1. **Freeze** the taxonomy of section 3 and the thresholds of section 4 into `data/calibration_bundle.json`, recording per-family provenance and the labelable footing. This is the only write, and it needs explicit approval.
2. **Pre-register the pass criterion**, per family and per side: the held-out precision (or NPV) lower bound must clear the same target the threshold was certified against - 0.90 and 0.95 - with the same one-sided Clopper-Pearson bound. No re-tuning after the half is opened; a miss is reported as a miss.
3. **Open in this order**, one at a time, each opened once and never re-opened:

| order | locked half | n | what it settles |
|---:|---|---:|---|
| 1 | halide (round 1) | 2,000 | the fluoride carve-out and both halide-side thresholds - the only adopted change |
| 2 | oxide (round 1) | 2,000 | that oxide's unstable-only routing holds out of sample |
| 3 | chalcogenide residual (round 3) | 1,500 | the provisional chalcogenide threshold |
| 4 | 'other' residual (round 3) | 1,500 | the provisional 'other' threshold |
| - | sulfide (round 2) | 874 | **do not open.** Sulfide is not being adopted as a family; its half has nothing to settle under this taxonomy |
| - | original WBM test | 4,000 | already opened once, 2026-09-12; never again |

4. **Stop rule.** If the halide half misses, nothing else is opened and the taxonomy change is withdrawn - the remaining halves cannot rescue a change whose only justification has failed out of sample.
5. **Report** each opening as its own numbered section, with the pre-registered criterion quoted before the result.

## 7. What still needs approval

| # | decision | recommendation |
|---|---|---|
| 1 | Adopt the fluoride carve-out and the two halide-side thresholds | yes - the only change with a measured validity failure behind it |
| 2 | Adopt the re-measured oxide, chalcogenide and 'other' thresholds | yes, marked provisional - they replace thresholds fitted on 185-274 rows |
| 3 | Leave sulfide, carbide and nitride pooled in their parents | yes |
| 4 | Write the frozen bundle | needs your word; nothing has been written |
| 5 | Open the halide half first, under the section-6 protocol | needs your word |
| 6 | The sulfide locked half | recommend leaving it closed indefinitely; it has nothing to settle unless sulfide is revisited as a family |

