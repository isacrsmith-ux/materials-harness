"""Extract Table 4 (MISSE 2 PEACE Polymers Erosion Yield Data) from NASA/TM-2006-214482.

Source: de Groh, K. K., Banks, B. A., McCarthy, C. E., Rucker, R. N., Roberts, L. M.,
Berger, L. A., "MISSE PEACE Polymers Atomic Oxygen Erosion Results", NASA/TM-2006-214482,
NASA Glenn Research Center, 2006. Table 4, p. 17 (PDF page 21).
https://ntrs.nasa.gov/citations/20070002707  -- US Government work, public domain.

Run:  ./uvw run --with pypdf --no-project python reference_data/extract/misse2_peace.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "reference_data" / "raw" / "NASA-TM-2006-214482_MISSE2_PEACE.pdf"
OUT = ROOT / "reference_data" / "space_ao_erosion.csv"

CITATION_ID = "degroh2006_misse2_peace"

# Exposure conditions, all read from the report body (page numbers are PDF pages).
# p13: deployed 2001-08-16 on STS-105 at the ISS Quest Airlock.
# p13/p23: retrieved 2005-07-30 on STS-114.
# p19: "The average AO fluence ... was determined to be 8.43x10^21 atoms/cm2" (tray E5).
EXPOSURE = {
    "mission": "MISSE 2 (PEC 2, tray 1 E5), ISS exterior",
    "exposure_start": "2001-08-16",
    "exposure_end": "2005-07-30",
    "fluence_atoms_per_m2": 8.43e21 * 1e4,  # 8.43e21 atoms/cm^2 -> atoms/m^2
    "fluence_original": "8.43e21",
    "fluence_original_units": "atoms/cm^2",
}

# 2-E5-30 and 2-E5-33 are the Kapton H witness samples whose assumed erosion yield
# (3.0e-24 cm^3/atom, report p6/p18, citing its ref [4]) DEFINES the fluence above.
# Their listed yields are inputs to the calibration, not independent measurements.
WITNESS_SAMPLES = {"2-E5-30", "2-E5-33"}

# One row per sample. Serial numbers run 2-E5-6 .. 2-E5-46 (41 samples).
ROW = re.compile(
    r"(?P<serial>2-E5-\d+)\s+"
    r"(?P<rest>.*?)"
    r"(?P<mass>\d+\.\d+)\s+"
    r"(?P<density>\d+\.\d+)\s+"
    r"(?P<area>\d+\.\d+)\s+"
    r"(?P<gt>>\s*)?(?P<yield>\d\.\d+E-\d+)",
    re.S,
)


def table_text() -> str:
    import pypdf

    reader = pypdf.PdfReader(str(PDF))
    for page in reader.pages:
        text = page.extract_text() or ""
        if "Table 4" in text and "Erosion Yield Data" in text:
            return text
    raise SystemExit("Table 4 not found - is the vendored PDF the right report?")


def split_name(rest: str) -> tuple[str, str]:
    """The material name and its abbreviation share a cell pair; the abbreviation is the
    trailing parenthesised-or-capitalised token group. Names wrap across lines."""
    flat = " ".join(rest.split())
    # The abbreviation starts at the last run that looks like an acronym (ABS, PVF (Tedlar),
    # PI (Kapton H), PA 6). Anchor on the first token that is all-caps/digits after the name.
    m = re.search(r"\b([A-Z][A-Z0-9-]{1,7}(?:\s+\d+)?(?:\s*\([^)]*\))?)\s*$", flat)
    if not m:
        return flat, ""
    return flat[: m.start()].strip(), m.group(1).strip()


def main() -> None:
    rows = []
    for m in ROW.finditer(table_text()):
        name, abbrev = split_name(m.group("rest"))
        serial = m.group("serial")
        yield_cm3 = float(m.group("yield"))
        rows.append(
            {
                "material_key": f"misse2:{serial}",
                "sample_id": serial,
                "material_name": name,
                "abbreviation": abbrev,
                # cm^3/atom -> m^3/atom
                "erosion_yield_m3_per_atom": f"{yield_cm3 * 1e-6:.6e}",
                "erosion_yield_original": m.group("yield"),
                "original_units": "cm^3/atom",
                # ">" in the source: sample partially or completely eroded, so the printed
                # yield is a LOWER BOUND (report p20: "partial or complete erosion of 6 of the 41").
                "is_lower_bound": "true" if m.group("gt") else "false",
                "mass_loss_kg": f"{float(m.group('mass')) * 1e-3:.9f}",
                "mass_loss_original_g": m.group("mass"),
                "density_kg_per_m3": f"{float(m.group('density')) * 1e3:.1f}",
                "density_original_g_per_cm3": m.group("density"),
                "area_m2": f"{float(m.group('area')) * 1e-4:.8f}",
                "area_original_cm2": m.group("area"),
                **EXPOSURE,
                "is_fluence_witness": "true" if serial in WITNESS_SAMPLES else "false",
                "source_key": CITATION_ID,
                "source_locator": "Table 4, p. 17 (PDF p. 21)",
                "status": "verified",
                "note": (
                    "Fluence witness sample; its erosion yield is the assumed calibration "
                    "constant (3.0e-24 cm^3/atom) used to derive the fluence, not an "
                    "independent measurement."
                    if serial in WITNESS_SAMPLES
                    else ""
                ),
            }
        )

    if len(rows) != 41:
        raise SystemExit(f"expected 41 samples, parsed {len(rows)} - check the table regex")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    bounds = sum(r["is_lower_bound"] == "true" for r in rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows, {bounds} lower bounds")


if __name__ == "__main__":
    main()
