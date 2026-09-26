# OQMD development — post-hoc diagnostic of the stable-side result

> **POST-HOC, DEVELOPMENT TIER, licenses nothing.** Written *after* reading `reports/oqmd_development.md`.
> Changes no threshold and says nothing about the WBM held-out results.
> Reproduce: `python scripts/oqmd_posthoc_stable_calls.py reports/oqmd_development_posthoc.json`.

## Why this exists

On OQMD's development rows, the two live stable rules were far below target on Path A:

- **f-electron −20 meV:** precision 0.3893 (298 calls).
- **pnictide −20 meV:** precision 0.5189 (212 calls).

On WBM held-out data the same rules scored 0.9730 and 0.9564. The unstable sides held on OQMD (NPV 0.971–0.998).

One candidate explanation is a difference in **label definition**, not in the model. WBM's label is the distance to MP's hull, which never contains WBM's sibling candidates. OQMD's `stability` is the distance to OQMD's full hull, which includes OQMD's own hypothetical entries, other polymorphs of the same formula among them. The product only ever sees MP's hull, so it cannot know about a lower OQMD sibling.

## Test

Path-A stable calls were re-scored under a WBM-style label: OQMD formation energy minus OQMD's hull of **other compositions only** (same-formula entries excluded).

| family | stable calls | precision, OQMD label | precision, other-compositions label | CP95 (descriptive) | errors | errors with a lower same-formula OQMD entry | errors wrong even vs other compositions |
|---|---:|---:|---:|---:|---:|---:|---:|
| f-electron | 298 | 0.3893 | 0.4195 | 0.3715 | 182 | 29 | 169 |
| pnictide | 212 | 0.5189 | 0.5566 | 0.4978 | 102 | 13 | 93 |

## Reading

**The sibling effect is real but small.** It moves precision by about 3–4 points. Most wrong calls are above OQMD's hull even when same-formula siblings are ignored.

What remains cannot be split into *model* versus *convention* with this data. The rows where the two hulls agree within 25 meV give only 34 and 48 stable calls (precision 0.618 and 0.729). Two convention differences are not measured here:

- the candidate's **own** formation energy, which can differ between OQMD's fitted chemical potentials and MP2020 even when the hulls agree;
- OQMD's lanthanide treatment (f-in-core `Ln_3` PAW potentials appear in its settings).

**What this does and does not say.**

- It **does** say the live stable rules do not carry their WBM precision over to OQMD labels.
- It **does not** say which convention is right.
- It **does not** impugn the pre-registered WBM held-out confirmation, which tested the rule on the labels it was certified against.

Any use of OQMD as a check on stable-side claims would need the convention question resolved first. The cleanest route is still a targeted DFT campaign in MP settings on a sample of these very candidates.
