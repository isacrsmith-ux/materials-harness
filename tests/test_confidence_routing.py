"""Conformal intervals (finite-sample ranks, orientation, fallback), chemistry families, routing labels."""

import math

import numpy as np
import pandas as pd
import pytest

from harness import confidence as C
from harness import routing as R


def test_families():
    assert C.family("CeO2") == "f-electron" and C.family("Cu3Au") == "intermetallic"
    assert C.family("MgAl2O4") == "oxide" and C.family("NaCl") == "halide"
    assert C.family("ZnS") == "chalcogenide" and C.family("GaN") == "pnictide" and C.family("SiC") == "other"


def test_conformal_bounds_ranks():
    r = np.arange(1, 20)  # n = 19
    assert C.conformal_bounds(r, 0.1, two_sided=True) == (1.0, 19.0)  # ranks ceil(20*0.95)=19, floor(20*0.05)=1
    assert C.conformal_bounds(r, 0.1) == (2.0, 18.0)                   # one-sided: ranks ceil(20*0.9)=18, floor(20*0.1)=2
    lo, hi = C.conformal_bounds([0.0, 1.0], 0.1)  # too small for the level -> unbounded
    assert lo == -math.inf and hi == math.inf


def test_interval_orientation_and_fallback():
    rng = np.random.default_rng(0)
    n = 400
    true = rng.uniform(-0.1, 0.5, n)
    pred = true - 0.03 + rng.normal(0, 0.02, n)  # model over-stabilises by 30 meV/atom
    df = pd.DataFrame({"formula": ["MgO"] * n, "each_pred": pred, "each_true": true})
    m = C.fit(df, alpha=0.1, min_group=40)
    iv = m.interval("MgO", 0.0)
    assert iv["lo"] < 0.03 < iv["hi"]  # true = pred - r and r ~ -0.03: the interval is shifted UP
    assert iv["group_level"] in ("family × predicted bin", "family")
    assert m.interval("CeO2", 0.0)["group_level"] == "all"  # unseen family falls back to the global entry
    cv = C.crossval_coverage(df, 0.1, k=5).set_index("family")
    assert cv.loc["all", "upper bound holds"] == pytest.approx(0.9, abs=0.05)
    assert cv.loc["all", "interval holds"] == pytest.approx(0.8, abs=0.06)


def _model():
    return C.ConformalModel(0.1, 40, {"*|*": [-0.02, 0.02, 1000]})  # interval = pred ± 0.02


def test_routing_labels_and_reasons():
    pol = R.RoutingPolicy(threshold=0.0, disagreement_tol=0.05, weak_elements=frozenset({"Pu"}))
    assert R.route(R.Candidate("a", "MgO", -0.05), _model(), pol).label == R.LIKELY_STABLE
    assert R.route(R.Candidate("b", "MgO", 0.10), _model(), pol).label == R.LIKELY_UNSTABLE
    d = R.route(R.Candidate("c", "MgO", 0.01), _model(), pol)
    assert d.label == R.SEND_TO_DFT and d.reasons[0].startswith("low confidence")
    d = R.route(R.Candidate("d", "PuO2", 0.30), _model(), pol)
    assert d.label == R.SEND_TO_DFT and "known-weak chemistry (Pu)" in d.reasons
    d = R.route(R.Candidate("e", "MgO", -0.05, pred_e_hull_2=0.02, structure_changed=True), _model(), pol)
    assert d.label == R.SEND_TO_DFT and len(d.reasons) == 2


def test_weak_elements_flag_bad_and_rare_only():
    # O appears in every compound: its attributed MAE (10*60 + 150*20)/80 = 45 meV/atom is not demonstrably bad
    df = pd.DataFrame({"formula": ["FeO"] * 60 + ["NiO"] * 20 + ["PuO2"] * 3,
                       "de_mev": [10.0] * 60 + [150.0] * 20 + [5.0] * 3})
    weak = R.weak_elements_from(df, err_col="de_mev", min_count=20, caution_mev=60.0, n_boot=200)
    assert "Ni" in weak   # demonstrably bad: lower bound 150 > 60
    assert "Pu" in weak   # too few compounds to judge
    assert "Fe" not in weak and "O" not in weak  # O inherits a mixed error but is not demonstrably bad


def test_crossval_routing_summary():
    rng = np.random.default_rng(1)
    n = 600
    true = rng.uniform(-0.1, 0.4, n)
    df = pd.DataFrame({"formula": ["MgO"] * n, "each_true": true, "each_pred": true + rng.normal(0, 0.01, n)})
    dec = R.crossval_routing(df, alpha=0.1, k=5)
    s = R.routing_summary(dec)
    assert s["n"] == n and s["likely stable"] + s["likely unstable"] + s["send to DFT"] == n
    assert s["precision of 'likely stable'"] > 0.9 and s["NPV of 'likely unstable'"] > 0.9


def test_clopper_pearson_and_certify():
    assert C.cp_lower(0, 10, 0.95) == 0.0
    assert 0.605 < C.cp_lower(9, 10, 0.95) < 0.607  # one-sided 95 % Clopper-Pearson for 9/10: 0.6058
    rng = np.random.default_rng(3)
    pred = rng.uniform(-0.2, 0.4, 3000)
    truly_stable = rng.uniform(0, 1, 3000) < np.clip(0.5 - 3 * pred, 0, 0.99)  # lower prediction -> likelier stable
    t = C.certify(pred, truly_stable, 0.9, "stable")
    sel = pred <= t + 1e-6
    assert t is not None and truly_stable[sel].mean() >= 0.9  # the certified rule meets its target in-sample
    assert C.certify(pred, truly_stable, 0.999, "stable") is None  # an unreachable target is never certified


def test_certified_routing_uses_family_thresholds():
    rule = C.DecisionRule(thresholds={"oxide": {"stable": -0.05, "unstable": 0.10, "n": 500}})
    pol = R.RoutingPolicy()
    assert R.route(R.Candidate("a", "MgO", -0.06), _model(), pol, rule).label == R.LIKELY_STABLE
    assert R.route(R.Candidate("b", "MgO", 0.20), _model(), pol, rule).label == R.LIKELY_UNSTABLE
    assert R.route(R.Candidate("c", "MgO", 0.00), _model(), pol, rule).label == R.SEND_TO_DFT
    d = R.route(R.Candidate("d", "Cu3Au", -0.30), _model(), pol, rule)  # no certified thresholds for this family
    assert d.label == R.SEND_TO_DFT and "no certified thresholds" in d.reasons[0]


def test_dft_stub_records_requests(tmp_path):
    q = R.FileQueueDFT(tmp_path / "req.jsonl")
    c = R.Candidate("x", "MgO", 0.01)
    t = q.submit(c, R.route(c, _model(), R.RoutingPolicy()))
    assert t == "dft-x" and q.result(t) is None and "queued" in q.status(t)
    assert (tmp_path / "req.jsonl").read_text().count("\n") == 1
