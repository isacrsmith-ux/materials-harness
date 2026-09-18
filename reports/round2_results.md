
# Materials Harness - round 2

New families, the halide confirmation, the oxide splits, multi-start structure verification and the failure retry. Generated 18 September 2026. Production engine MACE-MPA-0 medium (cpu/float32, settings tag c2480e74), asserted at the start of every phase. Continues reports/test_results.pdf, which ends at section 12.

## How to read this document

Six new tests are recorded here, numbered 13 to 18, continuing the existing document. Every convention of that document is kept and none is relaxed. Intervals are 95% and **verdicts are read from the pessimistic end**, never the point estimate. Rates whose sample could be all-correct use Clopper-Pearson bounds rather than a bootstrap. Rejected relaxations are counted and excluded, never dropped, so an exclusion cannot quietly improve a rate. Each section names the report file it came from.

One term is used throughout. A family is **sample-size limited** when its best achievable point precision is already above target and only the confidence bound falls short - more calibration data would certify it. It is **precision limited** when the point precision itself peaks below target, so the bound converges under target at any n. That distinction is test 7's, and it is what decides whether more compute is worth spending. This document adds a third reading: a family can be sample-size limited and still unreachable, when the calibration set it would need is larger than the pool it could be drawn from.

> **The four families the brief named are not families in the frozen taxonomy.** `confidence.family()` resolves fluoride to halide, sulfide to chalcogenide, nitride to pnictide, and a metal carbide to 'other'; and 34-59% of the compounds containing each of those anions are also f-electron, which wins first-match. Round 2 therefore uses `round2.family2()`, which keeps f-electron, intermetallic and oxide exactly where they are and inserts the new anion families ahead of the rest. The frozen taxonomy, the frozen bundle and the round-1 certifications are untouched. Adopting any new family into production would carve it out of its parent, and the parent would have to be re-certified on its reduced population - a decision for the user, not this document.

## Summary of the round-2 tests

| # | Test | What it answers | Headline | Verdict |
|---|---|---|---|---|
| 13 | Diagnostic pull, four new families | Which families are worth a full calibration pull | sulfide, nitride and carbide all sample-size limited; fluoride precision limited | Three worth scaling, one not |
| 14 | Halide re-certification | Does more data certify halide's stable side at 0.90 | n 3,500 -> 6,300: CP-lower 0.8803 -> 0.9028 at -70 meV | **Certified** |
| 15 | New families certified | Can sulfide, nitride and carbide be certified | carbide certifies both sides; sulfide and nitride certify the unstable side and miss the stable side at 0.8747 and 0.8745 | One certified, two out of reach |
| 16 | Oxide subfamily split | Does any oxide subfamily certify where the whole family cannot | No split certifies at 0.90; three look sample-size limited | No viable path at 0.90 |
| 17 | Multi-start verification | Does the answer depend on where the relaxation started | 1 candidate in 5 disagrees across starts; 0.056 in the 0-0.025 bin, 0.509 above 0.3 eV/atom | Confirms the >0.3 refusal |
| 18 | Failure retry pass | How many failures are the method, how many are the engine | 4 of 6 hard failures resolved; 54% of multi-start disagreements; 4% of 'left its start' | Mostly genuine, not fixable |


## 13. Diagnostic pull - four new families

Source: `reports/round2_phase1_diagnostic.md`. Methodology inherited from test 7 without change: pool exclusion of every prior and locked id, per-family base rates preserved by a per-bin proportional draw, Clopper-Pearson bounds Bonferroni-corrected over the threshold grid, verdicts from the pessimistic end, rejections counted-and-excluded.

Before committing a full pull to nitride, carbide, fluoride and sulfide, roughly 500 structures of each were run and put through the same diagnosis that distinguished halide from oxide in test 7. The point of the test is to spend compute only where more data can change the answer.

> **Fluoride was never drawn.** It is a strict subset of `confidence.family()`'s halide, so the round-1 halide calibration set already held 1,208 fluorides - more than a fresh draw of the remaining pool could have bought. It is diagnosed on those, as a halide subfamily, at zero additional compute. The same logic does not apply to the other three: sulfide, nitride and carbide are largely outside the families already run.

| group | n usable | rejected | base rate | stable side | unstable side |
|---|---|---|---|---|---|
| sulfide@p1 | 500 | 0 | 0.144 | not certified | **+10 meV** |
| nitride@p1 | 500 | 0 | 0.092 | not certified | **+10 meV** |
| carbide@p1 | 500 | 0 | 0.102 | not certified | **+0 meV** |
| halide:fluoride | 1208 | 0 | 0.248 | not certified | **+10 meV** |
| halide:nonfluoride | 2292 | 0 | 0.224 | not certified | **+0 meV** |

### Diagnosis

| group | side | target | best t | n sel | k | point | CP-lower | verdict | n structs needed |
|---|---|---|---|---|---|---|---|---|---|
| sulfide@p1 | stable | 0.90 | -10 meV | 54 | 51 | 0.9444 | 0.7758 | sample-size limited | 3843 |
| sulfide@p1 | unstable | 0.95 | +30 meV | 360 | 359 | 0.9972 | 0.9740 | certified | - |
| nitride@p1 | stable | 0.90 | -10 meV | 35 | 34 | 0.9714 | 0.7602 | sample-size limited | 2315 |
| nitride@p1 | unstable | 0.95 | +80 meV | 350 | 350 | 1.0000 | 0.9799 | certified | - |
| carbide@p1 | stable | 0.90 | -30 meV | 29 | 29 | 1.0000 | 0.7827 | sample-size limited | 1173 |
| carbide@p1 | unstable | 0.95 | +30 meV | 415 | 415 | 1.0000 | 0.9830 | certified | - |
| halide:fluoride | stable | 0.90 | -20 meV | 219 | 192 | 0.8767 | 0.7926 | precision limited | - |
| halide:fluoride | unstable | 0.95 | +50 meV | 494 | 494 | 1.0000 | 0.9857 | certified | - |
| halide:nonfluoride | stable | 0.90 | -50 meV | 225 | 215 | 0.9556 | 0.8947 | sample-size limited | 2568 |
| halide:nonfluoride | unstable | 0.95 | +100 meV | 705 | 703 | 0.9972 | 0.9838 | certified | - |

**All three newly drawn families are sample-size limited**, so all three were scaled in phase 3. Their point precisions at the ceiling threshold are 0.9444, 0.9714 and 1.0000 respectively, all above the 0.90 target; only the bound falls short, and only because 500 structures yield 29 to 54 selected calls.

**Fluoride is not, and the result is the more interesting one.** At n = 1,208 its point precision peaks at 0.8767, below target, exactly as oxide does - and unlike oxide it does not clear the 0.80 fallback either. The non-fluoride halides, by contrast, reach 0.9556 and need only 1.12x more data. Fluoride is what was holding halide's stable side back.


## 14. Halide re-certification

Source: `reports/round2_phase2_halide.md`. 2,800 additional halide calibration candidates drawn from the pool ids neither the original split nor round 1 had touched, with every prior and locked id excluded by id and every candidate sharing a reduced formula with a locked-test id dropped.

Test 7 diagnosed halide as sample-size limited and predicted that roughly 1.8x more calibration structures would certify its stable side at 0.90. This is the direct test of that prediction. Recomputing test 7's own ceiling here gives 6,948 structures indicated, against the ~6,300 the brief asked for; 6,300 were run.

| group | n usable | rejected | base rate | stable side | unstable side |
|---|---|---|---|---|---|
| halide | 3500 | 0 | 0.232 | not certified | **+0 meV** |
| halide_topup | 2800 | 0 | 0.238 | not certified | **+0 meV** |
| halide_combined | 6300 | 0 | 0.235 | **-70 meV** | **+0 meV** |
| halide_combined:fluoride | 2241 | 0 | 0.250 | not certified | **+10 meV** |
| halide_combined:nonfluoride | 4059 | 0 | 0.226 | **-20 meV** | **+0 meV** |

### Diagnosis

| group | side | target | best t | n sel | k | point | CP-lower | verdict | n structs needed |
|---|---|---|---|---|---|---|---|---|---|
| halide | stable | 0.90 | -70 meV | 267 | 251 | 0.9401 | 0.8803 | sample-size limited | 6948 |
| halide | unstable | 0.95 | +100 meV | 1009 | 1007 | 0.9980 | 0.9887 | certified | - |
| halide_topup | stable | 0.90 | -60 meV | 243 | 231 | 0.9506 | 0.8909 | sample-size limited | 3711 |
| halide_topup | unstable | 0.95 | +120 meV | 713 | 713 | 1.0000 | 0.9901 | certified | - |
| halide_combined | stable | 0.90 | -70 meV | 480 | 453 | 0.9437 | 0.9028 | certified | - |
| halide_combined | unstable | 0.95 | +100 meV | 1843 | 1840 | 0.9984 | 0.9928 | certified | - |
| halide_combined:fluoride | stable | 0.90 | -70 meV | 175 | 158 | 0.9029 | 0.8133 | sample-size limited | 1393121 |
| halide_combined:fluoride | unstable | 0.95 | +60 meV | 847 | 846 | 0.9988 | 0.9889 | certified | - |
| halide_combined:nonfluoride | stable | 0.90 | -70 meV | 305 | 295 | 0.9672 | 0.9217 | certified | - |
| halide_combined:nonfluoride | unstable | 0.95 | +100 meV | 1259 | 1257 | 0.9984 | 0.9909 | certified | - |

**The stable side certifies.** At n = 6,300 the combined halide calibration set carries a certified stable threshold of -70 meV/atom: 480 selected calls, 453 of them truly stable, point precision 0.9437, and a Clopper-Pearson lower bound of 0.9028 against the 0.90 target. The verdict is read from 0.9028, not from 0.9437.

It certified on slightly less data than indicated because the top-up's own precision came out a little higher than round 1's (0.9506 against 0.9401). That is luck in the right direction, not a method improvement, and it should not be read as evidence that the estimate was conservative.

> **The split matters more than the total.** Certifying halide as one family buys a threshold of -70 meV/atom. Splitting fluoride out and certifying the rest buys -20 meV/atom on the non-fluoride halides - a far more inclusive rule, which labels many more candidates - while fluoride certifies nothing. Fluoride's own ceiling is 0.9029 on 175 calls, which is technically above target, but reaching the bound would take 1,393,121 calibration structures: 6.5x the whole 215,488-structure WBM unique-prototype pool. Sample-size limited and unreachable are not the same verdict, and fluoride is the second.


## 15. The three new families, fully calibrated

Source: `reports/round2_phase3_families.md`. sulfide 4,000, nitride 2,423 and carbide 1,876 calibration structures, drawn sequentially against a shared taken-set from the pool ids no earlier split had used. Same methodology as test 7 throughout.

Phase 1 diagnosed all three as sample-size limited, so all three were scaled to whatever the pool could supply. Only sulfide reached the 4,000 cap the brief named; nitride and carbide are the whole of what was available after the leakage guards.

| group | n usable | rejected | base rate | stable side | unstable side |
|---|---|---|---|---|---|
| sulfide | 4000 | 0 | 0.128 | not certified | **-10 meV** |
| nitride | 2423 | 0 | 0.092 | not certified | **-10 meV** |
| carbide | 1876 | 0 | 0.099 | **-20 meV** | **-10 meV** |

### Diagnosis

| group | side | target | best t | n sel | k | point | CP-lower | verdict | n structs needed |
|---|---|---|---|---|---|---|---|---|---|
| sulfide | stable | 0.90 | -90 meV | 101 | 98 | 0.9703 | 0.8747 | sample-size limited | 6416 |
| sulfide | unstable | 0.95 | +90 meV | 1993 | 1992 | 0.9995 | 0.9953 | certified | - |
| nitride | stable | 0.90 | -40 meV | 71 | 70 | 0.9859 | 0.8745 | sample-size limited | 3106 |
| nitride | unstable | 0.95 | +120 meV | 1432 | 1429 | 0.9979 | 0.9907 | certified | - |
| carbide | stable | 0.90 | -30 meV | 97 | 97 | 1.0000 | 0.9294 | certified | - |
| carbide | unstable | 0.95 | +50 meV | 1521 | 1521 | 1.0000 | 0.9953 | certified | - |

**Carbide certifies both sides.** Its stable threshold is -20 meV/atom, its unstable threshold -10 meV/atom. At the ceiling threshold all 97 selected calls were truly stable, and the verdict is still read from the bound (0.9294), never from that 1.0000.

**Sulfide and nitride miss, narrowly, and the pool is spent.** Sulfide's bound reaches 0.8747 and nitride's 0.8745 against the 0.90 target; both remain sample-size limited rather than precision limited, with point precisions of 0.9703 and 0.9859. Sulfide would need about 6,416 calibration structures against the 4,874 the draw could supply, and nitride about 3,106 against 2,423. Neither shortfall can be closed from this pool without dissolving a locked half or relaxing the reduced-formula leakage guard, and neither was done.

### What routing on the certified unstable thresholds actually costs

| group | threshold | share discarded without DFT | truly stable lost | (of) |
|---|---|---|---|---|
| sulfide | -10 meV | 0.897 | 0.269 | 137 of 510 |
| nitride | -10 meV | 0.934 | 0.351 | 78 of 222 |
| carbide | -10 meV | 0.922 | 0.247 | 46 of 186 |

> **Unstable-side certification is not a small result for these families, and it is not a free one.** All three certify it, which is what turns 'send everything to DFT' into 'discard most of it without DFT'. But more calibration data certifies a LOWER unstable threshold, which discards more - and loses more. At n = 500 these families discarded 81-89% of candidates and lost 8-13% of the truly stable ones; at full n they discard 90-93% and lose 25-35%. The round-1 caution therefore applies with more force, not less: a satisfied NPV target is not the same as keeping your discoveries, and both numbers belong in any proposal to route on these thresholds.


## 16. Oxide subfamily split

Source: `reports/round2_phase4_oxide_subfamilies.md`. The existing 3,994-row oxide calibration set, split by transition-metal against main-group, by the highest formal cation oxidation state in the first charge-balanced assignment, and by mixed valence. No new structures were run.

Test 7's verdict was that oxide is precision limited: its point precision peaks at 0.8750, below the 0.90 target, so the bound converges under target at any n. That is a statement about the family as a whole. This section asks whether some chemically coherent part of it behaves better.

Mixed valence is tested as 'no assignment of one integer oxidation state per element balances the charge' - the standard operational definition, which Fe3O4 fails and both FeO and Fe2O3 pass. Compositions pymatgen could not evaluate at all are counted in neither split, so the two splits' n need not sum to the parent's.

| group | n usable | rejected | base rate | stable side | unstable side |
|---|---|---|---|---|---|
| oxide | 3994 | 6 | 0.112 | not certified | **+0 meV** |
| oxide:tm | 3153 | 6 | 0.105 | not certified | **-10 meV** |
| oxide:maingroup | 841 | 6 | 0.136 | not certified | **+0 meV** |
| oxide:multi_tm | 871 | 6 | 0.096 | not certified | **+0 meV** |
| oxide:single_tm | 3123 | 6 | 0.116 | not certified | **+0 meV** |
| oxide:mixed_valence | 1266 | 6 | 0.087 | not certified | **-10 meV** |
| oxide:single_valence | 2728 | 6 | 0.123 | not certified | **+0 meV** |
| oxide:ox_le2 | 371 | 6 | 0.092 | not certified | **+10 meV** |
| oxide:ox_3 | 642 | 6 | 0.072 | not certified | **+0 meV** |
| oxide:ox_4 | 793 | 6 | 0.107 | not certified | **+0 meV** |
| oxide:ox_ge5 | 854 | 6 | 0.193 | not certified | **+10 meV** |

### Diagnosis

| group | side | target | best t | n sel | k | point | CP-lower | verdict | n structs needed |
|---|---|---|---|---|---|---|---|---|---|
| oxide | stable | 0.90 | -20 meV | 272 | 238 | 0.8750 | 0.8005 | precision limited | - |
| oxide | unstable | 0.95 | +60 meV | 2495 | 2489 | 0.9976 | 0.9927 | certified | - |
| oxide:tm | stable | 0.90 | -20 meV | 218 | 185 | 0.8486 | 0.7591 | precision limited | - |
| oxide:tm | unstable | 0.95 | +100 meV | 1575 | 1573 | 0.9987 | 0.9927 | certified | - |
| oxide:maingroup | stable | 0.90 | -20 meV | 54 | 53 | 0.9815 | 0.8380 | sample-size limited | 1714 |
| oxide:maingroup | unstable | 0.95 | +50 meV | 530 | 528 | 0.9962 | 0.9786 | certified | - |
| oxide:multi_tm | stable | 0.90 | +0 meV | 81 | 68 | 0.8395 | 0.6783 | precision limited | - |
| oxide:multi_tm | unstable | 0.95 | +60 meV | 566 | 566 | 1.0000 | 0.9875 | certified | - |
| oxide:single_tm | stable | 0.90 | -30 meV | 177 | 157 | 0.8870 | 0.7941 | precision limited | - |
| oxide:single_tm | unstable | 0.95 | +50 meV | 2058 | 2052 | 0.9971 | 0.9911 | certified | - |
| oxide:mixed_valence | stable | 0.90 | -30 meV | 52 | 49 | 0.9423 | 0.7681 | sample-size limited | 11370 |
| oxide:mixed_valence | unstable | 0.95 | +60 meV | 922 | 920 | 0.9978 | 0.9876 | certified | - |
| oxide:single_valence | stable | 0.90 | -20 meV | 200 | 174 | 0.8700 | 0.7799 | precision limited | - |
| oxide:single_valence | unstable | 0.95 | +50 meV | 1706 | 1702 | 0.9977 | 0.9912 | certified | - |
| oxide:ox_le2 | stable | 0.90 | -10 meV | 28 | 21 | 0.7500 | 0.4383 | precision limited | - |
| oxide:ox_le2 | unstable | 0.95 | +10 meV | 294 | 294 | 1.0000 | 0.9761 | certified | - |
| oxide:ox_3 | stable | 0.90 | -20 meV | 33 | 24 | 0.7273 | 0.4409 | precision limited | - |
| oxide:ox_3 | unstable | 0.95 | +40 meV | 497 | 494 | 0.9940 | 0.9735 | certified | - |
| oxide:ox_4 | stable | 0.90 | -20 meV | 42 | 42 | 1.0000 | 0.8443 | sample-size limited | 1284 |
| oxide:ox_4 | unstable | 0.95 | +20 meV | 620 | 619 | 0.9984 | 0.9849 | certified | - |
| oxide:ox_ge5 | stable | 0.90 | -20 meV | 97 | 87 | 0.8969 | 0.7662 | precision limited | - |
| oxide:ox_ge5 | unstable | 0.95 | +50 meV | 431 | 431 | 1.0000 | 0.9836 | certified | - |

**No oxide subfamily certifies a stable threshold at 0.90.** At the 0.80 fallback the whole family still certifies at -20 meV/atom, the main-group oxides at -10 meV/atom and the +4-cation oxides at -20 meV/atom; nothing else clears 0.80 either.

### The same splits, Bonferroni-corrected over the eleven splits searched

The certification confidence above is corrected over the threshold grid, which is what makes picking the best threshold safe. It is not corrected for having searched eleven splits and reported the best. Correcting for that as well (level 0.99545) gives:

| group | side | target | best t | n sel | k | point | CP-lower | verdict | n structs needed |
|---|---|---|---|---|---|---|---|---|---|
| oxide | stable | 0.90 | -20 meV | 272 | 238 | 0.8750 | 0.7837 | precision limited | - |
| oxide | unstable | 0.95 | +60 meV | 2495 | 2489 | 0.9976 | 0.9913 | certified | - |
| oxide:maingroup | stable | 0.90 | -20 meV | 54 | 53 | 0.9815 | 0.7979 | sample-size limited | 2430 |
| oxide:maingroup | unstable | 0.95 | +50 meV | 530 | 528 | 0.9962 | 0.9734 | certified | - |
| oxide:mixed_valence | stable | 0.90 | -30 meV | 52 | 49 | 0.9423 | 0.7243 | sample-size limited | 16020 |
| oxide:mixed_valence | unstable | 0.95 | +60 meV | 922 | 920 | 0.9978 | 0.9846 | certified | - |
| oxide:ox_4 | stable | 0.90 | -20 meV | 42 | 42 | 1.0000 | 0.7975 | sample-size limited | 1719 |
| oxide:ox_4 | unstable | 0.95 | +20 meV | 620 | 619 | 0.9984 | 0.9807 | certified | - |

**Under the split correction nothing clears 0.80 either, including oxide itself.** Whole oxide keeps its 0.80 certification at the published level - it is the parent, not one of the searched splits, and test 7 certified it without any split multiplicity to correct for. But every subfamily that looked promising loses it, and the three that looked sample-size limited need 2,430, 16,020 and 1,719 structures rather than the figures above. The honest reading is that the oxide splits generated one hypothesis worth a pre-registered draw - main-group oxides - and no result.

> **These splits are hypothesis-generating, not certified results.** The Clopper-Pearson level is Bonferroni-corrected over the threshold grid, which is what makes picking the best threshold safe - it is not corrected over the eleven splits searched here. A split that looks sample-size limited because it was the best of eleven would need its own pre-registered draw before any threshold from it could be certified. The split-corrected figures are reported alongside in the source report.

The one genuinely informative result is an inversion. The mixed-valence oxides, which are the half one would expect the engine to handle worst, are the better-behaved half on the stable side; the single-valence oxides are the precision-limited ones. That does not give oxide a viable threshold, but it does say the family's ceiling is not explained by mixed valence.


## 17. Multi-start structure verification

Source: `reports/round2_phase5_multistart.md`, from `results/round2_multistart.json`. 1,000 candidates sampled proportionally across all six groups run so far, each relaxed from three starting configurations instead of one.

Test 4 measured structure-finding by comparing one relaxation against a known target structure. A real candidate has no known target, so the analogue here is agreement between starts: if three entries into the same problem land in different minima, the single number the product reports is an artefact of where the relaxation began. Start B is a compressed cell (volume x 0.95) - the WBM stand-in for test 4's rescaled start, since a WBM candidate has no parent structure to predict a volume from - and start C is the fixed-seed rattle and strain of the production retry ladder.

| family | n | all 3 starts usable | disagreement | structure | energy |
|---|---|---|---|---|---|
| carbide | 101 | 100 | 0.168 | 0.158 | 0.139 |
| halide | 188 | 188 | 0.213 | 0.186 | 0.128 |
| halide_topup | 151 | 151 | 0.272 | 0.258 | 0.192 |
| nitride | 130 | 130 | 0.200 | 0.146 | 0.185 |
| oxide | 215 | 215 | 0.181 | 0.153 | 0.130 |
| sulfide | 215 | 215 | 0.191 | 0.186 | 0.158 |
| **all** | **1000** | 999 | **0.204** | 0.182 | 0.153 |

### By true hull-distance bin

| bin | n | disagreement | structure | energy | median spread |
|---|---|---|---|---|---|
| <0 | 152 | 0.086 | 0.079 | 0.046 | 0.0 meV |
| 0-0.025 | 107 | 0.056 | 0.047 | 0.037 | 0.0 meV |
| 0.025-0.1 | 246 | 0.175 | 0.150 | 0.102 | 0.0 meV |
| 0.1-0.3 | 326 | 0.172 | 0.147 | 0.126 | 0.0 meV |
| >0.3 | 169 | 0.509 | 0.473 | 0.450 | 9.2 meV |

**One candidate in five answers differently depending on where its relaxation started**, and the rate is not spread evenly. It is 5.6% in the 0-0.025 bin and 8.6% below the hull - the bins where 'likely stable' calls are actually made - and 50.9% above 0.3 eV/atom.

> **This independently confirms the >0.3 eV/atom refusal rule from a different measurement.** Test 4 put the structure-finding rate above 0.3 eV/atom at 0.38 on a sample of 16, which is the thinnest evidence behind any rule in the product. This is 169 candidates, needs no known target structure, and says the same thing: above 0.3 eV/atom the relaxation does not reliably find one answer, so the number attached to it does not describe one material.

The disagreement is mostly structural rather than energetic - 0.182 against 0.153 overall - and the median energy spread is 0.0 meV/atom everywhere except the >0.3 bin. Where the starts agree they agree very precisely; where they disagree they have found genuinely different minima rather than the same one to different tolerances.


## 18. Retesting every failure found in phases 1-5

Source: `reports/round2_phase6_retry.md`, from `results/round2_retry.json`. Every candidate that failed to converge, was rejected by the energy-plausibility guard, disagreed across phase 5's starts, or did not end in the basin of the structure it was given.

**Nothing was loosened to make a failure pass.** fmax, the maximum-stress criterion and the guard are identical on every retry rung; only the starting point and the step cap change. A retried job either genuinely converges to a plausible, structure-matched result or it stays counted-and-excluded.

> **The retry is the perturbed restart, not the ladder's first rung.** The production ladder's first rung continues from the previous relaxation's end point. For a candidate that already converged - which is nearly all of this set, since the dominant failure class is 'the relaxation left its start' rather than 'it failed' - that rung restarts at the point it converged to and converges again, testing nothing. Those candidates get the other rung: a fixed-seed rattle and strain of the ORIGINAL structure at the extended step cap, which is a different entry into the same basin question. The full ladder is used only for the candidates whose first attempt gave no usable result at all.

| failure class | candidates |
|---|---|
| guard_rejected | 6 |
| left_its_start | 2890 |
| multistart_disagree | 204 |
| not_converged | 6 |

A candidate can be in several classes, so these do not sum to the 3044 retried.

| failure class | n | resolved | genuine | rate | what 'resolved' means here |
|---|---|---|---|---|---|
| not_converged | 6 | 4 | 2 | 0.667 | a converged, physically plausible result now exists |
| guard_rejected | 6 | 4 | 2 | 0.667 | a converged, physically plausible result now exists |
| multistart_disagree | 204 | 111 | 93 | 0.544 | the lowest-energy result is reached from at least two starts |
| left_its_start | 2890 | 118 | 2772 | 0.041 | some attempt ends in the basin of the structure it was given |

### By family

| family | n | not_converged resolved / genuine | guard_rejected resolved / genuine | multistart_disagree resolved / genuine | left_its_start resolved / genuine |
|---|---|---|---|---|---|
| carbide | 243 | - | - | 12 / 5 | 5 / 224 |
| halide | 674 | - | - | 23 / 17 | 24 / 623 |
| halide_topup | 535 | - | - | 15 / 26 | 20 / 494 |
| nitride | 249 | - | - | 12 / 14 | 11 / 217 |
| oxide | 710 | 4 / 2 | 4 / 2 | 26 / 13 | 26 / 648 |
| sulfide | 633 | - | - | 23 / 18 | 32 / 566 |

### What the retry recovered, and what it did not

**Hard failures are rare and mostly recoverable.** Six candidates out of the 18,599 relaxed across round 1 and round 2 failed to converge or were rejected by the guard - and all six are oxides. Four of the six converge to a plausible result on the retry; two do not, and stay counted-and-excluded. Those two are the engine's genuine limit on this set, not the method's.

**Multi-start disagreement is about half recoverable.** Of the 204 candidates whose starts disagreed, 111 have a lowest-energy minimum that at least two starts reach once the perturbed restart is added, which is what 'best of the multi-start attempts' is supposed to buy. The remaining 93 have a best result found by exactly one start, and no amount of retrying at fixed tolerances changes that: the model's surface has several minima there and nothing in the pipeline can say which is the material.

> **'The relaxation left its start' is not a failure, and the retry is what proves it.** It is the largest class by far - 2,890 candidates - and only 4.1% of them end anywhere near their starting structure when restarted from a perturbation of it. The reason is that a WBM initial structure is a pre-DFT elemental-substitution guess, not a claimed minimum, so a relaxation leaving it is the expected behaviour rather than a fault. Test 4 measured this quantity against a known DFT-relaxed target, where leaving really is a failure; carrying the same metric to WBM measures something else.

That has a concrete consequence for the product, and it is a reassuring one. The routing policy excludes a candidate whose relaxation changed the structure (`route_structure_change` defaults to true), and those exclusions are what the certified thresholds were fitted on. The 95.9% genuine rate says that exclusion is stable rather than flaky: a candidate excluded this way would be excluded again on a different run. It is a reproducible property of the structure and the engine, not of one optimiser trajectory.

The right structure-finding measure for a candidate with no known target is section 17's multi-start disagreement, not this class.


## The master family table, updated

This is test 7's per-family table, in the same format, extended with every family round 2 touched. It supersedes the two-row version in section 7 of the existing document. Every figure is the certified threshold where one exists, and the pessimistic bound in every case; `n` is usable rows after guard rejections, which are counted and excluded.

| family | n usable | base rate | stable side | unstable side | stable-side diagnosis |
|---|---|---|---|---|---|
| oxide | 3,994 | 0.112 | not certified ceiling 0.8750, CP-lower 0.8005 | **+0 meV** CP-lower 0.9927 discards 0.881, loses 0.173 of stable | precision limited |
| halide (combined, n=6,300) | 6,300 | 0.235 | **-70 meV** CP-lower 0.9028 | **+0 meV** CP-lower 0.9928 discards 0.744, loses 0.112 of stable | certified |
|   of which fluoride | 2,241 | 0.250 | not certified ceiling 0.9029, CP-lower 0.8133 | **+10 meV** CP-lower 0.9889 discards 0.644, loses 0.045 of stable | sample-size limited needs ~1,393,121 structures |
|   of which non-fluoride | 4,059 | 0.226 | **-20 meV** CP-lower 0.9217 | **+0 meV** CP-lower 0.9909 discards 0.759, loses 0.102 of stable | certified |
| sulfide | 4,000 | 0.128 | not certified ceiling 0.9703, CP-lower 0.8747 | **-10 meV** CP-lower 0.9953 discards 0.897, loses 0.269 of stable | sample-size limited needs ~6,416 structures |
| nitride | 2,423 | 0.092 | not certified ceiling 0.9859, CP-lower 0.8745 | **-10 meV** CP-lower 0.9907 discards 0.934, loses 0.351 of stable | sample-size limited needs ~3,106 structures |
| carbide | 1,876 | 0.099 | **-20 meV** CP-lower 0.9294 | **-10 meV** CP-lower 0.9953 discards 0.922, loses 0.247 of stable | certified |

> **fluoride and non-fluoride are rows of the same 6,300 structures, not extra data.** Fluoride is a subset of halide, so the two sub-rows partition the halide row rather than adding to it. They are shown because the split changes the answer: certifying halide whole buys -70 meV/atom, certifying it without fluoride buys -20 meV/atom.

f-electron and intermetallic are unchanged and are not reproduced here; see the existing document. Nothing in this table has been frozen into `data/calibration_bundle.json`, which still records the round-1 state.


## What the tests say when read together - what round 2 changed

The existing document closes on five numbered takeaways. These extend them; none is retracted.

### 1. Coverage is still the binding constraint, but it is no longer stuck

Test 4's central finding was that the published precision had been measured almost entirely on f-electron chemistry, which barely appears in real use, and that 82% of real candidates went to DFT because their families had no certified threshold. Round 2 moves four families off that list. Halide now certifies both sides. Carbide certifies both sides. Sulfide and nitride certify the unstable side and miss the stable side narrowly. Oxide still certifies only the unstable side.

### 2. The sample-size / precision-limited distinction paid for itself, and needs a third term

Test 7 introduced it to decide where more compute was worth spending, and the prediction held: halide was called sample-size limited, 2,800 more structures were run, and the stable side certified. The phase 1 diagnostic then spent about 25 minutes of compute to decide where the next 14 hours should go, and was right about all four families it examined.

What round 2 adds is that 'sample-size limited' is not by itself an instruction to collect more data. Fluoride's point precision is above target, so the label applies - but reaching the bound would take 1,393,121 calibration structures, 6.5x WBM's whole unique-prototype pool. Sulfide and nitride are genuinely limited and genuinely out of reach: they need about 6,416 and 3,106 structures against the 4,874 and 2,423 their pools could supply. The useful question is not which of the two labels a family gets, but whether the indicated calibration set can actually be drawn.

### 3. Chemistry families are the wrong grain in at least one place

Halide certifies at -70 meV/atom as one family. Split fluoride out and the remaining halides certify at -20 meV/atom - a far more inclusive threshold, labelling many more candidates - while fluoride certifies nothing at 0.90 and nothing at 0.80 either. One sub-chemistry was holding back a family it was lumped with, and the frozen taxonomy cannot see it.

The same move does not rescue oxide. Eleven splits were searched - transition metal against main group, formal cation oxidation state, mixed valence - and none certifies at 0.90. Oxide has no viable stable-side path at the published target, and the answer to test 7's open question is no.

### 4. Structure-finding is measurable without a known target, and it says what test 4 said

The >0.3 eV/atom refusal rested on a structure-finding sample of n = 16, flagged as open work. Multi-start disagreement measures the same reliability on 1,000 candidates with no known target structure, and reaches 50.9% above 0.3 eV/atom against 5.6% in the 0-0.025 bin. Two independent measurements now support the refusal, and the disagreement rate is low exactly where the certified stable thresholds operate.

### 5. The guards earned their place again, and so did distrusting my own code

The engine assertion aborted on a wrong HARNESS_MODEL in a negative test before any phase ran - the exact failure that produced a wrong certification verdict in test 7. The split's disjointness assertion caught 619 ids that a first, wrong draw had put in a calibration set and a locked half at the same time.

Three bugs in this round's own analysis code were caught by looking at the numbers rather than by any guard, and all three would have produced quietly plausible results. The mixed-valence split matched nothing because `oxi_state_guesses` returns a tuple and the test compared it to a list. The multi-start comparison excluded the calibration relaxation from all 1,000 candidates because a None rejection round-trips through pandas as NaN and `not NaN` is False. The same NaN routed every retry to the wrong ladder rung. None of them raised; each produced a table that looked reasonable. The check that caught all three was reading a count that should not have been what it was - 0 mixed-valence oxides, 0 candidates with three usable starts, 0 perturbed restarts.


## Time against budget

The brief budgeted wall-clock per phase on an assumed 9.8 s per relaxation. That figure is section 1's engine-screening benchmark, measured on the screening subset's larger cells; WBM calibration structures average 8.6 atoms and the production engine relaxes them far faster. Measured on the completed round-1 run before any round-2 phase started: 15,000 jobs in 57 minutes, or 0.23 s per job. The budgets were recomputed on that basis after phase 1, as the brief required, rather than being allowed to drift.

| phase | budget | actual | what dominated |
|---|---|---|---|
| 0 setup | not budgeted | 0.3 h | repo read, the round2 module, the split and the phase driver with its engine guard |
| 1 diagnostic | 2 h | 0.4 h | 3,000 jobs in 9.2 min at 5.4 jobs/s, plus the diagnosis |
| 2 halide top-up | 6 h | 0.6 h | 5,600 jobs in 20.3 min at 4.6 jobs/s, plus the certification |
| 3 new families | 14 h | 0.8 h | 13,598 jobs in 37.5 min at 6.0 jobs/s, plus the certification |
| 4 oxide subfamilies | 6 h | 0.3 h | analysis only; no new structures were run |
| 5 multi-start | 8 h | 3.4 h | 2,000 extra relaxations at 5.9 s each of wall clock - a perturbed or compressed start costs about 15x a WBM initial structure, which is what the 9.8 s assumption would have caught if it had applied anywhere |
| 6 failure retry | 8 h | 4.8 h | 3,044 retries; a first attempt was abandoned after 2.2 h because six ladder jobs at up to 5,400 s each were holding the pool, and is not counted here - it is counted in the total below |
| 7 + 8 reports | 6 h | 0.6 h | this document and its markdown source |
| TOTAL | 48 h | 13.4 h | including the 2.2 h lost to the phase-6 pool ordering and the time spent re-deriving three silent analysis bugs |

## Locked and unopened as of this document

'unopened' means: the hash still verifies, the accessor still raises PermissionError without unlock=True, and no id of the set has a result in the results store under the production tag. The original WBM test set was opened once by design on 2026-09-12 and is reported as such; round 2 did not open it again and did not open any other.

| locked set | n | hash verifies | accessor refuses without unlock | ids with results in the store | state |
|---|---|---|---|---|---|
| original WBM locked test | 4000 | yes | yes | 4000 | opened once, 2026-09-12, reports/final_test.md |
| oxide locked test (round 1) | 2000 | yes | yes | 0 | UNOPENED |
| halide locked test (round 1) | 2000 | yes | yes | 0 | UNOPENED |
| sulfide locked test (round 2) | 874 | yes | yes | 0 | UNOPENED |

Round 2 drew 11,099 new calibration structures and never passed `unlock=True` anywhere. Every phase asserted this before enqueueing anything, alongside the engine check. The one new locked half round 2 created - 874 sulfide ids - is listed above and has not been opened either.

> **Sulfide could be certified at 0.90 by dissolving that half into its calibration set, and it was not.** Sulfide needs about 6,416 calibration structures and has 4,000; adding the 874 would still leave it short, and would spend a held-out half for a result that would then have nothing to validate against. The same is true of relaxing the reduced-formula leakage guard, which dropped 4,111 candidates across the round-2 draw. Neither is a decision this document should make.

