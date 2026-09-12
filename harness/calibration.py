"""The frozen calibration bundle the product predicts with.

Everything the product needs to turn one engine number into a decision was fitted on the WBM
CALIBRATION set and reported in `reports/validation_report.md` §6c and `reports/final_test.md`:
the conformal model, the known-weak element list, the per-family certified decision thresholds, the
two-engine disagreement tolerance, and the observed hit rate per chemistry family × predicted hull
bin. None of it may be refitted per call, and none of it may be refitted at all: `build()` writes the
bundle once, from the cached calibration results, and `load()` is what the product uses from then on.

`fit()` is the single fitting function. `build()` calls it, and so does the one-time locked-test
evaluation (`harness.final_eval`), so the product and the evaluation that certified it cannot drift
apart. Re-running `python -m harness final-test evaluate` after this refactor reproduces
`reports/final_test.md` byte for byte, which is the check that they have not.

Two rule sets are stored, because the labelable population differs between them and each was
certified on its own:
  with_second_engine     candidates that survive the disagreement filter (the system measured on the
                         locked test set: precision 0.96, NPV 0.988)
  without_second_engine  no second engine run (the system in validation_report §6c: calibration
                         precision 0.971, NPV 0.985 — never measured on the locked test set)
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from harness import compare
from harness import confidence as C
from harness import routing as R
from harness import splits
from harness.config import DATA_DIR, MODELS, ROOT, settings_tag

BUNDLE_FILE = DATA_DIR / "calibration_bundle.json"
PRODUCTION_ENGINE = ("mace-mpa-0-medium", "cpu", "float32")
SECOND_ENGINE = ("mace-mp-0-medium", "cpu", "float64")
DISAGREEMENT_QUANTILE = 0.95
RELIABILITY_BOOT = 500  # as in reports/validation_report.md §6c


def harness_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001 — provenance must never break a prediction
        return "unknown"


# --- fitting (calibration set only) --------------------------------------------------------------

@dataclass
class FittedRules:
    """Everything fitted on the calibration set, for one system configuration."""

    conformal: C.ConformalModel
    weak_elements: frozenset
    disagreement_tol: float | None
    rule: C.DecisionRule
    policy: R.RoutingPolicy
    n_labelable: int


def fit(cal: pd.DataFrame, *, threshold: float = 0.0, use_disagreement: bool) -> FittedRules:
    """Fit every rule on calibration rows (formula, each_pred, each_true, structure_changed, pred_2).

    `use_disagreement` decides both the tolerance (95th percentile of |primary − second| on
    calibration: the 5 % most disputed calibration structures would be flagged) and which rows count
    as labelable, which is what the per-family thresholds are then certified on.

    There is deliberately no knob here for the product's "above the trusted range" refusal. That
    refusal is applied when a candidate is routed, not when the thresholds are certified, so the
    thresholds stay exactly the ones `reports/validation_report.md` and `reports/final_test.md`
    published. It cannot affect the certified 'likely stable' precision (no family certifies a stable
    threshold anywhere near +300 meV/atom); what it does to the 'likely unstable' NPV is measured and
    stated in docs/predict.md rather than re-certified here.
    """
    tol = None
    if use_disagreement:
        both = cal.dropna(subset=["pred_2"])
        tol = float(np.quantile((both.each_pred - both.pred_2).abs(), DISAGREEMENT_QUANTILE))
    policy = R.RoutingPolicy(threshold=threshold, disagreement_tol=tol,
                             weak_elements=R.weak_elements_from(cal))
    labelable = cal[R.labelable(cal, policy)]
    return FittedRules(conformal=C.fit(cal, C.ALPHA), weak_elements=policy.weak_elements,
                       disagreement_tol=tol, rule=C.fit_decision(labelable), policy=policy,
                       n_labelable=len(labelable))


def calibration_table(engine=PRODUCTION_ENGINE, ids: set | None = None,
                      init_cache: str = "calibration_init_structs.json") -> pd.DataFrame:
    """Usable WBM calibration rows for one engine, with the structure-changed signal attached."""
    from harness.report import _start_changed
    from harness.suites import ood

    key, device, dtype = engine
    tag = settings_tag(device, dtype, model=key)
    ids = ids if ids is not None else set(splits.calibration_ids())
    df = ood.table(tag)
    df = df[df.wbm_id.isin(ids)]
    n_all = len(df)
    df = df[df.rejection.isna()].copy()
    df["structure_changed"] = _start_changed(f"{tag}_{init_cache}", df, init_cache)
    df.attrs["n_rejected"] = n_all - len(df)
    return df


# --- the frozen bundle ---------------------------------------------------------------------------

def _rule_dict(f: FittedRules) -> dict:
    return {"target_precision": f.rule.target_precision, "target_npv": f.rule.target_npv,
            "certification_confidence": f.rule.conf, "n_labelable": f.n_labelable,
            "thresholds": f.rule.thresholds}


def build(engine=PRODUCTION_ENGINE, second=SECOND_ENGINE, path=BUNDLE_FILE, force: bool = False) -> dict:
    """Fit every rule on the calibration set once and freeze it to `path`."""
    if path.is_file() and not force:
        raise FileExistsError(f"{path} exists; the calibration bundle is fitted once (force=True to refit)")
    split = splits.load_split()
    cal_ids = set(split["calibration"]["ids"])
    cal = calibration_table(engine, cal_ids)
    second_pred = calibration_table(second, cal_ids).set_index("wbm_id").each_pred if second else None
    cal["pred_2"] = cal.wbm_id.map(second_pred) if second_pred is not None else np.nan
    fits = {"with_second_engine": fit(cal, use_disagreement=second is not None),
            "without_second_engine": fit(cal, use_disagreement=False)}
    rel = C.empirical_reliability(cal, 0.0, RELIABILITY_BOOT)
    reliability = [{"family": r.family, "predicted_bin": r["predicted bin"], "n": int(r.n), "call": r.call,
                    "hit_rate": float(r["call right"][0]), "ci95": [float(r["call right"][1]), float(r["call right"][2])]}
                   for _, r in rel.iterrows()]
    primary = fits["with_second_engine"]
    out = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness_commit": harness_commit(),
        "engine": _engine_meta(engine),
        "second_engine": _engine_meta(second) if second else None,
        "calibration_set": {
            "source": "WBM calibration split (data/wbm_split.json)", "split_created_at": split["created_at"],
            "n_ids": len(cal_ids), "n_usable": len(cal), "n_rejected_by_guard": int(cal.attrs["n_rejected"]),
            "n_with_second_engine": int(cal.pred_2.notna().sum()),
            "ids_sha256": hashlib.sha256(",".join(sorted(cal_ids)).encode()).hexdigest()},
        "conformal": json.loads(primary.conformal.to_json()),
        "weak_elements": sorted(primary.weak_elements),
        "disagreement_tol_ev": primary.disagreement_tol,
        "rules": {name: _rule_dict(f) for name, f in fits.items()},
        "reliability": reliability,
        "reliability_meaning": ("observed hit rate of the plain threshold-0 stable/unstable call on the WBM "
                               "calibration set, per chemistry family x predicted hull bin; "
                               "reports/validation_report.md §6c"),
    }
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    return out


def _engine_meta(engine) -> dict:
    key, device, dtype = engine
    m = MODELS[key]
    return {"key": key, "name": m["name"], "checkpoint": m["file"], "checkpoint_sha256": m["sha256"],
            "device": device, "dtype": dtype, "settings_tag": settings_tag(device, dtype, model=key)}


@dataclass
class Bundle:
    """The frozen calibration bundle, as the product reads it."""

    raw: dict

    @property
    def conformal(self) -> C.ConformalModel:
        return C.ConformalModel.from_json(json.dumps(self.raw["conformal"]))

    @property
    def weak_elements(self) -> frozenset:
        return frozenset(self.raw["weak_elements"])

    @property
    def disagreement_tol(self) -> float | None:
        return self.raw["disagreement_tol_ev"]

    def rule(self, with_second_engine: bool) -> C.DecisionRule:
        d = self.raw["rules"]["with_second_engine" if with_second_engine else "without_second_engine"]
        return C.DecisionRule(d["target_precision"], d["target_npv"], d["certification_confidence"], d["thresholds"])

    def rule_name(self, with_second_engine: bool) -> str:
        return "with_second_engine" if with_second_engine else "without_second_engine"

    def policy(self, with_second_engine: bool, max_trustworthy_hull: float | None) -> R.RoutingPolicy:
        return R.RoutingPolicy(threshold=0.0,
                               disagreement_tol=self.disagreement_tol if with_second_engine else None,
                               weak_elements=self.weak_elements,
                               max_trustworthy_hull=max_trustworthy_hull)

    def reliability(self, formula: str, predicted_hull: float) -> dict | None:
        """The calibration table row for this chemistry family and predicted hull bin (None if absent)."""
        fam, b = C.family(formula), compare.hull_bin(predicted_hull, below_zero_bin=True)
        for row in self.raw["reliability"]:
            if row["family"] == fam and row["predicted_bin"] == b:
                return {**row, "source": self.raw["reliability_meaning"]}
        return None


def load(path=BUNDLE_FILE) -> Bundle:
    if not path.is_file():
        raise FileNotFoundError(f"{path} missing — run `python -m harness calibrate` to freeze it")
    return Bundle(json.loads(path.read_text()))
