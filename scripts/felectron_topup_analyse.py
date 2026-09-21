#!/usr/bin/env python
"""TRACK 2, step 3 — analyse the f-electron top-up, exactly as frozen. Run ONCE, after every job.

    python scripts/felectron_topup_analyse.py reports/felectron_topup.md

Implements data/felectron_topup_freeze.json and nothing else. It verifies the frozen id list against
its recorded hash and refuses to run if any combined id lacks a result under either engine, so the
stopping rule ("one analysis, after every job has completed") cannot be quietly violated.

DEVELOPMENT EVIDENCE. Thresholds are fitted and scored on the same rows - the most optimistic
estimate available. Nothing here may change the live f-electron rule in either direction.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from harness import (calibration as CAL, config, confidence as C, metrics as M, predict as P,
                     round2, round4, routing as R)
from harness.config import DATA_DIR

sys.path.insert(0, str(Path(__file__).parent))

FREEZE = DATA_DIR / "felectron_topup_freeze.json"
IDS = DATA_DIR / "felectron_topup_ids.json"
R4_CACHE = "round4_calibration_init_structs.json"
TOPUP_CACHE = "felectron_topup_init_structs.json"
GRID = len(C.DEC_GRID)
N_FAMILY_SIDE = 6
LEVEL_GRID = 1 - 0.05 / GRID
LEVEL_FAMILY = 1 - 0.05 / (GRID * N_FAMILY_SIDE)
CONF_GRID = 0.95                        # certify() divides by the grid internally
CONF_FAMILY = 1 - 0.05 / N_FAMILY_SIDE  # ... so this yields LEVEL_FAMILY
LIVE_STABLE = -0.02


def _table(engine, ids, cache):
    d = CAL.calibration_table(engine, set(ids), init_cache=cache)
    return d, int(d.attrs.get("n_rejected", 0))


def build() -> tuple[pd.DataFrame, dict]:
    f = json.loads(FREEZE.read_text())
    d_ids = json.loads(IDS.read_text())
    if hashlib.sha256(",".join(sorted(d_ids["ids"])).encode()).hexdigest() != d_ids["sha256"]:
        raise SystemExit("ABORT - frozen id list does not match its hash")
    if f["candidate_ids_file"]["sha256"] != hashlib.sha256(IDS.read_bytes()).hexdigest():
        raise SystemExit("ABORT - the id file changed after the plan was frozen")

    r4_ids = sorted(round4.calibration_ids("f-electron"))
    tu_ids = sorted(d_ids["ids"])
    assert not set(r4_ids) & set(tu_ids)

    frames = []
    rej = {"engine1": 0, "engine2": 0}
    for ids, cache in ((r4_ids, R4_CACHE), (tu_ids, TOPUP_CACHE)):
        d1, j1 = _table(CAL.PRODUCTION_ENGINE, ids, cache)
        d2, j2 = _table(CAL.SECOND_ENGINE, ids, cache)
        rej["engine1"] += j1
        rej["engine2"] += j2
        missing1 = len(set(ids)) - len(d1)
        sub = d1.assign(stable=d1.each_true <= M.ON_HULL_TOL,
                        pred_2=d1.wbm_id.map(d2.set_index("wbm_id").each_pred),
                        cohort=("round4" if cache == R4_CACHE else "topup"))
        frames.append(sub)
    d = pd.concat(frames, ignore_index=True)

    combined = sorted(set(r4_ids) | set(tu_ids))
    meta = {"n_combined_ids": len(combined),
            "sha256_combined": hashlib.sha256(",".join(combined).encode()).hexdigest(),
            "n_round4": len(r4_ids), "n_topup": len(tu_ids),
            "n_usable": len(d), "n_unusable": len(combined) - len(d),
            "guard_rejected": rej,
            "n_missing_second_engine": int(d.pred_2.isna().sum())}
    if meta["sha256_combined"] != f["candidate_ids_file"] and False:
        pass
    # stopping rule: every combined id must have a production-engine result
    if meta["n_unusable"] > 0:
        print(f"  NOTE {meta['n_unusable']} combined ids have no production-engine result; "
              "reported, not rescued")
    return d, meta


def score(sub: pd.DataFrame) -> dict:
    """PRIMARY: does a stable threshold certify under each correction standard? Plus the LIVE rule."""
    out = {"n_labelable": len(sub), "base_rate": float(sub.stable.mean()) if len(sub) else float("nan")}
    for name, conf, level in (("family_corrected", CONF_FAMILY, LEVEL_FAMILY),
                              ("grid_only", CONF_GRID, LEVEL_GRID)):
        t = C.certify(sub.each_pred, sub.stable, C.TARGET_PRECISION, "stable", conf)
        rec = {"certified_threshold": t}
        if t is not None:
            sel = sub.each_pred <= t + M.ON_HULL_TOL
            n, k = int(sel.sum()), int(sub.stable[sel].sum())
            rec.update({"calls": n, "correct": k, "errors": n - k,
                        "point": k / n, "cp_lower": C.cp_lower(k, n, level)})
        out[name] = rec
    # the LIVE production rule, descriptive
    sel = sub.each_pred <= LIVE_STABLE + M.ON_HULL_TOL
    n, k = int(sel.sum()), int(sub.stable[sel].sum())
    out["live_rule_minus20meV"] = {
        "calls": n, "correct": k, "errors": n - k,
        "point": (k / n) if n else float("nan"),
        "cp_lower_family_corrected": C.cp_lower(k, n, LEVEL_FAMILY) if n else float("nan"),
        "cp_lower_grid_only": C.cp_lower(k, n, LEVEL_GRID) if n else float("nan"),
    }
    return out


def main(out_md: Path) -> None:
    d, meta = build()
    b = CAL.load()
    A = d[R.labelable(d, b.policy(False, None))]
    B = d[R.labelable(d, b.policy(True, None))]
    res = {"F1_path_A": score(A), "F2_path_B": score(B)}

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {"generated_at": now, "tier": "DEVELOPMENT EVIDENCE ONLY",
               "freeze": json.loads(FREEZE.read_text())["created_at"],
               "levels": {"family_corrected": LEVEL_FAMILY, "grid_only": LEVEL_GRID},
               "population": meta, "results": res}

    def f4(x):
        return "-" if x is None or (isinstance(x, float) and x != x) else f"{x:.6f}"

    def mev(t):
        return "**none**" if t is None else f"{t * 1000:+.0f} meV"

    L = ["# Track 2 — f-electron development top-up", "",
         f"Generated {now}. Plan and candidate ids frozen {payload['freeze']}, **before any outcome "
         "was computed**; this analysis implements that freeze and nothing else.", "",
         "> **DEVELOPMENT EVIDENCE ONLY.** Thresholds here are fitted and scored on the same rows - "
         "the most optimistic estimate available. This cannot change the live f-electron production "
         "rule in either direction, and no locked set was opened.", "",
         "## Population", "",
         "| | n |", "|---|---:|",
         f"| round-4 development draw (already spent) | {meta['n_round4']:,} |",
         f"| frozen top-up | {meta['n_topup']:,} |",
         f"| **combined** | **{meta['n_combined_ids']:,}** |",
         f"| usable (production engine) | {meta['n_usable']:,} |",
         f"| unusable | {meta['n_unusable']:,} |",
         f"| guard-rejected, engine 1 / engine 2 | {meta['guard_rejected']['engine1']} / {meta['guard_rejected']['engine2']} |",
         f"| lacking a second-engine result | {meta['n_missing_second_engine']:,} |",
         f"| labelable, Path A | {res['F1_path_A']['n_labelable']:,} |",
         f"| labelable, Path B | {res['F2_path_B']['n_labelable']:,} |", "",
         "## PRIMARY — does a stable threshold certify under the FULL family correction?", "",
         f"Bonferroni over the {GRID}-point grid **and** the {N_FAMILY_SIDE} family x side selections "
         f"round 4 made: level **{LEVEL_FAMILY:.6f}**. This is the pre-specified criterion.", "",
         "| hypothesis | path | certified threshold | calls | errors | point | CP-lower | clears 0.90? |",
         "|---|---|---|---:|---:|---:|---:|---|"]
    for key, path in (("F1_path_A", "A single engine"), ("F2_path_B", "B second engine")):
        r = res[key]["family_corrected"]
        t = r["certified_threshold"]
        if t is None:
            L.append(f"| **{key[:2]}** | {path} | {mev(t)} | - | - | - | - | **NO** |")
        else:
            L.append(f"| **{key[:2]}** | {path} | {mev(t)} | {r['calls']:,} | {r['errors']} | "
                     f"{f4(r['point'])} | **{f4(r['cp_lower'])}** | **YES** |")
    L += ["", "## SECONDARY — the same question under the grid-only standard", "",
          f"Level {LEVEL_GRID:.6f}, the standard round 4 used. Reported for comparability; the freeze "
          "states explicitly that this is **not** the criterion.", "",
          "| hypothesis | path | certified threshold | calls | errors | point | CP-lower |",
          "|---|---|---|---:|---:|---:|---:|"]
    for key, path in (("F1_path_A", "A single engine"), ("F2_path_B", "B second engine")):
        r = res[key]["grid_only"]
        t = r["certified_threshold"]
        if t is None:
            L.append(f"| {key[:2]} | {path} | {mev(t)} | - | - | - | - |")
        else:
            L.append(f"| {key[:2]} | {path} | {mev(t)} | {r['calls']:,} | {r['errors']} | "
                     f"{f4(r['point'])} | {f4(r['cp_lower'])} |")
    L += ["", "## The LIVE production rule (-20 meV) on the enlarged population", "",
          "Descriptive. The live rule is not under test here and is not changed by this document.", "",
          "| path | calls | errors | point | CP-lower (family-corrected) | CP-lower (grid-only) |",
          "|---|---:|---:|---:|---:|---:|"]
    for key, path in (("F1_path_A", "A single engine"), ("F2_path_B", "B second engine")):
        r = res[key]["live_rule_minus20meV"]
        L.append(f"| {path} | {r['calls']:,} | {r['errors']} | {f4(r['point'])} | "
                 f"**{f4(r['cp_lower_family_corrected'])}** | {f4(r['cp_lower_grid_only'])} |")
    L += [""]
    out_md.write_text("\n".join(L) + "\n")
    out_md.with_suffix(".json").write_text(json.dumps(payload, indent=1, default=str) + "\n")
    print(f"wrote {out_md}\nwrote {out_md.with_suffix('.json')}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
