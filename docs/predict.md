# The prediction layer — the contract

`harness/predict.py` is the product: one candidate from a scientist, one decision back. Everything
else in this repository is a benchmark (dataset in, report out); this is the single call.

```python
from harness import predict

p = predict.predict("mp-aaacfzaj", "La:Dy")      # parent material + element swap
p = predict.predict_structure(my_structure)      # or a finished candidate
```

```bash
python -m harness predict --parent mp-aaacfzaj --substitute La:Dy [--json]
```

Nothing is fitted at call time. Every threshold, every bound and every confidence number comes from
`data/calibration_bundle.json`, frozen once from the WBM calibration set by `python -m harness
calibrate` and reproducing exactly the tables in `reports/validation_report.md` §6c and
`reports/final_test.md`. `tests/test_predict.py::test_bundle_matches_the_published_calibration_tables`
fails if that ever stops being true.

---

## 1. The contract

`predict()` returns a `Prediction` dataclass. `to_json()` serialises **exactly** these eight fields:

| field | type | what it is |
|:--|:--|:--|
| `structure` | CIF string, or `null` | the relaxed candidate. `null` only when no relaxation was usable. |
| `e_above_hull_mev` | float, or `null` | predicted energy above the hull, meV/atom, **mode (a)**: the engine's energy placed on the Materials Project GGA/GGA+U hull with MP2020 corrections. Signed — negative means below the MP hull. `null` when no hull could be built. |
| `label` | `"likely stable"` \| `"likely unstable"` \| `"needs DFT"` | the decision. |
| `confidence` | object, or `null` | the observed hit rate of a plain threshold-0 call for **this chemistry family and this predicted hull bin**, with its 95 % interval and the n it came from — read from the frozen calibration table, never recomputed. `null` when that cell does not exist, and then a warning says so. |
| `reasons` | list of strings | why it routed that way: the certified threshold it cleared, or every refusal reason that applied. |
| `properties` | object | `formula`, `n_atoms`, `volume_per_atom_A3`, `density_g_cm3`, and — when spglib can determine the symmetry — `spacegroup`, `crystal_system` and conventional-cell `lattice_constants`. `bulk_modulus` only when asked for (`--bulk-modulus`), because it costs nine more relaxations. Absent rather than guessed. |
| `provenance` | object | engine name and key, checkpoint sha256, device/dtype, settings tag, relaxation settings, harness commit, timestamp, wall time, which calibration bundle and which rule set, the parent and every start tried, the hull construction, the conformal interval, and the second engine's prediction. |
| `warnings` | list of strings | free text: anything the caller should know that is not a routing reason. |

`e_above_hull_mev` is reported **even when the label is `needs DFT`**, wherever it exists. A refusal
is a product outcome, not an error: the scientist still sees what was computed.

### What runs, in order

1. **Starts.** `compare.substitute` builds the candidate in the parent's cell; `compare.rescale_to_predicted_volume`
   builds a second start at a predicted volume. Both are relaxed and the lowest-energy *usable* one
   wins (`substitution.best_start` — the suite's own rule). `predict_structure` has one start.
2. **Relaxation.** `jobs.relax_job` at `config.DEFAULT_RELAX` (FrechetCellFilter + BFGS, fmax 0.01 eV/Å,
   |stress| ≤ 0.01 GPa, ≤ 500 steps), with `jobs.ladder_job` behind it, so a rejected relaxation goes
   through the same fallback ladder the calibration results did.
3. **Guard.** `compare.rejection_reason` — the reference-free half (convergence, minimum interatomic
   distance, absolute energy window). The half that needs a DFT energy cannot apply to a new material
   and does not run.
4. **Hull.** `hull.e_above_hull_mode_a`. Mode (a) is what the report recommends for new materials:
   relaxing the competitors too makes the error *larger* by +1.9 [+0.8, +3.2] meV/atom.
5. **Decision.** `routing.route` with the frozen conformal model, weak-element list and certified
   per-family thresholds.

### One engine or two

`reports/final_test.md` measured the **two-engine** system on the locked test set: MACE-MPA-0 medium
as the production engine, MACE-MP-0 medium as a disagreement check, tolerance 165 meV/atom
(95th percentile of |primary − second| on calibration). That is the default, and `rules:
with_second_engine` in the provenance says so.

`second_engine=None` (`--no-second-engine`) runs one engine and uses the rule set certified for *that*
configuration (`reports/validation_report.md` §6c: calibration precision 0.971, NPV 0.985). Both rule
sets were certified on the calibration set; neither is refitted. **The one-engine configuration was
never measured on the locked test set** — it is cheaper and less evidenced, and the provenance records
which one you got.

---

## 2. The refusal rules

The product returns `needs DFT` — no stability label — when any of these holds. Every one that
applies is listed in `reasons`.

| rule | why |
|:--|:--|
| predicted hull distance **> 0.3 eV/atom** | the report's verdict above 0.3 eV/atom is *not trustworthy* for every engine (energy MAE upper bound 97 meV/atom), and 15 % of those relaxations leave their starting structure. A number with a bar that wide is worse than a refusal. |
| **the relaxation left the starting structure** | those results carry 4.6× the energy error of the rest (102 vs 22 meV/atom MAE). The signal is StructureMatcher at default tolerances against the candidate's own start — the signal a real candidate has, since no DFT-relaxed cell exists for it. |
| **known-weak chemistry** (Be, Pm, Pu, Tc) | elements whose calibration error is not shown to be acceptable (per-element MAE lower bound > 60 meV/atom, or fewer than 20 calibration compounds). |
| **between the certified thresholds**, or a family with no certified threshold on either side | the per-family thresholds are certified for ≥ 90 % precision / ≥ 95 % NPV (Clopper–Pearson, Bonferroni over the threshold grid). Between them, nothing is certified. |
| **the two engines disagree** by more than 165 meV/atom | the disagreement tolerance certified on calibration. |
| **no usable relaxation** | nothing converged, or everything was rejected by the physical-sanity guard. |
| **no Materials Project reference hull** | a convex hull needs an entry at every elemental corner. Elemental **Yb** has no GGA/GGA+U thermo document in the MP API this harness reads, so no Yb compound can be placed at all (3.1 % of the calibration set, 3.4 % of the locked test set). The product refuses rather than placing a candidate on a hull with a missing corner. |

### What the > 0.3 eV/atom refusal costs — and a reservation

Applying that rule to the locked test set, with nothing else changed:

| | `final_test.md` system | the product |
|:--|--:|--:|
| likely stable | 224 | 224 |
| likely unstable | 2,146 | 1,874 |
| sent to DFT | 1,629 | 1,901 |
| precision of 'likely stable' | 0.960 [0.933, 0.982] | 0.960 [0.933, 0.982] |
| NPV of 'likely unstable' | 0.988 [0.984, 0.993] | 0.987 [0.981, 0.991] |
| share sent to DFT | 0.407 | **0.475** |

**The reservation, stated plainly.** The 272 candidates this converts from 'likely unstable' to
'needs DFT' contained exactly **one** truly stable material. What the report calls untrustworthy above
0.3 eV/atom is the *energy*, not the *unstable call* — a candidate predicted 500 meV above the hull is
essentially never stable, whatever the error bar. So this rule buys almost no protection and spends
6.8 points of DFT budget. It is implemented as asked, and it is one constant
(`predict.MAX_TRUSTWORTHY_HULL_EV`); setting it to `None` restores the `final_test.md` behaviour
exactly. The rule is applied **when a candidate is routed, never when the thresholds are certified**,
so the published thresholds are untouched by it.

---

## 3. The hull the product uses, and how far it is from WBM's

The validation numbers come from Matbench Discovery's construction,
`each_pred = each_true + (E_model − E_DFT)`, which needs a DFT energy the product does not have. The
product instead rebuilds the hull: the engine's relaxed structure and energy become one MP2020-corrected
entry (`hull.product_entry`), placed against the Materials Project GGA/GGA+U entries of its chemical
system. The calculation parameters are derived from the chemistry itself using MP2020's own U settings,
and `oxide_type` / `oxidation_states` are left unset so the correction scheme reads them off this
structure rather than inheriting another material's.

Measured on 140 WBM calibration structures, 20 per chemistry family:

* 137 placed, 3 refused (all Yb — see above);
* **129 of 137 agree with the recorded `each_pred` to within 1 meV/atom**; median |difference| 0.0003 meV/atom;
* 8 differ by 5–211 meV/atom.

Those 8 are **not** an entry-construction difference: the same offset appears when the *DFT* energy is
placed on our hull, so it is the reference hull itself. Matbench Discovery's hull is a 2023 Materials
Project snapshot; ours is the current MP API. The product's number is on today's MP hull. This matters
when comparing product-scored results with WBM-scored ones, and `reports/unseen_test.md` carries the
same caveat.

---

## 4. Worked example

`LaCuPb` (mp-aaacfzaj, hexagonal ZrNiAl-type) with La replaced by Dy. Materials Project has the target
`DyCuPb` at 55 meV/atom above the hull; the product is not told that.

```
$ python -m harness predict --parent mp-aaacfzaj --substitute La:Dy

candidate       DyCuPb  (6 atoms, SG 194, hexagonal)
decision        LIKELY UNSTABLE
hull distance   +50 meV/atom (predicted, mode (a))
second engine   +29 meV/atom (MACE-MP-0 medium)
confidence      a plain 'unstable' call for f-electron in the 0.025–0.1 predicted bin was right 99% of the time [98%, 99%] on 601 calibration structures
why
  - prediction > certified unstable threshold +10 meV/atom (f-electron)
lattice         a=4.6431 b=4.6431 c=7.2456 Å, α=90.00 β=90.00 γ=120.00°
volume          22.546 Å³/atom (10.637 g/cm³)
engine          MACE-MPA-0 medium · cpu/float32 · settings c2480e74 · harness 1ad6ba3
```

The same call with `--json` (structure CIF elided, everything else verbatim):

```json
{
 "structure": "# generated using pymatgen\ndata_DyCuPb\n... 6 sites ...",
 "e_above_hull_mev": 50.16230705240865,
 "label": "likely unstable",
 "confidence": {
  "family": "f-electron",
  "predicted_bin": "0.025–0.1",
  "n": 601,
  "call": "unstable",
  "hit_rate": 0.9850249584026622,
  "ci95": [0.9750415973377704, 0.9933444259567388],
  "source": "observed hit rate of the plain threshold-0 stable/unstable call on the WBM calibration set, per chemistry family x predicted hull bin; reports/validation_report.md §6c"
 },
 "reasons": ["prediction > certified unstable threshold +10 meV/atom (f-electron)"],
 "properties": {
  "formula": "DyCuPb",
  "n_atoms": 6,
  "volume_per_atom_A3": 22.545599887349127,
  "density_g_cm3": 10.636545682941277,
  "spacegroup": 194,
  "crystal_system": "hexagonal",
  "lattice_constants": {
   "a": 4.643071277140814, "b": 4.643071277140814, "c": 7.245551171854542,
   "alpha": 90.0, "beta": 90.0, "gamma": 120.00000000000001,
   "units": "Å and degrees, conventional standard cell (symprec 0.10)"
  }
 },
 "provenance": {
  "engine": "MACE-MPA-0 medium",
  "engine_key": "mace-mpa-0-medium",
  "checkpoint": "mace-mpa-0-medium.model",
  "checkpoint_sha256": "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638",
  "device": "cpu", "dtype": "float32", "settings_tag": "c2480e74",
  "relax_settings": {"fmax": 0.01, "max_stress_gpa": 0.01, "max_steps": 500,
                     "optimizer": "BFGS", "cell_filter": "FrechetCellFilter", "timeout_s": 900.0},
  "harness_commit": "1ad6ba3",
  "timestamp": "2026-09-12T20:33:59+00:00",
  "wall_time_s": 4.228881,
  "calibration_bundle": {
   "created_at": "2026-09-12T20:21:45+00:00",
   "harness_commit": "1ad6ba3",
   "calibration_ids_sha256": "29d974a4d56d54a398226c811239075f64217433862b4a5eb0b27bd81dd7efe3",
   "rules": "with_second_engine"
  },
  "parent": "mp-aaacfzaj LaCuPb (PBE structure from Materials Project), substitution {'La': 'Dy'}",
  "starts": {
   "sub":          {"method": "parent volume (unscaled)", "volume_factor": 1.0, "outcome": "usable"},
   "sub_rescaled": {"method": "RLS atomic radii", "volume_factor": 0.8869062426970018,
                    "failed_methods": ["RLS ionic radii: ValueError"], "outcome": "usable"}
  },
  "start_used": "sub",
  "hull": "mode (a): engine energy on the Materials Project GGA/GGA+U hull, MP2020 corrections",
  "second_engine": {"engine": "MACE-MP-0 medium", "engine_key": "mace-mp-0-medium",
                    "checkpoint_sha256": "01bfe22100139f424713cf921144e5509cbe353d67aa9fa1be9c6e1e0ed35845",
                    "device": "cpu", "dtype": "float64", "settings_tag": "207ccc81"},
  "predicted_hull_second_engine_mev": 29.48154411270032,
  "hull_details": {"signed": 0.05016230705240865, "e_above_hull": 0.05016230705240865,
                   "chemsys": "Cu-Dy-Pb", "n_mp_entries": 34, "mp2020_corrections": {},
                   "construction": "mode (a): engine energy on the MP GGA/GGA+U hull, MP2020 corrections"},
  "conformal_interval": {"lo": 0.03306075685099241, "hi": 0.07818961672953284, "family": "f-electron",
                         "pred_bin": "0.025–0.1", "group_level": "family × predicted bin", "n_group": 601,
                         "coverage": 0.9, "coverage_meaning": "each bound alone"},
  "relaxation": {"energy_per_atom_ev": -4.135..., "converged": true, "n_steps": 9,
                 "fmax_final": 0.00021294690668582916, "max_stress_gpa": 0.00027196097653359175,
                 "wall_time_s": 0.41844883299199864, "rung": "default", "structure_changed": false}
 },
 "warnings": []
}
```

Read it as: *the engine puts DyCuPb 50 meV above the hull, above the +10 meV/atom threshold certified
for f-electron chemistries, so this is an unstable call; on the calibration set, an unstable call for
an f-electron compound in this predicted bin was right 99 % of the time (98–99 %, n = 601). The second
engine agrees within 21 meV/atom, well inside the 165 meV/atom tolerance.* The true value is 55 meV/atom.

---

## 5. Using it from your own code

* **Engine selection is per process.** `HARNESS_MODEL` chooses the model at import time, because
  `mace_mp()` sets torch's global default dtype and the two engines run at different dtypes. `predict()`
  runs the production engine in this process when `HARNESS_MODEL` already names it, and spawns a worker
  otherwise. Every relaxation's recorded `model_key` is checked against the engine that was asked for,
  so a wrong model is an error and never a silent wrong answer. For batch use, set
  `HARNESS_MODEL=mace-mpa-0-medium` and call `predict()` inside your workers.
* **Scripts need the multiprocessing main guard.** The second engine runs in a spawned worker, which
  re-imports your `__main__`; put your calls under `if __name__ == "__main__":`.
* **The MP cache.** Hull construction reads MP entries for the candidate's chemical system
  (`cache/mp/entries_chemsys/`, permanent). A chemistry that is not yet cached needs `MP_API_KEY`.
* **Bulk modulus** (`with_bulk_modulus=True`) fits a third-order Birch–Murnaghan EOS over nine
  constant-volume relaxations, with the suite's own fit. Its verdict travels with the number:
  11.9 % MAE against MP's K_VRH (upper bound 16.8 %, n=82) — *use with caution* — and a relaxed-shape
  EOS is a Reuss-like average while MP's K_VRH is a Voigt–Reuss–Hill one.
* **The raw engine energy** is in `provenance.relaxation.energy_per_atom_ev`, not in `properties`. It is
  the engine's total energy per atom, meaningful only against MP's *uncorrected* GGA/PBE energies — a
  validation quantity, not a property of the material — and that is where `reports/unseen_test.md`
  reads it from.
* **`exclude_mp_ids` is for evaluation only.** A real candidate is not in Materials Project, so nothing
  is removed from its reference hull and the parameter stays empty. It exists so a material MP already
  has can be scored *as if* it were new — its own MP entry taken out of the hull, the same removal
  `stability.evaluate_target` makes for mode (a). `reports/unseen_test.md` is the only caller.
* `config/costs.json` still holds 1:1 placeholder costs. Nothing in this module is optimised against
  them; the decision thresholds are certified precision/NPV targets, not cost minima.
