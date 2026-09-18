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
from harness.config import REPORTS_DIR

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


def _mixed_valence(d):
    """Two or more distinct transition metals, or one TM in a formula whose stoichiometry admits
    more than one integer oxidation state for it (pymatgen's own guess returning >1 distinct state)."""
    from pymatgen.core import Composition

    def f(formula):
        c = Composition(formula)
        try:
            guesses = c.oxi_state_guesses(max_sites=-10)
        except Exception:  # noqa: BLE001 — an unguessable composition is simply not flagged
            return False
        if not guesses:
            return False
        from pymatgen.core import Element
        tms = [e.symbol for e in c.elements if Element(e.symbol).is_transition_metal]
        return any(len({round(g[t]) for t in tms if t in g}) > 1 for g in guesses) or len(tms) > 1

    return d.formula.map(f)


SUBFAMILIES = {
    "fluoride": _has("F"),
    "nonfluoride": lambda d: ~_has("F")(d),
    "tm": _tm,
    "maingroup": lambda d: ~_tm(d),
    "mixed_valence": _mixed_valence,
    "single_valence": lambda d: ~_mixed_valence(d),
}


# --- report ------------------------------------------------------------------------------------------

def rows_for(group: str, targets=((0.90, "stable"), (0.95, "unstable")), alt_target: float = 0.80) -> dict:
    d = resolve(group)
    d = d.assign(stable=d.each_true <= M.ON_HULL_TOL)
    out = {"group": group, "n_requested": d.attrs.get("n_requested"), "n_usable": len(d),
           "n_rejected": d.attrs.get("n_rejected"), "base_rate": float(d.stable.mean()) if len(d) else float("nan"),
           "diagnoses": [], "alt": None}
    for target, side in targets:
        out["diagnoses"].append(round2.diagnose(d.each_pred, d.stable, target, side))
    stable_dx = out["diagnoses"][0]
    if stable_dx["certified_threshold"] is None:
        out["alt"] = round2.diagnose(d.each_pred, d.stable, alt_target, "stable")
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
         "rather than dropped.", "",
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
          "| group | side | target | best t | n selected | k | point | CP-lower | verdict | n selected needed | factor |",
          "|---|---|---:|---|---:|---:|---:|---:|---|---:|---:|"]
    for r in results:
        for dx in r["diagnoses"]:
            L.append(f"| {r['group']} | {dx['side']} | {dx['target']:.2f} | {mev(dx['best_threshold'])} | "
                     f"{dx['n_selected']} | {dx['k']} | {fmt(dx['point'])} | {fmt(dx['cp_lower'])} | "
                     f"{dx['verdict']} | {dx['n_selected_needed'] or '-'} | "
                     f"{fmt(dx['scale_factor'], 2) if dx['scale_factor'] else '-'} |")
    alts = [r for r in results if r["alt"]]
    if alts:
        L += ["", "### Stable side at the alternate 0.80 target (test 7's fallback)", "",
              "| group | best t | n selected | point | CP-lower | certified at 0.80 |", "|---|---|---:|---:|---:|---|"]
        for r in alts:
            a = r["alt"]
            L.append(f"| {r['group']} | {mev(a['best_threshold'])} | {a['n_selected']} | {fmt(a['point'])} | "
                     f"{fmt(a['cp_lower'])} | {mev(a['certified_threshold']) if a['certified_threshold'] is not None else 'no'} |")
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
    out = REPORTS_DIR / sys.argv[2]
    res = [rows_for(g) for g in sys.argv[3:]]
    out.write_text(render(res))
    print(render(res))
    print(f"written: {out}")
