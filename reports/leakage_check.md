# Is SevenNet-Omni's screening win trustworthy? — WBM leakage check

**Question.** SevenNet-Omni ranks first in `reports/phase3/screening.md` (expected cost per screened
candidate 0.036 [0.020, 0.054] vs 0.050 [0.032, 0.070] for MACE-MPA-0), but
`reports/phase3/candidates.md` marks it `compliant = unverified`. Our screening score is measured on
WBM. If WBM structures were in its training data, that score is not a measure of prediction.

**Answer in one line.** Its two largest Alexandria-derived training blocks — 112 of its 243 million
structures — are documented as WBM-prototype-filtered by their own authors, and the residual
unverified surface is about 1 % of the training set and structurally unlikely to contain WBM
prototypes; the screening win is **probably real but not certified**, and an in-harness control
(its lead is the same size on Materials Project pairs, which are not WBM) supports that. **Keep it at
`unverified` and do not adopt it on this evidence alone.** What would settle it is one cheap
experiment, named at the end.

Sources read 2026-09-12: the SevenNet-Omni paper (arXiv:2510.11241, Table 1 and Methods §3.1), the
OMat24 paper (arXiv:2410.12771, §2.1.1 and §4.3), Matbench Discovery `data/datasets.yml` and
`models/sevennet/sevennet-omni-i12.yml`, and the SevenNet docs (pretrained models page).

## 1. What is actually in the training set

SevenNet-Omni-i12 is trained on `COSMOSDataset`, 242,788,218 structures from 15 databases
(model metadata `training_sets: [COSMOSDataset]`). Table 1 of the paper gives the composition. Only
the inorganic-crystal blocks can possibly contain a WBM entry; the catalysis and molecular blocks
(OC20, OC22, ODAC23, OMol25, SPICE, QCML — 125 M structures) cannot.

| block | channel | structures | can it contain WBM prototypes? |
|:--|:--|--:|:--|
| OMat24 | `omat24` | 101,901,967 | **No — filtered at source.** See §2. |
| Alex, 3D part (= sAlex) | `mpa` | 10,447,765 | **No — filtered at source.** See §2. |
| Alex, 1D + 2D part | `mpa` | ≈ 1,621,301 | **Not documented.** See §3. |
| MPtrj | `mpa` | 1,580,394 | Not a leakage route for this benchmark. See §4. |
| MP-ALOE, MP-r²SCAN | `matpes_r2scan`, `mp_r2scan` | 914,534 | Materials-Project-derived; same as MPtrj. |
| MatPES PBE + MatPES-r²SCAN | `matpes`, `matpes_r2scan` | 781,478 | **Not documented.** Partly Alexandria-derived. |
| MAD | `mad` | 86,049 | Not documented; 0.04 % of training. |
| DBS (domain-bridging set) | `mpa` | 121,141 | 0.1 % resample of six of the blocks above; inherits their status. |
| OC20, OC22, ODAC23, OMol25, SPICE, QCML | various | 125,333,589 | No — catalysis and molecules, not bulk crystals. |

We run this engine through the `mpa` channel (`config.MODELS["sevennet-omni"]["modal"] = "mpa"`),
which the paper says is the PBE(+U) task trained on MPtrj + Alex + DBS.

## 2. The two big Alexandria-derived blocks are filtered, and their authors say so

Both come from FAIR's OMat24 release, and both were filtered against WBM with AFLOW structure
prototype labels — the same prototype-label machinery Matbench Discovery itself uses.

* **sAlex.** OMat24 paper §4.3: *"Since similar structures exist in the Alexandria and the WBM
  dataset used for testing, we subsampled the Alexandria dataset for training to ensure there was no
  leakage between the training and testing datasets. The new subset of Alexandria (sAlexandria) was
  created by removing all trajectories in which any structure matched a structure in the WBM initial
  and relaxed structures using structure prototype labels."*
* **OMat24 itself.** §2.1.1: the 5.3 million structures whose prototype label matches a WBM initial
  or relaxed structure — including everything generated from an Alexandria parent with a matching
  label — were moved into a held-out *WBM Test* split, which is **not** part of the released training
  and validation splits. *"filtering the dataset and creating this test split is important to ensure
  that there was no inadvertent data leakage from the training data to the final Matbench Discovery
  results, as there is overlap in materials between the Alexandria and WBM datasets."*

SevenNet-Omni's Methods say they use "the full datasets from MPtrj, OMat24, …" — i.e. the released
(already filtered) OMat24 train split — and for the Alexandria 3D structures "we adopt the sAlex
split provided in ref. [22]", ref. 22 being the OMat24 paper. So 112.3 M of the 242.8 M structures
(46 %), and the overwhelming majority of the Alexandria-derived data, are WBM-prototype-free by
construction.

This also disposes of the worry that put `unverified` in the registry in the first place. The
registry note for SevenNet-Omni reads *"15 datasets incl. MPtrj, OMat24 and a 12.1M-structure
Alexandria subsample (WBM filtering not stated)"*. The 12.1 M Alexandria subsample **is** stated —
in the paper's Methods, not in the model card — and it is sAlex plus 1D/2D structures.

## 3. What is left unverified

Three things, in order of size:

1. **Alexandria 1D and 2D configurations, ≈ 1.6 M structures** (Table 1 gives Alex = 12,069,066 for
   the `mpa` channel; sAlex is 10,447,765, so ≈ 1.62 M is the 1D/2D remainder). The Methods describe
   the 1D/2D subsampling as an outlier filter on energy, force and stress — *not* a WBM prototype
   filter. The authors never claim these were checked against WBM. **Why this is probably harmless:**
   WBM is a 3D bulk set (elemental substitution into 3D MP/ICSD prototypes) and a prototype label
   encodes stoichiometry, space group, Pearson symbol and Wyckoff positions, so a 2D layer or a 1D
   chain from Alexandria will essentially never carry the label of a 3D WBM entry. That is our
   structural argument, not a statement by the authors, and it is not a measurement.
2. **MatPES PBE and MatPES-r²SCAN, 0.78 M structures.** MatPES v1.0 is built from molecular-dynamics
   snapshots of Materials Project *and* Alexandria structures, and neither the MatPES release nor the
   SevenNet-Omni paper states a WBM prototype filter on the Alexandria-derived part. These feed the
   `matpes` / `matpes_r2scan` channels, not `mpa` — but see §5.
3. **MAD, 0.09 M structures**, provenance mixed and not documented against WBM.

Together that is at most ≈ 2.5 M of 242.8 M structures, about **1 %** of the training set, and the
part of it that is structurally capable of matching a 3D WBM prototype is smaller still.

## 4. Why MPtrj is not the leak

WBM was built by substituting elements into Materials Project prototypes, so MP prototypes and WBM
prototypes overlap *by construction* — for every engine, this one and MACE-MP-0 alike. Matbench
Discovery handles this with the **unique-prototype subset**: WBM entries whose protostructure already
appears in MP (or in an earlier WBM step) are excluded. This harness scores only that subset
(`harness/splits.py`: `summary["unique_prototype"] == True`; 215,488 rows), so training on MPtrj is
not a route by which a scored WBM structure can have been seen.

## 5. The multi-fidelity caveat — why "the mpa head is clean" is not the end of it

SevenNet-Omni is one network, not fifteen. The paper describes shared universal parameters θ_C plus
small task-specific parameters θ_T under selective regularization; `mpa` selects an inference channel,
it does not select a separate model. Anything the shared backbone learned from an unfiltered block
(MatPES's Alexandria-derived MD snapshots, the Alexandria 1D/2D trajectories) is available to the
`mpa` channel. So a clean `mpa` data list is **necessary but not sufficient**; the argument has to
cover the whole 243 M-structure training set, which is why §3 lists what it does.

## 6. An in-harness control that the leakage story fails to explain

If SevenNet-Omni's lead came from having seen WBM, the lead should appear on WBM and not elsewhere.
On the fixed screening subset (`reports/phase3/screening.md`, 125 MP pairs per hull bin + 500 WBM
calibration structures, identical structures for every engine) it appears in both places, and by
about the same factor:

| set | SevenNet-Omni | MACE-MPA-0 | ratio |
|:--|:--|:--|--:|
| **new (WBM), all bins** | 21.2 [16.1, 27.4] | 31.1 [25.7, 37.2] | 0.68 |
| known (MP pairs) ≤0.025 | 4.8 [3.8, 5.9] | 6.0 [4.7, 7.3] | 0.80 |
| known (MP pairs) 0.025–0.1 | 8.2 [6.6, 10.2] | 9.4 [7.5, 11.5] | 0.87 |
| known (MP pairs) 0.1–0.3 | 12.1 [8.0, 17.4] | 18.0 [13.2, 23.8] | 0.67 |
| known (MP pairs) >0.3 | 79.2 [41.9, 127.8] | 122.4 [69.0, 184.2] | 0.65 |

Energy MAE in meV/atom. The MP substitution pairs are not WBM: they are Materials Project targets
reached by element swaps inside this harness. SevenNet-Omni is 0.65–0.87× MACE-MPA-0's error there,
and 0.68× on WBM — no WBM-specific bonus. A leaked test set would show up as a WBM-only advantage.

This control is suggestive, not conclusive: both engines have seen MP-like space heavily, so the MP
pairs are not a fully independent yardstick, and the intervals overlap.

## 7. Verdict

* **Could WBM prototypes be in SevenNet-Omni's training data?** For 46 % of it (OMat24) and for the
  3D Alexandria part (sAlex), **no** — the dataset authors filtered on WBM prototype labels and say
  so. For about 1 % of it (Alexandria 1D/2D, MatPES, MAD), **not documented either way**, and a 3D
  WBM prototype turning up in a 1D/2D Alexandria trajectory is structurally unlikely.
* **Is the screening win trustworthy?** Probably real. It is not certified, and the number in
  `screening.md` should keep its footnote. The strongest single piece of evidence for it is §6,
  which is in-harness and does not depend on anyone's data-release claims.
* **Registry status:** leave `compliant: "unverified"`. It is no longer *unexamined* — §2 removes the
  original stated reason for the flag — but "unverified" is still the honest label while §3 stands.
  **Do not adopt this engine** on this evidence.
* **Also worth knowing:** "compliant" in `harness/config.py` means *training data verified free of
  WBM*, which is this project's definition, not Matbench Discovery's. The OMat24 paper titles its own
  leaderboard table *"Matbench-Discovery benchmark results of non-compliant models"* for its
  OMat24-pretrained models, so by the leaderboard's stricter rule (train on the sanctioned set only)
  MACE-MPA-0 and eSEN-30M-OAM are non-compliant too, despite being marked `True` here. That is a
  difference of definition, not a contradiction — but the column should not be read as a leaderboard
  compliance flag.

## 8. What would settle it, cheaply

Compute AFLOW protostructure labels (`matbench_discovery.structure.prototype.get_protostructure_label`,
the same function sAlex and OMat24 were filtered with) for the 8,000 WBM ids in `data/wbm_split.json`,
and for the Alexandria 1D/2D and MatPES entries SevenNet-Omni used, then intersect. It needs no
relaxations and no GPU — only the two training files and a label pass. A zero intersection would move
SevenNet-Omni from `unverified` to `True` under this project's definition; a non-zero one would tell
us exactly which scored ids to drop before believing the screening number. Until that is run, the
engine stays a candidate, not a choice.
