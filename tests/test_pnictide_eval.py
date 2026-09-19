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


def test_the_sample_was_opened_exactly_once_and_is_recorded():
    """Was: "not opened". The sample has now been opened once, on 2026-09-19, and the property that
    matters is that it can never be opened again and that the opening is fully recorded."""
    import json as _json

    assert pnictide_eval.is_opened(), "the opening log is the record that the sample was spent"
    log = _json.loads(pnictide_eval.LOG_FILE.read_text())
    for field in ("opened_at", "harness_commit", "sha256", "preregistration", "active_bundle", "engines"):
        assert field in log, f"the opening log must record {field}"
    assert log["sha256"] == pnictide_eval.load()["test"]["sha256"]
    assert log["preregistration"]["sha256"] == hashlib.sha256(
        pnictide_eval.PREREG_FILE.read_bytes()).hexdigest(), "the protocol changed after opening"
    assert {e["model"] for e in log["engines"]} == {"mace-mpa-0-medium", "mace-mp-0-medium"}


def test_the_sample_cannot_be_reopened():
    """scripts/pnictide_eval.py open refuses while the log exists. Checked at the source of truth."""
    src = (pnictide_eval.DATA_DIR.parent / "scripts" / "pnictide_eval.py").read_text()
    assert "if PE.LOG_FILE.is_file():" in src and "has already been opened" in src


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


def test_every_drawn_id_has_a_result_under_both_engines():
    """Was the 'unopened' check. Now that the sample is spent, the property worth pinning is that the
    evaluation actually covered it: every drawn id has a result under BOTH engines, so no hypothesis
    was scored on a silently truncated population."""
    from harness import config
    from harness.suites import ood

    ids = set(pnictide_eval.test_ids(unlock=True))
    for model, dtype, floor in (("mace-mpa-0-medium", "float32", 1.0), ("mace-mp-0-medium", "float64", 0.99)):
        tag = config.settings_tag("cpu", dtype, model=model)
        have = set(ood.table(tag).wbm_id)
        covered = len(ids & have) / len(ids)
        assert covered >= floor, f"{model}: only {covered:.4f} of drawn ids have a result"


def _unused_no_result_check():
    """Retained for provenance: this is what the test above asserted while the sample was unopened."""
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


def test_the_promoted_pnictide_rule_is_the_preregistered_one():
    """Was: "production untouched by the draw", which asserted the none/none defect was still present.

    The rule has since been promoted on the strength of the held-out result, so what must now be
    pinned is that production carries EXACTLY the pre-registered thresholds - not a refitted, retuned
    or re-optimised variant - in BOTH rule sets.
    """
    from harness import confidence as C

    b = json.loads((pnictide_eval.DATA_DIR / "calibration_bundle.json").read_text())
    P = json.loads(pnictide_eval.PREREG_FILE.read_text())
    want_s = P["thresholds_under_test"]["stable_ev_per_atom"]
    want_u = P["thresholds_under_test"]["unstable_ev_per_atom"]
    assert (want_s, want_u) == (-0.02, 0.0)
    for path in ("with_second_engine", "without_second_engine"):
        e = b["rules"][path]["thresholds"]["pnictide"]
        assert e["stable"] == want_s, f"{path}: stable is not the pre-registered value"
        assert e["unstable"] == want_u, f"{path}: unstable is not the pre-registered value"
        assert e["status"] == "PREREGISTERED HELD-OUT CONFIRMED"
    # the fit date is provenance and must not be rewritten by a promotion
    assert b["created_at"] == "2026-09-12T20:21:45+00:00"
    assert "fluoride" not in C.FAMILIES


def test_the_promotion_records_full_provenance():
    b = json.loads((pnictide_eval.DATA_DIR / "calibration_bundle.json").read_text())
    proms = [p for p in b.get("promotions", []) if p["family"] == "pnictide"]
    assert len(proms) == 1, "exactly one pnictide promotion"
    p = proms[0]
    assert p["status"] == "PREREGISTERED HELD-OUT CONFIRMED"
    assert p["preregistration"]["sha256"] == hashlib.sha256(
        pnictide_eval.PREREG_FILE.read_bytes()).hexdigest()
    assert p["held_out_sample"]["sha256"] == pnictide_eval.load()["test"]["sha256"]
    for h in ("PA1", "PA2", "PB1", "PB2"):
        rec = p["evaluation"]["hypotheses"][h]
        assert rec["verdict"] == "PASS"
        assert rec["cp_lower_primary"] >= rec["target"], h
    assert p["evaluation"]["statistics"]["primary_confidence"] == 1 - 0.05 / 4
    assert "NO grid correction" in p["evaluation"]["statistics"]["multiplicity"]
    # the honest limit must travel with the rule
    assert "does NOT establish" in p["evaluation"]["power_limit"]


def test_no_other_family_was_changed_by_the_promotion():
    """The pre-promotion bundle is kept on disk precisely so this can be asserted, not argued."""
    pre = json.loads((pnictide_eval.DATA_DIR / "calibration_bundle_pre_pnictide.json").read_text())
    now = json.loads((pnictide_eval.DATA_DIR / "calibration_bundle.json").read_text())
    for path in ("with_second_engine", "without_second_engine"):
        a = {k: v for k, v in pre["rules"][path]["thresholds"].items() if k != "pnictide"}
        b = {k: v for k, v in now["rules"][path]["thresholds"].items() if k != "pnictide"}
        assert a == b, f"a non-pnictide threshold changed in {path}"
        for key in ("target_precision", "target_npv", "certification_confidence", "n_labelable"):
            assert pre["rules"][path][key] == now["rules"][path][key]
    for key in ("created_at", "engine", "second_engine", "calibration_set", "conformal",
                "weak_elements", "disagreement_tol_ev", "reliability"):
        assert pre[key] == now[key], f"top-level {key} changed"
