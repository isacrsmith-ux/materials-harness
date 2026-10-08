# Aerospace literature-and-data session: summary

> **DEVELOPMENT / DESCRIPTIVE TIER. No verdict.** Nothing here licenses a production change. Written 2026-10-07 local (2026-10-08 UTC). Every figure is computed from the committed
> reports and JSON. Row-level flight values stay in gitignored `cache/external/aerospace/`.

## Sources: acquired and dropped

| NTRS id | what it is | outcome |
|---|---|---|
| 19930001392 | de Rooij, Cu and Ag on LDEF | **Ingested.** Cu oxide thickness for 4 strips, fluence for 5. One fluence exponent is printed "09" and is not read. The fit law is a form with **no printed constants**. |
| 19930019095 | Raikar et al., Cu on LDEF A0114 | **Ingested.** The archival version. One Cu film (derived Cu2O thickness), one solid sample (CuO overlayer, probably post-flight). |
| 19930011567 | NASA CR-192306 | **Not a second version of the paper, which the brief said.** It is a grant report that *encloses a copy*. Same numbers (7 of 7 checked). Checked, not ingested, so nothing is double-counted. |
| 19940030882 | Gregory, A0114 final report | **Read; no rows.** Six-page narrative with **no tabulated Ag or Cu rates**. Its follow-on papers are listed as pointers only. |
| 19970025577 | Morton and Ferguson, EOIM-3 (NASA Lewis) | **Ingested.** 12 metals, 22 flight samples, a stated <0.1 mg limit, so 20 stored as **upper bounds**. A different set of samples from the MSFC paper. |
| 20100033233 | Finckenor et al., MISSE 6 | **Ingested** (anodized Al, electroless Ni: optical properties, not thickness). Sn-plated Be-Cu is a MISSE 7 sample here: no result. |
| 20080033099 | Pippin et al., MISSE-3/-4 exposures | **Dropped.** An abstract only (no PDF at NTRS), licence field `OTHER`, no exposure table in it. |
| 20140000657 | Burns et al., MAPTIS | Read for the query plan only. |

## Rows by `quantity_kind` (153 rows from 6 sources; 105 new)

mass_change 60 (20 are upper bounds) · surface_composition 44 · optical_property 18 · oxide_thickness 17 · film_thickness 4 · accommodation 5 · reactivity 5 · exposure_only 0.
Rows pool only within one (kind, quantity, unit), and never measured with upper bound. The Phase 1 rows still rebuild to `b1b352d8…`; the full table is `aece8651…`. All per-source checks passed
(the source's own Pilling-Bedworth relation, Table II averages, printed deltas, 64 of 65 Lewis rows confirmed by OCR). Three source inconsistencies are **recorded, not fixed**.

## Phase B: Cu oxide against fluence (`reports/aerospace_cu_fluence.md`)

- **n is 3 to 5**, not the 5 to 7 the brief expected. The two sources are **not the same hardware** (different experiments, trays and sample forms), but they share the modelled fluence scale, so they are not independent confirmation.
- Four forms fitted. The one-parameter parabolic and linear forms fail (worst residual at least 82%); the two-parameter forms **cannot be separated** (RMSE within a factor 2.2).
  Raikar's point is 1.79x the nearest strip's thickness at 1.12x its fluence, outside the source's stated +-30%, and its film is 81% consumed.
- The oxide holds only 1.7e-5 to 1.7e-3 of the incident O atoms. The harness returns static energies, not rates, so it can say nothing about this growth.
- **The null set is weaker than it looks.** The Lewis upper bounds for the metals Phase 2 covers (Al, Ti, Mo, Nb, W) sit beside oxide formation energies from -3.04 to -6.44 eV per O (MPA-0), so the energy does not order the result. But an oxide as thick as LDEF's Cu holds about 41x less mass than the 0.1 mg limit,
  so *any* metal that oxidises like Cu would give the same null. It shows no gross uptake, not that Al or Ti resist oxidation.

## Phase C: vacancy formation against a PBE population (`reports/aerospace_vacancy_population.md`)

- Reference: Angsten et al. 2014 (CC BY 3.0), **PBE, not experiment**. The NIST handle did not resolve, so the paper's own tables are used. 78 element-structure pairs, the paper's own cells and protocol, both engines.
- **MPA-0 (production): median |engine - ref| 0.095 eV, max 0.653 (fcc Er); 14 pairs over 0.2 eV.** MP-0 (second): median 0.189 eV with a -0.17 eV bias, max 2.272 (fcc Os); 38 over 0.2 eV, mostly 4d/5d metals. The brief's six elements: MPA-0 median 0.083 eV, MP-0 0.078 (with Ti at -0.67).
- Cell convergence moves the six elements by up to 0.095 eV (Ti, MP-0); Al reproduces Phase 0 to 0.0007 eV. Volumes checked against the paper (off by over 10%: fcc Er on both engines, and Cs on MPA-0).
- Migration barriers (stretch, 4 s per element, single-image constrained saddle, **not NEB**): MPA-0 median 0.071 eV over 112 pairs, but 4 negative "barriers" (the method failing). A rough screen only.

## Phases D and E, and the stretch

- **Stage 2 draft (`reports/drafts/`), NOT FROZEN, nothing run.** The "recommended 25 eV" for Al could not be traced: its two references are a textbook and an ASTM standard, both paywalled. The primary electron-irradiation papers (abstract pages) say **16 eV** (and a fitted 19). The draft proposes comparing a sampled minimum with 16 eV.
  The ZBL swap is nearly inert for E_PKA up to 36 eV (turning-point shift at most 0.011 A), so Stage 2 tests the engine's own wall. The pilot is 9.0 to 13.5 h of single-process time, over the 2 h gate. Al is not in Nordlund's arc-dpa table.
- **MAPTIS plan** written from the 2013 NTRS presentation, which says nothing about cost or terms. Go/no-go: under about 30 usable rows, drop MISSE.
- **T-phase stretch:** both papers read (CC BY, via Europe PMC); they cite Bergman, Waugh and Pauling (1957). **Materials Project has no Mg32(Zn,Al)49**, so there is no reference to compare an engine value with, and none was computed.

## What I did not do, and why

- **MAPTIS/MISSE:** no login, no network request, no credentials. (Your instruction.)
- **Bot checks:** the IOP PDF, ScienceDirect, ORNL, Wiley and IAEA CascadesDB all returned bot challenges or 402/403. **None was bypassed**, so the JNM review came from the author's copy, CascadesDB's Al coverage and licence are unknown, and OSTI's rate limit was not hammered.
- **Locked data:** OQMD was not queried (its local copy contains the locked held-out half). The bundle, registry, locked sets, `harness/predict.py` and settings tags are untouched.
- **No E_d MD, no freeze, no engine run beyond Phase C and a 251-point Al-Al dimer curve** for the turning-point table.
- **Gate 2** stays FAIL; **no flight value** is committed; **no figure written from memory**. A script found and removed three of my own committed literals (a script, a test and one aggregate).
