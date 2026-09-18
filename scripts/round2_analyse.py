#!/usr/bin/env python
"""Round-2 analysis: certification and diagnosis per group, test 7's methodology unchanged.

    python scripts/round2_analyse.py diagnose <report.md> <group> [<group> ...]

Groups are resolved to a set of WBM calibration ids and the cache their structures live in:
  sulfide / nitride / carbide   round-2 draw
  halide_topup                  round-2 draw
  halide                        round-1 halide calibration (3,500)
  halide_combined               round-1 halide + the top-up
  oxide                         round-1 oxide calibration (3,994 usable)
  <parent>:<subfamily>          a chemically-defined subset of a parent group (phase 4 / fluoride)

Conventions inherited from test 7 and never relaxed here:
  * Clopper-Pearson one-sided bounds, Bonferroni-corrected over the threshold grid, never bootstrap;
  * the verdict is read from the pessimistic end of the interval, never the point estimate;
  * guard rejections are counted and excluded, never dropped, and the count is printed with every n.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from harness import calibration as CAL, confidence as C, metrics as M, round2, splits
from harness.config import DATA_DIR, REPORTS_DIR

R2_CACHE = "round2_calibration_init_structs.json"
R1_CACHE = "oxide_halide_calibration_init_structs.json"


def _table(ids, cache) -> pd.DataFrame:
    d = CAL.calibration_table(CAL.PRODUCTION_ENGINE, set(ids), init_cache=cache)
    d.attrs["n_requested"] = len(set(ids))
    return d


def resolve(group: str) -> pd.DataFrame:
    """Usable calibration rows for a group, with n_requested / n_rejected kept in .attrs."""
    if ":" in group:
        parent, sub = group.split(":", 1)
        d = resolve(parent)
        mask = SUBFAMILIES[sub](d)
        out = d[mask].copy()
        out.attrs = dict(d.attrs) | {"n_requested": int(mask.sum()), "subfamily_of": parent}
        return out
    if group.endswith("@p1"):
        import json
        sel = json.loads((DATA_DIR / "round2_phase1_ids.json").read_text())["groups"]
        return _table(sel[group[:-3]], R2_CACHE)
    if group in ("sulfide", "nitride", "carbide", round2.HALIDE_TOPUP):
        return _table(round2.calibration_ids(group), R2_CACHE)
    if group in ("oxide", "halide"):
        return _table(splits.family_calibration_ids(group), R1_CACHE)
    if group == "halide_combined":
        a = _table(splits.family_calibration_ids("halide"), R1_CACHE)
        b = _table(round2.calibration_ids(round2.HALIDE_TOPUP), R2_CACHE)
        out = pd.concat([a, b], ignore_index=True)
        out.attrs = {"n_requested": a.attrs["n_requested"] + b.attrs["n_requested"],
                     "n_rejected": a.attrs["n_rejected"] + b.attrs["n_rejected"]}
        return out
    raise SystemExit(f"unknown group {group!r}")


# --- subfamily splits (phase 4, and fluoride inside halide) ------------------------------------------
def _els(d):
    from pymatgen.core import Composition
    return d.formula.map(lambda f: {e.symbol for e in Composition(f).elements})


def _has(sym):
    return lambda d: _els(d).map(lambda s: sym in s)


def _tm(d):
    from pymatgen.core import Element
    return _els(d).map(lambda s: any(Element(x).is_transition_metal for x in s))


def _guesses(formula):
    """Charge-balanced assignments of one integer oxidation state per element, or None when
    pymatgen could not evaluate the composition at all (kept distinct from 'none balance')."""
    from pymatgen.core import Composition
    try:
        return Composition(formula).oxi_state_guesses(max_sites=-1)
    except Exception:  # noqa: BLE001 — unevaluable, which is not the same as mixed valence
        return None


def _mixed_valence(d):
    """No assignment of ONE integer oxidation state per element balances the charge — the standard
    operational test for mixed valence (Fe3O4 fails it, FeO and Fe2O3 pass). Compositions pymatgen
    could not evaluate are NOT counted as mixed valence; they fall in neither split, and the two
    splits' n therefore need not sum to the parent's."""
    # oxi_state_guesses returns a TUPLE; comparing it to [] silently matched nothing.
    return d.formula.map(lambda f: (lambda g: g is not None and len(g) == 0)(_guesses(f)))


def _multi_tm(d):
    from pymatgen.core import Composition, Element
    return d.formula.map(lambda f: sum(Element(e.symbol).is_transition_metal
                                       for e in Composition(f).elements) > 1)


def _max_cation_state(formula):
    g = _guesses(formula)
    if not g:  # None (unevaluable) or [] (nothing balances)
        return None
    pos = [v for v in g[0].values() if v > 0]
    return max(pos) if pos else None


def _ox(pred):
    return lambda d: d.formula.map(lambda f: pred(_max_cation_state(f)))


SUBFAMILIES = {
    "fluoride": _has("F"),
    "nonfluoride": lambda d: ~_has("F")(d),
    "tm": _tm,
    "maingroup": lambda d: ~_tm(d),
    "multi_tm": _multi_tm,
    "single_tm": lambda d: ~_multi_tm(d),
    "mixed_valence": _mixed_valence,
    "single_valence": lambda d: d.formula.map(lambda f: bool(_guesses(f))),
    # highest formal cation oxidation state in the first charge-balanced assignment
    "ox_le2": _ox(lambda s: s is not None and s <= 2),
    "ox_3": _ox(lambda s: s == 3),
    "ox_4": _ox(lambda s: s == 4),
    "ox_ge5": _ox(lambda s: s is not None and s >= 5),
}


# --- report ------------------------------------------------------------------------------------------

def rows_for(group: str, targets=((0.90, "stable"), (0.95, "unstable")), alt_target: float = 0.80,
             n_splits: int = 1) -> dict:
    """n_splits > 1 additionally Bonferroni-corrects the certification confidence over the number of
    subfamily splits searched, so a split picked because it looked best still keeps its guarantee."""
    conf = 1 - (1 - C.CERT_CONF) / n_splits
    d = resolve(group)
    d = d.assign(stable=d.each_true <= M.ON_HULL_TOL)
    out = {"group": group, "n_requested": d.attrs.get("n_requested"), "n_usable": len(d),
           "n_rejected": d.attrs.get("n_rejected"), "base_rate": float(d.stable.mean()) if len(d) else float("nan"),
           "n_splits_corrected": n_splits, "cert_conf": conf, "diagnoses": [], "alt": None}
    for target, side in targets:
        out["diagnoses"].append(round2.diagnose(d.each_pred, d.stable, target, side, conf=conf))
    stable_dx = out["diagnoses"][0]
    if stable_dx["certified_threshold"] is None:
        out["alt"] = round2.diagnose(d.each_pred, d.stable, alt_target, "stable", conf=conf)
    # Routing impact of the certified UNSTABLE threshold. The project's standing rule is that a
    # satisfied NPV target is not the same as keeping your discoveries, so the share discarded and
    # the share of truly stable candidates lost are always reported together.
    ut = out["diagnoses"][1]["certified_threshold"]
    if ut is not None and len(d):
        called_unstable = d.each_pred > ut + M.ON_HULL_TOL
        n_stable = int(d.stable.sum())
        out["routing"] = {"unstable_threshold": ut,
                          "discard_share": float(called_unstable.mean()),
                          "n_truly_stable": n_stable,
                          "n_truly_stable_discarded": int((called_unstable & d.stable).sum()),
                          "truly_stable_lost": float((called_unstable & d.stable).sum() / n_stable)
                          if n_stable else float("nan")}
    else:
        out["routing"] = None
    t = stable_dx["certified_threshold"]
    t = t if t is not None else stable_dx["best_threshold"]
    out["by_true_bin"] = (round2.precision_by_true_bin(d.each_pred, d.stable, d.each_true, t)
                          if t is not None else pd.DataFrame())
    out["threshold_used_for_bins"] = t
    return out


def fmt(x, n=4):
    return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{n}f}"


def mev(t):
    return "-" if t is None else f"{t * 1000:+.0f} meV"


def render(results: list[dict]) -> str:
    L = [f"# Round 2 — certification and diagnosis", "",
         f"Engine: MACE-MPA-0 medium, cpu/float32, settings_tag `c2480e74` (asserted at the start of "
         f"every phase). Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}.", "",
         "Method is test 7's, unchanged: Clopper-Pearson one-sided bounds (never bootstrap), "
         "Bonferroni-corrected over the threshold grid so picking the best threshold keeps the "
         "guarantee, verdicts read from the pessimistic end, and guard rejections counted-and-excluded "
         "rather than dropped.", ""]
    ns = {r.get("n_splits_corrected", 1) for r in results}
    if ns != {1}:
        L += [f"Certification confidence is additionally Bonferroni-corrected over "
              f"{max(ns)} subfamily splits (level {max(r.get('cert_conf', 0.95) for r in results):.5f}), "
              f"so a split chosen because it looked best keeps its guarantee.", ""]
    L += [
         "## Summary", "",
         "| group | n requested | n usable | rejected (counted, excluded) | base rate | stable side | unstable side |",
         "|---|---:|---:|---:|---:|---|---|"]
    for r in results:
        s, u = r["diagnoses"][0], r["diagnoses"][1]
        L.append(f"| {r['group']} | {r['n_requested']} | {r['n_usable']} | {r['n_rejected']} | "
                 f"{fmt(r['base_rate'], 3)} | "
                 f"{'**' + mev(s['certified_threshold']) + '**' if s['certified_threshold'] is not None else 'not certified'} | "
                 f"{'**' + mev(u['certified_threshold']) + '**' if u['certified_threshold'] is not None else 'not certified'} |")
    L += ["", "## Diagnosis — sample-size limited or precision limited", "",
          "`n structures needed` converts `n selected needed` by the group's own selection rate: it is "
          "how large the calibration set would have to be, not how many calls. A figure larger than "
          "WBM's whole 215,488-structure unique-prototype pool means the group is sample-size limited "
          "only in principle.", "",
          "| group | side | target | best t | n selected | k | point | CP-lower | verdict | n selected needed | n structures needed | factor |",
          "|---|---|---:|---|---:|---:|---:|---:|---|---:|---:|---:|"]
    for r in results:
        for dx in r["diagnoses"]:
            L.append(f"| {r['group']} | {dx['side']} | {dx['target']:.2f} | {mev(dx['best_threshold'])} | "
                     f"{dx['n_selected']} | {dx['k']} | {fmt(dx['point'])} | {fmt(dx['cp_lower'])} | "
                     f"{dx['verdict']} | {dx['n_selected_needed'] or '-'} | "
                     f"{dx.get('n_structures_needed') or '-'} | "
                     f"{fmt(dx['scale_factor'], 2) if dx['scale_factor'] else '-'} |")
    alts = [r for r in results if r["alt"]]
    if alts:
        L += ["", "### Stable side at the alternate 0.80 target (test 7's fallback)", "",
              "| group | best t | n selected | point | CP-lower | certified at 0.80 |", "|---|---|---:|---:|---:|---|"]
        for r in alts:
            a = r["alt"]
            L.append(f"| {r['group']} | {mev(a['best_threshold'])} | {a['n_selected']} | {fmt(a['point'])} | "
                     f"{fmt(a['cp_lower'])} | {mev(a['certified_threshold']) if a['certified_threshold'] is not None else 'no'} |")
    routed = [r for r in results if r.get("routing")]
    if routed:
        L += ["", "## Routing impact of the certified 'likely unstable' threshold", "",
              "A satisfied NPV target is not the same as keeping your discoveries: both columns "
              "belong to any proposal to route on these thresholds.", "",
              "| group | threshold | share discarded without DFT | truly stable lost | (of) |",
              "|---|---|---:|---:|---:|"]
        for r in routed:
            g = r["routing"]
            L.append(f"| {r['group']} | {mev(g['unstable_threshold'])} | {g['discard_share']:.3f} | "
                     f"{g['truly_stable_lost']:.3f} | {g['n_truly_stable_discarded']} of {g['n_truly_stable']} |")
    L += ["", "## Precision of the 'likely stable' call by TRUE hull-distance bin", "",
          "At each group's certified stable threshold, or its best point threshold when nothing certified.", ""]
    for r in results:
        if not len(r["by_true_bin"]):
            continue
        L += [f"**{r['group']}** (threshold {mev(r['threshold_used_for_bins'])})", "",
              "| true hull bin | n selected | n correct | precision |", "|---|---:|---:|---:|"]
        for _, b in r["by_true_bin"].iterrows():
            L.append(f"| {b['bin']} | {int(b.n_selected)} | {int(b.n_correct)} | {fmt(b.precision, 3)} |")
        L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[1] != "diagnose":
        raise SystemExit(__doc__)
    args = sys.argv[3:]
    n_splits = 1
    if args and args[0].startswith("--splits="):
        n_splits = int(args[0].split("=", 1)[1])
        args = args[1:]
    out = REPORTS_DIR / sys.argv[2]
    res = [rows_for(g, n_splits=n_splits) for g in args]
    out.write_text(render(res))
    # the same numbers as machine-readable JSON, so the PDF transcribes rather than re-derives
    import json
    js = out.with_suffix(".json")
    js.write_text(json.dumps([{k: (v.to_dict("records") if isinstance(v, pd.DataFrame) else v)
                               for k, v in r.items()} for r in res], indent=1, default=float) + "\n")
    print(render(res))
    print(f"written: {out} and {js}")
