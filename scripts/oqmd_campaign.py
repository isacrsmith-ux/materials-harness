#!/usr/bin/env python
"""OQMD external validation, stages 1-2 and the development tier (campaign 2026-09-24).

    python scripts/oqmd_campaign.py download            # pinned v1.8 dump, resumable, size + md5 + sha256
    python scripts/oqmd_campaign.py normalise           # dump -> cache/external/oqmd/*.parquet (one pass)
    python scripts/oqmd_campaign.py protostructures     # parallel, checkpointed, pauses on battery
    python scripts/oqmd_campaign.py overlap             # stage 1  -> reports/oqmd_overlap.{md,json}
    python scripts/oqmd_campaign.py hull-disagreement   # stage 2  -> reports/oqmd_hull_disagreement.{md,json}
    python scripts/oqmd_campaign.py lock                # lock the held-out half BEFORE any ML job
    python scripts/oqmd_campaign.py pilot-enqueue       # 500 development structures, production engine
    python scripts/oqmd_campaign.py plan                # size the draw from the pilot; frozen + committed
    python scripts/oqmd_campaign.py dev-enqueue         # the current HARNESS_MODEL over the frozen dev ids
    python scripts/oqmd_campaign.py dev-report          # reports/oqmd_development.{md,json}

Every raw OQMD byte stays under cache/external/oqmd/ (gitignored). Only ids, hashes, provenance and
aggregates are committed. The OQMD held-out half is locked here and nothing in this campaign opens it.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OQMD_DIR = ROOT / "cache" / "external" / "oqmd"
DUMP_URL = "https://static.oqmd.org/static/downloads/qmdb__v1_8__022026.sql.gz"
DUMP = OQMD_DIR / "qmdb__v1_8__022026.sql.gz"
# read from the storage bucket's own response headers on 2026-09-24T19:40:05Z
DUMP_SIZE = 21034479961
DUMP_MD5_B64 = "qQUGz1mu2YaF/LID0z0+bQ=="
DOWNLOAD_RECORD = OQMD_DIR / "download.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lock(name: str):
    OQMD_DIR.mkdir(parents=True, exist_ok=True)
    fh = open(OQMD_DIR / f"{name}.lock", "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # the driver treats exit code 75 (EX_TEMPFAIL) as 'not finished, retry later'
        print(f"{name} is already running in another process")
        sys.exit(75)
    return fh


def download() -> None:
    lk = _lock("download")  # noqa: F841 - held for the life of the process
    if DOWNLOAD_RECORD.is_file():
        rec = json.loads(DOWNLOAD_RECORD.read_text())
        if DUMP.is_file() and DUMP.stat().st_size == DUMP_SIZE:
            print(f"ok: v1.8 dump present and verified at {rec['verified_at']}, sha256 {rec['sha256']}")
            return
    while not (DUMP.is_file() and DUMP.stat().st_size >= DUMP_SIZE):
        have = DUMP.stat().st_size if DUMP.is_file() else 0
        print(f"[{now()}] downloading from byte {have:,} of {DUMP_SIZE:,}", flush=True)
        r = subprocess.run(["curl", "-sS", "-L", "-C", "-", "--retry", "20", "--retry-delay", "30",
                            "--retry-all-errors", "--speed-time", "120", "--speed-limit", "10000",
                            "-o", str(DUMP), DUMP_URL])
        if r.returncode and DUMP.is_file() and DUMP.stat().st_size == have:
            raise SystemExit(f"curl exit {r.returncode} with no progress; retry later")
    if DUMP.stat().st_size != DUMP_SIZE:
        raise SystemExit(f"ABORT - size {DUMP.stat().st_size} != published {DUMP_SIZE}; delete and retry")
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(DUMP, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            md5.update(chunk)
            sha.update(chunk)
    got_md5 = base64.b64encode(md5.digest()).decode()
    if got_md5 != DUMP_MD5_B64:
        DUMP.rename(DUMP.with_suffix(".corrupt"))
        raise SystemExit(f"ABORT - md5 {got_md5} != published {DUMP_MD5_B64}; moved aside, will re-download")
    DOWNLOAD_RECORD.write_text(json.dumps({
        "source": "OQMD v1.8 bulk MySQL dump, https://oqmd.org/download/",
        "url": DUMP_URL, "version": "v1.8 (database updated February 2026)",
        "size_bytes": DUMP_SIZE, "md5_base64_published": DUMP_MD5_B64,
        "sha256": sha.hexdigest(), "verified_at": now(),
        "licence": "CC BY 4.0, as stated on oqmd.org (home, documentation and download pages) read 2026-09-24T19:39:41Z",
    }, indent=1) + "\n")
    print(f"ok: downloaded and verified, sha256 {sha.hexdigest()}")


if __name__ == "__main__":
    cmds = {"download": download}
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] not in cmds:
        print(f"{sys.argv[1]}: not implemented yet (implemented: {', '.join(cmds)})")
        sys.exit(75)
    cmds[sys.argv[1]]()
