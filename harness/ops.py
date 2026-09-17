"""Operational safety: the morning standup, git checkpoints, and verified backups.

Orchestration only — nothing here changes what is computed or how it is scored. Databases are opened
read-only everywhere in this module; the only SQLite writes are the online-backup copies inside a backup.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import plistlib
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import zlib
from contextlib import closing
from datetime import datetime
from pathlib import Path

from harness import ROOT
from harness.config import DB_PATH, LOG_DIR, QUEUE_DB, load_unattended_config

MAX_LINES = 40
HEADLINE = ("wbm_f1_opt", "wbm_precision_opt", "wbm_npv_opt", "wbm_daf_0", "routing_share sent to DFT")
STANDUP_STATE = LOG_DIR / "standup.json"
MAX_GIT_FILE_BYTES = 5_000_000  # checkpoint leaves bigger files out of git (README: big artifacts go to releases)
# Untracked files are only picked up under these; changes to already-tracked files are picked up anywhere.
CHECKPOINT_PATHS = (".github/", "config/", "data/", "docs/", "harness/", "reports/", "scripts/", "tests/",
                    "results/schema.sql", "results/summary.json")
BACKUP_DIRS = ("results", "reports", "config")  # not models/ or cache/: both re-downloadable
ARCHIVE_RE = re.compile(r"^harness-(\d{8}-\d{6})\.tar\.gz$")
MANIFEST = "SHA256SUMS"


def _ro(path) -> sqlite3.Connection:
    """Read-only connection: checking a database must never be able to change it."""
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=60)


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _bytes(n: float) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB"


def _local(iso: str | None) -> str:
    return datetime.fromisoformat(iso).astimezone().strftime("%a %d %b %H:%M") if iso else "?"


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    tmp.replace(p)


def latest_scorecard(root=ROOT) -> tuple[Path | None, dict]:
    """The most recently written scorecard.json (reports/ or a run directory under it)."""
    reports = Path(root) / "reports"
    cards = [p for p in [reports / "scorecard.json", *reports.glob("*/scorecard.json")] if p.is_file()]
    if not cards:
        return None, {}
    p = max(cards, key=lambda c: c.stat().st_mtime)
    return p, json.loads(p.read_text())


# --- standup -------------------------------------------------------------------------------------

def standup(queue_db=QUEUE_DB, verify: bool = False, db_path=DB_PATH) -> tuple[str, bool]:
    """Everything for the morning on one screen (at most MAX_LINES lines). Returns (text, databases_ok)."""
    from harness import jobqueue
    from harness import orchestrator as orch
    from harness.config import RESULTS_DIR, load_compute_config

    cfg = load_unattended_config()
    threshold = float(cfg["standup_metric_threshold"])
    prev = _read_json(STANDUP_STATE)
    since = prev.get("at", "")
    now = jobqueue.now()
    lines = [f"STANDUP {_local(now)}  ("
             + (f"changes since last standup {_local(since)})" if since else "first standup: 'since' covers all history)")]
    qdb = Path(queue_db)
    if not qdb.is_file():
        lines.append(f"Queue    none at {qdb.name} — build one with: python -m harness prepare")
    else:
        pid, st = orch.runner_pid(qdb), orch.read_state(qdb)
        if pid:
            pause = (f"PAUSED on battery since {_local(st.get('pause_since'))}" if st.get("status") == "paused"
                     else "not paused")
            lines.append(f"Runner   RUNNING pid {pid} | mode {st.get('mode')} | {pause} | run {st.get('run_id')}"
                         + (f" | draining: {st['draining']}" if st.get("draining") else ""))
        else:
            last = jobqueue.last_runs(qdb, 1)
            lines.append("Runner   not running (so not paused)"
                         + (f" | last run {last[0]['run_id']} ({last[0]['mode']}): {last[0]['status']}" if last else ""))
        c = jobqueue.counts(qdb)
        tot = {s: sum(v.get(s, 0) for v in c.values()) for s in jobqueue.STATUSES}
        total = sum(tot.values())
        lines.append(f"Progress {tot['done']}/{total} done ({tot['done'] / max(1, total):.1%}) | {tot['running']} running | "
                     f"{tot['pending']} pending | {tot['failed']} failed | {tot['timeout']} timed out")
        if tot["pending"] + tot["running"]:
            compute = load_compute_config()
            wp, wf = orch.layout("polite", compute, cfg)[0], orch.layout("full", compute, cfg)[0]
            lines.append(f"ETA      polite {orch._fmt_dur(orch.eta_seconds(qdb, wp))} ({wp} workers) | "
                         f"full {orch._fmt_dur(orch.eta_seconds(qdb, wf))} ({wf} workers)"
                         + (" | paused: the clock restarts on AC" if pid and st.get("status") == "paused" else ""))
        else:
            lines.append("ETA      nothing left in the queue")
        lines += _since(qdb, since)
        lines += _failures(jobqueue.failures_by_type(qdb))

    used = sum(p.stat().st_size for p in RESULTS_DIR.rglob("*") if p.is_file())
    du = shutil.disk_usage(ROOT)
    lines.append(f"Disk     results/ {_bytes(used)} | volume {_bytes(du.free)} free of {_bytes(du.total)}")

    card_path, card = latest_scorecard()
    cur = {k: v for k, v in card.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    old = prev.get("metrics") or {}
    moved = [(k, old[k], v) for k, v in cur.items() if k in old and abs(v - old[k]) > threshold * max(abs(old[k]), 1e-12)]
    if not card_path:
        lines.append("Metrics  no scorecard yet (python -m harness report)")
    elif not old:
        lines.append(f"Metrics  baseline recorded from {card_path.relative_to(ROOT)}; "
                     f"moves > {threshold:.0%} are listed from the next standup")
    else:
        changed = " | SETTINGS TAG CHANGED" if prev.get("settings_tag") != card.get("settings_tag") else ""
        lines.append(f"Metrics  {len(moved)} moved > {threshold:.0%} since last standup "
                     f"({card_path.relative_to(ROOT)}, settings {card.get('settings_tag')}{changed})")
        lines += [f"  {k[:44]:<44} {a:.4g} -> {b:.4g}" + (f" ({(b - a) / abs(a):+.0%})" if a else "") for k, a, b in moved[:8]]
        if len(moved) > 8:
            lines.append(f"  ... {len(moved) - 8} more")

    ok = True
    if verify:
        vlines, ok = verify_databases(qdb, db_path)
        lines += vlines
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + ["(cut to 40 lines — python -m harness status has the full queue view)"]
    _write_json(STANDUP_STATE, {"at": now, "settings_tag": card.get("settings_tag", prev.get("settings_tag")),
                                "metrics": cur or old})
    return "\n".join(lines), ok


def _since(qdb: Path, since: str) -> list[str]:
    from harness import jobqueue

    with jobqueue.connect(qdb) as con:
        rows = con.execute("SELECT suite, SUM(status = 'done') AS done, SUM(status != 'done') AS bad FROM queue "
                           "WHERE finished_at > ? AND status IN ('done', 'failed', 'timeout') "
                           "GROUP BY suite ORDER BY done DESC", (since,)).fetchall()
        runs = con.execute("SELECT run_id, mode, status, n_done, n_failed FROM runs WHERE finished_at > ? "
                           "ORDER BY finished_at DESC", (since,)).fetchall()
    out = [f"Since    +{sum(r['done'] for r in rows)} done, +{sum(r['bad'] for r in rows)} failed or timed out"]
    out += [f"  {r['suite']:<20} +{r['done']} done, +{r['bad']} failed" for r in rows[:5]]
    if len(rows) > 5:
        out.append(f"  ... {len(rows) - 5} more suites")
    out += [f"  run {r['run_id']} ({r['mode']}) ended {r['status']}: {r['n_done'] or 0} done, {r['n_failed'] or 0} failed"
            for r in runs[:3]]
    return out


def _failures(fails: list[dict]) -> list[str]:
    if not fails:
        return ["Failures none"]
    out = [f"Failures {sum(f['n'] for f in fails)} jobs in {len(fails)} error types (one example each)"]
    for f in fails[:6]:
        example = " ".join((f["example"] or "").split())[:80]
        out.append(f"  {(f['error_type'] or 'unknown')[:26]:<26} {f['n']:>5}  e.g. {example}")
    if len(fails) > 6:
        out.append(f"  ... {len(fails) - 6} more types: python -m harness status")
    return out


def verify_databases(queue_db=QUEUE_DB, db_path=DB_PATH) -> tuple[list[str], bool]:
    """Both databases open and pass PRAGMA quick_check, and the queue reconciles with the results store:
    every 'done' queue row has an 'ok' job row. Result rows without a job row are counted too — the
    recorders write results before the job row, so they mean an interrupted write that a re-run replaces."""
    lines, ok = ["Verify"], True
    for p in (Path(db_path), Path(queue_db)):
        try:
            with closing(_ro(p)) as con:
                check = [r[0] for r in con.execute("PRAGMA quick_check")]
        except sqlite3.DatabaseError as exc:
            check = [f"cannot open: {exc}"]
        ok &= check == ["ok"]
        lines.append(f"  {p.name:<22} " + ("opens cleanly, quick_check ok" if check == ["ok"] else "FAILED: " + "; ".join(check[:2])))
    if not ok:
        return lines, False
    with closing(_ro(db_path)) as con:
        con.execute("ATTACH DATABASE ? AS q", (Path(queue_db).resolve().as_uri() + "?mode=ro",))
        done, missing, not_ok = con.execute(
            "SELECT COUNT(*), SUM(j.status IS NULL), SUM(j.status != 'ok') FROM q.queue qq "
            "LEFT JOIN jobs j ON j.suite = qq.suite AND j.job_key = qq.job_key WHERE qq.status = 'done'").fetchone()
        n_results, orphans = con.execute(
            "SELECT COUNT(*), SUM(NOT EXISTS (SELECT 1 FROM jobs j WHERE j.suite = r.suite AND j.job_key = r.job_key)) "
            "FROM results r").fetchone()
    missing, not_ok, orphans = missing or 0, not_ok or 0, orphans or 0
    ok = not (missing or not_ok)
    lines.append(f"  queue 'done' {done}: {done - missing - not_ok} have an ok job row, {missing} missing, {not_ok} not ok"
                 + ("" if ok else "  <- MISMATCH: those jobs are marked done without a result and will not re-run"))
    lines.append(f"  results table {n_results} rows: {orphans} without a job row"
                 + (" (interrupted writes; re-running those jobs replaces them)" if orphans else ""))
    return lines, ok


# --- checkpoint ----------------------------------------------------------------------------------

def _git(root, *args, check: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=check, **kw)


def _grouped(con, sql: str) -> dict:
    out: dict = {}
    for suite, status, n in con.execute(sql):
        out.setdefault(suite, {})[status] = n
    return out


def write_db_summaries(root=ROOT, db_path=DB_PATH, queue_db=QUEUE_DB) -> dict:
    """results/schema.sql and results/summary.json: the part of the ~1 GB databases that belongs in git.
    No timestamps or absolute paths, so an unchanged database gives an unchanged file."""
    root = Path(root)
    schema, summary = [], {}
    for name, p in (("results", Path(db_path)), ("queue", Path(queue_db))):
        if not p.is_file():
            continue
        with closing(_ro(p)) as con:
            schema += [f"-- {name} database: results/{p.name}"] + [r[0] + ";" for r in con.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite%' ORDER BY type DESC, name")]
            if name == "results":
                summary["results_store"] = {"jobs": _grouped(con, "SELECT suite, status, COUNT(*) FROM jobs GROUP BY 1, 2"),
                                            "result_rows": dict(con.execute("SELECT suite, COUNT(*) FROM results GROUP BY 1"))}
            else:
                run = con.execute("SELECT run_id, mode, status, n_done, n_failed FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
                summary["queue"] = {"file": p.name, "jobs": _grouped(con, "SELECT suite, status, COUNT(*) FROM queue GROUP BY 1, 2"),
                                    "last_run": dict(zip(("run_id", "mode", "status", "n_done", "n_failed"), run)) if run else None}
    card_path, card = latest_scorecard(root)
    if card_path:
        summary["scorecard"] = {"file": card_path.relative_to(root).as_posix(),
                                **{k: card.get(k) for k in ("model", "settings_tag", *HEADLINE)}}
    (root / "results").mkdir(exist_ok=True)
    (root / "results" / "schema.sql").write_text("\n".join(schema) + "\n")
    (root / "results" / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


def _changed_paths(root: Path) -> list[str]:
    """Tracked changes anywhere, plus untracked files under CHECKPOINT_PATHS (gitignore applies)."""
    fields = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout.split("\0")
    out, i = [], 0
    while i < len(fields):
        f = fields[i]
        i += 1
        if len(f) < 4:
            continue
        xy, path = f[:2], f[3:]
        if xy[0] in "RC":
            i += 1  # the rename's original path follows as its own field
        if xy == "??" and not path.startswith(CHECKPOINT_PATHS):
            continue
        out.append(path)
    return out


def checkpoint(message: str, root=ROOT, db_path=DB_PATH, queue_db=QUEUE_DB, dry_run: bool = False) -> str:
    """Commit code, reports and the database schema/summaries with run metadata in the message.
    Files over MAX_GIT_FILE_BYTES stay out of git. Never pushes."""
    from harness.config import MODEL, load_compute_config, settings_tag

    root = Path(root)
    s = write_db_summaries(root, db_path, queue_db)
    changed = _changed_paths(root)
    big = [p for p in changed if (root / p).is_file() and (root / p).stat().st_size > MAX_GIT_FILE_BYTES]
    paths = [p for p in changed if p not in big]

    q = s.get("queue") or {}
    run = q.get("last_run") or {}
    qtot: dict = {}
    for by_status in (q.get("jobs") or {}).values():
        for k, n in by_status.items():
            qtot[k] = qtot.get(k, 0) + n
    store_ok = sum(v.get("ok", 0) for v in (s.get("results_store") or {}).get("jobs", {}).values())
    card = s.get("scorecard") or {}
    compute = load_compute_config()
    metrics = ", ".join(f"{k} {card[k]:.3f}" for k in HEADLINE if isinstance(card.get(k), (int, float)))
    body = [f"run {run.get('run_id', 'none')} ({run.get('mode')}, {run.get('status')}) | model {MODEL['name']} | "
            f"settings {settings_tag(compute['device'], compute['dtype'])} ({compute['device']}/{compute['dtype']})",
            f"jobs: queue {q.get('file')} {qtot.get('done', 0)} done, {qtot.get('failed', 0) + qtot.get('timeout', 0)} failed, "
            f"{qtot.get('pending', 0) + qtot.get('running', 0)} pending of {sum(qtot.values())}; results store {store_ok} ok",
            f"metrics: {metrics} ({card['file']}: {card.get('model')}, settings {card.get('settings_tag')})" if card
            else "metrics: no scorecard"]
    if big:
        body.append(f"left out of git (> {MAX_GIT_FILE_BYTES // 1_000_000} MB): " + ", ".join(big))
    msg = message.strip() + "\n\n" + "\n".join(body) + "\n"

    if dry_run:
        return f"DRY RUN: would commit {len(paths)} file(s)\n" + "".join(f"  {p}\n" for p in paths) + "\n" + msg
    if paths:
        _git(root, "add", "-A", "--", *paths)
    if _git(root, "diff", "--cached", "--quiet", check=False).returncode == 0:
        return "nothing to commit" + ("\n" + body[-1] if big else "")
    res = _git(root, "commit", "-q", "-F", "-", check=False, input=msg)
    if res.returncode:
        raise RuntimeError(f"git commit failed (blocked by the pre-commit hook?):\n{(res.stdout + res.stderr)[-2000:]}")
    return f"committed {_git(root, 'rev-parse', '--short', 'HEAD').stdout.strip()} ({len(paths)} files)\n\n{msg}"


# --- backups -------------------------------------------------------------------------------------

def backup_dest(root=ROOT) -> Path:
    """HARNESS_BACKUP_DIR (environment, then .env); default <project>/backups (gitignored)."""
    from dotenv import dotenv_values

    root = Path(root)
    raw = (os.environ.get("HARNESS_BACKUP_DIR") or dotenv_values(root / ".env").get("HARNESS_BACKUP_DIR") or "").strip()
    if not raw:
        return root / "backups"
    p = Path(raw).expanduser()
    return p if p.is_absolute() else root / p


def _diskutil(dev: str) -> dict:
    return plistlib.loads(subprocess.run(["diskutil", "info", "-plist", dev], capture_output=True, check=True, timeout=30).stdout)


def physical_disk(path) -> str | None:
    """Whole physical disk behind a path (e.g. 'disk0'), resolving APFS containers; None if it cannot be told."""
    try:
        dev = subprocess.run(["df", str(path)], capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()[-1].split()[0]
        info = _diskutil(dev)
        if info.get("APFSPhysicalStores"):
            info = _diskutil(info["APFSPhysicalStores"][0]["APFSPhysicalStore"])
        return info.get("ParentWholeDisk")
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
        return None


def same_disk_warning(root, dest) -> str | None:
    a, b = physical_disk(root), physical_disk(dest)
    if a and a == b:
        return (f"WARNING: the backup destination {dest} is on the SAME PHYSICAL DISK ({a}) as the project. A disk "
                "failure, a spilled coffee or a stolen laptop takes both. Set HARNESS_BACKUP_DIR in .env to an external "
                "drive (a cloud-synced folder only protects you once it has finished uploading).")
    if not (a and b):
        return f"note: could not tell which physical disk {dest} is on — check it is not this Mac's internal disk."
    return None


def _backup_files(root: Path) -> list[Path]:
    return [p.relative_to(root) for d in BACKUP_DIRS for p in sorted((root / d).rglob("*"))
            if p.is_file() and not p.is_symlink() and p.name != ".DS_Store" and not p.name.startswith(".fuse_hidden")
            and not p.name.endswith(("-wal", "-shm", "-journal"))]


def _sqlite_copy(src: Path, dst: Path) -> list[str]:
    """Consistent copy through SQLite's online backup (safe while a runner writes), then quick_check it."""
    with closing(_ro(src)) as s, closing(sqlite3.connect(dst)) as d:
        s.backup(d)
        check = [r[0] for r in d.execute("PRAGMA quick_check")]
    return [] if check == ["ok"] else [f"{src.name}: quick_check {'; '.join(check[:3])}"]


def backup(root=ROOT, dest=None, daily: int = 7, weekly: int = 4) -> dict:
    """Timestamped, compressed, checksummed snapshot of results/ (every database), reports/ and config/.
    Verified after writing; old archives are pruned only when this one is sound."""
    root = Path(root)
    dest = Path(dest) if dest else backup_dest(root)
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest / ".backup.lock", "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f"another backup is already writing to {dest}") from None
        for stale in dest.glob("harness-*.partial"):  # left by a killed backup; we hold the lock
            stale.unlink()
        archive = dest / f"harness-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
        problems: list[str] = []
        with tempfile.TemporaryDirectory(prefix="harness-backup-") as tmp:
            stage = Path(tmp)
            files = _backup_files(root)
            for rel in files:
                (stage / rel).parent.mkdir(parents=True, exist_ok=True)
                if rel.suffix == ".sqlite":
                    problems += _sqlite_copy(root / rel, stage / rel)
                else:
                    shutil.copy2(root / rel, stage / rel)
            sums = {rel.as_posix(): _sha256(stage / rel) for rel in files}
            (stage / MANIFEST).write_text("".join(f"{h}  {p}\n" for p, h in sorted(sums.items())))
            part = archive.with_name(archive.name + ".partial")
            with tarfile.open(part, "w:gz", compresslevel=6) as tar:
                tar.add(stage / MANIFEST, arcname=MANIFEST)
                for p in sorted(sums):
                    tar.add(stage / p, arcname=p)
            os.replace(part, archive)
        digest = _sha256(archive)
        (dest / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
        problems += verify_archive(archive)
        pruned = [] if problems else prune(dest, daily, weekly)
    return {"archive": archive, "bytes": archive.stat().st_size, "files": len(sums), "sha256": digest,
            "results_db_sha256": sums.get("results/results.sqlite"), "problems": problems, "pruned": pruned,
            "warning": same_disk_warning(root, dest)}


def verify_archive(archive) -> list[str]:
    """Re-read an archive end to end: its .sha256 sidecar, and every member against the SHA256SUMS inside it."""
    archive = Path(archive)
    problems = []
    side = archive.with_name(archive.name + ".sha256")
    if side.is_file() and side.read_text().split()[0] != _sha256(archive):
        problems.append("archive sha256 differs from its .sha256 file")
    expected, seen = None, {}
    try:
        with tarfile.open(archive, "r:gz") as tar:
            for m in tar:
                if not m.isfile():
                    continue
                fh = tar.extractfile(m)
                if m.name == MANIFEST:
                    expected = {p: h for h, p in (line.split("  ", 1) for line in fh.read().decode().splitlines())}
                    continue
                h = hashlib.sha256()
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
                seen[m.name] = h.hexdigest()
    except (tarfile.TarError, OSError, EOFError, zlib.error, ValueError) as exc:
        return problems + [f"archive unreadable: {type(exc).__name__}: {exc}"]
    if expected is None:
        return problems + [f"archive has no {MANIFEST} manifest"]
    bad = sorted(p for p in expected.keys() | seen.keys() if expected.get(p) != seen.get(p))
    if bad:
        problems.append(f"{len(bad)} file(s) missing or not matching the manifest: {', '.join(bad[:3])}")
    return problems


def prune(dest, daily: int = 7, weekly: int = 4) -> list[str]:
    """Keep the newest archive of each of the `daily` most recent days and of the `weekly` most recent ISO
    weeks; delete every other harness-*.tar.gz (and its .sha256). Other files are never touched."""
    dest = Path(dest)
    archives = sorted(((m.group(1), p) for p in dest.iterdir() if (m := ARCHIVE_RE.match(p.name))), reverse=True)
    keep, days, weeks = set(), [], []
    for stamp, p in archives:
        t = datetime.strptime(stamp, "%Y%m%d-%H%M%S")
        day, week = t.date(), t.isocalendar()[:2]
        if day not in days and len(days) < daily:
            days.append(day)
            keep.add(p)
        if week not in weeks and len(weeks) < weekly:
            weeks.append(week)
            keep.add(p)
    removed = []
    for _, p in archives:
        if p not in keep:
            p.unlink()
            p.with_name(p.name + ".sha256").unlink(missing_ok=True)
            removed.append(p.name)
    return removed


def backup_summary(info: dict) -> str:
    lines = [f"backup   {info['archive']} ({_bytes(info['bytes'])}, {info['files']} files) — "
             + ("verified: archive checksum and every file re-read against the manifest" if not info["problems"]
                else "PROBLEMS: " + "; ".join(info["problems"])),
             f"results.sqlite sha256 {info['results_db_sha256']}",
             "pruned   " + (", ".join(info["pruned"]) if info["pruned"] else
                            "nothing" if not info["problems"] else "nothing (skipped because of the problems above)")]
    if info["warning"]:
        lines.append(info["warning"])
    return "\n".join(lines)
