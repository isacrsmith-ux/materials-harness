# The unseen-real-materials test — MACE-MPA-0 medium

Opened once (2026-09-12T23:06:20+00:00). 325 real Materials Project materials that cannot be in the engine's MPtrj training data, each reached the way a user reaches a candidate — a known parent prototype plus one element substitution — and scored **end to end through `harness.predict`**, never through a suite. The pipeline was never given the target's DFT-relaxed cell or its DFT energy. Frozen id list `data/unseen_test.json`, sha256 `3379392d2bde2e13…`. No threshold was refitted: every rule comes from the calibration bundle already frozen for the product.

## 1. Why this test exists

Every stability number in this repository comes from WBM — random elemental substitution into MP prototypes. That is not what a user brings us, and our own 'implausible swap' stratum sometimes scores better than the plausible one, which says the WBM distribution is not measuring what we think it measures. Here every target is a material that really exists in Materials Project, so every substitution is one that DFT actually realised.

## 2. What counts as unseen

MACE-MPA-0 trained on MPtrj + sAlex. MPtrj is built from the Materials Project 2022.9 release, so every MPtrj material appears in any later MP snapshot. We exclude every one of the 154,718 ids in Matbench Discovery's MP reference snapshot `2023-01-10-mp-energies.csv.gz` — figshare doi:10.6084/m9.figshare.22715158 file 49083124, sha256 `046814c1c556e0e5…`.

That is a **proven superset** of MPtrj, not an approximation of it. The full MPtrj release is 12.2 GB of JSON (1.5 GB as an extxyz mirror) and its exact id list could only ever be a *subset* of what is excluded here — downloading it would make the exclusion weaker, not stronger, so it was not downloaded.

Snapshot ids are legacy (`mp-10597`); this harness sees the new format (`mp-aaaaaprp`). The two are the same integer written in base 26 over 'a'–'z' (`unseen.legacy_material_id`), verified against the live MP API in `tests/test_unseen.py`.

| step | materials |
|:--|--:|
| MP materials ≤ 40 atoms with a GGA/GGA+U hull | 117,692 |
| − in the MP 2023-01-10 snapshot (could be in MPtrj) | −116,894 |
| − same (formula, space group) as a WBM structure | −36 |
| − already a parent or target in the curated / auto pair sets | −25 |
| eligible unseen targets | 737 |
| … with a *seen* parent of the same prototype | 504 |
| … surviving prototype confirmation and the 5-per-prototype cap | **325** |

Rejections while verifying: StructureMatcher (anonymized): different prototype: 538, prototype cap reached: 578.

Composition of the frozen set: ≤0.025 172, 0.025–0.1 104, 0.1–0.3 33, >0.3 16 by MP hull bin; compound 295, metallic 30 by chemistry class; 274 of 325 swaps score as plausible on the pair sampler's own plausibility model.

**Residual uncertainty — stated, not assumed:**

* MACE-MPA-0 also trained on sAlex (subsampled Alexandria). Alexandria was filtered against WBM prototypes by its authors, not against Materials Project, so an Alexandria structure with the same prototype as one of these targets could have been in training. This test therefore shows that the targets are not in MPtrj; it cannot show that they are absent from sAlex.
* The snapshot holds 4 'mvc-' ids, which the base-26 id decoding cannot match. If MP later re-encoded those four materials into the mp- namespace they would not be excluded.
* A material that was in MP at 2022.9 and was deprecated before 2023-01-10 would be missing from the snapshot. Such a material could be in MPtrj and would not be excluded here.
* The parents are ordinary known MP materials and are expected to be in the training data. That is the realistic case: a scientist starts from something known. Only the target must be unseen.

## 3. What the pipeline was given

`predict(parent_mp_id, 'A:B')` — the parent's PBE structure and the substitution, nothing else. It built both starts itself (`sub`, `sub_rescaled`), relaxed them with the production engine through the same fallback ladder the calibration results went through, chose the lower-energy usable one, placed its energy on the Materials Project hull (mode (a)), ran the second engine for the disagreement check, and labelled the result with the frozen certified thresholds.

One thing had to differ from a real call: the target **is** in Materials Project, so its own MP entry was removed from the reference hull (`exclude_mp_ids`). Otherwise the candidate would be scored against a hull that already contains it. That is the same removal `stability.evaluate_target` makes for mode (a), and it is the situation WBM's numbers are in — a WBM material is not in the MP hull either. The DFT truth below is computed on the same hull, so prediction and truth are commensurate.

## 4. Routing — the same quantities as `reports/final_test.md`

| quantity                                      |   value |
|:----------------------------------------------|--------:|
| n                                             | 325.000 |
| likely stable                                 |  22.000 |
| likely unstable                               |  38.000 |
| send to DFT                                   | 265.000 |
| precision of 'likely stable'                  |   1.000 |
| NPV of 'likely unstable'                      |   0.947 |
| share sent to DFT                             |   0.815 |
| truly stable found as 'likely stable'         |   0.247 |
| truly stable sent to DFT                      |   0.730 |
| truly stable wrongly called 'likely unstable' |   0.022 |

'Likely stable' precision: 1.00 [0.85, 1.00] (target 90%); 'likely unstable' NPV: 0.947 [0.823, 0.994] (target 95%).

### Side by side with the locked WBM test set

Every rate here is a Clopper–Pearson interval on the actual call counts, on both sides. A bootstrap collapses to [1.00, 1.00] on a sample with no errors in it — which is exactly this set's 'likely stable' calls — and a verdict read off that bound would be an artifact of the estimator rather than a statement about the engine. The locked test's rates are recomputed the same way from its own counts, so the two columns are comparable; `reports/final_test.md` publishes bootstrap intervals, which is why its numbers read slightly narrower there.

| quantity | locked WBM test | same, with the product's > 0.3 eV/atom refusal | this unseen set (raw) | this unseen set, reweighted to the WBM bin mix |
|:--|:--|:--|:--|:--|
| precision of 'likely stable' | 0.96 [0.93, 0.98] (215/224) | 0.96 [0.93, 0.98] (215/224) | **1.00 [0.85, 1.00]** (22/22) | 1.00 [1.00, 1.00] † |
| NPV of 'likely unstable' | 0.988 [0.983, 0.992] (2121/2146) | 0.987 [0.980, 0.991] (1849/1874) | **0.947 [0.823, 0.994]** (36/38) | 0.980 [0.945, 1.000] |
| share sent to DFT | 0.407 | 0.475 | **0.815** | 0.793 [0.729, 0.851] |
| prevalence of truly stable | 0.153 | 0.153 | **0.274** | 0.153 |

† The reweighting resamples within each hull bin, and every 'likely stable' call in every bin here was correct — so that resampling cannot produce an error either, and the interval collapses just as the plain bootstrap does. Read the Clopper–Pearson column for the bound that means something; the reweighted point value still corrects the base rate, which is what it is for.

**Why the reweighted column exists.** Precision depends on the base rate. This set is real Materials Project materials, and MP adds mostly near-hull materials, so 27% of these targets are truly stable against 15% of the locked WBM test set. Comparing the raw numbers would compare two different base rates and flatter whichever set holds more stable materials. The last column reweights this set's per-bin results to the locked test set's hull-bin mix (bins used: 0.1–0.3, 0.025–0.1, <0, >0.3, 0–0.025), so the two are commensurate. Both columns are shown; neither is hidden.

Why candidates were sent to DFT (a candidate can have several reasons): low confidence: between the certified thresholds: 249, no threshold could be certified on either side for the oxide family at 90% precision / 95% NPV: 155, relaxation changed the structure: 60, no threshold could be certified on either side for the halide family at 90% precision / 95% NPV: 39, no threshold could be certified on either side for the pnictide family at 90% precision / 95% NPV: 12, predicted hull distance  is above the trusted range: 8, no threshold could be certified on either side for the chalcogenide family at 90% precision / 95% NPV: 8, known-weak chemistry: 4, engines disagree by: 4.

### 4b. The two sets are not the same chemistry — and that decides what can be compared at all

The certified thresholds are per chemistry family, and a family with no certified threshold on a side can never receive that label, whatever the engine predicts. So the comparison above is only as meaningful as the overlap between the two populations' chemistries:

| chemistry family   | this unseen set   | locked WBM test   | certified 'stable' threshold (meV/atom)   | certified 'unstable' threshold (meV/atom)   |
|:-------------------|:------------------|:------------------|:------------------------------------------|:--------------------------------------------|
| oxide              | 48%               | 5%                | none                                      | none                                        |
| f-electron         | 26%               | 53%               | -20                                       | +10                                         |
| halide             | 12%               | 5%                | none                                      | none                                        |
| intermetallic      | 6%                | 18%               | none                                      | +0                                          |
| pnictide           | 4%                | 6%                | none                                      | none                                        |
| chalcogenide       | 2%                | 6%                | none                                      | none                                        |
| other              | 2%                | 8%                | none                                      | +30                                         |

Read that table before reading any precision number on this page. Random elemental substitution into MP prototypes produces rare-earth intermetallics in bulk, which is why the locked WBM test set is mostly f-electron — and f-electron is the **only** family in which a 'likely stable' threshold could be certified at all. What Materials Project actually adds is complex oxides and halides, where neither side is certified. The published precision was therefore measured almost entirely on a chemistry that barely appears in this set.

## 5. Structure-finding rate — did the pipeline arrive at the right structure at all?

Nothing in the harness measured this before, and it is a product outcome rather than a diagnostic: if the relaxation lands somewhere else, every number attached to it describes a material the user did not ask about. Species-aware StructureMatcher at default tolerances against the target's MP PBE structure, parsed back from the CIF the product actually returns. 'Relaxation left its start' is the product's own refusal signal, which needs no DFT structure and is what a real candidate is judged on.

| bin       |   n | found the target structure   | relaxation left its start   |
|:----------|----:|:-----------------------------|:----------------------------|
| <0        |  89 | 0.89 [0.82, 0.96]            | 11%                         |
| 0–0.025   |  83 | 0.86 [0.78, 0.93]            | 16%                         |
| 0.025–0.1 | 105 | 0.74 [0.67, 0.83]            | 26%                         |
| 0.1–0.3   |  32 | 0.94 [0.84, 1.00]            | 6%                          |
| >0.3      |  16 | 0.38 [0.12, 0.62]            | 50%                         |
| all       | 325 | 0.81 [0.77, 0.85]            | 18%                         |

## 6. Energy error against MP's uncorrected PBE energy

Split by whether the pipeline found the target structure, because the two are different failures and are never mixed. MAE with its median and 10 % trimmed mean beside it, per the reporting rule. meV/atom.

| bin       | outcome           |   n | energy MAE           | median |err|         | trimmed mean         |
|:----------|:------------------|----:|:---------------------|:---------------------|:---------------------|
| <0        | same structure    |  79 | 7.1 [5.3, 9.5]       | 4.6 [3.3, 5.9]       | 5.1 [4.1, 6.7]       |
| 0–0.025   | same structure    |  71 | 7.7 [5.5, 10.3]      | 4.9 [3.1, 6.2]       | 5.3 [4.1, 7.1]       |
| 0.025–0.1 | same structure    |  78 | 12.1 [9.2, 15.4]     | 8.5 [4.9, 11.7]      | 9.6 [7.4, 12.3]      |
| 0.1–0.3   | same structure    |  30 | 14.0 [8.8, 19.9]     | 7.6 [4.2, 12.7]      | 11.3 [6.5, 17.4]     |
| >0.3      | same structure    |   6 | 24.9 [14.1, 35.8]    | 29.9 [6.5, 38.4]     | 24.9 [14.1, 35.8]    |
| <0        | relaxed elsewhere |  10 | 15.3 [6.7, 29.5]     | 9.4 [4.5, 14.4]      | 9.9 [6.2, 27.1]      |
| 0–0.025   | relaxed elsewhere |  12 | 7.4 [4.3, 11.0]      | 4.8 [3.3, 11.4]      | 6.6 [3.7, 10.9]      |
| 0.025–0.1 | relaxed elsewhere |  27 | 21.0 [15.1, 27.5]    | 15.8 [9.1, 22.9]     | 19.5 [13.3, 27.0]    |
| 0.1–0.3   | relaxed elsewhere |   2 | 29.9 [14.3, 45.5]    | 29.9 [14.3, 45.5]    | 29.9 [14.3, 45.5]    |
| >0.3      | relaxed elsewhere |  10 | 414.6 [249.3, 596.7] | 323.6 [163.0, 704.7] | 396.2 [221.9, 609.4] |

### Predicted hull distance against the true hull distance (meV/atom)

| bin       |   n | hull-distance MAE    | median |err|        | trimmed mean         |
|:----------|----:|:---------------------|:--------------------|:---------------------|
| <0        |  89 | 8.1 [5.7, 10.7]      | 4.7 [3.7, 6.0]      | 5.7 [4.5, 7.2]       |
| 0–0.025   |  83 | 7.7 [5.7, 9.8]       | 4.9 [3.6, 6.1]      | 5.5 [4.4, 7.0]       |
| 0.025–0.1 | 105 | 14.4 [11.5, 17.3]    | 9.4 [6.6, 14.1]     | 11.7 [9.2, 14.5]     |
| 0.1–0.3   |  32 | 15.0 [9.8, 20.8]     | 8.2 [5.2, 14.3]     | 12.5 [7.4, 18.6]     |
| >0.3      |  16 | 291.3 [158.1, 442.9] | 161.8 [39.6, 352.2] | 269.0 [130.0, 441.1] |

## 7. Does the WBM precision hold up on real chemistry?

Compared at the Clopper–Pearson lower bound on both sides. A bootstrap is degenerate on a sample with no errors in it (see §4), so a verdict read off one would be an artifact.

**Precision of 'likely stable': not distinguishable.** The interval here ([0.85, 1.00]) straddles the WBM lower bound (0.93); this set is too small to tell the two apart. The pessimistic reading is that the rate could be as low as 0.85, against 0.96 on WBM.

**NPV of 'likely unstable': not distinguishable.** The interval here ([0.82, 0.99]) straddles the WBM lower bound (0.98); this set is too small to tell the two apart. The pessimistic reading is that the rate could be as low as 0.82, against 0.99 on WBM.

At WBM's base rate, after reweighting: precision 1.00 [1.00, 1.00], NPV 0.980 [0.945, 1.000]. The reweighting corrects the base rate, which is what it is for, but its interval is resampled within bins — so where every call in every bin was correct it collapses for exactly the reason the plain bootstrap does, and the bound above is the one to read.

Read at face value:

* `likely stable` was awarded to 22 of 325 candidates; precision 1.00 [0.85, 1.00] — **trustworthy** at the pessimistic bound (trustworthy ≥ 0.80, caution ≥ 0.60).
* `likely unstable` was awarded to 38; NPV 0.947 [0.823, 0.994] — **not trustworthy** (trustworthy ≥ 0.95, caution ≥ 0.90).
* 82% of candidates were sent to DFT, against 41% on the locked WBM test set (48% once the product's > 0.3 eV/atom refusal is applied there too). That is the largest difference between the two populations, and §4b says why.
* The pipeline arrived at the right structure 0.81 [0.77, 0.85] of the time, measured here for the first time. Nothing in the WBM numbers speaks to this: a WBM candidate starts from WBM's own initial structure, while a real candidate is built from a parent prototype and can land anywhere.

### What this set cannot settle

* 325 candidates is a tenth of the locked test set, and the near-hull bins carry most of them. Intervals here are correspondingly wide, and the thinnest bins should not be read as verdicts.
* The base rate differs by a factor of 1.8 (27% truly stable here against 15% on WBM), because Materials Project adds mostly near-hull materials. The reweighted point values are the comparable ones; the raw column is what a user screening this population would actually see. Neither column's interval is any narrower than 22 and 38 calls allow.
* Absence from MPtrj is proven; absence from sAlex is not (see §2).

