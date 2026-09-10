"""Unit tests for the substitution suite's diagnosis and aggregate statistics (no MACE, no network)."""

import math

import pandas as pd
import pytest

from harness.suites.substitution import _diagnose, group_stats


def test_diagnose_categories():
    assert _diagnose(pd.Series({"sub_match": True, "ctrl_match": True})) == "ok (both match)"
    assert _diagnose(pd.Series({"sub_match": False, "ctrl_match": True})) == "substitution relaxed elsewhere"
    # If the control itself leaves the MP structure, blame the model regardless of the substitution.
    assert _diagnose(pd.Series({"sub_match": True, "ctrl_match": False})) == "model moves MP structure (model off)"
    assert _diagnose(pd.Series({"sub_match": False, "ctrl_match": False})) == "model moves MP structure (model off)"
    assert _diagnose(pd.Series({"sub_match": None, "ctrl_match": True})) == "incomplete"


def test_group_stats_uses_absolute_errors_and_rates():
    df = pd.DataFrame({
        "sub_vol_pct": [2.0, -4.0], "ctrl_vol_pct": [1.0, -1.0],
        "sub_max_lat_pct": [0.5, 1.5], "ctrl_max_lat_pct": [None, 0.3],
        "sub_match": [True, False], "ctrl_match": [True, True],
        "sub_dE_mev": [10.0, -30.0], "ctrl_dE_mev": [-20.0, 40.0],
    })
    s = group_stats(df)
    assert s["n"] == 2
    assert s["sub_vol_mae_pct"] == pytest.approx(3.0)
    assert s["ctrl_vol_mae_pct"] == pytest.approx(1.0)
    assert s["ctrl_lat_mae_pct"] == pytest.approx(0.3)  # None ignored
    assert s["sub_match_rate"] == pytest.approx(0.5)
    assert s["ctrl_E_mae_mev"] == pytest.approx(30.0)


def test_group_stats_empty_is_nan_not_error():
    s = group_stats(pd.DataFrame(columns=["sub_vol_pct", "sub_match", "ctrl_match"]))
    assert s["n"] == 0 and math.isnan(s["sub_vol_mae_pct"]) and math.isnan(s["sub_match_rate"])
