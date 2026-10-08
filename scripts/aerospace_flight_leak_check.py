"""Invariant: no committed file may contain a row-level flight value (open decision 5, "commit flight values?", is not taken).

Reads the gitignored transcriptions (so this script itself holds no values), builds the distinctive printed strings, and searches the
tracked files of the aerospace track. A string counts as distinctive if, without its sign, it has a decimal point and at least 5 characters, or
an exponent form, and occurs in at most two transcribed rows. Short numbers (0.32, 500) are not searched: they are everywhere, and the power of
this check is therefore for long strings (masses to 5 decimals, fluences, 4-digit thicknesses), not for every value. Hits are
printed for review; the exit status is 1 only for hits outside ALLOWED.

    .venv/bin/python scripts/aerospace_flight_leak_check.py
"""

from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "external" / "aerospace"
# Only files that could carry flight values. The Phase 0/2, Stage 1 and vacancy reports hold engine and DFT numbers, which coincide with
# printed two-decimal values by chance, so they are not searched.
TRACK = ("reports/aerospace_phase1_ingest.json", "reports/aerospace_durability_development", "reports/aerospace_cu_fluence", "reports/aerospace_lit_summary.md",
         "reports/aerospace_tphase_stretch.md", "reports/drafts", "docs/methodology/data_provenance.md", "docs/methodology/maptis_query_plan.md",
         "NOTICE", "HANDOFF.md", "scripts/aerospace_ingest.py", "scripts/aerospace_cu_fluence.py", "scripts/aerospace_phase2_report.py",
         "scripts/aerospace_flight_leak_check.py", "tests/test_aerospace")
# Pre-existing (Phase 1, commit 77f8bc4): print-form examples quoted in scripts/aerospace_ingest.py. Not new.
# "0.051" is a tolerance constant in the Morton check (print precision of a stated mg value), not a flight value.
ALLOWED = {("scripts/aerospace_ingest.py", "3.6 x 10^-26"), ("scripts/aerospace_ingest.py", "1/10^3"), ("scripts/aerospace_ingest.py", "9/2 x 10^5"),
           ("scripts/aerospace_ingest.py", "0.051")}


def tokens() -> collections.Counter:
    c: collections.Counter = collections.Counter()
    t1 = json.loads((CACHE / "transcription.json").read_text())
    for r in t1["rows"]:
        for k in ("accommodation_printed", "reactivity_printed", "dm_mg", "dm_per_area_mg_cm2"):
            if k in r:
                c[str(r[k]).strip()] += 1
    for r in json.loads((CACHE / "transcription_v2.json").read_text())["rows"]:
        for s in [r["value_as_printed"], r.get("fluence_as_printed") or ""] + [str(v) for k, v in r["extra"].items() if k in ("pre_g", "post_g", "appendix_dm_g", "pre", "post")]:
            c[s.strip()] += 1
    return c


def main() -> int:
    c = tokens()
    core = lambda s: s.lstrip("+-")
    cand = sorted({core(s) for s, n in c.items() if n <= 2 and (("." in core(s) and len(core(s)) >= 5) or "10^" in s) and re.search(r"\d", s)})
    files = [f for f in subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split() if f.startswith(TRACK)]
    hits = []
    for f in files:
        if f.endswith((".pdf", ".parquet")):
            continue
        txt = (ROOT / f).read_text(errors="ignore")
        hits += [(f, s) for s in cand if re.search(r"(?<![\d.A-Za-z])" + re.escape(s) + r"(?![\dA-Za-z])", txt)]
    new = [h for h in hits if h not in ALLOWED]
    print(f"{len(cand)} distinctive strings, {len(files)} tracked files searched, {len(hits)} hits, {len(new)} not allowed")
    for f, s in new:
        print("  HIT", f, repr(s))
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
