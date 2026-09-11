"""Worker-side job functions (top-level so the spawn-based pool can pickle them)."""

from __future__ import annotations

from harness.config import DEFAULT_RELAX


def _relax_out(res) -> dict:
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


def relax_job(job: dict) -> dict:
    """Relax job['structure'] (cell + positions) on job['device'] / job['dtype']."""
    from harness import engine

    res = engine.relax(job["structure"], DEFAULT_RELAX, job["device"], job["dtype"],
                       relax_cell=job.get("relax_cell", True))
    return _relax_out(res)


def ladder_job(job: dict) -> dict:
    """Fallback rungs (config.FALLBACK_LADDER) for a relaxation whose rung 1 (DEFAULT_RELAX) did not
    give a usable result. job['rung1'] is that stored rung-1 result (relaxed structure, energy, ...);
    job['original'] the original starting structure; job['seed'] fixes the perturbed restart.

    Stops at the first rung whose result is converged (which includes the physical-sanity guard).
    If no rung converges, returns the last rung's (unconverged) result, or rung 1 unchanged if every
    fallback rung timed out. Every rung is recorded in 'ladder', so nothing is hidden.
    """
    from harness import compare, engine
    from harness.config import FALLBACK_LADDER, PERTURB_RESTART, settings_tag

    rung1 = job["rung1"]
    history, last = [], None
    for name, settings, start_mode in FALLBACK_LADDER:
        start = (last["relaxed"] if last else rung1["relaxed"]) if start_mode == "continue" else \
            compare.perturb(job["original"], seed=job["seed"], **PERTURB_RESTART)
        step = {"rung": name, "optimizer": settings.optimizer, "max_steps": settings.max_steps, "start": start_mode,
                "settings_tag": settings_tag(job["device"], job["dtype"], settings)}
        try:
            res = engine.relax(start, settings, job["device"], job["dtype"])
        except engine.RelaxTimeout as exc:
            history.append({**step, "error": f"RelaxTimeout: {exc}"})
            continue
        history.append({**step, "converged": res.converged, "n_steps": res.n_steps, "fmax_final": res.fmax_final,
                        "max_stress_gpa": res.max_stress_gpa, "min_distance_ratio": res.min_distance_ratio,
                        "energy_per_atom": res.energy_per_atom, "wall_time_s": res.wall_time_s})
        last = _relax_out(res) | {"rung": name}
        if res.converged:
            return last | {"ladder": history}
    if last is None:
        keep = ("relaxed", "energy_per_atom", "converged", "n_steps", "fmax_final", "max_stress_gpa",
                "min_distance_ratio", "wall_time_s", "metadata")
        return {k: rung1.get(k) for k in keep} | {"rung": None, "ladder": history}
    return last | {"rung": None, "ladder": history}


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
    import time

    from harness import engine

    t0 = time.perf_counter()
    sp = engine.single_point(job["structure"], job["device"], job["dtype"])
    return {"energy_per_atom": sp["energy_per_atom"], "wall_time_s": time.perf_counter() - t0,
            "metadata": engine.engine_metadata(job["device"], job["dtype"]) | {"calculation": "single_point"}}


JOB_FUNCTIONS = {"relax": relax_job, "static": static_job, "ladder": ladder_job}


def run_job(job: dict) -> dict:
    """Dispatch on job['job_fn'] (default 'relax'); used by the unattended runner for mixed queues."""
    return JOB_FUNCTIONS[job.get("job_fn", "relax")](job)
