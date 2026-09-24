"""scripts/felectron_eval.py: the one-time open / enqueue / score of the f-electron held-out sample.

These pin what the script must refuse and what the scorer must compute, on synthetic rows: no test
here reads a held-out outcome.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from harness import confidence as C, felectron_eval as FE

SCRIPT = Path(__file__).parents[1] / "scripts" / "felectron_eval.py"
spec = importlib.util.spec_from_file_location("felectron_eval_script", SCRIPT)
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

pytestmark = pytest.mark.skipif(not FE.SPLIT_FILE.exists(), reason="f-electron sample not drawn")


def _rows(pred_true: list[tuple[float, float]]) -> pd.DataFrame:
    d = pd.DataFrame(pred_true, columns=["each_pred", "each_true"])
    return d.assign(stable=d.each_true <= 0.0)


def test_the_hashes_are_the_full_committed_values():
    assert S.PREREG_SHA256 == hashlib.sha256(FE.PREREG_FILE.read_bytes()).hexdigest()
    assert S.PREREG_SHA256.startswith("d3995f66") and len(S.PREREG_SHA256) == 64
    assert S.SAMPLE_SHA256 == FE.load()["test"]["sha256"] and S.SAMPLE_SHA256.startswith("43a675a7")


def test_a_hash_mismatch_aborts(monkeypatch, tmp_path):
    fake = tmp_path / "prereg.json"
    fake.write_bytes(FE.PREREG_FILE.read_bytes() + b" ")
    monkeypatch.setattr(FE, "PREREG_FILE", fake)
    with pytest.raises(SystemExit, match="ABORT"):
        S.prereg()


def test_open_refuses_to_reopen(monkeypatch, tmp_path):
    log = tmp_path / "log.json"
    log.write_text("{}")
    monkeypatch.setattr(FE, "LOG_FILE", log)
    with pytest.raises(SystemExit, match="already been opened"):
        S.open_sample()


def test_score_refuses_to_rescore(monkeypatch, tmp_path):
    log, rep = tmp_path / "log.json", tmp_path / "felectron_test.json"
    log.write_text("{}")
    rep.write_text("{}")
    monkeypatch.setattr(FE, "LOG_FILE", log)
    monkeypatch.setattr(S, "REPORT_JSON", rep)
    with pytest.raises(SystemExit, match="scored once"):
        S.score()


def test_the_scorer_uses_exactly_the_preregistered_thresholds_and_confidence():
    Pr = S.prereg()
    assert S.thresholds(Pr) == (-0.02, 0.01)
    assert S.PRIMARY_CONF == 0.9875 == Pr["statistics"]["primary_confidence"]
    assert S.SECONDARY_CONF == Pr["statistics"]["secondary_confidence"]
    assert {h: (v["target"]) for h, v in Pr["hypotheses"].items()} == {"EA1": 0.9, "EA2": 0.95, "EB1": 0.9, "EB2": 0.95}
    # -20 meV stable, +10 meV unstable, the band between is DFT: exactly one row per side here
    d = _rows([(-0.05, -0.01), (0.0, 0.05), (0.2, 0.3)])
    st = S.score_side(d, -0.02, 0.01, "stable", 0.9)
    un = S.score_side(d, -0.02, 0.01, "unstable", 0.95)
    assert (st["calls"], st["correct"]) == (1, 1)
    assert (un["calls"], un["correct"]) == (1, 1)


def test_the_verdict_is_read_from_the_primary_bound():
    n, k = 500, 470                                     # point 0.94 > 0.90
    d = _rows([(-0.1, -0.1)] * k + [(-0.1, 0.1)] * (n - k))
    r = S.score_side(d, -0.02, 0.01, "stable", 0.9)
    assert r["cp_lower_primary"] == pytest.approx(C.cp_lower(k, n, 0.9875))
    assert r["verdict"] == ("PASS" if r["cp_lower_primary"] >= 0.9 else "FAIL")
    d = _rows([(-0.1, -0.1)] * 23 + [(-0.1, 0.1)] * 2)  # point 0.92 > 0.90, bound far below
    r = S.score_side(d, -0.02, 0.01, "stable", 0.9)
    assert r["verdict"] == "FAIL" and "near-miss" in r["note"]


def _good(n=1000):
    return _rows([(-0.1, -0.1)] * n + [(0.3, 0.3)] * n)


def test_every_inconclusive_trigger_fires():
    Pr = S.prereg()
    A = _good()
    H, trig = S.hypotheses(A, A, 2000, 0, 0, Pr)
    assert S.overall(H) == "PASS" and trig == []

    few = _rows([(-0.1, -0.1)] * 19 + [(0.3, 0.3)] * 1000)
    H, _ = S.hypotheses(few, few, 2000, 0, 0, Pr)
    assert H["EA1"]["verdict"] == "INCONCLUSIVE" and "too_few_calls" in H["EA1"]["note"]
    assert S.overall(H) == "INCONCLUSIVE"

    H, trig = S.hypotheses(A, A, 2000, 41, 0, Pr)       # 41/2000 > 2%
    assert all(h["verdict"] == "INCONCLUSIVE" for h in H.values()) and "unusable_rows" in trig[0]
    H, _ = S.hypotheses(A, A, 2000, 40, 0, Pr)          # exactly 2% does not fire
    assert S.overall(H) == "PASS"

    H, trig = S.hypotheses(A, A, 2000, 0, 41, Pr)       # 41/2000 labelable A rows > 2%
    assert [H[h]["verdict"] for h in ("EA1", "EA2", "EB1", "EB2")] == ["PASS", "PASS", "INCONCLUSIVE", "INCONCLUSIVE"]
    assert "missing_second_engine" in trig[0]

    empty = A.iloc[:0]
    H, trig = S.hypotheses(A, empty, 2000, 0, 0, Pr)
    assert H["EB1"]["verdict"] == H["EB2"]["verdict"] == "INCONCLUSIVE" and "no_labelable_rows: path B" in trig


def test_a_fail_outranks_an_inconclusive():
    assert S.overall({"a": {"verdict": "FAIL"}, "b": {"verdict": "INCONCLUSIVE"}}) == "FAIL"


def test_no_code_path_can_select_a_threshold():
    """No identifier, attribute or import anywhere in the script names a selection routine."""
    import ast

    tree = ast.parse(SCRIPT.read_text())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    for banned in ("certify", "diagnose", "best_bound", "grid", "fit", "arange", "linspace", "numpy"):
        assert not {x for x in names if banned in x.lower()}, banned


def test_the_report_quotes_the_outcome_branch_verbatim():
    Pr = S.prereg()
    A = _good()
    H, trig = S.hypotheses(A, A, 2000, 0, 0, Pr)
    p = {"opened_at": "t0", "authorised_by": S.AUTHORISED_BY, "harness_commit_at_open": "abc", "evaluated_at": "t1",
         "sample_sha256": S.SAMPLE_SHA256, "preregistration_sha256": S.PREREG_SHA256, "active_bundle_sha256": "x",
         "thresholds": {"stable": -0.02, "unstable": 0.01}, "primary_confidence": 0.9875,
         "population": {"drawn": 2000, "usable": 2000, "unusable": 0, "guard_rejected_engine1": 0,
                        "guard_rejected_engine2": 0, "labelable_A": 2000, "labelable_B": 2000,
                        "removed_by_disagreement": 0, "missing_second_engine": 0, "labelable_C": 2000},
         "inconclusive_triggers_fired": trig, "hypotheses": H, "overall": S.overall(H),
         "expected": {k: Pr["error_budget"]["primary"][k] for k in H},
         "path_C_descriptive": {"labelable": 2000, "stable": H["EA1"], "unstable": H["EA2"]}}
    md = S.render(p, Pr)
    assert Pr["outcome_rule"]["all_four_pass"] in md
    assert "Isac Smith, 2026-09-24" in md and "not the held-out data being better" in md
