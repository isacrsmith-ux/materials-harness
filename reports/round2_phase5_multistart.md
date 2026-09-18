# Phase 5 — multi-start structure verification

Source: `results/round2_multistart.json`. Engine mace-mpa-0-medium cpu/float32, settings_tag `c2480e74`. 1000 candidates, each relaxed from three starting configurations instead of one.

| start | what it is |
|---|---|
| `A_wbm_init` | WBM initial structure (the calibration relaxation) |
| `B_compressed` | same cell, volume x 0.95 |
| `C_perturbed` | rattle 0.02 A + strain 0.005, 1x1x1, seed = sha256(wbm_id) |

A candidate is counted as **disagreeing** when its usable starts do not all land in the same structure, or their predicted hull distances span more than 25 meV/atom. Starts the convergence or energy-plausibility guard rejected are counted and excluded, never dropped: they appear in `starts excluded` and reduce the number of starts a candidate can be compared on.

## By family

| family | n | all 3 starts usable | starts excluded | disagreement | structure | energy | median spread |
|---|---:|---:|---:|---:|---:|---:|---:|
| carbide | 101 | 100 | 1 | 0.168 | 0.158 | 0.139 | 0.0 meV |
| halide | 188 | 188 | 0 | 0.213 | 0.186 | 0.128 | 0.0 meV |
| halide_topup | 151 | 151 | 0 | 0.272 | 0.258 | 0.192 | 0.0 meV |
| nitride | 130 | 130 | 0 | 0.200 | 0.146 | 0.185 | 0.0 meV |
| oxide | 215 | 215 | 0 | 0.181 | 0.153 | 0.130 | 0.0 meV |
| sulfide | 215 | 215 | 0 | 0.191 | 0.186 | 0.158 | 0.0 meV |
| **all** | **1000** | 999 | 1 | **0.204** | 0.182 | 0.153 | 0.0 meV |

## By true hull-distance bin

| bin | n | disagreement | structure | energy | median spread |
|---|---:|---:|---:|---:|---:|
| <0 | 152 | 0.086 | 0.079 | 0.046 | 0.0 meV |
| 0–0.025 | 107 | 0.056 | 0.047 | 0.037 | 0.0 meV |
| 0.025–0.1 | 246 | 0.175 | 0.150 | 0.102 | 0.0 meV |
| 0.1–0.3 | 326 | 0.172 | 0.147 | 0.126 | 0.0 meV |
| >0.3 | 169 | 0.509 | 0.473 | 0.450 | 9.2 meV |
