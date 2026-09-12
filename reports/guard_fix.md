# Energy-plausibility guard: what changed and what it did to the numbers

One converged relaxation with a physically impossible energy was being averaged into the reported
statistics. This records the fix, every call site it touched, and the before/after numbers.

Nothing was loosened to produce these numbers: the settings tag is unchanged (`207ccc81` for the
baseline, `c2480e74` for MACE-MPA-0), no tolerance moved, no hard case was dropped, and the guard only
ever moves a result from *scored* to *counted-and-excluded*.

## 1. The bug

`substitution_auto`, `AlN->AlSb [mp-aaaaaazl>mp-aaacfybs]`, kind `sub`:

| quantity | value |
|:--|:--|
| energy | **−1131.01 eV/atom** (MP reference −4.09) |
| converged | True |
| max \|stress\| | 0.0096 GPa (limit 0.01) |
| final fmax | 0.0018 eV/Å (limit 0.01) |
| steps | 68 |
| min d / r_cov | **0.514** (unphysical cut 0.50) |
| structure_match | True ("same structure") |
| volume | −77 % vs the PBE cell |

The relaxation fell into a spurious short-range minimum of the model's potential-energy surface that
is just wide enough to keep the nearest-neighbour ratio above the collapse cut, and then converged
cleanly there. Neither existing guard — convergence, or minimum interatomic distance — can see it.
A single row then dominated every mean it entered.

Two more results in the same class were found by sweeping the whole database: `Ba2Pb->PbF2 … sub_rescaled`
at −25.60 eV/atom and the WBM structure `wbm-4-21859` (Pu2MnZn2) at −23.77 eV/atom. Both had already
been through the full fallback ladder, and both were converged.

## 2. The rule

`harness/compare.py` now carries the whole rejection rule, and every suite calls it
(`compare.rejection_reason`). Two energy checks were added, applied independently of convergence and
of the min-distance ratio:

* **Absolute window:** reject an energy outside **[−20, +5] eV/atom**.
* **Reference deviation:** reject a result whose energy differs from its DFT reference by more than
  **5 eV/atom**, where a reference exists.

Bounds picked from the data (51,110 scored energy-per-atom rows, every suite, both engines):

| observation | value |
|:--|--:|
| DFT reference energies, range | −13.07 … −0.07 eV/atom |
| model energies that are not numerical blow-ups, range | −13.22 … −0.04 eV/atom |
| most negative rows outside [−15, 0] | −25.6, −23.8, then nothing until −13.22 |
| \|E_model − E_DFT\|, p99.9 | 2.6 eV/atom |
| largest **legitimate** \|E_model − E_DFT\| | 3.90 eV/atom |
| next values up | 15.8, 20.7 eV/atom |

Both cuts therefore sit inside wide empty bands (>6 eV/atom below the deepest real energy; a 12 eV
gap around the 5 eV/atom deviation cut) and cannot remove a physically meaningful result. The largest
legitimate deviations are MP targets 3–4 eV/atom above the hull that the model relaxes into a real,
much lower minimum; those stay in, and the report separates them as *relaxed into a different
structure*.

The absolute window needs no reference and is a check the product could also apply. The
reference-deviation check needs the DFT energy and is therefore a validation-time guard only.

## 3. Call sites unified

One rule, one function. Previously `rejection_reason` lived in `harness/suites/stability.py` and three
paths did not use it.

| call site | before | after |
|:--|:--|:--|
| `substitution` / `substitution_auto` (ctrl, sub, sub_rescaled, sub_rattled\*) | `stability.rejection_reason` | `compare.rejection_reason` |
| stability competitors (mode b hulls) | `stability.rejection_reason`, no DFT reference | same function, now passed the competitor's own MP energy |
| `mode_b` | `stability.rejection_reason` on competitors; **stored** reason on the target | same function, both re-evaluated |
| `ood` (WBM) | `stability.rejection_reason`; **stored** reason reused by `ood.table` | re-evaluated on read (`compare.recheck`) |
| **`bulk` EOS points** | **inline copy of the rule** (`converged and min_distance_ratio >= …`) | `compare.rejection_reason` |
| **`bulk` material list** | **`converged` only** | `compare.rejection_reason` |
| **`experimental` lattice checks** | **no guard at all** | `compare.rejection_reason`, recorded and reported |
| `engine.relax` convergence flag | folded in the min-distance cut only | also the absolute energy window, so the fallback ladder cannot stop on an impossible rung |

Phase 0 had already found one unguarded path; these are the rest. Stored `rejection` values are now
re-evaluated when a table is read (`compare.recheck`), so a stricter rule takes effect on existing
results without re-running a suite — the convergence and distance verdicts are reused, only the
arithmetic energy checks are re-applied.

## 4. Jobs re-run

Three results are newly rejected, all at the baseline tag. Only the affected jobs were re-run, via
the harness's own fallback ladder (`substitution.retry_jobs` + `run_pool`), not the suite:

| result | ladder available? | outcome |
|:--|:--|:--|
| `AlN->AlSb … sub` | yes | **re-run.** FIRE from the bad minimum, then a perturbed restart from the original: both worse (−2.96×10¹³ eV/atom, not converged). Stays rejected. The pair's other start, `sub_rescaled`, is usable at −4.077 eV/atom (reference −4.088, error −11 meV/atom) and is what `sub_best` now uses. |
| `Ba2Pb->PbF2 … sub_rescaled` | no — ladder already exhausted (rung `perturbed_restart`) | stays rejected and counted. The pair's `sub` start is usable at −4.853 eV/atom. |
| `wbm-4-21859` (Pu2MnZn2) | no — ladder already exhausted | stays rejected and counted. |

## 5. Numbers, before and after

### 5a. The corrupted cells (MACE-MP-0, report section 2, substituted parent, best of two starts)

| cell | before MAE | after MAE | median (unchanged) |
|:--|--:|--:|--:|
| ≤0.025, same structure | **2322.0** [11.2, 6941.9] | **12.7** [11.0, 15.1] | 7.3 |
| ≤0.025, compound | **3233.2** [12.1, 9674.2] | **13.5** [11.7, 15.8] | 7.7 |
| ≤0.025, plausible swap | **2517.4** [11.6, 7527.3] | **13.1** [11.2, 15.8] | 7.4 |

The verdict on the first row moves from *not trustworthy* to *trustworthy*. That is the verdict the
median said all along — which is why the median is now printed next to every MAE.

### 5b. New materials (MACE-MP-0, section 3), the cell holding `wbm-4-21859`

| cell | before | after |
|:--|:--|:--|
| 0.1–0.3, relaxed into a different structure, n | 157 | 156 |
| … energy MAE | 194.9 [86.1, 401.3] | **94.6** [83.0, 106.9] |
| … mean signed | −146.1 [−354.3, −32.5] | **−45.5** [−62.4, −27.1] |

Whole-set effects: WBM calibration goes from 3,994 usable / 6 rejected to 3,993 / 7;
`wbm_energy_mae_0.1–0.3` 77.6 → 65.7 meV/atom (upper bound 103.5 → 69.2); the plain-threshold
precision, recall, F1 and DAF move by ≤ 0.004. `Pu2MnZn2 (wbm-4-21859)` leaves the section-8
worst-case table, where it stood at −15,836 meV/atom.

Routing on the baseline: n 3,994 → 3,993, 'likely unstable' 1,486 → 1,455, 'send to DFT' 2,508 →
2,538, NPV 0.978 → 0.980.

### 5c. MACE-MPA-0

No result at the MACE-MPA-0 tag is newly rejected — its largest deviation from a DFT reference is
3.90 eV/atom, inside the guard. Its numbers are unchanged by the guard; what changed in its report is
the new median / trimmed-mean / exclusion-count columns, and sections 9 and 10, which it did not have.

## 6. Reporting changes that came with it

* Every stratified table prints the MAE next to its **median \|error\|** and its **10 % trimmed mean**,
  plus the count of results the guard excluded for that bin. `stratified_table` now *raises* if a
  caller asks for a verdict without supplying the exclusion count — no verdict may come from an
  unguarded mean.
* Verdicts still come from the MAE's pessimistic bound. The trimmed mean is a companion, never a
  substitute: trimming is exactly the operation that would flatter a heavy-tailed error.
* `scorecard.json` can no longer contain `NaN`. Undefined metrics are dropped and listed under
  `undefined_metrics`; the degenerate routing case is reported in words (see
  `reports/mace-mp-0-medium/validation_report.md` §6c).
