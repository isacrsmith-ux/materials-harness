#!/usr/bin/env python
"""Freeze the round-3 specification as data/calibration_spec_v2.json, and register every locked half.

This writes a SPECIFICATION, not a live product bundle. data/calibration_bundle.json (v1,
2026-09-12) is left exactly as it is and remains what harness.predict actually loads. v2 becomes the
active bundle only if the halide held-out evaluation passes its pre-registered criteria; until then
the product's behaviour is unchanged and v1's historical meaning is preserved intact.

The taxonomy change is deliberately NOT wired into confidence.family() here. Doing so would give
fluoride no entry in v1's threshold table and silently stop the product labelling fluorides, which
is a behaviour change nobody has evaluated. family() changes when v2 is promoted, not before.

    python scripts/freeze_spec_v2.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from harness import calibration as CAL, confidence as C, round2, splits
from harness.config import DATA_DIR, MODELS, settings_tag

SPEC_FILE = DATA_DIR / "calibration_spec_v2.json"
REGISTRY_FILE = DATA_DIR / "locked_sets_registry.json"
PNICTIDE_SPLIT = DATA_DIR / "wbm_split_pnictide_eval.json"
FELECTRON_SPLIT = DATA_DIR / "wbm_split_felectron_eval.json"
FINAL = "reports/round3_final_spec.json"


def sha(ids) -> str:
    return hashlib.sha256(",".join(sorted(ids)).encode()).hexdigest()


def id_sets() -> dict:
    """The calibration ids behind each family's threshold, hashed, so the fit can be reproduced."""
    hal = sorted(set(splits.family_calibration_ids("halide")) |
                 set(round2.calibration_ids(round2.HALIDE_TOPUP)))
    return {
        "halide_draw": {"n": len(hal), "sha256": sha(hal),
                        "source": "data/wbm_split_oxide_halide.json halide calibration + "
                                  "data/wbm_split_round2.json halide_topup calibration",
                        "used_for": ["fluoride", "halide"]},
        "oxide_draw": {"n": len(splits.family_calibration_ids("oxide")),
                       "sha256": sha(splits.family_calibration_ids("oxide")),
                       "source": "data/wbm_split_oxide_halide.json oxide calibration",
                       "used_for": ["oxide"]},
        "chalcogenide_residual_draw": {"n": len(round2.calibration_ids3("chalcogenide_residual")),
                                       "sha256": sha(round2.calibration_ids3("chalcogenide_residual")),
                                       "source": "data/wbm_split_round3.json chalcogenide_residual calibration",
                                       "used_for": ["chalcogenide"]},
        "other_residual_draw": {"n": len(round2.calibration_ids3("other_residual")),
                                "sha256": sha(round2.calibration_ids3("other_residual")),
                                "source": "data/wbm_split_round3.json other_residual calibration",
                                "used_for": ["other"]},
        "sulfide_draw": {"n": len(round2.calibration_ids("sulfide")),
                         "sha256": sha(round2.calibration_ids("sulfide")),
                         "source": "data/wbm_split_round2.json sulfide calibration",
                         "used_for": ["chalcogenide (subsampled into the reconstructed mixture)"]},
        "carbide_draw": {"n": len(round2.calibration_ids("carbide")),
                         "sha256": sha(round2.calibration_ids("carbide")),
                         "source": "data/wbm_split_round2.json carbide calibration",
                         "used_for": ["other (subsampled into the reconstructed mixture)"]},
    }


def build_spec() -> dict:
    F = json.loads(open(FINAL).read())
    v1 = CAL.load()
    key, device, dtype = CAL.PRODUCTION_ENGINE
    m = MODELS[key]

    thresholds = {}
    for fam, t in F["thresholds"].items():
        thresholds[fam] = {
            "stable": t["stable_threshold"], "unstable": t["unstable_threshold"],
            "n_labelable": t["n"], "base_rate": t["base_rate"],
            "n_called_stable": t["n_called_stable"], "n_called_unstable": t["n_called_unstable"],
            "n_truly_stable": t["n_truly_stable"],
            "stable_precision": t["precision"], "stable_precision_cp_lower": t["precision_cp_lower"],
            "unstable_npv": t["npv"], "unstable_npv_cp_lower": t["npv_cp_lower"],
            "recall_stable": t["recall_stable"], "stable_lost": t["stable_lost"],
            "dft_share": t["dft_share"],
            "status": t["status"], "provenance": t["provenance"], "population": t["population"],
        }
    for fam, t in F["carried_over"].items():
        thresholds[fam] = {"stable": t["stable_threshold"], "unstable": t["unstable_threshold"],
                           "n_labelable": t["n"], "status": t["status"], "provenance": t["provenance"]}

    return {
        "spec_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness_commit": CAL.harness_commit(),
        "status": "FROZEN SPECIFICATION - NOT THE ACTIVE BUNDLE",
        "active_bundle": {
            "file": "data/calibration_bundle.json", "spec_version": 1,
            "created_at": v1.raw["created_at"],
            "note": ("v1 remains what harness.predict loads and is unmodified. v2 is promoted only "
                     "if the halide held-out evaluation passes the pre-registered criteria in "
                     "reports/halide_evaluation_preregistration.md. v1's historical meaning is "
                     "preserved: it is the bundle the locked WBM test of 2026-09-12 validated.")},
        "engine": {"key": key, "name": m["name"], "checkpoint": m["file"],
                   "checkpoint_sha256": m["sha256"], "device": device, "dtype": dtype,
                   "settings_tag": settings_tag(device, dtype, model=key)},

        "taxonomy": {
            "chain": ["f-electron", "intermetallic", "oxide", "fluoride", "halide",
                      "chalcogenide", "pnictide", "other"],
            "rule": "first match wins, as in confidence.family()",
            "change_from_v1": "fluoride inserted immediately before halide; nothing else changed",
            "implemented_in_code": False,
            "implementation_note": ("confidence.family() is NOT changed by this file. Changing it "
                                    "would leave fluoride with no entry in v1's threshold table and "
                                    "silently stop the product labelling fluorides. family() changes "
                                    "when v2 is promoted."),
            "justification": {
                "criterion": ("a child is carved out only where the parent's pooled rule has a "
                              "genuine PRECISION deficit on the child - point precision below the "
                              "0.90 target on the child's own rows - not merely a loose confidence "
                              "bound on a small subgroup"),
                "fluoride": ("ADOPTED ON VALIDITY GROUNDS, NOT ROUTING GROUNDS. Under halide's "
                             "pooled -20 meV rule, 350 of 1,888 fluorides are labelled 'likely "
                             "stable' at a point precision of 0.8971, which FAILS the >= 0.90 "
                             "requirement the product promises (CP-lower 0.8366). The carve-out "
                             "INCREASES DFT routing rather than decreasing it: halide's DFT share "
                             "rises 0.096 -> 0.192 and its recall of truly stable candidates falls "
                             "0.599 -> 0.338. That cost is accepted as the price of not making a "
                             "precision promise the engine cannot keep on this chemistry."),
                "sulfide": ("NOT carved out: point precision 0.9448 on 290 calls under "
                            "chalcogenide's pooled rule - no deficit. Splitting costs recall "
                            "0.575 -> 0.545 and buys nothing."),
                "carbide": ("NOT carved out: point precision 0.9826 on 115 calls under 'other's "
                            "pooled rule, bound 0.9043 - holds outright. Splitting collapses "
                            "residual 'other' recall 0.547 -> 0.220."),
                "nitride": ("REJECTED by the user, and independently: it removes pnictide's only "
                            "certified threshold (+50 meV, bound 0.9515 -> nothing at n=166)."),
                "rejected_criterion": ("routing efficiency was considered and rejected as the "
                                       "criterion: it rejects all three carve-outs including the "
                                       "valid one, because pooling always buys statistical power "
                                       "and a split always spends it"),
            },
        },

        "population": {
            "name": "labelable",
            "definition": ("calibration rows that would actually receive a label from the product: "
                           "usable (not rejected by the energy-plausibility guard), AND not "
                           "containing a known-weak element, AND whose relaxation did not leave the "
                           "structure it was given"),
            "authoritative_for": "certification of every threshold in this specification",
            "second_engine_term": ("NOT applied. Round 2 and round 3 ran one engine, so this "
                                   "corresponds to v1's 'without_second_engine' rule set."),
            "secondary_diagnostic": ("all-usable rows, retained in reports/round2_results.md; they "
                                     "describe engine behaviour on a chemistry, not what the product "
                                     "labels, and are NOT the certification footing"),
        },

        "exclusion_rules": {
            "energy_plausibility_guard": ("compare.rejection_reason - convergence, minimum "
                                          "interatomic distance, and energy plausibility against the "
                                          "DFT reference. Rejections are COUNTED AND EXCLUDED, never "
                                          "dropped, so an exclusion cannot quietly improve a rate."),
            "weak_elements": sorted(v1.weak_elements),
            "weak_elements_provenance": "frozen bundle v1, routing.weak_elements_from on the original calibration set",
            "structure_change": ("routing.route_structure_change - a candidate whose relaxation did "
                                 "not end in the basin of the structure it was given is routed to "
                                 "DFT and is not labelable. Phase 6 measured this exclusion to be "
                                 "reproducible: 95.9% of such candidates leave again on a perturbed "
                                 "restart."),
            "above_trusted_range": ("the > 0.3 eV/atom refusal is applied at ROUTING, not at "
                                    "certification, exactly as in v1, so the thresholds here are "
                                    "the ones the reports publish"),
        },

        "certification": {
            "target_precision": C.TARGET_PRECISION, "target_npv": C.TARGET_NPV,
            "confidence": C.CERT_CONF, "grid": [min(C.DEC_GRID), max(C.DEC_GRID), len(C.DEC_GRID)],
            "bound": ("one-sided Clopper-Pearson, Bonferroni-corrected over the threshold grid so "
                      "picking the best threshold keeps the guarantee; never a bootstrap"),
            "verdict_rule": "read from the pessimistic end of the interval, never the point estimate",
            "min_selected": C.MIN_SELECTED, "min_family": C.MIN_FAMILY,
        },

        "thresholds": thresholds,
        "status_meanings": {
            "certified": ("certified on calibration data at the stated target, on a single "
                          "representative draw of that family"),
            "provisional": ("certified on calibration data, but on a population reconstructed by "
                            "mixing two draws at the pool's true ratio rather than on one draw of "
                            "the family. MUST NOT be described as held-out certified anywhere."),
            "carried over": ("unchanged from bundle v1, 2026-09-12, and NOT re-measured in round 2 "
                             "or round 3. Fitted on 210-1,801 rows; the weakest part of the product."),
        },
        "in_sample_caveat": ("every threshold in this specification is fitted and scored on "
                            "calibration rows and is in-sample by construction. NO held-out "
                            "evaluation has been run against any of them. No locked half has been "
                            "opened for this specification."),
        "calibration_id_sets": id_sets(),
        "evaluation_procedure": {
            "document": "reports/halide_evaluation_preregistration.md",
            "state": "written and committed; NOT yet executed",
            "first_set": "halide locked half (round 1, n=2,000)",
            "rule": ("criteria are pre-registered before the half is opened and are not changed "
                     "afterwards; each half is opened once and never re-opened; a miss is reported "
                     "as a miss"),
        },
    }


def build_registry() -> dict:
    fam = splits.load_split(splits.FAMILY_SPLIT_FILE)
    r2, r3 = round2.load(), round2.load3()
    sets = []

    def add(name, t, source, status, note):
        sets.append({"name": name, "n": t["n"], "sha256": t["sha256"],
                     "hash_verifies": sha(t["ids"]) == t["sha256"],
                     "source_file": source, "status": status, "note": note})

    add("original WBM locked test", splits.load_split()["test"], "data/wbm_split.json",
        "OPENED ONCE", "opened 2026-09-12 for the final evaluation (reports/final_test.md); never again")
    add("oxide locked test (round 1)", fam["families"]["oxide"]["test"], "data/wbm_split_oxide_halide.json",
        "UNOPENED", "reserved for the oxide unstable-only routing check, order 2 in the evaluation protocol")
    # state is read from the opening log, not asserted: a registry that can go stale is worse than none
    hlog = DATA_DIR / "halide_test_log.json"
    if hlog.is_file():
        d = json.loads(hlog.read_text())
        add("halide locked test (round 1)", fam["families"]["halide"]["test"], "data/wbm_split_oxide_halide.json",
            "OPENED ONCE",
            (f"opened {d['opened_at']} at commit {d['harness_commit']} under the pre-registration in "
             "reports/halide_evaluation_preregistration.md; result in reports/halide_test.md "
             "(H1-H3 PASS, R1 ambiguous). Never to be re-opened; scripts/halide_eval.py refuses "
             "while data/halide_test_log.json exists."))
    else:
        add("halide locked test (round 1)", fam["families"]["halide"]["test"], "data/wbm_split_oxide_halide.json",
            "UNOPENED", "reserved for the FIRST held-out evaluation: the fluoride carve-out and both halide-side thresholds")
    add("sulfide locked test (round 2)", r2["groups"]["sulfide"]["test"], "data/wbm_split_round2.json",
        "SEALED - UNUSED UNDER THE CURRENT TAXONOMY",
        ("sulfide is not adopted as a family in spec v2, so this half has nothing to settle under "
         "the current taxonomy. It is NOT deleted and NOT closed permanently: its ids, hash and "
         "provenance are retained intact and it remains unavailable to the present analysis, "
         "available to a future separately pre-registered question if one arises."))
    for g in round2.groups3():
        add(f"{g} locked test (round 3)", r3["groups"][g]["test"], "data/wbm_split_round3.json",
            "UNOPENED", f"reserved for the provisional {g.replace('_residual','')} threshold, order 3-4 in the protocol")

    # Drawn under its own pre-registration, after round 4. State is read from the opening log rather
    # than asserted, for the same reason halide's is: a registry that can go stale is worse than none.
    if PNICTIDE_SPLIT.is_file():
        pn = json.loads(PNICTIDE_SPLIT.read_text())
        plog = DATA_DIR / "pnictide_eval_log.json"
        if plog.is_file():
            d = json.loads(plog.read_text())
            status, note = "OPENED ONCE", (
                f"opened {d['opened_at']} at commit {d.get('harness_commit')} under "
                "reports/pnictide_evaluation_preregistration.md. Never to be re-opened.")
        else:
            status, note = "DRAWN, UNOPENED", (
                "drawn " + pn["created_at"] + " under reports/pnictide_evaluation_preregistration.md "
                f"(prereg sha256 {pn['preregistration']['sha256'][:16]}...). Tests the FIXED thresholds "
                "stable -20 meV / unstable +0 meV against four pre-registered hypotheses on both "
                "production paths. No job queued, nothing scored, no opening log exists. Refitting on "
                "this sample is forbidden by the pre-registration.")
        add("pnictide evaluation (round 4)", pn["test"], "data/wbm_split_pnictide_eval.json",
            status, note)

    # f-electron: drawn under its own pre-registration, which was PUSHED before the draw.
    if FELECTRON_SPLIT.is_file():
        fe = json.loads(FELECTRON_SPLIT.read_text())
        flog = DATA_DIR / "felectron_eval_log.json"
        if flog.is_file():
            e = json.loads(flog.read_text())
            status, note = "OPENED ONCE", (
                f"opened {e['opened_at']} at commit {e.get('harness_commit')} under "
                "reports/felectron_evaluation_preregistration.md. Never to be re-opened.")
        else:
            status, note = "DRAWN, UNOPENED", (
                "drawn " + fe["created_at"] + " under reports/felectron_evaluation_preregistration.md "
                f"(prereg sha256 {fe['preregistration']['sha256'][:16]}..., published before the draw). "
                "Tests the LIVE production rule - stable -20 meV / unstable +10 meV - against four "
                "pre-registered hypotheses on both paths. Consumes no earlier locked half: round 4 "
                "reserved no f-electron half, so this was a fresh draw. No job queued, nothing scored.")
        add("f-electron evaluation", fe["test"], "data/wbm_split_felectron_eval.json", status, note)

    # OQMD external held-out half (campaign 2026-09-24): locked before any ML job, never opened by it.
    oqmd_split = DATA_DIR / "oqmd_split.json"
    if oqmd_split.is_file():
        oq = json.loads(oqmd_split.read_text())
        olog = DATA_DIR / "oqmd_heldout_log.json"
        if olog.is_file():
            o = json.loads(olog.read_text())
            status, note = "OPENED ONCE", f"opened {o['opened_at']} under its own pre-registration."
        else:
            status, note = "LOCKED, UNOPENED", (
                "OQMD v1.8 entries independent of the MP 2023-01-10 snapshot (MPtrj superset) and of WBM "
                "by reduced formula; drawn " + oq["created_at"] + " by family x OQMD-stability-bin "
                "stratification, locked BEFORE any ML job ran. No OQMD evaluation is pre-registered; "
                "opening it requires one.")
        t = {"n": oq["heldout"]["n"], "sha256": oq["heldout"]["sha256"],
             "ids": [str(i) for i in sorted(oq["heldout"]["ids"])]}
        add("OQMD external held-out (campaign 2026-09-24)", t, "data/oqmd_split.json", status, note)

    return {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "purpose": ("every held-out set this project has created, its hash, its provenance and "
                        "its state. Nothing here hands out ids: each set's accessor still raises "
                        "PermissionError without unlock=True."),
            "accessor_contract": {
                "original WBM": "splits.test_ids(unlock=True)",
                "round-1 families": "splits.family_test_ids(fam, unlock=True)",
                "round-2 groups": "round2.test_ids(group, unlock=True)",
                "round-3 groups": "round2.test_ids3(group, unlock=True)",
                "pnictide evaluation": "pnictide_eval.test_ids(unlock=True)",
                "f-electron evaluation": "felectron_eval.test_ids(unlock=True)",
                "OQMD external held-out": "external_oqmd.heldout_ids(unlock=True)"},
            "sets": sets,
            "all_hashes_verify": all(s["hash_verifies"] for s in sets)}


if __name__ == "__main__":
    if SPEC_FILE.exists():
        print(f"kept (frozen, written once): {SPEC_FILE}")
    else:
        SPEC_FILE.write_text(json.dumps(build_spec(), indent=1, default=str) + "\n")
        print(f"written: {SPEC_FILE}")
    # the registry tracks STATE and is regenerated on demand; the spec above is frozen and is not
    REGISTRY_FILE.write_text(json.dumps(build_registry(), indent=1, default=str) + "\n")
    print(f"written: {REGISTRY_FILE}")
    reg = json.loads(REGISTRY_FILE.read_text())
    print()
    for s in reg["sets"]:
        print(f"  {s['name']:38s} n={s['n']:5d}  hash {'ok' if s['hash_verifies'] else 'FAIL'}  {s['status']}")
    print(f"\nall hashes verify: {reg['all_hashes_verify']}")
