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
