"""Validation harness for a MACE-based materials simulation engine."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Keep every third-party cache inside the project folder. Must run before
# torch / matplotlib are imported anywhere.
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))
os.environ.setdefault("TORCH_HOME", str(ROOT / "cache" / "torch"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / "cache" / "xdg"))

__version__ = "0.1.0"
