#!/usr/bin/env python
"""TRACK 2, step 2 — queue the frozen f-electron top-up ids. One engine per invocation.

    HARNESS_MODEL=mace-mpa-0-medium python scripts/felectron_topup_run.py
    HARNESS_MODEL=mace-mp-0-medium  python scripts/felectron_topup_run.py

A runner executes ONE settings tag, so each engine is queued and drained separately. Queueing both
and draining once is what made all 7,000 second-engine jobs fail during the pnictide evaluation.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from harness import config, jobqueue, store
from harness.config import DATA_DIR, QUEUE_DB, load_compute_config

sys.path.insert(0, str(Path(__file__).parent))

INIT_CACHE = "felectron_topup_init_structs.json"
CSE_CACHE = "felectron_topup_cse.json"
IDS = DATA_DIR / "felectron_topup_ids.json"
FREEZE = DATA_DIR / "felectron_topup_freeze.json"


def main() -> None:
    from harness import orchestrator as O
    from harness import pnictide_eval as PE, round4
    from harness.suites import ood

    d = json.loads(IDS.read_text())
    ids = d["ids"]
    if hashlib.sha256(",".join(sorted(ids)).encode()).hexdigest() != d["sha256"]:
        raise SystemExit("ABORT - the frozen id list does not match its recorded hash")
    f = json.loads(FREEZE.read_text())
    if f["candidate_ids_file"]["sha256"] != hashlib.sha256(IDS.read_bytes()).hexdigest():
        raise SystemExit("ABORT - the id file changed since the plan was frozen")

    # nothing locked or held-out may enter the queue
    forbidden = round4._locked_test_ids() | PE.excluded_ids()
    leaked = set(ids) & forbidden
    if leaked:
        raise SystemExit(f"ABORT - {len(leaked)} top-up ids are locked or held-out ids")

    compute = load_compute_config()
    tag = config.settings_tag(compute["device"], compute["dtype"])
    config.model_path(config.ACTIVE_MODEL)
    print(f"engine {config.MODEL['name']} ({config.ACTIVE_MODEL}) settings_tag {tag} - checkpoint verified")
    print(f"frozen id list verified: n={len(ids)}, sha256 {d['sha256']}")

    jobs = O.build_wbm_calibration_jobs(compute, ids=ids,
                                        init_cache=ood.WBM_DIR / INIT_CACHE,
                                        cse_cache=ood.WBM_DIR / CSE_CACHE, strict=True)
    done = store.completed_keys("ood", retry_failed=True)
    print("enqueue:", jobqueue.enqueue(jobs, QUEUE_DB, done_keys=done), f"({len(jobs)} jobs)")
    with jobqueue.connect() as con:
        tags = {r["tag"]: r["n"] for r in con.execute(
            "SELECT substr(job_key, instr(job_key,'@')+1) tag, COUNT(*) n FROM queue "
            "WHERE suite='ood' AND status IN ('pending','running') GROUP BY tag")}
    if len(tags) > 1:
        print(f"  NOTE: pending jobs under {len(tags)} settings tags: {tags}")
        print("  A runner executes ONE tag. Drain this engine before queueing the other.")
    _warn_if_a_runner_holds_the_lock_for_another_engine(tag)


def _warn_if_a_runner_holds_the_lock_for_another_engine(job_tag: str) -> None:
    """One runner per queue, and it executes ONE settings tag.

    This has now cost two separate incidents: during the pnictide evaluation a runner started under
    the production engine refused 7,000 second-engine jobs with SettingsMismatch, and during the
    f-electron top-up a still-alive production-engine runner held the fcntl lock so the second-engine
    runner never started at all - `run_unattended.sh` reports that only as a missing log file. Both
    are the same root cause seen from different angles, so the check looks at the RUNNER rather than
    at the queue.
    """
    from harness.orchestrator import paths as _paths

    state = _paths(QUEUE_DB)["state"]
    if not state.is_file():
        return
    try:
        st = json.loads(state.read_text())
    except Exception:
        return
    if st.get("status") not in ("running", "paused"):
        return
    running_tag = (st.get("settings_tag") or st.get("tag") or "")
    print(f"\n  WARNING: a runner is already active (run {st.get('run_id')}, pid {st.get('pid')}).")
    if running_tag and running_tag != job_tag:
        print(f"  It executes settings tag {running_tag}, but these jobs are tagged {job_tag}.")
    print("  Only one runner may hold the queue, and it runs one engine. Stop it first:")
    print("      python -m harness stop")
    print("  then start a runner under THIS engine's HARNESS_MODEL. Starting one now would either")
    print("  fail to acquire the lock silently, or fail every job here with SettingsMismatch.")


if __name__ == "__main__":
    main()
