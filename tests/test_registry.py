"""Model registry: the baseline keeps its round-1 settings tag; every model gets its own tag."""

import importlib
import os

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


# `importlib.reload(config)` rebinds ACTIVE_MODEL for the WHOLE session, so these two tests have to put
# back the caller's own HARNESS_MODEL rather than deleting it. Deleting it silently switched every later
# test in the process to the baseline engine, which made `pytest` pass and `pytest -m slow` fail.
@pytest.fixture
def restore_active_model():
    original = os.environ.get("HARNESS_MODEL")
    yield
    if original is None:
        os.environ.pop("HARNESS_MODEL", None)
    else:
        os.environ["HARNESS_MODEL"] = original
    importlib.reload(config)


def test_active_model_from_environment(monkeypatch, restore_active_model):
    monkeypatch.setenv("HARNESS_MODEL", "mace-mpa-0-medium")
    cfg = importlib.reload(config)
    assert cfg.ACTIVE_MODEL == "mace-mpa-0-medium" and cfg.MODEL["name"] == "MACE-MPA-0 medium"
    assert cfg.compute_config_path().name == "compute-mace-mpa-0-medium.json"


def test_unknown_model_is_refused(monkeypatch, restore_active_model):
    monkeypatch.setenv("HARNESS_MODEL", "no-such-model")
    with pytest.raises(KeyError):
        importlib.reload(config)


def test_default_model_is_the_baseline(monkeypatch, restore_active_model):
    monkeypatch.delenv("HARNESS_MODEL", raising=False)
    cfg = importlib.reload(config)
    assert cfg.ACTIVE_MODEL == cfg.BASELINE_MODEL
