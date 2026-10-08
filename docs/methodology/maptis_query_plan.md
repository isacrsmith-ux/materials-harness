# MAPTIS / MISSE: query plan (a plan only; nothing here has been run)

**Written 2026-10-07 local (2026-10-08 UTC).** No request was made to MAPTIS, no login was attempted and no
credential was stored or asked for. Isac has registered and does not know whether access is live or what it
costs (his statement, 2026-10-07). This is the plan for *if* he decides to go ahead. It is not evidence of anything.

## 1. What MAPTIS holds, as the source states it

Source: Burns, Finckenor, Henrie, "MISSE in the Materials and Processes Technical Information System (MAPTIS)",
National Space and Missile Materials Symposium, Bellevue WA, 24-27 June 2013 (NTRS 20140000657, report M13-2718;
licence GOV_PUBLIC_USE_PERMITTED, read 2026-10-08T02:14:24Z; PDF sha256 `5086f3fe74…`). **It is a 2013 presentation
and says nothing about cost, terms of use or redistribution.** What it does say, with PDF page locators:

- MISSE data is being gathered into MAPTIS at Marshall Space Flight Center "into a central location with controlled access and
  safe storage for any ITAR-restricted, export-controlled, or proprietary data" (pp. 1, 7).
- The database holds information about **materials, samples and flights**, with pictures, PDFs, Excel and Word files and
  other file types (p. 1). Capabilities: access control, browsing, searching, reports, record comparison (p. 1).
  Search is either general (all metadata *and* inside attached files) or advanced (chosen metadata) (pp. 12-13).
- Organisation: MISSE Overview, Flights, Samples, Materials, Papers & Reports, Images (p. 10). Where possible the
  publication PDF is attached (p. 16). Alternate material names point to one record, so "Ag/TFE", "Ag/Teflon" and
  "silver/Teflon" are the same record (p. 18).
- **Scale as of 2013:** "nearly 4,000 material samples flown since 2001" (p. 3); 3,331 records (samples, materials,
  experiments, flights), 13,948 record-to-record links and 22,037 pieces of metadata (p. 17).
- The materials span "thermal control coatings, polymers, metals, optics, insulation, composites, solar cells, shielding
  materials, part labeling" (p. 6). **The metal fraction is not stated.** MISSE-1 to -4 were "almost entirely passive"
  with post-flight analysis only (p. 3).
- The data "is still being collected" (p. 19). The 2013 presentation names a MAPTIS support contact (an email address, not reproduced here).

**What the repository already records about access** (page captured 2026-09-29, **not re-read**, since there is no network
access this session): from January 2026 non-NASA users must pay by registered-user count, and unaffiliated accounts "will be
temporarily locked until payment is arranged" (`docs/methodology/data_provenance.md`). Whether Isac's account is live
is unknown.

## 2. Public MISSE metal data already in hand, so it is not paid for twice

- **MISSE-6**, NTRS 20100033233 (ingested): anodized aluminium (6 samples) and electroless nickel (3), optical properties with
  ESH and AO fluence printed per row. The same deck prints MISSE-6 AO fluence for two exposures.
- The per-tray fluence and dose table the brief wanted for MISSE-3 and -4 (NTRS 20080033099) **is not on NTRS**: the record is an
  abstract with no document and a licence field of `OTHER` (`docs/methodology/data_provenance.md`). The cross-walk in query 5
  therefore has no committed target for MISSE-3/-4; the exposure record would have to come from MAPTIS itself or from the full paper.

## 3. Ordered query list

The field and filter names are **unknown until someone is logged in**, so the queries are stated by what they must return.
For every query, record the date, the exact filters used, and the count, in a gitignored log.

1. **Count of metal-class records across MISSE 1-7.** Material records whose class is metal (or the nearest equivalent), the
   sample records linked to them, and the same two counts per flight (MISSE-1 to -7). Counts only. This is the go/no-go input.
2. **Aluminium alloys:** 6061, 7075, 2219, 2090 and 2195. For each hit: sample count, flights, whether a post-flight
   quantity is attached (mass or thickness change, optical properties, erosion yield, images only).
3. **Magnesium alloys, Ti-6Al-4V and Be.** As in 2.
4. **Ag, Cu and Os.** As in 2. These are the elements with prior flight data in hand (Ag and Cu from LDEF and EOIM-3), so
   a MISSE row would add a second environment (ISS, up to years) to the same metals. Os is included because it is a classic
   AO-resistant reference.
5. **For each hit: the tray fluence and dose record**, and whether the exposure is stated per tray, per flight or not at all.
   Where a hit has no fluence, it is not a usable row (section 5).

Stop after query 1 if the count rule in section 5 already says no.

## 4. Rules that will apply to anything ingested

1. **Read MAPTIS's own terms of use before any download.** The data may not be redistributable. **Assume it is not, and that even
   derived aggregates may not go in this public repository, until the terms have been read in-session and say otherwise.** A
   record count may be the only thing publishable. If the terms forbid derived aggregates, nothing from MAPTIS goes in `reports/`.
2. **Isac does the login and the export; the harness never holds credentials, never scrapes and never automates the site.** Use the
   system's own browsing, search and report functions by hand, and save exports to the gitignored cache
   (`cache/external/aerospace/maptis/`). The harness reads only files Isac has saved.
3. **Export-controlled, ITAR-restricted and proprietary records are out.** The source says MAPTIS holds them under access control.
   Any record carrying such a flag, or lacking a statement that it is releasable, is excluded and not summarised.
4. **The existing discipline:** URL or export identifier, retrieval time (UTC), licence or terms as read that day, file sha256, canonical
   citation; every value transcribed with a locator; row-level values in gitignored files only (open decision 5, "commit flight values?",
   is not taken); the `quantity_kind` schema; EOIM-3-style null results as upper bounds, never as zeros; rows of different kinds never pooled.
5. **Check the account first, without scraping.** If the account is locked or payment is required, stop and record that; do not create
   another account or work around it.
6. **Cost is Isac's decision and is not committed here.** Record what was paid and for what in the provenance table.

## 5. Go / no-go

A **usable row** is a metal-class sample with all of: (a) an identified material (alloy or purity), (b) a flight with a fluence or dose record,
(c) a post-flight measured quantity (mass change, thickness change, erosion, optical property), and (d) a release the terms and flags allow.

- **Under about 30 usable rows with fluence: recommend dropping MISSE.** For scale, the public sources already ingested give 54 distinct flight samples
  with a stated fluence (counted from the gitignored row table, 19930001392: 4, 19930019095: 2, 19950021220: 18, 19970025577: 22, 20100033233: 8), so a MISSE yield under about 30 would add little.
- **30 or more:** worth going on to queries 2-5, *subject to the terms reading in section 4 rule 1*. If the terms bar any public derived
  output, the rows could be used privately but nothing could be reported in the repository, and the recommendation is to drop MISSE as
  a source for this public harness.
- **Cost gate:** if payment is required, the count from query 1 (obtained inside whatever access is already live) should be seen before
  any further spend.

## Open decision

**Pay and run this plan, or drop MISSE?** The facts that would settle it are the account status, the cost and the terms of use. None of them is known.
