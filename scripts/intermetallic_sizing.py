#!/usr/bin/env python
"""TRACK 1 — intermetallic sizing. Analysis only: draws nothing, pre-registers nothing.

    python scripts/intermetallic_sizing.py reports/intermetallic_sizing.md

Answers one question before any fresh candidate is spent: could a realistically sized independent
test actually distinguish pass from fail for the proposed intermetallic rule, given that its
unstable-side bound clears its target by only +0.0039 on development data?

It uses the EXACT procedure a future held-out evaluation would use, which is the procedure the
pnictide evaluation used: one-sided Clopper-Pearson, Bonferroni over the four hypotheses
(1 - 0.05/4 = 0.9875), NO grid correction because the thresholds would be fixed in advance, and NO
family correction because only one family would be tested.

Nothing here touches a locked set, the bundle, or the pnictide sample.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import binom

from harness import confidence as C

N_HYP = 4
PRIMARY_CONF = 1 - 0.05 / N_HYP
SECONDARY_CONF = 0.95
POOL = 33707          # unspent intermetallic candidates after round 4
N_DRAWN_DEV = 4000    # the round-4 development draw the rates come from

# Development observations, from reports/round4_carried_over.json (Path A fit) and
# reports/round4_pathb_refit.json (B-refit). Design inputs only - never pooled with anything.
DEV = {
    "IA1 Path-A stable":   {"calls": 182,  "errors": 4,   "target": C.TARGET_PRECISION, "bound": 0.9197369487841499},
    "IA2 Path-A unstable": {"calls": 3365, "errors": 115, "target": C.TARGET_NPV,       "bound": 0.9548},
    "IB1 Path-B stable":   {"calls": 181,  "errors": 4,   "target": C.TARGET_PRECISION, "bound": 0.9193},
    "IB2 Path-B unstable": {"calls": 3300, "errors": 115, "target": C.TARGET_NPV,       "bound": 0.9539},
}
for v in DEV.values():
    v["point"] = (v["calls"] - v["errors"]) / v["calls"]
    v["rate"] = v["calls"] / N_DRAWN_DEV


def _kstar(n, target, conf):
    """Smallest k with cp_lower(k, n, conf) >= target, by binary search.

    cp_lower is monotone non-decreasing in k at fixed n, so bisection is exact and turns an O(n)
    scan of beta quantiles into O(log n). The naive scan made the sensitivity sweep intractable.
    """
    lo, hi = 0, n
    if C.cp_lower(n, n, conf) < target:
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if C.cp_lower(mid, n, conf) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _power_at(n, p_true, target, conf):
    ks = _kstar(n, target, conf)
    if ks is None:
        return 0.0
    return float(1 - binom.cdf(ks - 1, n, p_true)) if ks > 0 else 1.0


def calls_needed(p_true, target, conf, power, cap=400_000):
    """Smallest n with P(CP_lower(K,n,conf) >= target) >= power, K ~ Bin(n, p_true).

    Power is not perfectly monotone in n (k must be an integer, so it sawtooths), so this brackets
    on a geometric ladder and then refines linearly inside the last interval rather than trusting a
    pure bisection.
    """
    if p_true <= target:
        return None                     # the bound can never clear a target the truth sits at or below
    prev = 20
    n = 20
    while n <= cap:
        if _power_at(n, p_true, target, conf) >= power:
            break
        prev, n = n, max(n + 1, int(n * 1.35))
    else:
        return None
    step = max(1, (n - prev) // 64)
    for m in range(prev, n + 1, step):
        if _power_at(m, p_true, target, conf) >= power:
            for mm in range(max(prev, m - step), m + 1):
                if _power_at(mm, p_true, target, conf) >= power:
                    return mm
            return m
    return n


def sizing_row(h, p_true, conf):
    d = DEV[h]
    out = {}
    for power in (0.80, 0.90, 0.95):
        n = calls_needed(p_true, d["target"], conf, power)
        out[f"{power:.0%}"] = {"calls": n,
                               "structures": int(math.ceil(n / d["rate"])) if n else None,
                               "feasible": (n is not None and math.ceil(n / d["rate"]) <= POOL)}
    return out


def main(out_md: Path) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {"generated_at": now, "kind": "sizing analysis only; nothing drawn, nothing pre-registered",
               "procedure": {"bound": "one-sided Clopper-Pearson", "primary_confidence": PRIMARY_CONF,
                             "multiplicity": "Bonferroni over 4 hypotheses; no grid correction; no family correction",
                             "targets": {"stable_precision": C.TARGET_PRECISION, "unstable_npv": C.TARGET_NPV}},
               "unspent_pool": POOL, "development": DEV, "at_development_point": {}, "sensitivity": {}}

    L = ["# Track 1 — intermetallic sizing (analysis only)", "",
         f"Generated {now}. **Nothing was drawn and nothing was pre-registered.** This asks whether an "
         "independent test of the proposed intermetallic rule could distinguish pass from fail at a "
         "size the remaining pool can supply, before any fresh candidate is spent.", "",
         "Procedure is the one a held-out evaluation would use, identical to the pnictide evaluation: "
         f"one-sided Clopper-Pearson at **{PRIMARY_CONF}** (Bonferroni over 4 hypotheses), **no grid "
         "correction** (thresholds would be fixed in advance), **no family correction** (one family "
         "tested). Targets: stable precision 0.90, unstable NPV 0.95.", "",
         "## The development starting point", "",
         "| hypothesis | proposed rule | calls | errors | point | dev bound | target | dev margin |",
         "|---|---|---:|---:|---:|---:|---:|---:|"]
    RULES = {"IA1 Path-A stable": "-20 meV", "IA2 Path-A unstable": "-10 meV",
             "IB1 Path-B stable": "-20 meV", "IB2 Path-B unstable": "-10 meV"}
    for h, d in DEV.items():
        L.append(f"| {h} | {RULES[h]} | {d['calls']:,} | {d['errors']} | {d['point']:.4f} | "
                 f"{d['bound']:.4f} | {d['target']} | **{d['bound'] - d['target']:+.4f}** |")
    L += ["", "The two unstable-side rows are the problem this analysis exists for: they clear their "
              "target by **+0.0048 and +0.0039** on the very data the thresholds were selected on, "
              "which is the most optimistic estimate available.", "",
          "## Required size, powered against the development point estimate", "",
          "| hypothesis | truth assumed | calls/structure | 80% power | 90% power | 95% power |",
          "|---|---:|---:|---|---|---|"]
    for h, d in DEV.items():
        r = sizing_row(h, d["point"], PRIMARY_CONF)
        payload["at_development_point"][h] = r
        cells = []
        for p in ("80%", "90%", "95%"):
            s = r[p]["structures"]
            cells.append(f"{s:,} str" + ("" if r[p]["feasible"] else " **> pool**") if s else "**not reachable**")
        L.append(f"| {h} | {d['point']:.4f} | {d['rate']:.5f} | " + " | ".join(cells) + " |")
    L += ["", f"Unspent intermetallic pool: **{POOL:,}** candidates.", "",
          "## Sensitivity — the question that actually decides feasibility", "",
          "A study is only worth running if it can separate pass from fail at the truth values that "
          "are actually plausible. The development point estimate is the optimistic end of that range; "
          "the development *bound* is the pessimistic end. Both are plausible.", ""]
    for h, d in DEV.items():
        tgt = d["target"]
        if tgt == C.TARGET_NPV:
            truths = [0.9500, 0.9550, 0.9600, 0.9650, d["point"], 0.9700, 0.9750]
        else:
            truths = [0.9000, 0.9200, 0.9400, 0.9600, d["point"], 0.9800, 0.9900]
        truths = sorted(set(round(t, 4) for t in truths))
        L += [f"### {h} (rule {RULES[h]}, target {tgt})", "",
              "| assumed true value | effect size vs target | 80% power | 90% power | feasible within pool? |",
              "|---:|---:|---|---|---|"]
        payload["sensitivity"][h] = {}
        for t in truths:
            r = sizing_row(h, t, PRIMARY_CONF)
            payload["sensitivity"][h][str(t)] = r
            s80, s90 = r["80%"]["structures"], r["90%"]["structures"]
            mark = " *(development point)*" if abs(t - d["point"]) < 1e-9 else (
                " *(development bound)*" if abs(t - d["bound"]) < 5e-4 else "")
            fe = "yes" if (s80 and s80 <= POOL) else "**no**"
            L.append(f"| {t:.4f}{mark} | {t - tgt:+.4f} | "
                     f"{(f'{s80:,}' if s80 else 'not reachable')} | "
                     f"{(f'{s90:,}' if s90 else 'not reachable')} | {fe} |")
        L += [""]
    # --- recommended design and its honest limits
    CAND = (2000, 2500, 2750, 3000, 3500, 4000)
    L += ["## Power at candidate draw sizes (development point estimates)", "",
          "| n drawn | IA1 | IA2 | IB1 | IB2 | worst case |", "|---:|---:|---:|---:|---:|---:|"]
    best = None
    for N in CAND:
        ps = []
        for h, d in DEV.items():
            calls = int(round(N * d["rate"]))
            ps.append(_power_at(calls, d["point"], d["target"], PRIMARY_CONF))
        payload.setdefault("power_at_candidate_n", {})[str(N)] = {
            h: ps[i] for i, h in enumerate(DEV)}
        L.append(f"| {N:,} | " + " | ".join(f"{x:.3f}" for x in ps) + f" | **{min(ps):.3f}** |")
        if min(ps) >= 0.95 and best is None:
            best = N
    L += ["", "Power is not monotone in n: the number of allowed errors is an integer, so it "
              "sawtooths (2,750 beats 3,000 on the stable side). That is why a size should be read "
              "off this table rather than from a single power target.", "",
          f"### Recommended: n = {best:,} if this is ever pre-registered", "",
          f"At {best:,} drawn structures every hypothesis has power >= 0.96 against the development "
          f"point estimates, and {POOL - best:,} candidates would remain unspent. Expected calls and "
          "error budgets:", "",
          "| hypothesis | expected calls | expected errors | max errors allowed |",
          "|---|---:|---:|---:|"]
    for h, d in DEV.items():
        calls = int(round(best * d["rate"]))
        ks = _kstar(calls, d["target"], PRIMARY_CONF)
        L.append(f"| {h} | {calls:,} | {calls * (1 - d['point']):.1f} | {calls - ks:,} |")
        payload.setdefault("recommended", {})["n_draw"] = best
        payload["recommended"].setdefault("budget", {})[h] = {
            "expected_calls": calls, "expected_errors": round(calls * (1 - d["point"]), 1),
            "max_errors_allowed": calls - ks}
    L += ["", "### What this design could NOT settle", "",
          "The binding constraint is **not** the thin unstable-side margin. It is the stable side's "
          "call rate: only about 4.5% of drawn structures become a stable call, against 82-84% for "
          "the unstable side. The unstable side's margin is thin but its *effect size* is large "
          "(0.0152-0.0158 above target), and effect size is what drives power.", "",
          "The real limit is the pessimistic branch. If intermetallic's true stable precision were "
          "0.9200 - the development lower bound, and entirely plausible - certifying it would need "
          "roughly **43,500 structures at 80% power**, which exceeds the whole remaining pool of "
          f"{POOL:,}. On the unstable side a true value at the development bound (0.9550) would need "
          "about 20,700, which the pool can just afford but which is seven times the recommended "
          "draw.", "",
          "So a pass at n = " + f"{best:,}" + " would mean the rule behaves as development suggested. "
          "A failure would be genuinely ambiguous: it could not distinguish 'the rule is worse than "
          "development implied' from 'the truth is in the 0.92-0.96 band where this size has no "
          "power'. That asymmetry should be written into any pre-registration before the draw, not "
          "discovered afterwards.", "",
          "Neither the stable nor the unstable side can be certified if the truth sits exactly at "
          "target: at an effect size of zero no finite sample clears a one-sided bound, which is why "
          "the 0.9000 and 0.9500 rows read 'not reachable'. That is arithmetic, not pessimism.", ""]
    out_md.write_text("\n".join(L) + "\n")
    out_md.with_suffix(".json").write_text(json.dumps(payload, indent=1, default=str) + "\n")
    print(f"wrote {out_md}\nwrote {out_md.with_suffix('.json')}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
