"""Build lattice_constants.csv for oxides from the Crystallography Open Database.

COD is CC0 (public domain dedication); users are asked to acknowledge the original authors
of each structure, so every row carries its own DOI, authors and COD id -- the citation
travels with the value.

Selection rules, applied mechanically so they can be audited:
  * the source must print a cell uncertainty (siga) -- the brief requires stated uncertainty
  * the source must have a DOI -- the brief requires a traceable source
  * titles indicating a doped, substituted, hydrated, amorphous or thin-film sample are
    excluded (COD's first Al2O3 hit is ruby, i.e. Cr-doped corundum, not corundum)
  * EVERY qualifying determination is kept, not one per material and never an average, so
    the spread between independent measurements can be reported

Temperature is recorded, never assumed. Where the source states no temperature the row has
temperature_k empty and temperature_status="not_stated_in_source". Crystallographic cells
are usually measured at ambient, but "usually" is not a citation.

Run:  .venv/bin/python reference_data/extract/cod_oxides.py [--refresh]
Cached COD responses live in raw/cod/ so the build is reproducible offline.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "reference_data" / "raw" / "cod"
OUT = ROOT / "reference_data" / "lattice_constants.csv"
SOURCE_KEY = "cod"

# COD writes formulae with element symbols in alphabetical order.
TARGETS = [
    ("Al2 O3", "Al2O3"), ("O2 Ti", "TiO2"), ("O2 Zr", "ZrO2"), ("Mg O", "MgO"),
    ("O2 Si", "SiO2"), ("Be O", "BeO"), ("Ca O", "CaO"), ("O3 Y2", "Y2O3"),
    ("Hf O2", "HfO2"), ("Ce O2", "CeO2"), ("Al2 Mg O4", "MgAl2O4"),
    ("Cr2 O3", "Cr2O3"), ("Fe2 O3", "Fe2O3"), ("Ni O", "NiO"), ("Co O", "CoO"),
    ("Mn O", "MnO"), ("Cu O", "CuO"), ("Cu2 O", "Cu2O"), ("O Zn", "ZnO"),
    ("O2 Sn", "SnO2"), ("O3 W", "WO3"), ("O5 V2", "V2O5"),
    ("O3 Sr Ti", "SrTiO3"), ("Ba O3 Ti", "BaTiO3"), ("O3 Sc2", "Sc2O3"),
    ("In2 O3", "In2O3"), ("Ga2 O3", "Ga2O3"), ("La2 O3", "La2O3"),
]

RT_RANGE = (283.0, 303.0)

IMPURE = re.compile(
    r"\b(dop|ruby|solid solution|substitut|alloy|glass|amorphous|thin.?film|nanocryst|"
    r"nanoparticle|nanorod|nanostructur|hydrate|hydrous|deuterat|non-?stoichiometr|"
    r"defect|impurit|mixed)", re.I
)

# COD's structured cellpressure/diffrpressure fields are null even for explicit
# diamond-anvil studies (verified 2026-09-17: the ZnO zincite series cod-2300112..116
# records celltemp=293 and NO pressure at all, while its title says "High-pressure X-ray
# investigation ... using diamond anvils"). So non-ambient conditions can ONLY be screened
# out of COD by reading the title. Anything matching here is off-ambient, a different
# phase, or a framework silicate that merely shares a formula.
NON_AMBIENT = re.compile(
    r"(high.?pressure|diamond.?anvil|equation[s]? of state|compress|gigapascal|\bGPa\b|"
    r"high.?temperatur|bei hohen Temperaturen|in.?situ heat|thermal expansion|"
    r"zeolit|faujasit|sodalit|clathrasil|framework|"
    # An incommensurately modulated structure has no ordinary periodic cell (its symmetry is
    # a superspace group), so its "lattice constant" is not comparable to a relaxed cell.
    r"incommensurat|modulated structure|superspace)", re.I
)

# Volume per formula unit identifies the phase independently of cell setting, so an entry
# that is actually a different compound or a different polymorph is caught even when its
# space group and formula match. Tolerance is generous: real determinations of one phase
# agree far closer than this.
VOL_PER_FU_TOL = 0.05

ANGSTROM_TO_M = 1e-10


def fetch(cod_formula: str, refresh: bool) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (cod_formula.replace(" ", "_") + ".json")
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    url = "https://www.crystallography.net/cod/result?" + urllib.parse.urlencode(
        {"formula": cod_formula, "format": "json"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "materials-harness/reference-data"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        data = json.load(fh)
    path.write_text(json.dumps(data, indent=1))
    time.sleep(1.5)  # be a good citizen; COD asks for delays on bulk access
    return data


def num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def temperature(rec) -> tuple[float | None, str]:
    """Cell temperature if the source states one, else the diffraction temperature."""
    for key, label in (("celltemp", "cell"), ("diffrtemp", "diffraction")):
        t = num(rec.get(key))
        if t is not None:
            return t, f"recorded_{label}"
    return None, "not_stated_in_source"


def build(refresh: bool) -> list[dict]:
    rows = []
    for cod_formula, label in TARGETS:
        for rec in fetch(cod_formula, refresh):
            a, siga = num(rec.get("a")), num(rec.get("siga"))
            if a is None or siga is None or not rec.get("doi"):
                continue
            text = f"{rec.get('title') or ''} {rec.get('chemname') or ''}"
            if IMPURE.search(text) or NON_AMBIENT.search(text):
                continue
            t_k, t_status = temperature(rec)
            if t_k is not None and not (RT_RANGE[0] <= t_k <= RT_RANGE[1]):
                continue  # this table is room temperature only
            b, c = num(rec.get("b")), num(rec.get("c"))
            vol, z = num(rec.get("vol")), num(rec.get("Z"))
            vol_per_fu = vol / z if vol and z else None
            rows.append(
                {
                    "_vol_per_fu": vol_per_fu,
                    "material_key": f"{label}:cod-{rec['file']}",
                    "formula": label,
                    "cod_id": rec["file"],
                    "mineral_name": rec.get("mineral") or "",
                    "chemical_name": rec.get("chemname") or "",
                    "space_group": rec.get("sg") or "",
                    "space_group_number": rec.get("sgNumber") or "",
                    "a_m": f"{a * ANGSTROM_TO_M:.12e}",
                    "a_original_angstrom": rec["a"],
                    "a_uncertainty_angstrom": rec["siga"],
                    "b_original_angstrom": rec.get("b") or "",
                    "b_uncertainty_angstrom": rec.get("sigb") or "",
                    "c_original_angstrom": rec.get("c") or "",
                    "c_uncertainty_angstrom": rec.get("sigc") or "",
                    "alpha_deg": rec.get("alpha") or "",
                    "beta_deg": rec.get("beta") or "",
                    "gamma_deg": rec.get("gamma") or "",
                    "original_units": "angstrom",
                    "temperature_k": "" if t_k is None else f"{t_k:g}",
                    "temperature_status": t_status,
                    "sample_form": "single crystal or powder - see source",
                    "r_factor_all": rec.get("Rall") or "",
                    "doi": rec["doi"],
                    "authors": rec.get("authors") or "",
                    "journal": rec.get("journal") or "",
                    "year": rec.get("year") or "",
                    "title": (rec.get("title") or "").strip(),
                    "source_key": SOURCE_KEY,
                    "source_locator": f"COD entry {rec['file']}",
                    "status": "verified",
                    "note": (
                        ""
                        if t_k is not None
                        else "Source states no measurement temperature; not assumed to be ambient."
                    ),
                }
            )
    return rows


def reject_parametric_series(rows: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Drop pressure/temperature scans that COD does not label as such.

    A single paper contributing several entries for one phase, with the cell parameter
    walking steadily across them, is a parametric series - a compression run or an in-situ
    heating run - not several independent determinations. COD records no pressure for these
    (see NON_AMBIENT), so the series shape is the only available signal. Two real examples
    in this target list:

      * cod-2108450..456, one DOI, monoclinic ZrO2, a walking 5.147 -> 5.059 A: a
        compression series ("softenings of bulk modulus" in the title).
      * cod-4320487..508, one DOI, NiO, a walking 4.183 -> 4.201 A: NiO as a secondary
        phase in an in-situ neutron study of Ni3N.

    Neither states which point, if any, is ambient, so the whole group goes. Entries
    repeating one determination (identical cells) are kept and deduplicated elsewhere.
    """
    import statistics as st
    from collections import defaultdict

    by_paper = defaultdict(list)
    for r in rows:
        by_paper[(r["formula"], r["space_group_number"], r["doi"])].append(r)

    kept, dropped = [], []
    for (formula, sg, doi), members in by_paper.items():
        values = [float(m["a_original_angstrom"]) for m in members]
        spread = (max(values) - min(values)) / st.mean(values) * 1e6 if values else 0
        if len(members) >= 3 and spread > 1000:
            for m in members:
                dropped.append(
                    (m, f"{len(members)} entries from one DOI spanning {spread:.0f} ppm "
                        f"for {formula} sg{sg}: a parametric series, not repeat measurements")
                )
        else:
            kept.extend(members)
    return kept, dropped


def deduplicate(rows: list[dict]) -> tuple[list[dict], int]:
    """One paper reporting the same cell several times (e.g. several refinements of one
    crystal) is one determination, not several, and must not be counted as agreement."""
    seen, kept = {}, []
    for r in rows:
        key = (r["doi"], r["a_original_angstrom"], r["b_original_angstrom"], r["c_original_angstrom"])
        if key in seen:
            seen[key]["note"] = (
                seen[key]["note"] + " " if seen[key]["note"] else ""
            ) + "Source reports this same cell in more than one COD entry; kept once."
            continue
        seen[key] = r
        kept.append(r)
    return kept, len(rows) - len(kept)


def reject_phase_outliers(rows: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Drop entries whose volume per formula unit disagrees with the rest of their
    (formula, space group) group: those are a different compound or a different phase that
    merely shares a formula, not a disagreeing measurement of the same thing."""
    import statistics as st
    from collections import defaultdict

    groups = defaultdict(list)
    for r in rows:
        groups[(r["formula"], r["space_group_number"])].append(r)

    kept, dropped = [], []
    for key, members in groups.items():
        vols = [r["_vol_per_fu"] for r in members if r["_vol_per_fu"]]
        if len(vols) < 2:
            kept.extend(members)
            continue
        median = st.median(vols)
        for r in members:
            v = r["_vol_per_fu"]
            if v and abs(v - median) / median > VOL_PER_FU_TOL:
                dropped.append(
                    (r, f"volume/formula unit {v:.2f} A^3 vs group median {median:.2f} "
                        f"for {key[0]} sg{key[1]}")
                )
            else:
                kept.append(r)
    return kept, dropped


def main() -> None:
    rows = build("--refresh" in sys.argv)
    rows, dropped = reject_phase_outliers(rows)
    rows, dropped_series = reject_parametric_series(rows)
    rows, n_dupes = deduplicate(rows)
    for r in rows:
        r.pop("_vol_per_fu", None)
        rel = float(r["a_uncertainty_angstrom"]) / float(r["a_original_angstrom"])
        # A stated uncertainty below ~1 ppm on a diffraction cell is not credible; a
        # relative uncertainty above 1e-3 is too coarse to test a simulation against.
        if rel > 1e-3:
            r["quality_flag"] = "low_precision"
        elif rel < 1e-6:
            r["quality_flag"] = "implausible_precision"
        else:
            r["quality_flag"] = "ok"
    for label, group in (("a different phase or compound", dropped),
                         ("a parametric (pressure/temperature) series", dropped_series)):
        if group:
            print(f"rejected {len(group)} entries as {label}:")
            for r, why in sorted(group, key=lambda x: x[0]["cod_id"]):
                print(f"  cod-{r['cod_id']:9} {r['formula']:8} {why}")
    if n_dupes:
        print(f"merged {n_dupes} duplicate entries reporting an already-listed cell")
    rows.sort(key=lambda r: (r["formula"], r["space_group_number"], r["cod_id"]))
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with_t = sum(r["temperature_status"].startswith("recorded") for r in rows)
    print(
        f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows across "
        f"{len({r['formula'] for r in rows})} formulae, "
        f"{len({(r['formula'], r['space_group_number']) for r in rows})} polymorphs; "
        f"{with_t} with a recorded temperature, {len(rows) - with_t} without"
    )


if __name__ == "__main__":
    main()
