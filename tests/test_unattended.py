"""Unattended-run helpers: power parsing, modes, stop time, notifications, launchd plist (offline)."""

from datetime import datetime

from harness import notify, orchestrator, power, schedule
from harness.config import UNATTENDED_DEFAULTS


def test_parse_pmset():
    assert power.parse_pmset("Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t100%; charged") == "ac"
    assert power.parse_pmset("Now drawing from 'Battery Power'\n -InternalBattery-0\t87%; discharging") == "battery"
    assert power.parse_pmset("Now drawing from 'UPS Power'") == "battery"
    assert power.parse_pmset("") == "unknown"


def test_power_override_only_via_environment(tmp_path, monkeypatch):
    f = tmp_path / "power"
    f.write_text("battery")
    monkeypatch.delenv(power.OVERRIDE_ENV, raising=False)
    assert power.override_path() is None
    monkeypatch.setenv(power.OVERRIDE_ENV, str(f))
    assert power.power_source() == "battery"
    f.write_text("ac")
    assert power.power_source() == "ac"


def test_layout_modes(monkeypatch):
    monkeypatch.setattr(orchestrator, "core_counts", lambda: {"performance": 10, "efficiency": 4, "physical": 14})
    cfg = dict(UNATTENDED_DEFAULTS)
    assert orchestrator.layout("polite", {"workers": 10, "threads_per_worker": 1}, cfg) == (8, 1)
    assert orchestrator.layout("full", {"workers": 10, "threads_per_worker": 1}, cfg) == (10, 1)
    assert orchestrator.layout("polite", {"workers": 5, "threads_per_worker": 2}, cfg) == (4, 2)
    assert orchestrator.layout("full", {"workers": 5, "threads_per_worker": 2}, cfg) == (5, 2)
    assert orchestrator.layout("polite", {"workers": 1, "threads_per_worker": 10}, cfg) == (1, 8)


def test_parse_stop_at_rolls_over_midnight():
    now = datetime(2026, 9, 10, 23, 0)
    assert orchestrator.parse_stop_at("07:00", now) == datetime(2026, 9, 11, 7, 0)
    assert orchestrator.parse_stop_at("23:30", now) == datetime(2026, 9, 10, 23, 30)
    assert orchestrator.parse_stop_at(None, now) is None


def test_notify_silenced(monkeypatch):
    calls = []
    monkeypatch.setenv("HARNESS_NOTIFY", "0")
    monkeypatch.setattr(notify.subprocess, "run", lambda *a, **k: calls.append(a))
    notify.notify("title", "message")
    assert calls == []


def test_osascript_quotes_are_escaped(monkeypatch):
    seen = {}
    monkeypatch.setattr(notify.subprocess, "run", lambda args, **k: seen.setdefault("args", args))
    notify.macos('say "hi"', 'path\\x "quoted"')
    script = seen["args"][2]
    assert seen["args"][:2] == ["osascript", "-e"]
    assert '\\"hi\\"' in script and '\\\\x' in script


def test_ntfy_off_without_topic(monkeypatch):
    monkeypatch.setattr(notify, "ntfy_settings", lambda: (None, "https://ntfy.sh"))
    assert notify.ntfy("t", "m") is False


def test_launchd_plist():
    cfg = dict(UNATTENDED_DEFAULTS, schedule={"start": "23:00", "stop": "07:00", "mode": "full"})
    p = schedule.build_plist(cfg)
    assert p["StartCalendarInterval"] == {"Hour": 23, "Minute": 0}
    args = p["ProgramArguments"]
    assert args[1].endswith("run_unattended.sh") and args[2:] == ["--foreground", "full", "--stop-at", "07:00"]
    assert p["RunAtLoad"] is False
