"""The flight-data pooling guard and the print conventions of scripts/aerospace_ingest.py (no data, no pypdf)."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

sys.modules.setdefault("pypdf", types.SimpleNamespace(PdfReader=None))  # the script's PDF reader is not under test
_spec = importlib.util.spec_from_file_location("aerospace_ingest", Path(__file__).resolve().parents[1] / "scripts" / "aerospace_ingest.py")
ing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ing)


def _r(kind="mass_change", q="dm_mg", unit="mg", ub=False):
    return {"quantity_kind": kind, "quantity": q, "unit": unit, "is_upper_bound": ub}


def test_pooling_refuses_different_quantities_and_upper_bounds():
    ing.assert_poolable([_r(), _r()])
    with pytest.raises(ValueError):
        ing.assert_poolable([_r(), _r(kind="oxide_thickness", q="cu2o_thickness_nm", unit="nm")])
    with pytest.raises(ValueError):
        ing.assert_poolable([_r(), _r(q="dm_per_area_mg_cm2")])
    with pytest.raises(ValueError):
        ing.assert_poolable([_r(ub=True), _r(ub=False)])


def test_print_conventions():
    assert ing.parse_v2("5.55 x 10^21") == pytest.approx(5.55e21)
    assert ing.parse_v2("5.55 x 10^09") is None  # leading-zero exponent is not interpreted
    assert ing.parse_v2("-") == 0.0 and ing.parse_v2("+0.13") == 0.13
    assert ing.parse_v2("400-500") is None and ing.parse_v2("No change") is None
