# T-phase Al alloys: stretch task, read and recorded, **no relaxation done**

> **DEVELOPMENT / DESCRIPTIVE TIER. No verdict. Nothing here is a radiation-tolerance claim.** Written 2026-10-07 local (2026-10-08 UTC).
> The stretch task asked for one descriptive data point on whether the production engine handles a giant-cell intermetallic. **It could not be produced**, and the reasons are below.

## What the two papers say

Both are open access under CC BY 4.0 (licence read from the Europe PMC full-text XML), read via Europe PMC because the publisher's DOI pages sit behind a Cloudflare challenge (HTTP 403,
not bypassed). Provenance and hashes: `docs/methodology/data_provenance.md`.

| | Tunes et al. | Willenshofer et al. |
|---|---|---|
| citation | *Adv. Sci.* **7**, 2002397 (2020), doi:10.1002/advs.202002397, "Prototypic Lightweight Alloy Design for Stellar-Radiation Environments" | *Adv. Mater.*, doi:10.1002/adma.202513450, "Radiation-Resistant Aluminum Alloy for Space Missions in the Extreme Environment of the Solar System". Received 2025-07-14, issue dated 2026-04-07 on the Europe PMC record. **The brief said 2025; the issue date is 2026.** |
| alloy | AlMg4.7Zn3.4 (wt%), a 5xxx / 7xxx crossover | Al-5.34Mg-1.56Zn-0.26Cu-0.04Ag (at%), ultrafine-grained by high-pressure torsion |
| T-phase | Mg32(Zn,Al)49, cubic, "reported stoichiometry"; precipitates 10-200 nm | Mg32(Zn,Al)49, **162 atoms in the unit cell**; precipitates 6.7 +- 0.7 nm after heat treatment |
| irradiation | 100 keV Pb+ in situ in a TEM at MIAMI-2 (Huddersfield), up to 1 dpa; precipitates survive, no cavities, black-spot damage | 300 keV Ar+ in situ TEM up to a stated 100 dpa; 600 keV Ne2+ for microtensile tests up to 20 dpa; T-phase tolerant to 24 dpa, voids only beyond 75 dpa |
| structure source cited | Pauling File datasheet "Mg32(Al,Zn)49 (Mg32Zn31.9Al17.1)", *Pauling File Multinaries Edition 2012*, Springer Materials / MPDS / NIMS (ref. 80); **Bergman, Waugh, Pauling, *Acta Crystallogr.* 10, 254 (1957)** (ref. 83); orientation relationship from Ryum, *Z. Metallkd.* 66, 377 (1975) | **Bergman, Waugh, Pauling, *Acta Crystallogr.* 10, 254 (1957)** (ref. 61) |

Tunes states that its structure drawing was made in CrystalMaker "using existing reference literature data". Neither paper gives a lattice constant, space group or atomic coordinates in the text read.
The Pauling File composition Mg32Zn31.9Al17.1 has 81 atoms, so the 162-atom cell holds two formula units, and the Zn/Al sites are **mixed (partially occupied)**.

## Why no engine data point

1. **Materials Project has no such structure.** Searching the harness's cached MP summary for the Al-Mg-Zn system returned 12 entries, the largest with 76 sites (not this phase), and
   no Mg32Zn49, Mg32Al49 or ordered Mg32(Zn,Al)49 under any formula tried. In the binaries, the only entries between 81 and 162 sites have other site counts and compositions (Mg41Al67 with 108 sites, Mg21Zn25 with 92, and two dilute Mg149 cells with 150).
   I did not examine their structures further. None has the formula the papers state. **So I found no MP formation energy or hull distance for this phase to compare with.**
2. **Without a DFT value for the same structure the comparison is not a comparison.** An engine formation energy for an ordered 81-atom model would be a prediction with no reference, and the ordering
   itself (which sites carry Zn and which Al) is a modelling choice the sources do not fix.
3. **OQMD was not consulted.** The local OQMD copy holds the locked, unopened held-out half, which this session must not touch.
4. **COD (a primary structure database, CC0):** two metadata queries returned empty bodies (HTTP 200); inconclusive, not pursued. The Bergman-Waugh-Pauling structure may well be in COD or ICSD with partial occupancies.
5. **No DFT code is installed** in the environment (Phase 0 scoping), so a reference could not be generated here.

## What would make it doable

A structure file with coordinates (COD or ICSD, from Bergman et al.), an ordering rule for the Zn/Al sites, and a DFT reference for that ordered cell, from a database that has it or from a campaign.
The first two are an afternoon; the third is the first monetary cost on this track. None of it is a radiation-tolerance test: both papers' claim rests on irradiation in a TEM, which a static formation energy does not address.
