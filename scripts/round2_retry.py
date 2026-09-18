#!/usr/bin/env python
"""Phase 6 — retest every failure found in phases 1-5.

The failure set, collected across every group run so far:

  not_converged      the relaxation hit the step cap or the wall-clock limit
  guard_rejected     the energy-plausibility / min-distance guard rejected it (includes the above)
  multistart_disagree  phase 5's starts did not agree (different minima, or predicted hull
                     distances spanning more than the bin width)
  left_its_start     the relaxation did not end in the basin of the structure it was given
                     (compare.relaxed_into_target against the WBM initial structure)

Each is retried with config.FALLBACK_LADDER: FIRE continuing from the rung-1 end point at a 1,500
step cap, then a perturbed restart from the ORIGINAL structure at a 1,000 step cap. **fmax and the
maximum-stress criterion are identical on every rung and the guard is unchanged** — nothing is
loosened to make a failure pass. Where phase 5 ran, the retry is scored as best-of over every
attempt rather than the single ladder run.

Results go to results/round2_retry.json. This never writes into the results store, so no
certification in phases 1-4 can shift underneath itself; whether re-including resolved rows would
move a verdict is computed and reported separately.

    python scripts/round2_retry.py [max_candidates]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd
from monty.json import MontyEncoder

from harness import calibration as CAL, compare, round2, splits, store
from harness.config import LADDER_BUDGET_S, RESULTS_DIR, load_compute_config, settings_tag
from harness.jobs import run_job
from harness.runner import run_pool
from harness.suites import ood

OUT = RESULTS_DIR / "round2_retry.json"
MULTISTART = RESULTS_DIR / "round2_multistart.json"
SPREAD_MEV = 25.0

GROUPS = {"oxide": ("r1", "oxide"), "halide": ("r1", "halide"),
          "halide_topup": ("r2", "halide_topup"), "sulfide": ("r2", "sulfide"),
          "nitride": ("r2", "nitride"), "carbide": ("r2", "carbide")}
CACHE = {"r1": "oxide_halide_calibration_init_structs.json", "r2": "round2_calibration_init_structs.json"}


def failure_set(tag: str) -> pd.DataFrame:
    """Every candidate in a failure class, with the classes it belongs to (a candidate can be in
    several). Counted, never dropped: the totals here are the denominators the report uses."""
    pls = store.load_payloads("ood", tag=tag)
    ms = {}
    if MULTISTART.is_file():
        from monty.json import MontyDecoder
        ms = {r["wbm_id"]: r for r in json.loads(MULTISTART.read_text(), cls=MontyDecoder)["rows"]}

    rows = []
    for name, (which, key) in GROUPS.items():
        ids = splits.family_calibration_ids(key) if which == "r1" else round2.calibration_ids(key)
        d = CAL.calibration_table(CAL.PRODUCTION_ENGINE, set(ids), init_cache=CACHE[which])
        changed = dict(zip(d.wbm_id, d.structure_changed))
        for wid in ids:
            pl = pls.get(f"{wid}@{tag}")
            if not pl or "each_pred" not in pl:
                continue
            rej = compare.recheck(pl.get("rejection"), pl)
            classes = []
            if not pl.get("converged"):
                classes.append("not_converged")
            if rej:
                classes.append("guard_rejected")
            if changed.get(wid) is True:
                classes.append("left_its_start")
            if ms.get(wid, {}).get("disagreement"):
                classes.append("multistart_disagree")
            if classes:
                rows.append({"wbm_id": wid, "group": name, "cache": CACHE[which], "formula": pl["formula"],
                             "each_true": pl["each_true"], "each_pred": pl["each_pred"], "e_dft": pl["e_dft"],
                             "e_a": pl["e_mace"], "rejection": _nn(rej), "converged": bool(pl.get("converged")),
                             "classes": classes, "payload": pl,
                             "ms": ms.get(wid)})
    d = pd.DataFrame(rows).drop_duplicates(subset="wbm_id", keep="first")
    if len(d):
        d["bin"] = d.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
    return d


def build(d: pd.DataFrame, compute: dict) -> list[dict]:
    jobs = []
    for cache, gd in d.groupby("cache"):
        starts = ood.load_structures(sorted(gd.wbm_id), cache_file=ood.WBM_DIR / cache)
        for r in gd.itertuples():
            jobs.append({"job_key": f"{r.wbm_id}:retry", "wbm_id": r.wbm_id,
                         "rung1": r.payload, "original": starts.get(r.wbm_id, r.payload["relaxed"]),
                         "seed": compare.stable_seed(f"{r.wbm_id}:retry"), "budget_s": LADDER_BUDGET_S,
                         # the ladder's continue-rung is only meaningful for a candidate whose rung 1
                         # did NOT give a usable result; for one that converged, it restarts from the
                         # point it converged to and converges again, testing nothing
                         "job_fn": ("ladder" if (bool(_nn(r.rejection)) or not r.converged)
                                    else "perturbed_restart"),
                         "device": compute["device"], "dtype": compute["dtype"]})
    return jobs


def _nn(x):
    """None for a missing rejection, whatever pandas turned it into. A None round-trips through a
    DataFrame as NaN, and bool(NaN) is True - which silently marks every clean row as rejected."""
    return None if x is None or x != x else x


def _usable(att: dict) -> bool:
    return att.get("status") == "ok" and not _nn(att.get("rejection"))


def score(r, retry: dict, init) -> dict:
    """Every attempt for one candidate, and the two verdicts the classes are read from.

    usable_after      is there now a converged, physically plausible result at all
    reproduced        is the lowest-energy usable attempt reached from at least two distinct starts
    stayed_in_start   does any usable attempt end in the basin of the structure it was given
    """
    att = {"A_wbm_init": {"status": "ok", "rejection": _nn(r.rejection), "converged": r.converged,
                          "energy_per_atom": r.e_a, "relaxed": r.payload["relaxed"]}}
    for k, v in ((r.ms or {}).get("starts") or {}).items():
        if k != "A_wbm_init" and v.get("relaxed") is not None:
            att[k] = v
    att[retry.get("rung") or "retry"] = retry
    usable = {k: v for k, v in att.items() if _usable(v)}
    out = {"usable_before": _usable(att["A_wbm_init"]), "usable_after": bool(usable),
           "attempts": {k: {"status": v.get("status"), "converged": v.get("converged"),
                            "rejection": _nn(v.get("rejection")), "rung": v.get("rung"),
                            "energy_per_atom": v.get("energy_per_atom")} for k, v in att.items()}}
    if usable:
        lo = min(usable, key=lambda k: usable[k]["energy_per_atom"])
        ref = usable[lo]
        agree = [k for k, v in usable.items()
                 if k == lo or (abs(v["energy_per_atom"] - ref["energy_per_atom"]) * 1000 <= SPREAD_MEV
                                and compare.relaxed_into_target(v["relaxed"], ref["relaxed"]))]
        out["best_start"] = lo
        out["n_starts_in_best_basin"] = len(agree)
        out["reproduced"] = len(agree) >= 2
        out["stayed_in_start"] = any(compare.relaxed_into_target(v["relaxed"], init) for v in usable.values())
        out["best_energy_per_atom"] = ref["energy_per_atom"]
        out["energy_gain_mev"] = ((r.e_a - ref["energy_per_atom"]) * 1000) if out["usable_before"] else None
    return out


def main(cap: int | None = None) -> None:
    compute = load_compute_config()
    tag = settings_tag(compute["device"], compute["dtype"])
    d = failure_set(tag)
    if cap:
        d = d.head(cap)
    counts = defaultdict(int)
    for cs in d.classes:
        for c in cs:
            counts[c] += 1
    print(f"failure set: {len(d)} candidates; by class {dict(counts)}")
    if not len(d):
        return
    jobs = build(d, compute)
    jobs.sort(key=lambda j: j["job_fn"] != "ladder")  # slowest first: they must not finish last
    got: dict[str, dict] = {}

    def on_result(job, res):
        wid = job["wbm_id"]
        if res.get("status") != "ok":
            got[wid] = {"status": res["status"], "error": res.get("error")}
            return
        rej = compare.rejection_reason(res, reference_per_atom=None)
        got[wid] = {"status": "ok", "converged": res["converged"], "rejection": _nn(rej), "rung": res.get("rung"),
                    "energy_per_atom": res["energy_per_atom"], "relaxed": res["relaxed"],
                    "ladder": res.get("ladder", []), "n_steps": res.get("n_steps")}
        if len(got) % 50 == 0:
            print(f"  {len(got)}/{len(jobs)}", flush=True)

    # ONE pool, dispatching per job on job_fn. Run as two pools the handful of full-ladder jobs
    # block it: each may spend the ladder's whole 5,400 s budget, and six of them on five workers
    # held the 3,038 perturbed restarts for nearly two hours before any of them started.
    n_ladder = sum(j["job_fn"] == "ladder" for j in jobs)
    print(f"  {n_ladder} full-ladder retries (rung 1 gave no usable result), "
          f"{len(jobs) - n_ladder} perturbed restarts, one pool")
    run_pool(run_job, jobs, compute["workers"], compute["threads_per_worker"], on_result,
             extra_env={"HARNESS_MODEL": "mace-mpa-0-medium"})

    inits = {}
    for cache, gd in d.groupby("cache"):
        inits |= ood.load_structures(sorted(gd.wbm_id), cache_file=ood.WBM_DIR / cache)

    rows = []
    for r in d.itertuples():
        retry = got.get(r.wbm_id, {"status": "missing"})
        s = score(r, retry, inits[r.wbm_id])
        rows.append({"wbm_id": r.wbm_id, "group": r.group, "formula": r.formula, "bin": r.bin,
                     "classes": r.classes, "rejection_before": _nn(r.rejection), **s})
    OUT.write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine": "mace-mpa-0-medium cpu/float32", "settings_tag": tag,
        "ladder": ("config.FALLBACK_LADDER — the perturbed restart from the ORIGINAL structure at a "
                   "1,000 step cap for every candidate whose rung 1 already gave a usable result, and the "
                   "full ladder (FIRE/1500 continuing, then the perturbed restart) for the ones it did not"),
        "unchanged": "fmax, max stress and the energy-plausibility guard are identical on every rung",
        "energy_spread_threshold_mev": SPREAD_MEV,
        "n_candidates": len(rows), "by_class": dict(counts), "rows": rows},
        cls=MontyEncoder, indent=1) + "\n")
    print(f"written: {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
