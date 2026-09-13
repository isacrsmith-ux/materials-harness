"""Skip, with a reason, the tests that cannot run until setup is finished.

`pytest -m "not slow"` needs nothing but a checkout — no API key, no model weights, no downloaded
data — and that is the run the README points a newcomer at. The `slow` tests do need those, and
before this file they raised `MissingAPIKey` and `FileNotFoundError` in a fresh clone, which reads
like a broken repository rather than an unfinished setup. They now skip and say which README step is
missing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _has_api_key() -> bool:
    if os.environ.get("MP_API_KEY", "").strip():
        return True
    env = ROOT / ".env"
    if not env.is_file():
        return False
    for line in env.read_text().splitlines():
        if line.strip().startswith("MP_API_KEY="):
            return bool(line.split("=", 1)[1].strip().strip("\"'"))
    return False


def _has_model_weights() -> bool:
    from harness import config

    try:
        return config.model_path().is_file()
    except Exception:  # noqa: BLE001 — missing file, missing pin, or a hash mismatch: all "not set up"
        return False


def pytest_collection_modifyitems(config, items):
    """Mark every `slow` test skipped when the setup it needs has not been done."""
    have_key, have_weights = _has_api_key(), _has_model_weights()
    if have_key and have_weights:
        return
    missing = []
    if not have_key:
        missing.append("a Materials Project API key (README setup step 4: cp .env.example .env)")
    if not have_weights:
        missing.append("the model weights (README setup step 3)")
    reason = "needs " + " and ".join(missing)
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
