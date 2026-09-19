# Schema — `results/public/`

Aggregate-only export of the round-4 development evidence. **No material identifiers, no random
seeds, no per-bin counts and no row-level data appear in any file here.** See
[`reports/public/WITHHELD.md`](../../reports/public/WITHHELD.md) for what was left out and why.

> **Round 4 and Path-B results are development/calibration results. Unless explicitly identified as
> preregistered held-out results, they must not be interpreted as independent estimates of
> production performance.**

## `round4_aggregate.csv` / `round4_aggregate.json`

One record per (experiment, path, family, side). No record covers fewer than 20 rows.

| column | type | meaning |
|---|---|---|
| `experiment` | string | `round4_pathA_fit` — the single-engine development fit. `round4c_path_comparison` — the three paths each at their own thresholds. `round4c_family_corrected_sensitivity` — which selections survive an additional 6-fold Bonferroni. |
| `path` | string | `A_single_engine` / `A_single_engine_v1_table` (no disagreement term), `B_old_second_engine_v1_table` (the rule table production uses today when a second engine is supplied), `B_refit_second_engine_development` (fitted on the Path-B development population). |
| `family` | string | Chemistry family under `harness.confidence.family()`, first match wins. See the methodology note on precedence. |
| `side` | string | `stable` (the "likely stable" call, scored by precision) or `unstable` (the "likely unstable" call, scored by NPV). |
| `evidence_tier` | string | Always `development` in this export. See `docs/methodology/evidence_tiers.md`. |
| `n_population_labelable` | int | Rows in the scored population after guard rejection and the labelable exclusions. |
| `threshold_ev_per_atom` | float or empty | The decision threshold on predicted hull distance. **Empty means no rule on that side**, so every such candidate is routed to DFT — it is not a missing value. |
| `n_calls` | int | Candidates receiving that label. |
| `n_errors` | int | Calls that were wrong. |
| `point_estimate` | float | Precision (stable side) or NPV (unstable side). |
| `cp_lower_bound` | float | One-sided Clopper-Pearson lower bound at 0.95, Bonferroni-corrected over the 61-point threshold grid. **This, not the point estimate, is what a verdict is read from.** |
| `target` | float | 0.90 for stable precision, 0.95 for unstable NPV. |
| `margin_vs_target` | float | `cp_lower_bound - target`. Negative means the bound misses. |
| `meets_target_in_development` | bool | `cp_lower_bound >= target` **on development data**. This is not a validation claim. |
| `recall_truly_stable` | float | Fraction of truly stable materials in the population that received a "likely stable" label. |
| `dft_routing_fraction` | float | Fraction of the population receiving no label and routed to DFT. |
| `note` | string | Qualifications that must travel with the row, including "no rule on this side" and the meaning of `none` in the sensitivity experiment. |

### Reading the sensitivity experiment

In `round4c_family_corrected_sensitivity`, only `threshold_ev_per_atom` is meaningful. An empty
threshold there means **the selection did not survive** the additional 6-fold Bonferroni over
families × sides — not that no threshold was tried. `meets_target_in_development` in those rows
records only whether a threshold survived.

## `round4_population.csv`

One record per family: the population accounting, including every exclusion.

| column | meaning |
|---|---|
| `n_drawn` | Development structures drawn for that family. |
| `n_guard_rejected_engine1` / `_engine2` | Rejected by the energy-plausibility guard, per engine. Counted and excluded, never dropped silently. |
| `n_usable` | Not rejected by the guard. |
| `n_excluded_not_labelable` | Usable but removed by the weak-element or structure-change exclusions. |
| `n_labelable_pathA` / `_pathB` / `_pathC_product` | The three scored populations. Path B is a strict subset of Path A. |
| `n_removed_by_disagreement` | Rows Path B removes from Path A because the two engines disagree beyond tolerance. |
| `disagreement_fraction_of_pathA` | The above as a fraction. |
| `n_missing_second_engine_result` | Rows with no usable second-engine result. These **pass the disagreement term untested**, because `abs(NaN) > tol` is false. That is the production behaviour and is reported rather than folded in. |
| `n_failed_jobs` | Jobs that never produced a usable result. Zero for all three families. |
| `base_rate_truly_stable_pathA` | Fraction of the Path-A population that is truly stable. |
| `prior_threshold_fitted_on_n_pathA` / `_pathB` | Row count the **existing production** threshold for that path was fitted on, for comparison. The two rule sets were fitted on different counts. |
