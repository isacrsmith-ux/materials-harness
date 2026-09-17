"""Optional launchd user agents. Generated here; installed only by the user (scripts/).

nightly  runs `run_unattended.sh --foreground <mode> --stop-at <stop>` at schedule.start. The runner
         drains gracefully at the stop time (finishes running jobs, then exits).
backup   runs `scripts/backup.sh` at schedule.backup.
If the Mac is asleep at a start time, launchd starts the job at the next wake.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

from harness import ROOT
from harness.config import CONFIG_DIR, LOG_DIR, load_unattended_config

LABEL = "com.materials-harness.nightly"
PLIST_PATH = CONFIG_DIR / "launchd" / f"{LABEL}.plist"
AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
BACKUP_LABEL = "com.materials-harness.backup"
BACKUP_PLIST_PATH = CONFIG_DIR / "launchd" / f"{BACKUP_LABEL}.plist"
BACKUP_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{BACKUP_LABEL}.plist"


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


def build_backup_plist(cfg: dict | None = None) -> dict:
    h, m = _hm((cfg or load_unattended_config())["schedule"]["backup"])
    return {
        "Label": BACKUP_LABEL,
        "ProgramArguments": ["/bin/bash", str(ROOT / "scripts" / "backup.sh")],
        "WorkingDirectory": str(ROOT),
        "StartCalendarInterval": {"Hour": h, "Minute": m},
        "RunAtLoad": False,
        "ProcessType": "Background",
        "StandardOutPath": str(LOG_DIR / "backup.out.log"),
        "StandardErrorPath": str(LOG_DIR / "backup.err.log"),
        "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
    }


def write_plist(cfg: dict | None = None) -> list[Path]:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_bytes(plistlib.dumps(build_plist(cfg)))
    BACKUP_PLIST_PATH.write_bytes(plistlib.dumps(build_backup_plist(cfg)))
    return [PLIST_PATH, BACKUP_PLIST_PATH]


def instructions(cfg: dict | None = None) -> str:
    s = (cfg or load_unattended_config())["schedule"]
    return "\n".join([
        f"Nightly agent {LABEL}: start {s['start']} ({s.get('mode', 'full')} mode), graceful stop by {s['stop']}.",
        f"  plist {PLIST_PATH}; installed: {'yes' if AGENT_PATH.exists() else 'no'} ({AGENT_PATH})",
        "  install: ./scripts/install_schedule.sh    uninstall: ./scripts/uninstall_schedule.sh",
        f"Nightly backup {BACKUP_LABEL}: {s['backup']}, runs scripts/backup.sh.",
        f"  plist {BACKUP_PLIST_PATH}; installed: {'yes' if BACKUP_AGENT_PATH.exists() else 'no'} ({BACKUP_AGENT_PATH})",
        "  install: ./scripts/install_schedule.sh backup    uninstall: ./scripts/uninstall_schedule.sh backup",
        "Inspect:  launchctl print gui/$(id -u)/<label>",
        "Change the times in config/unattended.json (schedule.start / stop / backup), then reinstall.",
    ])
