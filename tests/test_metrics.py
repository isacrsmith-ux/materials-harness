"""Stratified metrics: bootstrap intervals, decision metrics, threshold sweep, cost optimum, pessimistic verdicts."""

import math

import numpy as np
import pandas as pd
import pytest

from harness import metrics as m


def test_boot_ci_contains_point_and_ignores_nan():
    p, lo, hi = m.boot_ci([1.0, -2.0, 3.0, float("nan"), None, -4.0], m.MAE, n_boot=500)
    assert p == 2.5 and lo <= p <= hi


def test_confusion_metrics_by_hand():
    # pred:  S S S U U U ; true: S U S S U U  -> tp 2, fp 1, fn 1, tn 2
    c = m.confusion([1, 1, 1, 0, 0, 0], [1, 0, 1, 1, 0, 0])
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (2, 1, 1, 2)
    assert c["precision"] == pytest.approx(2 / 3) and c["recall"] == pytest.approx(2 / 3)
    assert c["npv"] == pytest.approx(2 / 3) and c["prevalence"] == pytest.approx(0.5)
    assert c["daf"] == pytest.approx((2 / 3) / 0.5)


def test_decision_metrics_threshold_and_interval():
    true = np.array([-0.05, 0.0, 0.02, 0.2, 0.3, 0.5])
    pred = np.array([-0.04, 0.01, -0.01, 0.1, 0.35, 0.4])
    d0 = m.decision_metrics(pred, true, threshold=0.0, n_boot=200)
    assert (d0["tp"], d0["fp"], d0["fn"]) == (1, 1, 1)
    d1 = m.decision_metrics(pred, true, threshold=0.05, n_boot=200)
    assert d1["tp"] == 2 and d1["fp"] == 1
    lo, hi = d1["precision_ci"][1], d1["precision_ci"][2]
    assert lo <= d1["precision"] <= hi


def test_threshold_sweep_and_cost_optimum():
    true = np.array([-0.1, -0.02, 0.05, 0.15, 0.4])
    pred = np.array([-0.12, 0.03, -0.01, 0.2, 0.3])
    sw = m.threshold_sweep(pred, true, [-0.05, 0.0, 0.05])
    assert list(sw.called_stable) == [1, 2, 3]
    # missing a stable material is 10x worse than a wasted test -> the loosest threshold wins
    assert m.cost_optimal_threshold(sw, cost_fp=1, cost_fn=10)["threshold"] == 0.05
    # a wasted test is 10x worse -> the strictest wins
    assert m.cost_optimal_threshold(sw, cost_fp=10, cost_fn=1)["threshold"] == -0.05


def test_verdict_uses_pessimistic_bound():
    # error: point 25 (good) but upper bound 45 -> judged on 45
    assert m.verdict_ci((25.0, 15.0, 45.0), good=30, caution=60, lower_is_better=True) == "use with caution"
    # score: point 0.9 but lower bound 0.7
    assert m.verdict_ci((0.9, 0.7, 0.95), good=0.85, caution=0.6, lower_is_better=False) == "use with caution"
    assert m.verdict_ci((float("nan"),) * 3, 1, 2, True) == "no data"


def test_per_element_min_count():
    df = pd.DataFrame({"f": ["FeO"] * 25 + ["NiS"] * 3, "e": [10.0] * 25 + [100.0] * 3})
    t, below = m.per_element(df, "f", "e", min_count=20, n_boot=100)
    assert set(t.element) == {"Fe", "O"} and below == 2  # Ni and S counted, not shown
    assert t.iloc[0]["MAE"][0] == pytest.approx(10.0)


def test_by_group_counts():
    df = pd.DataFrame({"bin": ["a", "a", "b"], "err": [1.0, -3.0, float("nan")]})
    t = m.by_group(df, "bin", "err", order=["a", "b"], n_boot=100)
    assert list(t.n) == [2, 0] and t.iloc[0]["MAE"][0] == 2.0 and math.isnan(t.iloc[1]["MAE"][0])
