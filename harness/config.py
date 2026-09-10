"""Paths, pinned model identity, relaxation settings, and the saved compute config."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from harness import ROOT

CACHE_DIR = ROOT / "cache"
MP_CACHE_DIR = CACHE_DIR / "mp"
EXTERNAL_CACHE_DIR = CACHE_DIR / "external"
DATA_DIR = ROOT / "data"  # curated, committed inputs (pair lists, experimental references)
MODELS_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"
DB_PATH = RESULTS_DIR / "results.sqlite"
LOG_DIR = ROOT / "logs"
REPORTS_DIR = ROOT / "reports"
FIG_DIR = REPORTS_DIR / "figures"
CONFIG_DIR = ROOT / "config"
COMPUTE_CONFIG = CONFIG_DIR / "compute.json"

# The engine under test. Pinned by file hash: mace-torch >= 0.3.10 silently switched its
# default "mace_mp()" model to MACE-MPA-0, so we never rely on library defaults.
MODEL = {
    "name": "MACE-MP-0 medium",
    "mace_key": "medium",
    "file": "2023-12-03-mace-128-L1_epoch-199.model",
    "url": "https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/2023-12-03-mace-128-L1_epoch-199.model",
    "sha256": "01bfe22100139f424713cf921144e5509cbe353d67aa9fa1be9c6e1e0ed35845",
    "training_data": "MPtrj (Materials Project PBE/PBE+U relaxation trajectories, 2022.9)",
}


@lru_cache(maxsize=1)
def model_path() -> Path:
    path = MODELS_DIR / MODEL["file"]
    if not path.is_file():
        raise FileNotFoundError(
            f"Model weights missing at {path}. Download with:\n"
            f"  curl -L -o '{path}' {MODEL['url']}"
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != MODEL["sha256"]:
        raise RuntimeError(f"Model hash mismatch for {path}: {digest} != {MODEL['sha256']}")
    return path


@dataclass(frozen=True)
class RelaxSettings:
    """Relaxation protocol recorded with every simulated value."""

    fmax: float = 0.01  # eV/Å on every atom
    # Explicit cell criterion. FrechetCellFilter applies fmax to stress * V / N, which lets small
    # cells stop with ~0.1-0.2 GPa residual stress; we additionally require max |stress| <= this.
    max_stress_gpa: float = 0.01
    max_steps: int = 500
    optimizer: str = "BFGS"
    cell_filter: str = "FrechetCellFilter"
    timeout_s: float = 900.0  # per-structure wall-clock limit

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT_RELAX = RelaxSettings()


def settings_tag(device: str, dtype: str, relax: RelaxSettings = DEFAULT_RELAX) -> str:
    """Short hash of everything that changes a simulated value. Appended to every job key
    ("...@<tag>"), so changing the protocol can never silently reuse stale results."""
    blob = json.dumps({"model": MODEL["sha256"], "device": device, "dtype": dtype, "relax": relax.as_dict()},
                      sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:8]

# Used until `python -m harness benchmark` writes config/compute.json.
_FALLBACK_COMPUTE = {"device": "cpu", "dtype": "float64", "workers": 1, "threads_per_worker": None}


def load_compute_config() -> dict:
    if COMPUTE_CONFIG.is_file():
        return json.loads(COMPUTE_CONFIG.read_text())
    from harness.platform_check import core_counts

    return {**_FALLBACK_COMPUTE, "threads_per_worker": core_counts()["performance"], "source": "fallback"}


def save_compute_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    COMPUTE_CONFIG.write_text(json.dumps(cfg, indent=2, default=str) + "\n")
