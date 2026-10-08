# Engine vacancy energies against a PBE DFT population (Angsten et al. 2014)

> **DEVELOPMENT / DESCRIPTIVE TIER. Evidence, no verdict.** The reference is **PBE DFT, not experiment**: agreement
> with it measures fidelity to another calculation, not accuracy. Nothing here licenses a production change.

Generated 2026-10-08T02:43:19Z by `scripts/aerospace_vacancy_population_report.py` from
`reports/aerospace_vacancy_population/<engine>.json`. Checkpoints: MPA-0 `75428afe3a1d`, MP-0 `01bfe2210013`.

## Reference and protocol

- **Reference:** Angsten, Mayeshiba, Wu, Morgan, *New J. Phys.* **16**, 015018 (2014), doi:10.1088/1367-2630/16/1/015018, appendix
  Tables A.1 (fcc) and A.2 (hcp), CC BY 3.0 (page capture sha256 `a48f8a37d602`). The NIST dataset it points
  to (hdl:11256/102) did not resolve, so its licence was not read; the paper's own tables are used (`docs/methodology/data_provenance.md`).
- **The reference's own DFT** (what the numbers are): VASP 5.2.2, PBE, PAW; fcc 3x3x3 conventional cells (108 sites), hcp 3x3x2 (36 sites); the defect cell at
  the fixed volume of the relaxed perfect cell. The paper states a **20-30 meV size-effect error** and k-point errors of 18 meV (Al) and 9 meV (Mg). Values are
  printed to 0.01 eV.
- **Engine protocol, primary comparison:** the same cells and the same protocol: relax the 2- or 4-atom cell to zero pressure from the paper's tabulated atomic
  volume, repeat to the paper's cell, remove one atom, relax positions at the relaxed-bulk cell (`fixed_cell`, fmax 0.01 eV/A). This is a like-for-like comparison; it is
  *not* a converged-cell value.
- **Convergence (the Phase 0 approach):** the brief's six elements (marked * below), in their usual structure, were also run at two larger cells, in `fixed_cell` and
  `zero_pressure` (defect cell relaxed with its cell) modes.
- **Population:** 78 element-structure pairs (42 fcc, 36 hcp) of 114 table
  rows, unweighted. Excluded, by rules fixed before any engine ran: 1 Mn, 3 negative H_vf, 7 noble gas (vdW solid), 4 non-magnetic row superseded by the spin-polarised row (kept as second reference), 14 paper footnote a, 5 paper footnote b, 2 paper footnote c. Not computed or not converged: MPA-0 0, MP-0 0
  (none).

## Result: engine - reference over the population (the paper's cell and protocol)

| engine / subset | n | median \|engine - ref\| (eV) | mean | max | median signed (eV) | within 0.1 eV | over 0.2 eV |
|---|---:|---:|---:|---:|---:|---:|---:|
| MPA-0 (production), all | 78 | 0.095 | 0.126 | 0.653 | +0.009 | 41 | 14 |
| MPA-0 (production), fcc | 42 | 0.098 | 0.14 | 0.653 | +0.025 | 21 | 10 |
| MPA-0 (production), hcp | 36 | 0.079 | 0.111 | 0.608 | -0.003 | 20 | 4 |
| MPA-0 (production), six focus elements | 6 | 0.083 | 0.087 | 0.195 | +0.083 | 4 | 0 |
| MP-0 (second), all | 78 | 0.189 | 0.372 | 2.272 | -0.170 | 27 | 38 |
| MP-0 (second), fcc | 42 | 0.18 | 0.364 | 2.272 | -0.155 | 16 | 20 |
| MP-0 (second), hcp | 36 | 0.199 | 0.382 | 1.664 | -0.183 | 11 | 18 |
| MP-0 (second), six focus elements | 6 | 0.078 | 0.191 | 0.671 | -0.078 | 3 | 2 |

Same 78 pairs for both engines: MPA-0 median 0.095 eV, max 0.653; MP-0 median
0.189 eV, max 2.272. The two engines differ from each other by a median of 0.118 eV
(max 2.339).

**Outliers** (|engine - ref| over 0.2 eV, about 7 times the paper's stated size error; a reporting convenience, not a tolerance):

- MPA-0 (production): fcc:Er (+0.65), hcp:Fe (-0.61), fcc:Fe (-0.58), fcc:Ce (+0.51), fcc:Sc (-0.39), fcc:Cs (-0.32), hcp:Cs (-0.28), fcc:Pa (+0.27), fcc:Rh (+0.27), hcp:Zr (+0.26), fcc:Ir (+0.23), fcc:Pt (+0.22), hcp:Re (-0.22), fcc:Ru (+0.21)
- MP-0 (second): fcc:Os (-2.27), hcp:Re (-1.66), hcp:Ru (-1.55), hcp:Os (-1.55), fcc:Ru (-1.44), fcc:Re (-1.34), hcp:Tc (-1.31), fcc:Tc (-1.13), fcc:Rh (-0.82), hcp:Fe (-0.80), hcp:Rh (-0.76), fcc:Fe (-0.72), fcc:Er (+0.70), hcp:Ti (-0.67), fcc:Ir (-0.66), fcc:Ti (-0.61), hcp:Co:mag (-0.57), hcp:Ba (-0.55), fcc:Ba (-0.53), hcp:Zr (+0.53), fcc:Zr (+0.48), fcc:Co:mag (-0.46), fcc:Sc (-0.41), hcp:Si (-0.41), fcc:La (-0.38), fcc:Ce (-0.34), fcc:Cs (-0.33), hcp:Sr (-0.32), fcc:Ni:mag (-0.32), hcp:Cs (-0.30), fcc:Pb (-0.29), hcp:Ir (-0.29), fcc:Sr (-0.29), hcp:Ni:mag (-0.25), hcp:Pb (-0.25), fcc:Cd (-0.22), hcp:Y (-0.20), hcp:Rb (-0.20)

For scale, the reference's own stated size and k-point errors are 0.01-0.03 eV and its values are rounded to 0.01 eV. Two PBE references for the same quantity also
differ: the Phase 0 memo's Al value (Hood et al., 0.67 eV) is +0.06 eV from this paper's Al value (0.61 eV), which is larger than the
reference's stated errors. **Reproducibility:** the Al vacancy values of this run reproduce Phase 0's to within
0.0007 eV on both engines (all cells and modes both runs share).

**Equilibrium-volume check** (engine's relaxed atomic volume over the paper's tabulated Omega, which catches a structure that collapsed on relaxation):
MPA-0 median 1.001 (range 0.749 to 1.133), 3 pairs off by more than 10%;
MP-0 median 1.008 (range 0.759 to 1.072), 1 pairs off by more than 10%: fcc:Er (0.759).
MPA-0 off by more than 10%: fcc:Er (0.749), hcp:Cs (1.133), fcc:Cs (1.132).

## Per-element table (* = the brief's six elements in their usual structure)

| structure | element | ref H_vf (eV) | MPA-0 | MP-0 | MPA-0 - ref | MP-0 - ref |
|---|---|---:|---:|---:|---:|---:|
| fcc | Ac | 1.26 | 1.417 | 1.235 | +0.157 | -0.025 |
| fcc | Ag * | 0.68 | 0.776 | 0.679 | +0.096 | -0.001 |
| fcc | Al * | 0.61 | 0.679 | 0.480 | +0.069 | -0.130 |
| fcc | Au | 0.40 | 0.467 | 0.439 | +0.067 | +0.039 |
| fcc | Ba | 1.09 | 0.926 | 0.557 | -0.164 | -0.533 |
| fcc | Ca | 1.13 | 1.021 | 0.950 | -0.109 | -0.180 |
| fcc | Cd | 0.30 | 0.147 | 0.083 | -0.153 | -0.217 |
| fcc | Ce | 1.30 | 1.806 | 0.955 | +0.506 | -0.345 |
| fcc | Co (spin-polarised; non-magnetic ref 1.84) | 1.79 | 1.799 | 1.332 | +0.009 | -0.458 |
| fcc | Cs | 0.34 | 0.023 | 0.008 | -0.317 | -0.332 |
| fcc | Cu * | 1.07 | 1.068 | 1.044 | -0.002 | -0.026 |
| fcc | Er | 1.02 | 1.673 | 1.723 | +0.653 | +0.703 |
| fcc | Fe | 2.32 | 1.741 | 1.601 | -0.579 | -0.719 |
| fcc | Hf | 2.09 | 2.141 | 2.256 | +0.051 | +0.166 |
| fcc | Ho | 1.74 | 1.619 | 1.726 | -0.121 | -0.014 |
| fcc | In | 0.28 | 0.312 | 0.257 | +0.032 | -0.023 |
| fcc | Ir | 1.55 | 1.784 | 0.888 | +0.234 | -0.662 |
| fcc | K | 0.34 | 0.210 | 0.202 | -0.130 | -0.138 |
| fcc | La | 1.44 | 1.394 | 1.064 | -0.046 | -0.376 |
| fcc | Li | 0.60 | 0.588 | 0.621 | -0.012 | +0.021 |
| fcc | Mg | 0.82 | 0.821 | 0.770 | +0.001 | -0.050 |
| fcc | Na | 0.38 | 0.374 | 0.443 | -0.006 | +0.063 |
| fcc | Ni (spin-polarised; non-magnetic ref 1.39) * | 1.43 | 1.540 | 1.115 | +0.110 | -0.315 |
| fcc | Os | 2.75 | 2.817 | 0.478 | +0.067 | -2.272 |
| fcc | Pa | 1.54 | 1.812 | 1.559 | +0.272 | +0.019 |
| fcc | Pb | 0.45 | 0.432 | 0.156 | -0.018 | -0.294 |
| fcc | Pd | 1.16 | 1.209 | 1.181 | +0.049 | +0.021 |
| fcc | Pt | 0.61 | 0.827 | 0.439 | +0.217 | -0.171 |
| fcc | Rb | 0.30 | 0.187 | 0.120 | -0.113 | -0.180 |
| fcc | Re | 2.94 | 2.976 | 1.600 | +0.036 | -1.340 |
| fcc | Rh | 1.57 | 1.838 | 0.748 | +0.268 | -0.822 |
| fcc | Ru | 2.51 | 2.716 | 1.073 | +0.206 | -1.437 |
| fcc | Sc | 2.07 | 1.677 | 1.660 | -0.393 | -0.410 |
| fcc | Sn | 0.26 | 0.322 | 0.224 | +0.062 | -0.036 |
| fcc | Sr | 0.95 | 0.945 | 0.664 | -0.005 | -0.286 |
| fcc | Tb | 1.75 | 1.661 | 1.686 | -0.089 | -0.064 |
| fcc | Tc | 2.62 | 2.514 | 1.490 | -0.106 | -1.130 |
| fcc | Th | 1.92 | 2.015 | 1.953 | +0.095 | +0.033 |
| fcc | Ti | 1.95 | 2.076 | 1.338 | +0.126 | -0.612 |
| fcc | Tl | 0.37 | 0.387 | 0.294 | +0.017 | -0.076 |
| fcc | Y | 1.72 | 1.719 | 1.662 | -0.001 | -0.058 |
| fcc | Zr | 2.02 | 2.120 | 2.504 | +0.100 | +0.484 |
| hcp | Ag | 0.76 | 0.771 | 0.691 | +0.011 | -0.069 |
| hcp | Al | 0.62 | 0.629 | 0.489 | +0.009 | -0.131 |
| hcp | Au | 0.40 | 0.460 | 0.456 | +0.060 | +0.056 |
| hcp | Ba | 1.11 | 0.926 | 0.564 | -0.184 | -0.546 |
| hcp | Be | 1.04 | 0.888 | 1.004 | -0.152 | -0.036 |
| hcp | Ca | 1.06 | 1.014 | 0.952 | -0.046 | -0.108 |
| hcp | Cd | 0.25 | 0.289 | 0.113 | +0.039 | -0.137 |
| hcp | Co (spin-polarised; non-magnetic ref 1.67) | 1.93 | 1.802 | 1.362 | -0.128 | -0.568 |
| hcp | Cs | 0.31 | 0.025 | 0.008 | -0.285 | -0.302 |
| hcp | Cu | 1.04 | 1.057 | 1.054 | +0.017 | +0.014 |
| hcp | Fe | 2.43 | 1.822 | 1.628 | -0.608 | -0.802 |
| hcp | Ga | 0.21 | 0.255 | 0.153 | +0.045 | -0.057 |
| hcp | Hf | 2.26 | 2.412 | 2.292 | +0.152 | +0.032 |
| hcp | In | 0.31 | 0.343 | 0.281 | +0.033 | -0.029 |
| hcp | Ir | 1.25 | 1.441 | 0.958 | +0.191 | -0.292 |
| hcp | K | 0.35 | 0.212 | 0.201 | -0.138 | -0.149 |
| hcp | Li | 0.63 | 0.601 | 0.654 | -0.029 | +0.024 |
| hcp | Mg * | 0.78 | 0.827 | 0.775 | +0.047 | -0.005 |
| hcp | Ni (spin-polarised; non-magnetic ref 1.35) | 1.37 | 1.465 | 1.116 | +0.095 | -0.254 |
| hcp | Os | 3.03 | 3.055 | 1.481 | +0.025 | -1.549 |
| hcp | Pb | 0.41 | 0.410 | 0.161 | -0.000 | -0.249 |
| hcp | Pd | 1.10 | 1.186 | 1.191 | +0.086 | +0.091 |
| hcp | Rb | 0.32 | 0.184 | 0.120 | -0.136 | -0.200 |
| hcp | Re | 3.42 | 3.204 | 1.756 | -0.216 | -1.664 |
| hcp | Rh | 1.53 | 1.601 | 0.768 | +0.071 | -0.762 |
| hcp | Ru | 2.68 | 2.856 | 1.129 | +0.176 | -1.551 |
| hcp | Sc | 1.87 | 1.820 | 1.701 | -0.050 | -0.169 |
| hcp | Si | 0.08 | -0.050 | -0.330 | -0.130 | -0.410 |
| hcp | Sn | 0.40 | 0.350 | 0.235 | -0.050 | -0.165 |
| hcp | Sr | 0.98 | 0.948 | 0.664 | -0.032 | -0.316 |
| hcp | Tc | 2.85 | 2.803 | 1.536 | -0.047 | -1.314 |
| hcp | Ti * | 2.06 | 2.255 | 1.389 | +0.195 | -0.671 |
| hcp | Tl | 0.40 | 0.394 | 0.303 | -0.006 | -0.097 |
| hcp | Y | 1.87 | 1.750 | 1.668 | -0.120 | -0.202 |
| hcp | Zn | 0.47 | 0.361 | 0.272 | -0.109 | -0.198 |
| hcp | Zr | 2.03 | 2.292 | 2.562 | +0.262 | +0.532 |

## Cell-size convergence, the six elements

| element (structure) | ref | engine | cells and modes (N, mode: eV; FC = fixed cell, ZP = zero pressure) | spread (eV) |
|---|---:|---|---|---:|
| fcc:Ag | 0.68 | MPA-0 (production) | 108 FC: 0.776; 108 ZP: 0.773; 256 FC: 0.777; 256 ZP: 0.777; 500 FC: 0.776; 500 ZP: 0.775 | 0.004 |
| fcc:Ag | 0.68 | MP-0 (second) | 108 FC: 0.679; 108 ZP: 0.675; 256 FC: 0.678; 256 ZP: 0.678; 500 FC: 0.678; 500 ZP: 0.678 | 0.004 |
| fcc:Al | 0.61 | MPA-0 (production) | 108 FC: 0.679; 108 ZP: 0.675; 256 FC: 0.677; 256 ZP: 0.677; 500 FC: 0.676; 500 ZP: 0.676 | 0.004 |
| fcc:Al | 0.61 | MP-0 (second) | 108 FC: 0.480; 108 ZP: 0.478; 256 FC: 0.479; 256 ZP: 0.479; 500 FC: 0.479; 500 ZP: 0.479 | 0.002 |
| fcc:Cu | 1.07 | MPA-0 (production) | 108 FC: 1.068; 108 ZP: 1.064; 256 FC: 1.068; 256 ZP: 1.068; 500 FC: 1.056; 500 ZP: 1.057 | 0.012 |
| fcc:Cu | 1.07 | MP-0 (second) | 108 FC: 1.044; 108 ZP: 1.039; 256 FC: 1.042; 256 ZP: 1.041; 500 FC: 1.042; 500 ZP: 1.042 | 0.005 |
| fcc:Ni:mag | 1.43 | MPA-0 (production) | 108 FC: 1.540; 108 ZP: 1.534; 256 FC: 1.536; 256 ZP: 1.533; 500 FC: 1.537; 500 ZP: 1.536 | 0.007 |
| fcc:Ni:mag | 1.43 | MP-0 (second) | 108 FC: 1.115; 108 ZP: 1.109; 256 FC: 1.113; 256 ZP: 1.110; 500 FC: 1.112; 500 ZP: 1.111 | 0.006 |
| hcp:Mg | 0.78 | MPA-0 (production) | 36 FC: 0.827; 36 ZP: 0.822; 96 FC: 0.829; 96 ZP: 0.827; 288 FC: 0.827; 288 ZP: 0.827 | 0.007 |
| hcp:Mg | 0.78 | MP-0 (second) | 36 FC: 0.775; 36 ZP: 0.770; 96 FC: 0.772; 96 ZP: 0.770; 288 FC: 0.771; 288 ZP: 0.771 | 0.005 |
| hcp:Ti | 2.06 | MPA-0 (production) | 36 FC: 2.255; 36 ZP: 2.240; 96 FC: 2.225; 96 ZP: 2.218; 288 FC: 2.210; 288 ZP: 2.204 | 0.051 |
| hcp:Ti | 2.06 | MP-0 (second) | 36 FC: 1.389; 36 ZP: 1.323; 96 FC: 1.329; 96 ZP: 1.301; 288 FC: 1.317; 288 ZP: 1.294 | 0.095 |

The spread is the range over all cells and both modes. The paper's stated size-effect error is 0.02-0.03 eV.

## Migration barriers (stretch goal)

Measured on Al first: 3.9 s for MPA-0, far inside the 20-minute limit, so every pair was run. The method follows the paper's (section 2.5), but it
is a **single-image constrained saddle, not a converged NEB chain**: the migrating atom is placed at the midpoint of the hop (a symmetry point for these hops) and
everything is relaxed with that atom held in the bisecting plane, at the relaxed-bulk cell. It equals the paper's single-image CI-NEB only where the midpoint is the true saddle.
hcp is compared in-plane against H_vm(perp) and out-of-plane against H_vm(par).

| engine / hop | n | median \|engine - ref\| (eV) | max | median signed |
|---|---:|---:|---:|---:|
| MPA-0 (production), all | 112 | 0.071 | 3.634 | -0.014 |
| MPA-0 (production), all excluding negative barriers | 108 | 0.068 | 0.837 | -0.012 |
| MPA-0 (production), hop | 42 | 0.071 | 0.543 | -0.027 |
| MPA-0 (production), in plane | 36 | 0.064 | 2.632 | -0.002 |
| MPA-0 (production), out of plane | 34 | 0.096 | 3.634 | -0.016 |
| MP-0 (second), all | 113 | 0.149 | 3.515 | -0.102 |
| MP-0 (second), all excluding negative barriers | 106 | 0.145 | 2.26 | -0.092 |
| MP-0 (second), hop | 42 | 0.18 | 3.441 | -0.145 |
| MP-0 (second), in plane | 36 | 0.15 | 3.515 | -0.132 |
| MP-0 (second), out of plane | 35 | 0.132 | 2.26 | -0.088 |

**Negative barriers.** A "barrier" below zero means the constrained midpoint relaxed *below* the relaxed vacancy: the method found a lower state, not a saddle. That may mean the host structure is not a
minimum for that engine; this was not checked. They are kept in the first row and left out of the second. MPA-0: 4
(fcc:Ti hop, hcp:Ga out_of_plane, hcp:Si in_plane, hcp:Si out_of_plane). MP-0: 7
(fcc:Ce hop, fcc:Os hop, fcc:Ti hop, hcp:Ga in_plane, hcp:Ga out_of_plane, hcp:Si in_plane, hcp:Sn in_plane). Large positive differences remain after that (see the JSON `pairs`), so treat these
barriers as a rough screen, not as converged NEB values.

## What this does and does not say

- **Does:** on 78 metals the production engine reproduces PBE vacancy formation energies to a median of 0.095 eV; the second engine to 0.189 eV. The
  engines were trained on PBE data of the Materials Project convention, so this is partly convention fidelity.
- **Does not:** say the engines are accurate (the reference is not experiment); cover alloys, defect complexes, close approach (Phase 0 and Stage 1 found that the engine fails there) or
  radiation damage; replace the converged-cell value (the cells here are the paper's, not infinite).
- **Metastable structures** are in the population (the paper tabulates both fcc and hcp for every element). They are not weighted down; the fcc and hcp rows are reported separately.
- **Float32.** MPA-0 runs float32 and its relaxations carry about 1-5 meV of run-to-run noise (Stage 1 gate 2 diagnosis), small against the 0.1 eV scale of the medians above.

## Open decisions

1. **Is a vacancy-population check the right next step, or does the product need the E_d result?** This is a static, near-equilibrium
   quantity; it does not touch the short-range regime the aerospace question needs. (HANDOFF, Stage 2.)
2. **Whether to read the NIST dataset when it is reachable**, in case it carries more than the paper's tables (for example per-structure convergence).
