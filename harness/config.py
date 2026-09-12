"""Paths, pinned model identity, relaxation settings, and the saved compute config."""

from __future__ import annotations

import hashlib
import json
import os
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
UNATTENDED_CONFIG = CONFIG_DIR / "unattended.json"
QUEUE_DB = RESULTS_DIR / "queue.sqlite"

# Model registry. Every engine is pinned by file hash (mace-torch >= 0.3.10 silently switched its default
# "mace_mp()" model to MACE-MPA-0, so library defaults are never used). The active model is chosen per
# process with the HARNESS_MODEL environment variable (default: the round-1 baseline). Its key enters the
# settings tag, so results of different models never mix; the baseline keeps its round-1 tag.
#   loader  how engine.get_calculator builds the ASE calculator
#   env     separate virtualenv (models whose dependencies conflict with mace-torch); None = this venv
#   compliant  Matbench Discovery compliance of the training data (WBM excluded): True / False / "unverified"
BASELINE_MODEL = "mace-mp-0-medium"
MODELS = {
    "mace-mp-0-medium": {
        "name": "MACE-MP-0 medium", "loader": "mace", "env": None,
        "file": "2023-12-03-mace-128-L1_epoch-199.model",
        "url": "https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/2023-12-03-mace-128-L1_epoch-199.model",
        "sha256": "01bfe22100139f424713cf921144e5509cbe353d67aa9fa1be9c6e1e0ed35845",
        "training_data": "MPtrj (Materials Project PBE/PBE+U relaxation trajectories, 2022.9)",
        "license": "MIT (code and checkpoint)", "compliant": True,
    },
    "mace-mpa-0-medium": {
        "name": "MACE-MPA-0 medium", "loader": "mace", "env": None,
        "file": "mace-mpa-0-medium.model",
        "url": "https://github.com/ACEsuit/mace-foundations/releases/download/mace_mpa_0/mace-mpa-0-medium.model",
        "size_bytes": 79462305,
        "sha256": "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638",  # downloaded 2026-09-11
        "training_data": "MPtrj + sAlex (subsampled Alexandria, WBM-overlapping structures removed)",
        "license": "MIT (code and checkpoint)", "compliant": True,
    },
    "esen-30m-oam": {
        "name": "eSEN-30M-OAM", "loader": "fairchem", "env": ".envs/fairchem",
        "file": "esen_30m_oam.pt", "url": "https://huggingface.co/fairchem/OMAT24/resolve/main/esen_30m_oam.pt",
        "gated": True, "dtypes": ["float32"], "size_bytes": 362285045,
        "sha256": "adf7d38e5bccb8e0334434c0bd65ac75661fb646891df17ecc89c19d111efde1",  # downloaded 2026-09-11
        "training_data": "OMat24 + MPtrj + sAlex", "compliant": True,
        "license": "code MIT; checkpoint OMat24 license (commercial use permitted, FAIR acceptable-use policy)",
    },
    "sevennet-omni": {
        "name": "SevenNet-Omni", "loader": "sevenn", "env": ".envs/sevenn",
        "file": "checkpoint_sevennet_omni_i12.pth", "url": "https://ndownloader.figshare.com/files/60977863",
        "sha256": "771543388f360d2762e09f62de685bfb85e9f637a06575f2545f03974d6f0522", "size_bytes": 219904945,
        "modal": "mpa",  # PBE(+U) task used for Matbench Discovery (SevenNet docs)
        "dtypes": ["float32"],  # the calculator runs float32 only; a float64 request is refused, never relabelled
        "training_data": "COSMOS: 15 datasets, 242.8M structures (MPtrj, OMat24, Alexandria, MatPES, OC20/22, "
                         "ODAC23, OMol25, SPICE, QCML, MAD, MP-ALOE, MP-/MatPES-r2SCAN)",
        # Still "unverified", but no longer unexamined — see reports/leakage_check.md. OMat24 (101.9M) and the
        # 3D Alexandria part (sAlex, 10.4M) are WBM-prototype-filtered by their authors (arXiv:2410.12771
        # §2.1.1, §4.3). About 1% of the training set — Alexandria 1D/2D (~1.6M), MatPES (0.78M), MAD (0.09M) —
        # carries no documented WBM filter, so the flag stays and the engine is not adopted.
        "compliant": "unverified", "license": "MIT (code and checkpoint)",
        "compliance_note": "reports/leakage_check.md: OMat24 + sAlex filtered at source; ~1% of training "
                           "(Alexandria 1D/2D, MatPES, MAD) undocumented",
    },
}
ACTIVE_MODEL = os.environ.get("HARNESS_MODEL", BASELINE_MODEL)
if ACTIVE_MODEL not in MODELS:
    raise KeyError(f"HARNESS_MODEL={ACTIVE_MODEL!r} is not in the registry ({sorted(MODELS)})")
MODEL = {"key": ACTIVE_MODEL, **MODELS[ACTIVE_MODEL]}
MODEL["mace_key"] = "medium"  # legacy field (round-1 metadata)


@lru_cache(maxsize=None)
def model_path(key: str | None = None) -> Path:
    m = MODELS[key or ACTIVE_MODEL]
    path = MODELS_DIR / m["file"]
    if not path.is_file():
        raise FileNotFoundError(f"Model weights missing at {path}. Source: {m['url']}"
                                + (" (gated: accept the license on Hugging Face first)" if m.get("gated") else ""))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if m.get("sha256") is None:
        raise RuntimeError(f"{m['name']}: no SHA-256 pinned in config.MODELS yet (file hash {digest}); pin it before use")
    if digest != m["sha256"]:
        raise RuntimeError(f"Model hash mismatch for {path}: {digest} != {m['sha256']}")
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

# Retry ladder for relaxations that do not converge (or fail the sanity guard) under DEFAULT_RELAX.
# The convergence criteria (fmax, max |stress|) are identical on every rung and are never loosened;
# only the optimizer, the step cap and the starting point change. Rung 1 is DEFAULT_RELAX itself.
#   "continue": start from the previous rung's end point;  "perturb": restart from the original
#   structure with a small fixed-seed rattle + strain (PERTURB_RESTART).
FALLBACK_LADDER = (
    ("fire", RelaxSettings(optimizer="FIRE", max_steps=1500, timeout_s=3000.0), "continue"),
    ("perturbed_restart", RelaxSettings(max_steps=1000, timeout_s=2400.0), "perturb"),
)
PERTURB_RESTART = {"rattle_angstrom": 0.02, "strain": 0.005, "supercell": (1, 1, 1)}
LADDER_BUDGET_S = sum(s.timeout_s for _, s, _ in FALLBACK_LADDER) + 600.0  # watchdog allowance per ladder job


def settings_tag(device: str, dtype: str, relax: RelaxSettings = DEFAULT_RELAX, model: str | None = None) -> str:
    """Short hash of everything that changes a simulated value. Appended to every job key
    ("...@<tag>"), so changing the protocol can never silently reuse stale results.

    The baseline model hashes exactly the round-1 blob (tag 207ccc81 for its CPU/float64 protocol);
    every other model adds its registry key, so its results can never share a tag with another model's."""
    key = model or ACTIVE_MODEL
    m = MODELS[key]
    blob = {"model": m.get("sha256") or key, "device": device, "dtype": dtype, "relax": relax.as_dict()}
    if key != BASELINE_MODEL:
        blob["model_key"] = key
    return hashlib.sha256(json.dumps(blob, sort_keys=True).encode()).hexdigest()[:8]

# Used until `python -m harness benchmark` writes config/compute.json.
_FALLBACK_COMPUTE = {"device": "cpu", "dtype": "float64", "workers": 1, "threads_per_worker": None}


def compute_config_path(model: str | None = None) -> Path:
    """Benchmarked layout per model: config/compute.json for the baseline, config/compute-<key>.json otherwise."""
    key = model or ACTIVE_MODEL
    return COMPUTE_CONFIG if key == BASELINE_MODEL else CONFIG_DIR / f"compute-{key}.json"


def load_compute_config() -> dict:
    path = compute_config_path()
    if path.is_file():
        return json.loads(path.read_text())
    from harness.platform_check import core_counts

    return {**_FALLBACK_COMPUTE, "threads_per_worker": core_counts()["performance"], "source": "fallback"}


def save_compute_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    compute_config_path().write_text(json.dumps(cfg, indent=2, default=str) + "\n")


# Unattended-run (orchestration) settings. Nothing here changes what is computed or how it is scored;
# config/unattended.json overrides these defaults key by key.
UNATTENDED_DEFAULTS = {
    "max_pairs": 2000,               # auto-generated substitution pairs to queue
    "max_atoms": 40,                 # max atoms per cell (both parent and target, PBE structures)
    "ood_sample": 2000,              # WBM out-of-distribution sample size
    # sub = unscaled start, sub_rescaled = predicted-volume start, static = single point at the PBE
    # structure; add "sub_rattled" for 2x2x2 symmetry-broken runs (8x the atoms)
    "auto_pair_kinds": ["sub", "sub_rescaled", "ctrl", "static"],
    "max_attempts": 2,               # first try + one retry
    "hard_timeout_s": 1800,          # watchdog for hung workers (the engine's own limit is 900 s/relaxation)
    "report_every": 100,             # partial report every N completed jobs
    "power_poll_s": 300,             # pmset check interval
    "polite_reserved_cores": 2,      # performance cores left free in polite mode
    "polite_nice": 10,               # scheduling niceness of polite-mode workers
    "failure_alert_fraction": 0.10,  # notify when more than this fraction of jobs fail
    "failure_alert_min_jobs": 20,    # ...once at least this many finished (always checked at the end)
    "schedule": {"start": "23:00", "stop": "07:00", "mode": "full"},
}


def load_unattended_config() -> dict:
    cfg = json.loads(json.dumps(UNATTENDED_DEFAULTS))
    if UNATTENDED_CONFIG.is_file():
        for k, v in json.loads(UNATTENDED_CONFIG.read_text()).items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg
