"""Run the experimental (lattice-vs-experiment) and bulk (modulus) suites for MACE-MPA-0 medium.

Bulk's material list is, by construction, the engine-relaxed CONTROL structures of the curated
substitution targets plus the engine-relaxed experimental solids (harness/suites/bulk.py). Only the
'ctrl' kind of the curated substitution suite is therefore run here — the other curated kinds feed
section 6, which is out of scope for this task and stays baseline-only.

Usage:  HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/run_mpa_exp_bulk.py [ctrl|experimental|bulk ...]
"""

import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from harness.config import ACTIVE_MODEL, load_compute_config, settings_tag  # noqa: E402
from harness.curation import resolve_pairs  # noqa: E402
from harness.runner import run_pool  # noqa: E402
from harness.suites import bulk, experimental, substitution  # noqa: E402
from harness import store  # noqa: E402


def curated_ctrl(compute, tag):
    pairs = resolve_pairs()
    done = store.completed_keys(substitution.SUITE)
    jobs = substitution.build_jobs(pairs, ("ctrl",), compute, done=done)
    for j in jobs:
        j["settings"] |= {"workers": compute["workers"], "threads_per_worker": compute["threads_per_worker"]}
    print(f"curated ctrl: {len(jobs)} job(s) to run of {len(pairs)} pairs", flush=True)
    if jobs:
        run_pool(substitution.run_job, jobs, compute["workers"], compute["threads_per_worker"],
                 on_result=substitution._record)


def main():
    steps = sys.argv[1:] or ["ctrl", "experimental", "bulk"]
    compute = load_compute_config()
    tag = settings_tag(compute["device"], compute["dtype"])
    print(f"model={ACTIVE_MODEL} tag={tag} device={compute['device']}/{compute['dtype']} "
          f"workers={compute['workers']}x{compute['threads_per_worker']}", flush=True)
    for step in steps:
        t0 = time.time()
        if step == "ctrl":
            curated_ctrl(compute, tag)
        elif step == "experimental":
            experimental.run(compute=compute)
        elif step == "bulk":
            bulk.run(compute=compute)
        else:
            raise SystemExit(f"unknown step {step!r}")
        print(f"=== {step} finished in {time.time() - t0:.0f} s ===", flush=True)


if __name__ == "__main__":
    main()
