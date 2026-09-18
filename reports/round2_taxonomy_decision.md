# Taxonomy carve-out decision report

Engine MACE-MPA-0 medium cpu/float32, settings_tag c2480e74. Generated 2026-09-18T17:17:41+00:00. Targets: precision >= 0.9, NPV >= 0.95, read from a one-sided Clopper-Pearson lower bound at confidence 0.95, Bonferroni-corrected over the 61-point threshold grid. Verdicts are read from the bound, never the point estimate.

**Nothing here was adopted.** `data/calibration_bundle.json` is untouched (created 2026-09-12T20:21:45+00:00). No locked half was opened.

## What is being decided

Each proposed new family is carved out of a parent that the product already treats as one population. The question is not only whether the child certifies - the round-2 document answered that - but whether the **residual parent still certifies after the child is removed**, because the parent's existing thresholds were fitted on the undivided family.

| child | carved out of | also takes from |
|---|---|---|
| fluoride | halide | - |
| sulfide | chalcogenide | halide |
| nitride | pnictide | halide, chalcogenide |
| carbide | other | halide, chalcogenide, pnictide |

### Two differences from the round-2 document, both of which matter here

Certification below is on **labelable** rows: bundle weak-element list + structure-change exclusion; no second-engine disagreement term (round 2 ran one engine). The frozen bundle fits its thresholds on the rows that would actually receive a label, so an adoption decision has to be made on that population. The round-2 document certified on all usable rows, which is a superset. Both are shown, and **they do not always agree**.

## Evidence available per parent

| parent | calibration evidence | n usable | n labelable | carved away | residual (usable) |
|---|---|---:|---:|---:|---:|
| halide | round-2 halide draw (3,500 round-1 + 2,800 top-up = 6,300) | 6300 | 5135 | 2844 | 3456 |
| chalcogenide | original WBM calibration set only | 260 | 224 | 113 | 147 |
| pnictide | original WBM calibration set only | 239 | 210 | 51 | 188 |
| other | original WBM calibration set only | 301 | 274 | 28 | 273 |

The asymmetry in that table is the single most important fact in this report. Round 2 drew a full 6,300-structure halide set, so both sides of the fluoride carve-out are measured on thousands of rows. It drew no chalcogenide, pnictide or 'other' set - it drew their sulfide, nitride and carbide *subsets*. What is left of those three parents is only what the original 4,000-id calibration set happens to contain.

## Parent: halide

Evidence: round-2 halide draw (3,500 round-1 + 2,800 top-up = 6,300). Carved out: fluoride 2241, sulfide 297, nitride 165, carbide 141.

| | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall (stable) | stable lost | to DFT |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| before, usable rows | 6300 | 0.235 | **-70 meV** | 0.9437 | 0.9028 | **+0 meV** | 0.9648 | 0.9555 | 0.306 | 0.112 | 0.180 |
| before, labelable | 5135 | 0.234 | **-20 meV** | 0.9351 | 0.9025 | **+0 meV** | 0.9638 | 0.9534 | 0.599 | 0.116 | 0.096 |
| after, usable rows | 3456 | 0.220 | **-20 meV** | 0.9545 | 0.9166 | **+0 meV** | 0.9681 | 0.9559 | 0.605 | 0.112 | 0.089 |
| after, labelable | 2819 | 0.215 | **-10 meV** | 0.9545 | 0.9145 | **+0 meV** | 0.9683 | 0.9548 | 0.693 | 0.116 | 0.061 |

Frozen bundle thresholds for `halide`: `{'stable': None, 'unstable': None, 'n': 153}`. Routing this same labelable population with the frozen rule sends 1.000 to DFT, labels 0 'likely stable' (recall 0.000) and loses 0.000 of the truly stable ones.

## Parent: chalcogenide

Evidence: original WBM calibration set only. Carved out: sulfide 110, nitride 1, carbide 2.

| | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall (stable) | stable lost | to DFT |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| before, usable rows | 260 | 0.158 | none | - | - | none | - | - | 0.000 | 0.000 | 1.000 |
| before, labelable | 224 | 0.174 | none | - | - | none | - | - | 0.000 | 0.000 | 1.000 |
| after, usable rows | 147 | 0.197 | none | - | - | none | - | - | 0.000 | 0.000 | 1.000 |
| after, labelable | 130 | 0.215 | none | - | - | none | - | - | 0.000 | 0.000 | 1.000 |

Frozen bundle thresholds for `chalcogenide`: `{'stable': None, 'unstable': None, 'n': 224}`. Routing this same labelable population with the frozen rule sends 1.000 to DFT, labels 0 'likely stable' (recall 0.000) and loses 0.000 of the truly stable ones.

## Parent: pnictide

Evidence: original WBM calibration set only. Carved out: nitride 51.

| | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall (stable) | stable lost | to DFT |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| before, usable rows | 239 | 0.113 | none | - | - | **+50 meV** | 1.0000 | 0.9593 | 0.000 | 0.000 | 0.285 |
| before, labelable | 210 | 0.129 | none | - | - | **+50 meV** | 1.0000 | 0.9515 | 0.000 | 0.000 | 0.319 |
| after, usable rows | 188 | 0.122 | none | - | - | none | - | - | 0.000 | 0.000 | 1.000 |
| after, labelable | 166 | 0.139 | none | - | - | none | - | - | 0.000 | 0.000 | 1.000 |

Frozen bundle thresholds for `pnictide`: `{'stable': None, 'unstable': 0.05, 'n': 210}`. Routing this same labelable population with the frozen rule sends 0.319 to DFT, labels 0 'likely stable' (recall 0.000) and loses 0.000 of the truly stable ones.

## Parent: other

Evidence: original WBM calibration set only. Carved out: carbide 28.

| | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall (stable) | stable lost | to DFT |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| before, usable rows | 301 | 0.113 | none | - | - | **+30 meV** | 0.9959 | 0.9621 | 0.000 | 0.029 | 0.186 |
| before, labelable | 274 | 0.120 | none | - | - | **+30 meV** | 0.9954 | 0.9577 | 0.000 | 0.030 | 0.201 |
| after, usable rows | 273 | 0.110 | none | - | - | **+20 meV** | 0.9914 | 0.9516 | 0.000 | 0.067 | 0.150 |
| after, labelable | 248 | 0.121 | none | - | - | **+30 meV** | 1.0000 | 0.9646 | 0.000 | 0.000 | 0.206 |

Frozen bundle thresholds for `other`: `{'stable': None, 'unstable': 0.03, 'n': 274}`. Routing this same labelable population with the frozen rule sends 0.201 to DFT, labels 0 'likely stable' (recall 0.000) and loses 0.030 of the truly stable ones.

## The carved-out children, on the same labelable footing

| child | source | n usable | n labelable | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall | stable lost | to DFT |
|---|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| fluoride | halide-draw subset | 2241 | 1888 | none | - | - | **+10 meV** | 0.9825 | 0.9671 | 0.000 | 0.042 | 0.365 |
| sulfide | round-2 sulfide draw | 4000 | 3402 | **-30 meV** | 0.9615 | 0.9047 | **+0 meV** | 0.9806 | 0.9712 | 0.495 | 0.125 | 0.068 |
| nitride | round-2 nitride draw | 2423 | 2159 | none | - | - | **+0 meV** | 0.9729 | 0.9594 | 0.000 | 0.244 | 0.093 |
| carbide | round-2 carbide draw | 1876 | 1647 | **-20 meV** | 0.9826 | 0.9043 | **-10 meV** | 0.9708 | 0.9545 | 0.635 | 0.247 | 0.015 |

## Incremental routing benefit

One population of 13,204 labelable calibration rows, routed three ways. **B and C fit their thresholds on the very rows they are scored on**, so both are in-sample and optimistic; the comparison between them is still meaningful because the optimism applies equally. A is the frozen bundle and is genuinely out of sample for every round-2 row.

_the mix is an artifact of what round 2 drew, not a candidate distribution: halide, sulfide, nitride and carbide are over-represented relative to any real stream. Read the per-family rows, not the aggregate, for anything but a sanity check._

| regime | to DFT | n called stable | precision | CP-lower | recall (stable) | stable lost |
|---|---:|---:|---:|---:|---:|---:|
| A frozen bundle, current taxonomy | 0.751 | 0 | - | - | 0.000 | 0.005 |
| B re-certified, current taxonomy | 0.079 | 1165 | 0.9468 | 0.9229 | 0.502 | 0.145 |
| C re-certified, proposed taxonomy | 0.143 | 746 | 0.9584 | 0.9302 | 0.326 | 0.117 |

### Where the DFT share moves, family by family

| family | regime | n | to DFT |
|---|---|---:|---:|
| chalcogenide | A | 3698 | 1.000 |
| halide | A | 5394 | 1.000 |
| other | A | 1784 | 0.150 |
| pnictide | A | 2328 | 0.237 |
| chalcogenide | B | 3698 | 0.070 |
| halide | B | 5394 | 0.098 |
| other | B | 1784 | 0.071 |
| pnictide | B | 2328 | 0.058 |
| carbide | C | 1787 | 0.088 |
| chalcogenide | C | 130 | 1.000 |
| fluoride | C | 1935 | 0.371 |
| halide | C | 2910 | 0.061 |
| nitride | C | 2344 | 0.095 |
| other | C | 248 | 0.206 |
| pnictide | C | 166 | 1.000 |
| sulfide | C | 3684 | 0.072 |

### Regime B is not a valid 'do nothing' baseline, and the aggregate should not be read as one

B fits a `chalcogenide` threshold on 3,698 rows of which **3,684 are sulfides and 130 are actual residual chalcogenides**, and a `pnictide` threshold on 2,328 rows that are mostly nitrides. Those are child thresholds wearing the parent's name. B scores well for exactly the reason C exists - the chemistry really does separate - while keeping the parent label, so the aggregate cannot tell the two apart on this population.

The contamination is a property of what round 2 drew, not of either taxonomy. Round 2 drew sulfide, nitride and carbide *subsets*; it never drew a representative chalcogenide, pnictide or 'other' set. **The only carve-out whose two sides are both measured on a representative draw is fluoride out of halide**, and that is the only one the aggregate here can be trusted about.

### The carbide result is marginal and moves with the population

On its own 1,647-row draw carbide certifies a stable threshold at -20 meV with a bound of 0.9043 - 0.0043 above target. Pool in the 140 carbides that arrived inside the halide, chalcogenide and pnictide draws and the same family certifies **nothing** on the stable side. A threshold that flips on a 9% change in population composition is not one to adopt without an out-of-sample check.

## Verdict per carve-out

| carve-out | child certifies | residual parent certifies | net effect | verdict |
|---|---|---|---|---|
| fluoride out of halide | unstable only (+10 meV, 0.9671) | **yes, and better**: -10 meV, bound 0.9145, recall 0.599 -> 0.693, DFT 0.096 -> 0.061 | strict improvement on a representative draw | **supported by the evidence** |
| sulfide out of chalcogenide | **both sides** (-30 meV, 0.9047; +0 meV, 0.9712) | residual n=130, certifies nothing - but it certified nothing before the carve-out either | child gains a lot, parent loses nothing it had | **plausible, unmeasured parent** |
| nitride out of pnictide | unstable only (+0 meV, 0.9594) | **NO - and pnictide loses the +50 meV unstable threshold it has today** (bound 0.9515 -> nothing at n=166) | strict regression for the parent | **not supported** |
| carbide out of 'other' | both sides on its own draw, neither when pooled | yes, +30 meV bound 0.9646 (was 0.9577) | parent unharmed, child marginal | **parent safe, child needs a check** |

For comparison, the same children certified on all usable rows (the round-2 document's footing):

| child | n usable | stable t | CP-lower | unstable t | CP-lower |
|---|---:|---|---:|---|---:|
| fluoride | 2241 | none | - | +10 meV | 0.9690 |
| sulfide | 4000 | none | - | -10 meV | 0.9507 |
| nitride | 2423 | none | - | -10 meV | 0.9518 |
| carbide | 1876 | -20 meV | 0.9074 | -10 meV | 0.9589 |
