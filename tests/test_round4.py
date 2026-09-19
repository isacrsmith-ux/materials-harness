"""Round 4 is a DEVELOPMENT-ONLY draw. The properties that matter are what it must not do: reuse a
spent id, touch a locked half, share a composition with one, or hand out a held-out half it never
reserved.

These run against the real committed split, because that is the artifact the results depend on.
"""

import hashlib
import json

import pytest

from harness import round2, round4, splits
from harness.confidence import family

pytestmark = pytest.mark.skipif(not round4.SPLIT_FILE.exists(), reason="round-4 split not made")


def test_no_test_half_is_reserved():
    """The whole point: round 4 is development only. Reserving a half is a pre-registration decision."""
    for fam in round4.groups():
        assert round4.load()["groups"][fam]["test"] is None


def test_test_ids_refuses_rather_than_keyerrors():
    for fam in round4.groups():
        with pytest.raises(PermissionError):
            round4.test_ids(fam)


def test_calibration_ids_verify_their_hash():
    for fam in round4.groups():
        ids = round4.calibration_ids(fam)
        g = round4.load()["groups"][fam]["calibration"]
        assert hashlib.sha256(",".join(ids).encode()).hexdigest() == g["sha256"]
        assert len(ids) == g["n"]


def test_no_id_is_shared_with_any_earlier_split():
    spent = round4._spent_ids()
    for fam in round4.groups():
        assert not set(round4.calibration_ids(fam)) & spent, fam


def test_no_id_is_a_locked_test_id():
    locked = round4._locked_test_ids()
    assert len(locked) == 11874, "the six locked halves total 11,874 ids"
    for fam in round4.groups():
        assert not set(round4.calibration_ids(fam)) & locked, fam


def test_families_are_disjoint_from_each_other():
    seen: set[str] = set()
    for fam in round4.groups():
        ids = set(round4.calibration_ids(fam))
        assert not ids & seen, fam
        seen |= ids
    assert len(seen) == round4.load()["n_unique_calibration_ids"]


def test_split_is_made_once():
    from harness.suites import ood

    with pytest.raises(splits.SplitExists):
        round4.make_split(None, path=round4.SPLIT_FILE)


def test_the_draw_is_the_families_it_claims():
    """A round-4 'pnictide' row must be what production calls a pnictide, not a round-2 overlay."""
    import pandas as pd
    from harness.suites import ood

    summary = ood.load_summary().set_index("material_id")
    for fam in round4.groups():
        ids = round4.calibration_ids(fam)
        sample = ids[:: max(1, len(ids) // 40)]
        for wid in sample:
            assert family(summary.loc[wid].formula) == fam, f"{wid} is not {fam}"


def test_production_is_untouched_by_round_4():
    from harness import confidence as C

    b = json.loads((round4.DATA_DIR / "calibration_bundle.json").read_text())
    assert b["created_at"] == "2026-09-12T20:21:45+00:00"
    assert "fluoride" not in C.FAMILIES


# --- round 4b: the with_second_engine path ---------------------------------------------------------

def test_a_missing_second_engine_prediction_passes_the_disagreement_term():
    """The behaviour every round-4b number depends on, pinned so it cannot change silently.

    routing.labelable's disagreement term is `~((each_pred - pred_2).abs() > tol)`. With pred_2 NaN
    the comparison is False, so the row stays labelable — it passes the check by never being tested.
    That mirrors harness.predict, which warns that "the certified thresholds in use assume the
    disagreement check ran" and labels the candidate anyway. If this ever flips to excluding such
    rows, round 4b's populations change and the report must be regenerated.
    """
    import pandas as pd

    from harness import calibration as CAL, routing as R

    b = CAL.load()
    pol = b.policy(with_second_engine=True, max_trustworthy_hull=None)
    d = pd.DataFrame({
        "formula": ["NaCl", "NaCl", "NaCl"],
        "each_pred": [0.0, 0.0, 0.0],
        "pred_2": [0.0, float("nan"), 9.0],   # agrees / unknown / wildly disagrees
        "structure_changed": [False, False, False],
    })
    ok = R.labelable(d, pol)
    assert bool(ok.iloc[0]) is True, "agreeing pair must stay labelable"
    assert bool(ok.iloc[1]) is True, "missing pred_2 passes untested — production's real behaviour"
    assert bool(ok.iloc[2]) is False, "a pair past the tolerance must be refused a label"


def test_the_two_engines_have_distinct_settings_tags():
    """If the tags ever collided, one engine's results would overwrite the other's in the store."""
    from harness import config
    from harness.calibration import PRODUCTION_ENGINE, SECOND_ENGINE

    tags = {config.settings_tag(dev, dt, model=key) for key, dev, dt in (PRODUCTION_ENGINE, SECOND_ENGINE)}
    assert len(tags) == 2
