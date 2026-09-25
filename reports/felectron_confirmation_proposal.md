# Proposal: record the f-electron held-out confirmation in the production bundle

**Status: PROPOSED, NOT DONE.** `scripts/record_felectron_confirmation.py` is written and tested on a
temporary copy of the bundle. It has **not** been run. `data/calibration_bundle.json` is unchanged
(sha256 `419c11514d6a54854584258375eadab6b2be0c449e955125799fc51df2310288`). Running it needs an explicit decision, and the script refuses
without `--i-have-an-explicit-decision`.

## The evidence (evidence commit `34c40d3`, `reports/felectron_test.md`)

The pre-registered f-electron held-out evaluation was opened once on 2026-09-24T19:37:44+00:00, authorised by
Isac Smith, 2026-09-24, and scored once on 2026-09-24T21:11:35+00:00. It used the fixed live thresholds
−20 / +10 meV on 4,500 never-used WBM f-electron structures. 3,942 were labelable on
Path A and 3,847 on Path B. No pre-registered inconclusive trigger fired.

| id | path | side | calls | errors | point | CP-lower @0.9875 | target | verdict |
|---|---|---|---:|---:|---:|---:|---:|---|
| EA1 | A | stable | 481 | 13 | 0.9730 | **0.9513** | 0.9 | PASS |
| EA2 | A | unstable | 3,020 | 33 | 0.9891 | **0.9840** | 0.95 | PASS |
| EB1 | B | stable | 475 | 13 | 0.9726 | **0.9507** | 0.9 | PASS |
| EB2 | B | unstable | 2,933 | 33 | 0.9887 | **0.9835** | 0.95 | PASS |

## What the pre-registration says to do

The applicable branch is `outcome_rule.all_four_pass`, quoted verbatim:

> the live f-electron rule is CONFIRMED out of sample on both paths. Note what this does and does not license: it confirms a rule ALREADY IN PRODUCTION, so the correct action is to record the confirmation and the provenance in the bundle. It is NOT a licence to change any threshold, and no threshold would change.

## What the script changes, exactly

* In **both** rule sets, the f-electron entry gains `status: PREREGISTERED HELD-OUT CONFIRMED` and a
  provenance pointer. Its thresholds (−0.02 / +0.01) and its `n` are **unchanged**.
* A new top-level `confirmations[]` list gets one record with the full provenance: pre-registration and
  sample hashes, opening and scoring times, the four counts and bounds, the multiplicity and the power
  limit. This is kept separate from `promotions[]`, because nothing was promoted: the rule was already live.
* `modified_at` is updated. `created_at`, every other family, the targets, exclusions, the tolerance
  and the reliability table are verified byte-identical, and any other difference aborts.
* The prior bundle is copied to `data/calibration_bundle_pre_felectron_confirmation.json`, so the
  change is reversible by swapping the file back.

## Product impact

None on behaviour: every prediction, label and DFT share stays identical, because no threshold moves.
What changes is what the bundle can *claim*. The f-electron stable and unstable rules would go from
development-certified to pre-registered-held-out-confirmed, the same evidence tier as pnictide. The
product's binding constraint is unchanged: f-electron and pnictide remain the only families that can
return *likely stable*.

## Limits that stay attached

* The study was powered against the development **point** estimates. A pass means the rule behaves as
  development suggested; it does **not** establish that true precision is far above 0.90.
* The held-out bounds (EA1 0.9513, EB1 0.9507) exceed the development bounds
  (0.9171 / 0.9231) because development paid a 61-point grid × 6 family-side correction and this test
  paid only the 4-hypothesis Bonferroni. That is not the held-out data being "better".
* WBM only, MP-convention labels only. The OQMD stage-2 measurement (`reports/oqmd_hull_disagreement.md`)
  is a reminder that a different hull convention disagrees on a material's side for about a fifth of
  materials at −20 meV.

## To run it, on an explicit decision

```bash
HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/record_felectron_confirmation.py --i-have-an-explicit-decision
```

Then commit the bundle as its own **production** commit, separate from any evidence commit, and update
the HANDOFF invariant that pins the bundle's sha256.
