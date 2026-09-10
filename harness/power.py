"""Power source (AC / battery) for unattended runs, via `pmset -g batt`.

Test hook: if the environment variable HARNESS_POWER_OVERRIDE names a file containing "ac" or
"battery", that value is used instead of pmset. The variable is only set by tests, so a leftover
file can never make a real run ignore the battery.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

OVERRIDE_ENV = "HARNESS_POWER_OVERRIDE"


def parse_pmset(text: str | None) -> str:
    """'ac', 'battery' or 'unknown' from `pmset -g batt` output."""
    m = re.search(r"Now drawing from '([^']+)'", text or "")
    if not m:
        return "unknown"
    src = m.group(1).strip().lower()
    if src.startswith("ac"):
        return "ac"
    if src.startswith("battery") or "ups" in src:
        return "battery"
    return "unknown"


def override_path() -> Path | None:
    p = os.environ.get(OVERRIDE_ENV)
    return Path(p) if p else None


def power_source() -> str:
    p = override_path()
    if p is not None:
        try:
            v = p.read_text().strip().lower()
            if v in ("ac", "battery"):
                return v
        except OSError:
            pass
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return parse_pmset(out)
