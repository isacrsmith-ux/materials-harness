# Polymorph ranking — MACE-MPA-0 medium

Generated from settings tag `c2480e74`. 297 Materials Project compositions scored, 3 not scored, 4 of 1144 relaxations rejected by the guard (counted, never averaged in). Brackets: 95 % bootstrap intervals; verdicts from the pessimistic end, as everywhere else in this project.

## The question

A scientist rarely asks *is this exact structure stable* — they ask *which form of this composition wins*. That question has no hull and no reference cell in it: the forms share a composition, so the answer is decided entirely by energy differences of tens of meV/atom. MP2020 corrections are identical for every polymorph of one composition and cancel out of every number below; MP's uncorrected GGA/GGA+U energies are the truth, which is what the engine was trained to reproduce.

## The set

* MP compositions with 3–8 known polymorphs inside a 0.2 eV/atom window, cells ≤ 40 atoms.
* 4,509 compositions are eligible; 300 were drawn at random (seed 20260912, fixed-seed random draw from every eligible composition; no stratification), giving 1144 relaxations.
* Deduplicated with StructureMatcher on the PBE structures — MP holds the same structure more than once (different magnetic settings, different tasks). Dropped at curation: duplicate structure in MP: 147, fewer than 3 distinct forms after dedupe: 59.
* Every form is relaxed from its own MP PBE structure with the production engine.

## Headline

| quantity | value | verdict |
|:--|:--|:--|
| ground state ranked first | 0.69 [0.63, 0.74] | **use with caution** |
| Spearman ρ of the full ordering (mean over compositions) | 0.66 [0.60, 0.71] | **use with caution** |
| error on the energy gaps from the ground state | 19.4 [17.3, 21.7] meV/atom | **trustworthy** |
| … median \|error\| / 10 % trimmed mean | 8.2 [7.2, 9.0] / 11.9 [10.8, 13.2] meV/atom | — |

A composition here has 3.8 usable forms on average, so picking the ground state at random would be right about 26% of the time.

## Where it is right and where it is not

**By how hard the ranking is** — the DFT gap between the ground state and the runner-up. A 5 meV/atom gap is below this engine's own error on new materials, so getting it right there is close to a coin flip by construction.

| DFT gap to the runner-up (meV/atom)   |   n | ground state first   | Spearman ρ        | gap MAE           | median |gap err|   | trimmed mean      |
|:--------------------------------------|----:|:---------------------|:------------------|:------------------|:-------------------|:------------------|
| ≤10                                   | 133 | 0.55 [0.47, 0.62]    | 0.59 [0.50, 0.68] | 13.7 [11.4, 16.3] | 5.7 [4.9, 6.9]     | 8.4 [7.3, 9.6]    |
| 10–50                                 | 126 | 0.78 [0.70, 0.85]    | 0.70 [0.61, 0.77] | 20.7 [17.7, 23.9] | 9.7 [8.5, 11.9]    | 14.1 [12.2, 16.3] |
| 50–200                                |  38 | 0.87 [0.76, 0.97]    | 0.76 [0.61, 0.89] | 39.3 [29.0, 51.3] | 13.6 [10.5, 22.4]  | 27.6 [19.5, 38.8] |

**By the composition's distance from the hull**

| composition hull bin   |   n | ground state first   | Spearman ρ        | gap MAE           | median |gap err|   | trimmed mean      |
|:-----------------------|----:|:---------------------|:------------------|:------------------|:-------------------|:------------------|
| ≤0.025                 | 138 | 0.76 [0.69, 0.83]    | 0.78 [0.72, 0.84] | 13.0 [10.9, 15.2] | 5.7 [4.5, 6.7]     | 8.1 [6.9, 9.4]    |
| 0.025–0.1              |  78 | 0.59 [0.49, 0.69]    | 0.59 [0.48, 0.70] | 15.9 [12.9, 19.2] | 8.5 [7.0, 10.3]    | 10.7 [9.0, 12.8]  |
| 0.1–0.3                |  68 | 0.65 [0.53, 0.76]    | 0.50 [0.36, 0.64] | 31.2 [25.5, 37.4] | 16.2 [12.5, 21.1]  | 22.5 [18.4, 27.0] |
| >0.3                   |  13 | 0.69 [0.46, 0.92]    | 0.56 [0.19, 0.88] | 46.2 [23.0, 72.3] | 11.5 [2.6, 31.7]   | 31.7 [12.1, 60.8] |

**By chemistry**

| chemistry   |   n | ground state first   | Spearman ρ        | gap MAE           | median |gap err|   | trimmed mean      |
|:------------|----:|:---------------------|:------------------|:------------------|:-------------------|:------------------|
| metallic    |  44 | 0.59 [0.45, 0.73]    | 0.52 [0.32, 0.71] | 17.3 [14.0, 21.1] | 12.1 [9.7, 14.2]   | 14.0 [11.5, 17.0] |
| compound    | 253 | 0.70 [0.65, 0.76]    | 0.68 [0.62, 0.74] | 19.7 [17.4, 22.2] | 7.4 [6.4, 8.6]     | 11.7 [10.4, 13.1] |

## What the relaxation did to the forms

* In 14% of scored compositions, the relaxation drove two distinct MP forms into the **same** structure. Their relative ranking is meaningless whatever the energies say, and a product that reports an ordering without saying this is reporting noise as a result.
* 83% of relaxed forms still match the MP structure they started from (species-aware StructureMatcher, default tolerances). The rest moved somewhere else — sometimes onto another form of the same composition, which is the line above.

* 4 relaxations were rejected by the guard and excluded from every statistic: not converged (4).

* For 1 composition(s) the Spearman ρ is **undefined**: the engine gave every form the same energy, so there is no ordering to correlate. Those are excluded from the ρ column and counted here, never averaged in as a zero.

* 3 compositions are **not scored**: only 2 usable forms (need 3) (3).

## Caveats

* **These are known materials.** The engine trained on MPtrj, which is built from Materials Project, so this measures ranking skill on material it has seen. `reports/unseen_test.md` is the test that holds the target out; this one does not.
* **No spin.** The engine has no explicit magnetism, and MP polymorph sets frequently differ by magnetic ordering. Where deduplication left two forms that DFT distinguishes only by spin, the engine cannot tell them apart in principle.
* **Ties.** DFT energies within 1 µeV/atom count as tied, and a tie counts as a hit for any tied form.
* `config/costs.json` still holds 1:1 placeholder costs; nothing here is optimised against them.

