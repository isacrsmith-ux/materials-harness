"""scripts/record_felectron_confirmation.py, exercised ONLY on a temporary copy of the bundle."""

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("rfc", ROOT / "scripts" / "record_felectron_confirmation.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

pytestmark = pytest.mark.skipif(not (ROOT / "reports" / "felectron_test.json").exists(), reason="not scored")


def test_it_records_status_and_provenance_changes_no_threshold_and_refuses_twice(tmp_path):
    real = ROOT / "data" / "calibration_bundle.json"
    sha_real = hashlib.sha256(real.read_bytes()).hexdigest()
    b = tmp_path / "bundle.json"
    shutil.copy(real, b)
    if json.loads((ROOT / "reports" / "felectron_test.json").read_text())["overall"] != "PASS":
        with pytest.raises(SystemExit, match="not all four"):
            S.main(bundle_path=b, backup=tmp_path / "pre.json")
        return
    S.main(bundle_path=b, backup=tmp_path / "pre.json")
    before, after = json.loads(real.read_text()), json.loads(b.read_text())
    for path in ("with_second_engine", "without_second_engine"):
        e0, e1 = before["rules"][path]["thresholds"]["f-electron"], after["rules"][path]["thresholds"]["f-electron"]
        assert (e1["stable"], e1["unstable"], e1["n"]) == (e0["stable"], e0["unstable"], e0["n"]) == (-0.02, 0.01, e0["n"])
        assert e1["status"] == "PREREGISTERED HELD-OUT CONFIRMED"
    assert [p["family"] for p in after["promotions"]] == ["pnictide"], "a confirmation is not a promotion"
    assert [c["family"] for c in after["confirmations"]] == ["f-electron"]
    assert after["created_at"] == before["created_at"]
    with pytest.raises(SystemExit, match="ABORT|already"):
        S.main(bundle_path=b, backup=tmp_path / "pre.json")
    assert hashlib.sha256(real.read_bytes()).hexdigest() == sha_real, "the real bundle must be untouched"


def test_it_will_not_run_without_the_explicit_flag():
    src = (ROOT / "scripts" / "record_felectron_confirmation.py").read_text()
    assert '"--i-have-an-explicit-decision" not in sys.argv' in src
