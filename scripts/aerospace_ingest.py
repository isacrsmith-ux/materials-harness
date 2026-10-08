"""Aerospace-durability Phase 1: normalise the flight-exposure metal data into one schema.

The sources are a handful of scanned NTRS PDFs, not an API, so this is a plain script rather than a
harness module. Row-level values stay gitignored under cache/external/aerospace/:

    cache/external/aerospace/ntrs/*.pdf          the documents (sha256-pinned below)
    cache/external/aerospace/transcription.json  values as printed, with a locator per row
    cache/external/aerospace/durability_rows.csv  output: one row per (sample, quantity)

What is committed is this script and reports/aerospace_phase1_ingest.json (hashes, counts, checks —
no values). Run:  ./uvw run --with pypdf python scripts/aerospace_ingest.py

Literature session (2026-10-07) adds seven NTRS sources through cache/external/aerospace/transcription_v2.json
(same discipline: values read off the page images, a locator per row, refuse-to-write checks) and a
`quantity_kind` column. The Phase 1 rows are rebuilt unchanged: durability_rows.csv keeps its original bytes and
its hash is pinned below; the superset goes to durability_rows_v2.csv. Rows are poolable only within one
(quantity_kind, quantity, unit) and only if all are measured or all are upper bounds (assert_poolable).

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
import io
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "external" / "aerospace"
OUT_ROWS = CACHE / "durability_rows.csv"
OUT_REPORT = ROOT / "reports" / "aerospace_phase1_ingest.json"
V2_TRANSCRIPTION = CACHE / "transcription_v2.json"
OUT_ROWS_V2 = CACHE / "durability_rows_v2.csv"
PHASE1_ROWS_SHA256 = "b1b352d80d14025a0a9d4eac4a8e62b85a8b01d09b758fd7a220948d6a81bebe"  # committed in 8cb98f6
LEGACY_KIND = {"accommodation": "accommodation", "reactivity": "reactivity", "dm_mg": "mass_change",
               "dm_per_area_mg_cm2": "mass_change"}
V2_MISSIONS = {
    "ntrs_19930001392": ("LDEF (UHCRE experiment trays)", "almost 6 years (p. 479)"),
    "ntrs_19930019095": ("LDEF experiment A0114", "nearly six years (p. 1170)"),
    "ntrs_19970025577": ("EOIM-3, STS-46 (NASA Lewis hardware)", "42 h bay-to-ram at 229 km (p. 2)"),
    "ntrs_20100033233": ("MISSE-6 (ISS)", "ESH and AO fluence as printed per row"),
}
V2_EXTRA_COLS = ["quantity_kind", "is_upper_bound", "detection_limit", "specimen_id", "oxide_phase", "extra_json"]

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


def pool_key(r: dict) -> tuple:
    return (r["quantity_kind"], r["quantity"], r["unit"])


def assert_poolable(rows: list[dict]) -> None:
    """Rows of different kinds or quantities are different measurements and are never pooled; an upper bound
    (a detection limit) is not a measurement and is never pooled with measured values."""
    if len({pool_key(r) for r in rows}) > 1:
        raise ValueError(f"refusing to pool different quantities: {sorted({pool_key(r) for r in rows})}")
    if len({bool(r.get("is_upper_bound")) for r in rows}) > 1:
        raise ValueError("refusing to pool upper bounds with measured values")


def norm(s: str) -> str:
    """OCR-tolerant form: no whitespace or signs, O->0, l/I->1 (the scans read 'E10' as 'El0')."""
    s = re.sub(r"[\s+\-\u2212\u2013]", "", s)
    return s.replace("O", "0").replace("l", "1").replace("I", "1")


def parse_v2(s: str) -> float | None:
    s = s.strip()
    if m := re.fullmatch(r"([\d.]+) x 10\^(0\d+)", s):
        return None  # exponent printed with a leading zero: not interpreted
    if m := re.fullmatch(r"([\d.]+) x 10\^(-?\d+)", s):
        return float(m[1]) * 10 ** int(m[2])
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", s):
        return float(s)
    if s == "-":
        return 0.0  # a dash in a delta column: pre = post as printed
    return None  # ranges, 'No change', '(not tabulated)'


def ingest_literature(report: dict, legacy_rows: list[dict], legacy_cols: list[str]) -> None:
    t = json.loads(V2_TRANSCRIPTION.read_text())
    docs = {}
    for key, d in t["documents"].items():
        got = sha256(CACHE / d["pdf"])
        if got != d["sha256"]:
            raise SystemExit(f"{key}: sha256 {got} != pinned {d['sha256']}")
        docs[key] = {"sha256": got, "pdf": d["pdf"]}
    report["documents_literature_session"] = docs

    pages = {}

    def page_text(doc: str, pdf_page: int) -> str:
        if (doc, pdf_page) not in pages:
            pages[(doc, pdf_page)] = norm(PdfReader(CACHE / docs[doc]["pdf"]).pages[pdf_page - 1].extract_text() or "")
        return pages[(doc, pdf_page)]

    rows, confirmed, dropped = [], {}, {}
    for r in t["rows"]:
        doc = r["doc"]
        mission, duration = V2_MISSIONS[doc]
        fl = r["fluence_as_printed"]
        v = parse_v2(r["value_as_printed"])
        if r["quantity_kind"] == "mass_change":
            v = r["detection_limit"] if r["is_upper_bound"] else r["extra"]["appendix_dm_mg"]
        if r["ocr_row"] is not None:
            ok = norm(r["ocr_row"]) in page_text(doc, r["pdf_page"])
            (confirmed if ok else dropped)[doc] = (confirmed if ok else dropped).get(doc, 0) + 1
        rows.append({
            "source_key": doc, "ntrs_id": doc.split("_")[1], "locator": r["locator"], "material": r["material"],
            "composition": f"{r['material']} (as named in source; composition not tabulated)", "form": r["form"],
            "mission": mission, "duration": duration, "fluence_atoms_per_cm2": parse_v2(fl) if fl else None,
            "condition": r["condition"], "quantity": r["quantity"], "value": v, "value_as_printed": r["value_as_printed"],
            "unit": r["unit"], "uncertainty_as_printed": r["uncertainty_as_printed"], "flag": r["flag"],
            "quantity_kind": r["quantity_kind"], "is_upper_bound": bool(r["is_upper_bound"]),
            "detection_limit": r["detection_limit"], "specimen_id": r["specimen_id"], "oxide_phase": r["oxide_phase"],
            "extra_json": json.dumps(r["extra"], sort_keys=True)})
    by = lambda doc, **kw: [x for x, tr in zip(rows, t["rows"]) if tr["doc"] == doc and all(x[k] == w for k, w in kw.items())]
    ci, mism = t["check_inputs"], []

    # --- de Rooij: Table II average = mean of the X-ray and Auger columns (to the print's rounding); text vs table
    d_ok = []
    for sid in sorted({x["specimen_id"] for x in rows if x["source_key"] == "ntrs_19930001392" and x["value"] is not None}):
        q = {x["quantity"]: x["value"] for x in by("ntrs_19930001392", specimen_id=sid)}
        d_ok.append(abs(q["oxide_thickness_average_A"] - (q["oxide_thickness_xray_A"] + q["oxide_thickness_auger_xps_A"]) / 2) <= 1.0)
    e10 = {x["quantity"]: x["value"] for x in by("ntrs_19930001392", specimen_id="E10")}
    text_ok = (e10["oxide_thickness_xray_A"] == ci["derooij"]["E10_xray_text_A"]
               and ci["derooij"]["E10_auger_text_range_A"][0] <= e10["oxide_thickness_auger_xps_A"] <= ci["derooij"]["E10_auger_text_range_A"][1])
    fl_vals = [x["fluence_atoms_per_cm2"] for x in rows if x["source_key"] == "ntrs_19930001392" and x["oxide_phase"]]
    if not (all(d_ok) and text_ok):
        raise SystemExit("de Rooij: Table II average / text-vs-table check failed: transcription error")

    # --- Raikar: the source's own Pilling-Bedworth relation (Table 1 densities) must reproduce its stated numbers
    rk = {x["quantity"]: x["value"] for x in rows if x["source_key"] == "ntrs_19930019095" and x["specimen_id"] == "C9-16"}
    tb = ci["raikar"]["table1"]
    vr2 = (tb["Cu2O"]["M"] / tb["Cu2O"]["rho"]) / (2 * tb["Cu"]["M"] / tb["Cu"]["rho"])
    vr1 = lambda rho: (tb["CuO"]["M"] / rho) / (tb["Cu"]["M"] / tb["Cu"]["rho"])
    t0, t1 = rk["film_thickness_unexposed_nm"], rk["film_thickness_exposed_nm"]
    consumed = (t1 - t0) / (vr2 - 1)
    r_checks = {
        "full_conversion_cu2o_reproduced": abs(t0 * vr2 - ci["raikar"]["full_conversion_cu2o_nm_stated"]) < 1.0,
        "full_conversion_cuo_within_stated_density_range": min(t0 * vr1(tb["CuO"]["rho_hi"]), t0 * vr1(tb["CuO"]["rho_lo"])) - 1
        <= ci["raikar"]["full_conversion_cuo_nm_stated"] <= max(t0 * vr1(tb["CuO"]["rho_hi"]), t0 * vr1(tb["CuO"]["rho_lo"])) + 1,
        "cu_consumed_reproduced": abs(consumed - rk["cu_consumed_nm"]) < 1.0,
        "cu2o_thickness_reproduced": abs(consumed * vr2 - rk["cu2o_thickness_nm"]) < 1.0,
        "cu_unoxidised_reproduced": abs((t0 - consumed) - rk["cu_unoxidised_nm"]) < 1.0,
    }
    if not all(r_checks.values()):
        raise SystemExit(f"Raikar: Pilling-Bedworth relation does not reproduce the stated numbers: {r_checks}")
    step, sig_step = rk["profilometer_step_height_nm"], 0.5
    diff = t1 - t0
    mism.append({"id": "raikar_step_height_vs_film_thickness_difference", "source": "ntrs_19930019095",
                 "what": "text says the mask-edge step is 'in agreement with the difference in total film thickness'",
                 "relative_discrepancy": round(abs(diff - step) / diff, 3),
                 "in_combined_sigma": round(abs(diff - step) / (sig_step ** 2 + 1.0 ** 2 + 1.0 ** 2) ** 0.5, 2)})
    mism.append({"id": "raikar_percent_greater_statement", "source": "ntrs_19930019095",
                 "what": "text says the exposed film is '40% greater' than the unexposed one",
                 "printed_percent": ci["raikar"]["percent_greater_stated"], "from_printed_thicknesses_percent": round(100 * (t1 / t0 - 1), 1)})

    # --- Morton: fluence per sample; Appendix A change = post - pre (print rounding); Table II vs Appendix A
    m = ci["morton"]
    m_checks = {"per_sample_fluence_reproduced": abs(m["fluence_cm2"] * m["area_cm2"] - m["per_sample_fluence"]) / m["per_sample_fluence"] < 0.01}
    mass = [x for x in rows if x["source_key"] == "ntrs_19970025577" and x["quantity"] == "dm_mg"]
    ex = [json.loads(x["extra_json"]) for x in mass]
    m_checks["appendix_change_equals_post_minus_pre"] = all(abs(float(e["post_g"]) - float(e["pre_g"]) - float(e["appendix_dm_g"])) < 1.5e-5 for e in ex)
    m_checks["no_detectable_rows_below_limit"] = all(abs(e["appendix_dm_mg"]) < 0.1 for x, e in zip(mass, ex) if x["is_upper_bound"])
    m_checks["quantified_rows_match_table_ii"] = all(
        abs(abs(e["appendix_dm_mg"]) - float(re.search(r"([\d.]+) mg", e["tableII_status"])[1])) <= 0.051
        for x, e in zip(mass, ex) if not x["is_upper_bound"])
    ctl = [abs(e["control_dm_mg"]) for e in ex]
    m_checks["control_max_abs_dm_mg_below_limit"] = max(ctl) < 0.1
    if not all(m_checks.values()):
        raise SystemExit(f"Morton checks failed: {m_checks}")

    # --- MISSE-6: printed delta = post - pre
    ms = [json.loads(x["extra_json"]) for x in rows if x["source_key"] == "ntrs_20100033233"]
    ms_ok = all(abs((float(e["post"]) - float(e["pre"])) - (0.0 if e["printed_delta"] == "-" else float(e["printed_delta"]))) < 0.0051 for e in ms)
    if not ms_ok:
        raise SystemExit("MISSE-6: printed delta != post - pre for some row")

    # --- duplicate: CR-192306 encloses the same Raikar paper
    dup = {k: sum(n in norm(" ".join((PdfReader(CACHE / docs[k]["pdf"]).pages[i].extract_text() or "") for i in range(len(PdfReader(CACHE / docs[k]["pdf"]).pages)))) for n in map(norm, ci["duplicate_needles"]))
           for k in ("ntrs_19930019095", "ntrs_19930011567")}
    if dup["ntrs_19930019095"] != dup["ntrs_19930011567"]:
        raise SystemExit(f"CR-192306 does not carry the same Raikar numbers: {dup}")

    # --- cross-source
    mism.append({"id": "eoim3_fluence_two_sources", "source": "ntrs_19950021220 vs ntrs_19970025577",
                 "what": "EOIM-3 total AO fluence as printed by the MSFC paper and by the Lewis memorandum (preliminary mass spectrometer value)",
                 "relative_difference": round(abs(2.3e20 - 2.2e20) / 2.25e20, 3)})

    # --- legacy rows in the v2 schema; their CSV must still hash to the committed value
    all_rows = []
    for r in legacy_rows:
        all_rows.append({**r, "quantity_kind": LEGACY_KIND[r["quantity"]], "is_upper_bound": False, "detection_limit": None,
                         "specimen_id": "", "oxide_phase": "", "extra_json": "{}"})
    all_rows += rows
    cols = legacy_cols + V2_EXTRA_COLS
    with OUT_ROWS_V2.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows({c: r.get(c) for c in cols} for r in all_rows)
    kinds = sorted({r["quantity_kind"] for r in all_rows})
    report["literature_session"] = {
        "tier": "development / descriptive, no verdict",
        "checks": {
            "pdf_sha256_all_match": True,
            "ocr_row_confirmed_by_source": confirmed, "ocr_row_dropped_or_garbled": dropped,
            "derooij_table_ii_average_equals_mean_of_methods": f"{sum(d_ok)}/{len(d_ok)}",
            "derooij_text_vs_table_E10": text_ok,
            "raikar_pilling_bedworth_relation": r_checks,
            "morton": m_checks,
            "misse6_printed_delta_equals_post_minus_pre": f"{len(ms)}/{len(ms)}",
            "cr192306_carries_same_raikar_numbers": dup,
            "derooij_fluence_exponent_printed_with_leading_zero": sum(1 for x in rows if x["source_key"] == "ntrs_19930001392"
                                                                      and x["oxide_phase"] and x["fluence_atoms_per_cm2"] is None
                                                                      and x["specimen_id"] == "E02") > 0,
        },
        "recorded_mismatches_not_corrected": mism,
        "counts": {"rows": len(all_rows), "new_rows": len(rows),
                   "by_quantity_kind": {k: sum(r["quantity_kind"] == k for r in all_rows) for k in kinds},
                   "by_source": {k: sum(r["source_key"] == k for r in all_rows) for k in sorted({r["source_key"] for r in all_rows})},
                   "upper_bound_rows": sum(r["is_upper_bound"] for r in all_rows),
                   "null_values": sum(r["value"] is None for r in all_rows),
                   "pooling_groups": len({pool_key(r) for r in all_rows}),
                   "qualitative_notes": len(t["notes"])},
        "rule": "rows are pooled only within one (quantity_kind, quantity, unit), never across kinds, and never mixing "
                "measured values with upper bounds (assert_poolable)",
    }
    report["rows_sha256"] = sha256(OUT_ROWS_V2)


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
    legacy_cols = list(rows[0])
    with OUT_ROWS.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=legacy_cols)
        w.writeheader()
        w.writerows(rows)
    report["phase1_rows_sha256"] = sha256(OUT_ROWS)
    if report["phase1_rows_sha256"] != PHASE1_ROWS_SHA256:
        raise SystemExit(f"Phase 1 rows no longer rebuild to the committed hash: {report['phase1_rows_sha256']}")
    ingest_literature(report, rows, legacy_cols)
    OUT_REPORT.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
