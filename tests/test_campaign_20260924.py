"""scripts/campaign_20260924.py: the resumable campaign driver. Nothing here launches a runner."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "campaign_20260924.py"
spec = importlib.util.spec_from_file_location("campaign_driver", SCRIPT)
D = importlib.util.module_from_spec(spec)
sys.modules["campaign_driver"] = D
spec.loader.exec_module(D)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(D, "runner_alive", lambda: None)
    return tmp_path / "state.json"


def test_run_engine_refuses_when_other_tags_are_pending(monkeypatch):
    monkeypatch.setattr(D, "runner_alive", lambda: None)
    monkeypatch.setattr(D, "pending_tags", lambda: {"c2480e74": 10, "207ccc81": 5})
    monkeypatch.setattr(D, "sh", lambda *a, **k: pytest.fail("must not launch"))
    with pytest.raises(D.Refuse, match="REFUSED"):
        D.run_engine(D.PROD)


def test_run_engine_waits_while_a_runner_holds_a_lock(monkeypatch):
    monkeypatch.setattr(D, "runner_alive", lambda: 4242)
    monkeypatch.setattr(D, "sh", lambda *a, **k: pytest.fail("must not launch"))
    with pytest.raises(D.Wait, match="4242"):
        D.run_engine(D.SECOND)


def test_run_engine_with_nothing_pending_is_done_without_launching(monkeypatch):
    monkeypatch.setattr(D, "runner_alive", lambda: None)
    monkeypatch.setattr(D, "pending_tags", lambda: {})
    monkeypatch.setattr(D, "sh", lambda *a, **k: pytest.fail("must not launch"))
    assert D.run_engine(D.PROD).startswith("ok")


def test_the_launch_carries_the_engine_and_no_stop_at(monkeypatch):
    calls = []
    left = iter([{"207ccc81": 3}, {}])
    monkeypatch.setattr(D, "runner_alive", lambda: None)
    monkeypatch.setattr(D, "pending_tags", lambda: next(left))
    monkeypatch.setattr(D, "on_ac", lambda: True)
    monkeypatch.setattr(D, "sh", lambda args, model=None, check=True: calls.append((args, model)) or
                        type("R", (), {"returncode": 0})())
    D.run_engine(D.SECOND)
    (args, model), = calls
    assert model == "mace-mp-0-medium" and "--stop-at" not in args and "--foreground" in args


def test_advance_is_idempotent_and_skips_dependents_of_a_failure(state):
    ran = []

    def ok():
        ran.append("a")
        return "ok"

    def boom():
        raise RuntimeError("x")

    steps = [D.Step("a", "1", ok), D.Step("b", "1", boom), D.Step("c", "1", ok, ["b"]), D.Step("d", "2", ok)]
    for _ in range(D.MAX_ATTEMPTS):
        D.advance(steps)
    st = D.load_state()
    assert st["steps"]["b"]["outcome"].startswith("FAILED")
    assert st["steps"]["c"]["outcome"].startswith("skipped")
    assert st["steps"]["d"]["outcome"] == "ok" and st["finished_at"]
    assert ran == ["a", "a"], "a finished step is never re-run; d runs once"
    assert D.advance(steps) == "campaign finished; nothing to do"


def test_a_wait_stops_the_invocation_without_failing(state):
    def wait():
        raise D.Wait("battery")

    steps = [D.Step("a", "1", wait), D.Step("b", "1", lambda: pytest.fail("ran past a Wait"))]
    assert "waiting at a" in D.advance(steps)
    assert "finished_at" not in D.load_state()["steps"]["a"]


def test_a_missing_script_waits_until_the_deadline(monkeypatch):
    with pytest.raises(D.Wait, match="not written yet"):
        D.script("no_such_script_20260924.py")
    monkeypatch.setattr(D, "BUILD_DEADLINE", "2000-01-01T00:00:00+00:00")
    assert D.script("no_such_script_20260924.py").startswith("skipped")


def test_advance_exits_while_a_runner_is_alive(state, monkeypatch):
    monkeypatch.setattr(D, "runner_alive", lambda: 7)
    assert "runner is alive" in D.advance([D.Step("a", "1", lambda: pytest.fail("ran"))])


def test_the_campaign_runs_production_before_second_and_phase_1_first():
    names = [s.name for s in D.STEPS]
    assert names.index("fe_run_production") < names.index("fe_run_second") < names.index("oqmd_download")
    assert names[-1] == "finish"
