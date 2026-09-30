"""Diagnosis of the Stage 1 gate-2 failure (reports/aerospace_stage1.json). The gate's verdict stands; this
only asks whether the deviation comes from the ZBL correction or from the engine's own run-to-run noise.

Re-runs the Phase 0 near-equilibrium cases twice in one process, engine alone and engine + correction,
and compares every energy with the Phase 0 reference and with each other. If "engine alone vs reference"
is as large as "corrected vs reference", the 1 meV tolerance sat below the engine's noise floor.

    HARNESS_MODEL=mace-mpa-0-medium .venv/bin/python scripts/aerospace_stage1_gate2_diagnosis.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import aerospace_phase0 as P0  # noqa: E402
from aerospace_stage1 import leaves  # noqa: E402

from harness import config, zbl  # noqa: E402
from harness.engine import get_calculator  # noqa: E402

OUT = config.ROOT / "reports" / "aerospace_stage1_gate2_diagnosis.json"


def run(calc) -> dict:
    P0.CALC = calc
    return dict(leaves({"al_defects": P0.al_defects(), "ag_oxygen": P0.ag_oxygen()}))


def main() -> None:
    cc = config.load_compute_config()
    engine = get_calculator(cc["device"], cc["dtype"])
    ref = json.loads((config.ROOT / "reports" / "aerospace_phase0" / "mace-mpa-0-medium.json").read_text())
    r = dict(leaves({k: ref[k] for k in ("al_defects", "ag_oxygen")}))
    plain = run(engine)
    corr = run(zbl.corrected(engine, ["Al", "Ag", "O"]))
    rows = {k: {"ref": r[k], "plain_minus_ref": plain[k] - r[k], "corrected_minus_ref": corr[k] - r[k],
                "corrected_minus_plain": corr[k] - plain[k]} for k in r}

    def stat(col):
        v = [abs(x[col]) for x in rows.values()]
        return {"max_abs_eV": max(v), "n_over_1meV": sum(x > 1e-3 for x in v), "n": len(v)}

    out = {"dtype": cc["dtype"], "summary": {c: stat(c) for c in ("plain_minus_ref", "corrected_minus_ref",
                                                                   "corrected_minus_plain")}, "values": rows}
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
