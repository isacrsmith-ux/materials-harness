"""The simulation engine under test: MACE-MP-0 + ASE relaxations.

One calculator per (device, dtype) per process. mace_mp() sets torch's global default
dtype, so never mix float32 and float64 engines in the same process — the benchmark and
the process pool each use fresh spawned workers for that reason.
"""

from __future__ import annotations

import contextlib
import os
import signal
import threading
import time
import warnings
from dataclasses import dataclass, field
from importlib.metadata import version

import numpy as np
from pymatgen.core import Structure

from harness import config
from harness.config import RelaxSettings

_CALCS: dict[tuple[str, str], object] = {}
EV_PER_A3_TO_GPA = 160.21766208


class RelaxTimeout(Exception):
    pass


def stress_residual(stress_voigt, constant_volume: bool = False) -> float:
    """max |stress| (eV/Å^3); at constant volume only the deviatoric part (hydrostatic removed)."""
    s = np.asarray(stress_voigt, dtype=float).copy()
    if constant_volume:
        s[:3] -= s[:3].mean()
    return float(np.abs(s).max())


def _mace_calculator(device: str, dtype: str):
    from mace.calculators import mace_mp

    # The checkpoint is stored in float64, and torch.load(map_location="mps") fails on
    # float64 tensors — so for MPS, load + downcast on CPU, then move to the GPU.
    load_device = "cpu" if device == "mps" else device
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with contextlib.redirect_stdout(open(os.devnull, "w")):
            calc = mace_mp(model=str(config.model_path()), device=load_device, default_dtype=dtype)
    if device == "mps":
        import torch

        calc.models = [m.to("mps") for m in calc.models]
        calc.device = torch.device("mps")
    return calc


def _fairchem_calculator(device: str, dtype: str):
    """eSEN (fairchem-core, run from its own venv). The calculator API differs between fairchem-core
    releases; both are tried, and anything else is a clear error rather than a silent fallback."""
    try:
        from fairchem.core import OCPCalculator  # fairchem-core 1.x
    except ImportError:
        OCPCalculator = None
    if OCPCalculator is not None:  # errors while building it surface as they are, never as "wrong version"
        return OCPCalculator(checkpoint_path=str(config.model_path()), cpu=(device == "cpu"), seed=0)
    from fairchem.core.units.mlip_unit import load_predict_unit  # fairchem-core 2.x
    from fairchem.core import FAIRChemCalculator

    unit = load_predict_unit(str(config.model_path()), device="cuda" if device == "cuda" else "cpu")
    return FAIRChemCalculator(unit, task_name="omat")


def _sevenn_calculator(device: str, dtype: str):
    """SevenNet (own venv). modal from the registry ('mpa': the PBE(+U) task used for Matbench Discovery);
    cuEquivariance / flash kernels are CUDA-only and stay off."""
    from sevenn.calculator import SevenNetCalculator

    kw = {"model": str(config.model_path()), "modal": config.MODEL.get("modal", "mpa"), "device": device}
    try:
        return SevenNetCalculator(**kw, enable_cueq=False, enable_flash=False)
    except TypeError:  # older sevenn without these switches
        return SevenNetCalculator(**kw)


_LOADERS = {"mace": _mace_calculator, "fairchem": _fairchem_calculator, "sevenn": _sevenn_calculator}


def get_calculator(device: str = "cpu", dtype: str = "float64"):
    """ASE calculator of the ACTIVE model (config.MODEL, from HARNESS_MODEL) on device / dtype."""
    key = (config.ACTIVE_MODEL, device, dtype)
    if key not in _CALCS:
        if device == "mps":
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        if device == "mps" and dtype == "float64":
            raise ValueError("PyTorch MPS does not support float64.")
        if dtype not in config.MODEL.get("dtypes", ("float64", "float32")):
            raise ValueError(f"{config.MODEL['name']} runs {config.MODEL['dtypes']} only; {dtype} would be mislabelled")
        _CALCS[key] = _LOADERS[config.MODEL["loader"]](device, dtype)
    return _CALCS[key]


def engine_metadata(device: str, dtype: str, settings: RelaxSettings | None = None) -> dict:
    """Everything needed to reproduce a simulated value. Stored with every result row."""
    def _v(pkg):
        try:
            return version(pkg)
        except Exception:  # noqa: BLE001 — a package absent from this model's venv
            return None

    meta = {
        "model_key": config.ACTIVE_MODEL,
        "model_name": config.MODEL["name"],
        "model_file": config.MODEL["file"],
        "model_sha256": config.MODEL["sha256"],
        "mace_torch_version": _v("mace-torch"),
        "fairchem_core_version": _v("fairchem-core"),
        "sevenn_version": _v("sevenn"),
        "torch_version": _v("torch"),
        "ase_version": _v("ase"),
        "device": device,
        "dtype": dtype,
    }
    if settings is not None:
        meta["relax"] = settings.as_dict()
    return meta


@contextlib.contextmanager
def wall_clock_limit(seconds: float | None):
    """Raise RelaxTimeout after `seconds` (SIGALRM; only possible on the main thread)."""
    if not seconds or threading.current_thread() is not threading.main_thread():
        yield
        return

    def _handler(signum, frame):
        raise RelaxTimeout(f"exceeded {seconds:.0f} s wall-clock limit")

    previous = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@dataclass
class RelaxResult:
    structure: Structure
    energy_per_atom: float  # eV/atom, raw MACE (MP-compatible PBE/PBE+U reference, uncorrected)
    converged: bool
    n_steps: int
    fmax_final: float  # eV/Å, max atomic force
    max_stress_gpa: float
    wall_time_s: float
    min_distance_ratio: float = float("nan")  # see compare.UNPHYSICAL_DISTANCE_RATIO
    metadata: dict = field(default_factory=dict)

    @property
    def time_per_step_s(self) -> float:
        return self.wall_time_s / max(self.n_steps, 1)


def _to_atoms(structure: Structure):
    from pymatgen.io.ase import AseAtomsAdaptor

    s = structure.copy()
    s.remove_site_property("magmom") if "magmom" in s.site_properties else None
    return AseAtomsAdaptor.get_atoms(s)


def _to_structure(atoms) -> Structure:
    return Structure(atoms.cell.array.copy(), atoms.get_chemical_symbols(), atoms.positions.copy(),
                     coords_are_cartesian=True)


def relax(
    structure: Structure,
    settings: RelaxSettings = config.DEFAULT_RELAX,
    device: str = "cpu",
    dtype: str = "float64",
    relax_cell: bool = True,
    constant_volume: bool = False,
) -> RelaxResult:
    """Relax positions (and cell) with FrechetCellFilter + settings.optimizer (BFGS or FIRE).
    Raises RelaxTimeout.

    constant_volume=True relaxes cell shape at fixed volume (equation-of-state points); the stress
    criterion then applies to the deviatoric stress only, since the hydrostatic part is the point.
    """
    from ase.filters import FrechetCellFilter
    from ase.optimize import BFGS, FIRE

    optimizers = {"BFGS": BFGS, "FIRE": FIRE}
    if settings.optimizer not in optimizers:
        raise ValueError(f"unknown optimizer {settings.optimizer!r}")
    atoms = _to_atoms(structure)
    atoms.calc = get_calculator(device, dtype)
    target = FrechetCellFilter(atoms, constant_volume=constant_volume) if relax_cell else atoms
    opt = optimizers[settings.optimizer](target, logfile=None)
    stress_limit = settings.max_stress_gpa / EV_PER_A3_TO_GPA
    filter_fmax = settings.fmax
    t0 = time.perf_counter()
    with wall_clock_limit(settings.timeout_s):
        while (remaining := settings.max_steps - opt.get_number_of_steps()) > 0:
            opt.run(fmax=filter_fmax, steps=remaining)
            forces_ok = np.linalg.norm(atoms.get_forces(), axis=1).max() <= settings.fmax
            stress_ok = not relax_cell or stress_residual(atoms.get_stress(voigt=True), constant_volume) <= stress_limit
            if (forces_ok and stress_ok) or filter_fmax < 1e-5:
                break
            # The filter scales stress by V/N; tighten its criterion (same BFGS, Hessian kept)
            # until the explicit stress limit holds or the step cap is reached.
            filter_fmax /= 2
    wall = time.perf_counter() - t0

    from harness.compare import UNPHYSICAL_DISTANCE_RATIO, energy_rejection, min_distance_ratio

    forces = atoms.get_forces()
    stress = atoms.get_stress(voigt=True)  # eV/Å^3
    fmax_final = float(np.linalg.norm(forces, axis=1).max())
    final = _to_structure(atoms)
    mdr = min_distance_ratio(final)
    e_per_atom = float(atoms.get_potential_energy() / len(atoms))
    # An unphysical geometry (collapsed atoms) or a physically impossible energy is never reported as a
    # converged result — the fallback ladder stops at the first converged rung, so a rung that landed in
    # a spurious deep minimum of the model's PES must not end the ladder. Only the reference-free half of
    # compare's energy rule can apply here: the engine has no DFT energy to compare against.
    converged = (fmax_final <= settings.fmax
                 and (not relax_cell or stress_residual(stress, constant_volume) <= stress_limit)
                 and mdr >= UNPHYSICAL_DISTANCE_RATIO
                 and energy_rejection(e_per_atom) is None)
    return RelaxResult(
        structure=final,
        min_distance_ratio=mdr,
        energy_per_atom=e_per_atom,
        converged=converged,
        n_steps=int(opt.get_number_of_steps()),
        fmax_final=fmax_final,
        max_stress_gpa=float(np.abs(stress).max() * EV_PER_A3_TO_GPA),
        wall_time_s=wall,
        metadata=engine_metadata(device, dtype, settings) | {"relax_cell": relax_cell, "constant_volume": constant_volume},
    )


def single_point(structure: Structure, device: str = "cpu", dtype: str = "float64") -> dict:
    """Energy (eV/atom), forces (eV/Å), stress (eV/Å^3) for a fixed structure."""
    atoms = _to_atoms(structure)
    calc = get_calculator(device, dtype)
    calc.reset()  # ASE caches results for identical positions; always compute fresh
    atoms.calc = calc
    return {
        "energy_per_atom": float(atoms.get_potential_energy() / len(atoms)),
        "forces": atoms.get_forces().copy(),
        "stress": atoms.get_stress(voigt=True).copy(),
    }
