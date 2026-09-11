"""The one-time evaluation of the complete system on the locked WBM test set (Phase 5).

start() records data/final_test_log.json (refused if it exists: the test set is evaluated once) and unlocks the
test ids for the queue. Every rule is fitted on the CALIBRATION set only: conformal bounds, certified per-family
thresholds, known-weak elements, and the engine-disagreement tolerance (the 95th percentile of |primary − second|
predicted hull distance on calibration, i.e. the 5 % most disputed calibration structures would be flagged).
evaluate() then applies them unchanged to the test structures and writes reports/final_test.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from harness import compare, splits
from harness import metrics as M
from harness.config import DATA_DIR, MODELS, REPORTS_DIR, ROOT, settings_tag

FINAL_LOG = DATA_DIR / "final_test_log.json"
DISAGREEMENT_QUANTILE = 0.95


def started() -> bool:
    return FINAL_LOG.is_file()


def start(models: list[str]) -> dict:
    if FINAL_LOG.is_file():
        raise RuntimeError(f"{FINAL_LOG} exists: the locked test set has already been opened")
    split = splits.load_split()
    log = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "models": models,
           "test_sha256": split["test"]["sha256"], "n_test": split["test"]["n"],
           "rule": "all thresholds fitted on calibration only; applied once to the test set"}
    FINAL_LOG.write_text(json.dumps(log, indent=1) + "\n")
    return log


def build_test_jobs(compute: dict) -> list[dict]:
    """Relaxations of every test structure for the ACTIVE model (only after start())."""
    from harness.orchestrator import MODEL, _plain, _settings
    from harness.suites import ood

    if not started():
        raise PermissionError("final evaluation not started (python -m harness final-test --start ...)")
    tag, settings = _settings(compute)
    ids = splits.test_ids(unlock=True)
    starts = ood.load_structures(ids, cache_file=ood.WBM_DIR / "test_init_structs.json")
    summary = ood.load_summary().set_index("material_id")
    jobs = []
    for rank, wid in enumerate(ids):
        if wid in starts:
            key = f"{wid}@{tag}"
            jobs.append({"suite": "ood", "job_key": key, "rank": rank, "n_atoms": len(starts[wid]), "model": MODEL["file"],
                         "settings": settings, "priority": -len(starts[wid]),
                         "inputs": {"job_key": key, "wbm_id": wid, "structure": starts[wid],
                                    "ref": _plain(summary.loc[wid].to_dict()), "suite": "ood"}})
    return jobs


def _table(key: str, device: str, dtype: str, ids: set, init_cache: str) -> pd.DataFrame:
    from harness.report import _start_changed
    from harness.suites import ood

    df = ood.table(settings_tag(device, dtype, model=key))
    df = df[df.wbm_id.isin(ids)]
    n_all = len(df)
    df = df[df.rejection.isna()].copy()
    df["structure_changed"] = _start_changed(settings_tag(device, dtype, model=key) + "_" + init_cache, df, init_cache)
    df.attrs["n_rejected"] = n_all - len(df)
    return df


def evaluate(primary: tuple[str, str, str], second: tuple[str, str, str] | None) -> str:
    from harness import confidence as C
    from harness import routing as R
    from harness.report import _costs

    split = splits.load_split()
    cal_ids, test_ids = set(split["calibration"]["ids"]), set(splits.test_ids(unlock=True))
    cal = _table(*primary, cal_ids, "calibration_init_structs.json")
    test = _table(*primary, test_ids, "test_init_structs.json")
    tol = None
    if second:
        for name, df, ids, cache in (("cal", cal, cal_ids, "calibration_init_structs.json"), ("test", test, test_ids, "test_init_structs.json")):
            s = _table(*second, ids, cache).set_index("wbm_id").each_pred
            df["pred_2"] = df.wbm_id.map(s)
        both = cal.dropna(subset=["pred_2"])
        tol = float(np.quantile((both.each_pred - both.pred_2).abs(), DISAGREEMENT_QUANTILE))
    pol = R.RoutingPolicy(threshold=0.0, disagreement_tol=tol, weak_elements=R.weak_elements_from(cal))
    model = C.fit(cal, C.ALPHA)
    rule = C.fit_decision(cal[R.labelable(cal, pol)])
    rows = []
    for r in test.itertuples():
        cand = R.Candidate(r.wbm_id, r.formula, r.each_pred, getattr(r, "pred_2", None), bool(r.structure_changed))
        d = R.route(cand, model, pol, rule)
        rows.append({"id": r.wbm_id, "label": d.label, "truly_stable": r.each_true <= M.ON_HULL_TOL, "each_true": r.each_true,
                     "reasons": "; ".join(d.reasons)})
    dec = pd.DataFrame(rows)
    rs = R.routing_summary(dec)
    costs = _costs()
    sweep = M.threshold_sweep(cal.each_pred.values, cal.each_true.values, [round(x, 3) for x in np.arange(-0.2, 0.2001, 0.01)])
    opt = M.cost_optimal_threshold(sweep, costs["cost_false_positive"], costs["cost_missed_stable"])
    dm = M.decision_metrics(test.each_pred.values, test.each_true.values, opt["threshold"])
    st = dec[dec.label == R.LIKELY_STABLE]
    un = dec[dec.label == R.LIKELY_UNSTABLE]
    prec_ci = M.boot_ci(st.truly_stable.astype(float), M.MEAN) if len(st) else (float("nan"),) * 3
    npv_ci = M.boot_ci((~un.truly_stable).astype(float), M.MEAN) if len(un) else (float("nan"),) * 3
    test = test.assign(bin=test.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True)))
    bins = pd.DataFrame([{"bin": b, "n": int((test.bin == b).sum()), "energy MAE": M.fmt_ci(M.boot_ci(test[test.bin == b].de_mev, M.MAE)),
                          "median |err|": M.fmt_ci(M.boot_ci(test[test.bin == b].de_mev, M.MEDIAN_ABS))} for b in compare.HULL_BINS_WBM])
    name = MODELS[primary[0]]["name"] + (f" (second engine for disagreement: {MODELS[second[0]]['name']})" if second else "")
    L = [f"# Final evaluation on the locked WBM test set — {name}", "",
         f"Opened once ({json.loads(FINAL_LOG.read_text())['started_at']}); every rule fitted on the calibration set only. "
         f"{len(test):,} usable test relaxations, {test.attrs['n_rejected']} rejected by the guard (counted). "
         f"Disagreement tolerance {tol * 1000:.0f} meV/atom (95th percentile on calibration)." if tol else "No second engine.", "",
         "## Routing (the complete system)", "",
         pd.DataFrame([rs]).T.reset_index().rename(columns={"index": "quantity", 0: "value"}).to_markdown(index=False, floatfmt=".3f"), "",
         f"'Likely stable' precision on test: {M.fmt_ci(prec_ci, '{:.2f}')} (target {C.TARGET_PRECISION:.0%}); 'likely unstable' "
         f"NPV: {M.fmt_ci(npv_ci, '{:.3f}')} (target {C.TARGET_NPV:.0%}).", "",
         f"## Plain threshold (cost-optimal on calibration: {opt['threshold'] * 1000:+.0f} meV/atom)", "",
         f"precision {M.fmt_ci(dm['precision_ci'], '{:.2f}')}, recall {M.fmt_ci(dm['recall_ci'], '{:.2f}')}, F1 "
         f"{M.fmt_ci(dm['f1_ci'], '{:.2f}')}, NPV {M.fmt_ci(dm['npv_ci'], '{:.3f}')}, DAF {M.fmt_ci(dm['daf_ci'], '{:.2f}')}.", "",
         "## Energy error by hull bin (test)", "", bins.to_markdown(index=False), ""]
    out = REPORTS_DIR / "final_test.md"
    out.write_text("\n".join(L) + "\n")
    return str(out.relative_to(ROOT))
