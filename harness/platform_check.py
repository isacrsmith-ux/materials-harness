"""Platform guards and hardware detection for Apple Silicon Macs."""

from __future__ import annotations

import os
import platform
import subprocess
import sys


class PlatformError(RuntimeError):
    pass


def _sysctl(name: str) -> str | None:
    try:
        out = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def assert_native_arm64() -> None:
    """Stop unless we are a native arm64 process on macOS (not under Rosetta)."""
    if sys.platform != "darwin":
        raise PlatformError(f"This harness targets macOS on Apple Silicon; got {sys.platform}.")
    if platform.machine() != "arm64":
        raise PlatformError(
            f"platform.machine() == {platform.machine()!r}, expected 'arm64'. "
            "This Python is running under Rosetta or is an x86_64 build. "
            "Use the project venv (./uvw run ...), which is native arm64."
        )
    if _sysctl("sysctl.proc_translated") == "1":
        raise PlatformError("Process is translated by Rosetta 2. Run a native arm64 Python.")


def core_counts() -> dict[str, int]:
    """Performance / efficiency / total physical cores, detected at runtime."""
    physical = int(_sysctl("hw.physicalcpu") or os.cpu_count() or 1)
    perf = int(_sysctl("hw.perflevel0.physicalcpu") or 0) or physical
    eff = int(_sysctl("hw.perflevel1.physicalcpu") or 0)
    return {"performance": perf, "efficiency": eff, "physical": physical}


def machine_info() -> dict[str, object]:
    mem = _sysctl("hw.memsize")
    return {
        "chip": _sysctl("machdep.cpu.brand_string"),
        "model": _sysctl("hw.model"),
        "macos": platform.mac_ver()[0],
        "arch": platform.machine(),
        "memory_gb": round(int(mem) / 2**30, 1) if mem else None,
        "python": platform.python_version(),
        **{f"{k}_cores": v for k, v in core_counts().items()},
    }
