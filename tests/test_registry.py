"""Model registry: the baseline keeps its round-1 settings tag; every model gets its own tag."""

import importlib

import pytest

from harness import config


def test_baseline_tag_is_unchanged():
    # every result of rounds 1 and 2 so far lives under this tag; changing it would silently orphan them
    assert config.settings_tag("cpu", "float64", model=config.BASELINE_MODEL) == "207ccc81"


def test_every_model_has_a_distinct_tag():
    tags = {config.settings_tag("cpu", "float64", model=k) for k in config.MODELS}
    assert len(tags) == len(config.MODELS)
    assert config.settings_tag("cpu", "float32", model="mace-mpa-0-medium") != config.settings_tag(
        "cpu", "float64", model="mace-mpa-0-medium")


def test_registry_entries_are_complete():
    for key, m in config.MODELS.items():
        for field in ("name", "loader", "file", "url", "license", "training_data", "compliant"):
            assert field in m, (key, field)
        assert m["loader"] in ("mace", "fairchem", "sevenn")


def test_active_model_from_environment(monkeypatch):
    monkeypatch.setenv("HARNESS_MODEL", "mace-mpa-0-medium")
    cfg = importlib.reload(config)
    try:
        assert cfg.ACTIVE_MODEL == "mace-mpa-0-medium" and cfg.MODEL["name"] == "MACE-MPA-0 medium"
        assert cfg.compute_config_path().name == "compute-mace-mpa-0-medium.json"
    finally:
        monkeypatch.delenv("HARNESS_MODEL")
        importlib.reload(config)
    assert config.ACTIVE_MODEL == config.BASELINE_MODEL


def test_unknown_model_is_refused(monkeypatch):
    monkeypatch.setenv("HARNESS_MODEL", "no-such-model")
    with pytest.raises(KeyError):
        importlib.reload(config)
    monkeypatch.delenv("HARNESS_MODEL")
    importlib.reload(config)
