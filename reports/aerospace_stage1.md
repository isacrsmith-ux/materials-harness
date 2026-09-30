# Aerospace Stage 1 — pairwise ZBL swap on the production engine

**Written 2026-09-30 (UTC).** This is Stage 1 of `reports/aerospace_md_scoping.md` §6. The gates and
tolerances were fixed in `scripts/aerospace_stage1.py` before any run.

- **Result: 2 of 3 gates pass. Gate 2 FAILED at its pre-set 1 meV tolerance.**
- **Diagnosis:** the failure is the engine's own float32 run-to-run noise, not the correction. The
  verdict stands as recorded; re-specifying the gate is an open decision.

Numbers come from `reports/aerospace_stage1.json` and `reports/aerospace_stage1_gate2_diagnosis.json`.
Nothing here touches `harness.predict`, the bundle, any settings tag or any locked set.

## What was built

`harness/zbl.py`. It corrects the engine pair by pair:

    E = E_engine + Σ_pairs S(r)·[ZBL(r) − V_engine(r)]

- **V_engine** is the engine's own isolated-dimer curve, tabulated at construction.
- **S** is 1 below R_a and 0 above R_b, with the C² switch of arXiv:1904.00360 eq. 4.
- **Switching range:** R_a = 0.40 and R_b = 0.70 × the sum of covalent radii. These are calibration knobs.
- **Forces and stress** are analytic.
- **Use:** `harness.zbl.corrected(engine, elements)` returns one ASE calculator.

**A deviation from the scope, stated plainly.** Scope §3-A proposed swapping only MACE's built-in ZBL
term. That leaves the learned energy inside the core, −70.5 eV for Al–Al at 0.3 Å (the scoping JSON), so it
could not meet the scope's own gate "dimer = ZBL below R_a". Subtracting the whole dimer curve meets it,
and it also removes the 0.8–1.25 Å learned bump *at the dimer level*.

**Known ceiling:** in a condensed phase, a close pair's many-body engine energy is not exactly
V_engine(r). Option B or C removes that.

**Tests:** `tests/test_zbl.py`, 6 tests, model-free (a Morse potential stands in for the engine). They
check:

- the ZBL derivative against finite differences;
- the switch values and derivative;
- dimer = ZBL inside R_a and = the engine outside R_b;
- forces and stress against finite differences, with a pair inside the switching range;
- no change at equilibrium.

The suite now passes 350 tests.

## Gates

| gate | criterion (fixed before running) | result |
|---|---|---|
| **1. dimers** | Al–Al, Al–O, Ag–O, Ag–Ag, O–O: within 1e-6 relative of ZBL below R_a; strictly decreasing below R_b | **PASS.** Max relative deviation 4.4e-16; all five strictly decreasing |
| **2. near-equilibrium invariance** | all 40 Phase 0 energies (Al defects at 108–864 atoms, both cell modes; O on/under Ag(111); O₂) within 1 meV of `reports/aerospace_phase0/mace-mpa-0-medium.json` | **FAIL.** 5.4 meV on `al_defects / zero_pressure / 864 / tetrahedral` |
| **3. switching range** | no pair in any Phase 2 structure (59 MP ground states and hull oxides, 20 species pairs) inside its R_b | **PASS.** Tightest is O–V at 1.610 Å against R_b = 1.533 Å (mp-aaaablkh), margin 5% |

Switching ranges (Å):

| pair | R_a | R_b |
|---|---:|---:|
| Al–Al | 0.968 | 1.694 |
| Al–O | 0.748 | 1.309 |
| Ag–O | 0.844 | 1.477 |
| Ag–Ag | 1.160 | 2.030 |
| O–O | 0.528 | 0.924 |

The O–O R_b sits below the O₂ bond, and gate 2's O₂ binding value is among the 40 compared.

## Gate 2 diagnosis

`scripts/aerospace_stage1_gate2_diagnosis.py` re-ran the 40 Phase 0 energies twice in one process:
engine alone, then engine plus correction.

| comparison | max \|Δ\| | values over 1 meV |
|---|---:|---:|
| engine alone vs Phase 0 reference | **4.88 meV** (the same tetrahedral value) | 1 of 40 |
| engine + correction vs Phase 0 reference | 0.49 meV | 0 of 40 |
| engine + correction vs engine alone, same process | 4.88 meV | 1 of 40 |

- **The engine alone misses by as much as the corrected run did in gate 2.** In this re-run the
  corrected run happened to land on the reference instead.
- **The differences are float32 steps.** 14 of the 40 are bit-identical between the corrected and plain
  runs; the rest differ by multiples of 2⁻¹² eV.
- **Why it happens.** No pair in these cells comes near its switching range, so the correction adds exactly
  zero. The difference comes from the relaxation trajectory amplifying float32 rounding in the engine.
  The 864-atom zero-pressure tetrahedral cell is the most sensitive case.
- **Why the gate failed.** Its 1 meV tolerance sat below a noise floor that had not been measured when it
  was set.

## Open decisions

1. **Gate 2.** Accept the diagnosis and re-specify the gate for any future use, e.g. "corrected − plain
   within the plain-vs-plain spread, measured in the same session", or run the gate in float64? Either
   way, the recorded verdict stays FAIL.
2. **Stage 2** (E_d pilot for Al) is next per the scope. It needs the primary E_d sources read, a
   pre-registration, and a runner decision. Proceed, or stop the track here?
