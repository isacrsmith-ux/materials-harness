# Data provenance, licences and retrieval

**No source dataset is redistributed by this project.** Structures, energies and convex hulls are
downloaded into `cache/external/`, which is gitignored. Model checkpoints are downloaded into
`models/`, which is gitignored. What this repository contains is code, configuration, aggregate
results, and WBM material identifiers.

Every licence below was read from the source itself; `reference_data/SOURCES.md` records the date
each was checked and also the sources that were **rejected** for licence reasons, so the same dead
ends are not re-explored.

## Datasets the round-4 work depends on

| dataset | role | licence | redistributed here? |
|---|---|---|---|
| **WBM** | the candidate pool: every structure in the round-4 draws | see Matbench Discovery data files | **No** — identifiers only |
| **Matbench Discovery** | the WBM summary and structure files actually consumed | **CC BY 4.0** (data files); MIT (repository) | **No** |
| **Materials Project** | convex hull references | **CC BY 4.0** | **No** |
| **MPtrj** | training data of both engines; not used by this project | MIT | **No** — not used |
| **MACE-MPA-0 medium** | primary engine checkpoint | MIT (code and checkpoint) | **No** |
| **MACE-MP-0 medium** | second engine checkpoint | MIT (code and checkpoint) | **No** |

### Citations

- H.-C. Wang, S. Botti, M. A. L. Marques, "Predicting stable crystalline compounds using chemical
  similarity", *npj Computational Materials* **7**, 12 (2021). — the WBM dataset.
- J. Riebesell et al., "Matbench Discovery", *Nature Machine Intelligence* (2025), arXiv:2308.14920.
  Data files: **doi:10.6084/m9.figshare.22715158**.
- A. Jain et al., "The Materials Project: A materials genome approach to accelerating materials
  innovation", *APL Materials* **1**, 011002 (2013).
- I. Batatia et al., "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and
  Accurate Force Fields", *NeurIPS* (2022); MACE-MPA-0 / MACE-MP-0 foundation checkpoints.

### Why identifiers are present but data is not

Files under `data/` contain WBM material identifiers derived from the Matbench Discovery data files,
which are CC BY 4.0 — attribution-only, so identifiers may be redistributed with the citation above.
The structures and energies themselves are not redistributed. This distinction is recorded in
`NOTICE`.

## Retrieval — reproducing the inputs

The engines are pinned by checkpoint SHA-256 and verified on every load, so a silently different
checkpoint cannot produce results under the same settings tag.

```bash
# 1. Engines (downloaded to models/, gitignored, SHA-256 verified on load)
python -m harness models fetch mace-mpa-0-medium   # sha256 75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638
python -m harness models fetch mace-mp-0-medium    # sha256 01bfe22100139f424713cf921144e5509cbe353d67aa9fa1be9c6e1e0ed35845

# 2. WBM summary + structures (downloaded to cache/external/wbm/, gitignored)
#    Source: Matbench Discovery, doi:10.6084/m9.figshare.22715158
#      2023-12-13-wbm-summary.csv.gz
#      2022-10-19-wbm-init-structs.jsonl.gz
#      2022-10-19-wbm-computed-structure-entries.jsonl.gz
python -m harness data fetch wbm

# 3. A Materials Project API key is needed only for the reference-data and hull work,
#    not for the round-4 analyses. Put it in .env as MP_API_KEY (never committed).
```

## External validation sources (campaign 2026-09-24)

Every entry below was read **from the source itself on 2026-09-24**, in-session; nothing is written from
memory. Page captures (with the sha256 prefixes quoted) are kept under `cache/external/oqmd/provenance/`,
which is gitignored. **No row of any of these sources is redistributed** — the campaign commits ids,
hashes, provenance and aggregates only.

| source | exact artefact | retrieved (UTC) | licence, as read that day | sha256 |
|---|---|---|---|---|
| **OQMD** | v1.8 bulk MySQL dump `qmdb__v1_8__022026.sql.gz` ("Database updated on: February, 2026"), from `https://static.oqmd.org/static/downloads/`, linked from `https://oqmd.org/download/` | page 2026-09-24T19:39:41Z; file verified 2026-09-24T19:56Z | **CC BY 4.0** — "The data in OQMD is licensed under CC-BY 4.0", stated on the home, documentation and download pages (captures `948dea89…`, `1735b99a…`) | `66c3f1b752d4043b579e84485fe6c8e1913af52f41fc1a949c598e94b6646333` (21,034,479,961 bytes; size and md5 `qQUGz1mu2YaF/LID0z0+bQ==` match the storage bucket's published headers) |
| **Matbench Discovery MP snapshot** | `2023-01-10-mp-energies.csv.gz`, figshare file 49083124 of doi:10.6084/m9.figshare.22715158 (record v38) — reused from the existing cache | 2026-09-24T20:09:26Z (record read via the figshare API, capture `dbf622ea…`) | **CC BY 4.0** (record licence field) | `046814c1c556e0e5c9531df00650c56cb197b2c01ba22695a46efcfb4876a4a8`; md5 `888579e2…` equals figshare's published md5 |
| **WBM** | the files already in `cache/external/wbm/` (see above) | — | as above | as above |
| **Materials Project** | MP2020-corrected GGA/GGA+U thermo documents via `mp_api` with the key in `.env` (never printed) | at query time; database version recorded in each report | **not re-read on 2026-09-24**: `materialsproject.org/about/terms` returned HTTP 403 behind a Cloudflare bot check, which was not bypassed. MP's own AWS Open Data registry entry (capture `21b5631e…`, read that day) names "Materials Project Terms of Use" as the licence. The CC BY 4.0 statement in `NOTICE` rests on the earlier reading recorded in `reference_data/SOURCES.md`. | — |
| **protostructure labels** | `matbench_discovery.structure.prototype.get_protostructure_label` from github.com/janosh/matbench-discovery at commit `71633e8bdfdfd41d56d64b1d777e5686d9eda3ec` (not in any PyPI release; the repository is MIT), run in an ephemeral Python 3.14 env via `./uvw run --with`, never installed into `.venv` | 2026-09-24 | MIT (repository) | commit hash |

Citations, as given on `https://oqmd.org/documentation/publications` (capture `67c2ac99…`):

- J. E. Saal, S. Kirklin, M. Aykol, B. Meredig, C. Wolverton, "Materials Design and Discovery with
  High-Throughput Density Functional Theory: The Open Quantum Materials Database (OQMD)", *JOM* **65**,
  1501–1509 (2013). doi:10.1007/s11837-013-0755-4
- S. Kirklin, J. E. Saal, B. Meredig, A. Thompson, J. W. Doak, M. Aykol, S. Rühl, C. Wolverton, "The Open
  Quantum Materials Database (OQMD): assessing the accuracy of DFT formation energies", *npj Computational
  Materials* **1**, 15010 (2015). doi:10.1038/npjcompumats.2015.10

**Population figures.** oqmd.org's home page read on 2026-09-24 states 1,407,395 materials, and the
OPTIMADE endpoint reported `data_available: 1407395` the same day; the page's embedded metadata separately
says "600,000+". Neither is used as a denominator: every count in the OQMD reports is computed from the
pinned dump.

**Why not OPTIMADE.** It serves the live database without a version pin and exposes only a
`calculation_id`, not the DFT settings; the v1.8 dump is pinned and carries each calculation's settings.

## Aerospace durability sources (2026-09-29)

Every entry was read **from the source itself on 2026-09-29 (UTC)**, in-session. PDFs, NTRS metadata
captures and the transcription sit under `cache/external/aerospace/`, which is gitignored. **No row is
committed.** `reports/aerospace_phase1_ingest.json` carries hashes, counts and check results only.

### Flight data actually used

The "licence" column is NTRS's `copyright.determinationType` field, read from `ntrs.nasa.gov/api/citations/<id>`
that day. Every entry also had `containsThirdPartyMaterial: false`.

| source | NTRS id | retrieved (UTC) | licence as read | sha256 | what it gives |
|---|---|---|---|---|---|
| Whitaker, "Selected results for metals from LDEF experiment A0171" (MSFC, 1992) | 19930001391 | 2026-09-29T02:10:23Z | GOV_PUBLIC_USE_PERMITTED | `5dbe1f283037b0daf7651008f21762d0576dd263fd9c8f8c07ab59f77a5adcd8` | Table II (p. 471): AO accommodation and reactivity for **5 samples**: Ag disk, Ag ribbon (thermally isolated), Cu, Mo, Ti 75A. Duration 5.8 years (p. 467). **No fluence, no Al, no Al-Li.** |
| Vaughn, Linton, Finckenor, Kamenetzky, "Evaluation of space environmental effects on metals and optical thin films on EOIM-3" (MSFC, 1995) | 19950021220 | 2026-09-29T02:12:22Z | GOV_PUBLIC_USE_PERMITTED | `763ace569f26f11a70683cf21da515e9021e5f7a5889b65dca3320d712298add` | Table I (p. 1056): Δm and Δm/A for 99.9999% pure Cu, Au, Ni, Nb, Ag, Ta, W and V, and the Al-Li alloys 2090 and Weldalite, by tray (60 / 120 / 200 °C / passive). Fluence 2.2×10²⁰ atoms/cm² (p. 1054); 0.71 cm² exposed area for the pure metals (p. 1055). |
| Linton, Vaughn, Finckenor, Kamenetzky, "Orbital atomic oxygen effects on materials: an overview of MSFC experiments on the STS-46 EOIM-3" (MSFC, 1995) | 19950021216 | 2026-09-29T02:10:23Z | GOV_PUBLIC_USE_PERMITTED | `9b13c44909bc310ac2c1af5d6f29fed149c5a0b8398a65122453c8c336bdd8c3` | Context only. It describes the single-crystal Ag/Cu at [100]/[111] and 60/120/200 °C (PDF p. 2), but **gives no numbers for them**. They are also absent from 19950021220's Table I. |

**How values were read.** The text layers are 1990s OCR and drop or garble many cells. Every value was
therefore transcribed from the page image and recorded as printed with its locator
(`cache/external/aerospace/transcription.json`). `scripts/aerospace_ingest.py` then refuses to write unless:

- every PDF hash matches;
- where OCR survives, it agrees with the transcription (34 of 48 values confirmed; 14 dropped by OCR);
- the EOIM-3 pure-metal Δm/A is reproduced by Δm / 0.71 cm² within the print's rounding (15/15).

**Caveats that travel with these rows:**

- **Ti 75A accommodation is printed "9/2 x 10⁵"** and cannot be read unambiguously. Its value is left null.
- **EOIM-3 Al-Li areas.** The implied exposed areas (Δm ÷ Δm/A) are 3.29 / 3.27 cm² for 2090 and 1.67 cm² for
  Weldalite. Neither matches the covers described on p. 1055 (half-covered or "D"-ringed 2.54 cm discs). The
  per-area values cannot be reconstructed from the text.
- **Al-Li confound.** The source attributes the Al-Li mass loss to lithium loss, not oxidation (p. 1057).
  Weldalite flew only on passive trays and 2090 only on heated ones, so alloy and temperature are confounded.
- **EOIM-3 Δm precision is ±0.02 mg,** per the Table I header. Several pure-metal changes are within 1–2σ of zero.
- **EOIM-3 text vs table.** The text says Ag also flew on the 200 °C tray (p. 1055), but Table I has no
  such row.
- **LDEF A0171 prints no fluence.** Its reactivities (cm³/atom) are the author's normalisation and assume
  the highest oxide formed (p. 467).
- **Different quantities, not comparable.** LDEF reports reactivity/accommodation; EOIM-3 reports raw mass
  change. They are different quantities under very different exposures (5.8 years vs 42 hours) and must
  never be pooled.

### Sources checked and not usable

| source | checked (UTC) | outcome |
|---|---|---|
| MISSE database, `materialsinspace.nasa.gov` | 2026-09-29T02:09:16Z | **Host does not resolve** (curl: could not resolve host). |
| MAPTIS, `maptis.nasa.gov` (home of MISSE data) | 2026-09-29T02:09:16Z, capture `5cd7bc88…` | **Registration required, and paid for non-NASA users.** The home page says that from January 2026 "all non-NASA users and NASA programs must pay based on the number of registered users", and that unaffiliated accounts "will be temporarily locked until payment is arranged". It also showed a system-outage notice. **Not registered; source stopped.** |
| de Groh, "NASA Glenn Research Center's Materials International Space Station Experiments (MISSE 1-7)" | NTRS 20090005995, sha256 `1ba550c4…`, PUBLIC_USE_PERMITTED | Glenn's share only: "39 individual materials flight experiments (>540 samples)" (PDF pp. 5, 44), essentially polymers, coatings and thin films. **No bare-metal erosion data.** |
| de Groh, "MISSE: Overview, Accomplishments and Future Needs" (2014) | NTRS 20150000889, sha256 `9fd6966b…`, PUBLIC_USE_PERMITTED | "NASA Glenn has flown 41 experiments with 630 samples". No MISSE-wide total or metal fraction is given. |
| "Atomic Oxygen Erosion Data from the MISSE 2-8 Missions" (2019) | NTRS 20190025445, sha256 `d203dd4b…`, PUBLIC_USE_PERMITTED | 71 materials, **all polymers / carbon**. |
| Lan, Smith, Cross, LANL O-atom facility, coatings (1988) | NTRS 19890003221, sha256 `a147a0a3…`, GOV_PUBLIC_USE_PERMITTED | Ground-based fluence lifetimes of **coatings** (Teflon, Al₂O₃, SiO₂, silicone). No metal-erosion data. |
| Fromhold, "Experimental results on atomic oxygen corrosion of silver" (1988) | NTRS 19890012367, sha256 `69c4d64c…`, GOV_PUBLIC_USE_PERMITTED | Ground-based (plasma asher, **not the LANL facility**) Ag oxide-growth kinetics, 0–70 °C, Auburn University / MSFC. No flight comparison. |
| Cross, Lan, Smith, Whatley, BN and Si₃N₄, ground vs flight (1990) | NTRS 19910009833, sha256 `9a5b75a7…`, GOV_PUBLIC_USE_PERMITTED | The only ground-vs-flight comparison of the three. It is **qualitative**, and the materials are BN and Si₃N₄, not metals. |

**MISSE's metal fraction is unknown.** Public NASA documents cover only Glenn's experiments (630 samples),
which are polymer- and coating-dominated. The MISSE-wide population and its metal fraction could not be
read from any accessible source, so no such figure is written here.

### Literature session additions (read 2026-10-08 UTC; 2026-10-07 local)

Every entry was read **from the source itself in-session**. Licence fields were read from
`ntrs.nasa.gov/api/citations/<id>` (`copyright.determinationType`, `containsThirdPartyMaterial`) at the time
shown; every record had `containsThirdPartyMaterial: false`. PDFs, API captures (`<id>.meta.json`), the
transcription (`transcription_v2.json`) and the row table (`durability_rows_v2.csv`) sit under
`cache/external/aerospace/`, gitignored. **No row is committed.** Aggregates and check results are in
`reports/aerospace_phase1_ingest.json` (regenerated, still without values).

| source | NTRS id | record read / PDF fetched (UTC) | licence as read | sha256 | what it gave |
|---|---|---|---|---|---|
| de Rooij (ESA/ESTEC), "Some results of the oxidation investigation of copper and silver samples flown on LDEF", *LDEF Materials Workshop 1991, Part 2* (NASA LaRC, listed 1992-09-01), printed pp. 479-490 | 19930001392 | 02:14:21Z / 02:14:52Z | GOV_PUBLIC_USE_PERMITTED | `cdb2b7b4761e3306e8732017c2995f237192befc5f06ea57fc7bb23fb6e8eb46` | Table I (fluence for 5 Cu grounding strips) and Table II (oxide thickness by X-ray, Auger-XPS, colour, average; 4 strips). The stated thickness-fluence law is a form only (Fig. 8): **its constants are not printed**. Ag results are qualitative. |
| Raikar, Gregory, Christl, Peters, "The interaction of atomic oxygen with copper: an XPS, AES, XRD, optical transmission and stylus profilometry study", *LDEF - 69 Months in Space, Part 3: Second Post-Retrieval Symposium* (NASA LaRC, listed 1993-04-01), printed pp. 1169-1186 | 19930019095 | 02:14:22Z / 02:14:54Z | GOV_PUBLIC_USE_PERMITTED | `117fe74285269ab69289b59308c364f4f03dd1fcc57595b35e89ebbdb0303613` | **The archival version.** One Cu thin film and one solid OFHC Cu sample, flown on the leading-edge C9 tray (row 9, A0114): film thickness before and after, derived Cu2O and Cu-consumed thickness, CuO overlayer, fluence for row 9. |
| Gregory (PI), "Analysis of surfaces from the LDEF A0114, phase 2", NASA CR-192306, Univ. of Alabama in Huntsville semi-annual report, 1 Mar - 31 Aug 1992 (NAG1-1228) | 19930011567 | 02:14:22Z / 02:14:55Z | GOV_PUBLIC_USE_PERMITTED | `1a8bea5dfa39b7635574087fcc7ba1761115c1361bb0685b94ea2a89d9e919d4` | **Not a second version of the paper.** The brief named this id as one; NTRS says it is a grant report that *encloses a copy* of the Raikar paper. Same sample, same numbers (7 of 7 key numbers found in both, checked). Not ingested, so nothing is double-counted. |
| Gregory, "Results from LDEF experiment A0114: the interaction of atomic oxygen with materials surfaces at orbital altitudes", NASA CR-196016, final report, June 1994 | 19940030882 | 02:14:23Z / 02:14:56Z | GOV_PUBLIC_USE_PERMITTED | `b94ce803b83ceae7c2bbfddaeff871bac477395d918b1d54a0bbd04751dcdb18` | Six-page narrative. **No tabulated oxidation rates for Ag or Cu.** It states qualitatively that thick oxide films form on copper at 20 C, and lists follow-on papers (below). |
| Morton, Ferguson, "Atomic oxygen exposure of power system and other spacecraft materials: results of the EOIM-3 experiment", NASA TM-107427, NASA Lewis, May 1997 | 19970025577 | 02:14:23Z / 02:14:58Z | GOV_PUBLIC_USE_PERMITTED | `8d916d16f47e09dbbfe97df69d0283b15b932b6ba43b13b4afa13366d4795fa6` | Appendix A mass table (pre, post, change, for 60 C, 200 C and a control) and Table II (stated detection limit, AES oxygen and carbon signal changes, SEM remarks) for 12 metals. **A different set of samples and hardware from the MSFC paper (19950021220).** |
| Finckenor, Golden, Kravchenko, O'Rourke, "Analysis of International Space Station vehicle materials on MISSE 6", National Space & Missile Materials Symposium, Scottsdale AZ, 28 Jun - 2 Jul 2010 (NSMMS report M10-0758) | 20100033233 | 02:14:23Z / 02:14:59Z | PUBLIC_USE_PERMITTED | `cf3bceeea97eebfc86887c3995c828c4178b8edc0859a72642b41d8de0e85a30` | Slides 7 and 9: pre/post optical properties with ESH and AO fluence for anodized Al (6 samples) and electroless Ni (3). Born-digital text layer, not OCR. **Sn-plated Be-Cu is a MISSE 7 sample here: no result.** |
| Burns, Finckenor, Henrie, "MISSE in the Materials and Processes Technical Information System (MAPTIS)", NSMMS 2013 (M13-2718) | 20140000657 | 02:14:24Z / 02:15:01Z | GOV_PUBLIC_USE_PERMITTED | `5086f3fe744bc9aecab7718c3cf23ca3519b643c9a44d6d69e1fb9cddece3c4d` | Read for `docs/methodology/maptis_query_plan.md` only. No flight values ingested. |

**Dropped: Pippin, Normand, Finckenor, "Estimated environmental exposures for MISSE-3 and MISSE-4"**
(NTRS 20080033099, record read 02:14:24Z). The record is an **abstract only** (`downloadsAvailable: false`, no
PDF), its licence field reads `OTHER`, and the abstract prints no per-tray fluence or dose. There is no exposure
table to transcribe, so nothing was acquired. The per-tray record the brief wanted would have to come from the
full paper, which is not on NTRS.

**How values were read.** Scanned sources (de Rooij, Raikar, Morton, CR-192306): from the page images, with a
locator per row, then checked row by row against the OCR text layer (`aerospace_ingest.py`). One of 65 Morton rows
the OCR garbled; the image was unambiguous. The MISSE-6 deck is born-digital, so its text layer is the source;
row alignment was confirmed in layout mode.

**Caveats that travel with these rows:**

- **de Rooij E02 fluence is printed with the exponent "09"** in Table I. It is not read as 10^9 or 10^19; the
  fluence is left null. The probable typo is an inference, not something the source says. Table I also states
  the fluences are maxima, because the strips are not in plane with their trays.
- **de Rooij's D01 strip has no oxide thickness:** the depth profile shows a silicon-oxide contaminant.
- **de Rooij's accuracy statements:** thickness "not better than +-30%", Talystep calibration +-20% (p. 487).
- **Strip-to-tray mapping** (D01 to tray 1, and so on) rests on the matching numerals and on the one explicit
  "tray 10 (E10)". The text does not tabulate it.
- **Raikar's CuO overlayer** (about 2-3 nm on the solid sample) is hypothesised by the authors to have formed
  after return to Earth; de Rooij says the same of his CuO top layer. It is not flight-grown oxide.
- **Raikar internal consistency.** The source's own Table 1 densities reproduce its stated 114 nm and 117 nm
  full-conversion thicknesses, and its 55 / 92 / 13 nm split. Two statements do **not** hold, and are recorded,
  not fixed: the mask-edge step height differs from the film-thickness difference by 2.0 combined sigma although
  the text says they agree, and "40% greater" is 54.9% from the printed thicknesses.
- **Morton's detection limit is "<0.1 mg"** (Table II). The 20 samples with "no detectable change" are stored as
  **upper bounds** equal to that limit, with the measured Appendix A change kept alongside. The largest control
  change in Appendix A is 0.09 mg. Two flight samples are quantified: 6061-T6 Al at 200 C (a loss printed as 0.1
  mg, exactly at the limit) and tungsten at 60 C (a gain of 0.94 mg that its 200 C partner and control do not
  show, unexplained in the summary).
- **Morton's Table II prints identical AES cells for Tungsten and Molybdenum** (O +51/-40, C -77/-85), checked on
  the page image. A duplicated cell is suspected; both are kept as printed and flagged. The AES percentages do
  not say what they are relative to.
- **Brass and titanium flew only at 200 C** in the Lewis set (no 60 C sample).
- **EOIM-3 fluence is printed twice.** The Lewis memorandum gives a preliminary mass-spectrometer value; the MSFC
  paper's value is 4.4% lower. Different samples, so they are not pooled.
- **MISSE-6 quantity labels.** The anodize and electroless-Ni slides print two lines per sample without naming
  them. They are treated as solar absorptance then emittance, which is how the same deck labels its beta-cloth
  slides. That is an inference, flagged on every row.

**Follow-on papers cited by NTRS 19940030882 (pointers only; titles as printed there; not fetched, not verified):**
Raikar, Gregory, Peters, "Oxidation of Copper by Fast Atomic Oxygen", *Oxidation of Metals* 42, 1-15 (1994, "in
press"); Gregory, Christl, Raikar, Peters, "Effects on LDEF Exposed Copper Film, and Bulk", First LDEF
Post-Retrieval Symposium (NASA CP-3134, part 2, pp. 755-762); Peters, Gregory, Raikar, "Changes in Chemical and
Optical Properties of Thin Film Metals Mirrors on LDEF", LDEF Materials Results for Spacecraft Applications
conference (Huntsville, 27-28 Oct 1992); Peters, Gregory, Nag, "Measurements of the Optical Properties of Thin
Films of Silver and Silver Oxide", Third LDEF Post-Retrieval Symposium (1993, "in press"); Gregory, Christl,
Peters, "Measurements of Erosion Characteristics for Metal and Polymer Surfaces Using Profilometry" (CP-3134,
part 2, pp. 723-735). The journal paper is the one most likely to hold more Cu data; it is publisher-copyrighted.


### Stage 2 draft sources (read 2026-10-08 UTC; 2026-10-07 local)

Every entry was read in-session. Captures are under `cache/external/aerospace/ed/` and `.../comparators/`, gitignored. These are for the Stage 2 *draft*
(`reports/drafts/aerospace_stage2_preregistration_DRAFT.md`); no E_d MD was run. "Abstract page only" means exactly that: the full text of the APS papers was not read.

| source | retrieved (UTC) | licence as read | sha256 | what it gave |
|---|---|---|---|---|
| Nordlund et al., "Improving atomic displacement and replacement calculations with physically realistic damage models", *Nat. Commun.* **9**, 1084 (2018), doi:10.1038/s41467-018-03415-5 | article page 02:44:06Z | **CC BY 4.0**, stated on the page | `03222d0373b9e5805d5821b1ecef0ff6ce408489c3e198828689be372aee3c5d` | Definition of E_d used (average threshold displacement energy, citing Nordlund, Wallenius, Malerba 2005). **Al is not in its Table 1.** |
| (same paper, Table 1 page) | 02:44:27Z | CC BY 4.0 | `d676c4a677f2742e4019f7d611dfe12219d3cf1034ed5f74782fe2e325875644` | Table 1: arc-dpa constants and E_d for Fe, Cu, Ni, Pd, Pt, W. |
| Nordlund et al., "Primary radiation damage: a review of current understanding and models", *J. Nucl. Mater.* **512**, 450 (2018), doi:10.1016/j.jnucmat.2018.10.027: the **author's copy** (file `Nor18.pdf`) on the University of Helsinki site (`www.mv.helsinki.fi`, the first author's publications page) | 02:49:02Z (8,161,194 bytes) | **CC BY-NC-ND 4.0**, stated in the PDF's own front matter (open access). Read; **no text reproduced** | `cd1d46eb2a722d5ed7bcb620988bcf12cb529c66c32e5dc352f4b5f61db85702` | Section 2.1: how the threshold displacement energy is defined (per direction, stochastic near threshold, falls with temperature). **No Al-specific E_d**; 25 eV appears only as an assumed input in an ion-mixing table. The publisher's DOI page returned HTTP 403 (a bot check, not bypassed) and the OSTI accepted-manuscript PDF HTTP 429 (too many concurrent downloads), so the author's copy was used. |
| Neely, Bauer, *Phys. Rev.* **149**, 535 (1966), doi:10.1103/PhysRev.149.535 | APS page 02:50:15Z | (c) 1966 American Physical Society. **Abstract page only; the full text was not read.** Values used as facts, text not reproduced | `db8ccb8d8be3392c0ba1e03e7633637ab3716efac2f2bd697f0177352285375c` | Al threshold 16 eV (extrapolating the damage rate to zero, near 8 K, 0.19-1.6 MeV electrons) and an effective 19 eV from a fit. |
| Simpson, Chaplin, *Phys. Rev.* **185**, 958 (1969), doi:10.1103/PhysRev.185.958 | APS page 02:50:14Z | (c) 1969 American Physical Society. **Abstract page only.** Facts used, text not reproduced | `3b144adda75669bdf4a51f37d23e6c6d10c950f8b3ea4842af6988b43abe4c67` | Al threshold 16 eV from damage rates, 0.16-0.40 MeV electrons; the abstract gives no temperature or orientation. |
| Sosin, "Radiation effects in metals at low temperatures", *J. Phys. Soc. Jpn.* **18** Suppl. III, 277 (1963) | 02:45:22Z | not read (journal PDF) | `97371f0e21a1ac131c35377a9d0fbdc3c75d27635b7be41106ae47a3ff5a525f` | Read in full: electron-irradiation recovery in Cu and Al. **Gave no Al E_d**; nothing was taken from it. |
| Qiu, "Orbital-free density-functional theory simulations of displacement cascade in aluminum", arXiv:1709.08288 | 02:49:43Z | not read (PDF only; the arXiv abstract page was not fetched) | `9e9877ae6570d72a5cf9461546ce5a43b500283ccff9c85c718fa4080d7f0989` | Per-direction E_d(Al) from OF-DFT and MD at 100 K in a 32,000-atom cell; **values are in a figure only**. |
| "Effect of crystal orientation on dislocation loop evolution under electron radiation in pure aluminum" (PMC12843142) | 02:49:43Z | **CC BY**, stated on the page | `f1af08cf5915cff8f1965dd69d6032dc9be934394227611fa12b479e38bc2203` | Used only to find refs 27 and 28 (Simpson & Chaplin; Neely & Bauer) and the electron-irradiation directions [110], [111], [310], [100]. Its own value for Al is secondary. |
| OpenKIM item `MO_971738391444_000` (v000, 2NN MEAM, Al-Li; Roy, Dutta, Chakraborti 2021), doi:10.25950/96965eb6, and its LICENSE file | item page 02:51:40Z; LICENSE 02:51:56Z | Authors hold the copyright; **no commercial use without permission**; free for academic use at the user's risk if the 2021 paper is cited. Not an open-source licence | `b91739f08937a4d05b52ea72c1bcf51f64629ea5c70455695620629c184b18c7` | Comparator only; nothing downloaded beyond the item page and licence text. |
| NIST Interatomic Potentials Repository, home page and Al system page (`ctcms.nist.gov/potentials`) | 02:51:04Z; 02:51:26Z | **No licence statement** on the pages read; the home page asks for acknowledgement | `2f227db57e39014dfef5deb33ded09be8d6cbfa494791c9cf0c8887f9419fc75` | Comparator only; no potential downloaded. |

**Not read, and why:** G. S. Was, *Fundamentals of Radiation Materials Science* (Springer, 2016) and Norgett-Robinson-Torrens in the *Annual Book of ASTM Standards* (1975), the two
references behind the "recommended 25 eV" in arXiv:1904.00360 (paywalled); Jung and Ehrhart in Landolt-Bornstein vol. 25 (1991); Lucasson & Walker (1962); Iseler et al. (1966).

**IAEA CascadesDB** (`cascadesdb.iaea.org`) could **not** be read: curl returned HTTP 403 with a JavaScript challenge ("Just a moment ...") and WebFetch returned HTTP 402, both at 2026-10-08T02:51:03Z.
Its Al coverage and licence are unknown; a web-search summary (secondary, unverified) says Al is not among its materials. Nothing was bypassed or downloaded.


### T-phase stretch sources (read 2026-10-08 UTC; 2026-10-07 local)

| source | retrieved (UTC) | licence as read | sha256 |
|---|---|---|---|
| Tunes, Stemper, Greaves, Uggowitzer, Pogatscher, *Adv. Sci.* **7**, 2002397 (2020), doi:10.1002/advs.202002397, full-text XML from Europe PMC (PMC7675061) | 2026-10-08T03:00:24Z | **CC BY 4.0**, stated in the XML | `dec8267687038f4ac11ee5ea76cb1cd604c72127b5f7608492e89bd184da4614` |
| Willenshofer, Tunes, Vo, Stemper, Alfreider, Renk, Greaves, Kiener, Uggowitzer, Pogatscher, *Adv. Mater.*, doi:10.1002/adma.202513450, full-text XML from Europe PMC (PMC13054116) | 2026-10-08T03:00:27Z | **CC BY 4.0**, stated in the XML | `2838724a26f8e56e2dd346f667ae8b80cb40cd4c165c4d00d093fa0adbc5bc6a` |

The publisher's DOI pages returned HTTP 403 with a Cloudflare challenge (03:00:01Z) and were not bypassed. The Materials Project search was made through the harness's cached summary
search (database version as of the query; MP is CC BY 4.0 per `NOTICE`). Two COD queries (03:02Z) returned empty bodies. Nothing from OQMD was read.

### DFT population reference (Phase C)

| source | what | retrieved (UTC) | licence as read | sha256 |
|---|---|---|---|---|
| Angsten, Mayeshiba, Wu, Morgan, "Elemental vacancy diffusion database from high-throughput first-principles calculations for fcc and hcp structures", *New J. Phys.* **16**, 015018 (2014), doi:10.1088/1367-2630/16/1/015018 | landing page `https://doi.org/10.1088/1367-2630/16/1/015018` (resolved to `iopscience.iop.org`), which carries the full text and the appendix tables A.1 (fcc) and A.2 (hcp) | 2026-10-08T02:19:17Z | **CC BY 3.0**, stated on the page: use is allowed with attribution to the authors, the title, the journal citation and the DOI | `a48f8a37d6024ce52f2c9f22b3b966d00aa652f260905686b98288dc1ecca51e` (235,755 bytes) |

- **The NIST dataset (hdl:11256/102) could not be read.** `https://hdl.handle.net/11256/102` returned HTTP 500
  ("cannot be found", 02:18:29Z and 02:19:19Z) and `https://materialsdata.nist.gov/handle/11256/102` returned HTTP
  404 (02:19:17Z). Its licence was therefore **not** read. The paper's own appendix tables, which it says list
  all calculated data, are the reference, and they carry the paper's CC BY 3.0 licence.
- **The IOP PDF endpoint answered with a bot-detection challenge** (02:19:56Z). It was not bypassed. The capture
  is kept as `BLOCKED_iop_pdf_botcheck_*.html` so it cannot be mistaken for the paper.
- **The paper's DFT settings** (what the reference is, not ours): VASP 5.2.2 with MAST and pymatgen; PBE
  exchange-correlation, PAW; first-order Methfessel-Paxton smearing, 0.2 eV, for relaxations; tetrahedron method
  with Bloechl corrections for fixed-ion energies; no spin polarisation except Co, Ni, Mn and hcp Fe; plane-wave
  cutoff 1.5 x ENMAX. Cells: fcc 3x3x3 conventional (108 sites), 4x4x4 Monkhorst-Pack k-mesh; hcp 3x3x2
  conventional (36 sites), 9x9x9 Gamma-centred. Vacancy formation: the defect cell at the fixed volume of the
  relaxed perfect cell, ions relaxed. Stated size-effect error 20-30 meV, k-point error 18 meV for Al (fcc) and 9
  meV for Mg (hcp).

### Reference values used by the Phase 0 feasibility memo

These are journal articles (value and locator only, no text or table reproduced): Hood, Kent & Reboredo,
arXiv:1210.5489; Li, Stampfl & Scheffler, arXiv:cond-mat/0302122; and ZBL constants from
`docs.lammps.org/pair_zbl.html`. Retrieval times, licences as read and hashes are in
`reports/aerospace_durability_feasibility.md`.

## Vendored third-party content, and why it is allowed

Two public-domain sources are vendored verbatim under `reference_data/raw/` so the reference-data
build reproduces without network access. Neither is used by the round-4 work.

| artefact | licence | redistribution |
|---|---|---|
| `NASA-TM-2006-214482_MISSE2_PEACE.pdf` | US Government work, public domain (no third-party copyright marks found in the document) | permitted |
| `raw/cod/*.json` — Crystallography Open Database entries | **CC0 1.0** — "all data in the COD and the database itself are dedicated to the public domain" | permitted; each row still carries its own DOI and author list |

## Sources deliberately excluded for licence reasons

| source | reason |
|---|---|
| **NIST Standard Reference Data** | copyrighted under 15 U.S.C. §290e. **Not redistributed.** Cite-and-locator only. |
| Journal article values | publisher copyright. Value plus locator recorded; no text or table reproduced. |

NIST *non*-SRD data is a different case and is redistributable with attribution; it is marked as such
in the coverage report so a downstream consumer can tell the two apart.

## What the export itself contains

`results/public/` holds aggregate statistics computed from WBM-derived predictions: counts,
proportions, confidence bounds. It contains no structures, no energies, no per-material rows and no
identifiers. Aggregates at this level are derived results, not a redistribution of the source data.
