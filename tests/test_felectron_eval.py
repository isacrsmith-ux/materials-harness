"""The f-electron held-out sample is DRAWN but NOT OPENED, under a pre-registration that was
PUBLISHED before the draw. These tests pin all three of those properties."""

import hashlib
import json
import subprocess

import pytest

from harness import felectron_eval as FE, pnictide_eval as PE, round2, round4, splits

pytestmark = pytest.mark.skipif(not FE.SPLIT_FILE.exists(), reason="f-electron sample not drawn")


def test_the_sample_is_unopened_or_opened_exactly_once_and_recorded():
    """Was: "not opened". Opening was authorised on 2026-09-24; before it, nothing may exist, and after
    it the log must record everything item 4 of the pre-registration's chain of custody lists."""
    if not FE.is_opened():
        assert not FE.LOG_FILE.exists()
        return
    log = json.loads(FE.LOG_FILE.read_text())
    for field in ("opened_at", "authorised_by", "harness_commit", "sha256", "preregistration",
                  "active_bundle", "engines"):
        assert field in log, f"the opening log must record {field}"
    assert log["sha256"] == FE.load()["test"]["sha256"]
    assert log["preregistration"]["sha256"] == hashlib.sha256(FE.PREREG_FILE.read_bytes()).hexdigest()
    assert {e["model"] for e in log["engines"]} == {"mace-mpa-0-medium", "mace-mp-0-medium"}
    assert all(e["checkpoint_sha256"] for e in log["engines"])


def test_ids_are_locked_without_unlock():
    with pytest.raises(PermissionError):
        FE.test_ids()


def test_unlock_returns_hash_verified_ids():
    ids = FE.test_ids(unlock=True)
    d = FE.load()
    assert len(ids) == d["test"]["n"] == 4500
    assert hashlib.sha256(",".join(ids).encode()).hexdigest() == d["test"]["sha256"]


def test_drawn_once():
    with pytest.raises(splits.SplitExists):
        FE.make_split(None)


def test_no_id_has_ever_participated_in_anything():
    ids = set(FE.test_ids(unlock=True))
    assert not ids & FE._spent_ids()
    assert not ids & FE._protected_ids()
    assert not ids & round4.excluded_ids()
    assert not ids & PE.excluded_ids(), "overlaps the pnictide held-out sample"
    assert not ids & set(splits.calibration_ids())
    topup = set(json.loads((FE.DATA_DIR / "felectron_topup_ids.json").read_text())["ids"])
    assert not ids & topup, "overlaps the f-electron development top-up"


def test_every_id_is_f_electron_under_the_production_taxonomy():
    from harness.confidence import family
    from harness.suites import ood

    summary = ood.load_summary().set_index("material_id")
    ids = FE.test_ids(unlock=True)
    for wid in ids[:: max(1, len(ids) // 50)]:
        assert family(summary.loc[wid].formula) == "f-electron", wid


def test_the_preregistration_is_unmodified_since_the_draw():
    d = FE.load()
    assert hashlib.sha256(FE.PREREG_FILE.read_bytes()).hexdigest() == d["preregistration"]["sha256"]


def test_the_preregistration_was_published_before_the_draw():
    """The property the pnictide draw could not check automatically: a protocol that exists only
    locally when the sample is drawn is not a pre-registration."""
    rel = "data/felectron_evaluation_preregistration.json"
    sha = subprocess.run(["git", "log", "-1", "--format=%H", "--", rel],
                         capture_output=True, text=True).stdout.strip()
    if not sha:
        pytest.skip("not a git checkout")
    on_remote = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "origin/main"],
                               capture_output=True)
    if on_remote.returncode != 0:
        pytest.skip("origin/main not available in this checkout")
    published = subprocess.run(["git", "show", f"origin/main:{rel}"], capture_output=True).stdout
    assert hashlib.sha256(published).hexdigest() == FE.load()["preregistration"]["sha256"]


def test_the_thresholds_under_test_are_the_live_production_rule():
    d = FE.load()
    b = json.loads((FE.DATA_DIR / "calibration_bundle.json").read_text())
    for path in ("with_second_engine", "without_second_engine"):
        e = b["rules"][path]["thresholds"]["f-electron"]
        assert e["stable"] == d["thresholds_under_test"]["stable"] == -0.02
        assert e["unstable"] == d["thresholds_under_test"]["unstable"] == 0.01


def test_no_result_exists_for_any_drawn_id_until_opened():
    """Before opening, no drawn id may have a result. After opening this is vacuous: coverage is
    checked by the scorer's unusable / missing-second-engine triggers instead."""
    if FE.is_opened():
        return
    from harness import config
    from harness.suites import ood

    ids = set(FE.test_ids(unlock=True))
    for model, dtype in (("mace-mpa-0-medium", "float32"), ("mace-mp-0-medium", "float64")):
        tag = config.settings_tag("cpu", dtype, model=model)
        try:
            have = set(ood.table(tag).wbm_id)
        except Exception:
            continue
        assert not ids & have, f"{len(ids & have)} drawn ids already have {model} results"


def test_no_earlier_locked_half_was_consumed():
    assert FE.load()["consumes_no_existing_locked_half"] is True
    for fn in (lambda: splits.family_test_ids("oxide"), lambda: round2.test_ids("sulfide"),
               lambda: round2.test_ids3("chalcogenide"), lambda: round2.test_ids3("other")):
        with pytest.raises(PermissionError):
            fn()
