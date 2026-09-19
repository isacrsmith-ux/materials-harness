#!/usr/bin/env python
"""The one-time pnictide held-out evaluation.

    python scripts/pnictide_eval.py open      # records the opening, then queues both engines
    python scripts/pnictide_eval.py score     # scores the four hypotheses, once

`open` refuses while data/pnictide_eval_log.json exists: the sample is opened once.

EVERYTHING HERE IS FIXED BY data/pnictide_evaluation_preregistration.json. The thresholds are
stable -20 meV and unstable +0 meV. Nothing is fitted, selected or searched on this sample: no
certify, no diagnose, no best_bound, no grid. The pre-registration forbids it, and this script
contains no code that could do it.

Verdicts: PASS when the primary-confidence Clopper-Pearson lower bound >= target. FAIL when it is
below, INCLUDING when the point estimate is above target. There is no 'ambiguous' verdict for a
primary hypothesis. INCONCLUSIVE only for the pre-specified triggers.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from harness import (calibration as CAL, config, confidence as C, jobqueue, metrics as M,
                     pnictide_eval as PE, predict as P, routing as R, store)
from harness.config import QUEUE_DB, REPORTS_DIR, load_compute_config

sys.path.insert(0, str(Path(__file__).parent))

INIT_CACHE = "pnictide_eval_init_structs.json"
CSE_CACHE = "pnictide_eval_cse.json"
N_HYP = 4
PRIMARY_CONF = 1 - 0.05 / N_HYP          # 0.9875
SECONDARY_CONF = 0.95
MIN_CALLS = C.MIN_SELECTED               # 20
MAX_UNUSABLE_FRAC = 0.02


def _engine(which):
    key, device, dtype = which
    tag = config.settings_tag(device, dtype, model=key)
    return key, tag


def _assert_engine(expect_key: str) -> tuple[str, dict]:
    compute = load_compute_config()
    tag = config.settings_tag(compute["device"], compute["dtype"])
    _, want = _engine(CAL.PRODUCTION_ENGINE if "mpa" in expect_key else CAL.SECOND_ENGINE)
    if config.ACTIVE_MODEL != expect_key or tag != want:
        raise SystemExit(f"ABORT - engine mismatch: {config.ACTIVE_MODEL}/{tag} != {expect_key}/{want}")
    config.model_path(expect_key)
    print(f"engine {config.MODEL['name']} settings_tag {tag} - checkpoint sha256 verified")
    return tag, compute


def open_sample() -> None:
    """Record the opening, verify every hash, then queue both engines. Once."""
    if PE.LOG_FILE.is_file():
        raise SystemExit(f"{PE.LOG_FILE} exists: the pnictide sample has already been opened. "
                         "It is opened once.")
    split = PE.load()
    prereg_sha = hashlib.sha256(PE.PREREG_FILE.read_bytes()).hexdigest()
    if prereg_sha != split["preregistration"]["sha256"]:
        raise SystemExit("ABORT - the pre-registration has changed since the sample was drawn:\n"
                         f"  now  {prereg_sha}\n  then {split['preregistration']['sha256']}")
    ids = PE.test_ids(unlock=True)          # verifies the sample's own recorded hash
    got = hashlib.sha256(",".join(ids).encode()).hexdigest()
    if got != split["test"]["sha256"] or len(ids) != split["test"]["n"]:
        raise SystemExit("ABORT - the sample does not match its recorded hash")
    print(f"pre-registration verified: {prereg_sha}")
    print(f"sample verified: n={len(ids)}, sha256 {got}")

    prod_key, prod_tag = _engine(CAL.PRODUCTION_ENGINE)
    sec_key, sec_tag = _engine(CAL.SECOND_ENGINE)
    PE.LOG_FILE.write_text(json.dumps({
        "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness_commit": CAL.harness_commit(),
        "set": "pnictide evaluation (round 4)",
        "n": len(ids),
        "sha256": got,
        "source_file": "data/wbm_split_pnictide_eval.json",
        "preregistration": {"file": "data/pnictide_evaluation_preregistration.json",
                            "sha256": prereg_sha},
        "thresholds_under_test": split["thresholds_under_test"],
        "active_bundle": {"file": "data/calibration_bundle.json",
                          "sha256": hashlib.sha256(CAL.BUNDLE_FILE.read_bytes()).hexdigest()},
        "engines": [
            {"model": prod_key, "settings_tag": prod_tag, "role": "primary",
             "checkpoint_sha256": config.MODELS[prod_key]["sha256"]},
            {"model": sec_key, "settings_tag": sec_tag, "role": "second / disagreement check",
             "checkpoint_sha256": config.MODELS[sec_key]["sha256"]},
        ],
        "rule": ("every threshold, exclusion, hypothesis, target, confidence and correction was fixed "
                 "before this file was written; nothing is fitted on this sample, and it is opened once"),
    }, indent=1) + "\n")
    print(f"\nOPENED. recorded in {PE.LOG_FILE}")

    from harness import orchestrator as O
    from harness.suites import ood

    tag, compute = _assert_engine(config.ACTIVE_MODEL)
    jobs = O.build_wbm_calibration_jobs(compute, ids=ids,
                                        init_cache=ood.WBM_DIR / INIT_CACHE,
                                        cse_cache=ood.WBM_DIR / CSE_CACHE, strict=True)
    done = store.completed_keys("ood", retry_failed=True)
    print("enqueue:", jobqueue.enqueue(jobs, QUEUE_DB, done_keys=done), f"({len(jobs)} jobs, tag {tag})")
    _warn_one_runner_per_engine()


def _warn_one_runner_per_engine() -> None:
    """A runner executes ONE settings tag. Queueing two engines and draining once leaves the other
    engine's jobs to fail with SettingsMismatch - which is what happened on the first attempt at this
    evaluation. The guard caught it, but the operator should not have to rediscover that.
    """
    with jobqueue.connect() as con:
        rows = con.execute(
            "SELECT substr(job_key, instr(job_key,'@')+1) tag, COUNT(*) n FROM queue "
            "WHERE suite='ood' AND status IN ('pending','running') GROUP BY tag").fetchall()
    tags = {r["tag"]: r["n"] for r in rows}
    if len(tags) > 1:
        print("\n  NOTE: the queue now holds pending jobs under more than one settings tag:")
        for t, n in sorted(tags.items()):
            print(f"    {t}: {n:,} pending")
        print("  A runner executes ONE tag. Drain each engine with its own HARNESS_MODEL, or the")
        print("  other engine's jobs will fail with SettingsMismatch and need requeueing.")


def enqueue_only() -> None:
    """Queue the OTHER engine over the already-opened sample. Adds no new structures."""
    if not PE.LOG_FILE.is_file():
        raise SystemExit("the sample has not been opened (run `open` first)")
    from harness import orchestrator as O
    from harness.suites import ood

    tag, compute = _assert_engine(config.ACTIVE_MODEL)
    ids = PE.test_ids(unlock=True)
    jobs = O.build_wbm_calibration_jobs(compute, ids=ids,
                                        init_cache=ood.WBM_DIR / INIT_CACHE,
                                        cse_cache=ood.WBM_DIR / CSE_CACHE, strict=True)
    done = store.completed_keys("ood", retry_failed=True)
    print("enqueue:", jobqueue.enqueue(jobs, QUEUE_DB, done_keys=done), f"({len(jobs)} jobs, tag {tag})")
    _warn_one_runner_per_engine()


def _table(engine, ids):
    d = CAL.calibration_table(engine, set(ids), init_cache=INIT_CACHE)
    return d, int(d.attrs.get("n_rejected", 0))


def _score_side(sub: pd.DataFrame, t: float, side: str, target: float) -> dict:
    """Counts and bounds at the FIXED threshold. No selection of any kind happens here."""
    tol = M.ON_HULL_TOL
    if side == "stable":
        sel = sub.each_pred <= t + tol
        k = int(sub.stable[sel].sum())
    else:
        sel = (~(sub.each_pred <= -0.02 + tol)) & (sub.each_pred > t + tol)
        k = int((~sub.stable[sel]).sum())
    n = int(sel.sum())
    lo_p = C.cp_lower(k, n, PRIMARY_CONF) if n else float("nan")
    lo_s = C.cp_lower(k, n, SECONDARY_CONF) if n else float("nan")
    if n < MIN_CALLS:
        verdict, why = "INCONCLUSIVE", f"only {n} calls, below the pre-specified minimum of {MIN_CALLS}"
    elif lo_p >= target:
        verdict, why = "PASS", ""
    else:
        verdict, why = "FAIL", ("the primary bound is below target; the point estimate being above it "
                               "does not change this" if n and k / n >= target else "")
    return {"threshold": t, "calls": n, "correct": k, "errors": n - k,
            "point": (k / n) if n else float("nan"),
            "cp_lower_primary": lo_p, "cp_lower_secondary": lo_s,
            "target": target, "margin": lo_p - target if n else float("nan"),
            "verdict": verdict, "note": why}


def score() -> None:
    if not PE.LOG_FILE.is_file():
        raise SystemExit("the sample has not been opened (run `open` first)")
    log = json.loads(PE.LOG_FILE.read_text())
    split = PE.load()
    if hashlib.sha256(PE.PREREG_FILE.read_bytes()).hexdigest() != log["preregistration"]["sha256"]:
        raise SystemExit("ABORT - the pre-registration changed after the sample was opened")
    ids = PE.test_ids(unlock=True)
    t_s = split["thresholds_under_test"]["stable"]
    t_u = split["thresholds_under_test"]["unstable"]

    d1, rej1 = _table(CAL.PRODUCTION_ENGINE, ids)
    d2, rej2 = _table(CAL.SECOND_ENGINE, ids)
    n_drawn = len(ids)
    unusable = n_drawn - len(d1)
    d = d1.assign(stable=d1.each_true <= M.ON_HULL_TOL,
                  pred_2=d1.wbm_id.map(d2.set_index("wbm_id").each_pred))

    b = CAL.load()
    pol_a = b.policy(with_second_engine=False, max_trustworthy_hull=None)
    pol_b = b.policy(with_second_engine=True, max_trustworthy_hull=None)
    pol_c = b.policy(with_second_engine=True, max_trustworthy_hull=P.MAX_TRUSTWORTHY_HULL_EV)
    mask_a, mask_b, mask_c = R.labelable(d, pol_a), R.labelable(d, pol_b), R.labelable(d, pol_c)
    A, B, Cc = d[mask_a], d[mask_b], d[mask_c]
    missing_2 = int(A.pred_2.isna().sum())

    # pre-specified inconclusive triggers, evaluated BEFORE any verdict is read
    triggers = []
    if unusable / n_drawn > MAX_UNUSABLE_FRAC:
        triggers.append(f"unusable_rows: {unusable}/{n_drawn} = {unusable/n_drawn:.4f} > {MAX_UNUSABLE_FRAC}")
    if len(A) == 0 or len(B) == 0:
        triggers.append("no_labelable_rows")
    pathB_blocked = missing_2 / len(A) > MAX_UNUSABLE_FRAC if len(A) else True
    if pathB_blocked:
        triggers.append(f"missing_second_engine: {missing_2}/{len(A)} = "
                        f"{missing_2/max(len(A),1):.4f} > {MAX_UNUSABLE_FRAC}")

    H = {
        "PA1": _score_side(A, t_s, "stable", C.TARGET_PRECISION),
        "PA2": _score_side(A, t_u, "unstable", C.TARGET_NPV),
        "PB1": _score_side(B, t_s, "stable", C.TARGET_PRECISION),
        "PB2": _score_side(B, t_u, "unstable", C.TARGET_NPV),
    }
    if pathB_blocked:
        for h in ("PB1", "PB2"):
            H[h]["verdict"] = "INCONCLUSIVE"
            H[h]["note"] = "Path B blocked by the missing-second-engine trigger"

    overall = ("PASS" if all(v["verdict"] == "PASS" for v in H.values())
               else "FAIL / NOT ELIGIBLE FOR PROMOTION")
    payload = {"evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "opened_at": log["opened_at"], "sample_sha256": log["sha256"],
               "preregistration_sha256": log["preregistration"]["sha256"],
               "thresholds": {"stable": t_s, "unstable": t_u},
               "primary_confidence": PRIMARY_CONF, "secondary_confidence": SECONDARY_CONF,
               "population": {"drawn": n_drawn, "usable": len(d1), "unusable": unusable,
                              "guard_rejected_engine1": rej1, "guard_rejected_engine2": rej2,
                              "labelable_A": len(A), "labelable_B": len(B), "labelable_C": len(Cc),
                              "removed_by_disagreement": len(A) - len(B),
                              "missing_second_engine": missing_2},
               "inconclusive_triggers_fired": triggers,
               "hypotheses": H, "overall": overall,
               "path_C_descriptive": {
                   "labelable": len(Cc),
                   "stable": _score_side(Cc, t_s, "stable", C.TARGET_PRECISION),
                   "unstable": _score_side(Cc, t_u, "unstable", C.TARGET_NPV)},
               }
    out = REPORTS_DIR / "pnictide_test.json"
    out.write_text(json.dumps(payload, indent=1, default=str) + "\n")
    print(json.dumps({k: {kk: v[kk] for kk in ("calls", "correct", "errors", "point",
                                               "cp_lower_primary", "margin", "verdict")}
                      for k, v in H.items()}, indent=1, default=str))
    print(f"\nOVERALL: {overall}")
    print(f"wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    {"open": open_sample, "enqueue": enqueue_only, "score": score}[sys.argv[1]]()
