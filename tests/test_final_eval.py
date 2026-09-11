"""The locked test set is opened once."""

import pytest

from harness import final_eval


def test_start_refuses_a_second_opening(tmp_path, monkeypatch):
    monkeypatch.setattr(final_eval, "FINAL_LOG", tmp_path / "final.json")
    monkeypatch.setattr("harness.splits.load_split", lambda: {"test": {"sha256": "abc", "n": 4000}})
    assert not final_eval.started()
    log = final_eval.start(["esen-30m-oam", "mace-mpa-0-medium"])
    assert final_eval.started() and log["models"][0] == "esen-30m-oam"
    with pytest.raises(RuntimeError):
        final_eval.start(["x"])


def test_test_jobs_need_the_start_record(tmp_path, monkeypatch):
    monkeypatch.setattr(final_eval, "FINAL_LOG", tmp_path / "final.json")
    with pytest.raises(PermissionError):
        final_eval.build_test_jobs({"device": "cpu", "dtype": "float64"})
