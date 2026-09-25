"""Protostructure labels for the normalised OQMD structures. Runs in an EPHEMERAL env, never .venv:

    ./uvw run --python 3.14 --no-project \
        --with "matbench-discovery @ git+https://github.com/janosh/matbench-discovery@71633e8bdfdfd41d56d64b1d777e5686d9eda3ec" \
        python scripts/oqmd_protostructure_worker.py <structures.jsonl.gz> <out_dir> [workers]

Standalone on purpose (no harness import): the ephemeral env has its own pymatgen. Work is split into
chunks of CHUNK structures; each finished chunk is written atomically to <out_dir>/labels_<k>.json and
skipped on a rerun, so the step is checkpointed. Between chunks the power source is checked and the
process exits 75 on battery, exactly as the runner pauses; the campaign driver retries later.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import subprocess
import sys
from multiprocessing import get_context
from pathlib import Path

CHUNK = 5000


def on_battery() -> bool:
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    m = re.search(r"Now drawing from '([^']+)'", out)
    return bool(m and m.group(1).lower().startswith("battery"))


def label(rec: dict) -> tuple[int, str | None, str | None]:
    from matbench_discovery.structure.prototype import get_protostructure_label
    from pymatgen.core import Lattice, Structure

    try:
        s = Structure(Lattice(rec["lattice"]), rec["species"], rec["frac"])
        return rec["id"], get_protostructure_label(s), None
    except Exception as exc:  # noqa: BLE001 - recorded per structure, counted in the report
        return rec["id"], None, f"{type(exc).__name__}: {exc}"[:200]


def main() -> int:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else max(1, (os.cpu_count() or 2) - 2)
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(src, "rt") as fh:
        recs = [json.loads(line) for line in fh]
    chunks = [recs[i:i + CHUNK] for i in range(0, len(recs), CHUNK)]
    todo = [k for k in range(len(chunks)) if not (out / f"labels_{k:05d}.json").is_file()]
    print(f"{len(recs):,} structures in {len(chunks)} chunks; {len(todo)} to do on {workers} workers", flush=True)
    with get_context("spawn").Pool(workers) as pool:
        for k in todo:
            if on_battery():
                print("on battery: pausing (exit 75); the driver resumes on AC", flush=True)
                return 75
            res = pool.map(label, chunks[k], chunksize=50)
            tmp = out / f"labels_{k:05d}.tmp"
            tmp.write_text(json.dumps([{"id": i, "label": lab, "error": err} for i, lab, err in res]))
            tmp.replace(out / f"labels_{k:05d}.json")
            print(f"chunk {k + 1}/{len(chunks)} done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
