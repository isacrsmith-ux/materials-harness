# reference_data

Citable experimental reference data for property suites, gathered for later validation.
Data gathering only: nothing here runs a simulation, and nothing here modifies the existing
validation suites in `harness/suites/`.

## The rule this collection is built on

**No value is ever written from recall.** A number appears here only if it was read out of a
source retrieved in-session, and its row records where in that source it came from. Anything
untraceable is left empty with `status="unverified"` and an explanation of what was tried.
`SOURCES.md` records every source, its licence, and — as importantly — the sources that were
attempted and rejected, so the same dead ends are not re-explored.

## Using it

```python
import sys; sys.path.insert(0, "reference_data")
import loader

rows = loader.load("lattice_constants")   # raises on the first schema/unit/provenance error
loader.tables()                           # what is available
```

`python reference_data/loader.py` validates every table and prints a row count each.

## What is here

| File | Contents |
|---|---|
| `materials.csv` | Shared key table: one row per phase, keyed `formula\|space-group symbol` |
| `lattice_constants.csv` | Room-temperature oxide lattice constants, each with its own DOI |
| `space_ao_erosion.csv` | Atomic oxygen erosion yields, MISSE 2 PEACE (41 polymers) |
| `schema/*.json` | JSON Schema per table, including SI units and unit-pair factors |
| `loader.py` | Loading + validation |
| `extract/*.py` | One extractor per source; re-running reproduces the CSVs |
| `raw/` | Vendored sources and cached API responses, so builds reproduce offline |
| `SOURCES.md` | Full citations, licences, commercial-use status, rejected sources |
| `COVERAGE.md` | Counts, overlap with existing suites, experimental spread, gaps |
| `tests/test_loader.py` | 24 tests, mostly about what the loader *rejects* |

## Three things that will bite you if unnoticed

**Units are checked, not trusted.** Each schema declares `unit_pairs` — the SI column, the
source's original column, and the factor between them. The loader recomputes the SI value
from the original on every row, so a value accidentally left in the source's units is
rejected rather than loaded. Both columns are kept: SI for use, original for audit.

**A missing temperature is recorded, not assumed.** 34 of 48 lattice rows have
`temperature_status = not_stated_in_source`. Crystallographic cells are usually measured at
ambient, but "usually" is not a citation, so those rows carry no temperature at all. Only
rows with a recorded temperature are safe for thermal work.

**The cell setting is part of a phase's identity.** `R -3 c :H` and `R -3 c :R` are the same
space group and the same phase, but corundum's *a* is 4.75 Å in one and 5.12 Å in the other.
Group on the full Hermann-Mauguin symbol, never the space-group number. Comparing across
settings manufactures a ~76 000 ppm disagreement out of nothing — it happened during this
build, and `test_phase_grouping_uses_cell_setting` now pins it.

## Rebuilding

```bash
.venv/bin/python reference_data/extract/cod_oxides.py        # lattice constants (cached)
.venv/bin/python reference_data/extract/materials_table.py   # shared key table
.venv/bin/python reference_data/extract/coverage_report.py   # COVERAGE.md
./uvw run --with pypdf --no-project python reference_data/extract/misse2_peace.py
```

Pass `--refresh` to the first two to re-query the network instead of using `raw/`. The MISSE
extractor needs `pypdf`, which is deliberately *not* a project dependency — the `uvw run
--with` invocation supplies it for that one command.
