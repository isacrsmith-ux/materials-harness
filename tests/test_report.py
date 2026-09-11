"""Report verdicts (pessimistic bound), likely-cause rule order, stratified tables."""

import math

import pandas as pd

from harness.report import VERDICT_RULES, boot_ci, likely_cause, stratified_table, verdict, verdict_ci


def test_verdict_lower_is_better():
    good, caution, _ = VERDICT_RULES["energy_mae_mev"]
    assert verdict("energy_mae_mev", good) == "trustworthy"
    assert verdict("energy_mae_mev", (good + caution) / 2) == "use with caution"
    assert verdict("energy_mae_mev", caution + 1) == "not trustworthy"


def test_verdict_higher_is_better():
    good, caution, _ = VERDICT_RULES["precision"]
    assert verdict("precision", 1.0) == "trustworthy"
    assert verdict("precision", (good + caution) / 2) == "use with caution"
    assert verdict("precision", caution - 0.01) == "not trustworthy"


def test_verdict_ci_judges_the_pessimistic_bound():
    # point 29.3 is 'trustworthy' but the upper bound 42.8 is not -> the verdict follows the bound
    assert verdict_ci("energy_mae_mev", (29.3, 18.4, 42.8)) == "use with caution"
    assert verdict_ci("volume_mae_pct", (0.37, 0.28, 0.47)) == "trustworthy"
    assert verdict_ci("precision", (0.85, 0.62, 0.9)) == "use with caution"
    assert verdict_ci("energy_mae_mev", (float("nan"),) * 3) == "no data"


def test_boot_ci_contains_point_and_ignores_nan():
    point, lo, hi = boot_ci([1.0, -2.0, 3.0, float("nan"), None, -4.0])
    assert point == 2.5 and lo <= point <= hi and all(math.isfinite(v) for v in (lo, hi))


def test_likely_cause_checks_hull_and_structure_first():
    c = likely_cause("Zn(BrN)2", 1.2, "relaxed into a different structure", magnetic_pbe=True, source="MP")
    parts = c.split("; ")
    assert parts[0].startswith("far above the hull") and parts[1] == "relaxed into a different structure"
    assert likely_cause("MgO", 0.0, "same structure", False, "MP") == "no flag — generic model error"


def test_stratified_table_counts_rejected_and_splits():
    df = pd.DataFrame({"bin": ["≤0.025"] * 4, "e": [10.0, -20.0, None, 5.0], "o": ["same", "same", None, "diff"],
                       "rej": [None, None, "not converged", None]})
    t = stratified_table(df, ["≤0.025"], "e", None, "o", rej_col="rej")
    assert list(t.o) == ["diff", "same"] and list(t.n) == [1, 2]
    t2 = stratified_table(df, ["≤0.025"], "e", rej_col="rej")
    assert t2.iloc[0]["n"] == 3 and t2.iloc[0]["rejected (guard)"] == 1
