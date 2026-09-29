# Aerospace durability — Phase 0 feasibility memo

**Written 2026-09-29 (UTC). Evidence tier: none — this is a capability check on six textbook cases, not
a test of anything the product does.** It decides what Phase 2 may honestly claim.

**Question.** Can `mace-mpa-0-medium` (production engine) and `mace-mp-0-medium` (second engine),
used the way this harness already uses them, compute anything relevant to atomic-oxygen (AO) erosion
and radiation damage of light metals?

**Answer in one line.** They can compute *static, near-equilibrium* energies — vacancy and interstitial
formation energies, and oxygen site preferences on a metal surface — and the production engine does so
well enough for a descriptive tier. Neither engine can be trusted at the short interatomic separations
that collision cascades and hyperthermal impacts produce. **Recommendation: (a), restricted as set out
below, with the dynamic half of the question returned to you as (b).**

Every computed number below is in `reports/aerospace_phase0/<engine>.json`, produced by
`scripts/aerospace_phase0.py`. Every reference number was read from the primary source on 2026-09-29
(UTC); provenance is at the end.

---

## What was run

| case | set-up | reference protocol |
|---|---|---|
| Al vacancy, ⟨100⟩ dumbbell, octahedral and tetrahedral self-interstitials | fcc Al, conventional 3³ … 6³ supercells (108 … 864 atoms); both fixed bulk cell and zero-pressure cell relaxation | Hood, Kent & Reboredo, PBE in 7³ cells, zero-pressure enthalpies (their Table I) |
| O on Ag(111), 0.25 ML: on-surface fcc hollow vs sub-surface octahedral | 2×2, five-layer slab, 15 Å vacuum, O on one side, bottom two layers fixed | Li, Stampfl & Scheffler, GGA, same slab set-up (their Table I and §III A) |
| O₂ binding energy per O atom | isolated O₂ relaxed in a 15 Å box | same paper, GGA and experiment |
| close approach: Al–Al, Al–O, Ag–O, Ag–Ag dimers, 0.2–3.0 Å | single points, E(r) − E(isolated atoms) | ZBL universal screened repulsion, constants from the LAMMPS `pair_zbl` documentation |

The engines ran on CPU through `harness.engine.get_calculator`, with the harness's `fmax` of 0.01 eV/Å.
Each engine used its own compute config: float32 for MPA-0, per `config/compute-mace-mpa-0-medium.json`,
and float64 for MP-0. Every relaxation converged. Wall time was 12 min (MPA-0) and 18 min (MP-0).

## Results

### 1. Point defects in Al — converged cell (6³, 864 atoms), zero pressure

| quantity (eV) | MPA-0 | MP-0 | PBE, Hood et al. (7³) | DMC, Hood et al. | experiment, as tabulated by Hood et al. |
|---|---:|---:|---:|---:|---|
| vacancy formation | **0.678** | 0.479 | 0.67 | 0.67 | 0.67(3), 0.67, 0.66(2) |
| ⟨100⟩ dumbbell | 2.160 | 1.677 | 2.70 | 2.94 | 3.0, 3.2(5) |
| octahedral | 2.360 | 1.870 | 2.91 | 3.13 | — |
| tetrahedral | 2.676 | 2.114 | 3.23 | 3.56 | — |
| octahedral − dumbbell | **0.200** | 0.193 | 0.21 | 0.19 | — |
| tetrahedral − dumbbell | **0.516** | 0.437 | 0.53 | 0.62 | — |

What this shows:

- **The vacancy is right on MPA-0.** 0.678 eV against 0.67 eV (PBE, DMC and experiment). MP-0 is 0.19 eV low.
- **The interstitial ordering is right on both engines**: dumbbell < octahedral < tetrahedral. That is the
  ordering Hood et al. and the experiment they cite report.
- **MPA-0 gets relative interstitial energies right to 0.02 eV, but every absolute interstitial energy is
  0.54–0.55 eV too low.** The error is almost a constant offset. It is not scatter.
- **MP-0 is worse in absolute terms.** The dumbbell is 1.02 eV low.
- **Size convergence** (JSON, `by_mode.zero_pressure`) holds within 0.02 eV from 256 atoms upward for
  every defect. The fixed-cell numbers approach the zero-pressure ones as the cell grows: at 864 atoms the
  dumbbell is 2.173 vs 2.160. Hood et al.'s own 4³ PBE tetrahedral value (3.53 vs 3.23 at 7³, their
  Table II) is a reminder that small DFT cells are not converged either. Our comparison uses their 7³
  values.
- The symmetric octahedral and tetrahedral starts stay where they are (drift < 10⁻⁵ Å). These are
  constrained energies, as in the reference, not proven minima.

### 2. Oxygen on and under Ag(111), 0.25 ML

| quantity (eV) | MPA-0 | MP-0 | GGA, Li et al. | experiment |
|---|---:|---:|---:|---:|
| E_ad, O on-surface fcc hollow, vs free O atom | 3.617 | 2.993 | 3.52 (quoted from their ref. 34) | — |
| E_ad, O sub-surface octahedral, vs free O atom | 3.024 | 2.416 | 2.86 (Table I; the text on p. 3 says 2.85) | — |
| **on-surface minus sub-surface** | **0.593** | **0.577** | **0.66** | — |
| O₂ binding energy per O atom | 3.142 | 2.763 | 3.16 | 2.56 |

What this shows:

- **Both engines get the site preference right** (on-surface favoured at low coverage), and its size to
  within 0.07–0.08 eV. That relative number does not depend on the free-O-atom energy.
- **Absolute adsorption energies on MPA-0 are within 0.1–0.2 eV of GGA.** MPA-0's O₂ binding (3.14 eV) also
  reproduces the GGA overbinding (3.16 eV) rather than experiment (2.56 eV). That is expected of a model
  trained on PBE, and it means **MPA-0 inherits GGA's O₂ error**. Li et al. show that error is large
  enough to flip whether sub-surface O is stable relative to O₂.
- **MP-0 underbinds everything by about 0.6 eV,** O₂ included. Its errors partly cancel against O₂, not
  against the free atom.
- **This contradicts the phase prompt's example** ("this engine has no way to represent chemisorption").
  At the static level it can, and does so about as well as the GGA it was trained on.

### 3. Close approach — the part that matters for cascades and AO impacts

E(r) − E(atoms) against the ZBL screened nuclear repulsion:

| pair | ratio MLIP / ZBL at 0.5 Å (MPA-0 / MP-0) | ratio at 1.0 Å (MPA-0 / MP-0) | pathology |
|---|---:|---:|---|
| Al–Al | 0.14 / **−0.11** | 0.46 / 0.09 | **MP-0 is attractive (negative) from 0.5 to 0.9 Å.** MPA-0 is non-monotonic between 0.8 and 1.0 Å (19.9 → 21.0 eV), a spurious attractive force. |
| Al–O | 0.24 / 22.5 | 0.37 / 0.49 | MP-0 blows up to 8×10⁵ eV at 0.2 Å. MPA-0 is 4× too soft. |
| Ag–O | 0.15 / 0.32 | 0.54 / 0.48 | Both too soft by 2–7×. |
| Ag–Ag | 0.06 / 0.08 | 0.16 / 0.29 | MP-0 is non-monotonic between 0.8 and 1.0 Å. Both are 3–15× too soft. |

- **Neither engine is usable below about 1.25 Å.** Short-range repulsion is too soft by factors of 2–15. One
  engine has a collapse hole for Al–Al, and both have non-monotonic regions.
- **Consequence:** in any process that pushes pairs into this region (collision cascades, sputtering,
  hyperthermal O impact), atoms would pass through each other or bind spuriously.
- **This is the known failure** of general-purpose MLIPs that the phase prompt anticipated. The Al work
  it names (arXiv:1904.00360) fixes it by blending ZBL into the potential below its nearest-neighbour
  switching range (1.2–2.0 Å chosen for cascades, their p. 2).

### 4. Oxide-phase formation energies — not re-tested here, already known to be fragile

Oxide formation energies need an oxygen reference. The round-2 Phase 0 audit
(`reports/phase0/phase0_report.md`, the mp-aaaaatej rows) recorded that MP-0 **collapses solid O₂** (MP's O
hull vertex) on every rung of the relaxation ladder, so oxide targets referenced to it went unscored.
Section 2 shows MPA-0 reproduces the GGA O₂ molecule. A usable oxide formation energy in this domain
therefore means one of two things:

- a hull built on MP's own corrected energies (the harness's existing mode, subject to the OQMD-style
  convention caveats); or
- an O₂-molecule reference that carries GGA's O₂ overbinding.

Neither was measured against experiment here.

## What the engines get right, get wrong, and cannot attempt

| | MPA-0 (production) | MP-0 |
|---|---|---|
| **right** | vacancy formation in Al; the ordering and relative energies of self-interstitials; O site preference on Ag(111); absolute O adsorption and O₂ binding at GGA quality | interstitial ordering; O site preference |
| **wrong** | absolute interstitial formation energies (−0.55 eV, systematic); inherits GGA's O₂ overbinding (+0.58 eV/atom vs experiment) | vacancy (−0.19 eV); dumbbell (−1.0 eV); all O binding about 0.6 eV weak |
| **cannot attempt** | anything below about 1.25 Å: cascades, sputtering, AO impact dynamics; also anything kinetic (oxide growth, spallation, flux, temperature dependence) — a static energy is not a rate | same, with an Al–Al collapse hole |

## Recommendation

**(a), restricted: usable at a descriptive tier, production engine only.**

Allowed:

- defect formation energies (vacancy; interstitials only as **relative** energies, or with the ~0.55 eV
  offset stated wherever an absolute is shown);
- O adsorption-site energetics on metal surfaces;
- bulk oxide formation energies on the harness's MP-corrected hull convention.

MP-0 may appear alongside for contrast. It must not carry a defect number on its own.

**(b) for everything the flight data actually measures.**

- AO erosion yield, reactivity and accommodation numbers are outcomes of impact dynamics, oxide growth and
  spallation kinetics. No static energy computes them.
- Radiation damage needs cascade MD.
- Both require molecular dynamics with a potential validated at short range (ZBL-corrected, as in
  arXiv:1904.00360). The harness has neither the MD machinery nor such a potential.
- **Out of scope as built; returned to you, not bolted on.**

**What this means for Phase 2.** The Phase 2 table can put static quantities next to flight numbers.
It cannot claim that one predicts the other:

- the flight rows cover a handful of metals;
- each metal is measured under its own exposure conditions;
- the causal chain from a vacancy energy or an adsorption energy to a mass loss runs through kinetics
  these engines do not model.

Any agreement or disagreement in that table is anecdote, and the report must say so.

---

## Provenance of reference values (all read 2026-09-29 UTC; none redistributed)

Page and PDF captures are kept under `cache/external/aerospace/provenance/` (gitignored). Only values and
locators are reproduced here; no text or table is copied.

| source | artefact | retrieved (UTC) | licence / terms as read | sha256 | used for |
|---|---|---|---|---|---|
| R. Q. Hood, P. R. C. Kent, F. A. Reboredo, *Phys. Rev. B* **85**, 134109 (2012) | arXiv:1210.5489 (latest version at `arxiv.org/pdf/1210.5489`, abstract page lists v1) | 2026-09-29T01:35:56Z | arXiv non-exclusive distribution licence 1.0 (`arxiv.org/licenses/nonexclusive-distrib/1.0/`) | PDF `8cdbb0e6e6cc1d0a2bfe03eab17a9c176318b507a746a3d7aa094b7263c7aec9` | Al defect PBE, DMC and experimental values: Table I (p. 11), Table II (p. 12) |
| W.-X. Li, C. Stampfl, M. Scheffler, *Phys. Rev. B* **67**, 045408 (2003) | arXiv:cond-mat/0302122 v1 | 2026-09-29T01:31:45Z | arXiv licence field: `assumed-1991-2003` | PDF `d9b27fd686423c92888fb413eac0973d4440384eaddebc9131e586e3240ecec5` | O/Ag(111) set-up (§II), Table I (p. 4), on-surface values and O₂ binding (p. 4 text) |
| Hao Wang, Xun Guo, Linfeng Zhang, Han Wang, Jianming Xue, "Deep learning inter-atomic potential model for accurate irradiation damage simulations", arXiv (submitted 2019-03-31) | arXiv:1904.00360 (latest; abstract page lists v1, v2) | 2026-09-29T01:30:51Z | arXiv non-exclusive distribution licence 1.0 | PDF `b19f4beb43695bbc8ab39d411bc715f78f78fe7ba401f69e1957c6fcd059fa73` | methodology only: ZBL blending and switching range (pp. 1–2). Its Table I labels Hood et al.'s values "DFT"; we cite Hood et al. directly instead. |
| LAMMPS documentation, `pair_style zbl` | `docs.lammps.org/pair_zbl.html` | 2026-09-29T01:32:37Z | "© Copyright 2003-2026 Sandia Corporation"; only the published formula constants are used (facts, not text), and the page cites Ziegler, Biersack & Littmark, *The Stopping and Range of Ions in Matter* (1985) | page `341e6097d16691f17339316ffe1df6e672f3fb093c9c7c96f27a4e715b3bdf6a` | ZBL screening constants in `scripts/aerospace_phase0.py` |

The arXiv abstract page for 1904.00360 carried no journal reference on the day it was read.

## Open decisions

1. **Accept recommendation (a)-restricted for Phase 2?** Or treat the dynamic half as the real question,
   in which case Phase 2 is of limited value and the next step is scoping (b): an MD-with-ZBL tool, which
   I have not started.
2. **Interstitial offset.** Report MPA-0 interstitials as relative energies only, or as absolutes with the
   measured −0.55 eV offset stated beside them?
