"""Offline tests for the OOD (WBM) scoring math."""

import numpy as np
import pandas as pd
import pytest

from harness.suites import ood


def test_predict_e_hull_shifts_by_energy_error():
    assert ood.predict_e_hull(0.05, -5.02, -5.00) == pytest.approx(0.03)
    assert ood.predict_e_hull(0.0, -4.90, -5.00) == pytest.approx(0.10)


def _summary(n=50):
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "material_id": [f"wbm-1-{i}" for i in range(n)],
        "unique_prototype": [i % 5 != 0 for i in range(n)],
        "uncorrected_energy_from_cse": rng.normal(-20, 1, n), "n_sites": 4.0,
        "e_above_hull_mp2020_corrected_ppd_mp": rng.uniform(0, 0.3, n),
        "e_form_per_atom_mp2020_corrected": rng.normal(-1, 0.3, n), "e_correction_per_atom_mp2020": 0.0,
    })
    df.loc[3, "n_sites"] = np.nan  # rows with missing required data are never sampled
    return df


def test_sample_ids_deterministic_and_filtered():
    df = _summary()
    a, b = ood.sample_ids(df, n=10, seed=1), ood.sample_ids(df, n=10, seed=1)
    assert a == b and len(set(a)) == 10
    assert a != ood.sample_ids(df, n=10, seed=2)
    allowed = set(df[(df.unique_prototype) & df.n_sites.notna()].material_id)
    assert set(a) <= allowed
    assert len(ood.sample_ids(df, n=1000, seed=1)) == len(allowed)


def test_id_regex_on_jsonl_line():
    line = '{"material_id": "wbm-3-1234", "formula_from_cse": "Fe2 O3", "initial_structure": {"@module": "x"}}'
    assert ood.ID_RE.search(line[:200]).group(1) == "wbm-3-1234"


def test_score_excludes_rejected_and_classifies():
    df = pd.DataFrame({
        "de_mev": [10.0, -30.0, 5000.0], "each_true": [0.0, 0.2, 0.0], "each_pred": [0.01, 0.17, 5.0],
        "rejection": [None, None, "not converged"]})
    s = ood.score(df)
    assert s["n"] == 2 and s["n_rejected"] == 1
    assert s["energy_mae_mev"] == pytest.approx(20.0)
    assert s["e_hull_mae_mev"] == pytest.approx(20.0)
    t0 = s["thr0.0"]  # true stable: row0 ; predicted stable: none
    assert (t0["tp"], t0["fn"], t0["tn"]) == (0, 1, 1)
    t1 = s["thr0.1"]  # true stable (<=0.1): row0 ; predicted: row0
    assert t1["precision"] == 1.0 and t1["recall"] == 1.0
