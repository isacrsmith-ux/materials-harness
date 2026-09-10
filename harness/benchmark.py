"""Compute benchmark: CPU/float64 vs MPS/float32, and worker x thread layouts.

Writes config/compute.json. MPS is only recommended if its relaxed results agree with the
CPU/float64 reference within AGREEMENT_TOL *and* it is actually faster.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import numpy as np

from harness import config
from harness.platform_check import assert_native_arm64, core_counts, machine_info
from harness.runner import run_pool

# Much tighter than the ~1 % physics targets, so precision loss can't hide in the noise.
AGREEMENT_TOL = {
    "energy_mev_per_atom": 1.0,
    "volume_pct": 0.1,
    "lattice_angstrom": 0.005,
    "single_point_force_ev_per_a": 0.005,
}


def _device_structures():
    """Rattled, strained supercells (64-72 atoms) — no MP access needed."""
    from ase.build import bulk
    from pymatgen.io.ase import AseAtomsAdaptor

    specs = {
        "Si_diamond_64": bulk("Si", "diamond", a=5.43, cubic=True).repeat(2),
        "MgO_rocksalt_64": bulk("MgO", "rocksalt", a=4.21, cubic=True).repeat(2),
        "GaN_wurtzite_72": bulk("GaN", "wurtzite", a=3.19, c=5.19).repeat((3, 3, 2)),
    }
    out = {}
    for i, (name, atoms) in enumerate(specs.items()):
        atoms.set_cell(atoms.cell * 1.02, scale_atoms=True)
        atoms.rattle(stdev=0.03, seed=42 + i)
        out[name] = AseAtomsAdaptor.get_structure(atoms)
    return out


def _pool_structures():
    """A batch shaped like the real suites: many small primitive/conventional cells."""
    from ase.build import bulk
    from ase.spacegroup import crystal
    from pymatgen.io.ase import AseAtomsAdaptor

    cells = [
        bulk("Si", "diamond", a=5.43), bulk("Ge", "diamond", a=5.66), bulk("C", "diamond", a=3.57),
        bulk("Al", "fcc", a=4.05, cubic=True), bulk("Cu", "fcc", a=3.61, cubic=True),
        bulk("MgO", "rocksalt", a=4.21, cubic=True), bulk("LiF", "rocksalt", a=4.03, cubic=True),
        bulk("NaCl", "rocksalt", a=5.64, cubic=True), bulk("GaAs", "zincblende", a=5.65, cubic=True),
        bulk("SiC", "zincblende", a=4.36, cubic=True), bulk("GaN", "wurtzite", a=3.19, c=5.19),
        bulk("AlN", "wurtzite", a=3.11, c=4.98), bulk("ZnO", "wurtzite", a=3.25, c=5.21),
        bulk("CaF2", "fluorite", a=5.46, cubic=True),
        crystal(["Ti", "O"], basis=[(0, 0, 0), (0.305, 0.305, 0)], spacegroup=136,
                cellpar=[4.59, 4.59, 2.96, 90, 90, 90]),
        crystal(["Sr", "Ti", "O"], basis=[(0, 0, 0), (0.5, 0.5, 0.5), (0.5, 0.5, 0)], spacegroup=221,
                cellpar=[3.905] * 3 + [90] * 3),
    ]
    out = []
    for i, atoms in enumerate(cells):
        atoms.set_cell(atoms.cell * (1.03 if i % 2 else 0.97), scale_atoms=True)
        atoms.rattle(stdev=0.02, seed=i)
        out.append({"name": atoms.get_chemical_formula(), "structure": AseAtomsAdaptor.get_structure(atoms)})
    return out


def _device_job(job: dict) -> dict:
    """Runs inside a spawned worker: warm up, time single points, then relax."""
    from harness import engine

    s, device, dtype = job["structure"], job["device"], job["dtype"]
    engine.single_point(s, device, dtype)  # warm-up (model load, MPS kernel compile)
    t0 = time.perf_counter()
    n_sp = 10
    for _ in range(n_sp):
        sp = engine.single_point(s, device, dtype)
    sp_ms = (time.perf_counter() - t0) / n_sp * 1000
    res = engine.relax(s, config.DEFAULT_RELAX, device, dtype)
    return {
        "single_point_ms": sp_ms,
        "sp_energy_per_atom": sp["energy_per_atom"],
        "sp_forces": sp["forces"].tolist(),
        "relaxed": res.structure,
        "energy_per_atom": res.energy_per_atom,
        "converged": res.converged,
        "n_steps": res.n_steps,
        "relax_wall_s": res.wall_time_s,
        "fmax_final": res.fmax_final,
    }


def _pool_job(job: dict) -> dict:
    from harness import engine

    res = engine.relax(job["structure"], config.DEFAULT_RELAX, "cpu", "float64")
    return {"converged": res.converged, "n_steps": res.n_steps, "energy_per_atom": res.energy_per_atom}


def _compare(ref: dict, test: dict) -> dict:
    from pymatgen.analysis.structure_matcher import StructureMatcher

    a, b = ref["relaxed"], test["relaxed"]
    return {
        "energy_mev_per_atom": abs(ref["energy_per_atom"] - test["energy_per_atom"]) * 1000,
        "volume_pct": abs(b.volume / len(b) - a.volume / len(a)) / (a.volume / len(a)) * 100,
        "lattice_angstrom": float(np.max(np.abs(np.array(a.lattice.abc) - np.array(b.lattice.abc)))),
        "single_point_force_ev_per_a": float(np.max(np.abs(np.array(ref["sp_forces"]) - np.array(test["sp_forces"])))),
        "structure_match": bool(StructureMatcher().fit(a, b)),
        "test_converged": test["converged"],
    }


def device_benchmark(threads: int) -> dict:
    structures = _device_structures()
    runs: dict[str, dict] = {}
    for device, dtype, env in [("cpu", "float64", {}), ("mps", "float32", {"PYTORCH_ENABLE_MPS_FALLBACK": "1"})]:
        label = f"{device}/{dtype}"
        runs[label] = {}
        jobs = [{"name": n, "structure": s, "device": device, "dtype": dtype} for n, s in structures.items()]
        run_pool(_device_job, jobs, workers=1, threads=threads, extra_env=env,
                 on_result=lambda job, r, lab=label: runs[lab].__setitem__(job["name"], r))
        print(f"  {label}: done")

    timing_keys = ("single_point_ms", "relax_wall_s", "n_steps", "converged", "energy_per_atom")
    per_structure, all_agree, errors = {}, True, []
    for name in structures:
        ref, test = runs["cpu/float64"][name], runs["mps/float32"][name]
        if ref.get("status") != "ok" or test.get("status") != "ok":
            errors.append({name: {"cpu": ref.get("error"), "mps": test.get("error")}})
            all_agree = False
            per_structure[name] = {"n_atoms": len(structures[name]),
                                   "cpu_float64": {k: ref.get(k) for k in timing_keys},
                                   "mps_float32": None}
            continue
        cmp = _compare(ref, test)
        cmp["agrees"] = all(cmp[k] <= tol for k, tol in AGREEMENT_TOL.items()) and cmp["structure_match"] and cmp["test_converged"]
        all_agree &= cmp["agrees"]
        per_structure[name] = {
            "n_atoms": len(structures[name]),
            "cpu_float64": {k: ref[k] for k in ("single_point_ms", "relax_wall_s", "n_steps", "converged", "energy_per_atom")},
            "mps_float32": {k: test[k] for k in ("single_point_ms", "relax_wall_s", "n_steps", "converged", "energy_per_atom")},
            "differences": cmp,
            "single_point_speedup_mps": ref["single_point_ms"] / test["single_point_ms"],
        }
    speedups = [v["single_point_speedup_mps"] for v in per_structure.values() if "single_point_speedup_mps" in v]
    mean_speedup = float(np.mean(speedups)) if speedups else float("nan")
    use_mps = bool(all_agree and mean_speedup > 1.1)
    mps_errors = {n: runs["mps/float32"][n].get("error") for n in structures
                  if runs["mps/float32"][n].get("status") != "ok"}
    if use_mps:
        reason = f"MPS/float32 agreed within tolerance on every structure and was {mean_speedup:.2f}x faster."
    elif mps_errors:
        first = next(iter(mps_errors.values())) or "unknown error"
        reason = (f"MPS/float32 could not run ({len(mps_errors)}/{len(structures)} structures failed: "
                  f"{first.splitlines()[0][:200]}); CPU/float64 required.")
    elif not all_agree:
        reason = "MPS/float32 did NOT agree with CPU/float64 within tolerance on every structure; CPU/float64 required."
    else:
        reason = f"MPS/float32 agreed but was not meaningfully faster ({mean_speedup:.2f}x); CPU/float64 kept."
    return {"tolerances": AGREEMENT_TOL, "threads": threads, "per_structure": per_structure, "errors": errors,
            "all_agree": all_agree, "mean_single_point_speedup_mps": mean_speedup,
            "recommend": {"device": "mps", "dtype": "float32"} if use_mps else {"device": "cpu", "dtype": "float64"},
            "reason": reason}


def layout_candidates(perf: int) -> list[tuple[int, int]]:
    """2-3 (workers, threads) layouts with workers*threads ~= performance cores."""
    cands = [(1, perf), (max(perf // 2, 1), 2), (perf, 1)]
    return list(dict.fromkeys(c for c in cands if c[0] * c[1] <= perf))


POOL_REPEATS = 3  # 48 jobs, so worker spawn + model load is amortized as in the real suites


def pool_benchmark(perf: int) -> dict:
    jobs = _pool_structures() * POOL_REPEATS
    results = []
    for workers, threads in layout_candidates(perf):
        statuses = []
        t0 = time.perf_counter()
        run_pool(_pool_job, jobs, workers, threads, on_result=lambda j, r: statuses.append(r.get("status")))
        wall = time.perf_counter() - t0
        results.append({"workers": workers, "threads_per_worker": threads, "wall_s": wall,
                        "n_jobs": len(jobs), "n_ok": statuses.count("ok"), "s_per_structure": wall / len(jobs)})
        print(f"  {workers} workers x {threads} threads: {wall:.1f} s for {len(jobs)} relaxations")
    best = min((r for r in results if r["n_ok"] == r["n_jobs"]), key=lambda r: r["wall_s"], default=None)
    return {"layouts": results, "best": best}


def run_benchmark() -> dict:
    assert_native_arm64()
    cores = core_counts()
    perf = cores["performance"]
    print(f"Detected {cores}")
    print("Device benchmark (CPU/float64 vs MPS/float32) ...")
    dev = device_benchmark(threads=perf)
    print(f"  -> {dev['reason']}")
    print("Pool benchmark (workers x threads) ...")
    pool = pool_benchmark(perf)
    best = pool["best"] or {"workers": 1, "threads_per_worker": perf}
    cfg = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": machine_info(),
        "device": dev["recommend"]["device"],
        "dtype": dev["recommend"]["dtype"],
        "workers": best["workers"],
        "threads_per_worker": best["threads_per_worker"],
        "device_reason": dev["reason"],
        "device_benchmark": dev,
        "pool_benchmark": pool,
        "source": "benchmark",
    }
    config.save_compute_config(cfg)
    print(f"Saved {config.COMPUTE_CONFIG.relative_to(config.ROOT)}: device={cfg['device']} dtype={cfg['dtype']} "
          f"workers={cfg['workers']} threads/worker={cfg['threads_per_worker']}")
    return cfg


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2, default=str)[:4000])
