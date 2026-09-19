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
