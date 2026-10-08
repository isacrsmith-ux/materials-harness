# Aerospace Stage 2: threshold displacement energy of Al. Pre-registration **DRAFT, NOT FROZEN**

**DRAFT, NOT FROZEN.** This file is a draft. It is not a pre-registration until Isac freezes and commits it as one, and **nothing in it has
been run**: no E_d molecular dynamics, no pilot. Stage 2 itself remains his decision (`reports/aerospace_stage1.md`, open decision 2).
Tier if it were run: pre-registered held-out only after freezing; anything run before that is development tier. Written 2026-10-07 local
(2026-10-08 UTC) from sources read in-session. Every number below is either read from a cited source that day or computed from the repository files named.

## 0. What Stage 1 left standing, and what this draft decided

- **Engine:** the production engine `mace-mpa-0-medium` (cpu, float32) with `harness.zbl.corrected` (Stage 1). Not the second engine: it has no built-in
  short-range term and its Al-Al dimer goes negative at close range (Phase 0).
- **Gate 2 FAILED and its verdict stands** (section 9).
- **The "recommended 25 eV" could not be traced to a primary source** (section 2). The primary experiments that could be read say **16 eV**.
  That changes what the experiment should be compared with, and is the first thing for Isac to decide at freeze.

## 1. The claim, and what is not claimed

**Claim (one sentence):** *In fcc Al, the production engine with the Stage 1 correction produces a threshold displacement energy, for the lowest-threshold
direction among the sampled directions, within a pre-set tolerance of the experimentally measured threshold energy.*

**Not claimed:** anything about atomic-oxygen erosion (Stage 2 does not touch it; the flight data in hand measure no radiation damage), about other metals,
about cascades above threshold, or about the average E_d over all directions (that needs the full survey of section 3, which this draft does not freeze).
Stage 1's correction is not what this tests (section 4, "What the E_d regime exercises").

## 2. What E_d means here, and what the sources say

E_d is not one number. The sources differ in **what it is** (minimum or average, over directions), **how it was obtained** (experiment or MD), and **at what
temperature**. Everything below was read in-session on 2026-10-08 UTC; hashes are in `docs/methodology/data_provenance.md`.

| value | definition as the source gives it | temperature | method | source (what I read) |
|---|---|---|---|---|
| **16 eV** | the threshold found by extrapolating the damage rate to zero damage production | near 8 K | resistivity increase of Al under electron irradiation, 0.19-1.6 MeV; experiment | Neely & Bauer, *Phys. Rev.* **149**, 535 (1966): abstract on the APS page |
| **19 eV** | an *effective* threshold, from fitting the measured displacement cross section with a unit step function and a Frenkel resistivity | near 8 K | same experiment; a fit parameter, not a measured onset | same abstract |
| **16 eV** | the threshold for an atomic displacement, from analysis of the damage rate against electron energy; high-purity Al, 0.16-0.40 MeV | not in the abstract (the paper discusses stage-I recovery, i.e. low-temperature irradiation) | electron irradiation; experiment | Simpson & Chaplin, *Phys. Rev.* **185**, 958 (1969): abstract on the APS page |
| **25.0 eV** | a *recommended* value for fcc Al, cited to refs 63 and 66 | not given | a convention for NRT-dpa; **not a measurement as quoted** | arXiv:1904.00360 Table II and supplement; ref 63 is G. S. Was, *Fundamentals of Radiation Materials Science* (Springer, 2016), ref 66 is Norgett, Robinson, Torrens, *Annual Book of ASTM Standards* (1975). **Both are paywalled and were not read.** |
| 26.54 / 22.67 / 16.73 eV | the spherical average of a per-direction threshold, which is the lowest PKA energy that leaves a stable Frenkel pair; PKA velocity on a 5 degree grid, 500-atom cell | not stated for this procedure (the cascade runs use 300 K) | MD with DP-ZBL / MEAM-ZBL / EAM-ZBL | arXiv:1904.00360 Table II and supplement |
| per-direction E_d(Al) for <100>, <110>, <111> | per direction, the lowest PKA kinetic energy that forms a stable defect | 100 K | OF-DFT and MD, 32,000 atoms | Qiu, arXiv:1709.08288 Fig. 1: **a graph only, no tabulated values**; the text says E_d has low pockets around <100>, <110> and <111> |
| no Al value | E_d is taken as the average threshold displacement energy (citing Nordlund, Wallenius, Malerba 2005); the table lists Fe 40, Cu 33, Ni 39, Pd 41, Pt 42, W 70 eV | n/a | arc-dpa parameters from MD | Nordlund et al., *Nat. Commun.* **9**, 1084 (2018), Table 1. **Al is not listed.** |
| no Al value | the review defines the threshold per direction, says it is stochastic near threshold and falls with temperature, and puts metals typically at 10-50 eV; 25 eV appears only as an *assumed* input to an ion-mixing calculation | n/a | review | Nordlund et al., *J. Nucl. Mater.* **512**, 450 (2018), section 2.1 and its Table 2 |

**What this says.**

1. **The experimentally measured onset for Al is 16 eV** in two independent low-energy electron experiments (Neely & Bauer; Simpson & Chaplin), with a
   fitted *effective* 19 eV in the first. The abstracts do not say which direction was probed or whether the sample was a polycrystal. An onset extrapolated
   from the damage rate to zero is expected to reflect the easiest directions, so it is read here as a **minimum-type threshold**. That is an inference, not something the abstracts state.
2. **The "recommended 25 eV" is a different thing.** As quoted it is an NRT convention. The primary route to it (a textbook and an ASTM table) was not
   readable. It sits 9 eV above the measured onset. It is plausibly closer in kind to a direction average than to a minimum, but **that is not established by anything I read**.
3. **Which one the engine should be compared with depends on which quantity is computed.** A *minimum over directions* is the analogue of the 16 eV
   experiments. A *spherical average* is the analogue of a recommended value (and of the three MD numbers in the table), and needs far more directions than a pilot can afford.
4. **The Al experimental direction dependence is not in any readable source** (Jung's Landolt-Bornstein chapter, Ehrhart's compilation and the earlier
   Lucasson-Walker and Iseler papers are paywalled or old and were not read). Neither abstract gives crystal orientation.

**Sources named but not read, and why:** Was (2016), Norgett-Robinson-Torrens (ASTM, 1975; and *Nucl. Eng. Des.* **33**, 50), Jung and Ehrhart in
Landolt-Bornstein vol. 25 (1991), Lucasson & Walker (1962), Iseler et al. (1966), Nordlund-Wallenius-Malerba (2005), King-Merkle-Meshii (1983, cited for the
low-E_d pockets; whether it concerns Al was not checked). All paywalled or not fetched.

## 3. Directions and sampling

- **Pilot (what this draft would freeze): five directions.** <100>, <110>, <111>, <310> and one fixed general direction. The first three are the symmetry
  axes; <310> appears among the electron-irradiation directions of a recent Al study (Materials, open access, PMC12843142), qualitatively only; the general
  direction is fixed now as (3, 2, 1)/sqrt(14), not drawn, so that the set is known before any run.
- **PKA:** the atom nearest the cell centre. Velocity set along the direction from the PKA's kinetic energy; the centre-of-mass motion of the cell is left as it is.
- **Full survey (not frozen here):** uniform in solid angle over the irreducible wedge of the cubic group, N directions chosen after the pilot's cost is known. Its
  summary statistic would be the area-weighted average E_d, to be compared with the 25 eV convention only as a convention. The reference MD study's 5 degree grid
  over-samples the pole (a uniform grid in the angles is not uniform on the sphere), and it does not say how it weighted; this draft will not copy that.
- **Why a minimum over five directions is biased and in which direction:** the lowest of five thresholds can only be **at or above** the true minimum. So a
  sampled minimum below the reference by more than the tolerance is conclusive; one above is only an upper bound on the true minimum (section 7).

## 4. Temperature, cell, integration

- **Temperature: 10 K**, to match the near-8 K experiments, set by an ASE Langevin equilibration of 2 ps before the PKA is launched and NVE after. (Option: 0 K, athermal, deterministic;
  cheaper, but the review notes the onset is still stochastic at 0 K, and float32 noise decides near-threshold outcomes, so determinism is not purchased.)
- **Cell:** fcc Al, **5x5x5 conventional cells = 500 atoms**, periodic, lattice constant the engine's own zero-pressure value (4.0387 A in Phase 0). 500 atoms is the
  reference study's size and is far inside the 2,000-atom budget. A **6x6x6 (864 atoms) check in one direction** tests size sensitivity.
- **Integration:** velocity Verlet, **1 fs**, 1,000 steps (1 ps) as the default. The run length is **set by the calibration step** (section 8), not frozen
  from guesswork: the end of recombination is read off three test runs.
- **What the E_d regime exercises (computed, `reports/drafts/aerospace_stage2_turning_points.json`):** the head-on, two-body turning point of an Al-Al collision with
  E_cm = E_PKA/2. The Stage 1 switch runs from R_a = 0.968 A to R_b = 1.694 A.

| E_PKA (eV) | E_cm (eV) | turning point, ZBL (A) | engine alone (A) | engine + correction (A) | barrier shift from the correction (eV) |
|---:|---:|---:|---:|---:|---:|
| 10 | 5.0 | 1.695 | 1.623 | 1.623 | 0.01 |
| 16 | 8.0 | 1.532 | 1.486 | 1.492 | 0.17 |
| 20 | 10.0 | 1.458 | 1.427 | 1.434 | 0.25 |
| 25 | 12.5 | 1.385 | 1.371 | 1.376 | 0.22 |
| 32 | 16.0 | 1.307 | 1.302 | 1.305 | 0.14 |
| 36 | 18.0 | 1.271 | 1.256 | 1.267 | 0.61 |
| 40 | 20.0 | 1.239 | 1.186 | 1.233 | 3.23 |
| 50 | 25.0 | 1.172 | 0.669 | 1.165 | 153.77 |
| 100 | 50.0 | 0.978 | 0.521 | 0.978 | 323.74 |

  Up to E_PKA = 36 eV the correction moves the turning point by at most 0.011 A and the barrier by at most 0.61 eV: **it is nearly inert in the
  E_d regime**, because there MPA-0's own repulsive wall (1.3-1.6 A) is already within a few percent of ZBL. From 40 eV up the uncorrected engine turns at about
  0.5-0.7 A (the non-monotonic dimer found in Phase 0) while the corrected curve follows ZBL. **So the verdict is a test of the engine's own wall and its many-body behaviour at
  1.3-1.6 A, not of the ZBL swap**; the swap matters for the high-energy bracket runs (above about 40 eV), where the uncorrected engine would give artefacts. This is a two-body estimate
  (a bound neighbour takes less energy than a free one), so it is indicative only.

## 5. The energy ladder and the stopping rule

Per direction, per seed:

1. **Bracket:** run at 10 eV (expect no stable pair) and at 100 eV (expect one).
   If 100 eV gives none, the direction is **censored (E_d > 100 eV)** and is INCONCLUSIVE for that direction.
   If 10 eV already gives one, the direction is censored below and recorded.
2. **Bisect** the bracket to **1 eV** resolution (7 further runs).
3. **Confirm monotonicity:** run at E* + 2, + 5 and + 10 eV, where E* is the lowest bisected energy that produced a stable pair. If any of them gives none, the threshold is
   not a clean step: **set E* to the next rung above that failure and repeat step 3**. Stop after at most 3 such resets and mark the direction INCONCLUSIVE.
4. **E_d(direction) := E*** once step 3 passes.
5. **Hard stops:** at most 20 runs per direction; the pilot ends at the wall-clock cap of section 8; a run whose total energy drifts by more than 1% of E_PKA, or ends in a
   numerical failure, is discarded and re-run once with a new seed, then the direction is INCONCLUSIVE.

**Reproducibility (R1):** for the two rungs that straddle E*, repeat with 3 seeds each (thermal seeds at 10 K, same PKA and direction). E* is **reproducible** if the
no-event rung gives no event in at least 2 of 3 and the event rung gives one in at least 2 of 3. Otherwise the direction's threshold is stochastic at this resolution and the direction is INCONCLUSIVE.

## 6. Definition of "displaced" (a stable Frenkel pair)

- **After the run:** continue NVE to the length set in section 8, then relax with the harness's own optimiser to fmax = 0.01 eV/A (Phase 0 and Stage 1 use this).
- **Wigner-Seitz analysis** against the **pre-PKA relaxed perfect lattice** (ideal sites at their relaxed positions): each atom is assigned to its nearest site; a site with no atom is a
  vacancy, a site with two or more is an interstitial.
- **A stable Frenkel pair:** at least one vacancy and one interstitial **survive the final relaxation** and a hold of 5 ps at 10 K after it. Surviving the relaxation is what excludes the
  spontaneous-recombination case that makes the threshold exceed the Frenkel-pair formation energy (Nordlund 2018, section 2.1). The pair separation is recorded as a covariate but is not a criterion.
- **Not displaced:** any final state with zero vacancies and zero interstitials after relaxation, however far atoms moved during the run.
- **Why not copy the reference study:** it says only "a stable Frenkel pair", with no stated criterion. This definition is mine and is part of what Isac is asked to accept at freeze.

## 7. Tolerance, and PASS / FAIL / INCONCLUSIVE

**Primary quantity:** Q = the lowest E_d(direction) among the five pilot directions, compared with the measured onset **E_ref = 16 eV** (both primary experiments).

**Tolerance (to be fixed by Isac at freeze; this is a proposal):** **+-4 eV**. The reasoning, all computed from what was read:
the experimental spread is 16 to 19 eV (the fitted effective value), 3 eV; and in the reference MD study the three potentials sit 1.54, 2.33 and
8.27 eV from its 25 eV figure (DP-ZBL, MEAM-ZBL, EAM-ZBL), so +-4 eV would have passed the first two and failed the third. Alternatives: +-2 eV (narrower than the 3 eV between the two experimental readings), +-6 eV (looser than the
reference MD potentials' own spread).

| outcome | rule |
|---|---|
| **PASS** | all five directions resolved (bracket within 1 eV, section 5), R1 satisfied for the direction that sets Q, and \|Q - E_ref\| <= tolerance |
| **FAIL** | all five resolved and R1 satisfied for the direction that sets Q, and **Q < E_ref - tolerance** (the lowest sampled threshold is already too low; unsampled directions cannot raise it) |
| **INCONCLUSIVE** | anything else, including: **Q > E_ref + tolerance** (a sampled minimum is only an upper bound on the true minimum, so this does not show the engine is too stiff, unless Isac decides at freeze to treat the five directions as the whole set); any direction censored or unresolved; R1 not satisfied; a numerical failure; fewer than five directions finished within the cap; or the plain-engine secondary run disagrees with the corrected one by more than the tolerance at the rung that sets E* |

**Pre-set secondary reports (no verdict):**
- the **plain engine** (no correction) on the same initial conditions for every rung at or below 36 eV, to show directly that the correction is inert in this regime;
- E_d for every direction, with its bracket, seed outcomes, final defect positions and separations;
- the 864-atom check in one direction;
- Q against the 19 eV effective value and, as a convention only, the lowest direction against 25 eV.

**The 25 eV convention is not a verdict criterion:** as quoted it is not a measurement, and the primary route to it was not read.

## 8. Compute sizing, from measured MPA-0 throughput

Measured (`reports/aerospace_md_scoping.json`, CPU, float32): **0.541 s per force call at 500 atoms**, 2.24 s at 2,048; the cost per atom per step is flat up to 2,048 atoms
(about 1088 us), so other sizes are scaled linearly. One step of MD costs one force call; the integrator overhead is not measured and is taken as zero.

| cell | atoms | minutes per 1,000 steps |
|---|---:|---:|
| 5x5x5 (500 atoms, primary) | 500 | 9.0 |
| 6x6x6 (864 atoms, size check) | 864 | 15.7 |
| 7x7x7 (1,372 atoms) | 1372 | 24.9 |

Runs per direction: the bracket (2), the bisection (7) and the monotonicity checks (3) are **12 runs**; with R1's three seeds on two straddling rungs, **18 runs**. At 1,000 steps and 500 atoms:

| plan | runs per direction | hours per direction | hours for 5 directions |
|---|---:|---:|---:|
| bisection and confirmation only | 12 | 1.8 | 9.0 |
| with R1 | 18 | 2.7 | 13.5 |

- **Both exceed the 2-hour gate**, so the pilot needs resumable, idempotent run machinery and its ETA approved by Isac. They also compete with the nightly runner.
- **Calibration step (no verdict, under the gate):** three runs on <100> at 500 atoms (12, 25 and 40 eV) take about 27 minutes. They set the run length, the energy-drift tolerance and the
  timestep check, and replace the guesses above. This is the only thing the draft proposes to run before a freeze.
- **Unmeasured levers** that could cut these times: several single-thread processes in parallel, and MPS float32. Neither is assumed. The 7.5-day figure in the scoping report was an assumption (100 directions);
  this pilot is not that survey.
- **Wall-clock cap (proposed):** 24 h for the pilot, after which unfinished directions are INCONCLUSIVE.

## 9. Gate 2 failed: how this draft treats it

- **The record.** Stage 1 gate 2 (near-equilibrium invariance within 1 meV of the Phase 0 values) **FAILED**: 5.4 meV on `/al_defects/by_mode/zero_pressure/864/tetrahedral/E_f_eV`; the diagnosis (`reports/aerospace_stage1_gate2_diagnosis.json`) attributes it to the engine's own float32 run-to-run noise, not the correction: the engine alone misses by as much, (plain minus Phase 0: 4.88 meV at most), and 14 of
  40 values are bit-identical between plain and corrected runs. **The recorded verdict stays FAIL.**
- **This draft does not re-specify or waive Gate 2.** That is Stage 1's open decision 1 and remains Isac's.
- **How the draft is built so that the failure does not decide the verdict:**
  1. The E_d tolerance is in eV; the noise is in meV, about three orders smaller.
  2. The one route from float32 noise to the verdict is chaotic amplification of a near-threshold event. **R1 measures it directly** (repeat seeds at the straddling rungs), and a direction
     that is not reproducible is INCONCLUSIVE, never a PASS or a FAIL.
  3. The plain engine is run on the same initial conditions at every rung below 36 eV, so the correction's effect is observed, not assumed.
- **If Isac re-specifies Gate 2 before freezing**, the re-specified gate is run first and its result goes into the frozen record. **If he does not**, any result must be reported as
  *conditional on an engine and correction whose Gate 2 verdict is FAIL*, with the diagnosis attached.

## 10. Comparison resources: recorded, not acquired

These matter only as comparators. **Scope option D, "adopt an external potential", changes the product** (the harness would validate someone else's potential), and nothing here proposes it.

| resource | what I could read | licence as read | status |
|---|---|---|---|
| **IAEA CascadesDB** (cascadesdb.iaea.org) | **Nothing from the site.** curl got HTTP 403 and a JavaScript challenge ("Just a moment ..."); WebFetch got HTTP 402. Not bypassed. A web-search summary (secondary, unverified) says the database lists W, Fe, Cu, Au, Ag, Ni, Pd and Pt, **not Al**, in 14,398 simulations; I did not confirm it | **not read** | Al coverage and licence **unknown**; do not rely on the search summary |
| **OpenKIM `MO_971738391444`**, doi:10.25950/96965eb6: "MEAM_LAMMPS_RoyDuttaChakraborti_2021_AlLi", a 2NN MEAM for Al and Al-Li (Roy, Dutta, Chakraborti, *Comput. Mater. Sci.* **190**, 2021) | the item page and its LICENSE file (v000; a newer v001 exists and was not read) | **Copyright held by the authors; no commercial use without permission; free for academic use "at the user's own risk", provided the 2021 article is cited.** Not an open-source licence | comparator only; it would not fit this Apache-2.0 repository without the authors' permission |
| **NIST Interatomic Potentials Repository** (ctcms.nist.gov/potentials) | the home page and the Al system page, which lists many Al entries. The home page asks for acknowledgement when potentials are used; one Al entry is noted to be used together with ZBL in LAMMPS (an MTP, files from 2026) | **no licence statement on the pages read**; each entry has its own citation | comparator only; per-potential licences would have to be read |

## 11. What Isac would be deciding at freeze

1. **Which reference?** 16 eV (measured onset, two experiments) as proposed, or the 25 eV convention. This draft recommends 16 eV and treats 25 eV as a convention only.
2. **Tolerance:** +-4 eV as proposed, or +-2 or +-6.
3. **Whether a sampled minimum above the band may count as FAIL** (treating five directions as the whole set), or stays INCONCLUSIVE as proposed.
4. **Temperature** (10 K as proposed, or 0 K), **cell** (500 atoms) and **run length** (after the calibration).
5. **Whether the E_d pilot is wanted at all.** Stage 2 tests radiation-damage physics, and no flight data in hand measures radiation damage; and in this regime it tests the
   engine's own repulsive wall rather than the ZBL swap (section 4).
6. **The runner:** the pilot exceeds 2 hours and competes with the nightly queue.
7. **Gate 2** (section 9).

## 12. What this draft does not do

It does not freeze, commit as a pre-registration, run an E_d simulation, or touch the bundle, the registry, any locked set, `harness/predict.py` or any settings tag.
