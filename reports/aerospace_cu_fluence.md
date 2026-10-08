# Cu oxide thickness vs atomic-oxygen fluence, and the EOIM-3 null set

> **DEVELOPMENT / DESCRIPTIVE TIER. No verdict.** Chosen as the working first target by Isac on 2026-10-07,
> development tier, revisitable (open decision 3 of `reports/aerospace_durability_development.md`, provisionally
> answered). No engine was run. Row values and fitted constants stay in the gitignored
> `cache/external/aerospace/cu_fluence_side_by_side.md`; this report carries names, counts and residual summaries only.

Generated 2026-10-08T02:39:40Z by `scripts/aerospace_cu_fluence.py` from the gitignored row table (sha256 `aece86512773b148824f079755ddde87e17e7184fe78e2378b86b74467ca3cfc`).

## The data, and whether it is one dataset

- **de Rooij** (NTRS 19930001392): copper grounding strips from the Ultra-Heavy Cosmic Ray Experiment trays
  (p. 479), oxide thickness by X-ray (TFOS), Auger-XPS depth profile and, for one strip, colour; Table II's
  average is what the source plots. Four strips have a thickness; D01 has none (a silicone-derived oxide).
  The source states +-30% at best (p. 487).
- **Raikar et al.** (NTRS 19930019095): one 68 nm sputtered Cu film on fused silica from experiment A0114, leading-edge
  row 9, tray C9 (pp. 1170, 1177). Its Cu2O thickness is *derived* from profilometry and XRD with theoretical densities.
- **Same hardware? No.** Different experiments (UHCRE trays 1, 2, 6, 7, 10 against A0114's C9), different sample
  forms (grounding strips against a sputtered film), different trays (the nearest in fluence is strip E10 from tray 10;
  Raikar's is tray C9, row 9), and different thickness methods. They share the spacecraft, the six years and the **modelled** fluence-per-location
  scale: neither source measured fluence on its samples. de Rooij's are stated maxima, and Raikar's paper cites no source
  for its value. Raikar also says his result is consistent with de Rooij's [10]. So they are
  two samples, but **not independent confirmation of the fluence scale**.
- **Raikar's film is nearly used up.** 81% of its copper is
  converted, so growth there may be limited by supply, not by transport. It is not a like-for-like bulk-strip point.
  Its Cu2O thickness is 1.79x that of strip E10 at 1.12x the
  fluence, outside the +-30% de Rooij states for his own method, so the two do not agree quantitatively.
- **Not usable as fluence-resolved rows:** the E02 strip, whose fluence exponent is printed "09" (read as 10^9 or 10^19
  only as a labelled inference); the Raikar solid-Cu CuO overlayer (2-3 nm, probably formed after return to Earth).

## Fits (n is 3 to 5; fitted constants are in the gitignored file)

Four forms, each fitted by unweighted least squares: `stated_logarithmic` (2 parameters), `inverse_logarithmic` (2 parameters), `parabolic` (1 parameter), `linear` (1 parameter).
The source states only the first, and gives no constants. "Linear-log" is the same family as the stated form (it is
linear in ln F), so it is not fitted twice; the inverse-logarithmic law, which the source's text names, stands in
as the comparison. The inverse-log fit is done in 1/T, the parabolic and linear fits in T; residuals below are in
thickness.

### V1: de Rooij strips as printed (n = 3, 2.2 decades of fluence)

| form | parameters | n | dof | RMSE (A) | relative RMS | max relative residual | points within the source's +-30% |
|---|---:|---:|---:|---:|---:|---:|---:|
| stated_logarithmic | 2 | 3 | 1 | 6.1 | 1.2% | 1.6% | 3 of 3 |
| inverse_logarithmic | 2 | 3 | 1 | 13.7 | 2.7% | 3.5% | 3 of 3 |
| parabolic | 1 | 3 | 2 | 179.5 | 51.8% | 85.2% | 2 of 3 |
| linear | 1 | 3 | 2 | 240.3 | 64.8% | 98.8% | 1 of 3 |

### V2: with E02 read as 10^19 (an inference) (n = 4)

| form | parameters | n | dof | RMSE (A) | relative RMS | max relative residual | points within the source's +-30% |
|---|---:|---:|---:|---:|---:|---:|---:|
| stated_logarithmic | 2 | 4 | 2 | 37.1 | 16.7% | 28.6% | 4 of 4 |
| inverse_logarithmic | 2 | 4 | 2 | 78.9 | 22.1% | 31.2% | 3 of 4 |
| parabolic | 1 | 4 | 3 | 169.0 | 61.4% | 85.1% | 2 of 4 |
| linear | 1 | 4 | 3 | 222.4 | 74.9% | 99.3% | 1 of 4 |

### V3: V1 plus the Raikar point (n = 4)

| form | parameters | n | dof | RMSE (A) | relative RMS | max relative residual | points within the source's +-30% |
|---|---:|---:|---:|---:|---:|---:|---:|
| stated_logarithmic | 2 | 4 | 2 | 154.1 | 23.2% | 30.3% | 3 of 4 |
| inverse_logarithmic | 2 | 4 | 2 | 151.4 | 19.2% | 30.2% | 3 of 4 |
| parabolic | 1 | 4 | 3 | 187.0 | 46.7% | 82.3% | 2 of 4 |
| linear | 1 | 4 | 3 | 222.8 | 57.3% | 98.6% | 1 of 4 |

### V4: everything (n = 5)

| form | parameters | n | dof | RMSE (A) | relative RMS | max relative residual | points within the source's +-30% |
|---|---:|---:|---:|---:|---:|---:|---:|
| stated_logarithmic | 2 | 5 | 3 | 138.5 | 22.1% | 30.8% | 4 of 5 |
| inverse_logarithmic | 2 | 5 | 3 | 126.4 | 24.9% | 36.0% | 3 of 5 |
| parabolic | 1 | 5 | 4 | 176.7 | 55.3% | 82.3% | 2 of 5 |
| linear | 1 | 5 | 4 | 211.2 | 67.8% | 99.2% | 1 of 5 |

**What this supports.** The two one-parameter forms (parabolic, linear) leave at least one point outside the source's
+-30% in every variant, and their worst-case residual never falls below 82.3%: thickness
rises more slowly than the square root of fluence over this span. The two-parameter forms put every point within the source's
+-30% in: the stated form, V1_as_printed, V2_E02_read_as_1e19; the inverse-log form, V1_as_printed. With
1 to 3 degrees of freedom a small residual mostly counts parameters; it is not evidence for the form. They
**cannot be separated from each other** (their RMSEs differ by at most a factor 2.2 in any variant). Adding the
Raikar point raises the stated form's RMSE from 6.1 A to 154.1 A, because that film does not lie on the
strips' curve. The oxide holds between 2e-05 and
2e-03 of the incident O atoms (the three strips with a readable
fluence, using the source's own Cu2O density and formula weight): almost every atom that arrives does not stay as oxide.

## What the harness cannot do here

Its engines return **static energies**, not oxidation rates. Cu2O growth over years in LEO is a kinetic,
transport-limited process: O adsorption and reflection at hyperthermal energy, diffusion of ions and electrons
through a growing scale, sputtering, and re-oxidation after return to Earth. None of that is a static energy,
and the Phase 0 memo found the engines unusable below about 1.25 A, where impacts happen. **Nothing here
predicts a thickness, and a formation energy for Cu2O would say the oxide is favoured, which the flight data
already show.** The only thing the harness could add is a static input to a kinetic model (for example point-defect
energies in Cu2O). That was not computed, not validated, and is not claimed.

## The null set, and what it can and cannot say

Descriptive only; not a rule.

- **Lewis EOIM-3 (NTRS 19970025577):** 22 flight samples of 12 metals at 60 and 200 C, a stated
  detection limit of <0.1 mg, and a per-sample fluence of 1.64e+20 atoms. **20 are
  stored as upper bounds, 2 as measured** (one at the limit, one a gain). If every incident
  atom stuck, a sample would gain about 4.36 mg, so the limit
  corresponds to **net retention of under 2.3% of incident O atoms**.
- **Beside the Phase 2 oxide formation energies** (per O atom, MP-corrected convention; most negative stable oxide,
  from `reports/aerospace_durability_development.json`):

| material (named) | flight samples | at or under the limit | measured | element: most negative oxide, MP / MPA-0 (eV per O) |
|---|---:|---:|---:|---|
| 6061-T6 Al | 2 | 1 | 1 | Al: Al2O3, -5.711 / -5.712 |
| Titanium | 1 | 1 | 0 | Ti: Ti6O, -6.417 / -6.438 |
| Molybdenum | 2 | 2 | 0 | Mo: MoO2, -3.032 / -3.037 |
| Tungsten | 2 | 1 | 1 | W: WO2, -3.055 / -3.013 |
| Nb-1Zr | 2 | 2 | 0 | Nb: NbO, -4.575 / -4.587 |
| Mo-13Re | 2 | 2 | 0 | Mo: MoO2, -3.032 / -3.037 |
| W/Nb composite | 2 | 2 | 0 | W: WO2, -3.055 / -3.013; Nb: NbO, -4.575 / -4.587 |

  Not mapped (304 stainless steel, Brass, Inconel 718, PWC-11, Udimet 720): the composition is not in the source, or an alloying element has no Phase 2 oxide energy
  (no Fe, Cr, Zr, Re, Zn, Co were computed).

- **What the set shows.** No sample of Al, Mo, Nb, Ti shows a mass gain at or above the limit (Al's one quantified sample is
  a *loss* at the limit); W has one sample that does, at 60 C and not at 200 C, which the source does not explain.
  The most negative oxide energies of the no-gain set run from -6.44 to -3.04 eV per O (MPA-0). Cu (Cu2O,
  -1.90) and Ag (Ag2O, -0.98) are less favoured by 1.1 eV per O or more. Within this set,
  **the oxide formation energy does not order the observed mass change**: 20 of 22 samples are at or under the limit whatever the metal's energy,
  and the one gain is on W (-3.01), whose energy is within 0.02 eV of Mo (-3.04), where none is seen.
- **But the limit cannot see oxide growth, so this is a weak observation.** An O-containing Cu2O film as thick as the LDEF strips
  reached (the three strips with a readable fluence, the source's own density and formula weight), on a 0.713 cm2 Lewis disc, holds
  1.6e-03 to 2.5e-03 mg of oxygen: about
  **41x below the 0.1 mg limit** (and 16x below
  twice the MSFC set's +-0.02 mg). So a null at this limit is what *any* metal that oxidises like Cu on LDEF would give. The data cannot show that
  Al or Ti oxidise less than Cu does; they bound gross uptake or loss, not film growth. The Lewis memorandum's own account (p. 1,
  introduction) is that aluminium and silicon form protective oxides that resist further oxidation and that silver's oxide spalls
  off and is lost. Those are kinetic and mechanical statements the formation energy does not contain, and this report did not test them.
- **Within one experiment** (the MSFC EOIM-3 pure-metal rows, printed uncertainty +-0.02 mg), samples above twice that
  uncertainty, by element: Ag 1 of 1, Au 0 of 1, Cu 1 of 2, Nb 1 of 2, Ni 2 of 2, Ta 1 of 2, V 1 of 1, W 1 of 3.
  Those mass changes are larger than any Cu-like oxide could add, so **they are not oxide growth of that size**; this analysis does not say what
  they are. The two EOIM-3 sets use different hardware and different detection limits, so they are not pooled.
- **Limits of the comparison.** Different fluences (EOIM-3 about 10^20, LDEF 10^19 to 10^22), a single temperature pair, formation
  energy for the *bulk* oxide only, and surface chemistry that the mass limit cannot see: 14 of the 21
  Lewis Auger oxygen-signal readings rose, even where the mass change was below the limit.

## Open decisions

1. **Is Cu2O vs fluence still the first target?** With n of 3 to 5, two non-independent sources and no printed
   constants, it can serve as a descriptive reference but not as a validation target for these engines. This is
   in `HANDOFF.md` as an open decision.
2. **Whether to fetch the *Oxidation of Metals* paper** (Raikar, Gregory, Peters, 1994), the likeliest source of
   more Cu points. It is publisher-copyrighted and was not fetched.
