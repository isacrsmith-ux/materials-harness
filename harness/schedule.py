"""Optional nightly launchd user agent. Generated here; installed only by the user (scripts/).

The agent runs `run_unattended.sh --foreground <mode> --stop-at <stop>` at the configured start
time. The runner drains gracefully at the stop time (finishes running jobs, then exits). If the
Mac is asleep at the start time, launchd starts the job at the next wake.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

from harness import ROOT
from harness.config import CONFIG_DIR, LOG_DIR, load_unattended_config

LABEL = "com.materials-harness.nightly"
PLIST_PATH = CONFIG_DIR / "launchd" / f"{LABEL}.plist"
AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _hm(text: str) -> tuple[int, int]:
    h, m = (int(x) for x in text.split(":"))
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"bad time {text!r}")
    return h, m


def build_plist(cfg: dict | None = None) -> dict:
    s = (cfg or load_unattended_config())["schedule"]
    h, m = _hm(s["start"])
    _hm(s["stop"])
    return {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(ROOT / "run_unattended.sh"), "--foreground", s.get("mode", "full"),
                             "--stop-at", s["stop"]],
        "WorkingDirectory": str(ROOT),
        "StartCalendarInterval": {"Hour": h, "Minute": m},
        "RunAtLoad": False,
        "ProcessType": "Standard",
        "StandardOutPath": str(LOG_DIR / "launchd.out.log"),
        "StandardErrorPath": str(LOG_DIR / "launchd.err.log"),
        "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
    }


def write_plist(cfg: dict | None = None) -> Path:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_bytes(plistlib.dumps(build_plist(cfg)))
    return PLIST_PATH


def instructions(cfg: dict | None = None) -> str:
    s = (cfg or load_unattended_config())["schedule"]
    installed = AGENT_PATH.exists()
    return "\n".join([
        f"Nightly agent {LABEL}: start {s['start']} ({s.get('mode', 'full')} mode), graceful stop by {s['stop']}.",
        f"Generated plist: {PLIST_PATH}",
        f"Currently installed: {'yes' if installed else 'no'} ({AGENT_PATH})",
        "Install:    ./scripts/install_schedule.sh",
        "Uninstall:  ./scripts/uninstall_schedule.sh",
        f"Inspect:    launchctl print gui/$(id -u)/{LABEL}",
        "Change the times in config/unattended.json (schedule.start / schedule.stop), then reinstall.",
    ])
