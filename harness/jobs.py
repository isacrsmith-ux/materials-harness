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


def static_job(job: dict) -> dict:
    """Single-point energy of job['structure'] (no relaxation)."""
    from harness import engine

    sp = engine.single_point(job["structure"], job["device"], job["dtype"])
    return {"energy_per_atom": sp["energy_per_atom"],
            "metadata": engine.engine_metadata(job["device"], job["dtype"]) | {"calculation": "single_point"}}
