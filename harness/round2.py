"""Round 2: four new anion families, a halide top-up, multi-start starts and the failure retry.

Everything here follows test 7's methodology unchanged — pool exclusion of prior and locked ids,
Clopper-Pearson bounds, verdicts read from the pessimistic end, per-family base rates, rejected
results counted-and-excluded rather than dropped. Nothing here refits or overwrites the frozen
product bundle.

TAXONOMY. `confidence.family()` has no nitride / carbide / fluoride / sulfide: fluoride falls under
halide, sulfide under chalcogenide, nitride under pnictide, and a metal carbide under 'other'. On the
unspent pool, 34-59 % of the compounds containing each of those anions are ALSO f-electron, and
f-electron wins first-match in the frozen chain. `family2()` therefore keeps f-electron, intermetallic
and oxide exactly where they are and inserts the four new families ahead of halide / chalcogenide /
pnictide / other, so:

  * the frozen taxonomy, the frozen bundle and the round-1 oxide/halide certifications are untouched;
  * a "nitride" result here is about non-f-electron, non-intermetallic nitrides — the population whose
    behaviour is not already covered by a certified family;
  * adopting any of these into production would carve fluoride out of halide, sulfide out of
    chalcogenide and nitride out of pnictide, so those parent families would have to be re-certified on
    their reduced populations. That is a decision for the user, not this module.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pymatgen.core import Composition

from harness import compare, splits
from harness.config import DATA_DIR
from harness.confidence import CHALCOGENS, HALOGENS, PNICTOGENS, cp_lower

SPLIT_FILE = DATA_DIR / "wbm_split_round2.json"
SEED = 20260918
NEW_FAMILIES = ("sulfide", "nitride", "carbide")  # fluoride is a halide subfamily; see make_split
HALIDE_TOPUP = "halide_topup"
MAX_CAL = 4000          # Phase 3 cap; three of the four families are pool-limited well below it
TOPUP_N = 2800          # Phase 2: 3,500 round-1 halides + 2,800 = ~6,300, the n test 7 asked for
MIN_LOCKED_HALF = 500   # a held-out half is only reserved when this much pool is left over


def family2(formula: str) -> str:
    """Round-2 taxonomy: `confidence.family()` with fluoride / sulfide / nitride / carbide inserted
    after oxide and before halide / chalcogenide / pnictide / other. First match wins, as there."""
    els = Composition(formula).elements
    syms = {e.symbol for e in els}
    if syms & compare.F_ELECTRON:
        return "f-electron"
    if all(e.is_metal for e in els):
        return "intermetallic"
    if "O" in syms:
        return "oxide"
    if "F" in syms:
        return "fluoride"
    if "S" in syms:
        return "sulfide"
    if "N" in syms:
        return "nitride"
    if "C" in syms:
        return "carbide"
    if syms & HALOGENS:
        return "halide"
    if syms & CHALCOGENS:
        return "chalcogenide"
    if syms & PNICTOGENS:
        return "pnictide"
    return "other"


# --- the split ------------------------------------------------------------------------------------

def _spent_ids() -> set[str]:
    """Every id the original split and the round-1 family split have already spent — calibration and
    locked test alike. Ids only, never outcomes; both files' test hashes are verified on the way."""
    fam = splits.load_split(splits.FAMILY_SPLIT_FILE)
    out = splits.excluded_ids() | splits.family_excluded_ids()
    for f in ("oxide", "halide"):
        out |= set(fam["families"][f]["calibration"]["ids"])
    return out


def _locked_formulas(pool: pd.DataFrame) -> set[str]:
    """Reduced formulas of every LOCKED test id, from both splits. WBM's unique_prototype dedups
    prototypes, not compositions, so a candidate sharing a formula with a locked-test id is dropped."""
    locked = splits.excluded_ids() - set(splits.calibration_ids())
    locked |= splits.family_excluded_ids()
    return {Composition(f).reduced_formula for f in pool[pool.material_id.isin(locked)].formula}


def make_split(summary: pd.DataFrame, seed: int = SEED, path=SPLIT_FILE) -> dict:
    """Calibration draws for the halide top-up and the three new families that need new structures.

    Groups are drawn SEQUENTIALLY against a shared taken-set, because they overlap: fluoride is a
    subset of confidence.family()'s halide, and a compound can hold both S and a halogen. Drawing
    them independently put 619 ids in a calibration draw AND a locked half at once — the exact
    leak the guards exist to stop.

    fluoride is deliberately NOT drawn. It is a strict subset of halide, so every fluoride structure
    the halide set holds is already computed; spending pool on a separate fluoride draw would buy
    fewer fluorides than the halide set already contains. It is analysed as a halide subfamily, the
    same way test 7's oxide split is.

    halide_topup gets no test half either: round 1 already locked 2,000 halide test ids, and that
    half still serves halide. Made once.
    """
    from harness.confidence import family
    from harness.suites import ood

    if path.exists():
        raise splits.SplitExists(f"{path} exists; the round-2 split is made once and never regenerated")
    pool = summary[(summary["unique_prototype"] == True) & summary[ood.REQUIRED].notna().all(axis=1)].copy()  # noqa: E712
    pool["bin"] = pool[splits.HULL_COL].map(lambda e: compare.hull_bin(e, below_zero_bin=True))

    spent = _spent_ids()
    locked_formulas = _locked_formulas(pool)
    rest = pool[~pool.material_id.isin(spent)].copy()
    rest["reduced_formula"] = [Composition(f).reduced_formula for f in rest.formula]
    n_before = len(rest)
    rest = rest[~rest.reduced_formula.isin(locked_formulas)]

    rest["fam2"] = [family2(f) for f in rest.formula]
    rest["fam1"] = [family(f) for f in rest.formula]

    out = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": seed,
           "pool": "WBM unique_prototype == True with every required column", "pool_size": len(pool),
           "hull_column": splits.HULL_COL, "bins": list(compare.HULL_BINS_WBM),
           "excluded_prior_ids": len(spent),
           "dropped_sharing_locked_test_formula": n_before - len(rest),
           "taxonomy": ("harness.round2.family2 — confidence.family() with fluoride/sulfide/nitride/carbide "
                        "inserted after oxide; halide_topup uses the frozen confidence.family()"),
           "fluoride": ("not drawn: a strict subset of confidence.family()'s halide, analysed as a halide "
                        "subfamily on the combined round-1 + top-up halide calibration set"),
           "method": ("drawn only from ids neither the original split nor the round-1 family split ever used; "
                      "groups drawn SEQUENTIALLY against a shared taken-set (they overlap chemically), each "
                      "per-bin proportional to that group's own share of what is still available; "
                      "pandas.DataFrame.sample(random_state=seed + group index + bin index)"),
           "draw_order": [HALIDE_TOPUP, *NEW_FAMILIES],
           "leakage_guards": ["every original and round-1 calibration and locked-test id excluded by id",
                              "every candidate sharing a reduced formula with any locked-test id dropped",
                              "groups drawn sequentially, so no id is in two draws or in both a calibration "
                              "draw and a locked half",
                              "each group drawn and certified on its own chemistry only"],
           "groups": {}}

    taken: set[str] = set()
    plan = [(HALIDE_TOPUP, "fam1", "halide", TOPUP_N, False)]
    plan += [(f, "fam2", f, MAX_CAL, True) for f in NEW_FAMILIES]
    for gi, (name, col, value, cap, want_test) in enumerate(plan):
        g = rest[(rest[col] == value) & ~rest.material_id.isin(taken)]
        shares = g["bin"].value_counts(normalize=True).reindex(compare.HULL_BINS_WBM).fillna(0)
        cal_q = splits._quotas(shares, min(cap, len(g)))
        cal = []
        for i, b in enumerate(compare.HULL_BINS_WBM):
            avail = g[g.bin == b]
            cal.append(avail.sample(n=min(cal_q[b], len(avail)), random_state=seed + 1000 * gi + i))
        cal = pd.concat(cal)
        taken |= set(cal.material_id)
        left = g.drop(cal.index)
        entry = {"available": len(g), "cap": cap,
                 "calibration": {"n": len(cal), "by_bin": cal.bin.value_counts().to_dict(),
                                 "ids": sorted(cal.material_id)}, "test": None}
        if want_test and len(left) >= MIN_LOCKED_HALF:
            t_ids = sorted(left.material_id)
            taken |= set(t_ids)
            entry["test"] = {"n": len(t_ids), "locked": True,
                             "sha256": hashlib.sha256(",".join(t_ids).encode()).hexdigest(), "ids": t_ids}
        elif want_test:
            entry["no_test_half_reason"] = (
                f"only {len(left)} candidates left after the calibration draw (< {MIN_LOCKED_HALF}); "
                "this group's thresholds are calibration-set results with no held-out half")
        else:
            entry["no_test_half_reason"] = ("round 1 already locked 2,000 halide test ids; that half still "
                                            "serves halide, so the top-up is calibration only")
        assert not set(cal.material_id) & spent
        out["groups"][name] = entry

    cal_all = {i for g in out["groups"].values() for i in g["calibration"]["ids"]}
    test_all = {i for g in out["groups"].values() if g["test"] for i in g["test"]["ids"]}
    assert not cal_all & test_all, "a calibration id is also in a locked half"
    out["n_unique_calibration_ids"] = len(cal_all)
    out["fluoride_in_draw"] = int(sum(family2(f) == "fluoride" for f in
                                      rest[rest.material_id.isin(out["groups"][HALIDE_TOPUP]["calibration"]["ids"])].formula))
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def load(path=SPLIT_FILE) -> dict:
    return json.loads(path.read_text())


def calibration_ids(group: str, path=SPLIT_FILE) -> list[str]:
    return load(path)["groups"][group]["calibration"]["ids"]


def groups(path=SPLIT_FILE) -> list[str]:
    return list(load(path)["groups"])


def test_ids(group: str, unlock: bool = False, path=SPLIT_FILE) -> list[str]:
    """Locked round-2 test ids. Nothing in this project passes unlock=True."""
    if not unlock:
        raise PermissionError(f"the round-2 {group} test set is locked (test_ids('{group}', unlock=True))")
    t = load(path)["groups"][group]["test"]
    if t is None:
        raise KeyError(f"{group} has no test half")
    if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
        raise RuntimeError(f"round-2 {group} test ids do not match their recorded hash")
    return t["ids"]


def excluded_ids(path=SPLIT_FILE) -> set[str]:
    """Every round-2 LOCKED test id, for exclusion only. Each hash verified, as elsewhere."""
    out: set[str] = set()
    for name, g in load(path)["groups"].items():
        t = g.get("test")
        if not t:
            continue
        if hashlib.sha256(",".join(t["ids"]).encode()).hexdigest() != t["sha256"]:
            raise RuntimeError(f"round-2 {name} test ids do not match their recorded hash")
        out |= set(t["ids"])
    return out


# --- the diagnostic test 7 used to tell halide from oxide -------------------------------------------

def _level(conf: float, grid) -> float:
    """Bonferroni level over the threshold grid, exactly as confidence.certify uses it."""
    return 1 - (1 - conf) / len(grid)


def best_bound(pred, stable, side: str, grid, min_selected: int, level: float) -> dict:
    """The threshold whose Clopper-Pearson LOWER bound is highest, over the same grid certify()
    searches — the group's certification ceiling. Ties go to the loosest threshold, as certify() does.

    Selecting by the bound rather than by the point estimate is what makes the ceiling meaningful:
    the point estimate is maximised by whatever threshold happens to select the fewest candidates
    (halide's grid maximum is 0.9600 on 25 calls, which certifies nothing), whereas the bound is the
    quantity every verdict in this project is read from.
    """
    from harness import metrics as M

    pred, stable = np.asarray(pred, float), np.asarray(stable, bool)
    best = None
    for t in grid:
        sel = pred <= t + M.ON_HULL_TOL if side == "stable" else pred > t + M.ON_HULL_TOL
        n = int(sel.sum())
        if n < min_selected:
            continue
        k = int(stable[sel].sum()) if side == "stable" else int((~stable[sel]).sum())
        lo = cp_lower(k, n, level)
        if best is None or lo > best["cp_lower"] + 1e-12 or (abs(lo - best["cp_lower"]) <= 1e-12 and t > best["t"]):
            best = {"t": float(t), "n_selected": n, "k": k, "point": k / n, "cp_lower": float(lo)}
    return best or {"t": None, "n_selected": 0, "k": 0, "point": float("nan"), "cp_lower": 0.0}


def n_needed(point: float, target: float, conf: float, grid, cap: int = 200_000) -> int | None:
    """Smallest number of selected calls at which an observed rate of `point` would clear `target`
    on the Clopper-Pearson lower bound. None if it never does (a precision-limited group)."""
    if not np.isfinite(point) or point <= target:
        return None
    level = _level(conf, grid)
    lo, hi = 1, 1024
    while hi <= cap and cp_lower(int(round(point * hi)), hi, level) < target:
        lo, hi = hi, hi * 2
    if hi > cap:
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if cp_lower(int(round(point * mid)), mid, level) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def diagnose(pred, stable, target: float, side: str = "stable", conf: float | None = None,
             grid=None, min_selected: int | None = None) -> dict:
    """Test 7's diagnosis: is this group sample-size limited (more data would certify it) or
    precision limited (the ceiling is below target, so no n helps)?"""
    from harness import confidence as C

    conf = C.CERT_CONF if conf is None else conf
    grid = C.DEC_GRID if grid is None else grid
    min_selected = C.MIN_SELECTED if min_selected is None else min_selected

    cert = C.certify(pred, stable, target, side, conf, grid, min_selected)
    b = best_bound(pred, stable, side, grid, min_selected, _level(conf, grid))
    lower = b["cp_lower"]
    need = n_needed(b["point"], target, conf, grid)
    if cert is not None:
        verdict = "certified"
    elif np.isfinite(b["point"]) and b["point"] > target:
        verdict = "sample-size limited"
    else:
        verdict = "precision limited"
    if cert is not None:
        need = None  # already certified: "how many more would it take" has no meaning
    return {"side": side, "target": target, "certified_threshold": cert,
            "best_threshold": b["t"], "n_selected": b["n_selected"], "k": b["k"],
            "point": b["point"], "cp_lower": float(lower), "verdict": verdict,
            "n_selected_needed": need,
            "scale_factor": (need / b["n_selected"]) if (need and b["n_selected"]) else None}


def precision_by_true_bin(pred, stable, each_true, threshold: float) -> pd.DataFrame:
    """Precision of the 'stable' call at `threshold`, split by TRUE hull-distance bin — the
    precision-vs-hull-distance view test 7 used alongside the diagnosis."""
    from harness import metrics as M

    d = pd.DataFrame({"pred": np.asarray(pred, float), "stable": np.asarray(stable, bool),
                      "each_true": np.asarray(each_true, float)})
    d["bin"] = d.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
    d = d[d.pred <= threshold + M.ON_HULL_TOL]
    rows = []
    for b in compare.HULL_BINS_WBM:
        g = d[d.bin == b]
        rows.append({"bin": b, "n_selected": len(g), "n_correct": int(g.stable.sum()),
                     "precision": float(g.stable.mean()) if len(g) else float("nan")})
    return pd.DataFrame(rows)
