#!/usr/bin/env python
"""Promote the pre-registered pnictide shared rule into the production bundle. Once.

    python scripts/promote_pnictide.py

Writes the FIXED thresholds stable = -20 meV and unstable = +0 meV into BOTH rule sets' pnictide
entries, and nothing else. It does not refit, optimise, search, or read the held-out outcomes for any
purpose other than recording them as provenance. The values come from the pre-registration, which
fixed them before the held-out sample was drawn.

Refuses unless all four pre-registered hypotheses passed. Refuses if already promoted. The
pre-promotion bundle is copied to data/calibration_bundle_pre_pnictide.json so the prior production
state stays on disk and the change is reversible by file swap.

Every family other than pnictide is compared byte-for-byte before and after; any difference aborts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from datetime import datetime, timezone

from harness import calibration as CAL, confidence as C
from harness.config import DATA_DIR

BUNDLE = CAL.BUNDLE_FILE
BACKUP = DATA_DIR / "calibration_bundle_pre_pnictide.json"
PREREG = DATA_DIR / "pnictide_evaluation_preregistration.json"
SPLIT = DATA_DIR / "wbm_split_pnictide_eval.json"
LOG = DATA_DIR / "pnictide_eval_log.json"
RESULT = DATA_DIR.parent / "reports" / "pnictide_test.json"

FAMILY = "pnictide"
T_STABLE, T_UNSTABLE = -0.02, 0.0
HYPS = ("PA1", "PA2", "PB1", "PB2")


def _commit_of(path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", str(path)], text=True).strip() or None
    except Exception:
        return None


def main() -> None:
    bundle = json.loads(BUNDLE.read_text())
    before = copy.deepcopy(bundle)

    # --- refuse unless the held-out evaluation exists and passed on every hypothesis
    if not (LOG.is_file() and RESULT.is_file()):
        raise SystemExit("ABORT - no held-out evaluation record; promotion requires one")
    R = json.loads(RESULT.read_text())
    verdicts = {h: R["hypotheses"][h]["verdict"] for h in HYPS}
    if set(verdicts.values()) != {"PASS"}:
        raise SystemExit(f"ABORT - not all hypotheses passed: {verdicts}")
    log = json.loads(LOG.read_text())

    # --- the protocol must be the one the sample was drawn and opened under
    prereg_sha = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    split = json.loads(SPLIT.read_text())
    for label, want in (("split", split["preregistration"]["sha256"]),
                        ("opening log", log["preregistration"]["sha256"])):
        if prereg_sha != want:
            raise SystemExit(f"ABORT - pre-registration hash disagrees with the {label}")
    if R["preregistration_sha256"] != prereg_sha:
        raise SystemExit("ABORT - the evaluation scored a different pre-registration")
    if R["sample_sha256"] != split["test"]["sha256"] != log["sha256"]:
        raise SystemExit("ABORT - sample hash disagreement")

    # --- the thresholds must be exactly what was pre-registered; nothing is derived here
    P = json.loads(PREREG.read_text())
    if (P["thresholds_under_test"]["stable_ev_per_atom"],
            P["thresholds_under_test"]["unstable_ev_per_atom"]) != (T_STABLE, T_UNSTABLE):
        raise SystemExit("ABORT - the pre-registered thresholds are not the ones this script writes")

    # --- idempotence guard
    already = all(bundle["rules"][p]["thresholds"][FAMILY].get("stable") == T_STABLE
                  and bundle["rules"][p]["thresholds"][FAMILY].get("unstable") == T_UNSTABLE
                  for p in ("with_second_engine", "without_second_engine"))
    if already:
        raise SystemExit("already promoted; this script writes the pnictide rule once")

    if not BACKUP.exists():
        BACKUP.write_text(BUNDLE.read_text())
        print(f"pre-promotion bundle preserved: {BACKUP.name}")

    prov = {
        "promoted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "family": FAMILY,
        "thresholds": {"stable_ev_per_atom": T_STABLE, "unstable_ev_per_atom": T_UNSTABLE},
        "applied_to": ["without_second_engine (Path A)", "with_second_engine (Path B)"],
        "status": "PREREGISTERED HELD-OUT CONFIRMED",
        "replaced": {
            "without_second_engine": {"stable": before["rules"]["without_second_engine"]["thresholds"][FAMILY].get("stable"),
                                      "unstable": before["rules"]["without_second_engine"]["thresholds"][FAMILY].get("unstable"),
                                      "n": before["rules"]["without_second_engine"]["thresholds"][FAMILY].get("n")},
            "with_second_engine": {"stable": before["rules"]["with_second_engine"]["thresholds"][FAMILY].get("stable"),
                                   "unstable": before["rules"]["with_second_engine"]["thresholds"][FAMILY].get("unstable"),
                                   "n": before["rules"]["with_second_engine"]["thresholds"][FAMILY].get("n")},
        },
        "development_source": {
            "path_A_fit": "reports/round4_carried_over.{md,json} - pnictide labelable, n=3,637",
            "path_B_fit": "reports/round4_pathb_refit.{md,json} - B-refit, n=3,501",
            "note": ("the thresholds were SELECTED on these development populations and are not "
                     "re-derived here; the held-out evaluation tested them as fixed values"),
        },
        "preregistration": {
            "file": "data/pnictide_evaluation_preregistration.json",
            "sha256": prereg_sha,
            "commit": _commit_of(PREREG),
            "committed_before_the_sample_was_drawn": True,
        },
        "held_out_sample": {
            "file": "data/wbm_split_pnictide_eval.json",
            "sha256": split["test"]["sha256"],
            "n_drawn": R["population"]["drawn"],
            "commit": _commit_of(SPLIT),
        },
        "evaluation": {
            "opened_at": log["opened_at"],
            "evaluated_at": R["evaluated_at"],
            "result_file": "reports/pnictide_test.json",
            "commit": _commit_of(RESULT),
            "opening_log_commit": _commit_of(LOG),
            "population": {
                "drawn": R["population"]["drawn"],
                "usable": R["population"]["usable"],
                "unusable": R["population"]["unusable"],
                "labelable_path_A": R["population"]["labelable_A"],
                "labelable_path_B": R["population"]["labelable_B"],
                "removed_by_disagreement": R["population"]["removed_by_disagreement"],
            },
            "hypotheses": {h: {"path": ("A" if h.startswith("PA") else "B"),
                               "side": ("stable" if h.endswith("1") else "unstable"),
                               "calls": R["hypotheses"][h]["calls"],
                               "errors": R["hypotheses"][h]["errors"],
                               "point": R["hypotheses"][h]["point"],
                               "cp_lower_primary": R["hypotheses"][h]["cp_lower_primary"],
                               "target": R["hypotheses"][h]["target"],
                               "verdict": R["hypotheses"][h]["verdict"]} for h in HYPS},
            "statistics": {
                "bound": "one-sided Clopper-Pearson lower bound; never a bootstrap",
                "primary_confidence": R["primary_confidence"],
                "multiplicity": ("Bonferroni over the 4 pre-registered hypotheses (1 - 0.05/4). NO grid "
                                 "correction: the thresholds were fixed before the sample existed, so "
                                 "nothing was selected on held-out data. NO family correction: only "
                                 "pnictide was tested."),
                "dependence": ("Path B is a strict subset of Path A. Bonferroni is valid under arbitrary "
                               "dependence (Boole's inequality), and the conjunctive promotion rule makes "
                               "the correction strictly conservative. Resolved in the pre-registration "
                               "before any result existed."),
                "verdict_rule": "read from the bound, never the point estimate",
            },
            "power_limit": ("powered against the development POINT estimate. A pass means the thresholds "
                            "behave as development suggested; it does NOT establish that true precision "
                            "is comfortably above 0.90."),
        },
    }

    for path, n_fit in (("without_second_engine", R["population"]["labelable_A"]),
                        ("with_second_engine", R["population"]["labelable_B"])):
        e = bundle["rules"][path]["thresholds"][FAMILY]
        e["stable"], e["unstable"] = T_STABLE, T_UNSTABLE
        e["n"] = {"without_second_engine": 3637, "with_second_engine": 3501}[path]  # development fit n
        e["status"] = "PREREGISTERED HELD-OUT CONFIRMED"
        e["provenance"] = "see promotions[] in this file; reports/pnictide_test.md"

    bundle.setdefault("promotions", []).append(prov)
    bundle["modified_at"] = prov["promoted_at"]

    # --- nothing but pnictide may change
    for path in ("with_second_engine", "without_second_engine"):
        b4 = {k: v for k, v in before["rules"][path]["thresholds"].items() if k != FAMILY}
        af = {k: v for k, v in bundle["rules"][path]["thresholds"].items() if k != FAMILY}
        if b4 != af:
            raise SystemExit(f"ABORT - a non-pnictide threshold changed in {path}")
        for key in ("target_precision", "target_npv", "certification_confidence", "n_labelable"):
            if before["rules"][path].get(key) != bundle["rules"][path].get(key):
                raise SystemExit(f"ABORT - {path}.{key} changed")
    for key in ("created_at", "harness_commit", "engine", "second_engine", "calibration_set",
                "conformal", "weak_elements", "disagreement_tol_ev", "reliability"):
        if json.dumps(before.get(key), sort_keys=True) != json.dumps(bundle.get(key), sort_keys=True):
            raise SystemExit(f"ABORT - top-level '{key}' changed")

    BUNDLE.write_text(json.dumps(bundle, indent=1) + "\n")
    print(f"promoted {FAMILY}: stable {T_STABLE * 1000:+.0f} meV, unstable {T_UNSTABLE * 1000:+.0f} meV "
          "in BOTH rule sets")
    print(f"  status: {prov['status']}")
    print(f"  every other family, target, exclusion and top-level field verified unchanged")
    print(f"  wrote {BUNDLE}")
    print(f"  new bundle sha256 {hashlib.sha256(BUNDLE.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
