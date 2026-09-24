#!/usr/bin/env python
"""Resumable driver for the 2026-09-24 campaign. Safe to re-invoke at any time.

    .venv/bin/python scripts/campaign_20260924.py            # advance as far as possible, then exit
    .venv/bin/python scripts/campaign_20260924.py --status   # print the state file, change nothing

Invoked by the launchd agent com.materials-harness.campaign at load and every 30 minutes
(scripts/campaign_20260924_agent.sh). Each invocation:

  * exits at once if another driver holds logs/campaign_20260924.lock, if any runner holds a queue
    lock, or if every step is finished;
  * walks STEPS in order. A finished step is skipped; a step whose dependency failed is skipped and
    recorded; a step that raises Wait stops this invocation (it is retried on the next one);
  * runs engine queues ONE AFTER ANOTHER, never concurrently, through run_unattended.sh --foreground
    with the step's HARNESS_MODEL and no --stop-at. Before each launch it refuses unless no runner
    holds the lock AND every pending/running job in the queue carries the tag it is about to run.

State: data/campaign_20260924_state.json (started_at / finished_at / outcome per step).
Heavy non-runner steps pause on battery by raising Wait, exactly as the runner pauses.
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "campaign_20260924_state.json"
LOCK = ROOT / "logs" / "campaign_20260924.lock"
PY = str(ROOT / ".venv" / "bin" / "python")
PROD, SECOND = "mace-mpa-0-medium", "mace-mp-0-medium"
TAGS = {PROD: "c2480e74", SECOND: "207ccc81"}
MAX_ATTEMPTS = 3
# A step whose script still does not exist after this is skipped (with its dependents), so a session
# that dies mid-build cannot leave the nightly agent unloaded forever.
BUILD_DEADLINE = "2026-09-27T12:00:00+00:00"


class Wait(Exception):
    """Not finished and not failed: stop this invocation, retry on the next."""


class Refuse(Wait):
    """A safety check failed. Logged loudly; retried later, never forced."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{now()}] {msg}", flush=True)


# --- state ------------------------------------------------------------------------------------------

def load_state() -> dict:
    if STATE.is_file():
        return json.loads(STATE.read_text())
    return {"campaign": "2026-09-24", "created_at": now(), "steps": {}, "finished_at": None}


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1) + "\n")
    tmp.replace(STATE)


# --- guards -----------------------------------------------------------------------------------------

def queue_db() -> Path:
    return ROOT / "results" / "queue.sqlite"


def runner_alive() -> int | None:
    """PID of any live runner on ANY queue in results/ (one runner at a time, full stop)."""
    sys.path.insert(0, str(ROOT))
    from harness.orchestrator import runner_pid

    for q in sorted((ROOT / "results").glob("queue*.sqlite")):
        pid = runner_pid(q)
        if pid:
            return pid
    return None


def pending_tags() -> dict[str, int]:
    import sqlite3

    con = sqlite3.connect(queue_db(), timeout=60)
    try:
        rows = con.execute("SELECT substr(job_key, instr(job_key,'@')+1), COUNT(*) FROM queue "
                           "WHERE status IN ('pending','running') GROUP BY 1").fetchall()
    finally:
        con.close()
    return {t: n for t, n in rows}


def on_ac() -> bool:
    sys.path.insert(0, str(ROOT))
    from harness import power

    return power.power_source() != "battery"


def require_ac() -> None:
    if not on_ac():
        raise Wait("on battery: heavy steps pause until AC returns")


# --- step kinds -------------------------------------------------------------------------------------

def sh(args: list[str], model: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("HARNESS_MODEL", None)
    if model:
        env["HARNESS_MODEL"] = model
    log(f"$ {'HARNESS_MODEL=' + model + ' ' if model else ''}{' '.join(args)}")
    r = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
    out = (r.stdout + r.stderr)[-4000:]
    print(out, flush=True)
    if check and r.returncode:
        raise RuntimeError(f"exit {r.returncode}: {out[-800:]}")
    return r


def script(name: str, *args: str, model: str | None = PROD) -> str:
    path = ROOT / "scripts" / name
    if not path.is_file():
        if now() > BUILD_DEADLINE:
            return f"skipped: scripts/{name} was not written before {BUILD_DEADLINE}"
        raise Wait(f"scripts/{name} not written yet")
    r = sh([PY, str(path), *args], model=model)
    return (r.stdout.strip().splitlines() or ["ok"])[-1][:300]


def run_engine(model: str) -> str:
    """Drain every job tagged for `model`, in the foreground, then verify nothing of it is pending."""
    tag = TAGS[model]
    pid = runner_alive()
    if pid:
        raise Wait(f"a runner is alive (pid {pid}); one runner at a time")
    tags = pending_tags()
    if not tags.get(tag):
        return f"ok: nothing pending under {tag}"
    foreign = {t: n for t, n in tags.items() if t != tag}
    if foreign:
        raise Refuse(f"REFUSED to start {model}: the queue holds jobs under other tags {foreign}. "
                     "A runner executes ONE tag; drain or remove those first.")
    if not on_ac():
        raise Wait("on battery: not starting a runner (it would only pause)")
    log(f"launching runner {model} ({tag}) over {tags[tag]} pending jobs, no --stop-at")
    r = sh(["/bin/bash", "run_unattended.sh", "--foreground", "full"], model=model, check=False)
    if r.returncode == 3:
        raise Wait("runner did not start: another runner holds the lock")
    left = pending_tags().get(tag, 0)
    if left:
        raise Wait(f"runner exited (code {r.returncode}) with {left} jobs still pending under {tag}")
    return f"ok: drained {tags[tag]} jobs under {tag} (runner exit {r.returncode})"


def git_commit(paths: list[str], message: str) -> str:
    existing = [p for p in paths if (ROOT / p).exists() or sh(["git", "ls-files", "--error-unmatch", p],
                                                             check=False).returncode == 0]
    if existing:
        sh(["git", "add", "--", *existing])
    if not existing or sh(["git", "diff", "--cached", "--quiet", "--", *existing], check=False).returncode == 0:
        return "nothing to commit"
    msg = message + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
    sh(["git", "commit", "-q", "-m", msg, "--", *existing])     # only these paths, never the rest of the index
    return "committed " + sh(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()


# --- the campaign -----------------------------------------------------------------------------------

@dataclass
class Step:
    name: str
    phase: str
    fn: callable
    deps: list[str] = field(default_factory=list)


def fe_open() -> str:
    """Open once (writes the log, queues engine 1). If the log exists, only (re)queue engine 1."""
    if (ROOT / "data" / "felectron_eval_log.json").is_file():
        script("felectron_eval.py", "enqueue", model=PROD)
        return "ok: already opened; engine-1 jobs (re)queued idempotently"
    script("felectron_eval.py", "open", model=PROD)
    return git_commit(["data/felectron_eval_log.json"],
                      "Open the f-electron held-out sample once (authorised by Isac Smith, 2026-09-24)\n\n"
                      "Writes data/felectron_eval_log.json and queues the production engine over the 4,500 "
                      "pre-registered ids. Nothing is scored.")


def fe_score() -> str:
    if (ROOT / "reports" / "felectron_test.json").is_file():
        return "ok: already scored (scored once)"
    return script("felectron_eval.py", "score", model=PROD)


def fe_evidence_commit() -> str:
    sh([PY, "scripts/freeze_spec_v2.py"], model=PROD)
    verdict = json.loads((ROOT / "reports" / "felectron_test.json").read_text())["overall"]
    return git_commit(["reports/felectron_test.md", "reports/felectron_test.json", "data/felectron_eval_log.json",
                       "data/locked_sets_registry.json"],
                      f"Evidence: f-electron held-out evaluation scored once - overall {verdict}\n\n"
                      "EA1/EA2/EB1/EB2 at the fixed live thresholds -20/+10 meV, CP-lower at 0.9875. "
                      "Registry regenerated: f-electron OPENED ONCE. No bundle change.")


def oqmd(sub: str, model: str | None = PROD, heavy: bool = False):
    def f() -> str:
        if heavy:
            require_ac()
        return script("oqmd_campaign.py", sub, model=model)
    f.__name__ = f"oqmd_{sub}"
    return f


def finish() -> str:
    sh(["/bin/bash", "scripts/campaign_20260924_agent.sh", "restore-nightly"])
    return "ok: nightly agent restored (campaign agent unloads itself next)"


STEPS = [
    # Phase 1 - the f-electron held-out evaluation. Nothing later may share its runner.
    Step("fe_open", "1", fe_open),
    Step("fe_run_production", "1", lambda: run_engine(PROD), ["fe_open"]),
    Step("fe_enqueue_second", "1", lambda: script("felectron_eval.py", "enqueue", model=SECOND),
         ["fe_run_production"]),
    Step("fe_run_second", "1", lambda: run_engine(SECOND), ["fe_enqueue_second"]),
    Step("fe_score", "1", fe_score, ["fe_run_second"]),
    Step("fe_evidence_commit", "1", fe_evidence_commit, ["fe_score"]),
    # Phase 2 - OQMD acquisition, overlap (stage 1) and hull disagreement (stage 2)
    Step("oqmd_download", "2", oqmd("download", model=None)),
    Step("oqmd_normalise", "2", oqmd("normalise", heavy=True), ["oqmd_download"]),
    Step("oqmd_protostructures", "2", oqmd("protostructures", model=None, heavy=True), ["oqmd_normalise"]),
    Step("oqmd_overlap", "2", oqmd("overlap"), ["oqmd_protostructures"]),
    Step("oqmd_hull_disagreement", "2", oqmd("hull-disagreement"), ["oqmd_overlap"]),
    # Phase 3 - lock a held-out half, pilot, frozen plan, development runs, report
    Step("oqmd_lock", "3", oqmd("lock"), ["oqmd_hull_disagreement"]),
    Step("oqmd_pilot_enqueue", "3", oqmd("pilot-enqueue"), ["oqmd_lock"]),
    Step("oqmd_pilot_run", "3", lambda: run_engine(PROD), ["oqmd_pilot_enqueue"]),
    Step("oqmd_plan", "3", oqmd("plan"), ["oqmd_pilot_run"]),
    Step("oqmd_dev_enqueue_production", "3", oqmd("dev-enqueue"), ["oqmd_plan"]),
    Step("oqmd_dev_run_production", "3", lambda: run_engine(PROD), ["oqmd_dev_enqueue_production"]),
    Step("oqmd_dev_enqueue_second", "3", oqmd("dev-enqueue", model=SECOND), ["oqmd_dev_run_production"]),
    Step("oqmd_dev_run_second", "3", lambda: run_engine(SECOND), ["oqmd_dev_enqueue_second"]),
    Step("oqmd_dev_report", "3", oqmd("dev-report"), ["oqmd_dev_run_second"]),
    # Finishing (mechanical part; prose, export and push are done by a session)
    Step("finish", "finish", finish),
]


def advance(steps=STEPS) -> str:
    st = load_state()
    if st.get("finished_at"):
        return "campaign finished; nothing to do"
    pid = runner_alive()
    if pid:
        return f"a runner is alive (pid {pid}); exiting"
    for s in steps:
        rec = st["steps"].setdefault(s.name, {"phase": s.phase, "attempts": 0})
        if rec.get("finished_at"):
            continue
        bad = [d for d in s.deps if st["steps"].get(d, {}).get("outcome", "").startswith(("FAILED", "skipped"))]
        if bad:
            rec.update(outcome=f"skipped: dependency {bad} did not complete", finished_at=now())
            save_state(st)
            continue
        if s.name == "finish" and any(not st["steps"].get(o.name, {}).get("finished_at") for o in steps[:-1]):
            return "finish waits for every other step"
        rec.setdefault("started_at", now())
        save_state(st)
        try:
            out = s.fn()
        except Wait as w:
            rec["last_wait"] = f"{now()} {w}"
            save_state(st)
            log(f"{s.name}: waiting - {w}")
            return f"waiting at {s.name}: {w}"
        except Exception as e:  # noqa: BLE001
            rec["attempts"] += 1
            rec["last_error"] = f"{now()} {type(e).__name__}: {e}"[:2000]
            log(f"{s.name}: error (attempt {rec['attempts']}):\n{traceback.format_exc()}")
            if rec["attempts"] >= MAX_ATTEMPTS:
                rec.update(outcome=f"FAILED after {rec['attempts']} attempts: {e}"[:1000], finished_at=now())
                save_state(st)
                continue
            save_state(st)
            return f"error at {s.name}; retried next invocation"
        rec.update(outcome=str(out) or "ok", finished_at=now())
        save_state(st)
        log(f"{s.name}: {rec['outcome']}")
    st["finished_at"] = now()
    save_state(st)
    return "campaign finished"


def main() -> int:
    if "--status" in sys.argv:
        print(json.dumps(load_state(), indent=1))
        return 0
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another driver invocation is running; exiting")
        return 0
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    log(f"driver pid {os.getpid()}: {advance()}")
    if load_state().get("finished_at"):
        sh(["/bin/bash", "scripts/campaign_20260924_agent.sh", "unload-campaign"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
