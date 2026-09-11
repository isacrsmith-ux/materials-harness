"""Screening subset (fixed, stratified, calibration-only) and candidate-table formatting (offline)."""

import json

import pandas as pd

from harness import candidates, screening


def _fake_inputs(monkeypatch):
    bins = [0.0, 0.05, 0.2, 0.5]
    pairs = [{"pair_id": f"P{i}", "target_e_above_hull": bins[i % 4]} for i in range(40)]
    monkeypatch.setattr("harness.pairgen.load_pairs", lambda: pairs)
    cal = [f"wbm-{i}" for i in range(100)]
    hulls = {w: [-0.05, 0.01, 0.05, 0.2, 0.5][i % 5] for i, w in enumerate(cal)}
    split = {"calibration": {"ids": cal, "n": 100, "by_bin": {"<0": 20, "0–0.025": 20, "0.025–0.1": 20, "0.1–0.3": 20, ">0.3": 20}},
             "test": {"ids": ["wbm-test-1"]}}
    monkeypatch.setattr("harness.splits.load_split", lambda: split)
    summary = pd.DataFrame({"material_id": cal, "e_above_hull_mp2020_corrected_ppd_mp": [hulls[w] for w in cal]})
    monkeypatch.setattr("harness.suites.ood.load_summary", lambda: summary)
    monkeypatch.setattr(screening, "PAIRS_PER_BIN", 5)
    monkeypatch.setattr(screening, "N_WBM", 25)


def test_subset_is_stratified_calibration_only_and_fixed(monkeypatch, tmp_path):
    _fake_inputs(monkeypatch)
    s = screening.make_subset(tmp_path / "s.json")
    assert len(s["pair_ids"]) == 20  # 5 per bin x 4 bins
    assert len(s["wbm_ids"]) == 25 and "wbm-test-1" not in s["wbm_ids"]
    again = screening.make_subset(tmp_path / "s.json")  # read back, never regenerated
    assert again == json.loads((tmp_path / "s.json").read_text()) == s


def test_candidate_settings_text():
    b = {"device_benchmark": {"per_structure": {"a": {}, "b": {}}, "settings": {
        "cpu/float32": {"failures": 0, "mean_relax_speedup": 1.8, "all_agree": True, "first_error": None},
        "mps/float32": {"failures": 2, "mean_relax_speedup": float("nan"), "all_agree": False, "first_error": "TypeError: x"}}}}
    t = candidates._settings_text(b)
    assert "cpu/float32: 1.80× vs reference, agrees" in t and "mps/float32: cannot run (TypeError: x)" in t
    assert candidates._settings_text(None) == "not benchmarked"
