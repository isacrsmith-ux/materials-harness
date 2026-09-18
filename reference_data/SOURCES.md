# Sources

Every row in every table carries a `source_key` that must match a `###` heading here, or
`loader.py` refuses to load the table.

**Rule for this collection:** no value is ever written from recall. A value is entered only
when it was read out of a source retrieved in-session, and the row records where in that
source it came from. Anything that could not be traced is left null with
`status="unverified"` and an explanation, rather than being filled in.

Licences below were read from the source in-session on 2026-09-17; the date each was checked
is recorded per entry. Where a licence could not be found on the source itself, the entry
says so instead of assuming.

---

## Licence summary

| Source | Licence | Commercial redistribution | Used by |
|---|---|---|---|
| NASA (NTRS, GSFC) | US Government work, public domain | **Yes**, with caveats below | `space_ao_erosion` |
| Crystallography Open Database | CC0 1.0 (public domain dedication) | **Yes** | planned: `lattice_constants` |
| NIST — non-SRD data | Not subject to US copyright (17 U.S.C. §105) | **Yes**, attribution requested | planned |
| NIST — Standard Reference Data | **Copyrighted** under 15 U.S.C. §290e | **No — do not redistribute** | planned: cite-only |
| Materials Project | CC BY 4.0 | Yes, with attribution | not used (see note) |
| Journal articles | Publisher copyright | **No** — cite value + locator only | planned |

### The NIST Standard Reference Data trap

This is the case flagged at the outset, and it is real. NIST secures copyright on SRD
compilations under the Standard Reference Data Act (15 U.S.C. §290e), *even though the
numbers are freely readable*. The NIST Chemistry WebBook is SRD Number 69 and carries:

> "© 2026 by the U.S. Secretary of Commerce on behalf of the United States of America.
> All rights reserved."

and additionally "NIST reserves the right to charge for access to this database in the future."

Consequence for this collection: individual facts are not copyrightable in the US
(*Feist v. Rural Telephone*, 499 U.S. 340), but the compilation is. So from any NIST SRD
product we store **a small number of individual values with their citation and locator, never
a bulk copy of a table, and never scanned or reproduced source text**. Tables drawing on SRD
are marked commercial-redistribution = NO in the coverage report, so a downstream consumer is
never misled about what they may republish.

NIST's *non*-SRD data is different and is fine to redistribute, asking only:

> "Please explicitly acknowledge the National Institute of Standards and Technology as the
> source of the data."

Whether the NIST cryogenic material properties database is an SRD product is **not yet
resolved** — the page carries no notice either way. It is treated as SRD (the restrictive
assumption) until confirmed.

### NASA material

NASA-produced content "generally are not subject to copyright in the United States" and may
be reused commercially. Three caveats that apply to us:

- The NASA insignia and logotype are **not** public domain — do not reproduce them.
- NASA publications sometimes embed third-party copyrighted material, which is marked as
  such in the document; NASA's use conveys no rights to others. Checked per document.
- Reuse must not imply NASA endorsement.

---

## Entries

### `degroh2006_misse2_peace`

de Groh, K. K.; Banks, B. A.; McCarthy, C. E.; Rucker, R. N.; Roberts, L. M.; Berger, L. A.
*MISSE PEACE Polymers Atomic Oxygen Erosion Results.* NASA/TM—2006-214482. NASA Glenn
Research Center, Cleveland, OH, 2006. Prepared for the 2006 MISSE Post-Retrieval Conference,
Orlando, FL.

- **Retrieved:** <https://ntrs.nasa.gov/citations/20070002707> (PDF via NTRS API), 2026-09-17
- **Vendored:** `raw/NASA-TM-2006-214482_MISSE2_PEACE.pdf`,
  sha256 `e3111dafbf5a34567581c6d3dbf5cba99fe2f4429fdd3166516a05551b546564`
- **Licence:** US Government work, public domain. No third-party copyright marks found in the
  document. Commercial redistribution: **permitted**.
- **Used by:** `space_ao_erosion.csv` (all 41 rows)
- **Extracted by:** `extract/misse2_peace.py` (parses the vendored PDF; no value typed by hand)
- **Locator:** Table 4, "MISSE 2 PEACE Polymers Erosion Yield Data", p. 17 (PDF p. 21)

**Measurement conditions**, read from the report body:

| | |
|---|---|
| Mission | MISSE 2, PEC 2 tray 1 E5, ISS exterior (Quest Airlock) |
| Deployed | 2001-08-16, STS-105 (p. 13) |
| Retrieved | 2005-07-30, STS-114 (p. 13, p. 23) |
| Duration | ~3.95 years ("almost 4-year duration", p. 14) |
| AO fluence | 8.43 × 10²¹ atoms/cm² (p. 19) |
| Orbit basis | ~400 km circular, 51.6° inclination (p. 9) |
| Method | vacuum-dehydrated mass loss; yield = ΔM / (ρ · A · F) |

**Three caveats that must travel with this data:**

1. **Six of the 41 values are lower bounds, not measurements.** The source prints `>` on them
   because the sample partially or completely eroded (p. 20: "partial or complete erosion of 6
   of the 41"). Column `is_lower_bound` carries this. The parser's count of 6 independently
   reproduces the report's own sentence, which is the cross-check that the table parsed
   correctly. Comparing these as equalities will understate erosion.
2. **The two Kapton H rows are circular.** Samples 2-E5-30 and 2-E5-33 are the fluence witness
   samples: the fluence above was *derived* from their mass loss by assuming Kapton H's erosion
   yield is 3.0 × 10⁻²⁴ cm³/atom (p. 6, p. 18, citing the report's ref. [4] — Banks 1997, a
   Wiley book chapter, not independently verified here). Their listed yields are calibration
   inputs. Column `is_fluence_witness` flags them. Every other yield in the table is
   conditional on that same assumed constant.
3. **These are polymers, plus one pyrolytic graphite (2-E5-25).** They are outside what an
   interatomic-potential harness models. This table is lookup data for material selection,
   not a validation target — as requested.

---

### `cod`

Crystallography Open Database (COD), <https://www.crystallography.net/cod/>. Queried
2026-09-17 via the JSON search interface
(`https://www.crystallography.net/cod/result?formula=<formula>&format=json`).

- **Licence:** CC0 1.0 — "All data in the COD and the database itself are dedicated to the
  public domain and licensed under the CC0 License." Commercial redistribution:
  **permitted**. COD asks that "users of the data should acknowledge the original authors of
  the structural data", so every row carries its own DOI, author list and COD entry id.
- **Used by:** `lattice_constants.csv`
- **Extracted by:** `extract/cod_oxides.py`; raw responses cached in `raw/cod/`
- **Note:** COD aggregates published determinations. The citation that matters for any row is
  its own `doi` column, not COD itself.

**COD requires curation, and this is the important part of this entry.** Formula matching
alone produces a badly contaminated set. Four distinct failure modes were found and are
filtered by the extractor; each is worth knowing about before trusting any COD-derived table:

1. **Pressure is invisible in the structured fields.** `cellpressure` and `diffrpressure` are
   null even for explicit diamond-anvil work. Verified case: COD entries 2300112–2300116, a
   zincite ZnO series whose title reads "High-pressure X-ray investigation … using diamond
   anvils", record `celltemp = 293` and **no pressure whatsoever**. Filtering on structured
   fields alone therefore silently ingests high-pressure cells as if they were ambient. Only
   the title reveals them.
2. **Parametric series masquerade as repeat measurements.** One paper contributing several
   entries whose cell walks steadily is a compression or in-situ heating run, not independent
   determinations. Rejected here: COD 2108450–2108456 (monoclinic ZrO₂, *a* 5.147 → 5.059 Å,
   a compression series) and COD 4320487–4320508 (NiO drifting 4.183 → 4.201 Å, present only
   as a *secondary phase* in a neutron study of Ni₃N). Since no point is identified as
   ambient, the whole group is dropped.
3. **Formula matching pulls in other compounds.** COD 7224240 is siliceous **faujasite**, a
   zeolite (Z = 192, V = 14 278 Å³), retrieved simply because it is SiO₂; COD 2300375 is
   alumina appearing inside a paper on NiSi. Caught by a volume-per-formula-unit check
   against the rest of the phase group.
4. **Doped samples sit under the parent formula.** COD's very first Al₂O₃ hit is **ruby** —
   Cr-doped corundum.

Surviving rows still carry a `quality_flag`. Three pre-1926 determinations (COD 1010914
corundum, and the 1922 "Erdalkalioxyde" CaO and MgO cells) are flagged `low_precision` for
stated relative uncertainty worse than 1e-3; one Y₂O₃ entry stating ±0.000004 Å on 10.604 Å
— 0.4 ppm, which no powder diffraction cell supports — is flagged `implausible_precision`.
They are kept and flagged rather than deleted, per the standing instruction to surface
suspect source values rather than drop them quietly, but they must be excluded before
computing any spread.

### Cell setting is part of a phase's identity

Worth stating because it produced a false alarm during this build. COD 1010914 reports
corundum as *a* = *b* = *c* = 5.12 Å with α = β = γ = 55.28°: that is the **rhombohedral**
setting (`R -3 c :R`) of the same structure the other entries give in the **hexagonal**
setting (`R -3 c :H`, *a* = 4.754 Å, *c* = 12.99 Å). Compared naively against them it looks
like a 76 000 ppm disagreement; it is not a disagreement at all, just a different cell
convention. It was initially mistaken here for an erroneous 1925 measurement.

Consequently every grouping in this collection keys on the **full Hermann-Mauguin symbol
including its setting suffix**, never on the space-group number: `R -3 c :H` and
`R -3 c :R` are the same space group (167) and the same phase, but their lattice constants
are not comparable numbers. `test_phase_grouping_uses_cell_setting` pins this.

---

## Sources attempted and NOT usable

Recorded so the same ground is not re-covered.

### NASA Outgassing Database (TML / CVCM / WVR) — **blocked, no data collected**

<https://etd.gsfc.nasa.gov/capabilities/outgassing-database/>. The searchable interface is
protected by Google reCAPTCHA v3. Solving or bypassing a CAPTCHA is out of bounds, so the live
database was not queried. No bulk download or API was found on the page.

The printed equivalent, NASA RP-1124 *Outgassing Data for Selecting Spacecraft Materials*, was
downloaded and rejected:

| Edition | NTRS id | Pages | Outcome |
|---|---|---|---|
| 1984, original | 20030053424 | 280 | Scanned; data tables OCR to unusable noise |
| 1997, 11th compilation (supersedes Rev. 3) | 19970027853 | 444 | Narrative has a text layer; **data tables are scanned images**, OCR unusable |
| 2014 revision | 20140000899 | — | No PDF download offered by NTRS |

Sample of the OCR on a 1997 data page: `_HHH_HH O 000 °o o oQ QQQ`. Transcribing numbers from
that would be invention, so nothing was taken from it.

**Awaiting a manual export (decided 2026-09-17).** A human can use the web interface the
CAPTCHA is guarding. To unblock: run a search at the URL above, export the result, and drop
the file in `raw/` — CSV, TSV or XLSX all fine, whatever the site offers. The columns needed
are material, manufacturer, TML %, CVCM %, WVR %, the data reference and the test year; the
ASTM E595 conditions (125 °C, 10⁻⁵ torr, 24 h) apply to the whole table and will be recorded
once at the table level rather than per row. An extractor will then be written against the
actual export rather than a guess at its shape.

### Duffy single-crystal elasticity database — **unreachable**

<https://duffy.princeton.edu/single-crystal-elasticity-database>. HTTP 403 to both WebFetch and
curl with a browser user agent. Reported (via search result, **not verified at source**) to hold
198 compositions / 477 measurements at ambient conditions. The underlying review paper is being
tried instead; see the elastic-constants entry when that dataset lands.

### Materials Project elasticity — **deliberately not used**

Reachable and working (API key in `.env`). Excluded from this collection by decision on
2026-09-17: MP elasticity is DFT-computed, and the production engine (MACE-MPA-0) is trained on
MP data, so MP values measure agreement with the engine's own training distribution rather than
with reality. `harness/suites/bulk.py` already covers that comparison and tags it
`reference_provenance: "mp_computed"`. This collection is experimental-only by design.

Note also that `harness/suites/bulk.py` documents MP elasticity returning broken documents
(potassium `K_VRH` = 33,306 GPa beside `K_Reuss` = 3.7 GPa), which is a further reason to want
an independent experimental set.
