"""Aerospace-durability Phase 1: normalise the flight-exposure metal data into one schema.

The sources are a handful of scanned NTRS PDFs, not an API, so this is a plain script rather than a
harness module. Row-level values stay gitignored under cache/external/aerospace/:

    cache/external/aerospace/ntrs/*.pdf          the documents (sha256-pinned below)
    cache/external/aerospace/transcription.json  values as printed, with a locator per row
    cache/external/aerospace/durability_rows.csv  output: one row per (sample, quantity)

What is committed is this script and reports/aerospace_phase1_ingest.json (hashes, counts, checks —
no values). Run:  ./uvw run --with pypdf python scripts/aerospace_ingest.py

Checks, all of which must pass or the script refuses to write:
  1. every PDF matches its pinned sha256;
  2. every transcribed mantissa that the OCR text layer still carries is found on the cited page
     (cells the OCR dropped are counted, not failed — that is why the transcription exists);
  3. EOIM-3 pure metals: dm / 0.71 cm^2 (exposed area, p. 1055) reproduces the printed dm/A, allowing
     for dm being printed to 0.01 mg (a column error, e.g. a swapped row, still fails).
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "external" / "aerospace"
OUT_ROWS = CACHE / "durability_rows.csv"
OUT_REPORT = ROOT / "reports" / "aerospace_phase1_ingest.json"

# Exposure conditions as stated in each document (locators in the comments). None = not stated there.
MISSIONS = {
    "ntrs_19930001391": {"mission": "LDEF experiment A0171", "duration": "5.8 years (p. 467)",
                         "fluence_atoms_per_cm2": None, "page_index": 4},
    "ntrs_19950021220": {"mission": "EOIM-3, STS-46", "duration": "42 h in velocity vector (p. 1053)",
                         "fluence_atoms_per_cm2": 2.2e20,  # p. 1054
                         "page_index": 3},
}
EOIM_PURE_METAL_AREA_CM2 = 0.71  # p. 1055, "All the pure metals had an exposed area of 0.71 cm2"
EOIM_UNCERTAINTY = {"dm_mg": "±0.02", "dm_per_area_mg_cm2": "±0.03"}  # Table I column heads
COMPOSITION = {"Ag": "Ag", "Cu": "Cu", "Mo": "Mo", "Au": "Au", "Ni": "Ni", "Nb": "Nb", "Ta": "Ta", "W": "W",
               "V": "V", "V (pre-oxidized)": "V", "Ti (75A)": "Ti (commercially pure grade 75A)",
               "Al-Li 2090": "Al-Li alloy 2090 (composition not given in source)",
               "Weldalite": "Weldalite Al-Li alloy (composition not given in source)"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_printed(s: str) -> float | None:
    """'3.6 x 10^-26' -> 3.6e-26; '1/10^3' -> 1e-3; '+0.23' -> 0.23. Ambiguous forms return None."""
    s = s.strip()
    if m := re.fullmatch(r"([\d.]+) x 10\^(-?\d+)", s):
        return float(m[1]) * 10 ** int(m[2])
    if m := re.fullmatch(r"(\d+)/10\^(\d+)", s):
        return int(m[1]) / 10 ** int(m[2])
    if re.fullmatch(r"[+-]?\d*\.\d+", s):
        return float(s)
    return None  # e.g. '9/2 x 10^5': (9/2)x10^5 or 9/(2x10^5) cannot be told apart from the print


def ocr_tokens(pdf: Path, page_index: int) -> str:
    text = PdfReader(pdf).pages[page_index].extract_text() or ""
    return re.sub(r"\s+", "", text.replace("O", "0"))


def mantissa(s: str) -> str:
    return re.sub(r"\s+", "", s.split(" x ")[0].split("/")[0].lstrip("+"))


def main() -> None:
    t = json.loads((CACHE / "transcription.json").read_text())
    report = {"documents": {}, "checks": {}, "counts": {}}
    for key, d in t["documents"].items():
        got = sha256(CACHE / d["pdf"])
        if got != d["sha256"]:
            raise SystemExit(f"{key}: sha256 {got} != pinned {d['sha256']}")
        report["documents"][key] = {"sha256": got, "pdf": d["pdf"]}

    ocr = {k: ocr_tokens(CACHE / d["pdf"], MISSIONS[k]["page_index"]) for k, d in t["documents"].items()}
    found = missing = 0
    rows, area_checks, implied_areas = [], [], {}
    for r in t["rows"]:
        m = MISSIONS[r["doc"]]
        base = {"source_key": r["doc"], "ntrs_id": r["doc"].split("_")[1], "locator": r["locator"],
                "material": r["material"], "composition": COMPOSITION[r["material"]],
                "form": r.get("form", "bulk sheet/shim stock (p. 1054)" if r["doc"] == "ntrs_19950021220" else ""),
                "mission": m["mission"], "duration": m["duration"], "fluence_atoms_per_cm2": m["fluence_atoms_per_cm2"],
                "condition": r.get("condition") or f"EOIM-3 {r['tray']} tray"}
        for q, unit in (("accommodation_printed", "reacted/incident O atoms"), ("reactivity_printed", "cm^3/atom"),
                        ("dm_mg", "mg"), ("dm_per_area_mg_cm2", "mg/cm^2")):
            if q not in r:
                continue
            printed = r[q]
            if mantissa(printed).replace("0", "") and mantissa(printed) in ocr[r["doc"]]:
                found += 1
            else:
                missing += 1
            v = parse_printed(printed)
            rows.append({**base, "quantity": q.removesuffix("_printed"), "value": v, "value_as_printed": printed,
                         "unit": unit, "uncertainty_as_printed": EOIM_UNCERTAINTY.get(q, ""),
                         "flag": "" if v is not None else "ambiguous as printed; value left null"})
        if "dm_mg" in r:
            dm, dma = float(r["dm_mg"]), float(r["dm_per_area_mg_cm2"])
            if r["material"] in ("Al-Li 2090", "Weldalite"):
                implied_areas.setdefault(r["material"], []).append(round(dm / dma, 2))
            else:
                # dm is printed to 0.01 mg, so the true dm lies within +-0.005 mg of it; dm/A is printed
                # to 0.001. The check passes iff the printed dm/A is reachable from some dm in that interval.
                ok = abs(dm / EOIM_PURE_METAL_AREA_CM2 - dma) <= 0.005 / EOIM_PURE_METAL_AREA_CM2 + 0.0005
                area_checks.append(ok)

    if not all(area_checks):
        raise SystemExit("EOIM-3 dm/A does not reproduce dm/0.71 for every pure metal: transcription error")
    report["checks"] = {
        "pdf_sha256_all_match": True,
        "transcribed_values_confirmed_by_ocr": found,
        "transcribed_values_ocr_dropped_or_garbled": missing,
        "eoim3_pure_metal_dm_over_area_reproduced": f"{sum(area_checks)}/{len(area_checks)}",
        "eoim3_al_li_implied_exposed_area_cm2": implied_areas,
    }
    report["counts"] = {
        "rows": len(rows),
        "by_source": {k: sum(r["source_key"] == k for r in rows) for k in MISSIONS},
        "by_quantity": {q: sum(r["quantity"] == q for r in rows) for q in sorted({r["quantity"] for r in rows})},
        "null_values": sum(r["value"] is None for r in rows),
        "materials": sorted({r["material"] for r in rows}),
    }
    with OUT_ROWS.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    report["rows_sha256"] = sha256(OUT_ROWS)
    OUT_REPORT.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
