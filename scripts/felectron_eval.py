#!/usr/bin/env python
"""The one-time f-electron held-out evaluation.

    HARNESS_MODEL=mace-mpa-0-medium python scripts/felectron_eval.py open     # record the opening, queue engine 1
    HARNESS_MODEL=mace-mp-0-medium  python scripts/felectron_eval.py enqueue  # queue engine 2 over the SAME ids
    HARNESS_MODEL=mace-mpa-0-medium python scripts/felectron_eval.py score    # score the four hypotheses, once

`open` refuses while data/felectron_eval_log.json exists: the sample is opened once. `score` refuses
while reports/felectron_test.json exists: the sample is scored once.

EVERYTHING HERE IS FIXED BY data/felectron_evaluation_preregistration.json. The thresholds are the
LIVE production rule, stable -20 meV and unstable +10 meV, read from the pre-registration and checked
against it. Nothing is fitted, selected or searched on this sample: no certify, no diagnose, no
best_bound, no grid. The pre-registration forbids it, and this script contains no code that could.

Verdicts: PASS when the primary-confidence Clopper-Pearson lower bound >= target. FAIL when it is
below, INCLUDING when the point estimate is above target. INCONCLUSIVE only for the pre-specified
triggers: too_few_calls, unusable_rows, missing_second_engine, no_labelable_rows.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone

import pandas as pd

from harness import (calibration as CAL, config, confidence as C, felectron_eval as FE, jobqueue,
                     metrics as M, predict as P, routing as R, store)
from harness.config import QUEUE_DB, REPORTS_DIR, load_compute_config

INIT_CACHE = "felectron_eval_init_structs.json"
CSE_CACHE = "felectron_eval_cse.json"
AUTHORISED_BY = "Isac Smith, 2026-09-24"
PREREG_SHA256 = "d3995f66d562efd9893137e95a200ef103bc9a7e01ba3d7620356e7c7aafd4d2"
SAMPLE_SHA256 = "43a675a7b4d67d44a18c0ed35b5a12f5d27b3f09452fc55556aa2f27aa348445"
N_HYP = 4
PRIMARY_CONF = 1 - 0.05 / N_HYP          # 0.9875
SECONDARY_CONF = 0.95
MIN_CALLS = 20
MAX_UNUSABLE_FRAC = 0.02
REPORT_JSON = REPORTS_DIR / "felectron_test.json"
REPORT_MD = REPORTS_DIR / "felectron_test.md"
DEV_BOUNDS = {"A": 0.9171, "B": 0.9231}   # reports/felectron_topup.md, full family correction


def prereg() -> dict:
    """The pre-registration, refused unless its FULL sha256 is the one committed and pushed."""
    raw = FE.PREREG_FILE.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != PREREG_SHA256:
        raise SystemExit(f"ABORT - pre-registration sha256 {got} != the committed {PREREG_SHA256}")
    return json.loads(raw)


def sample_ids() -> list[str]:
    split = FE.load()
    if split["preregistration"]["sha256"] != PREREG_SHA256:
        raise SystemExit("ABORT - the sample was drawn under a different pre-registration")
    ids = FE.test_ids(unlock=True)          # verifies the sample's own recorded hash
    got = hashlib.sha256(",".join(ids).encode()).hexdigest()
    if got != SAMPLE_SHA256 or got != split["test"]["sha256"] or len(ids) != split["test"]["n"]:
        raise SystemExit(f"ABORT - sample sha256 {got} != the recorded {SAMPLE_SHA256}")
    return ids


def thresholds(Pr: dict) -> tuple[float, float]:
    t = Pr["thresholds_under_test"]
    t_s, t_u = t["stable_ev_per_atom"], t["unstable_ev_per_atom"]
    if (t_s, t_u) != (-0.02, 0.01):
        raise SystemExit(f"ABORT - thresholds {t_s}/{t_u} are not the pre-registered -0.02/+0.01")
    return t_s, t_u


def _engine(which):
    key, device, dtype = which
    return key, config.settings_tag(device, dtype, model=key)


def _assert_engine(expect) -> tuple[str, dict]:
    compute = load_compute_config()
    tag = config.settings_tag(compute["device"], compute["dtype"])
    key, want = _engine(expect)
    if config.ACTIVE_MODEL != key or tag != want:
        raise SystemExit(f"ABORT - engine mismatch: {config.ACTIVE_MODEL}/{tag} != {key}/{want}")
    config.model_path(key)
    print(f"engine {config.MODEL['name']} settings_tag {tag} - checkpoint sha256 verified")
    return tag, compute


def _enqueue(ids: list[str]) -> None:
    from harness import orchestrator as O
    from harness.suites import ood

    engine = CAL.PRODUCTION_ENGINE if config.ACTIVE_MODEL == CAL.PRODUCTION_ENGINE[0] else CAL.SECOND_ENGINE
    tag, compute = _assert_engine(engine)
    jobs = O.build_wbm_calibration_jobs(compute, ids=ids,
                                        init_cache=ood.WBM_DIR / INIT_CACHE,
                                        cse_cache=ood.WBM_DIR / CSE_CACHE, strict=True)
    done = store.completed_keys("ood", retry_failed=True)
    print("enqueue:", jobqueue.enqueue(jobs, QUEUE_DB, done_keys=done), f"({len(jobs)} jobs, tag {tag})")


def open_sample() -> None:
    """Record the opening, verify every hash, then queue the PRODUCTION engine. Once."""
    if FE.LOG_FILE.is_file():
        raise SystemExit(f"{FE.LOG_FILE} exists: the f-electron sample has already been opened. "
                         "It is opened once.")
    _assert_engine(CAL.PRODUCTION_ENGINE)
    Pr = prereg()
    t_s, t_u = thresholds(Pr)
    ids = sample_ids()
    bundle_sha = hashlib.sha256(CAL.BUNDLE_FILE.read_bytes()).hexdigest()
    if bundle_sha != Pr["thresholds_under_test"]["active_bundle_sha256"]:
        raise SystemExit(f"ABORT - the active bundle changed since pre-registration: {bundle_sha}")
    print(f"pre-registration verified: {PREREG_SHA256}")
    print(f"sample verified: n={len(ids)}, sha256 {SAMPLE_SHA256}")

    prod_key, prod_tag = _engine(CAL.PRODUCTION_ENGINE)
    sec_key, sec_tag = _engine(CAL.SECOND_ENGINE)
    FE.LOG_FILE.write_text(json.dumps({
        "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "authorised_by": AUTHORISED_BY,
        "harness_commit": CAL.harness_commit(),
        "set": "f-electron evaluation",
        "n": len(ids),
        "sha256": SAMPLE_SHA256,
        "source_file": "data/wbm_split_felectron_eval.json",
        "preregistration": {"file": "data/felectron_evaluation_preregistration.json",
                            "sha256": PREREG_SHA256},
        "thresholds_under_test": {"stable": t_s, "unstable": t_u},
        "active_bundle": {"file": "data/calibration_bundle.json", "sha256": bundle_sha},
        "engines": [
            {"model": prod_key, "settings_tag": prod_tag, "role": "primary",
             "checkpoint_sha256": config.MODELS[prod_key]["sha256"]},
            {"model": sec_key, "settings_tag": sec_tag, "role": "second / disagreement check",
             "checkpoint_sha256": config.MODELS[sec_key]["sha256"]},
        ],
        "rule": ("every threshold, exclusion, hypothesis, target, confidence and correction was fixed "
                 "before this file was written; nothing is fitted on this sample, and it is opened once"),
    }, indent=1) + "\n")
    print(f"\nOPENED. recorded in {FE.LOG_FILE}")
    _enqueue(ids)


def enqueue_only() -> None:
    """Queue the CURRENT engine over the already-opened sample. Adds no new structures."""
    if not FE.LOG_FILE.is_file():
        raise SystemExit("the sample has not been opened (run `open` first)")
    prereg()
    _enqueue(sample_ids())


# --- scoring: FIXED thresholds only ---------------------------------------------------------------

def score_side(sub: pd.DataFrame, t_s: float, t_u: float, side: str, target: float) -> dict:
    """Counts and bounds at the FIXED threshold. No selection of any kind happens here."""
    tol = M.ON_HULL_TOL
    if side == "stable":
        sel = sub.each_pred <= t_s + tol
        k = int(sub.stable[sel].sum())
    else:
        sel = (~(sub.each_pred <= t_s + tol)) & (sub.each_pred > t_u + tol)
        k = int((~sub.stable[sel]).sum())
    n = int(sel.sum())
    lo_p = C.cp_lower(k, n, PRIMARY_CONF) if n else float("nan")
    lo_s = C.cp_lower(k, n, SECONDARY_CONF) if n else float("nan")
    if n < MIN_CALLS:
        verdict, why = "INCONCLUSIVE", f"too_few_calls: {n} calls, below the pre-specified minimum of {MIN_CALLS}"
    elif lo_p >= target:
        verdict, why = "PASS", ""
    else:
        verdict, why = "FAIL", ("near-miss: the primary bound is below target; the point estimate being "
                               "above it does not change this" if k / n >= target else "")
    return {"threshold": t_s if side == "stable" else t_u, "calls": n, "correct": k, "errors": n - k,
            "point": (k / n) if n else float("nan"),
            "cp_lower_primary": lo_p, "cp_lower_secondary": lo_s,
            "target": target, "margin": lo_p - target if n else float("nan"),
            "verdict": verdict, "note": why}


def hypotheses(A: pd.DataFrame, B: pd.DataFrame, n_drawn: int, unusable: int, missing_2: int,
               Pr: dict) -> tuple[dict, list[str]]:
    """The four pre-registered hypotheses with every inconclusive trigger applied."""
    t_s, t_u = thresholds(Pr)
    tgt = Pr["targets"]
    triggers = []
    all_blocked = unusable / n_drawn > MAX_UNUSABLE_FRAC
    if all_blocked:
        triggers.append(f"unusable_rows: {unusable}/{n_drawn} = {unusable / n_drawn:.4f} > {MAX_UNUSABLE_FRAC}")
    blocked = {"A": len(A) == 0, "B": len(B) == 0}
    for p, b in blocked.items():
        if b:
            triggers.append(f"no_labelable_rows: path {p}")
    b_missing = (missing_2 / len(A) > MAX_UNUSABLE_FRAC) if len(A) else False
    if b_missing:
        triggers.append(f"missing_second_engine: {missing_2}/{len(A)} = {missing_2 / len(A):.4f} > {MAX_UNUSABLE_FRAC}")

    H = {}
    for hid, h in Pr["hypotheses"].items():
        sub = A if h["path"] == "A" else B
        target = tgt["stable_precision"] if h["side"] == "stable" else tgt["unstable_npv"]
        assert h["target"] == target and h["threshold_ev_per_atom"] == (t_s if h["side"] == "stable" else t_u)
        r = score_side(sub, t_s, t_u, h["side"], target)
        why = ("unusable_rows" if all_blocked else
               "no_labelable_rows" if blocked[h["path"]] else
               "missing_second_engine" if (h["path"] == "B" and b_missing) else None)
        if why:
            r["verdict"], r["note"] = "INCONCLUSIVE", f"{why} (pre-specified trigger)"
        H[hid] = {"path": h["path"], "side": h["side"], **r}
    return H, triggers


def overall(H: dict) -> str:
    v = {h["verdict"] for h in H.values()}
    if v == {"PASS"}:
        return "PASS"
    return "FAIL" if "FAIL" in v else "INCONCLUSIVE"


def score() -> None:
    if not FE.LOG_FILE.is_file():
        raise SystemExit("the sample has not been opened (run `open` first)")
    if REPORT_JSON.exists():
        raise SystemExit(f"{REPORT_JSON} exists: the f-electron sample is scored once.")
    log = json.loads(FE.LOG_FILE.read_text())
    Pr = prereg()
    if log["preregistration"]["sha256"] != PREREG_SHA256 or log["sha256"] != SAMPLE_SHA256:
        raise SystemExit("ABORT - the opening log disagrees with the recorded hashes")
    ids = sample_ids()

    d1 = CAL.calibration_table(CAL.PRODUCTION_ENGINE, set(ids), init_cache=INIT_CACHE)
    d2 = CAL.calibration_table(CAL.SECOND_ENGINE, set(ids), init_cache=INIT_CACHE)
    n_drawn, unusable = len(ids), len(ids) - len(d1)
    d = d1.assign(stable=d1.each_true <= M.ON_HULL_TOL,
                  pred_2=d1.wbm_id.map(d2.set_index("wbm_id").each_pred))

    b = CAL.load()
    pol_a = b.policy(with_second_engine=False, max_trustworthy_hull=None)
    pol_b = b.policy(with_second_engine=True, max_trustworthy_hull=None)
    pol_c = b.policy(with_second_engine=True, max_trustworthy_hull=P.MAX_TRUSTWORTHY_HULL_EV)
    A, B, Cc = d[R.labelable(d, pol_a)], d[R.labelable(d, pol_b)], d[R.labelable(d, pol_c)]
    missing_2 = int(A.pred_2.isna().sum())

    H, triggers = hypotheses(A, B, n_drawn, unusable, missing_2, Pr)
    t_s, t_u = thresholds(Pr)
    payload = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "opened_at": log["opened_at"], "authorised_by": log["authorised_by"],
        "harness_commit_at_open": log["harness_commit"], "harness_commit_at_score": CAL.harness_commit(),
        "sample_sha256": SAMPLE_SHA256, "preregistration_sha256": PREREG_SHA256,
        "active_bundle_sha256": hashlib.sha256(CAL.BUNDLE_FILE.read_bytes()).hexdigest(),
        "thresholds": {"stable": t_s, "unstable": t_u},
        "primary_confidence": PRIMARY_CONF, "secondary_confidence": SECONDARY_CONF,
        "population": {"drawn": n_drawn, "usable": len(d1), "unusable": unusable,
                       "guard_rejected_engine1": int(d1.attrs.get("n_rejected", 0)),
                       "guard_rejected_engine2": int(d2.attrs.get("n_rejected", 0)),
                       "second_engine_usable": len(d2),
                       "labelable_A": len(A), "labelable_B": len(B), "labelable_C": len(Cc),
                       "removed_by_disagreement": len(A) - len(B), "missing_second_engine": missing_2},
        "inconclusive_triggers_fired": triggers,
        "hypotheses": H, "overall": overall(H),
        "expected": {k: Pr["error_budget"]["primary"][k] for k in H},
        "path_C_descriptive": {"labelable": len(Cc),
                               "stable": score_side(Cc, t_s, t_u, "stable", Pr["targets"]["stable_precision"]),
                               "unstable": score_side(Cc, t_s, t_u, "unstable", Pr["targets"]["unstable_npv"])},
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=1, default=str) + "\n")
    REPORT_MD.write_text(render(payload, Pr))
    print(json.dumps({k: {kk: v[kk] for kk in ("calls", "errors", "point", "cp_lower_primary", "verdict")}
                      for k, v in H.items()}, indent=1, default=str))
    print(f"\nOVERALL: {payload['overall']}\nwrote {REPORT_JSON} and {REPORT_MD}")


def render(p: dict, Pr: dict) -> str:
    """reports/felectron_test.md, every figure from the payload, the outcome branch quoted verbatim."""
    H, pop, E = p["hypotheses"], p["population"], p["expected"]
    f4 = lambda x: "n/a" if x != x else f"{x:.4f}"  # noqa: E731
    branch = {"PASS": "all_four_pass", "FAIL": "any_fail", "INCONCLUSIVE": "any_inconclusive"}[p["overall"]]
    L = [
        "# f-electron held-out evaluation — the one-time result", "",
        f"Opened {p['opened_at']} at commit `{p['harness_commit_at_open']}`, **authorised by "
        f"{p['authorised_by']}**. Evaluated {p['evaluated_at']}. Sample sha256 `{p['sample_sha256']}`, "
        f"pre-registration sha256 `{p['preregistration_sha256']}` — both verified in full before any structure "
        "was queued, and again before scoring. Active bundle sha256 at scoring `"
        f"{p['active_bundle_sha256']}`.", "",
        "Every threshold, exclusion, hypothesis, target, confidence and correction was fixed in "
        "`reports/felectron_evaluation_preregistration.md`, committed at `37886a8` and **pushed before the "
        "sample was drawn**. Nothing was fitted on this sample. `scripts/felectron_eval.py` contains no "
        "`certify`, `diagnose`, `best_bound` or grid-search code.", "",
        "## Thresholds under test (fixed)", "",
        f"The LIVE production rule: stable **{p['thresholds']['stable'] * 1000:+.0f} meV**, unstable "
        f"**{p['thresholds']['unstable'] * 1000:+.0f} meV**, on both paths. Not re-derived here.", "",
        "## Population", "", "| | n |", "|---|---:|",
        f"| drawn | {pop['drawn']:,} |", f"| usable (production engine) | {pop['usable']:,} |",
        f"| unusable | **{pop['unusable']:,}** |",
        f"| guard-rejected, engine 1 / engine 2 | {pop['guard_rejected_engine1']} / {pop['guard_rejected_engine2']} |",
        f"| **labelable, Path A** | **{pop['labelable_A']:,}** |",
        f"| **labelable, Path B** | **{pop['labelable_B']:,}** |",
        f"| removed by the disagreement term | {pop['removed_by_disagreement']:,} |",
        f"| lacking a second-engine result | {pop['missing_second_engine']:,} |",
        f"| labelable, path C (descriptive) | {pop['labelable_C']:,} |", "",
        "Pre-registered inconclusive triggers fired: **"
        + ("; ".join(p["inconclusive_triggers_fired"]) or "NONE") + "**.", "",
        "## The four pre-registered hypotheses", "",
        f"Primary confidence **{p['primary_confidence']}** (Bonferroni over the four hypotheses). One-sided "
        "Clopper-Pearson. The verdict is read from the primary bound, never the point estimate or the 0.95 bound.", "",
        "| id | path | side | calls | correct | errors | point | CP-lower @0.9875 | CP-lower @0.95 | target | verdict |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for k, h in H.items():
        L.append(f"| **{k}** | {h['path']} | {h['side']} | {h['calls']:,} | {h['correct']:,} | {h['errors']:,} | "
                 f"{f4(h['point'])} | **{f4(h['cp_lower_primary'])}** | {f4(h['cp_lower_secondary'])} | "
                 f"{h['target']} | **{h['verdict']}** |")
    notes = [f"* {k}: {h['note']}" for k, h in H.items() if h["note"]]
    L += ["", f"**Overall: {p['overall']}** — the pre-registered rule is that all four must pass at the "
          "primary confidence.", ""] + (notes + [""] if notes else [])
    L += ["## Against the pre-registered expectations", "",
          "| id | expected calls | observed | ratio | expected errors | observed | max errors allowed | within budget |",
          "|---|---:|---:|---:|---:|---:|---:|---|"]
    for k, h in H.items():
        e = E[k]
        L.append(f"| {k} | {e['expected_calls']:,} | {h['calls']:,} | {h['calls'] / e['expected_calls']:.3f} | "
                 f"{e['expected_errors']} | {h['errors']} | {e['max_errors_allowed']} | "
                 f"{'yes' if h['errors'] <= e['max_errors_allowed'] else 'no'} |")
    L += ["", "## Held-out bound against development bound", "",
          f"The development bounds at n=8,800 were **{DEV_BOUNDS['A']}** (A) and **{DEV_BOUNDS['B']}** (B) on the "
          f"stable side. The held-out bounds are {f4(H['EA1']['cp_lower_primary'])} (EA1) and "
          f"{f4(H['EB1']['cp_lower_primary'])} (EB1). **A held-out bound is expected to exceed a development bound "
          "at similar n, and that is not the held-out data being better.** The development level (0.999863) paid "
          "for searching a 61-point grid across 6 family x side selections; this evaluation selected nothing and "
          "pays only the 4-fold correction (0.9875). The point estimates are the comparable quantity.", "",
          "## Dependence", "",
          "Path B is a strict subset of Path A (A minus rows whose engines disagree beyond tolerance), so the "
          "tests are nested and positively dependent. As pre-registered: Bonferroni is valid under arbitrary "
          "dependence, the conjunctive rule makes it strictly conservative, and no 'effective' correction was "
          f"estimated from the observed overlap. Here B retained {pop['labelable_B']:,} of A's "
          f"{pop['labelable_A']:,} labelable rows.", "",
          "## Path C — descriptive only, never a verdict", "",
          "| side | labelable | calls | errors | point | CP-lower @0.9875 |", "|---|---:|---:|---:|---:|---:|"]
    for side in ("stable", "unstable"):
        c = p["path_C_descriptive"][side]
        L.append(f"| {side} | {p['path_C_descriptive']['labelable']:,} | {c['calls']:,} | {c['errors']} | "
                 f"{f4(c['point'])} | {f4(c['cp_lower_primary'])} |")
    L += ["", "## The pre-registered outcome branch that applies (quoted verbatim)", "",
          f"`outcome_rule.{branch}`:", "", "> " + Pr["outcome_rule"][branch], "",
          "> " + Pr["outcome_rule"]["asymmetry_acknowledged"], "",
          "## What this does not do", "",
          "No threshold was changed and `data/calibration_bundle.json` is untouched by this evaluation. "
          "Recording a confirmation (if any) is a separate production commit on an explicit decision. This "
          "result says nothing about intermetallic, pnictide or any family other than f-electron, or about "
          "anything off WBM.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("open", "enqueue", "score"):
        raise SystemExit(__doc__)
    {"open": open_sample, "enqueue": enqueue_only, "score": score}[sys.argv[1]]()
