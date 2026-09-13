"""The unseen-real-materials test set: the id decoding it rests on, and the frozen set's invariants.

The whole exclusion argument depends on one claim — that MP's new id format is the legacy integer in
base 26 — so that claim is tested both offline (known pairs, round trip) and, marked slow, against the
live Materials Project API.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from harness import unseen

KNOWN = {"mp-aaaaadyf": "mp-2657", "mp-aaaaaprp": "mp-10597", "mp-aaacfzaj": "mp-1018741",
         "mp-aaabxdqe": "mp-863672", "mp-aaaaatej": "mp-12957"}


@pytest.fixture(scope="module")
def frozen():
    if not unseen.UNSEEN_FILE.is_file():
        pytest.skip("data/unseen_test.json not built")
    return unseen.load()


def test_new_and_legacy_ids_are_the_same_integer():
    for new, legacy in KNOWN.items():
        assert unseen.legacy_material_id(new) == legacy
        assert unseen.new_material_id(legacy) == new


def test_id_decoding_round_trips():
    for n in (0, 1, 25, 26, 2657, 10597, 2725306):
        assert unseen.legacy_material_id(unseen.new_material_id(f"mp-{n}")) == f"mp-{n}"


def test_id_decoding_refuses_what_it_cannot_decode():
    for bad in ("mp-10597", "mp-aaaa1dyf", "mp-", "wbm-1-1"):
        with pytest.raises(ValueError):
            unseen.legacy_material_id(bad)


def test_frozen_set_is_hashed_and_self_consistent(frozen):
    ids = [p["target_id"] for p in frozen["pairs"]]
    assert len(ids) == frozen["n"] == len(set(ids))  # one pair per target, no duplicates
    assert frozen["locked"] is True
    unseen.load()  # re-reads and re-checks the sha256; raises if the list was edited


def test_no_target_could_be_in_the_training_snapshot(frozen):
    if not unseen.MP_SNAPSHOT.is_file():
        pytest.skip("MP snapshot not downloaded")
    seen, meta = unseen.trained_ids()
    leaked = [p["target_id"] for p in frozen["pairs"] if unseen.legacy_material_id(p["target_id"]) in seen]
    assert leaked == [], f"{len(leaked)} targets are in the MP 2023-01-10 snapshot and could be in MPtrj"
    assert meta["n_ids"] > 150_000


def test_no_target_is_reused_from_the_existing_pair_sets(frozen):
    used = unseen.already_used_ids()
    assert [p["target_id"] for p in frozen["pairs"] if p["target_id"] in used] == []


def test_every_pair_is_a_real_one_element_substitution(frozen):
    for p in frozen["pairs"]:
        assert p["parent_id"] != p["target_id"]
        src, dst = p["mapping"].split(":")
        assert src != dst
        assert p["n_atoms_target"] <= frozen["design"]["max_atoms"]
    families = pd.Series([p["family"] for p in frozen["pairs"]]).value_counts()
    assert families.max() <= frozen["design"]["max_per_prototype"]


def test_reweighting_to_its_own_mix_is_the_identity():
    """The prevalence correction must not move a set that is already at the target mix."""
    df = pd.DataFrame({
        "label": ["likely stable"] * 4 + ["likely unstable"] * 4 + ["needs DFT"] * 2,
        "truly_stable": [True, True, True, False, False, False, False, True, True, False],
        "bin": ["<0"] * 5 + ["0.025–0.1"] * 5,
    })
    own = df.bin.value_counts(normalize=True)
    rw = unseen.reweighted(df, own, n_boot=50)
    assert rw[unseen.STABLE][0] == pytest.approx(3 / 4)
    assert rw[unseen.UNSTABLE][0] == pytest.approx(3 / 4)
    assert rw[unseen.DFT_SHARE][0] == pytest.approx(0.2)


def test_reweighting_moves_the_rate_when_the_mix_changes():
    df = pd.DataFrame({"label": ["likely stable"] * 10,
                       "truly_stable": [True] * 5 + [False] * 5,
                       "bin": ["<0"] * 5 + ["0.1–0.3"] * 5})
    heavy_stable = pd.Series({"<0": 0.9, "0.1–0.3": 0.1})
    rw = unseen.reweighted(df, heavy_stable, n_boot=50)
    assert rw[unseen.STABLE][0] == pytest.approx(0.9)


@pytest.mark.slow
def test_id_decoding_against_the_live_materials_project():
    """Ask MP for the decoded legacy ids and require it to hand back the same new-format materials."""
    from harness import mp_data

    legacy = [unseen.legacy_material_id(n) for n in KNOWN]
    docs = mp_data._summary_search(material_ids=legacy)
    returned = {str(d["material_id"]) for d in docs}
    assert set(KNOWN) <= returned


@pytest.mark.slow
def test_frozen_targets_resolve_to_real_mp_materials(frozen):
    from harness import mp_data

    for p in frozen["pairs"][:5]:
        ref = mp_data.pbe_reference(p["target_id"])
        assert ref["formula"] == p["target_formula"]


def test_hull_exclusion_is_evaluation_only_and_off_by_default():
    """A real candidate is not in MP, so nothing is removed from its hull. The unseen run removes the
    target's own MP entry, which is what makes its numbers comparable with WBM's."""
    import inspect

    from harness import hull

    sig = inspect.signature(hull.e_above_hull_mode_a)
    assert sig.parameters["exclude_ids"].default == ()
    assert "EVALUATION" in hull.e_above_hull_mode_a.__doc__
    src = inspect.getsource(unseen.predict_job)
    assert "exclude_mp_ids" in src and 'job["target_id"]' in src


def test_the_run_never_hands_the_pipeline_a_dft_relaxed_cell():
    """predict_job may pass only the parent id and the substitution — never a structure."""
    import inspect

    src = inspect.getsource(unseen.predict_job)
    assert "P.predict(job[\"parent_id\"], job[\"mapping\"]" in src
    for forbidden in ("pbe_reference", "structure=", "relaxed"):
        assert forbidden not in src, f"predict_job must not touch {forbidden}"


def test_scoring_reads_the_truth_only_after_the_answer(frozen):
    """The DFT reference lives in the parent process, in `reference()`, not in the worker."""
    import inspect

    assert "pbe_reference" in inspect.getsource(unseen.reference)
    assert "pbe_reference" not in inspect.getsource(unseen.build_jobs)


def test_a_rate_with_no_errors_in_it_does_not_report_a_degenerate_interval():
    """22 correct calls out of 22 is not evidence that the rate is 1.00 with certainty.

    A bootstrap of an all-ones sample can only ever produce ones, so its 'pessimistic' bound is an
    artifact. Clopper-Pearson is what the unseen report uses for every rate, on both sides of the
    comparison.
    """
    import numpy as np

    from harness import metrics as M

    boot = M.boot_ci(np.ones(22), M.MEAN)
    cp = M.proportion_ci(22, 22)
    assert boot[1] == 1.0, "the bootstrap really is degenerate here"
    assert 0.80 < cp[1] < 0.90 and cp[2] == 1.0
    assert M.proportion_ci(0, 10)[1] == 0.0
    assert M.proportion_ci(36, 38)[1] < 0.947 < M.proportion_ci(36, 38)[2]


def test_the_report_compares_both_sides_with_the_same_estimator():
    import inspect

    src = inspect.getsource(unseen.report)
    assert "proportion_ci" in src and "locked_test_counts" in src
    # the headline rates come from Clopper-Pearson, not from a bootstrap of the call outcomes
    for line in src.splitlines():
        if line.strip().startswith(("prec = ", "npv = ", "wbm_prec", "wbm_npv")):
            assert "proportion_ci" in line, line
