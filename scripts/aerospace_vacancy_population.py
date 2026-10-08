"""Aerospace lit-session Phase C: engine vacancy formation energies against a PBE DFT population.

Reference: Angsten, Mayeshiba, Wu, Morgan, New J. Phys. 16, 015018 (2014), doi:10.1088/1367-2630/16/1/015018,
Appendix Tables A.1 (fcc) and A.2 (hcp), parsed from the open-access (CC BY 3.0) landing page captured under
cache/external/aerospace/angsten/. The NIST handle quoted for the dataset (hdl:11256/102) did not resolve on
2026-10-08, so the paper's own tables are the reference. They are PBE DFT, not experiment.

One engine per process, as in Phase 0:

    HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/aerospace_vacancy_population.py
    HARNESS_MODEL=mace-mp-0-medium  .venv/bin/python scripts/aerospace_vacancy_population.py

Writes reports/aerospace_vacancy_population/<engine>.json after every element (resumable: finished
element-structure pairs are skipped on a re-run).

Protocol, per element-structure pair (the paper's own, section 2.4):
  1. relax the 2- or 4-atom cell (positions + cell) to zero pressure from the paper's tabulated atomic volume;
  2. build the paper's supercell (fcc 3x3x3 conventional = 108 sites; hcp 3x3x2 conventional = 36 sites);
  3. remove one atom and relax positions only, at the relaxed-bulk cell ("fixed_cell", the paper's protocol);
  H_vf = E(N-1) - (N-1)/N * E(N).
The focus elements (Al, Cu, Ag, Ni; Mg, Ti) are also run at two larger cells, in both the paper's fixed-cell
mode and a zero-pressure mode (defect cell relaxed with its cell), the Phase 0 convergence approach.

Population rules (fixed here, before any engine ran; they use only the paper's own flags):
  - drop every row the paper marks unstable (negative H_vf, or footnote a/b "instability ... precluded");
  - drop noble gases (van der Waals solids, H_vf <= 0.01 eV in the reference: nothing to compare);
  - drop Mn (the paper used different pseudopotentials for fcc and hcp Mn);
  - where the paper lists a spin-polarised row (Co, Ni), use it as the reference and keep the non-magnetic one
    as a second reference; the engines were trained on spin-polarised data.
"""

from __future__ import annotations

import hashlib
import html as htmllib
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import bulk
from ase.constraints import FixedPlane
from ase.filters import FrechetCellFilter
from ase.optimize import BFGS

from harness import config

ROOT = config.ROOT
LANDING = ROOT / "cache/external/aerospace/angsten/https___doi_org_10_1088_1367_2630_16_1_015018_.html"
OUTDIR = ROOT / "reports" / "aerospace_vacancy_population"
FMAX = config.DEFAULT_RELAX.fmax
MAX_STEPS = 1500
NOBLE = {"He", "Ne", "Ar", "Kr", "Xe"}
FOCUS = {("Al", "fcc"), ("Cu", "fcc"), ("Ag", "fcc"), ("Ni", "fcc"), ("Mg", "hcp"), ("Ti", "hcp")}
PAPER_CELL = {"fcc": (3, 3, 3), "hcp": (3, 3, 2)}
LARGE_CELLS = {"fcc": [(4, 4, 4), (5, 5, 5)], "hcp": [(4, 4, 3), (6, 6, 4)]}
CALC = None


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _cell_text(td: str) -> tuple[str, str]:
    """-> (text, footnote letters) for one <td>."""
    sups = re.findall(r"<sup[^>]*>.*?</sup>", td, flags=re.S)
    notes = "".join(re.sub(r"<[^>]+>", "", x) for x in sups)
    for x in sups:
        td = td.replace(x, "")
    txt = htmllib.unescape(re.sub(r"<[^>]+>", "", td.replace("<sub>", " "))).replace("−", "-").strip()
    return txt, notes


def parse_angsten() -> list[dict]:
    """Rows of Tables A.1 (fcc) and A.2 (hcp). Header names are asserted, so a changed page fails loudly."""
    s = LANDING.read_text(errors="ignore")
    tables = re.findall(r"<table[^>]*data-toolbar-title=\"(Table A\.\d)\.\".*?</table>", s, flags=re.S)
    assert tables == ["Table A.1", "Table A.2"], tables
    rows = []
    for label, structure in (("Table A.1", "fcc"), ("Table A.2", "hcp")):
        t = re.search(rf"<table[^>]*data-toolbar-title=\"{re.escape(label)}\.\".*?</table>", s, flags=re.S).group(0)
        heads = [htmllib.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", t, flags=re.S)]
        assert heads[0] == "Symbol" and "Hvf(eV)" in [h.replace(" ", "") for h in heads], heads
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t.split("<tbody>")[1], flags=re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
            cells = [_cell_text(td) for td in tds]
            sym_txt, sym_notes = cells[0]
            sym = sym_txt.split()[0]
            mag = "mag" in sym_txt
            vals = []
            for txt, notes in cells[1:]:
                vals.append(None if txt in ("–", "-", "") else float(txt))
            hvf_idx = 4  # E_coh, K, K', Omega, H_vf, H_vm...
            hvf_notes = cells[1 + hvf_idx][1]
            rows.append({"structure": structure, "symbol": sym, "magnetic_variant": mag,
                         "symbol_footnote": sym_notes, "hvf_footnote": hvf_notes,
                         "E_coh_eV": vals[0], "omega_A3": vals[3], "Hvf_eV": vals[4],
                         "Hvm_eV": vals[5] if structure == "fcc" else vals[5],
                         "Hvm_c_eV": vals[6] if structure == "hcp" else None})
    return rows


def check_parse(rows: list[dict]) -> None:
    """Spot-check against values read from the rendered page text on 2026-10-08."""
    by = {(r["structure"], r["symbol"], r["magnetic_variant"]): r for r in rows}
    exp = {("fcc", "Al", False): 0.61, ("fcc", "Cu", False): 1.07, ("fcc", "Ag", False): 0.68,
           ("fcc", "Ni", False): 1.39, ("fcc", "Ni", True): 1.43, ("hcp", "Mg", False): 0.78,
           ("hcp", "Ti", False): 2.06, ("fcc", "Mg", False): 0.82, ("fcc", "Be", False): -0.06}
    for k, v in exp.items():
        assert by[k]["Hvf_eV"] == v, (k, by[k]["Hvf_eV"], v)
    assert sum(r["structure"] == "fcc" for r in rows) >= 54 and sum(r["structure"] == "hcp" for r in rows) >= 50


def select_population(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    keep, drop = [], []
    have_mag = {(r["structure"], r["symbol"]) for r in rows if r["magnetic_variant"]}
    for r in rows:
        why = None
        if r["Hvf_eV"] is None or r["Hvf_eV"] < 0:
            why = "negative H_vf: paper says unstable"
        elif r["symbol_footnote"] or r["hvf_footnote"]:
            fn = r["symbol_footnote"] or r["hvf_footnote"]
            why = f"paper footnote {fn}: " + ("different pseudopotential used" if fn == "c" else "unstable in this structure")
        elif r["symbol"] in NOBLE:
            why = "noble gas (vdW solid)"
        elif r["symbol"] == "Mn":
            why = "Mn: different pseudopotentials for fcc and hcp in the paper"
        elif not r["magnetic_variant"] and (r["structure"], r["symbol"]) in have_mag:
            why = "non-magnetic row superseded by the spin-polarised row (kept as second reference)"
        (drop if why else keep).append({**r, **({"excluded_because": why} if why else {})})
    nm = {(r["structure"], r["symbol"]): r["Hvf_eV"] for r in rows if not r["magnetic_variant"]}
    for r in keep:
        r["Hvf_nonmagnetic_eV"] = nm.get((r["structure"], r["symbol"])) if r["magnetic_variant"] else None
    return keep, drop


# ---------------------------------------------------------------- engine side

def relax(atoms: Atoms, cell: bool) -> dict:
    atoms.calc = CALC
    target = FrechetCellFilter(atoms) if cell else atoms
    opt = BFGS(target, logfile=None)
    ok = opt.run(fmax=FMAX, steps=MAX_STEPS)
    return {"steps": opt.nsteps, "converged": bool(ok), "n_atoms": len(atoms)}


def unit_cell(sym: str, structure: str, omega: float) -> Atoms:
    """Starting guess from the paper's own tabulated atomic volume; the engine then relaxes it."""
    if structure == "fcc":
        return bulk(sym, "fcc", a=(4 * omega) ** (1 / 3), cubic=True)
    a = (2 * omega / (np.sqrt(3) / 2 * np.sqrt(8 / 3))) ** (1 / 3)
    return bulk(sym, "hcp", a=a, c=a * np.sqrt(8 / 3))


def vacancy(sym: str, structure: str, omega: float, rep: tuple, mode: str, uc: Atoms | None = None) -> dict:
    uc = unit_cell(sym, structure, omega) if uc is None else uc.copy()
    info_uc = relax(uc, cell=True)
    sc = uc.repeat(rep)
    sc.calc = CALC
    e_bulk = float(sc.get_potential_energy())
    n = len(sc)
    centre = int(np.argmin(np.linalg.norm(sc.positions - sc.cell.sum(axis=0) / 2, axis=1)))
    vac = sc.copy()
    del vac[centre]
    info = relax(vac, cell=(mode == "zero_pressure"))
    e_vac = float(vac.get_potential_energy())
    return {"N": n, "mode": mode, "E_f_eV": e_vac - (n - 1) / n * e_bulk, **info,
            "unit_cell_relax": info_uc, "cell_lengths_A": [round(float(x), 4) for x in uc.cell.lengths()]}


def migration(sym: str, structure: str, omega: float, rep: tuple) -> dict:
    """Barrier for nearest-neighbour vacancy hops, the way the paper did it (section 2.5): the migrating atom is
    placed at the midpoint of the hop (a symmetry point for these hops) and everything is relaxed with that atom
    held in the bisecting plane. This is a single-image constrained saddle, not a converged NEB chain; it equals
    the paper's single-image CI-NEB only where the hop's midpoint is the true saddle. fcc: one hop. hcp: in-plane
    (basal) and out-of-plane. Fixed cell at the relaxed-bulk volume, as in the vacancy protocol."""
    uc = unit_cell(sym, structure, omega)
    relax(uc, cell=True)
    sc = uc.repeat(rep)
    sc.calc = CALC
    centre = int(np.argmin(np.linalg.norm(sc.positions - sc.cell.sum(axis=0) / 2, axis=1)))
    d = sc.get_distances(centre, range(len(sc)), mic=True)
    d[centre] = 1e9
    nn = np.where(d < d.min() * 1.05 + 1e-9)[0]
    out = {}
    # fcc: all 12 neighbours equivalent -> take the first. hcp: split by whether the hop vector has a z component.
    hops = {}
    for j in nn:
        v = sc.get_distance(centre, int(j), mic=True, vector=True)
        kind = "hop" if structure == "fcc" else ("in_plane" if abs(v[2]) < 0.1 else "out_of_plane")
        hops.setdefault(kind, (int(j), v))
    for kind, (j, v) in hops.items():
        # v = vector from the vacant site (centre) to its neighbour j. IS: vacancy at centre, j in place.
        is_atoms = sc.copy()
        del is_atoms[centre]
        relax(is_atoms, cell=False)
        e_is = float(is_atoms.get_potential_energy())
        # TS: j sits at the midpoint of the hop, held in the plane that bisects it.
        ts = sc.copy()
        ts.positions[j] = sc.positions[centre] + v / 2
        j_after = j - 1 if j > centre else j  # index of j once the centre atom is deleted
        del ts[centre]
        ts.set_constraint(FixedPlane(j_after, v / np.linalg.norm(v)))
        info = relax(ts, cell=False)
        out[kind] = {"Hvm_eV": float(ts.get_potential_energy()) - e_is, "hop_length_A": float(np.linalg.norm(v)), **info}
    return out


def run_pair(r: dict, run_larger: bool, do_migration: bool) -> dict:
    sym, st, omega = r["symbol"], r["structure"], r["omega_A3"]
    rec = {"symbol": sym, "structure": st, "reference_Hvf_eV": r["Hvf_eV"], "reference_Hvm_eV": r["Hvm_eV"],
           "reference_Hvm_c_eV": r["Hvm_c_eV"], "magnetic_variant": r["magnetic_variant"], "runs": []}
    t0 = time.time()
    rec["runs"].append(vacancy(sym, st, omega, PAPER_CELL[st], "fixed_cell"))
    if run_larger:
        rec["runs"].append(vacancy(sym, st, omega, PAPER_CELL[st], "zero_pressure"))
        for rep in LARGE_CELLS[st]:
            for mode in ("fixed_cell", "zero_pressure"):
                rec["runs"].append(vacancy(sym, st, omega, rep, mode))
    if do_migration:
        t1 = time.time()
        try:
            rec["migration"] = migration(sym, st, omega, PAPER_CELL[st])
        except Exception as e:  # recorded, not hidden
            rec["migration_error"] = repr(e)
        rec["migration_wall_s"] = round(time.time() - t1, 1)
    rec["wall_s"] = round(time.time() - t0, 1)
    return rec


def main() -> None:
    global CALC
    from harness.engine import get_calculator
    engine = config.MODEL["key"]
    compute = config.load_compute_config()
    dtype = compute["dtype"]
    CALC = get_calculator(compute["device"], dtype)
    do_migration = "--migration" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    rows = parse_angsten()
    check_parse(rows)
    keep, drop = select_population(rows)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTDIR / f"{engine}.json"
    res = json.loads(out_path.read_text()) if out_path.exists() else {
        "engine": engine, "checkpoint_sha256": config.MODEL["sha256"], "dtype": dtype, "fmax_eV_per_A": FMAX, "reference_html_sha256": sha256(LANDING),
        "pairs": {}, "unsupported": []}
    zs = getattr(CALC, "z_table", None)
    supported = {int(z) for z in zs.zs} if zs is not None else None
    from ase.data import atomic_numbers
    t_all = time.time()
    for r in keep:
        key = f"{r['structure']}:{r['symbol']}{':mag' if r['magnetic_variant'] else ''}"
        if only and r["symbol"] not in only:
            continue
        if key in res["pairs"] and (not do_migration or "migration" in res["pairs"][key] or "migration_error" in res["pairs"][key]):
            continue
        if supported is not None and atomic_numbers[r["symbol"]] not in supported:
            if key not in res["unsupported"]:
                res["unsupported"].append(key)
            continue
        try:
            rec = run_pair(r, run_larger=(r["symbol"], r["structure"]) in FOCUS, do_migration=do_migration)
        except Exception as e:
            rec = {"symbol": r["symbol"], "structure": r["structure"], "error": repr(e)}
        old = res["pairs"].get(key, {})
        res["pairs"][key] = {**old, **rec}
        out_path.write_text(json.dumps(res, indent=1) + "\n")
        print(key, rec.get("wall_s"), flush=True)
    res["wall_s_last_session"] = round(time.time() - t_all, 1)
    res["excluded"] = [{k: d[k] for k in ("structure", "symbol", "magnetic_variant", "excluded_because")} for d in drop]
    out_path.write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
