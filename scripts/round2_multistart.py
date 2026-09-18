#!/usr/bin/env python
"""Phase 5 — multi-start structure verification.

Each sampled candidate is relaxed from three starting configurations instead of one:

  A  the WBM initial structure          (already computed: the calibration relaxation itself)
  B  a compressed start                 (the same cell, volume x 0.95)
  C  a symmetry-broken start            (config.PERTURB_RESTART rattle + strain, 1x1x1)

Test 4 measured structure-finding by comparing one relaxation against a known target. A real
candidate has no known target, so the analogue here is agreement BETWEEN starts: if three starts of
the same candidate land in different minima, the single number the product reports is an artefact of
where the relaxation happened to begin. B is the WBM stand-in for test 4's `sub_rescaled` start (a
candidate has no parent structure to predict a volume from, so a fixed compression is used instead).

Results go to results/round2_multistart.json only — this never writes into the results store, so the
calibration tables cannot pick up a second relaxation of the same id. Convergence tolerances and the
energy-plausibility guard are the production ones and are not relaxed for any start.

    python scripts/round2_multistart.py [n]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from monty.json import MontyEncoder

from harness import compare, round2, splits, store
from harness.config import DEFAULT_RELAX, PERTURB_RESTART, RESULTS_DIR, load_compute_config, settings_tag
from harness.jobs import relax_job
from harness.runner import run_pool
from harness.suites import ood

OUT = RESULTS_DIR / "round2_multistart.json"
N_DEFAULT = 1000
SEED = 20260918
COMPRESS = 0.95
ENERGY_SPREAD_MEV = 25.0  # a hull bin's width: the spread at which a call could change bin

GROUPS = {"oxide": ("r1", "oxide"), "halide": ("r1", "halide"),
          "halide_topup": ("r2", "halide_topup"), "sulfide": ("r2", "sulfide"),
          "nitride": ("r2", "nitride"), "carbide": ("r2", "carbide")}
CACHE = {"r1": "oxide_halide_calibration_init_structs.json", "r2": "round2_calibration_init_structs.json"}


def sample(n: int, tag: str) -> pd.DataFrame:
    """Candidates with a usable start-A relaxation, sampled proportionally across every group run
    so far. Fixed seed; the id list is written out with the results."""
    pls = store.load_payloads("ood", tag=tag)
    rows = []
    for name, (which, key) in GROUPS.items():
        ids = (splits.family_calibration_ids(key) if which == "r1" else round2.calibration_ids(key))
        for wid in ids:
            pl = pls.get(f"{wid}@{tag}")
            if pl and "each_pred" in pl:
                rows.append({"group": name, "cache": CACHE[which], "wbm_id": wid,
                             "formula": pl["formula"], "each_true": pl["each_true"],
                             "each_pred": pl["each_pred"], "e_a": pl["e_mace"], "e_dft": pl["e_dft"],
                             "conv_a": pl["converged"], "rej_a": compare.recheck(pl.get("rejection"), pl),
                             "relaxed_a": pl["relaxed"]})
    d = pd.DataFrame(rows).drop_duplicates(subset="wbm_id", keep="first")
    d["bin"] = d.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
    share = d.group.value_counts(normalize=True)
    out = []
    for i, (g, gd) in enumerate(d.groupby("group")):
        out.append(gd.sample(n=min(int(round(share[g] * n)), len(gd)), random_state=SEED + i))
    return pd.concat(out).reset_index(drop=True)


def build(d: pd.DataFrame, compute: dict) -> list[dict]:
    jobs = []
    for cache, gd in d.groupby("cache"):
        starts = ood.load_structures(sorted(gd.wbm_id), cache_file=ood.WBM_DIR / cache)
        for r in gd.itertuples():
            s0 = starts[r.wbm_id]
            b = s0.copy()
            b.scale_lattice(s0.volume * COMPRESS)
            c = compare.perturb(s0, seed=compare.stable_seed(r.wbm_id), supercell=(1, 1, 1),
                                rattle_angstrom=PERTURB_RESTART["rattle_angstrom"],
                                strain=PERTURB_RESTART["strain"])
            for start, s in (("B_compressed", b), ("C_perturbed", c)):
                jobs.append({"job_key": f"{r.wbm_id}:{start}", "wbm_id": r.wbm_id, "start": start,
                             "structure": s, "e_dft": r.e_dft, "each_true": r.each_true,
                             "device": compute["device"], "dtype": compute["dtype"]})
    return jobs


def main(n: int = N_DEFAULT) -> None:
    compute = load_compute_config()
    tag = settings_tag(compute["device"], compute["dtype"])
    d = sample(n, tag)
    print(f"sampled {len(d)} candidates across {d.group.nunique()} groups")
    print(d.group.value_counts().to_string())
    jobs = build(d, compute)
    print(f"{len(jobs)} extra relaxations (2 per candidate)")

    got: dict[str, dict] = {}

    def on_result(job, res):
        if res.get("status") != "ok":
            got[job["job_key"]] = {"status": res["status"], "error": res.get("error")}
            return
        rej = compare.rejection_reason(res, reference_per_atom=job["e_dft"])
        got[job["job_key"]] = {"status": "ok", "converged": res["converged"], "rejection": rej,
                               "energy_per_atom": res["energy_per_atom"], "n_steps": res["n_steps"],
                               "each_pred": ood.predict_e_hull(job["each_true"], res["energy_per_atom"], job["e_dft"]),
                               "relaxed": res["relaxed"], "wall_time_s": res["wall_time_s"]}
        if len(got) % 100 == 0:
            print(f"  {len(got)}/{len(jobs)}", flush=True)

    run_pool(relax_job, jobs, compute["workers"], compute["threads_per_worker"], on_result,
             extra_env={"HARNESS_MODEL": "mace-mpa-0-medium"})

    rows = []
    for r in d.itertuples():
        starts = {"A_wbm_init": {"status": "ok", "converged": bool(r.conv_a),
                                 # a None rejection round-trips through pandas as NaN, and `not NaN`
                                 # is False - which silently excluded start A from every comparison
                                 "rejection": (None if (r.rej_a is None or r.rej_a != r.rej_a) else r.rej_a),
                                 "energy_per_atom": r.e_a, "each_pred": r.each_pred, "relaxed": r.relaxed_a}}
        for s in ("B_compressed", "C_perturbed"):
            starts[s] = got.get(f"{r.wbm_id}:{s}", {"status": "missing"})
        rows.append({"wbm_id": r.wbm_id, "group": r.group, "formula": r.formula, "bin": r.bin,
                     "each_true": r.each_true, **_derive(starts),
                     "each_pred_by_start": {k: v.get("each_pred") for k, v in starts.items()},
                     "starts": {k: {"status": v.get("status"), "converged": v.get("converged"),
                                    "rejection": v.get("rejection"), "each_pred": v.get("each_pred"),
                                    "energy_per_atom": v.get("energy_per_atom"),
                                    "relaxed": v.get("relaxed")} for k, v in starts.items()}})
    OUT.write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine": "mace-mpa-0-medium cpu/float32", "settings_tag": tag,
        "starts": {"A_wbm_init": "WBM initial structure (the calibration relaxation)",
                   "B_compressed": f"same cell, volume x {COMPRESS}",
                   "C_perturbed": f"rattle {PERTURB_RESTART['rattle_angstrom']} A + strain "
                                  f"{PERTURB_RESTART['strain']}, 1x1x1, seed = sha256(wbm_id)"},
        "relax": DEFAULT_RELAX.as_dict(), "seed": SEED, "n_candidates": len(rows),
        "energy_spread_threshold_mev": ENERGY_SPREAD_MEV,
        "disagreement": "structures do not all match, OR predicted hull distances span more than the threshold",
        "rows": rows}, cls=MontyEncoder, indent=1) + "\n")
    print(f"written: {OUT}")


def _derive(starts: dict) -> dict:
    """The comparison, from three already-computed starts. Pure post-processing."""
    usable = {k: v for k, v in starts.items()
              if v.get("status") == "ok" and not (v.get("rejection") or None)}
    preds = [v["each_pred"] for v in usable.values() if v.get("each_pred") is not None]
    spread = float(max(preds) - min(preds)) * 1000 if len(preds) > 1 else None
    names = sorted(usable)
    matched = None
    if len(names) > 1:
        matched = all(compare.relaxed_into_target(usable[names[0]]["relaxed"], usable[k]["relaxed"])
                      for k in names[1:])
    return {"n_usable_starts": len(usable), "n_excluded_starts": len(starts) - len(usable),
            "excluded_reasons": {k: (v.get("rejection") or v.get("status"))
                                 for k, v in starts.items() if k not in usable},
            "structures_match": matched, "energy_spread_mev": spread,
            "energy_disagreement": (spread is not None and spread > ENERGY_SPREAD_MEV),
            "disagreement": bool((matched is False) or (spread is not None and spread > ENERGY_SPREAD_MEV))}


def recompute() -> None:
    """Rebuild every derived field from the saved starts. Used after the start-A exclusion bug;
    no relaxation is re-run, so the underlying numbers are untouched."""
    from monty.json import MontyDecoder

    raw = json.loads(OUT.read_text(), cls=MontyDecoder)
    for r in raw["rows"]:
        s = r["starts"]
        a = s["A_wbm_init"]
        if a.get("rejection") is not None and a["rejection"] != a["rejection"]:
            a["rejection"] = None
        r.update(_derive(s))
        r["each_pred_by_start"] = {k: v.get("each_pred") for k, v in s.items()}
    raw["recomputed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw["recompute_note"] = ("derived fields rebuilt from the saved starts: a None rejection on "
                             "start A round-tripped through pandas as NaN and `not NaN` is False, "
                             "so the calibration relaxation was excluded from every comparison. "
                             "No relaxation was re-run.")
    OUT.write_text(json.dumps(raw, cls=MontyEncoder, indent=1) + "\n")
    print(f"recomputed: {OUT}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "recompute":
        recompute()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else N_DEFAULT)
