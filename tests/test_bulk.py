"""Equation-of-state fitting and constant-volume stress criterion (offline)."""

import numpy as np
import pytest

from harness.engine import EV_PER_A3_TO_GPA, stress_residual
from harness.suites.bulk import VOLUME_FACTORS, fit_birch_murnaghan


def birch_murnaghan(v, e0, b0, bp, v0):
    eta = (v0 / v) ** (2 / 3)
    return e0 + 9 * v0 * b0 / 16 * ((eta - 1) ** 3 * bp + (eta - 1) ** 2 * (6 - 4 * eta))


def test_fit_recovers_known_bulk_modulus():
    v0, b0_gpa, bp = 20.0, 100.0, 4.5
    v = v0 * np.array(VOLUME_FACTORS)
    e = birch_murnaghan(v, -5.0, b0_gpa / EV_PER_A3_TO_GPA, bp, v0)
    fit = fit_birch_murnaghan(v, e)
    assert fit["b0_gpa"] == pytest.approx(b0_gpa, rel=1e-3)
    assert fit["bp"] == pytest.approx(bp, rel=1e-2)
    assert fit["v0"] == pytest.approx(v0, rel=1e-5)
    assert fit["rms_mev"] < 1e-3 and fit["v0_in_range"]


def test_volume_grid_is_nine_points_over_plus_minus_four_percent():
    assert len(VOLUME_FACTORS) == 9
    assert VOLUME_FACTORS[0] == pytest.approx(0.96) and VOLUME_FACTORS[-1] == pytest.approx(1.04)


def test_stress_residual_constant_volume_ignores_hydrostatic_part():
    hydro = np.array([0.01, 0.01, 0.01, 0.0, 0.0, 0.0])  # pure pressure
    assert stress_residual(hydro, constant_volume=False) == pytest.approx(0.01)
    assert stress_residual(hydro, constant_volume=True) == pytest.approx(0.0)
    shear = np.array([0.01, 0.01, 0.01, 0.002, 0.0, 0.0])
    assert stress_residual(shear, constant_volume=True) == pytest.approx(0.002)
