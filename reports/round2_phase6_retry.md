# Phase 6 — retesting every failure found in phases 1-5

Source: `results/round2_retry.json`. Engine mace-mpa-0-medium cpu/float32, settings_tag `c2480e74`. Retry ladder: config.FALLBACK_LADDER — the perturbed restart from the ORIGINAL structure at a 1,000 step cap for every candidate whose rung 1 already gave a usable result, and the full ladder (FIRE/1500 continuing, then the perturbed restart) for the ones it did not.

**fmax, max stress and the energy-plausibility guard are identical on every rung.** A retried job either genuinely converges to a plausible, structure-matched result or it stays counted-and-excluded.

3044 candidates were in at least one failure class. A candidate can be in several, so the class counts sum to more than the total.

## Outcome by failure class

| failure class | n | resolved | genuine | rate | what 'resolved' means for this class |
|---|---:|---:|---:|---:|---|
| not_converged | 6 | 4 | 2 | 0.667 | a converged, physically plausible result now exists |
| guard_rejected | 6 | 4 | 2 | 0.667 | a converged, physically plausible result now exists |
| multistart_disagree | 204 | 111 | 93 | 0.544 | the lowest-energy result is reached from at least two starts |
| left_its_start | 2890 | 118 | 2772 | 0.041 | some attempt ends in the basin of the structure it was given |

## Outcome by family

| family | n | not_converged res/gen | guard_rejected res/gen | multistart_disagree res/gen | left_its_start res/gen |
|---|---:|---:|---:|---:|---:|
| carbide | 243 | - | - | 12/5 | 5/224 |
| halide | 674 | - | - | 23/17 | 24/623 |
| halide_topup | 535 | - | - | 15/26 | 20/494 |
| nitride | 249 | - | - | 12/14 | 11/217 |
| oxide | 710 | 4/2 | 4/2 | 26/13 | 26/648 |
| sulfide | 633 | - | - | 23/18 | 32/566 |
