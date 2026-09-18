#!/usr/bin/env python
"""How large would an independent fluoride evaluation have to be to settle the carve-out?

The halide held-out evaluation validated its three hypotheses and left the carve-out's JUSTIFICATION
unresolved: on calibration the pooled halide rule labelled fluorides at 0.8971 (below the 0.90
target), on the held-out half at 0.9439 (above it), and neither sample can rule the other out. This
sizes the study that could.

Uses NO locked data and opens nothing. The two historical fluoride results are treated as FIXED
EVIDENCE and as design inputs only; they are never pooled, and no threshold is refitted here. The
threshold under study stays the pooled halide -20 meV/atom rule exactly as it is.

    python scripts/fluoride_power.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
from scipy.stats import beta, binom

from harness import confidence as C
from harness.config import REPORTS_DIR

OUT_MD = REPORTS_DIR / "fluoride_followup_power.md"
OUT_JSON = REPORTS_DIR / "fluoride_followup_power.json"

TARGET = C.TARGET_PRECISION          # 0.90
CONF = 0.95                          # one-sided, a single pre-registered hypothesis
POWERS = (0.80, 0.90)

# Fixed historical evidence. Design inputs only - never pooled, never refitted.
CAL = {"n_calls": 350, "n_correct": 314, "point": 314 / 350,
       "source": "spec v2 fit on the 6,300-structure halide calibration draw, labelable rows"}
TEST = {"n_calls": 107, "n_correct": 101, "point": 101 / 107,
        "source": "R1 of the halide locked-half evaluation, 2026-09-18"}

# Observed yield, for converting calls into structures. From the held-out half, which is the
# cleanest single measurement of the whole chain.
LABELABLE_FRAC = 1659 / 2000
FLUORIDE_CALL_RATE = 107 / 643        # stable calls per labelable fluoride at -20 meV
POOL_AVAILABLE = 429                  # unspent fluoride candidates after the leakage guard


def cp_lower(k, n, conf=CONF):
    return 0.0 if k <= 0 else float(beta.ppf(1 - conf, k, n - k + 1))


def cp_upper(k, n, conf=CONF):
    return 1.0 if k >= n else float(beta.ppf(conf, k + 1, n - k))


def n_to_certify(p_true: float, power: float, conf=CONF, cap=200_000):
    """Calls needed for the one-sided lower bound to clear TARGET with probability >= power."""
    for n in _ladder(cap):
        kstar = next((k for k in range(n + 1) if cp_lower(k, n, conf) >= TARGET), None)
        if kstar is not None and 1 - binom.cdf(kstar - 1, n, p_true) >= power:
            return n
    return None


def n_to_establish_deficit(p_true: float, power: float, conf=CONF, cap=200_000):
    """Calls needed for the one-sided UPPER bound to fall below TARGET with probability >= power,
    i.e. to establish that fluoride really is short of the promise."""
    for n in _ladder(cap):
        ks = [k for k in range(n + 1) if cp_upper(k, n, conf) < TARGET]
        if ks and binom.cdf(max(ks), n, p_true) >= power:
            return n
    return None


def _ladder(cap):
    n = 20
    while n <= cap:
        yield n
        n = int(n * 1.15) + 1


def structures_for(n_calls: int | None) -> int | None:
    if n_calls is None:
        return None
    return int(np.ceil(n_calls / (LABELABLE_FRAC * FLUORIDE_CALL_RATE)))


def build() -> dict:
    grid = [0.80, 0.84, 0.86, 0.88, 0.8971, 0.92, 0.9439, 0.96]
    rows = []
    for p in grid:
        r = {"p_true": p}
        for pw in POWERS:
            cert = n_to_certify(p, pw) if p > TARGET else None
            defi = n_to_establish_deficit(p, pw) if p < TARGET else None
            r[f"certify_calls_{int(pw*100)}"] = cert
            r[f"certify_structures_{int(pw*100)}"] = structures_for(cert)
            r[f"deficit_calls_{int(pw*100)}"] = defi
            r[f"deficit_structures_{int(pw*100)}"] = structures_for(defi)
        rows.append(r)

    # power of the study we could actually run from what is left of the pool
    max_calls = int(np.floor(POOL_AVAILABLE * LABELABLE_FRAC * FLUORIDE_CALL_RATE))
    feasible = {"pool_available": POOL_AVAILABLE, "max_calls": max_calls,
                "vs_evidence_in_hand": {"calibration_calls": CAL["n_calls"], "heldout_calls": TEST["n_calls"]}}
    for p, lab in ((0.8971, "calibration estimate"), (0.9439, "held-out estimate"),
                   (0.86, "a deficit worth acting on")):
        kstar = next((k for k in range(max_calls + 1) if cp_lower(k, max_calls, CONF) >= TARGET), None)
        ks = [k for k in range(max_calls + 1) if cp_upper(k, max_calls, CONF) < TARGET]
        feasible[f"p={p}"] = {
            "label": lab,
            "power_to_certify": float(1 - binom.cdf(kstar - 1, max_calls, p)) if kstar is not None else 0.0,
            "power_to_establish_deficit": float(binom.cdf(max(ks), max_calls, p)) if ks else 0.0}

    return {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "question": ("is fluoride's true precision under the POOLED halide -20 meV rule below "
                         "0.90 (a validity deficit, carve out) or at/above it (no deficit, keep pooled)?"),
            "uses_locked_data": False, "pools_historical_results": False, "refits_any_threshold": False,
            "target": TARGET, "confidence": CONF, "powers": list(POWERS),
            "fixed_evidence": {"calibration": CAL, "held_out": TEST},
            "yield_assumptions": {"labelable_fraction": LABELABLE_FRAC,
                                  "stable_calls_per_labelable_fluoride": FLUORIDE_CALL_RATE,
                                  "source": "the halide locked half, the cleanest single measurement of the chain"},
            "sizing": rows, "feasibility": feasible}


def render(D: dict) -> str:
    cal, tst = D["fixed_evidence"]["calibration"], D["fixed_evidence"]["held_out"]
    fz = D["feasibility"]
    L = ["# Follow-up: how large would an independent fluoride study have to be?", "",
         f"Generated {D['created_at']}. **Uses no locked data and opens nothing.** The two historical "
         "fluoride results are treated as fixed evidence and used only as design inputs: they are "
         "not pooled, and no threshold is refitted. The rule under study is the pooled halide "
         "-20 meV/atom threshold exactly as it stands.", "",
         "## The question", "", D["question"], "",
         "| evidence | calls | correct | point precision | source |", "|---|---:|---:|---:|---|",
         f"| calibration | {cal['n_calls']} | {cal['n_correct']} | {cal['point']:.4f} | {cal['source']} |",
         f"| held out | {tst['n_calls']} | {tst['n_correct']} | {tst['point']:.4f} | {tst['source']} |", "",
         "These straddle the 0.90 target and neither excludes the other. **They are preserved as they "
         "are.** Pooling them would produce a number that is neither a calibration estimate nor a "
         "held-out one, and would quietly turn a failed replication into a tuned threshold.", "",
         "## Sizing", "",
         f"One-sided Clopper-Pearson at {D['confidence']}, target {D['target']}. 'Certify' means the "
         "lower bound clears 0.90 - the pooled rule is shown to be sound on fluoride. 'Establish a "
         "deficit' means the upper bound falls below 0.90 - the carve-out's premise is shown to be "
         "real. Structures are calls divided by the observed yield "
         f"({D['yield_assumptions']['labelable_fraction']:.3f} labelable x "
         f"{D['yield_assumptions']['stable_calls_per_labelable_fluoride']:.4f} calls per labelable fluoride).", "",
         "| true precision | certify @80% | @90% | structures @80% | establish deficit @80% | @90% | structures @80% |",
         "|---:|---:|---:|---:|---:|---:|---:|"]
    for r in D["sizing"]:
        def g(k):
            v = r.get(k)
            return f"{v:,}" if isinstance(v, int) else "-"
        L.append(f"| {r['p_true']:.4f} | {g('certify_calls_80')} | {g('certify_calls_90')} | "
                 f"{g('certify_structures_80')} | {g('deficit_calls_80')} | {g('deficit_calls_90')} | "
                 f"{g('deficit_structures_80')} |")
    L += ["", "Read the two halves of that table against each other. Near 0.90 both columns explode: "
              "at a true precision of 0.8971 - the calibration estimate - establishing a deficit is "
              "hopeless, because the effect size is 0.0029. **If fluoride's true precision really is "
              "0.897, no feasible study can prove it, and none should: a rule that is 0.3 points "
              "short of its promise is not what the carve-out was for.** The carve-out is only worth "
              "its cost if the true value is meaningfully below target, and that is the row to size "
              "against.", "",
          "## What the remaining pool can actually support", "",
          f"WBM's unique-prototype pool has **{fz['pool_available']} unspent fluoride candidates** "
          "after every split's exclusions and the reduced-formula leakage guard. At the observed "
          f"yield that is about **{fz['max_calls']} stable calls** - fewer than the "
          f"{fz['vs_evidence_in_hand']['heldout_calls']} the held-out half already produced, and far "
          f"fewer than the {fz['vs_evidence_in_hand']['calibration_calls']} on calibration.", "",
          "| if the truth is | power to certify | power to establish a deficit |", "|---|---:|---:|"]
    for k, v in fz.items():
        if not k.startswith("p="):
            continue
        L.append(f"| {k[2:]} ({v['label']}) | {v['power_to_certify']:.3f} | "
                 f"{v['power_to_establish_deficit']:.3f} |")
    L += ["", "**The remaining WBM pool cannot settle this question at any power worth having.** An "
              "independent fluoride evaluation of useful size has to come from somewhere else - a "
              "targeted DFT campaign on fluorides, or a non-WBM source such as Alexandria or new MP "
              "additions, with its own pre-registration and its own held-out half.", "",
          "## The cost of the carve-out, stated plainly", "",
          "The fluoride carve-out **reduces recall and increases DFT routing**. It has never been a "
          "routing improvement and was never adopted as one; on the calibration halide draw, "
          "splitting fluoride out moves:", "",
          "| | pooled (no carve-out) | carved out | change |", "|---|---:|---:|---|",
          "| share sent to DFT | 0.096 | 0.192 | **doubles** |",
          "| recall of truly stable | 0.599 | 0.338 | **falls 44%** |",
          "| 'likely stable' calls | 771 | 421 | -45% |", "",
          "Out of sample the same direction shows in the two pre-registered results, by arithmetic on "
          "figures already reported and with no further analysis of the held-out set: H1 made **157** "
          "'likely stable' calls on non-fluoride halides, and R1 shows the pooled rule would have "
          "made **107** more on the fluorides. So the carve-out costs **107 of 264 labels, 40.5%**, "
          "on the held-out half.", "",
          "> **Therefore: adopt the fluoride carve-out only if a fluoride-specific validity deficit "
          "is established with adequate evidence.** The cost is certain, immediate and large; the "
          "benefit is a precision guarantee that the held-out data did not confirm. A carve-out that "
          "throws away two fifths of a family's labels has to be paid for by a demonstrated failure "
          "of the pooled rule, not by a calibration-set point estimate that did not replicate.", "",
          "## Status", "",
          "| | |", "|---|---|",
          "| H1-H3 | validated on the locked half; preserved as the primary result |",
          "| fluoride taxonomy decision | **unresolved** - the calibration deficit did not reproduce on the held-out point estimate, and the held-out sample was too small to certify the pooled rule at 0.90 either |",
          "| production taxonomy | unchanged; `confidence.family()` has no fluoride |",
          "| active bundle | v1, `data/calibration_bundle.json`, unmodified |",
          "| specification v2 | frozen, not promoted |",
          "| locked sets | five closed; the halide half opened once and reported |", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    D = build()
    OUT_JSON.write_text(json.dumps(D, indent=1, default=float) + "\n")
    OUT_MD.write_text(render(D))
    print(render(D))
    print(f"written: {OUT_MD} and {OUT_JSON}")
