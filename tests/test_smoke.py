"""Smoke test (needs MP data — cached after the first run — and runs one MACE relaxation)."""

import pytest

from harness.suites import smoke

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def result():
    return smoke.run_smoke("cpu", "float64", record=False)


def test_target_is_stable_diamond_ge(result):
    assert result["target_e_above_hull"] == pytest.approx(0.0, abs=1e-6)


def test_reference_is_pbe_not_r2scan(result):
    # MACE-MP-0 is a PBE/PBE+U model; an r2SCAN reference would be apples-to-oranges.
    assert result["target_functional"] == "PBE"
    assert result["target_thermo_type"] == "GGA_GGA+U"


def test_relaxation_converged(result):
    assert result["converged"], f"not converged after {result['n_steps']} steps (fmax {result['fmax_final']:.4f})"


def test_relaxed_into_diamond(result):
    assert result["sim_spacegroup"] == smoke.DIAMOND_SG
    assert result["relaxed_into_target"]


def test_lattice_vs_materials_project(result):
    assert abs(result["a_pct_err_vs_mp"]) <= smoke.TOL_VS_MP_PCT


def test_lattice_vs_experiment(result):
    assert abs(result["a_pct_err_vs_exp"]) <= smoke.TOL_VS_EXP_PCT


def test_settings_recorded(result):
    # The engine comes from HARNESS_MODEL, so assert against the active registry entry rather than a
    # hardcoded name — hardcoding made this test pass only because another test happened to reset the
    # environment first.
    from harness import config

    s = result["settings"]
    assert s["model_name"] == config.MODEL["name"] and s["dtype"] == "float64" and s["device"] == "cpu"
    assert s["relax"]["fmax"] == 0.01 and s["relax"]["cell_filter"] == "FrechetCellFilter"
    assert s["relax"]["max_stress_gpa"] == 0.01
