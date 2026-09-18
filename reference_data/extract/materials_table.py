"""Build materials.csv: the shared key table the property tables join against.

Keyed by formula, with a Materials Project id attached where one can be matched on
(formula, space group). The MP id is here as an IDENTIFIER ONLY - a join key into the
harness's existing suites. No MP value is used as reference data anywhere in this
collection; see SOURCES.md for why.

Note on MP ids: this harness already documents two id generations (harness/unseen.py:25 -
legacy 'mp-10597' vs current 'mp-aaaaaprp'). The ids written here are whatever the live API
returns today, recorded with the date, so a later mismatch is diagnosable.

Run:  .venv/bin/python reference_data/extract/materials_table.py
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import sys

import requests
from dotenv import dotenv_values

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "reference_data" / "raw" / "mp_ids.json"
OUT = ROOT / "reference_data" / "materials.csv"
API = "https://api.materialsproject.org/materials/summary/"


def mp_lookup(formulas: list[str], refresh: bool) -> dict:
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text())
    key = (dotenv_values(ROOT / ".env").get("MP_API_KEY") or "").strip()
    if not key:
        print("MP_API_KEY not set; material_project_id will be left empty", file=sys.stderr)
        return {}
    found = {}
    for formula in formulas:
        r = requests.get(
            API,
            headers={"X-API-KEY": key},
            params={
                "formula": formula,
                "_fields": "material_id,symmetry,energy_above_hull,formula_pretty",
                "_sort_fields": "energy_above_hull",
                "_limit": 50,
            },
            timeout=60,
        )
        r.raise_for_status()
        found[formula] = [
            {
                "material_id": d["material_id"],
                "sg": (d.get("symmetry") or {}).get("number"),
                "ehull": d.get("energy_above_hull"),
            }
            for d in r.json().get("data", [])
        ]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(found, indent=1))
    return found


def sg_number_from_symbol(symbol: str) -> int | None:
    """International Tables number for a Hermann-Mauguin symbol, e.g. 'R -3 c :H' -> 167.
    Returns None rather than guessing when the symbol is not recognised."""
    from pymatgen.symmetry.groups import SpaceGroup

    # COD writes the setting as a ':H'/':R'/':1'/':2' suffix and spaces between operators;
    # pymatgen wants the bare symbol.
    bare = symbol.split(":")[0].replace(" ", "").strip()
    for candidate in (bare, symbol.strip()):
        try:
            return SpaceGroup(candidate).int_number
        except Exception:
            continue
    return None


def main() -> None:
    sys.path.insert(0, str(ROOT / "reference_data"))
    import loader

    lattice = loader.load("lattice_constants")
    # A phase is (formula, cell setting). The space group NUMBER is missing from some COD
    # entries, so it is back-filled from any sibling entry that records it rather than
    # being allowed to split one phase into two rows.
    numbers: dict[tuple[str, str], str] = {}
    for r in lattice:
        if r["space_group_number"]:
            numbers.setdefault((r["formula"], r["space_group"]), r["space_group_number"])
        else:
            # Derive the number from the Hermann-Mauguin symbol via the International
            # Tables (pymatgen's tabulation), rather than leaving the join key incomplete.
            n = sg_number_from_symbol(r["space_group"])
            if n:
                numbers.setdefault((r["formula"], r["space_group"]), str(n))
    phases = sorted({(r["formula"], r["space_group"]) for r in lattice})
    mp = mp_lookup(sorted({f for f, _ in phases}), "--refresh" in sys.argv)
    today = dt.date.today().isoformat()

    rows = []
    for formula, sg_symbol in phases:
        sg_number = numbers.get((formula, sg_symbol), "")
        match = None
        if sg_number:
            for cand in mp.get(formula, []):
                if str(cand["sg"]) == sg_number:
                    match = cand
                    break
        n = sum(
            1 for r in lattice
            if r["formula"] == formula and r["space_group"] == sg_symbol
        )
        rows.append(
            {
                # The cell SETTING is part of the identity: corundum's hexagonal
                # (R -3 c :H, a=4.75) and rhombohedral (R -3 c :R, a=5.12) settings are the
                # same phase, but their lattice constants are not comparable numbers.
                "material_key": f"{formula}|{sg_symbol}",
                "formula": formula,
                "space_group_number": sg_number or "",
                "space_group": sg_symbol,
                "material_class": "oxide",
                "materials_project_id": match["material_id"] if match else "",
                "mp_energy_above_hull_ev_per_atom": (
                    f"{match['ehull']:.6f}" if match and match["ehull"] is not None else ""
                ),
                "mp_id_retrieved": today if match else "",
                "n_lattice_determinations": str(n),
                "note": (
                    "" if match else
                    "No Materials Project entry matched on (formula, space group); "
                    "id left empty rather than guessed."
                ),
            }
        )

    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    matched = sum(1 for r in rows if r["materials_project_id"])
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} phases, {matched} matched to an MP id")


if __name__ == "__main__":
    main()
