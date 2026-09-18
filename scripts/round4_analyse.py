#!/usr/bin/env python
"""Round-4 analysis: re-certify f-electron, intermetallic and pnictide on the new draws.

    python scripts/round4_analyse.py reports/round4_carried_over.md

Conventions inherited from test 7 and round 2, and never relaxed here:
  * Clopper-Pearson one-sided bounds, Bonferroni-corrected over the threshold grid, never bootstrap;
  * the verdict is read from the pessimistic end of the interval, never the point estimate;
  * guard rejections and non-labelable rows are COUNTED and excluded, never silently dropped;
  * LABELABLE rows are authoritative for certification (user ruling, 2026-09-18); all-usable figures
    are reported alongside as a secondary diagnostic of engine behaviour only.

Round 4 ran ONE engine, so everything here corresponds to the bundle's `without_second_engine` rule
set. The `with_second_engine` path cannot be evaluated from this draw and is reported as such.

Nothing here writes a bundle, changes a threshold, or touches a locked half.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from harness import calibration as CAL, confidence as C, round2, round4, store
from harness.config import REPORTS_DIR

sys.path.insert(0, str(Path(__file__).parent))
from round2_taxonomy_decision import certify_both, labelable_mask, route_metrics  # noqa: E402

R4_CACHE = "round4_calibration_init_structs.json"


def _fmt(x, nd=4):
    if x is None:
        return "-"
    if isinstance(x, float) and (math.isnan(x) or not math.isfinite(x)):
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return f"{x:,}" if isinstance(x, int) else str(x)


def _mev(t):
    return "none" if t is None else f"{t * 1000:+.0f} meV"


def table(fam: str) -> pd.DataFrame:
    """Usable calibration rows for one round-4 family, with the `stable` label attached the way
    round 2 attached it (truth within metrics.ON_HULL_TOL of the hull), and the guard-rejection count
    preserved in .attrs — assign() drops attrs."""
    from harness import metrics as M

    ids = set(round4.calibration_ids(fam))
    d = CAL.calibration_table(CAL.PRODUCTION_ENGINE, ids, init_cache=R4_CACHE)
    n_rej = d.attrs.get("n_rejected", 0)
    if len(d):
        d = d.assign(fam=d.formula.map(C.family), stable=d.each_true <= M.ON_HULL_TOL)
    d.attrs["n_rejected"] = n_rej
    d.attrs["n_requested"] = len(ids)
    return d


def failures(fam: str) -> dict:
    """Queue rows for this family's ids that never finished OK, read straight from the queue so a
    failure cannot be lost between the runner and the analysis. Recorded, never filtered out."""
    from harness import jobqueue

    ids = set(round4.calibration_ids(fam))
    kinds: dict[str, int] = {}
    n = 0
    with jobqueue.connect() as con:
        rows = con.execute(
            "SELECT job_key, status, error FROM queue WHERE suite='ood' AND status != 'done'"
        ).fetchall()
    unrun = 0
    for r in rows:
        wid = str(r["job_key"]).split("@")[0].split(":")[0]
        if wid not in ids:
            continue
        if r["status"] in ("pending", "running"):
            unrun += 1          # not a failure: the queue has not reached it yet
            continue
        n += 1
        k = f"{r['status']}: {str(r['error'] or '').split(':')[0]}".strip().rstrip(":")
        kinds[k] = kinds.get(k, 0) + 1
    return {"n_failed_jobs": n, "by_kind": kinds, "n_not_yet_run": unrun}


def active_thresholds(fam: str) -> dict:
    """What the ACTIVE v1 bundle says for this family today, in both rule sets."""
    b = json.loads(CAL.BUNDLE_FILE.read_text())
    out = {}
    for path in ("with_second_engine", "without_second_engine"):
        t = b["rules"][path]["thresholds"].get(fam, {})
        out[path] = {"stable": t.get("stable"), "unstable": t.get("unstable"), "n": t.get("n")}
    return out


def original_baseline() -> dict:
    """The ORIGINAL 4,000-id calibration set, labelable, per family — the population the active v1
    thresholds were actually fitted on. Needed because the round-4 draw is per-bin proportional to
    each family's own share of the REMAINING pool, while the original split was stratified across all
    families at once. A precision difference between the two could be composition rather than
    validity, and a report that does not show both cannot tell them apart."""
    from harness import compare, metrics as M, splits

    d = CAL.calibration_table(CAL.PRODUCTION_ENGINE, set(splits.calibration_ids()))
    d = d.assign(fam=d.formula.map(C.family), stable=d.each_true <= M.ON_HULL_TOL)
    d["bin"] = d.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
    dl = d[labelable_mask(d)]
    out = {}
    for fam in round4.groups():
        sub = dl[dl.fam == fam]
        out[fam] = {"n": len(sub), "base_rate": float(sub.stable.mean()) if len(sub) else float("nan"),
                    "bin_shares": {k: float(v) for k, v in sub.bin.value_counts(normalize=True).items()}}
    return out


def round4_composition(fam: str) -> dict:
    from harness import compare

    d = table(fam)
    if not len(d):
        return {"n": 0}
    dl = d[labelable_mask(d)].copy()
    dl["bin"] = dl.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
    return {"n": len(dl), "base_rate": float(dl.stable.mean()),
            "bin_shares": {k: float(v) for k, v in dl.bin.value_counts(normalize=True).items()}}


def analyse(fam: str) -> dict:
    d = table(fam)
    n_req, n_rej = d.attrs["n_requested"], d.attrs["n_rejected"]
    if not len(d):
        # routing.labelable cannot be called on an empty frame: its string columns make the `&=`
        # chain a str/bool operation. Report the emptiness rather than crashing or inventing rows.
        return {"family": fam, "n_requested": n_req, "n_rejected_by_guard": n_rej, "n_usable": 0,
                "n_labelable": 0, "n_excluded_not_labelable": 0, "failures": failures(fam),
                "active_v1": active_thresholds(fam), "labelable": {"n": 0}, "all_usable": {"n": 0},
                "carried_over_n": round4.load()["groups"][fam]["carried_over_threshold_n"],
                "calibration_sha256": round4.load()["groups"][fam]["calibration"]["sha256"],
                "today_routing_labelable": {}, "new_routing_labelable": {},
                "note": "NO USABLE ROWS - nothing was certified and nothing should be read from this row"}
    lab = labelable_mask(d)
    dl = d[lab].copy()

    res = {
        "family": fam,
        "n_requested": n_req,
        "n_rejected_by_guard": n_rej,
        "n_usable": len(d),
        "n_labelable": int(lab.sum()),
        "n_excluded_not_labelable": int(len(d) - lab.sum()),
        "failures": failures(fam),
        "active_v1": active_thresholds(fam),
        "labelable": certify_both(dl),
        "all_usable": certify_both(d),
        "carried_over_n": round4.load()["groups"][fam]["carried_over_threshold_n"],
        "calibration_sha256": round4.load()["groups"][fam]["calibration"]["sha256"],
    }
    # What production does TODAY on this same population, using the active without-second-engine rule.
    a = res["active_v1"]["without_second_engine"]
    res["today_routing_labelable"] = route_metrics(dl, a["stable"], a["unstable"]) if len(dl) else {}
    # And what the newly certified thresholds would do on it.
    res["new_routing_labelable"] = {k: res["labelable"][k] for k in
                                    ("n_called_stable", "n_called_unstable", "precision",
                                     "precision_cp_lower", "npv", "npv_cp_lower", "dft_share",
                                     "recall_stable", "stable_lost", "n_truly_stable")
                                    if k in res["labelable"]}
    return res


def report(out_md: Path) -> dict:
    fams = round4.groups()
    results = {f: analyse(f) for f in fams}
    split = round4.load()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    L = [f"# Round 4 — re-measuring the three carried-over families", "",
         f"Generated {now}. Engine MACE-MPA-0 medium, settings_tag "
         f"`{CAL.settings_tag(CAL.PRODUCTION_ENGINE[1], CAL.PRODUCTION_ENGINE[2], model=CAL.PRODUCTION_ENGINE[0])}`. "
         f"Development only: **no locked half was opened, and none was reserved.** Nothing here writes a "
         f"bundle, changes a threshold or promotes anything.", "",
         f"Draw: `data/wbm_split_round4.json`, created {split['created_at']}, seed {split['seed']}, "
         f"all-ids sha256 `{split['sha256_all_calibration_ids']}`. "
         f"{split['excluded_prior_ids']:,} prior ids and {split['locked_test_ids_excluded']:,} locked test ids "
         f"excluded by id; {split['dropped_sharing_locked_test_formula']:,} further candidates dropped for "
         f"sharing a reduced formula with a locked test id.", "",
         "Certification is on **labelable** rows — usable, and surviving the weak-element and "
         "structure-change exclusions. That is the population `calibration.fit()` takes and the "
         "population production labels. All-usable figures follow as a secondary diagnostic only.", "",
         "Round 4 ran one engine, so every figure corresponds to the bundle's "
         "`without_second_engine` rule set. The `with_second_engine` path is **not** evaluated here.", ""]

    # --- population
    L += ["## 1. Population, and everything that was excluded", "",
          "| family | drawn | guard-rejected | usable | not labelable | **labelable** | failed jobs | jobs not yet run |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for f in fams:
        r = results[f]
        L.append(f"| {f} | {r['n_requested']:,} | {r['n_rejected_by_guard']:,} | {r['n_usable']:,} | "
                 f"{r['n_excluded_not_labelable']:,} | **{r['n_labelable']:,}** | "
                 f"{r['failures']['n_failed_jobs']:,} | {r['failures']['n_not_yet_run']:,} |")
    L += ["", "Guard rejections and non-labelable rows are excluded from certification and counted here; "
              "nothing was filtered out silently.", ""]

    # --- headline
    L += ["## 2. Certification on labelable rows — the authoritative result", "",
          "| family | n | base rate | stable t | precision | CP-lower | unstable t | NPV | CP-lower | "
          "recall | stable lost | to DFT | stable-side verdict |",
          "|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---|"]
    for f in fams:
        m = results[f]["labelable"]
        if not m.get("n"):
            L.append(f"| {f} | 0 | - | - | - | - | - | - | - | - | - | - | no labelable rows |")
            continue
        L.append(f"| **{f}** | {m['n']:,} | {_fmt(m['base_rate'],3)} | {_mev(m['stable_threshold'])} | "
                 f"{_fmt(m['precision'])} | {_fmt(m['precision_cp_lower'])} | {_mev(m['unstable_threshold'])} | "
                 f"{_fmt(m['npv'])} | {_fmt(m['npv_cp_lower'])} | {_fmt(m['recall_stable'],3)} | "
                 f"{_fmt(m['stable_lost'],3)} | {_fmt(m['dft_share'],3)} | {m['stable_verdict']} |")
    L += ["", "`CP-lower` is the one-sided Clopper-Pearson bound at 0.95, Bonferroni-corrected over the "
              f"{len(C.DEC_GRID)}-point threshold grid, so picking the best threshold keeps the guarantee. "
              "A threshold is certified only when that bound clears the target (0.90 precision, 0.95 NPV); "
              "the verdict is read from the bound, never the point estimate.", ""]

    # --- diagnosis
    L += ["## 3. Stable-side diagnosis — sample-size limited or precision limited?", "",
          "| family | best t | n selected | point | CP-lower | verdict | more calls needed | structures needed |",
          "|---|---|---:|---:|---:|---|---:|---:|"]
    for f in fams:
        d = table(f)
        if not len(d):
            L.append(f"| {f} | - | 0 | - | - | no usable rows | - | - |")
            continue
        dl = d[labelable_mask(d)]
        if not len(dl):
            L.append(f"| {f} | - | 0 | - | - | no labelable rows | - | - |")
            continue
        dx = round2.diagnose(dl.each_pred, dl.stable, C.TARGET_PRECISION, "stable")
        L.append(f"| {f} | {_mev(dx['best_threshold'])} | {dx['n_selected']:,} | {_fmt(dx['point'])} | "
                 f"{_fmt(dx['cp_lower'])} | {dx['verdict']} | {_fmt(dx['n_selected_needed'])} | "
                 f"{_fmt(dx['n_structures_needed'])} |")
    L += [""]

    # --- vs production today
    L += ["## 4. What this changes against the active bundle", "",
          "The active v1 bundle's thresholds for these three families were fitted on the original "
          "4,000-id calibration set. Both rule sets are shown; round 4 can only speak to the second.", "",
          "| family | v1 with-2nd-engine | v1 without-2nd-engine | v1 n | round-4 n | round-4 stable t | round-4 unstable t |",
          "|---|---|---|---:|---:|---|---|"]
    for f in fams:
        r, m = results[f], results[f]["labelable"]
        w, wo = r["active_v1"]["with_second_engine"], r["active_v1"]["without_second_engine"]
        L.append(f"| {f} | {_mev(w['stable'])} / {_mev(w['unstable'])} | "
                 f"{_mev(wo['stable'])} / {_mev(wo['unstable'])} | {_fmt(wo['n'])} | {m.get('n',0):,} | "
                 f"{_mev(m.get('stable_threshold'))} | {_mev(m.get('unstable_threshold'))} |")
    L += ["", "Read as `stable / unstable`. `none` means the family has no rule on that side, so every "
              "candidate on that side is sent to DFT.", ""]

    L += ["### Routing the same labelable rows two ways", "",
          "Left: the active `without_second_engine` thresholds applied to the round-4 draw — what "
          "production does today on this population. Right: the round-4 certified thresholds. Same rows, "
          "same engine, same labelable filter; only the rule changes.", "",
          "| family | rule | called stable | precision | CP-lower | called unstable | NPV | CP-lower | recall | to DFT |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f in fams:
        r = results[f]
        for label, m in (("v1 (today)", r["today_routing_labelable"]), ("round 4", r["new_routing_labelable"])):
            if not m:
                continue
            L.append(f"| {f} | {label} | {m['n_called_stable']:,} | {_fmt(m['precision'])} | "
                     f"{_fmt(m['precision_cp_lower'])} | {m['n_called_unstable']:,} | {_fmt(m['npv'])} | "
                     f"{_fmt(m['npv_cp_lower'])} | {_fmt(m['recall_stable'],3)} | {_fmt(m['dft_share'],3)} |")
    L += [""]

    # --- comparability
    base = original_baseline()
    bins = ["<0", "0-0.025", "0.025-0.1", "0.1-0.3", ">0.3"]
    raw_bins = ["<0", "0\u20130.025", "0.025\u20130.1", "0.1\u20130.3", ">0.3"]
    L += ["## 4b. Are the two populations comparable? (read before section 4)", "",
          "The active v1 thresholds were fitted on the original 4,000-id calibration set, which was "
          "stratified by hull bin across **all families at once**. The round-4 draw is stratified "
          "per-bin proportional to **each family's own share of the remaining pool**. These are "
          "therefore not the same population, and a precision difference between them can be "
          "composition rather than validity. Both compositions are given so the two can be told apart.", "",
          "| family | set | n | base rate | " + " | ".join(raw_bins) + " |",
          "|---|---|---:|---:|" + "---:|" * len(bins)]
    for f in fams:
        b, r4 = base.get(f, {}), round4_composition(f)
        for label, m in (("original (v1 fit)", b), ("round 4", r4)):
            if not m.get("n"):
                continue
            cells = " | ".join(_fmt(m["bin_shares"].get(rb, 0.0), 3) for rb in raw_bins)
            L.append(f"| {f} | {label} | {m['n']:,} | {_fmt(m['base_rate'],4)} | {cells} |")
    L += ["", "Where the base rates differ materially, treat section 4's left-hand column as "
              "*what the v1 rule does on the round-4 population*, not as a restatement of the v1 "
              "certification. The v1 certification stands on its own population and is not revised here.", ""]

    # --- all-usable diagnostic
    L += ["## 5. All-usable footing — secondary diagnostic only", "",
          "Not a certification basis. Retained because the gap between the two footings is itself a "
          "measurement of how much the structure-change and weak-element exclusions are doing.", "",
          "| family | n | stable t | precision | CP-lower | unstable t | NPV | CP-lower | recall | to DFT |",
          "|---|---:|---|---:|---:|---|---:|---:|---:|---:|"]
    for f in fams:
        m = results[f]["all_usable"]
        if not m.get("n"):
            continue
        L.append(f"| {f} | {m['n']:,} | {_mev(m['stable_threshold'])} | {_fmt(m['precision'])} | "
                 f"{_fmt(m['precision_cp_lower'])} | {_mev(m['unstable_threshold'])} | {_fmt(m['npv'])} | "
                 f"{_fmt(m['npv_cp_lower'])} | {_fmt(m['recall_stable'],3)} | {_fmt(m['dft_share'],3)} |")
    L += [""]

    # --- pool left
    L += ["## 6. What pool is left, and what it could support", "",
          "| family | drawn here | left unspent and still eligible |", "|---|---:|---:|"]
    for f in fams:
        g = split["groups"][f]
        L.append(f"| {f} | {g['calibration']['n']:,} | {g['unspent_after_draw']:,} |")
    L += ["", "Every id drawn here is now spent and is **no longer eligible as independent held-out "
              "data**. The exact id sets and their sha256 hashes are in `data/wbm_split_round4.json`; "
              "per-family hashes are listed in section 7.", ""]

    L += ["## 7. Provenance", "",
          "| family | calibration ids | sha256 |", "|---|---:|---|"]
    for f in fams:
        L.append(f"| {f} | {split['groups'][f]['calibration']['n']:,} | "
                 f"`{split['groups'][f]['calibration']['sha256']}` |")
    L += ["", f"All ids together: `{split['sha256_all_calibration_ids']}`.", ""]

    out_md.write_text("\n".join(L) + "\n")
    out_json = out_md.with_suffix(".json")
    payload = {"generated_at": now, "split": {k: v for k, v in split.items() if k != "groups"},
               "results": results}
    out_json.write_text(json.dumps(payload, indent=1, default=lambda o: None if (
        isinstance(o, float) and not math.isfinite(o)) else str(o)) + "\n")
    print(f"wrote {out_md}\nwrote {out_json}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    report(Path(sys.argv[1]))
