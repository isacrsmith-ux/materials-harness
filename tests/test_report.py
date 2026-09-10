"""Report verdict logic: explicit thresholds, borderline flag when the CI crosses one."""

import math

from harness.report import VERDICT_RULES, boot_ci, verdict, verdict_ci


def test_verdict_lower_is_better():
    good, caution = VERDICT_RULES["energy_mae_mev"]
    assert verdict("energy_mae_mev", good) == "trustworthy"
    assert verdict("energy_mae_mev", (good + caution) / 2) == "use with caution"
    assert verdict("energy_mae_mev", caution + 1) == "not trustworthy"


def test_verdict_higher_is_better():
    good, caution = VERDICT_RULES["stability_acc_0.1"]
    assert verdict("stability_acc_0.1", 1.0) == "trustworthy"
    assert verdict("stability_acc_0.1", (good + caution) / 2) == "use with caution"
    assert verdict("stability_acc_0.1", caution - 0.01) == "not trustworthy"


def test_verdict_missing_data():
    assert verdict("energy_mae_mev", float("nan")) == "no data"
    assert verdict("energy_mae_mev", None) == "no data"
    assert verdict_ci("energy_mae_mev", (float("nan"),) * 3) == "no data"


def test_verdict_ci_marks_borderline_when_interval_crosses_threshold():
    # point estimate just under the 30 meV/atom line, CI spanning both sides -> must say borderline
    v = verdict_ci("energy_mae_mev", (29.3, 18.4, 42.8))
    assert v.startswith("trustworthy (borderline")
    assert "use with caution" in v
    # CI entirely inside one band -> no qualifier
    assert verdict_ci("volume_mae_pct", (0.37, 0.28, 0.47)) == "trustworthy"


def test_boot_ci_contains_point_and_ignores_nan():
    point, lo, hi = boot_ci([1.0, -2.0, 3.0, float("nan"), None, -4.0])
    assert point == 2.5
    assert lo <= point <= hi
    assert all(math.isfinite(v) for v in (lo, hi))
