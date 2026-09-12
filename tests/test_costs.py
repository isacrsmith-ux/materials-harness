"""Cost-driven operating point: implied precision floor, plateau, sensitivity table."""

import numpy as np
import pytest

from harness import costs
from harness import metrics as m


def test_implied_precision_floor_is_the_break_even_probability():
    # equal costs -> call stable above 50 % confidence
    assert costs.implied_precision_floor(1, 1) == pytest.approx(0.5)
    # a wasted test 9x worse than a missed material -> demand 90 %
    assert costs.implied_precision_floor(9, 1) == pytest.approx(0.9)
    # a missed material 4x worse -> be permissive
    assert costs.implied_precision_floor(1, 4) == pytest.approx(0.2)


def test_precision_target_and_cost_ratio_are_inverses():
    # the routing layer's 90 % target implies a wasted test is 9x worse than a miss
    assert costs.implied_cost_ratio(0.9) == pytest.approx(1 / 9)
    assert costs.implied_precision_floor(1.0, costs.implied_cost_ratio(0.9)) == pytest.approx(0.9)


def _sweep():
    true = np.array([-0.1, -0.02, 0.01, 0.05, 0.15, 0.4, 0.02, -0.03])
    pred = np.array([-0.12, 0.03, -0.01, 0.2, 0.3, 0.35, -0.02, 0.04])
    return m.threshold_sweep(pred, true, [round(x, 3) for x in np.arange(-0.1, 0.101, 0.01)])


def test_plateau_brackets_the_optimum():
    sw = _sweep()
    p = costs.plateau(sw, 1.0, 1.0)
    assert p["low"] <= p["best"] <= p["high"]
    assert p["min_cost"] == pytest.approx(m.cost_optimal_threshold(sw, 1.0, 1.0)["expected_cost"])
    assert p["n_thresholds"] >= 1


def test_plateau_widens_as_tolerance_grows():
    sw = _sweep()
    tight, loose = costs.plateau(sw, 1.0, 1.0, frac=0.0), costs.plateau(sw, 1.0, 1.0, frac=0.5)
    assert loose["n_thresholds"] >= tight["n_thresholds"]
    assert loose["low"] <= tight["low"] and loose["high"] >= tight["high"]


def test_ratio_table_threshold_rises_with_the_cost_of_a_miss():
    t = costs.ratio_table(_sweep(), [0.25, 1, 10])
    thr = list(t["optimal threshold (meV/atom)"])
    assert thr == sorted(thr), "a costlier miss must never tighten the threshold"
    floors = list(t["implied precision floor"])
    assert floors == sorted(floors, reverse=True), "a costlier miss must lower the precision demanded"
