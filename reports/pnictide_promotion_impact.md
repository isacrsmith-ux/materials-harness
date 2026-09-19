# Production impact of the pnictide promotion

Generated 2026-09-19T23:18:28+00:00.

> **This is an OPERATIONAL comparison on DEVELOPMENT data.** It routes the round-4 pnictide development draw under the pre-promotion and promoted bundles to show what the change does to routing. It is **not** a held-out result and **not** a second confirmation. The held-out confirmation happened exactly once, in [`pnictide_test.md`](pnictide_test.md); that sample is not reopened, rescored or read here, and this script asserts no held-out id reaches it.

## Pnictide routing, before and after

| rule set | bundle | n | stable t | unstable t | stable calls | unstable calls | recall | **to DFT** |
|---|---|---:|---|---|---:|---:|---:|---:|
| `without_second_engine` | before | 3,637 | none | +50 meV | 0 | 2,502 | 0.000 | **0.312** |
| `without_second_engine` | after | 3,637 | -20 meV | +0 meV | 306 | 3,154 | 0.583 | **0.049** |
| `with_second_engine` | before | 3,501 | none | none | 0 | 0 | 0.000 | **1.000** |
| `with_second_engine` | after | 3,501 | -20 meV | +0 meV | 306 | 3,018 | 0.583 | **0.051** |

**The 100%-to-DFT fall-through is gone.** On the second-engine path pnictide went from a DFT routing fraction of 1.0000 - every candidate - to 0.0506, and from 0 to 306 'likely stable' calls on 3,501 development rows.

## Every other family, both rule sets — unchanged by construction

| family | rule set | bundle | stable t | unstable t | to DFT |
|---|---|---|---|---|---:|
| f-electron | `without_second_engine` | before | -20 meV | +10 meV | 0.114 |
| f-electron | `without_second_engine` | after | -20 meV | +10 meV | 0.114 |
| f-electron | `with_second_engine` | before | -20 meV | +10 meV | 0.115 |
| f-electron | `with_second_engine` | after | -20 meV | +10 meV | 0.115 |
| intermetallic | `without_second_engine` | before | none | +0 meV | 0.100 |
| intermetallic | `without_second_engine` | after | none | +0 meV | 0.100 |
| intermetallic | `with_second_engine` | before | none | +0 meV | 0.102 |
| intermetallic | `with_second_engine` | after | none | +0 meV | 0.102 |

Identical before and after, which is the point: the promotion touched two threshold entries and nothing else.

## What this does not show

These are development rows the thresholds were selected on, so the precision and NPV they would produce here are in-sample and optimistic. They are deliberately omitted from the tables above: routing volumes are the operational question, and the quality question was already answered, once, on held-out data.

