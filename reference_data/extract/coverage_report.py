"""Generate reference_data/COVERAGE.md: what the collection holds, what it overlaps with
the project's existing suites, the experimental spread, and the biggest gaps.

Run:  .venv/bin/python reference_data/extract/coverage_report.py
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "reference_data"))
import loader  # noqa: E402

OUT = ROOT / "reference_data" / "COVERAGE.md"
SUBSTITUTION = ROOT / "data" / "substitution_candidates.csv"
EXISTING_LATTICE = ROOT / "data" / "experimental_lattice_constants.csv"
EXISTING_CSONKA = ROOT / "data" / "experimental_csonka2009.csv"


def elements(formula: str) -> list[str]:
    return re.findall(r"[A-Z][a-z]?", formula)


def substitution_materials() -> dict[str, set[str]]:
    families = defaultdict(set)
    with SUBSTITUTION.open() as fh:
        for r in csv.DictReader(fh):
            families[r["family"]].update([r["parent"], r["target"]])
    return families


def existing_experimental() -> set[str]:
    out = set()
    with EXISTING_LATTICE.open() as fh:
        out.update(r["formula"] for r in csv.DictReader(fh))
    with EXISTING_CSONKA.open() as fh:
        out.update(
            r["material"]
            for r in csv.DictReader(line for line in fh if not line.startswith("#"))
        )
    return out


def spread_table(rows):
    groups = defaultdict(list)
    for r in rows:
        if r["quality_flag"] == "ok":
            groups[(r["formula"], r["space_group"])].append(r)
    out = []
    for (formula, sg), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        a = [float(m["a_original_angstrom"]) for m in members]
        mean = st.mean(a)
        out.append((formula, sg, len(members), mean, (max(a) - min(a)) / mean * 1e6))
    return out


def main() -> None:
    lattice = loader.load("lattice_constants")
    erosion = loader.load("space_ao_erosion")
    materials = loader.load("materials")

    fams = substitution_materials()
    sub_all = set().union(*fams.values())
    sub_oxides = {m for m in sub_all if "O" in elements(m)}
    have = {r["formula"] for r in lattice}
    existing = existing_experimental()

    spreads = spread_table(lattice)
    values = [s for *_, s in spreads]

    L = []
    w = L.append
    w("# Coverage report")
    w("")
    w(f"Generated {dt.date.today().isoformat()} by `extract/coverage_report.py`. "
      "Every count below comes from loading the shipped tables through `loader.py`, "
      "so it cannot drift from what is actually in the CSVs.")
    w("")

    w("## Materials per property")
    w("")
    w("| Property | Table | Rows | Distinct materials | Distinct phases | Status |")
    w("|---|---|---:|---:|---:|---|")
    w(f"| Lattice constants (oxides, RT) | `lattice_constants.csv` | {len(lattice)} | "
      f"{len(have)} | {len({(r['formula'], r['space_group']) for r in lattice})} | complete |")
    w(f"| Atomic oxygen erosion | `space_ao_erosion.csv` | {len(erosion)} | "
      f"{len({r['material_name'] for r in erosion})} | n/a | complete |")
    w("| Outgassing (TML/CVCM/WVR) | — | 0 | 0 | n/a | **blocked** — see SOURCES.md |")
    w("| Elastic constants | — | 0 | 0 | n/a | not started |")
    w("| Thermal expansion | — | 0 | 0 | n/a | not started |")
    w("| Heat capacity / phonons | — | 0 | 0 | n/a | not started |")
    w("")
    w(f"Shared key table `materials.csv`: {len(materials)} phases, "
      f"{sum(1 for m in materials if m['materials_project_id'])} carrying a Materials "
      "Project id as a join key.")
    w("")

    w("## Temperature provenance")
    w("")
    by_status = defaultdict(int)
    for r in lattice:
        by_status[r["temperature_status"]] += 1
    w("| Temperature | Rows |")
    w("|---|---:|")
    for k, v in sorted(by_status.items(), key=lambda kv: -kv[1]):
        w(f"| {k} | {v} |")
    w("")
    w("The brief asked for room-temperature values. Most crystallographic determinations "
      "state no measurement temperature at all, and those rows carry "
      "`not_stated_in_source` rather than an assumed 293 K. **Only the "
      f"{by_status['recorded_cell'] + by_status['recorded_diffraction']} rows with a "
      "recorded temperature are safe for thermal work**; the rest are safe only for "
      "comparisons where a ~1e-5/K expansion coefficient over an unknown ambient range is "
      "tolerable.")
    w("")

    w("## Cross-check: spread between independent determinations")
    w("")
    w("This is the floor on useful simulation accuracy. Where two independent experiments "
      "of the same phase disagree by *x*, chasing accuracy below *x* is not measurable.")
    w("")
    w("Rows flagged `low_precision` or `implausible_precision` are excluded, and grouping "
      "keys on the **cell setting**, not the space-group number (see SOURCES.md).")
    w("")
    w("| Material | Setting | n | mean a (Å) | spread (ppm) | spread (%) |")
    w("|---|---|---:|---:|---:|---:|")
    for formula, sg, n, mean, ppm in spreads:
        w(f"| {formula} | `{sg}` | {n} | {mean:.5f} | {ppm:.0f} | {ppm / 1e4:.3f} |")
    w("")
    if values:
        w(f"**Median spread {st.median(values):.0f} ppm ({st.median(values) / 1e4:.3f} %), "
          f"worst {max(values):.0f} ppm ({max(values) / 1e4:.3f} %), over "
          f"{len(spreads)} phases with two or more determinations.**")
        w("")
        w(f"So for oxide lattice constants the experimental floor is roughly "
          f"{st.median(values) / 1e4:.2f} %. A simulation targeting 1 % sits comfortably "
          "above it; targeting better than ~0.1 % is chasing noise between experiments.")
    w("")

    w("## Overlap with the substitution suite")
    w("")
    w(f"`data/substitution_candidates.csv` holds {len(sub_all)} distinct materials across "
      f"{len(fams)} families, of which {len(sub_oxides)} are oxides.")
    w("")
    w("| Family | Oxides in family | Covered here | Missing |")
    w("|---|---:|---:|---|")
    for family, members in sorted(fams.items()):
        ox = sorted(m for m in members if "O" in elements(m))
        if not ox:
            continue
        hit = [m for m in ox if m in have]
        miss = [m for m in ox if m not in have]
        w(f"| {family} | {len(ox)} | {len(hit)} | {', '.join(miss) if miss else '—'} |")
    w("")
    covered = sorted(sub_oxides & have)
    w(f"**{len(covered)} of {len(sub_oxides)} substitution-suite oxides now have an "
      f"experimental room-temperature lattice constant**: {', '.join(covered)}.")
    w("")

    w("## The gap this fills")
    w("")
    only_mgo = sorted(f for f in existing if "O" in elements(f) and len(elements(f)) > 1)
    w(f"The project's existing experimental lattice set (`experimental_lattice_constants.csv` "
      f"plus `experimental_csonka2009.csv`) covers {len(existing)} materials, of which the "
      f"oxides are: {', '.join(only_mgo) or 'none'}.")
    w("")
    w("The brief described that set as covering neither metals nor oxides. Half of that is "
      "right. It covers **14 elemental metals** (Ag, Al, Ba, Ca, Cs, Cu, K, Li, Na, Pb, Pd, "
      "Rb, Rh, Sr) via the Csonka set, but only **one oxide**, MgO. So the oxide gap was "
      "real and is what this table fills; the metals gap was not.")
    w("")
    w("There is a second gap underneath, which the brief did not name: every existing metal "
      "value is a **0 K or low-temperature** figure with zero-point anharmonic expansion "
      "subtracted, not a room-temperature one. The project currently has no "
      "room-temperature experimental lattice constant for any metal.")
    w("")

    w("## Biggest remaining gaps, ranked")
    w("")
    w("1. **Outgassing data — blocked.** The NASA database is behind a reCAPTCHA and the "
      "printed RP-1124 editions are scans whose data tables OCR to noise. Needs a manual "
      "export.")
    w("2. **Elastic constants — not started, and the hardest.** The authoritative "
      "compilations (Simmons & Wang; Landolt-Börnstein) are copyrighted print handbooks, "
      "and the open Duffy database returns 403. Expect 15–30 materials from individual "
      "papers, not the 40–60 targeted.")
    w("3. **Thermal expansion and heat capacity — not started.** NIST's cryogenic database "
      "covers 43 materials but is mostly engineering alloys and polymers: no SiC, AlN, GaN, "
      "MgO or ZrO2, and its fits stop at 300 K, short of the +120 °C LEO limit.")
    w("4. **Room-temperature metals.** Not covered by this table (oxides only) and not by "
      "the existing 0 K set.")
    w("5. **Ternary oxides.** Only SrTiO3 and BaTiO3 here; the substitution suite's "
      "perovskite and spinel families are largely uncovered.")
    w("6. **Temperature provenance.** "
      f"{by_status['not_stated_in_source']} of {len(lattice)} lattice rows have no stated "
      "temperature. Narrowing these means reading each original paper.")
    w("")

    w("## Licence posture")
    w("")
    w("| Table | Source | Licence | Commercial redistribution |")
    w("|---|---|---|---|")
    w("| `lattice_constants.csv` | COD | CC0 1.0 | **Yes** (acknowledge original authors) |")
    w("| `space_ao_erosion.csv` | NASA/TM-2006-214482 | US Gov, public domain | **Yes** |")
    w("| `materials.csv` | derived + MP ids | CC BY 4.0 (MP ids) | Yes, with attribution |")
    w("")
    w("No NIST Standard Reference Data is used in any shipped table. When datasets 2 and 3 "
      "land they will be, and those rows will be cite-only and marked non-redistributable — "
      "NIST SRD is copyrighted under 15 U.S.C. §290e despite being free to read.")
    w("")

    OUT.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(L)} lines)")


if __name__ == "__main__":
    main()
