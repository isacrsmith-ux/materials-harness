# Evidence tiers — what each result in this project is, and is not

Three kinds of evidence exist here. They are not interchangeable, and the difference is the whole
point of the harness.

> **Round 4 and Path-B results are development/calibration results. Unless explicitly identified as
> preregistered held-out results, they must not be interpreted as independent estimates of
> production performance.**

## Tier 1 — development / calibration evidence

Thresholds selected on a population, then scored on that same population.

**This is the most optimistic estimate that exists.** A threshold chosen because it looked good on a
set of rows will look good on those rows. The Clopper-Pearson bounds reported for development
results are corrected for the threshold grid, which stops the *selection* from inflating the
guarantee, but no correction makes an in-sample estimate into an out-of-sample one.

Everything in `reports/public/round4_development_results.md` and `results/public/` is tier 1:

- the round-4 re-measurement of f-electron, intermetallic and pnictide;
- the Path-B (second-engine) refit and the A / B-old / B-refit comparison;
- the family-corrected sensitivity analysis.

**None of it is validated. None of it is production-ready.** A row whose
`meets_target_in_development` is true has met the target *on the data it was fitted to*, and that is
all that column claims.

## Tier 2 — preregistered held-out evidence

A protocol frozen and committed **before** the evaluation sample is opened: thresholds fixed,
hypotheses named, targets and confidence fixed, pass/fail rules and stop rules written down, the
sample's hash recorded, and the sample opened exactly once. A miss is reported as a miss.

This project has produced tier-2 evidence once: the halide locked-half evaluation of
18 September 2026, whose three primary hypotheses passed and whose rationale check did **not**
reproduce — a result left unresolved rather than tidied away.

One tier-2 evaluation is currently **pre-registered but not run**: a pnictide held-out test of the
`-20 / +0 meV` thresholds. Its protocol is frozen; **its sample does not exist**. Nothing about it
appears in this export except the fact of it.

## Tier 3 — production-adopted rules

What `harness.predict` actually loads and applies: `data/calibration_bundle.json`.

**No result described in this export is adopted in production.** At the time of this export the
active bundle is unchanged from 12 September 2026. In particular:

| family | production stable rule | production unstable rule |
|---|---|---|
| f-electron | −20 meV | +10 meV |
| intermetallic | none | +0 meV (single engine) |
| pnictide | none | +50 meV single engine; **none** with a second engine |

The pnictide `none / none` entry in the second-engine rule table is the defect the round-4 work
measured. It is still there. Measuring a defect and fixing it are different acts, and only the first
has happened.

## How to tell which tier you are reading

| signal | tier |
|---|---|
| lives under `results/public/` or `reports/public/` | 1 — development |
| `evidence_tier` column says `development` | 1 |
| has a committed preregistration whose hash matches, plus a one-time opening log | 2 |
| appears in `data/calibration_bundle.json` | 3 |

If a claim cannot be placed in this table, it is not yet evidence of anything.
