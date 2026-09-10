"""Worker-side job functions (top-level so the spawn-based pool can pickle them)."""

from __future__ import annotations

from harness.config import DEFAULT_RELAX


def relax_job(job: dict) -> dict:
    """Relax job['structure'] (cell + positions) on job['device'] / job['dtype']."""
    from harness import engine

    res = engine.relax(job["structure"], DEFAULT_RELAX, job["device"], job["dtype"],
                       relax_cell=job.get("relax_cell", True))
    return {
        "relaxed": res.structure,
        "energy_per_atom": res.energy_per_atom,
        "converged": res.converged,
        "n_steps": res.n_steps,
        "fmax_final": res.fmax_final,
        "max_stress_gpa": res.max_stress_gpa,
        "min_distance_ratio": res.min_distance_ratio,
        "wall_time_s": res.wall_time_s,
        "metadata": res.metadata,
    }


def eos_job(job: dict) -> dict:
    """Energy-volume points: isotropically scale job['structure'] by job['volume_factors'] and relax
    shape + positions at constant volume at each point. Failed points are reported, not raised."""
    from harness import engine

    s0 = job["structure"]
    points = []
    for f in job["volume_factors"]:
        s = s0.copy()
        s.scale_lattice(s0.volume * f)
        try:
            r = engine.relax(s, DEFAULT_RELAX, job["device"], job["dtype"], relax_cell=True, constant_volume=True)
            points.append({"factor": float(f), "volume_per_atom": r.structure.volume / len(r.structure),
                           "energy_per_atom": r.energy_per_atom, "converged": r.converged, "n_steps": r.n_steps,
                           "min_distance_ratio": r.min_distance_ratio, "wall_time_s": r.wall_time_s})
        except engine.RelaxTimeout as exc:
            points.append({"factor": float(f), "error": f"timeout: {exc}"})
    return {"points": points,
            "metadata": engine.engine_metadata(job["device"], job["dtype"], DEFAULT_RELAX)
            | {"calculation": "EOS", "constant_volume": True, "volume_factors": [float(x) for x in job["volume_factors"]]}}


def static_job(job: dict) -> dict:
    """Single-point energy of job['structure'] (no relaxation)."""
    from harness import engine

    sp = engine.single_point(job["structure"], job["device"], job["dtype"])
    return {"energy_per_atom": sp["energy_per_atom"],
            "metadata": engine.engine_metadata(job["device"], job["dtype"]) | {"calculation": "single_point"}}
