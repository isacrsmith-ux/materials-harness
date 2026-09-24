"""Invariants the 2026-09-24 campaign must leave true, whatever state it ends in."""

import hashlib
import json

import pytest

from harness import external_oqmd as X, felectron_eval as FE
from harness.config import DATA_DIR

BUNDLE_SHA256 = "419c11514d6a54854584258375eadab6b2be0c449e955125799fc51df2310288"


def test_the_production_bundle_is_byte_for_byte_unchanged():
    """No outcome of this campaign changes data/calibration_bundle.json; a confirmation, if any, is a
    separate production commit on an explicit decision."""
    assert hashlib.sha256((DATA_DIR / "calibration_bundle.json").read_bytes()).hexdigest() == BUNDLE_SHA256


def test_the_felectron_opening_is_authorised_and_recorded_once():
    if not FE.is_opened():
        pytest.skip("not opened yet")
    log = json.loads(FE.LOG_FILE.read_text())
    assert log["authorised_by"] == "Isac Smith, 2026-09-24"


@pytest.mark.skipif(not X.SPLIT_FILE.exists(), reason="OQMD half not locked yet")
def test_the_oqmd_heldout_half_is_locked_unopened_and_registered():
    with pytest.raises(PermissionError):
        X.heldout_ids()
    assert not X.is_opened()
    split = X.load_split()
    held, dev = set(split["heldout"]["ids"]), set(split["development"]["ids"])
    assert not held & dev
    assert X._sha(held) == split["heldout"]["sha256"]
    reg = json.loads((DATA_DIR / "locked_sets_registry.json").read_text())
    row = [s for s in reg["sets"] if s["name"].startswith("OQMD external held-out")]
    assert len(row) == 1 and row[0]["status"] == "LOCKED, UNOPENED" and row[0]["hash_verifies"]


@pytest.mark.skipif(not (DATA_DIR / "oqmd_dev_plan.json").exists(), reason="no OQMD plan yet")
def test_no_heldout_id_is_in_the_development_plan_or_the_pilot():
    held = X.excluded_heldout_ids()
    plan = json.loads((DATA_DIR / "oqmd_dev_plan.json").read_text())["ids"]["ids"]
    pilot = json.loads((DATA_DIR / "oqmd_pilot_ids.json").read_text())["ids"]
    assert not held & set(plan) and not held & set(pilot)
    assert set(pilot) <= set(plan)
