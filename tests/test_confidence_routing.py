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
    r = np.arange(1, 20)  # n = 19, alpha 0.1 -> ranks ceil(20*0.95)=19 and floor(20*0.05)=1
    assert C.conformal_bounds(r, 0.1) == (1.0, 19.0)
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
    cv = C.crossval_coverage(df, 0.1, k=5)
    assert cv[cv.family == "all"].coverage.iloc[0] == pytest.approx(0.9, abs=0.05)


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


def test_dft_stub_records_requests(tmp_path):
    q = R.FileQueueDFT(tmp_path / "req.jsonl")
    c = R.Candidate("x", "MgO", 0.01)
    t = q.submit(c, R.route(c, _model(), R.RoutingPolicy()))
    assert t == "dft-x" and q.result(t) is None and "queued" in q.status(t)
    assert (tmp_path / "req.jsonl").read_text().count("\n") == 1
