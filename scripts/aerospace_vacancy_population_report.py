"""Aerospace lit session Phase C report: engine vacancy energies against the Angsten et al. PBE population.

Reads reports/aerospace_vacancy_population/<engine>.json (scripts/aerospace_vacancy_population.py) and the
reference tables in the captured open-access page, writes reports/aerospace_vacancy_population.md / .json.
Both the reference values (CC BY 3.0, Angsten et al. 2014) and the engine values are computed or literature
numbers, not flight data, so the per-element tables are committed.

Run:  .venv/bin/python scripts/aerospace_vacancy_population_report.py
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("avp", ROOT / "scripts" / "aerospace_vacancy_population.py")
avp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(avp)

ENGINES = {"mace-mpa-0-medium": "MPA-0 (production)", "mace-mp-0-medium": "MP-0 (second)"}
OUTLIER_EV = 0.2  # a reporting convenience fixed before the report was written: ~7x the paper's stated 20-30 meV size error
NATURAL = {("Al", "fcc"), ("Cu", "fcc"), ("Ag", "fcc"), ("Ni", "fcc"), ("Mg", "hcp"), ("Ti", "hcp")}  # the brief's six elements in their usual structure
OUT_JSON = ROOT / "reports" / "aerospace_vacancy_population.json"
OUT_MD = ROOT / "reports" / "aerospace_vacancy_population.md"


def key(r: dict) -> str:
    return f"{r['structure']}:{r['symbol']}{':mag' if r['magnetic_variant'] else ''}"


def stats(d: np.ndarray) -> dict:
    a = np.abs(d)
    return {"n": int(len(d)), "median_abs_eV": round(float(np.median(a)), 3), "mean_abs_eV": round(float(a.mean()), 3),
            "max_abs_eV": round(float(a.max()), 3), "median_signed_eV": round(float(np.median(d)), 3),
            "within_0.05_eV": int((a <= 0.05).sum()), "within_0.1_eV": int((a <= 0.1).sum()),
            f"over_{OUTLIER_EV}_eV": int((a > OUTLIER_EV).sum())}


def main() -> None:
    rows = avp.parse_angsten()
    avp.check_parse(rows)
    keep, drop = avp.select_population(rows)
    ref = {key(r): r for r in keep}
    data = {e: json.loads((avp.OUTDIR / f"{e}.json").read_text()) for e in ENGINES}
    checkpoint = {e: d["checkpoint_sha256"] for e, d in data.items()}
    html_sha = {d["reference_html_sha256"] for d in data.values()}
    assert len(html_sha) == 1 and html_sha == {avp.sha256(avp.LANDING)}
    # --- primary comparison: the paper's own cell and protocol (runs[0] is always paper cell, fixed_cell)
    per = {}
    for k, r in ref.items():
        rec = {"symbol": r["symbol"], "structure": r["structure"], "magnetic": r["magnetic_variant"], "ref_Hvf": r["Hvf_eV"],
               "ref_Hvf_nonmagnetic": r.get("Hvf_nonmagnetic_eV"), "ref_Hvm": r["Hvm_eV"], "ref_Hvm_c": r["Hvm_c_eV"]}
        for e, d in data.items():
            p = d["pairs"].get(k)
            if p is None or "error" in p or not p["runs"][0]["converged"]:
                rec[e] = None
                continue
            rec[e] = {"Hvf": p["runs"][0]["E_f_eV"], "N": p["runs"][0]["N"], "migration": p.get("migration"),
                      "runs": p["runs"], "wall_s": p.get("wall_s")}
        per[k] = rec
    failed = {e: sorted(k for k, v in per.items() if v[e] is None) for e in ENGINES}
    both = [k for k, v in per.items() if all(v[e] is not None for e in ENGINES)]
    out = {"tier": "development / descriptive evidence, no verdict", "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "reference": "Angsten, Mayeshiba, Wu, Morgan, New J. Phys. 16, 015018 (2014), Tables A.1/A.2; PBE DFT, not experiment",
           "reference_html_sha256": html_sha.pop(), "checkpoint_sha256": checkpoint,
           "population": {"table_rows": len(rows), "in_population": len(keep), "excluded": len(drop),
                          "excluded_by_reason": {r: sum(d["excluded_because"].split(":")[0] == r for d in drop) for r in sorted({d["excluded_because"].split(":")[0] for d in drop})},
                          "fcc": sum(r["structure"] == "fcc" for r in keep), "hcp": sum(r["structure"] == "hcp" for r in keep)},
           "not_computed_or_not_converged": failed, "outlier_threshold_eV": OUTLIER_EV, "stats": {}}
    diffs = {}
    for e in ENGINES:
        sel = [k for k, v in per.items() if v[e] is not None]
        d = np.array([per[k][e]["Hvf"] - per[k]["ref_Hvf"] for k in sel])
        diffs[e] = dict(zip(sel, d))
        out["stats"][e] = {"all": stats(d)}
        for st in ("fcc", "hcp"):
            ss = [k for k in sel if per[k]["structure"] == st]
            out["stats"][e][st] = stats(np.array([diffs[e][k] for k in ss]))
        nat = [k for k in sel if (per[k]["symbol"], per[k]["structure"]) in NATURAL]
        out["stats"][e]["six_focus_elements"] = stats(np.array([diffs[e][k] for k in nat]))
        out["stats"][e]["wall_s"] = round(sum(per[k][e]["wall_s"] or 0 for k in sel), 0)
    # same-population comparison for the two engines
    out["stats_common"] = {e: stats(np.array([diffs[e][k] for k in both])) for e in ENGINES}
    out["outliers"] = {e: sorted(([k, round(float(v), 3)] for k, v in diffs[e].items() if abs(v) > OUTLIER_EV), key=lambda x: -abs(x[1])) for e in ENGINES}
    # --- the engines against each other
    eng = list(ENGINES)
    dd = np.array([per[k][eng[0]]["Hvf"] - per[k][eng[1]]["Hvf"] for k in both])
    out["engine_vs_engine"] = stats(dd)
    # --- convergence for the focus elements: spread across cells and modes
    conv = {}
    for k, v in per.items():
        if (v["symbol"], v["structure"]) not in NATURAL:
            continue
        conv[k] = {"ref_Hvf": v["ref_Hvf"]}
        for e in ENGINES:
            if v[e] is None:
                continue
            vals = [(r["N"], r["mode"], round(r["E_f_eV"], 3), r["converged"]) for r in v[e]["runs"]]
            conv[k][e] = {"runs": vals, "spread_eV": round(max(x[2] for x in vals) - min(x[2] for x in vals), 3),
                          "largest_cell_zero_pressure": [x[2] for x in vals if x[1] == "zero_pressure"][-1]}
    out["focus_convergence"] = conv
    # --- sanity: did the engine's relaxed 2- or 4-atom cell stay near the paper's tabulated atomic volume? (catches structure collapse)
    vol = {}
    for e in ENGINES:
        bad, ratios = [], []
        for k, v in per.items():
            if v[e] is None:
                continue
            L = v[e]["runs"][0]["cell_lengths_A"]
            omega = L[0] ** 3 / 4 if v["structure"] == "fcc" else L[0] ** 2 * L[2] * np.sin(np.pi / 3) / 2
            ratios.append(omega / ref[k]["omega_A3"])
            if abs(ratios[-1] - 1) > 0.10:
                bad.append([k, round(ratios[-1], 3)])
        vol[e] = {"median_ratio": round(float(np.median(ratios)), 3), "min_ratio": round(min(ratios), 3), "max_ratio": round(max(ratios), 3),
                  "pairs_off_by_more_than_10pct": sorted(bad, key=lambda x: -abs(x[1] - 1))}
    out["volume_check_engine_over_paper"] = vol
    # --- cross-checks read from the repo at write time: Phase 0's Al values, and the memo's PBE Al reference
    memo = (ROOT / "reports" / "aerospace_durability_feasibility.md").read_text()
    line = next(l for l in memo.splitlines() if l.startswith("| vacancy formation |"))
    hood_pbe = float(line.split("|")[4].strip())  # columns: label, MPA-0, MP-0, PBE, DMC, experiment
    ph0 = {}
    for e in ENGINES:
        a0 = json.loads((ROOT / "reports" / "aerospace_phase0" / f"{e}.json").read_text())["al_defects"]["by_mode"]
        now = {(r["N"], r["mode"]): r["E_f_eV"] for r in (data[e]["pairs"]["fcc:Al"]["runs"])}
        ph0[e] = {f"{mode}_{n}": round(abs(now[(int(n), mode)] - a0[mode][n]["vacancy"]["E_f_eV"]), 4)
                  for mode in ("fixed_cell", "zero_pressure") for n in ("108", "256", "500") if (int(n), mode) in now}
    out["phase0_al_vacancy_reproduced_abs_diff_eV"] = ph0
    out["al_reference_values_eV"] = {"angsten_table_A1": per["fcc:Al"]["ref_Hvf"], "hood_pbe_from_phase0_memo": hood_pbe}
    OUT_JSON.write_text(json.dumps(out, indent=1) + "\n")
    # --- migration (stretch): fcc hop vs H_vm; hcp in-plane vs H_vm-perp, out-of-plane vs H_vm-par
    mig = {}
    for e in ENGINES:
        pairs = []
        for k, v in per.items():
            m = v[e] and v[e]["migration"]
            if not m:
                continue
            if v["structure"] == "fcc" and v["ref_Hvm"] is not None and "hop" in m and m["hop"].get("converged"):
                pairs.append((k, "hop", m["hop"]["Hvm_eV"], v["ref_Hvm"]))
            if v["structure"] == "hcp":
                if v["ref_Hvm"] is not None and "in_plane" in m and m["in_plane"].get("converged"):
                    pairs.append((k, "in_plane", m["in_plane"]["Hvm_eV"], v["ref_Hvm"]))
                if v["ref_Hvm_c"] is not None and "out_of_plane" in m and m["out_of_plane"].get("converged"):
                    pairs.append((k, "out_of_plane", m["out_of_plane"]["Hvm_eV"], v["ref_Hvm_c"]))
        d = np.array([x[2] - x[3] for x in pairs])
        nonneg = [x for x in pairs if x[2] >= 0]
        mig[e] = {"all": stats(d), "all_excluding_negative_barriers": stats(np.array([x[2] - x[3] for x in nonneg])),
                  "negative_barriers": sorted([x[0], x[1], round(x[2], 3)] for x in pairs if x[2] < 0), **{h: stats(np.array([x[2] - x[3] for x in pairs if x[1] == h])) for h in ("hop", "in_plane", "out_of_plane")
                                       if any(x[1] == h for x in pairs)}, "pairs": [[x[0], x[1], round(x[2], 3), x[3]] for x in pairs]}
        al = [v for k, v in per.items() if k == "fcc:Al" and v[e]]
        mig[e]["al_fcc_migration_wall_s"] = (data[e]["pairs"].get("fcc:Al") or {}).get("migration_wall_s")
    out["migration"] = mig
    # --- per-element table (committed: both columns are literature DFT or computed values)
    out["per_element"] = {k: {"ref": v["ref_Hvf"], "ref_nonmagnetic": v["ref_Hvf_nonmagnetic"],
                              **{e: (round(v[e]["Hvf"], 3) if v[e] else None) for e in ENGINES}} for k, v in sorted(per.items())}
    OUT_JSON.write_text(json.dumps(out, indent=1) + "\n")

    # --- markdown
    S = out["stats"]
    row = lambda name, e, g: f"| {name} | {S[e][g]['n']} | {S[e][g]['median_abs_eV']} | {S[e][g]['mean_abs_eV']} | {S[e][g]['max_abs_eV']} | {S[e][g]['median_signed_eV']:+.3f} | {S[e][g]['within_0.1_eV']} | {S[e][g][f'over_{OUTLIER_EV}_eV']} |"
    tab = "| engine / subset | n | median \\|engine - ref\\| (eV) | mean | max | median signed (eV) | within 0.1 eV | over 0.2 eV |\n|---|---:|---:|---:|---:|---:|---:|---:|\n"
    tab += "\n".join(row(f"{ENGINES[e]}, {g.replace('_', ' ')}", e, g) for e in ENGINES for g in ("all", "fcc", "hcp", "six_focus_elements"))
    el = "| structure | element | ref H_vf (eV) | MPA-0 | MP-0 | MPA-0 - ref | MP-0 - ref |\n|---|---|---:|---:|---:|---:|---:|\n"
    for k, v in sorted(per.items(), key=lambda kv: (kv[1]["structure"], kv[1]["symbol"], kv[1]["magnetic"])):
        f = lambda e: f"{v[e]['Hvf']:.3f}" if v[e] else "-"
        g = lambda e: f"{v[e]['Hvf'] - v['ref_Hvf']:+.3f}" if v[e] else "-"
        nm = f" (spin-polarised; non-magnetic ref {v['ref_Hvf_nonmagnetic']})" if v["magnetic"] else ""
        mark = " *" if (v["symbol"], v["structure"]) in NATURAL else ""
        el += f"| {v['structure']} | {v['symbol']}{nm}{mark} | {v['ref_Hvf']:.2f} | {f(eng[0])} | {f(eng[1])} | {g(eng[0])} | {g(eng[1])} |\n"
    cv = "| element (structure) | ref | engine | cells and modes (N, mode: eV; FC = fixed cell, ZP = zero pressure) | spread (eV) |\n|---|---:|---|---|---:|\n"
    for k, c in conv.items():
        for e in ENGINES:
            if e in c:
                cv += f"| {k} | {c['ref_Hvf']:.2f} | {ENGINES[e]} | " + "; ".join(f"{n} {m.replace('zero_pressure', 'ZP').replace('fixed_cell', 'FC')}: {v:.3f}" for n, m, v, _ in c[e]["runs"]) + f" | {c[e]['spread_eV']} |\n"
    mg = "| engine / hop | n | median \\|engine - ref\\| (eV) | max | median signed |\n|---|---:|---:|---:|---:|\n"
    for e in ENGINES:
        for h in ("all", "all_excluding_negative_barriers", "hop", "in_plane", "out_of_plane"):
            if h in mig[e]:
                m = mig[e][h]
                mg += f"| {ENGINES[e]}, {h.replace('_', ' ')} | {m['n']} | {m['median_abs_eV']} | {m['max_abs_eV']} | {m['median_signed_eV']:+.3f} |\n"
    ol = "\n".join(f"- {ENGINES[e]}: " + (", ".join(f"{k} ({v:+.2f})" for k, v in out["outliers"][e]) or "none") for e in ENGINES)
    excl = ", ".join(f"{n} {r}" for r, n in out["population"]["excluded_by_reason"].items())
    md = f"""# Engine vacancy energies against a PBE DFT population (Angsten et al. 2014)

> **DEVELOPMENT / DESCRIPTIVE TIER. Evidence, no verdict.** The reference is **PBE DFT, not experiment**: agreement
> with it measures fidelity to another calculation, not accuracy. Nothing here licenses a production change.

Generated {out['generated_at']} by `scripts/aerospace_vacancy_population_report.py` from
`reports/aerospace_vacancy_population/<engine>.json`. Checkpoints: MPA-0 `{checkpoint['mace-mpa-0-medium'][:12]}`, MP-0 `{checkpoint['mace-mp-0-medium'][:12]}`.

## Reference and protocol

- **Reference:** Angsten, Mayeshiba, Wu, Morgan, *New J. Phys.* **16**, 015018 (2014), doi:10.1088/1367-2630/16/1/015018, appendix
  Tables A.1 (fcc) and A.2 (hcp), CC BY 3.0 (page capture sha256 `{out['reference_html_sha256'][:12]}`). The NIST dataset it points
  to (hdl:11256/102) did not resolve, so its licence was not read; the paper's own tables are used (`docs/methodology/data_provenance.md`).
- **The reference's own DFT** (what the numbers are): VASP 5.2.2, PBE, PAW; fcc 3x3x3 conventional cells (108 sites), hcp 3x3x2 (36 sites); the defect cell at
  the fixed volume of the relaxed perfect cell. The paper states a **20-30 meV size-effect error** and k-point errors of 18 meV (Al) and 9 meV (Mg). Values are
  printed to 0.01 eV.
- **Engine protocol, primary comparison:** the same cells and the same protocol: relax the 2- or 4-atom cell to zero pressure from the paper's tabulated atomic
  volume, repeat to the paper's cell, remove one atom, relax positions at the relaxed-bulk cell (`fixed_cell`, fmax {avp.FMAX} eV/A). This is a like-for-like comparison; it is
  *not* a converged-cell value.
- **Convergence (the Phase 0 approach):** the brief's six elements (marked * below), in their usual structure, were also run at two larger cells, in `fixed_cell` and
  `zero_pressure` (defect cell relaxed with its cell) modes.
- **Population:** {out['population']['in_population']} element-structure pairs ({out['population']['fcc']} fcc, {out['population']['hcp']} hcp) of {out['population']['table_rows']} table
  rows, unweighted. Excluded, by rules fixed before any engine ran: {excl}. Not computed or not converged: MPA-0 {len(failed[eng[0]])}, MP-0 {len(failed[eng[1]])}
  ({", ".join(failed[eng[0]] + failed[eng[1]]) or "none"}).

## Result: engine - reference over the population (the paper's cell and protocol)

{tab}

Same {out['stats_common'][eng[0]]['n']} pairs for both engines: MPA-0 median {out['stats_common'][eng[0]]['median_abs_eV']} eV, max {out['stats_common'][eng[0]]['max_abs_eV']}; MP-0 median
{out['stats_common'][eng[1]]['median_abs_eV']} eV, max {out['stats_common'][eng[1]]['max_abs_eV']}. The two engines differ from each other by a median of {out['engine_vs_engine']['median_abs_eV']} eV
(max {out['engine_vs_engine']['max_abs_eV']}).

**Outliers** (|engine - ref| over {OUTLIER_EV} eV, about 7 times the paper's stated size error; a reporting convenience, not a tolerance):

{ol}

For scale, the reference's own stated size and k-point errors are 0.01-0.03 eV and its values are rounded to 0.01 eV. Two PBE references for the same quantity also
differ: the Phase 0 memo's Al value (Hood et al., {hood_pbe} eV) is {hood_pbe - per['fcc:Al']['ref_Hvf']:+.2f} eV from this paper's Al value ({per['fcc:Al']['ref_Hvf']:.2f} eV), which is larger than the
reference's stated errors. **Reproducibility:** the Al vacancy values of this run reproduce Phase 0's to within
{max(max(v.values()) for v in ph0.values()):.4f} eV on both engines (all cells and modes both runs share).

**Equilibrium-volume check** (engine's relaxed atomic volume over the paper's tabulated Omega, which catches a structure that collapsed on relaxation):
MPA-0 median {vol[eng[0]]['median_ratio']} (range {vol[eng[0]]['min_ratio']} to {vol[eng[0]]['max_ratio']}), {len(vol[eng[0]]['pairs_off_by_more_than_10pct'])} pairs off by more than 10%;
MP-0 median {vol[eng[1]]['median_ratio']} (range {vol[eng[1]]['min_ratio']} to {vol[eng[1]]['max_ratio']}), {len(vol[eng[1]]['pairs_off_by_more_than_10pct'])} pairs off by more than 10%{(": " + ", ".join(f"{k} ({r})" for k, r in vol[eng[1]]['pairs_off_by_more_than_10pct'][:12])) if vol[eng[1]]['pairs_off_by_more_than_10pct'] else ""}.
{("MPA-0 off by more than 10%: " + ", ".join(f"{k} ({r})" for k, r in vol[eng[0]]['pairs_off_by_more_than_10pct'][:12]) + ".") if vol[eng[0]]['pairs_off_by_more_than_10pct'] else ""}

## Per-element table (* = the brief's six elements in their usual structure)

{el}
## Cell-size convergence, the six elements

{cv}
The spread is the range over all cells and both modes. The paper's stated size-effect error is 0.02-0.03 eV.

## Migration barriers (stretch goal)

Measured on Al first: {mig[eng[0]]['al_fcc_migration_wall_s']} s for MPA-0, far inside the 20-minute limit, so every pair was run. The method follows the paper's (section 2.5), but it
is a **single-image constrained saddle, not a converged NEB chain**: the migrating atom is placed at the midpoint of the hop (a symmetry point for these hops) and
everything is relaxed with that atom held in the bisecting plane, at the relaxed-bulk cell. It equals the paper's single-image CI-NEB only where the midpoint is the true saddle.
hcp is compared in-plane against H_vm(perp) and out-of-plane against H_vm(par).

{mg}
**Negative barriers.** A "barrier" below zero means the constrained midpoint relaxed *below* the relaxed vacancy: the method found a lower state, not a saddle. That may mean the host structure is not a
minimum for that engine; this was not checked. They are kept in the first row and left out of the second. MPA-0: {len(mig[eng[0]]['negative_barriers'])}
({", ".join(f"{k} {h}" for k, h, _ in mig[eng[0]]['negative_barriers']) or "none"}). MP-0: {len(mig[eng[1]]['negative_barriers'])}
({", ".join(f"{k} {h}" for k, h, _ in mig[eng[1]]['negative_barriers']) or "none"}). Large positive differences remain after that (see the JSON `pairs`), so treat these
barriers as a rough screen, not as converged NEB values.

## What this does and does not say

- **Does:** on {S[eng[0]]['all']['n']} metals the production engine reproduces PBE vacancy formation energies to a median of {S[eng[0]]['all']['median_abs_eV']} eV; the second engine to {S[eng[1]]['all']['median_abs_eV']} eV. The
  engines were trained on PBE data of the Materials Project convention, so this is partly convention fidelity.
- **Does not:** say the engines are accurate (the reference is not experiment); cover alloys, defect complexes, close approach (Phase 0 and Stage 1 found that the engine fails there) or
  radiation damage; replace the converged-cell value (the cells here are the paper's, not infinite).
- **Metastable structures** are in the population (the paper tabulates both fcc and hcp for every element). They are not weighted down; the fcc and hcp rows are reported separately.
- **Float32.** MPA-0 runs float32 and its relaxations carry about 1-5 meV of run-to-run noise (Stage 1 gate 2 diagnosis), small against the 0.1 eV scale of the medians above.

## Open decisions

1. **Is a vacancy-population check the right next step, or does the product need the E_d result?** This is a static, near-equilibrium
   quantity; it does not touch the short-range regime the aerospace question needs. (HANDOFF, Stage 2.)
2. **Whether to read the NIST dataset when it is reachable**, in case it carries more than the paper's tables (for example per-structure convergence).
"""
    OUT_MD.write_text(md)
    print(json.dumps({e: out["stats"][e]["all"] for e in ENGINES}, indent=0)[:600])


if __name__ == "__main__":
    main()
