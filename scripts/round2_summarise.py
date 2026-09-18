#!/usr/bin/env python
"""Summarise the phase 5 multi-start and phase 6 retry runs into tables the report transcribes.

    python scripts/round2_summarise.py multistart
    python scripts/round2_summarise.py retry

Writes results/round2_{multistart,retry}_summary.json and reports/round2_phase{5,6}_*.md.
Counts are of candidates, and every exclusion is reported as counted-and-excluded: a start that
the guard rejected still appears in n_excluded_starts, it is never silently removed.
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from harness.config import REPORTS_DIR, RESULTS_DIR

BINS = ["<0", "0–0.025", "0.025–0.1", "0.1–0.3", ">0.3"]


def _load(path):
    return json.loads(path.read_text())


def _rate(g, col):
    n = int(g[col].notna().sum())
    k = int(g[col].fillna(False).sum())
    return n, k, (k / n if n else float("nan"))


def multistart():
    raw = _load(RESULTS_DIR / "round2_multistart.json")
    d = pd.DataFrame([{k: v for k, v in r.items() if k != "starts"} for r in raw["rows"]])
    d["bin"] = pd.Categorical(d["bin"], BINS, ordered=True)

    def agg(g):
        n = len(g)
        return {"n": n,
                "n_all_three_usable": int((g.n_usable_starts == 3).sum()),
                "n_starts_excluded": int(g.n_excluded_starts.sum()),
                "n_comparable": int(g.disagreement.notna().sum()),
                "disagreement_rate": float(g.disagreement.mean()),
                "structure_disagreement": float((g.structures_match == False).mean()),  # noqa: E712
                "energy_disagreement": float(g.energy_disagreement.fillna(False).mean()),
                "median_energy_spread_mev": float(g.energy_spread_mev.median())}

    by_family = {g: agg(gd) for g, gd in d.groupby("group")}
    by_bin = {str(b): agg(gd) for b, gd in d.groupby("bin", observed=True)}
    by_family_bin = {f"{g}|{b}": agg(gd) for (g, b), gd in d.groupby(["group", "bin"], observed=True)}
    out = {"source": "results/round2_multistart.json", "created_at": raw["created_at"],
           "engine": raw["engine"], "settings_tag": raw["settings_tag"], "starts": raw["starts"],
           "energy_spread_threshold_mev": raw["energy_spread_threshold_mev"],
           "disagreement": raw["disagreement"],
           "overall": agg(d), "by_family": by_family, "by_bin": by_bin, "by_family_bin": by_family_bin}
    (RESULTS_DIR / "round2_multistart_summary.json").write_text(json.dumps(out, indent=1) + "\n")

    L = ["# Phase 5 — multi-start structure verification", "",
         f"Source: `results/round2_multistart.json`. Engine {raw['engine']}, settings_tag "
         f"`{raw['settings_tag']}`. {len(d)} candidates, each relaxed from three starting "
         "configurations instead of one.", "",
         "| start | what it is |", "|---|---|"]
    for k, v in raw["starts"].items():
        L.append(f"| `{k}` | {v} |")
    L += ["", f"A candidate is counted as **disagreeing** when its usable starts do not all land in "
              f"the same structure, or their predicted hull distances span more than "
              f"{raw['energy_spread_threshold_mev']:.0f} meV/atom. Starts the convergence or "
              "energy-plausibility guard rejected are counted and excluded, never dropped: they "
              "appear in `starts excluded` and reduce the number of starts a candidate can be "
              "compared on.", "",
         "## By family", "",
         "| family | n | all 3 starts usable | starts excluded | disagreement | structure | energy | median spread |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for g, a in sorted(by_family.items()):
        L.append(f"| {g} | {a['n']} | {a['n_all_three_usable']} | {a['n_starts_excluded']} | "
                 f"{a['disagreement_rate']:.3f} | {a['structure_disagreement']:.3f} | "
                 f"{a['energy_disagreement']:.3f} | {a['median_energy_spread_mev']:.1f} meV |")
    a = out["overall"]
    L.append(f"| **all** | **{a['n']}** | {a['n_all_three_usable']} | {a['n_starts_excluded']} | "
             f"**{a['disagreement_rate']:.3f}** | {a['structure_disagreement']:.3f} | "
             f"{a['energy_disagreement']:.3f} | {a['median_energy_spread_mev']:.1f} meV |")
    L += ["", "## By true hull-distance bin", "",
          "| bin | n | disagreement | structure | energy | median spread |", "|---|---:|---:|---:|---:|---:|"]
    for b in BINS:
        if b not in by_bin:
            continue
        a = by_bin[b]
        L.append(f"| {b} | {a['n']} | {a['disagreement_rate']:.3f} | {a['structure_disagreement']:.3f} | "
                 f"{a['energy_disagreement']:.3f} | {a['median_energy_spread_mev']:.1f} meV |")
    (REPORTS_DIR / "round2_phase5_multistart.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def retry():
    raw = _load(RESULTS_DIR / "round2_retry.json")
    rows = raw["rows"]
    d = pd.DataFrame(rows)
    d["bin"] = pd.Categorical(d["bin"], BINS, ordered=True)

    # Each failure class is scored on the criterion that class is about.
    CRIT = {"not_converged": ("usable_after", "a converged, physically plausible result now exists"),
            "guard_rejected": ("usable_after", "a converged, physically plausible result now exists"),
            "multistart_disagree": ("reproduced", "the lowest-energy result is reached from at least two starts"),
            "left_its_start": ("stayed_in_start", "some attempt ends in the basin of the structure it was given")}

    by_class = {}
    for cls, (col, meaning) in CRIT.items():
        g = d[d.classes.map(lambda cs: cls in cs)]
        if not len(g):
            continue
        resolved = int(g[col].fillna(False).sum())
        by_class[cls] = {"n": len(g), "criterion": col, "meaning": meaning,
                         "resolved": resolved, "genuine": len(g) - resolved,
                         "resolved_rate": resolved / len(g)}

    by_family = {}
    for fam, g in d.groupby("group"):
        row = {"n": len(g)}
        for cls, (col, _m) in CRIT.items():
            gg = g[g.classes.map(lambda cs: cls in cs)]
            if len(gg):
                r = int(gg[col].fillna(False).sum())
                row[cls] = {"n": len(gg), "resolved": r, "genuine": len(gg) - r}
        by_family[fam] = row

    out = {"source": "results/round2_retry.json", "created_at": raw["created_at"],
           "engine": raw["engine"], "settings_tag": raw["settings_tag"], "ladder": raw["ladder"],
           "unchanged": raw["unchanged"], "n_candidates": raw["n_candidates"],
           "by_class_input": raw["by_class"], "by_class": by_class, "by_family": by_family,
           "by_bin": {str(b): {"n": len(g), "usable_after": int(g.usable_after.fillna(False).sum())}
                      for b, g in d.groupby("bin", observed=True)}}
    (RESULTS_DIR / "round2_retry_summary.json").write_text(json.dumps(out, indent=1) + "\n")

    L = ["# Phase 6 — retesting every failure found in phases 1-5", "",
         f"Source: `results/round2_retry.json`. Engine {raw['engine']}, settings_tag "
         f"`{raw['settings_tag']}`. Retry ladder: {raw['ladder']}.", "",
         f"**{raw['unchanged']}.** A retried job either genuinely converges to a plausible, "
         "structure-matched result or it stays counted-and-excluded.", "",
         f"{raw['n_candidates']} candidates were in at least one failure class. A candidate can be "
         "in several, so the class counts sum to more than the total.", "",
         "## Outcome by failure class", "",
         "| failure class | n | resolved | genuine | rate | what 'resolved' means for this class |",
         "|---|---:|---:|---:|---:|---|"]
    for cls, a in by_class.items():
        L.append(f"| {cls} | {a['n']} | {a['resolved']} | {a['genuine']} | "
                 f"{a['resolved_rate']:.3f} | {a['meaning']} |")
    L += ["", "## Outcome by family", "",
          "| family | n | " + " | ".join(f"{c} res/gen" for c in CRIT) + " |",
          "|---|---:|" + "---:|" * len(CRIT)]
    for fam, row in sorted(by_family.items()):
        cells = []
        for c in CRIT:
            v = row.get(c)
            cells.append(f"{v['resolved']}/{v['genuine']}" if v else "-")
        L.append(f"| {fam} | {row['n']} | " + " | ".join(cells) + " |")
    (REPORTS_DIR / "round2_phase6_retry.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"multistart": multistart, "retry": retry}[sys.argv[1]]()
