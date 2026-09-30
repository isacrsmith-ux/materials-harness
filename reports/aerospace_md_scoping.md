# Scoping: an MD tool with a ZBL-corrected potential

**Written 2026-09-29 (UTC), in answer to open decision 1 of `reports/aerospace_durability_development.md`.
This is a scope, not a build.** Nothing here changes the harness, the bundle or any locked set.

Measured numbers come from `scripts/aerospace_md_scoping.py` → `reports/aerospace_md_scoping.json`,
and from `reports/aerospace_phase0/`. Where a number is an *assumption* for sizing, it is labelled as
one.

## Bottom line

1. **"Add ZBL to the engine" is not the fix.** The production engine **already has** MACE's
   built-in ZBL term (`pair_repulsion: True` in the MPA-0 checkpoint; MP-0 has none). It is
   **4–7× weaker than the universal ZBL** at 0.3 Å. Its screening constants differ, and it is enveloped
   to zero at the sum of covalent radii. The learned part then adds 10–55 eV of repulsion that nothing
   supports between 0.8 and 1.25 Å. A correction has to *replace* the short-range energy, not add to it.
2. **Atomic-oxygen erosion and radiation damage are two different problems. Only one needs ZBL.**
   - An O atom at orbital speed carries **5.31 eV**. Head-on, it stops at **1.17 Å (Al)** and
     **1.43 Å (Ag)** even on MPA-0's soft curve. That is reactive chemistry near bonding distances, and
     ZBL is irrelevant there.
   - Radiation cascades are keV events deep in the ZBL region.
3. **Full collision cascades are out of reach on this machine.** MPA-0 needs **6.6 MB per atom** on CPU,
   so 36 GiB holds about **5,900 atoms**. The reference cascade study used 600,000 atoms (≈ 3.9 TB at
   that rate).
4. **What *is* feasible here** are 500-atom calculations: threshold displacement energies (the
   cascade-relevant quantity with experimental values) and single O-impact trajectories on metal slabs.
   Each costs **9.0 min per 1,000 MD steps** at 500 atoms.
5. **Neither feasible piece reaches the flight observables.** The flight accommodation and reactivity
   numbers integrate oxide growth over months to years. MD reaches nanoseconds at best.

**Recommendation.** Do not build a cascade tool on this hardware. If you want to continue, the smallest
honest scope is:

- **Stage 1:** a pairwise ZBL swap with its own tests.
- **Stage 2:** a threshold-displacement-energy pilot for Al.
- **Stage 3 (optional):** an O-impact pilot on Ag(111).

Each stage has a go/no-go gate. That buys a validated statement about short-range behaviour, not a
durability prediction. Whether that statement is worth having is your decision (see the end).

---

## 1. What already exists

| item | state | evidence |
|---|---|---|
| MACE built-in ZBL (`ZBLBasis`) | in mace-torch 0.3.16. **On in MPA-0, off in MP-0.** Constants in the checkpoint: c = [0.1818, 0.5099, 0.2802, 0.02817], a = 0.4543·0.529 Å/(Z₁^0.3 + Z₂^0.3), polynomial envelope p = 5 to zero at r_cov,1 + r_cov,2 | JSON `checkpoint_zbl`; `mace/modules/radial.py` |
| universal ZBL | a = 0.46850 Å/(Z₁^0.23 + Z₂^0.23), same four-exponential form | LAMMPS `pair_zbl` docs, read 2026-09-29 (see feasibility memo) |
| MD integrators | ASE 3.29 (Velocity Verlet, Langevin) with the MACE calculator. No new dependency. | installed |
| LAMMPS | **not installed** (no `lmp`, no Python module) | checked 2026-09-29 |
| DFT code | **none installed** (no PySCF, GPAW, Psi4, QE, VASP, CP2K) | checked 2026-09-29 |
| per-atom energies from MACE | exposed (`energies`, `node_energy`). **Per-atom forces are not.** | `mace/calculators/mace.py` |

### Where MPA-0's short-range energy comes from

Universal ZBL divided by MPA-0's own ZBL term. The learned part is the model total minus its ZBL term.

| pair | 0.3 Å | 0.5 Å | 0.8 Å | 1.0 Å | 1.25 Å |
|---|---:|---:|---:|---:|---:|
| Al–Al ratio | 4.2 | 7.1 | 14.3 | 22.2 | 39.3 |
| Al–O ratio | 3.9 | 6.4 | 13.6 | 23.7 | 57.9 |
| Ag–O ratio | 5.1 | 9.4 | 21.3 | 36.0 | 76.9 |
| Ag–Ag ratio | 7.0 | 14.6 | 34.8 | 57.7 | 112.9 |

The eV values are in the JSON (`mpa0_dimer_decomposition`). For example, at 0.8 Å Al–Al is 100.7 eV
(universal), 7.0 eV (MACE term) and 19.9 eV (model total). At 0.8–1.25 Å the learned part is +10 to +55 eV
for every pair except Al–O at 1.25 Å. The ZBL gap and the learned bump both have to be dealt with.

---

## 2. Two problems, sized separately

| | atomic-oxygen impact | radiation-damage cascade |
|---|---|---|
| energy scale | O at 8 km/s (NTRS 19890003221, p. 1): **5.31 eV** lab; 3.33 eV (Al) and 4.62 eV (Ag) centre-of-mass | keV primary knock-on atoms (arXiv:1904.00360 used 1–5 keV) |
| separations probed | head-on stop at **1.17 Å (Al)**, **1.43 Å (Ag)** on the MPA-0 dimer | well below 1 Å |
| does ZBL matter? | **no.** The question is reactive chemistry at mild compression, validated only by DFT or beam experiments | **yes.** This is the regime where MPA-0 is 4–7× too soft at 0.3 Å |
| system size | slab of a few hundred atoms | 600,000 atoms in the reference study |
| feasible here? | yes: **9.0 min per 1,000 steps** at 500 atoms | **no** for cascades. **Yes** for threshold displacement energies, which use 500-atom cells in the reference study |
| what it would tell you | initial sticking/reaction of O on a clean surface | how many defects a hit leaves; the displacement threshold E_d |
| link to flight data | **weak.** Flight accommodation integrates years on an oxidising surface | **none in hand.** Neither flight source measures radiation damage |

---

## 3. Short-range correction: the options

| option | what it is | forces | fixes the learned bump? | needs | risk |
|---|---|---|---|---|---|
| **A. pairwise ZBL swap** | E = E_MPA-0 − Σ S(r)·ZBL_MACE(r) + Σ S(r)·ZBL_univ(r), with a smooth switch S from 1 to 0 over [R_a, R_b] | exact, analytic, ASE-level | **no**, unless R_b reaches about 1.3 Å, which would start touching near-equilibrium physics | nothing new | small. Can be tested against Phase 0: near-equilibrium energies must not move |
| **B. per-atom blend** (arXiv:1904.00360, eqs. 3–6) | E = Σᵢ [wᵢ·E_ZBL,i + (1 − wᵢ)·E_MLIP,i], with wᵢ from a smooth-minimum neighbour distance | need ∂E_MLIP,i/∂r, which is **not exposed**; must be built inside the torch model with autograd | **yes**: it turns the MLIP off inside R_a | wrapping the MACE model | moderate. Touches the engine's internals. Every settings tag changes |
| **C. fine-tune MPA-0** with short-range reference data | MACE fine-tuning on DFT dimer and compressed-cell data | native | **yes**, if the data covers it | a DFT code and a DFT campaign (none installed) | the real fix, and the costliest |
| **D. adopt an external cascade potential** (e.g. the DP-ZBL Al model, or EAM/MEAM-ZBL) | use someone else's validated potential | native in LAMMPS | n/a | LAMMPS, licence check (**not done**) | changes the product: the harness would validate *their* potential, not the MLIP it exists to test |

**Recommendation among these: A first.** It is the only option that needs nothing new, and it is testable
against Phase 0 without new reference data. Measure whether the learned bump matters for E_d before
paying for B or C.

---

## 4. What would make it a harness claim (validation targets)

Nothing below has been read yet. **No reference value is quoted.** Each must be read from the primary
source, in-session, before its stage starts.

| target | reference kind | status |
|---|---|---|
| dimer curves below R_a | universal ZBL (constants already read) | ready |
| 0.8–1.5 Å transition region | DFT dimers / compressed cells | **no local DFT code.** It is also the cheapest possible DFT campaign |
| E_d for Al, then Ag/Cu | experimental threshold displacement energies | arXiv:1904.00360 cites a "recommended" 25 eV for fcc Al via its refs 63 and 66. **Secondary and not read.** Read the primary sources before any comparison |
| near-equilibrium invariance | Phase 0 values (vacancy, interstitials, O/Ag(111)) must not move beyond a fixed tolerance after the swap | ready, in-repo |
| O sticking / reaction on Ag, Al | hyperthermal (~5 eV) molecular-beam experiments or DFT impact trajectories | **not searched yet** |

Following the harness's own discipline, an E_d comparison would need to be **pre-registered**:

- tolerance, directions and sampling fixed first;
- the protocol committed before the first MD run;
- a miss reported as a miss.

Anything run before that is development-tier.

---

## 5. Compute, from measured throughput

Measured MPA-0 force calls (CPU, float32, `reports/aerospace_md_scoping.json`):

| atoms | s per force call | µs per atom per step | peak memory |
|---:|---:|---:|---:|
| 500 | 0.54 | 1,082 | 4.0 GB |
| 2,048 | 2.24 | 1,094 | 14.5 GB |
| 4,000 | 7.67 | 1,917 | 26.3 GB |

Up to 2,048 atoms the cost is linear. At 4,000 atoms the machine is memory-bound (26 GB of 36 GiB),
and the rate degrades and varies from run to run. **Plan on ≤ 2,000 atoms.**

**Sizing examples.** The run counts and step counts are **assumptions**, to be replaced by pilot
measurements:

| study | assumed size | estimate at 500 atoms |
|---|---|---:|
| E_d survey, Al | 100 directions × 6 bisection runs × 2,000 steps | **7.5 days** of one process |
| O-impact statistics, Ag(111) | 200 trajectories × 3,000 steps | **3.8 days** |
| one 600,000-atom cascade | — | **impossible** (≈ 3.9 TB) |

- **Both feasible studies exceed the 2-hour line.** Each would need resumable, idempotent run machinery
  and the ETA gate the ground rules require.
- **They would also need a runner decision**, because they compete with the nightly queue.
- **Unmeasured levers:**
  - running several single-thread processes in parallel instead of one multi-thread process;
  - MPS float32 (the benchmark only showed MPS/float64 fails);
  - a GPU machine, which changes the cascade answer entirely.

---

## 6. Proposed stages, each gated

| stage | work | compute | gate to continue |
|---|---|---|---|
| **1. Pairwise ZBL swap** (option A) | one ASE calculator plus tests. Dimers must equal universal ZBL below R_a and be monotonic below R_b. Every Phase 0 near-equilibrium value must be unchanged within tolerance | minutes | tests pass **and** you agree the learned bump can stay for now |
| **2. E_d pilot, Al** | read the primary E_d sources; pre-register tolerance and sampling; pilot 5 directions to measure steps per run and replace the assumptions above | pilot ≈ hours; full survey scaled from the pilot | the pilot's ETA is acceptable to you, and the resumable runner is approved |
| **3. O-impact pilot, Ag(111)** (optional, no ZBL needed) | search for and read beam or DFT reference data; 10 trajectories to measure cost and outcome spread | ≈ hours | a reference exists to compare against. Without one, this stage produces no evidence and should not run |

**Not proposed:** full cascades on this hardware, option D (it changes what the harness validates), and
anything claiming to predict flight accommodation or reactivity.

## Open decisions

1. **Is a validated short-range statement worth building?** Stages 1–2 would yield "MPA-0 with a ZBL swap
   reproduces experimental E_d for Al within X". That is a claim about radiation-damage physics, and **no
   flight data in hand measures radiation damage**. If the product question is atomic-oxygen durability,
   stages 1–2 do not serve it.
2. **For atomic oxygen, which reference would you accept?** Beam experiments or a DFT campaign. The
   latter is the first real monetary cost in this track, and it would also serve option C.
3. **Hardware.** Cascades need a GPU or a much larger machine. Is that on the table, or is this track
   capped at 500-atom studies?
4. **Runner.** Stage 2 would be the first multi-day compute since the OQMD campaign. Does it get the queue,
   or does the paused stability-screening track?
