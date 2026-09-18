#!/usr/bin/env python
"""The ONE-TIME halide locked-half evaluation, exactly as pre-registered.

    python scripts/halide_eval.py open       # log the opening, verify the hash, enqueue
    python scripts/halide_eval.py evaluate   # apply the FIXED rules and report

`open` refuses if data/halide_test_log.json exists: the half is opened once. Nothing is fitted at
any point - every threshold, exclusion and criterion is read from the committed pre-registration and
from specification v2, and applied unchanged.
"""

from __future__ import annotations

import hashlib
import importlib.util as _u
import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pymatgen.core import Composition

from harness import calibration as CAL, config, confidence as C, jobqueue, metrics as M, splits, store
from harness.config import DATA_DIR, QUEUE_DB, REPORTS_DIR, load_compute_config

_spec = _u.spec_from_file_location("_tax", "scripts/round2_taxonomy_decision.py")
_tax = _u.module_from_spec(_spec)
_spec.loader.exec_module(_tax)

LOG = DATA_DIR / "halide_test_log.json"
PREREG = DATA_DIR / "halide_evaluation_preregistration.json"
SPEC = DATA_DIR / "calibration_spec_v2.json"
OUT_MD = REPORTS_DIR / "halide_test.md"
OUT_JSON = REPORTS_DIR / "halide_test.json"
INIT_CACHE = "halide_test_init_structs.json"
CSE_CACHE = "halide_test_cse.json"


def _prereg():
    return json.loads(PREREG.read_text()), json.loads(SPEC.read_text())


def _assert_engine():
    key, device, dtype = CAL.PRODUCTION_ENGINE
    compute = load_compute_config()
    tag = config.settings_tag(compute["device"], compute["dtype"])
    expect = config.settings_tag(device, dtype, model=key)
    if config.ACTIVE_MODEL != key or tag != expect:
        raise SystemExit(f"ABORT - engine mismatch: {config.ACTIVE_MODEL} / {tag} != {key} / {expect}")
    config.model_path(key)
    print(f"engine {config.MODEL['name']} settings_tag {tag} - checkpoint sha256 verified")
    return compute, tag


def open_half() -> None:
    P, S = _prereg()
    if LOG.is_file():
        raise SystemExit(f"{LOG} exists: the halide locked half has already been opened. It is opened once.")
    compute, tag = _assert_engine()

    ids = splits.family_test_ids("halide", unlock=True)          # verifies its own recorded hash
    got = hashlib.sha256(",".join(sorted(ids)).encode()).hexdigest()
    want = P["locked_set"]["sha256"]
    if got != want or len(ids) != P["locked_set"]["n"]:
        raise SystemExit(f"ABORT - locked set does not match the pre-registration:\n"
                         f"  n   {len(ids)} vs {P['locked_set']['n']}\n  sha {got}\n      {want}")
    print(f"locked set verified: n={len(ids)}, sha256 {got} == pre-registered")

    LOG.write_text(json.dumps({
        "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness_commit": CAL.harness_commit(),
        "set": "halide locked test (round 1)", "n": len(ids), "sha256": got,
        "source_file": "data/wbm_split_oxide_halide.json",
        "preregistration": {"file": "data/halide_evaluation_preregistration.json", "sha256": hashlib.sha256(PREREG.read_bytes()).hexdigest()},
        "specification": {"file": "data/calibration_spec_v2.json", "version": S["spec_version"],
                          "sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest()},
        "engine": {"model": config.ACTIVE_MODEL, "settings_tag": tag},
        "rule": ("every threshold, exclusion and criterion was fixed before this file was written; "
                 "nothing is fitted on this set, and it is opened once"),
    }, indent=1) + "\n")
    print(f"opening logged: {LOG}")

    from harness import orchestrator as O
    from harness.suites import ood
    jobs = O.build_wbm_calibration_jobs(compute, ids=ids,
                                        init_cache=ood.WBM_DIR / INIT_CACHE,
                                        cse_cache=ood.WBM_DIR / CSE_CACHE, strict=True)
    done = set()
    for suite in ("ood",):
        done |= store.completed_keys(suite, retry_failed=True)
    print("enqueue:", jobqueue.enqueue(jobs, QUEUE_DB, done_keys=done), f"({len(jobs)} jobs)")


def _cp(k: int, n: int, conf: float) -> float:
    return C.cp_lower(k, n, conf) if n else float("nan")


def _two_sided(k: int, n: int, conf: float = 0.95):
    from scipy.stats import beta
    if n == 0:
        return (float("nan"),) * 2
    a = (1 - conf) / 2
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a, k + 1, n - k))
    return lo, hi


CAL_R1 = (314, 350)   # calibration fluorides under the pooled -20 meV rule, from spec v2's fit


def _r1_posthoc(k: int, n: int) -> dict | None:
    """Descriptive comparison of the two R1 measurements. NOT a pre-registered test; it characterises
    the ambiguity and changes no verdict."""
    import math
    from statistics import NormalDist

    k1, n1 = CAL_R1
    if not n:
        return None
    p1, p2 = k1 / n1, k / n
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n)
    z = (p2 - p1) / se if se else float("nan")
    return {"cal_n": n1, "cal_k": k1, "cal_point": p1, "test_n": n, "test_k": k, "test_point": p2,
            "difference": p2 - p1, "se": se, "z": z,
            "p_two_sided": 2 * (1 - NormalDist().cdf(abs(z))), "power_ratio": n / n1}


def evaluate() -> None:
    P, S = _prereg()
    if not LOG.is_file():
        raise SystemExit("the half has not been opened (run `open` first)")
    _assert_engine()
    ids = splits.family_test_ids("halide", unlock=True)

    d = CAL.calibration_table(CAL.PRODUCTION_ENGINE, set(ids), init_cache=INIT_CACHE)
    n_usable, n_rejected = len(d), int(d.attrs["n_rejected"])
    d = d.assign(stable=d.each_true <= M.ON_HULL_TOL)
    lab = _tax.labelable_mask(d)
    n_excluded_labelable = int((~lab).sum())
    d = d[lab]
    is_f = d.formula.map(lambda x: "F" in {e.symbol for e in Composition(x).elements})
    nonf, flu = d[~is_f], d[is_f]

    th, tol = S["thresholds"], M.ON_HULL_TOL
    conf1 = P["statistics"]["primary_confidence"]
    conf2 = P["statistics"]["secondary_confidence"]

    def result(hid, g, kind, t, target):
        if kind == "stable":
            sel = g.each_pred <= t + tol
            correct = g.stable[sel]
        else:
            stable_t = th["halide"]["stable"] if hid == "H2" else th["fluoride"]["stable"]
            not_stable = (g.each_pred > stable_t + tol) if stable_t is not None else pd.Series(True, index=g.index)
            sel = not_stable & (g.each_pred > t + tol)
            correct = ~g.stable[sel]
        n, k = int(sel.sum()), int(correct.sum())
        lo1, lo2 = _cp(k, n, conf1), _cp(k, n, conf2)
        return {"id": hid, "n_population": len(g), "n_calls": n, "n_correct": k, "n_errors": n - k,
                "point": (k / n) if n else float("nan"),
                "cp_lower_primary": lo1, "cp_lower_secondary": lo2,
                "target": target, "pass": bool(n and lo1 >= target)}

    H = [result("H1", nonf, "stable", th["halide"]["stable"], C.TARGET_PRECISION),
         result("H2", nonf, "unstable", th["halide"]["unstable"], C.TARGET_NPV),
         result("H3", flu, "unstable", th["fluoride"]["unstable"], C.TARGET_NPV)]

    # R1 - diagnostic: the pooled halide rule applied to the held-out fluorides
    pooled_t = th["halide"]["stable"]
    sel = flu.each_pred <= pooled_t + tol
    n, k = int(sel.sum()), int(flu.stable[sel].sum())
    lo, hi = _two_sided(k, n)
    point = (k / n) if n else float("nan")
    R1 = {"id": "R1", "threshold": pooled_t, "n_calls": n, "n_correct": k, "n_errors": n - k,
          "point": point, "ci95_two_sided": [lo, hi],
          "cp_lower_secondary": _cp(k, n, conf2),
          "expectation": P["rationale_check"]["prereg_expectation"],
          "deficit_reproduced": bool(np.isfinite(point) and point < C.TARGET_PRECISION),
          "contradicts_prereg": bool(np.isfinite(point) and point >= C.TARGET_PRECISION
                                     and _cp(k, n, conf2) >= C.TARGET_PRECISION)}

    out = {"evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "log": json.loads(LOG.read_text()),
           "population": {"n_ids": len(ids), "n_usable": n_usable,
                          "n_rejected_by_guard": n_rejected,
                          "n_excluded_not_labelable": n_excluded_labelable,
                          "n_labelable": len(d), "n_non_fluoride": len(nonf), "n_fluoride": len(flu)},
           "confidence": {"primary": conf1, "secondary": conf2},
           "hypotheses": H, "rationale_check": R1,
           "r1_posthoc": _r1_posthoc(k, n),
           "overall_pass": all(h["pass"] for h in H)}
    OUT_JSON.write_text(json.dumps(out, indent=1, default=float) + "\n")
    OUT_MD.write_text(render(out, P))
    print(render(out, P))
    print(f"written: {OUT_MD} and {OUT_JSON}")


def render(o: dict, P: dict) -> str:
    p = o["population"]
    L = ["# Halide locked-half evaluation — the one-time result", "",
         f"Evaluated {o['evaluated_at']}. Opened {o['log']['opened_at']} at commit "
         f"`{o['log']['harness_commit']}`. Locked set sha256 `{o['log']['sha256']}`, verified against "
         "the pre-registration before any structure was queued.", "",
         "Every threshold, exclusion and criterion was fixed in "
         "`reports/halide_evaluation_preregistration.md` and committed before the half was opened. "
         "Nothing was fitted on this set.", "",
         "## Population", "",
         "| | n |", "|---|---:|",
         f"| locked ids | {p['n_ids']:,} |",
         f"| usable (guard rejections counted and excluded) | {p['n_usable']:,} |",
         f"| rejected by the energy-plausibility guard | {p['n_rejected_by_guard']} |",
         f"| excluded as not labelable (weak element / structure change) | {p['n_excluded_not_labelable']:,} |",
         f"| **labelable** | **{p['n_labelable']:,}** |",
         f"| of which non-fluoride | {p['n_non_fluoride']:,} |",
         f"| of which fluoride | {p['n_fluoride']:,} |", "",
         "## H1-H3, against the frozen criteria", "",
         f"Primary confidence {o['confidence']['primary']:.5f} (Bonferroni over the three "
         f"hypotheses); ordinary {o['confidence']['secondary']} reported alongside. The verdict is "
         "taken from the primary, as pre-registered.", "",
         "| id | population | calls | correct | errors | point | CP-lower (primary) | CP-lower (95%) | target | result |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    pre = {h["id"]: h for h in P["hypotheses"]}
    for h in o["hypotheses"]:
        L.append(f"| **{h['id']}** | {h['n_population']:,} | {h['n_calls']} | {h['n_correct']} | "
                 f"{h['n_errors']} | {h['point']:.4f} | **{h['cp_lower_primary']:.4f}** | "
                 f"{h['cp_lower_secondary']:.4f} | {h['target']:.2f} | "
                 f"**{'PASS' if h['pass'] else 'FAIL'}** |")
    L += ["", "Against the pre-registered error budget:", "",
          "| id | errors allowed | errors observed | calls expected | calls observed |",
          "|---|---:|---:|---:|---:|"]
    for h in o["hypotheses"]:
        q = pre[h["id"]]
        L.append(f"| {h['id']} | {q['max_errors_to_pass']} | {h['n_errors']} | "
                 f"{q['expected_n_calls']} | {h['n_calls']} |")
    r = o["rationale_check"]
    L += ["", f"**Overall: {'PASS' if o['overall_pass'] else 'FAIL'}** — the pre-registered rule is "
              "that all three must pass at the primary confidence.", "",
          "## R1 — rationale check (diagnostic, not pass/fail)", "",
          "Does the pooled halide rule still show a precision deficit on fluorides, out of sample? "
          "This is the carve-out's entire justification.", "",
          "| | |", "|---|---|",
          f"| pooled halide stable threshold applied to fluorides | {r['threshold']*1000:+.0f} meV/atom |",
          f"| calls | {r['n_calls']} |",
          f"| correct | {r['n_correct']} |",
          f"| errors | {r['n_errors']} |",
          f"| **point precision** | **{r['point']:.4f}** |",
          f"| two-sided 95% CI | [{r['ci95_two_sided'][0]:.4f}, {r['ci95_two_sided'][1]:.4f}] |",
          f"| one-sided 95% lower bound | {r['cp_lower_secondary']:.4f} |",
          f"| on calibration | 0.8971 on 350 calls |",
          f"| pre-registered expectation | {r['expectation']} |", "",
          (f"**The deficit is reproduced out of sample** (point precision {r['point']:.4f} < 0.90). "
           "The carve-out's justification holds." if r["deficit_reproduced"] else
           ("**THE PRE-REGISTERED EXPECTATION IS CONTRADICTED.** The pooled rule does NOT show a "
            f"precision deficit on the held-out fluorides (point {r['point']:.4f}, lower bound "
            f"{r['cp_lower_secondary']:.4f} >= 0.90). Per the pre-registered interpretation rule, "
            "adoption must be revisited even though the pass criteria were met, and this evaluation "
            "stops for a taxonomy decision." if r["contradicts_prereg"] else
            f"**Ambiguous.** Point precision {r['point']:.4f} is at or above 0.90 but its lower bound "
            f"({r['cp_lower_secondary']:.4f}) does not clear 0.90, so the deficit is neither "
            "reproduced nor refuted on this sample.")), ""]
    n = o.get("r1_posthoc")
    if n:
        L += ["## Post-hoc note on R1 (descriptive, not a pre-registered test)", "",
              "The two R1 measurements are of the same pre-specified quantity on two disjoint samples:", "",
              "| sample | calls | correct | point precision |", "|---|---:|---:|---:|",
              f"| calibration fluorides | {n['cal_n']} | {n['cal_k']} | {n['cal_point']:.4f} |",
              f"| held-out fluorides | {n['test_n']} | {n['test_k']} | {n['test_point']:.4f} |", "",
              f"Difference {n['difference']:+.4f} (SE {n['se']:.4f}, z {n['z']:.2f}, two-sided p "
              f"{n['p_two_sided']:.3f}). The held-out sample carries {n['power_ratio']:.2f}x the calls "
              "of the calibration sample, because the halide locked half holds 643 labelable "
              "fluorides against the calibration draw's 1,888. No expected n for R1 was "
              "pre-registered, and with these counts the interval cannot separate 0.90 from 0.94.", "",
              "This note characterises the ambiguity; it does not resolve it, and it changes no "
              "verdict. The pre-registered interpretation rule was met on neither branch: the "
              "deficit was not reproduced, and it was not refuted either.", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    {"open": open_half, "evaluate": evaluate}[sys.argv[1]]()
