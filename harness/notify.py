"""Notifications: a macOS banner (osascript) and, optionally, a phone push via ntfy.sh.

ntfy is off unless NTFY_TOPIC is set in .env (NTFY_SERVER optional, default https://ntfy.sh).
Messages carry run progress only — never paths to secrets or the MP key. HARNESS_NOTIFY=0
silences everything (used by unit tests).
"""

from __future__ import annotations

import logging
import os
import subprocess
import urllib.request

from harness import ROOT

log = logging.getLogger(__name__)


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def macos(title: str, message: str) -> None:
    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=15, check=True)


def ntfy_settings() -> tuple[str | None, str]:
    from dotenv import dotenv_values

    env = dotenv_values(ROOT / ".env")
    topic = (env.get("NTFY_TOPIC") or "").strip() or None
    server = (env.get("NTFY_SERVER") or "").strip() or "https://ntfy.sh"
    return topic, server


def ntfy(title: str, message: str) -> bool:
    topic, server = ntfy_settings()
    if not topic:
        return False
    req = urllib.request.Request(f"{server.rstrip('/')}/{topic}", data=message.encode("utf-8"), method="POST",
                                 headers={"Title": title.encode("ascii", "ignore").decode("ascii")})
    with urllib.request.urlopen(req, timeout=15):
        pass
    return True


def notify(title: str, message: str) -> None:
    if os.environ.get("HARNESS_NOTIFY", "1") == "0":
        log.info("notification (silenced): %s — %s", title, message)
        return
    log.info("notification: %s — %s", title, message)
    try:
        macos(title, message)
    except Exception as exc:  # noqa: BLE001 — a notification failure must never stop a run
        log.warning("macOS notification failed: %s", exc)
    try:
        ntfy(title, message)
    except Exception as exc:  # noqa: BLE001
        log.warning("ntfy push failed: %s", exc)
