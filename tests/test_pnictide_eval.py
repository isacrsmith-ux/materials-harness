"""The pnictide held-out sample is DRAWN but NOT OPENED. These tests pin that distinction.

The sample's value is entirely in its not having influenced anything. What matters is therefore what
it must refuse to do, and the tests run against the real committed artefact because that is the thing
the evaluation will depend on.
"""

import hashlib
import json

import pytest

from harness import pnictide_eval, round2, round4, splits

pytestmark = pytest.mark.skipif(not pnictide_eval.SPLIT_FILE.exists(),
                                reason="pnictide evaluation sample not drawn")


def test_the_sample_is_not_opened():
    """The single most important property. An opening log means it has been spent."""
    assert not pnictide_eval.is_opened()
    assert not pnictide_eval.LOG_FILE.exists()


def test_ids_are_locked_without_unlock():
    with pytest.raises(PermissionError):
        pnictide_eval.test_ids()


def test_unlock_returns_the_hash_verified_ids():
    """unlock=True is what the one-time evaluation will use; it must verify the recorded hash."""
    ids = pnictide_eval.test_ids(unlock=True)
    d = pnictide_eval.load()
    assert len(ids) == d["test"]["n"] == 3500
    assert hashlib.sha256(",".join(ids).encode()).hexdigest() == d["test"]["sha256"]


def test_the_sample_is_drawn_once():
    from harness import splits as S

    with pytest.raises(S.SplitExists):
        pnictide_eval.make_split(None)


def test_no_id_has_ever_participated_in_anything():
    ids = set(pnictide_eval.test_ids(unlock=True))
    assert not ids & pnictide_eval._spent_ids(), "an id was already spent by an earlier split"
    assert not ids & round4._locked_test_ids(), "an id is a locked test id of another half"
    assert not ids & round4.excluded_ids(), "an id was in the round-4 development draw"
    assert not ids & set(splits.calibration_ids()), "an id was in the original calibration set"


def test_every_id_is_a_pnictide_under_the_production_taxonomy():
    from harness.confidence import family
    from harness.suites import ood

    summary = ood.load_summary().set_index("material_id")
    ids = pnictide_eval.test_ids(unlock=True)
    sample = ids[:: max(1, len(ids) // 50)]
    for wid in sample:
        assert family(summary.loc[wid].formula) == "pnictide", wid


def test_the_preregistration_is_unmodified_since_the_draw():
    """If the protocol changed after the sample was drawn, the evaluation is worthless."""
    d = pnictide_eval.load()
    on_disk = hashlib.sha256(pnictide_eval.PREREG_FILE.read_bytes()).hexdigest()
    assert on_disk == d["preregistration"]["sha256"]


def test_the_thresholds_under_test_are_the_preregistered_ones():
    d = pnictide_eval.load()
    P = json.loads(pnictide_eval.PREREG_FILE.read_text())
    assert d["thresholds_under_test"]["stable"] == P["thresholds_under_test"]["stable_ev_per_atom"] == -0.02
    assert d["thresholds_under_test"]["unstable"] == P["thresholds_under_test"]["unstable_ev_per_atom"] == 0.0


def test_no_result_for_any_drawn_id_exists_in_the_store():
    """The operational meaning of 'unopened': nothing has been computed for these structures."""
    from harness import config
    from harness.suites import ood

    ids = set(pnictide_eval.test_ids(unlock=True))
    for model, dtype in (("mace-mpa-0-medium", "float32"), ("mace-mp-0-medium", "float64")):
        tag = config.settings_tag("cpu", dtype, model=model)
        try:
            have = set(ood.table(tag).wbm_id)
        except Exception:
            continue
        assert not ids & have, f"{len(ids & have)} drawn ids already have {model} results"


def test_production_is_untouched_by_the_draw():
    from harness import confidence as C

    b = json.loads((pnictide_eval.DATA_DIR / "calibration_bundle.json").read_text())
    assert b["created_at"] == "2026-09-12T20:21:45+00:00"
    assert "fluoride" not in C.FAMILIES
    # the very defect the evaluation exists to test a fix for is still present
    assert b["rules"]["with_second_engine"]["thresholds"]["pnictide"] == {
        "stable": None, "unstable": None, "n": 202}
