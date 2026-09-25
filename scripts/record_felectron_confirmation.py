#!/usr/bin/env python
"""Record the f-electron held-out CONFIRMATION in the production bundle. Once. NOT RUN BY THE CAMPAIGN.

    python scripts/record_felectron_confirmation.py            # requires an explicit decision to run

The pre-registered branch `all_four_pass` says: "the correct action is to record the confirmation and
the provenance in the bundle. It is NOT a licence to change any threshold, and no threshold would
change." This script does exactly that and nothing else:

  * adds `status: PREREGISTERED HELD-OUT CONFIRMED` and a provenance pointer to the f-electron entry of
    BOTH rule sets;
  * appends one record to a top-level `confirmations[]` list (NOT `promotions[]`: nothing was promoted,
    the rule was already live);
  * sets `modified_at`.

It changes NO threshold, n, target, exclusion or other family, and aborts if any of those differ
before/after. It refuses unless all four pre-registered hypotheses PASSED, unless every hash agrees,
and if a confirmation is already recorded. The pre-change bundle is copied to
data/calibration_bundle_pre_felectron_confirmation.json so the change is reversible by file swap.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FAMILY = "f-electron"
T_STABLE, T_UNSTABLE = -0.02, 0.01
HYPS = ("EA1", "EA2", "EB1", "EB2")
STATUS = "PREREGISTERED HELD-OUT CONFIRMED"
PREREG_SHA256 = "d3995f66d562efd9893137e95a200ef103bc9a7e01ba3d7620356e7c7aafd4d2"
SAMPLE_SHA256 = "43a675a7b4d67d44a18c0ed35b5a12f5d27b3f09452fc55556aa2f27aa348445"
BUNDLE_SHA256_BEFORE = "419c11514d6a54854584258375eadab6b2be0c449e955125799fc51df2310288"


def _commit_of(path: Path) -> str | None:
    r = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(path)], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or None


def main(bundle_path: Path = DATA / "calibration_bundle.json",
         backup: Path = DATA / "calibration_bundle_pre_felectron_confirmation.json",
         result_path: Path = ROOT / "reports" / "felectron_test.json",
         log_path: Path = DATA / "felectron_eval_log.json",
         prereg_path: Path = DATA / "felectron_evaluation_preregistration.json") -> dict:
    raw = bundle_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BUNDLE_SHA256_BEFORE:
        raise SystemExit("ABORT - the bundle is not the one the evaluation tested (sha256 differs)")
    bundle = json.loads(raw)
    before = copy.deepcopy(bundle)

    R, log = json.loads(result_path.read_text()), json.loads(log_path.read_text())
    verdicts = {h: R["hypotheses"][h]["verdict"] for h in HYPS}
    if set(verdicts.values()) != {"PASS"} or R["overall"] != "PASS":
        raise SystemExit(f"ABORT - not all four hypotheses passed: {verdicts}")
    if hashlib.sha256(prereg_path.read_bytes()).hexdigest() != PREREG_SHA256:
        raise SystemExit("ABORT - pre-registration hash differs")
    for label, got in (("result", R["preregistration_sha256"]), ("log", log["preregistration"]["sha256"])):
        if got != PREREG_SHA256:
            raise SystemExit(f"ABORT - the {label} records a different pre-registration")
    if not (R["sample_sha256"] == log["sha256"] == SAMPLE_SHA256):
        raise SystemExit("ABORT - sample hash disagreement")
    if R["active_bundle_sha256"] != BUNDLE_SHA256_BEFORE or log["active_bundle"]["sha256"] != BUNDLE_SHA256_BEFORE:
        raise SystemExit("ABORT - the evaluation ran against a different bundle")
    for path in ("with_second_engine", "without_second_engine"):
        e = bundle["rules"][path]["thresholds"][FAMILY]
        if (e["stable"], e["unstable"]) != (T_STABLE, T_UNSTABLE):
            raise SystemExit(f"ABORT - {path} f-electron thresholds are not the ones tested")
        if e.get("status") == STATUS:
            raise SystemExit("already recorded; this script records the confirmation once")
    if any(c.get("family") == FAMILY for c in bundle.get("confirmations", [])):
        raise SystemExit("already recorded; this script records the confirmation once")

    rec = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "family": FAMILY, "status": STATUS,
        "thresholds_confirmed": {"stable_ev_per_atom": T_STABLE, "unstable_ev_per_atom": T_UNSTABLE},
        "applied_to": ["without_second_engine (Path A)", "with_second_engine (Path B)"],
        "thresholds_changed": False,
        "authorised": "the opening was authorised by Isac Smith on 2026-09-24; recording this confirmation "
                      "requires its own separate decision",
        "preregistration": {"file": "data/felectron_evaluation_preregistration.json", "sha256": PREREG_SHA256,
                            "commit": _commit_of(prereg_path), "pushed_before_the_sample_was_drawn": True},
        "held_out_sample": {"file": "data/wbm_split_felectron_eval.json", "sha256": SAMPLE_SHA256,
                            "n_drawn": R["population"]["drawn"]},
        "evaluation": {"opened_at": log["opened_at"], "evaluated_at": R["evaluated_at"],
                       "result_file": "reports/felectron_test.json", "result_commit": _commit_of(result_path),
                       "population": R["population"],
                       "hypotheses": {h: {k: R["hypotheses"][h][k] for k in
                                          ("path", "side", "calls", "errors", "point", "cp_lower_primary",
                                           "cp_lower_secondary", "target", "verdict")} for h in HYPS},
                       "primary_confidence": R["primary_confidence"],
                       "multiplicity": "Bonferroni over the 4 hypotheses; no grid or family correction "
                                       "(thresholds fixed before the sample existed)"},
        "power_limit": "powered against the development point estimates; a pass means the rule behaves as "
                       "development suggested, not that true precision is far above 0.90",
    }
    for path in ("with_second_engine", "without_second_engine"):
        e = bundle["rules"][path]["thresholds"][FAMILY]
        e["status"] = STATUS
        e["provenance"] = "see confirmations[] in this file; reports/felectron_test.md"
    bundle.setdefault("confirmations", []).append(rec)
    bundle["modified_at"] = rec["recorded_at"]

    # nothing but the two status/provenance fields, confirmations[] and modified_at may change
    for path in ("with_second_engine", "without_second_engine"):
        for fam, e0 in before["rules"][path]["thresholds"].items():
            e1 = bundle["rules"][path]["thresholds"][fam]
            strip = (lambda d: {k: v for k, v in d.items() if k not in ("status", "provenance")}) \
                if fam == FAMILY else (lambda d: d)
            if strip(e0) != strip(e1):
                raise SystemExit(f"ABORT - {path}.{fam} changed beyond status/provenance")
        for key in set(before["rules"][path]) | set(bundle["rules"][path]):
            if key != "thresholds" and before["rules"][path].get(key) != bundle["rules"][path].get(key):
                raise SystemExit(f"ABORT - {path}.{key} changed")
    for key in set(before) | set(bundle):
        if key not in ("rules", "confirmations", "modified_at") and \
                json.dumps(before.get(key), sort_keys=True) != json.dumps(bundle.get(key), sort_keys=True):
            raise SystemExit(f"ABORT - top-level '{key}' changed")

    if not backup.exists():
        backup.write_bytes(raw)
    bundle_path.write_text(json.dumps(bundle, indent=1) + "\n")
    print(f"recorded {STATUS} for {FAMILY} in both rule sets; no threshold changed")
    print(f"  new bundle sha256 {hashlib.sha256(bundle_path.read_bytes()).hexdigest()}")
    return rec


if __name__ == "__main__":
    if "--i-have-an-explicit-decision" not in sys.argv:
        raise SystemExit(__doc__ + "\nRefusing: pass --i-have-an-explicit-decision once the decision is made.")
    main()
