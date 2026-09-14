# `results/results.parquet` — data dictionary

The full results table: **197,783 rows × 19 columns**, one row per *test* per *structure* per
*settings tag*. It is the raw material behind every number in [`reports/`](../reports/) — publishing
it means a reader can recompute any table in [`reports/validation_report.md`](../reports/validation_report.md)
rather than take it on trust.

**Format.** Apache Parquet, zstd level 19, single row group, 6.9 MB. Read it with anything:

```python
import pandas as pd
df = pd.read_parquet("results/results.parquet")
```

**Licence.** CC BY 4.0, © 2026 Isac Smith — the same terms as [`data/`](../data/) and
[`reports/`](../reports/). Reference values in this table are derived from Materials Project and WBM
data, both CC BY 4.0; the attribution in the root [`NOTICE`](../NOTICE) travels with the file. See
[`data/README.md`](../data/README.md) for the full provenance picture.

**What is *not* here.** The rest of `results/` — `results.sqlite` (the job store, ~600 MB), the
per-engine queue databases and snapshots — is gitignored and not published. This table is the export
of the `results` table from that store.

---

## The shape of the table

It is **long**, not wide. One structure that was measured on six tests produces six rows. The report
generators pivot it on `test` before building any table, and you will need to do the same.

The identity of a row is `(job_key, test)`. The identity of a *structure under one engine
configuration* is `job_key`.

---

## Columns

### Identity and grouping

| column | type | what it is |
|:--|:--|:--|
| `suite` | string | which test suite produced the row. 8 values: `substitution_auto` (135,122), `ood` (58,004), `substitution` (2,711), `polymorph` (1,144), `bulk` (332), `experimental` (264), `stability` (200), `smoke` (6) |
| `job_key` | string | unique id of the job that produced the row, **including the settings tag after `@`**. Format varies by suite — see "job_key formats" below |
| `structure` | string | human-readable label, e.g. `Si->Ge (mp-149 -> mp-32)`. **A label, not a serialised structure** — no geometry is embedded in this table |
| `formula` | string | reduced formula of the structure scored, e.g. `Ge` |
| `family` | string | prototype or grouping label, e.g. `elemental-diamond`, `rocksalt`, `AB2_Pnma`, or `wbm-unique-prototype` for the WBM rows. 2,538 distinct |
| `settings_tag` | string | 8-hex-character hash of the engine settings blob, or `pre-tag` for rows written before tagging existed. 5 distinct: `207ccc81` (113,455), `c2480e74` (70,480), `d738c212` (12,487), `6710d7b3` (758), `pre-tag` (603). **Always filter on this** — the table mixes engines |

### The measurement

| column | type | units | what it is |
|:--|:--|:--|:--|
| `test` | string | — | which quantity was measured. 51 distinct; see "test names" below |
| `units` | string | — | units of `simulated_value` and `reference_value`. 6 values: `eV/atom` (85,506), `Å` (53,035), `Å^3/atom` (19,670), `bool` (19,670), `SG number` (19,570), `GPa` (332) |
| `simulated_value` | double | per `units` | what the engine produced. For `bool` tests, 1.0 / 0.0 |
| `reference_value` | double | per `units` | what it is being compared against |
| `error_abs` | double | per `units` | `simulated_value − reference_value`, absolute difference |
| `error_pct` | double | % | the same as a percentage of `reference_value`. Null where a percentage is meaningless |
| `runtime_s` | double | seconds | wall time for the job that produced the row |
| `created_at` | string | ISO-8601 UTC | when the row was written |

### Provenance — where each side of the comparison came from

These four columns are why the table is worth publishing: every single number says what it is
being compared against and where that came from.

| column | type | what it is |
|:--|:--|:--|
| `simulated_provenance` | string | always `simulated` — the value came from this harness running the engine. Constant by construction; kept so the pair of provenance columns reads symmetrically |
| `reference_provenance` | string | the *kind* of reference. 3 values: `mp_computed` (139,645, a Materials Project DFT value), `wbm_computed` (58,004, a WBM/Matbench Discovery DFT value), `experimental` (134, a measured value from the literature) |
| `reference_source` | string | the *exact* reference, at full precision. For MP: `mp-<id> PBE (GGA_GGA+U thermo, task <task-id>)` — material id, functional, thermo type **and the specific MP task**. For WBM: the WBM id. For experimental: the paper and table. 41,025 distinct |
| `settings` | string (JSON) | the complete engine configuration: `model_name`, `model_file`, `model_sha256`, `mace_torch_version`, `torch_version`, `ase_version`, `device`, `dtype`, `relax_cell`, and a nested `relax` object (`fmax`, `max_steps`, `optimizer`, `cell_filter`, `timeout_s`) |

`reference_source` naming the MP *task id*, not just the material id, is what makes the
GGA/GGA+U-mixing check in [`reports/phase0/phase0_report.md`](../reports/phase0/phase0_report.md)
possible to redo from this file alone.

### Flags — per-row conditions and guard decisions

| column | type | what it is |
|:--|:--|:--|
| `flags` | string (JSON) | per-row conditions. Keys vary by suite |

Keys you will meet:

| key | meaning |
|:--|:--|
| `converged` | did the relaxation converge |
| `n_steps` | relaxation steps taken |
| `max_stress_gpa` | residual stress after relaxation |
| `rejection` | **non-null means the guard rejected this result.** Present on 5,988 of the first 40,000 rows sampled. Rows with a rejection are excluded from every average in the reports and counted separately as "excluded (guard)" |
| `transition_metal`, `tm_elements` | does the structure contain transition metals, and which |
| `f_electron`, `f_elements` | the same for f-electron elements |
| `magnetic`, `pbe_abs_magmom_per_site`, `spin_caveat` | magnetism of the MP reference, and whether that makes the comparison unsafe |
| `start_method`, `start_volume_factor` | which of the two starts produced this result (substitution suite) |
| `structure_outcome` | `same structure` vs `relaxed into a different structure` |
| `keeps_prototype_sg`, `sim_spacegroup`, `status`, `note` | polymorph-suite specifics |

**The `rejection` key is the one to respect.** Any recomputation that ignores it will disagree with
the reports, because the reports exclude guarded rows from averages by design.

---

## `job_key` formats, by suite

| suite | example |
|:--|:--|
| `substitution_auto` | `YSb->YN [mp-aaaaaaih>mp-aaaaaddi]:mp-aaaaaaih->mp-aaaaaddi:ctrl@207ccc81` |
| `ood` | `wbm-3-38282@207ccc81` |
| `polymorph` | `Sr2EuBiO6:mp-aaadijuk@c2480e74` |
| `bulk` | `mp-aaaaacfs@207ccc81` |
| `experimental` | `BP:zb@207ccc81` |
| `stability` | `Si->Ge@207ccc81` |
| `substitution` | `MgAl2O4->ZnAl2O4:mp-aaaaafga->mp-aaaaaehw:sub` |
| `smoke` | `mp-149:Si->Ge:mp-aaaaaabg` |

The suffix after `@` is `settings_tag`. The two suites with no `@` predate tagging and carry
`settings_tag == "pre-tag"`.

## `test` names

Prefixed names are relaxation variants within the substitution suites: `ctrl:` is the MP target
relaxed directly (the control), `sub:` is the substituted parent relaxed, and `sub_rescaled:`,
`sub_rattled:`, `sub_rattled_rescaled:` are the alternative starts. Each variant reports
`:energy_per_atom`, `:vol_per_atom`, `:spacegroup`, `:structure_match`, `:a`, `:b`, `:c`.

The unprefixed and specially-prefixed names: `energy_per_atom`, `e_form_per_atom`, `e_above_hull`,
`static:energy_per_atom`, `polymorph:energy_per_atom`, `mode_a:e_above_hull`,
`mode_a:signed_hull_energy`, `mode_b:e_above_hull`, `mode_b:signed_hull_energy`, `a_vs_mp`,
`a_vs_mp_pbe`, `c_vs_mp_pbe`, `a_vs_experiment`, `c_vs_experiment`, `B0_eos_vs_K_VRH`,
`B0_eos_vs_K_Reuss`.

---

## Joining this table back to the report tables

Every table in [`reports/validation_report.md`](../reports/validation_report.md) is a group-by over
this file. The recipe is always the same four steps.

**1. Pick one engine.** The table mixes engine configurations; the reports do not.

```python
df = df[df.settings_tag == "207ccc81"]          # or read settings to pick by model_name
```

**2. Drop guard-rejected rows**, the way the reports do — and count them separately if you want to
reproduce the "excluded (guard)" column.

```python
import json

def rejected(f):
    # flags is null on some rows, and pandas gives you NaN (a float), which is truthy
    return isinstance(f, str) and bool(json.loads(f).get("rejection"))

rej = df["flags"].map(rejected)
excluded, df = df[rej], df[~rej]
```

Two things bite here, and both bite silently:

> **Use `df["flags"]`, not `df.flags`.** `flags` is also the name of a pandas `DataFrame` attribute,
> so attribute access returns a pandas `Flags` object instead of this column, and fails with
> `'Flags' object has no attribute 'map'`. The same caution applies to `df["test"]`.
>
> **Guard on `isinstance(f, str)`, not on truthiness.** Rows with no flags come back as `NaN`, and
> `NaN` is truthy, so `if f else False` sends a float into `json.loads` and raises
> `TypeError: the JSON object must be str, bytes or bytearray, not float`.

**3. Pivot from long to wide on `test`**, keyed by `job_key`:

```python
wide = df.pivot_table(index="job_key", columns="test",
                      values=["simulated_value", "reference_value", "error_abs", "error_pct"],
                      aggfunc="first")
```

**4. Add the hull bin**, which is *not* a column here — the reports derive it from the target's
hull distance. Join to [`data/auto_pairs.json`](../data/auto_pairs.json) on the pair id (the part of
`job_key` before the first `:`) and bin `target_e_above_hull` on the edges in
[`harness/compare.py`](../harness/compare.py):

| edges | MP bins (§2) | WBM bins (§3, §4) |
|:--|:--|:--|
| 0.025, 0.1, 0.3 eV/atom | `≤0.025`, `0.025–0.1`, `0.1–0.3`, `>0.3` | `<0`, `0–0.025`, `0.025–0.1`, `0.1–0.3`, `>0.3` |

The WBM bins add a `<0` bin for materials below the MP hull; the MP bins do not. That is
`compare.hull_bin(e, below_zero_bin=True)` versus `below_zero_bin=False`.

> **The `substitution_auto` rows cover two different pair sets, and you must choose one.** The table
> holds **3,934 distinct pair ids**: 1,952 from the current [`data/auto_pairs.json`](../data/auto_pairs.json)
> and 1,982 more that exist only in the superseded round-1 set
> [`data/auto_pairs_v1.json`](../data/auto_pairs_v1.json). None is orphaned — every pair id resolves
> to one file or the other — but a join against `auto_pairs.json` alone silently drops about half the
> `substitution_auto` rows rather than erroring.
>
> **The reports are computed on `auto_pairs.json` only.** To reproduce them, keep only the pair ids
> in that file. To study the v1 rows, join to `auto_pairs_v1.json` instead — but do not pool the two,
> because the sets were generated under different quotas (`data/auto_pairs_meta.json` versus
> `data/auto_pairs_v1_meta.json`).
>
> Each pair contributes 4 `job_key` rows, one per relaxation variant.

### Which report section uses which rows

| report section | rows |
|:--|:--|
| §2 Known materials, by target hull distance | `suite == "substitution_auto"`, tests `ctrl:*` and `sub*:*` |
| §3 New materials, by hull distance | `suite == "ood"`, test `e_above_hull` |
| §4 Stability decisions on new materials | `suite == "ood"`, `mode_a:*` |
| §6b New materials, mode (b) | `suite == "ood"`, `mode_b:*` |
| §9 Lattice constants against experiment | `suite == "experimental"`, tests `a_vs_experiment`, `c_vs_experiment`, `reference_provenance == "experimental"` |
| §10 Bulk modulus | `suite == "bulk"`, tests `B0_eos_vs_K_VRH`, `B0_eos_vs_K_Reuss`, units `GPa` |
| §11 Runtime and job outcomes | all rows, `runtime_s` grouped by `suite` |
| Polymorph ranking ([`reports/polymorph.md`](../reports/polymorph.md)) | `suite == "polymorph"`, test `polymorph:energy_per_atom` |

The bootstrap confidence intervals in the reports are computed over these same rows; the reports
state the bootstrap count they use.

---

## Regenerating this file

`python -m harness.report` rewrites it from `results/results.sqlite`, at
[`harness/report.py:905`](../harness/report.py). Regenerating needs the SQLite store, which is not
published — so a reader can *verify* this table but cannot *rebuild* it without rerunning the
harness.

**Future versions will be attached as GitHub Release assets rather than recommitted**, so that
repository history does not grow by ~7 MB on every run. This copy is the one the published reports
were computed from.
