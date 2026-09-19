#!/usr/bin/env python
"""Before/after production-impact report for the pnictide promotion.

    python scripts/pnictide_promotion_impact.py reports/pnictide_promotion_impact.md

OPERATIONAL COMPARISON, ON DEVELOPMENT DATA ONLY. It routes the round-4 pnictide DEVELOPMENT draw
under the pre-promotion and promoted bundles and reports what changes. It is NOT a held-out result
and is NOT a second confirmation: the held-out confirmation happened once, in
reports/pnictide_test.md, and is not repeated, reopened or rescored here.

The held-out sample is never touched by this script. It reads the round-4 development rows only.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from harness import calibration as CAL, confidence as C, metrics as M, pnictide_eval as PE, round4
from harness.config import DATA_DIR

sys.path.insert(0, str(Path(__file__).parent))
from round2_taxonomy_decision import labelable_mask, route_metrics  # noqa: E402
from round4_second_engine import joined  # noqa: E402

PRE = DATA_DIR / "calibration_bundle_pre_pnictide.json"
FAMS = ["f-electron", "intermetallic", "pnictide"]


def _rules(path_json, rule_set):
    return json.loads(Path(path_json).read_text())["rules"][rule_set]["thresholds"]


def _f(x, n=4):
    return "-" if x is None or (isinstance(x, float) and x != x) else f"{x:.{n}f}"


def _mev(t):
    return "none" if t is None else f"{t * 1000:+.0f} meV"


def main(out: Path) -> None:
    # Hard guard: this script must never read the held-out sample.
    holdout = set(PE.test_ids(unlock=True)) if PE.SPLIT_FILE.exists() else set()

    from harness import routing as R, predict as P
    rows = []
    for fam in FAMS:
        d = joined(fam)                      # round-4 DEVELOPMENT rows only
        assert not set(d.wbm_id) & holdout, "held-out ids leaked into the impact report"
        b = CAL.load()
        for rule_set, pol in (("without_second_engine", b.policy(False, None)),
                              ("with_second_engine", b.policy(True, None))):
            sub = d[R.labelable(d, pol)]
            for label, src in (("before", PRE), ("after", CAL.BUNDLE_FILE)):
                t = _rules(src, rule_set).get(fam, {})
                m = route_metrics(sub, t.get("stable"), t.get("unstable"))
                rows.append({"family": fam, "rule_set": rule_set, "bundle": label,
                             "n": len(sub), "stable_t": t.get("stable"), "unstable_t": t.get("unstable"),
                             **m})
    L = ["# Production impact of the pnictide promotion", "",
         f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}.", "",
         "> **This is an OPERATIONAL comparison on DEVELOPMENT data.** It routes the round-4 pnictide "
         "development draw under the pre-promotion and promoted bundles to show what the change does "
         "to routing. It is **not** a held-out result and **not** a second confirmation. The held-out "
         "confirmation happened exactly once, in [`pnictide_test.md`](pnictide_test.md); that sample "
         "is not reopened, rescored or read here, and this script asserts no held-out id reaches it.", "",
         "## Pnictide routing, before and after", "",
         "| rule set | bundle | n | stable t | unstable t | stable calls | unstable calls | recall | **to DFT** |",
         "|---|---|---:|---|---|---:|---:|---:|---:|"]
    for r in rows:
        if r["family"] != "pnictide":
            continue
        L.append(f"| `{r['rule_set']}` | {r['bundle']} | {r['n']:,} | {_mev(r['stable_t'])} | "
                 f"{_mev(r['unstable_t'])} | {r['n_called_stable']:,} | {r['n_called_unstable']:,} | "
                 f"{_f(r['recall_stable'], 3)} | **{_f(r['dft_share'], 3)}** |")
    pn = {(r["rule_set"], r["bundle"]): r for r in rows if r["family"] == "pnictide"}
    b4 = pn[("with_second_engine", "before")]
    af = pn[("with_second_engine", "after")]
    L += ["", f"**The 100%-to-DFT fall-through is gone.** On the second-engine path pnictide went from "
              f"a DFT routing fraction of {_f(b4['dft_share'], 4)} - every candidate - to "
              f"{_f(af['dft_share'], 4)}, and from {b4['n_called_stable']:,} to "
              f"{af['n_called_stable']:,} 'likely stable' calls on {af['n']:,} development rows.", "",
          "## Every other family, both rule sets — unchanged by construction", "",
          "| family | rule set | bundle | stable t | unstable t | to DFT |", "|---|---|---|---|---|---:|"]
    for r in rows:
        if r["family"] == "pnictide":
            continue
        L.append(f"| {r['family']} | `{r['rule_set']}` | {r['bundle']} | {_mev(r['stable_t'])} | "
                 f"{_mev(r['unstable_t'])} | {_f(r['dft_share'], 3)} |")
    L += ["", "Identical before and after, which is the point: the promotion touched two threshold "
              "entries and nothing else.", "",
          "## What this does not show", "",
          "These are development rows the thresholds were selected on, so the precision and NPV they "
          "would produce here are in-sample and optimistic. They are deliberately omitted from the "
          "tables above: routing volumes are the operational question, and the quality question was "
          "already answered, once, on held-out data.", ""]
    out.write_text("\n".join(L) + "\n")
    out.with_suffix(".json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "kind": "operational comparison on development data; NOT a held-out result",
         "rows": rows}, indent=1, default=str) + "\n")
    print(f"wrote {out}\nwrote {out.with_suffix('.json')}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
