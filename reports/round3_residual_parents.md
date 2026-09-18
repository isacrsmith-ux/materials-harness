# Round 3 — the residual parents, measured properly

Engine MACE-MPA-0 medium cpu/float32, settings_tag c2480e74. Generated 2026-09-18T18:24:33+00:00. Footing: labelable rows — bundle weak-element list + structure-change exclusion, no second-engine term; the authoritative certification population.

Round 2 drew sulfide and carbide but never drew chalcogenide or 'other', so what would be left of those parents after the carve-outs could only be read off the handful of rows the original calibration set happened to contain. These are representative 4,000-structure draws of the residuals themselves, from ids no earlier split has touched.

**Nothing here is adopted and no locked half is opened.**

## True composition of each parent in the WBM pool

| parent | total in pool | residual share | child share |
|---|---:|---:|---:|
| chalcogenide | 13,441 | 0.6212 | sulfide 0.3750 |
| other | 16,685 | 0.8921 | carbide 0.1079 |

The 'whole' rows below reconstruct the undivided parent by subsampling the child draw down to that true share, so the mixture is the real one and every count stays an integer for Clopper-Pearson.

## chalcogenide (carving out sulfide)

Residual draw: 4,000 structures, 0 rejected by the guard (counted and excluded), 3,559 labelable. Child draw: 3,402 labelable, of which 2,149 are used to reconstruct the undivided parent.

The previous estimate of this residual rested on 130 labelable rows from the original calibration set.

| population | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall | stable lost | to DFT |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| whole parent, before carve-out | 5708 | 0.152 | **-20 meV** | 0.9577 | 0.9224 | **+0 meV** | 0.9733 | 0.9652 | 0.575 | 0.149 | 0.062 |
| residual parent, after carve-out | 3559 | 0.161 | **-20 meV** | 0.9610 | 0.9156 | **+0 meV** | 0.9691 | 0.9579 | 0.558 | 0.161 | 0.069 |
| sulfide (the child) | 3402 | 0.134 | **-30 meV** | 0.9615 | 0.9047 | **+0 meV** | 0.9806 | 0.9712 | 0.495 | 0.125 | 0.068 |

## other (carving out carbide)

Residual draw: 4,000 structures, 0 rejected by the guard (counted and excluded), 3,510 labelable. Child draw: 1,647 labelable, of which 425 are used to reconstruct the undivided parent.

The previous estimate of this residual rested on 248 labelable rows from the original calibration set.

| population | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall | stable lost | to DFT |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| whole parent, before carve-out | 3935 | 0.103 | **-20 meV** | 0.9609 | 0.9031 | **-10 meV** | 0.9645 | 0.9538 | 0.547 | 0.319 | 0.019 |
| residual parent, after carve-out | 3510 | 0.106 | **-70 meV** | 1.0000 | 0.9021 | **-10 meV** | 0.9629 | 0.9512 | 0.186 | 0.323 | 0.060 |
| carbide (the child) | 1647 | 0.108 | **-20 meV** | 0.9826 | 0.9043 | **-10 meV** | 0.9708 | 0.9545 | 0.635 | 0.247 | 0.015 |

