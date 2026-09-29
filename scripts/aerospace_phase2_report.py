"""Aerospace-durability Phase 2, report step. DEVELOPMENT / DESCRIPTIVE TIER — no verdict.

Reads reports/aerospace_phase2/<engine>.json (computed) and cache/external/aerospace/durability_rows.csv
(flight, gitignored) and writes:

  reports/aerospace_durability_development.md / .json   committed: computed values, flight COVERAGE and
                                                          locators only (the carried-over rule keeps
                                                          row-level flight data out of the public repo)
  cache/external/aerospace/development_side_by_side.md   gitignored: the same table with flight values

Every number in either file is computed here from those inputs at write time.

    .venv/bin/python scripts/aerospace_phase2_report.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINES = {"mace-mpa-0-medium": "MPA-0 (production)", "mace-mp-0-medium": "MP-0 (second)"}
ROWS = ROOT / "cache" / "external" / "aerospace" / "durability_rows.csv"
SIDE = ROOT / "cache" / "external" / "aerospace" / "development_side_by_side.md"
OUT_MD = ROOT / "reports" / "aerospace_durability_development.md"
OUT_JSON = ROOT / "reports" / "aerospace_durability_development.json"
SOURCES = {"ntrs_19930001391": "LDEF A0171 (NTRS 19930001391)", "ntrs_19950021220": "EOIM-3 / STS-46 (NTRS 19950021220)"}
# flight material label -> element whose oxides are computed
ELEMENT = {"Ag": "Ag", "Cu": "Cu", "Mo": "Mo", "Ti (75A)": "Ti", "Au": "Au", "Ni": "Ni", "Nb": "Nb", "Ta": "Ta",
           "W": "W", "V": "V", "V (pre-oxidized)": "V", "Al-Li 2090": "Al + Li", "Weldalite": "Al + Li"}


def o_per_m(formula: str, metal: str) -> float:
    from pymatgen.core import Composition
    c = Composition(formula)
    return c["O"] / c[metal]


def summarise(eng: dict) -> dict:
    out = {}
    for m, d in eng["metals"].items():
        ox = d["oxides"]
        neg = min(ox, key=lambda o: o["dEf_per_O_mp_eV"])
        hi = max(ox, key=lambda o: o_per_m(o["formula"], m))
        out[m] = {"n_stable_oxides": len(ox), "most_negative": neg["formula"], "most_negative_mp": neg["dEf_per_O_mp_eV"],
                  "most_negative_engine": neg.get("dEf_per_O_engine_eV"),
                  "highest_oxide": hi["formula"], "highest_oxide_mp": hi["dEf_per_O_mp_eV"],
                  "highest_oxide_engine": hi.get("dEf_per_O_engine_eV")}
    return out


def fmt(x, nd=3):
    return "—" if x is None else f"{x:+.{nd}f}" if nd else str(x)


def main() -> None:
    eng = {k: json.loads((ROOT / "reports" / "aerospace_phase2" / f"{k}.json").read_text()) for k in ENGINES}
    s = {k: summarise(v) for k, v in eng.items()}
    metals = list(eng["mace-mpa-0-medium"]["metals"])
    errs = {k: [o["engine_minus_mp_eV"] for d in v["metals"].values() for o in d["oxides"] if "engine_minus_mp_eV" in o]
            for k, v in eng.items()}
    n_ox = sum(len(d["oxides"]) for d in eng["mace-mpa-0-medium"]["metals"].values())
    n_conv = {k: sum(bool(o.get("converged")) for d in v["metals"].values() for o in d["oxides"]) for k, v in eng.items()}
    big = {k: sorted(((m, o["formula"], o["engine_minus_mp_eV"]) for m, d in v["metals"].items() for o in d["oxides"]
                      if abs(o.get("engine_minus_mp_eV", 0)) > 0.1), key=lambda t: -abs(t[2])) for k, v in eng.items()}
    rows = list(csv.DictReader(ROWS.open()))
    # EOIM-3 pure-metal mass changes within 2 x the printed +-0.02 mg balance uncertainty of zero
    pure = [r for r in rows if r["source_key"] == "ntrs_19950021220" and r["quantity"] == "dm_mg"
            and r["material"] not in ("Al-Li 2090", "Weldalite")]
    n_small = sum(abs(float(r["value"])) <= 2 * 0.02 for r in pure)
    rows_sha = hashlib.sha256(ROWS.read_bytes()).hexdigest()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    L = []
    w = L.append
    w("# Aerospace durability — development report")
    w("")
    w("> **DEVELOPMENT / DESCRIPTIVE TIER. Not a certified test.** No hypothesis was pre-registered, no")
    w("> threshold was selected or scored, and **no PASS/FAIL verdict is claimed**. Nothing here licenses a")
    w("> production change; no bundle change and no locked set follow from it.")
    w("")
    w(f"Generated {now} by `scripts/aerospace_phase2_report.py` from `reports/aerospace_phase2/*.json` and the")
    w(f"gitignored flight table (sha256 `{rows_sha}`). Every number is computed from those at write time.")
    w("")
    w("## What was compared, and what Phase 0 allowed")
    w("")
    w("The one static quantity the feasibility memo (`reports/aerospace_durability_feasibility.md`) allows for")
    w("this comparison is the **bulk oxide formation energy per O atom** on the harness's MP-corrected")
    w("convention: the thermodynamic driving force for oxidation. For each metal the flight rows cover, every")
    w("binary oxide on the MP GGA/GGA+U hull was relaxed with each engine and placed exactly as mode (a) places")
    w("a candidate (MP2020 corrections, MP's O reference). The O reference is shared by all metals, so its error")
    w("cannot reorder them.")
    w("")
    w("**Said plainly, where the comparison is limited by Phase 0:**")
    w("")
    w("- **Formation energy is not a rate.** The flight quantities are outcomes of oxide growth, spallation,")
    w("  temperature and flux over the exposure. Nothing computed here models any of that, so no agreement or")
    w("  disagreement below can be read as prediction.")
    w("- **Impact and cascade physics is left out entirely.** Both engines fail at close approach (memo §3), so")
    w("  no quantity involving an energetic O impact or a displacement cascade was computed.")
    w("- **Defect formation energies are left out.** Phase 0 found them usable, but neither flight source")
    w("  measures radiation damage, so there is no flight counterpart to set them against.")
    w("- **Surface chemisorption is left out.** The engine represents it statically (memo §2), but it was")
    w("  validated on one surface, Ag(111), and the flight samples are polycrystalline.")
    w("- **The Al-Li alloys are represented by Al and Li separately.** The source gives no composition, and")
    w("  attributes their mass loss to lithium loss, not oxidation.")
    w("")
    w("## Computed: oxide formation energy per O atom (eV)")
    w("")
    w(f"{n_ox} stable oxides across {len(metals)} elements. Converged relaxations: " +
      ", ".join(f"{ENGINES[k]} {n_conv[k]}/{n_ox}" for k in ENGINES) + ".")
    w("")
    w("| element | stable oxides | most negative per O | MP | MPA-0 | MP-0 | highest oxide | MP | MPA-0 | MP-0 |")
    w("|---|---:|---|---:|---:|---:|---|---:|---:|---:|")
    a, b = s["mace-mpa-0-medium"], s["mace-mp-0-medium"]
    for m in metals:
        w(f"| {m} | {a[m]['n_stable_oxides']} | {a[m]['most_negative']} | {fmt(a[m]['most_negative_mp'])} | "
          f"{fmt(a[m]['most_negative_engine'])} | {fmt(b[m]['most_negative_engine'])} | {a[m]['highest_oxide']} | "
          f"{fmt(a[m]['highest_oxide_mp'])} | {fmt(a[m]['highest_oxide_engine'])} | {fmt(b[m]['highest_oxide_engine'])} |")
    w("")
    w("\"Highest oxide\" is the stable oxide with the largest O:metal ratio, the assumption LDEF A0171 used to")
    w("normalise its reactivities (NTRS 19930001391, p. 467). Two picks need reading with care. For Ti, the most")
    w(f"negative per O is {a['Ti']['most_negative']}, a dilute interstitial suboxide rather than a surface scale. For")
    w(f"Li, the highest-ratio phase MP places on the hull is {a['Li']['highest_oxide']}.")
    w("")
    w("### Engine against MP, over every stable oxide")
    w("")
    w("| engine | n | median \\|engine − MP\\| | max \\|engine − MP\\| | oxides off by more than 0.1 eV/O |")
    w("|---|---:|---:|---:|---|")
    for k in ENGINES:
        e = errs[k]
        w(f"| {ENGINES[k]} | {len(e)} | {statistics.median(abs(x) for x in e):.3f} | {max(abs(x) for x in e):.3f} | "
          + (", ".join(f"{f} ({mm}) {d:+.3f}" for mm, f, d in big[k]) or "none") + " |")
    w("")
    w("Both engines were trained on MP-convention data, so agreement with MP measures convention fidelity, not")
    w("accuracy against experiment.")
    w("")
    w("## Flight coverage, split by source (values kept out of the public repo)")
    w("")
    w("The two sources measure different quantities under different exposures. **They are never pooled.** Per")
    w("the carried-over rule, row-level flight values stay gitignored. The side-by-side table with values is")
    w(f"`{SIDE.relative_to(ROOT)}`, regenerated by this script.")
    w("")
    cov = {}
    for src, label in SOURCES.items():
        sr = [r for r in rows if r["source_key"] == src]
        w(f"### {label}")
        w("")
        flu = sr[0]["fluence_atoms_per_cm2"]
        w(f"Mission: {sr[0]['mission']}; duration {sr[0]['duration']}; AO fluence "
          + (f"{float(flu):.2g} atoms/cm²." if flu else "not stated in the document."))
        w("")
        w("| flight sample | condition | quantities | computed element | locator |")
        w("|---|---|---|---|---|")
        seen, cov[src] = {}, []
        for r in sr:
            key = (r["material"], r["condition"], r["form"])
            seen.setdefault(key, []).append(r)
        for (mat, cond, form), rs in seen.items():
            qs = ", ".join(sorted({x["quantity"] for x in rs}))
            nulls = [x["quantity"] for x in rs if not x["value"]]
            w(f"| {mat}{' — ' + form if src == 'ntrs_19930001391' else ''} | {cond} | {qs}"
              f"{' (' + ', '.join(nulls) + ' ambiguous as printed)' if nulls else ''} | {ELEMENT[mat]} | {rs[0]['locator']} |")
            cov[src].append({"material": mat, "condition": cond, "quantities": qs.split(", "), "element": ELEMENT[mat]})
        w("")
    w("Computed elements with no LDEF counterpart and vice versa are visible above. Al and Li appear only")
    w("through EOIM-3's two alloys. **No flight row covers bare Al**, and **no source gives single-crystal")
    w("Ag/Cu numbers**: the EOIM-3 overview describes them, but neither document tabulates them.")
    w("")
    w("## Open decisions")
    w("")
    w("1. **Is the engine usable, or is a different tool needed?** Static energies, yes, at a descriptive tier")
    w("   and production engine only (memo). Everything the flight data measures is kinetic or impact-driven,")
    w("   so the real question needs MD with a short-range-corrected potential. **Not built; this is the")
    w("   recommendation coming back to you.**")
    w("2. **MISSE is not accessible,** and its metal fraction is unknown. `materialsinspace.nasa.gov` does not")
    w("   resolve. MAPTIS requires registration, paid for non-NASA users since January 2026. The public Glenn")
    w("   subset is polymers and coatings. Ingestion work is not justified unless access is arranged.")
    w("3. **Which alloy first?** The single-crystal Ag/Cu case has no numbers in any retrieved document. The")
    w("   usable choice is between EOIM-3's Al-Li rows and the pure metals:")
    w("   - **Al-Li rows:** structurally relevant, but composition-less, with alloy and temperature confounded")
    w("     and a Δm/A that cannot be reconstructed.")
    w(f"   - **Pure metals:** cleaner, but {n_small} of {len(pure)} pure-metal Δm values are within 2× the")
    w("     printed ±0.02 mg of zero.")
    w("4. **The paused stability-screening track** (f-electron confirmation, intermetallic, OQMD held-out):")
    w("   resume in parallel, or stay parked? Nothing here competes for its compute.")
    w("5. **Flight values in public reports.** The sources are US-Government public-use documents, and")
    w("   `reference_data/space_ao_erosion.csv` already commits MISSE-2 values, but this phase's rule kept them")
    w("   gitignored. Allow committing the side-by-side table?")
    OUT_MD.write_text("\n".join(L) + "\n")

    OUT_JSON.write_text(json.dumps({
        "tier": "development / descriptive — no verdict", "generated_at": now, "flight_rows_sha256": rows_sha,
        "engines": {k: {"checkpoint_sha256": v["checkpoint_sha256"], "dtype": v["dtype"], "settings_tag": v["settings_tag"]}
                    for k, v in eng.items()},
        "oxide_formation_per_O_eV": {k: s[k] for k in ENGINES},
        "engine_minus_mp": {k: {"n": len(e), "median_abs": statistics.median(abs(x) for x in e),
                                "max_abs": max(abs(x) for x in e)} for k, e in errs.items()},
        "flight_coverage": cov}, indent=1) + "\n")

    # gitignored: the same thing with the flight values
    S = [f"# Side-by-side (LOCAL ONLY — contains flight values; do not commit)\n\nGenerated {now}.\n"]
    for src, label in SOURCES.items():
        S.append(f"\n## {label}\n\n| sample | condition | quantity | value as printed | unit | element | MPA-0 most-negative ΔEf/O | MPA-0 highest-oxide ΔEf/O |\n|---|---|---|---|---|---|---:|---:|")
        for r in (r for r in rows if r["source_key"] == src):
            els = ELEMENT[r["material"]].split(" + ")
            v1 = " / ".join(fmt(a[e]["most_negative_engine"]) for e in els)
            v2 = " / ".join(fmt(a[e]["highest_oxide_engine"]) for e in els)
            S.append(f"| {r['material']} {r['form']} | {r['condition']} | {r['quantity']} | {r['value_as_printed']} | {r['unit']} | {'+'.join(els)} | {v1} | {v2} |")
    SIDE.write_text("\n".join(S) + "\n")
    print(OUT_MD.read_text())


if __name__ == "__main__":
    main()
