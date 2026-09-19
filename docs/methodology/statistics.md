# Statistical methodology

Applies to every number in `results/public/` and `reports/public/`.

## The two questions and their targets

| side | label | metric | target |
|---|---|---|---|
| stable | "likely stable" | precision — of the candidates called stable, how many truly are | **0.90** |
| unstable | "likely unstable" | NPV — of the candidates called unstable, how many truly are unstable | **0.95** |

"Truly stable" means a true hull distance within `metrics.ON_HULL_TOL` of the convex hull, using
WBM's `e_above_hull_mp2020_corrected_ppd_mp` column.

## Confidence bounds

One-sided **Clopper-Pearson** lower bound on a binomial proportion, at confidence 0.95. Never a
bootstrap: the quantities are proportions of small counts, where a bootstrap under-covers.

**The verdict is read from the bound, never from the point estimate.** A point estimate of 0.94 with
a bound of 0.89 does not meet a 0.90 target. This rule is applied without exception, including where
it produces an unwelcome answer — see the f-electron result.

## Grid correction (applied to all development fits)

A threshold is chosen by searching a 61-point grid from −0.30 to +0.30 eV/atom in 0.01 steps.
Searching a grid and then reporting the best result inflates the guarantee, so every bound is
computed at a Bonferroni-corrected level:

```
level = 1 - (1 - 0.95) / 61
```

A threshold is treated as meeting its target only when the corrected bound clears it. A side needs
at least 20 calls (`confidence.MIN_SELECTED`) for a threshold to be considered at all.

## Family / path / side multiplicity — stated, not hidden

The round-4 development fits selected **3 families × 2 sides = 6 thresholds** with only the grid
correction applied. The Path-B refit selected the same 6 again on a filtered subset of the same rows:
**12 selections on overlapping rows, neither fit family-corrected.**

That makes the Path-A vs Path-B comparison apples-to-apples but **both sides of it optimistic.** The
export therefore carries a sensitivity experiment repeating every selection under an additional
6-fold Bonferroni:

```
level = 1 - (1 - 0.95) / (61 x 6)
```

The result matters and is published rather than buried: **f-electron's Path-B stable threshold does
not survive it.** Its bound falls from 0.900359 to **0.892556**, a margin of −0.0074 against the
0.90 target. intermetallic and pnictide are unchanged by the correction.

### Why the held-out protocol corrects differently

The pre-registered pnictide protocol applies **no grid correction at all**, because its thresholds
are fixed in advance and nothing is selected on the held-out data. It applies **no family
correction**, because only one family is tested. It applies a 4-fold Bonferroni over its four
hypotheses. Correction structure follows from what is being selected, not from convention.

### Dependence between the paths

Path B is a strict **subset** of Path A — B is A minus the rows where the two engines disagree
beyond tolerance. The two tests are nested and strongly positively dependent, so a Bonferroni
correction across them is conservative rather than wrong: Bonferroni rests on Boole's inequality and
assumes nothing about independence. Dependence costs power, not validity. The pre-registered
protocol resolves this in advance rather than after seeing results.

## The labelable population, and every exclusion

Certification is on **labelable** rows, which is the population `calibration.fit()` takes and the
population the product actually labels. A row is labelable when all of the following hold:

1. **not guard-rejected** — it survives the energy-plausibility guard. Rejections are counted and
   excluded, never dropped silently.
2. **no weak element** — its composition contains none of `Be`, `Pm`, `Pu`, `Tc`, the elements whose
   per-element calibration error exceeded the caution threshold.
3. **structure did not change** — the relaxation did not leave its starting structure in a way the
   product refuses to label.
4. **(Path B only) the engines agree** — `|pred_engine1 − pred_engine2| <= 0.165255 eV/atom`.

A fifth exclusion, the product's refusal above 0.3 eV/atom predicted hull distance
(`predict.MAX_TRUSTWORTHY_HULL_EV`), is **not** applied to the primary populations, because the
thresholds were fitted without it. It appears as a descriptive path C only.

### A behaviour worth knowing about exclusion 4

A row with **no usable second-engine result** passes the disagreement term untested, because
`abs(NaN) > tol` is false in the implementation. This is production's real behaviour — `predict`
warns that "the certified thresholds in use assume the disagreement check ran" and then labels the
candidate anyway. Rather than quietly folding those rows in, their count is published
(`n_missing_second_engine_result`); it is 7 rows of 12,000.

### All-usable is a diagnostic only

Figures on the all-usable footing (guard-surviving, but before exclusions 2–4) are retained in the
full internal reports as a secondary diagnostic of engine behaviour. They are never a certification
basis and can never change a verdict.
