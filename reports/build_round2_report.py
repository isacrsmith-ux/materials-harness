"""Build reports/round2_results.md and reports/round2_results.pdf — the round-2 test results.

Continues the numbering of reports/test_results.pdf, which ends at section 12, so this document
starts at 13. Every number in the tables is READ from the JSON that the analysis scripts wrote
next to their markdown reports; nothing is recomputed or estimated here. Prose is written here.

ASCII only in drawn strings: reportlab's built-in Helvetica uses WinAnsiEncoding and has no glyph
for <=, >=, rho or the en dash, which render as black boxes.

Run: ./uvw run --with reportlab --no-project python reports/build_round2_report.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RESULTS = ROOT / "results"

ENGINE = "MACE-MPA-0 medium (cpu/float32, settings tag c2480e74)"
DATE = "18 September 2026"


def load(name):
    p = REPORTS / name
    return json.loads(p.read_text()) if p.is_file() else []


def by_group(rows):
    return {r["group"]: r for r in rows}


def dx(rec, side):
    for d in rec["diagnoses"]:
        if d["side"] == side:
            return d
    return {}


def mev(t):
    return "-" if t is None else f"{t * 1000:+.0f} meV"


def f4(x, n=4):
    return "-" if x is None else f"{x:.{n}f}"


def cert_cell(d):
    t = d.get("certified_threshold")
    return f"**{mev(t)}**" if t is not None else "not certified"


# --------------------------------------------------------------------------- data
P1 = by_group(load("round2_phase1_diagnostic.json"))
P2 = by_group(load("round2_phase2_halide.json"))
P3 = by_group(load("round2_phase3_families.json"))
P4 = by_group(load("round2_phase4_oxide_subfamilies.json"))
P4C = by_group(load("round2_phase4_oxide_subfamilies_corrected.json"))
TAX = load("round2_taxonomy_decision.json")
MS = json.loads((RESULTS / "round2_multistart_summary.json").read_text()) \
    if (RESULTS / "round2_multistart_summary.json").is_file() else {}
RT = json.loads((RESULTS / "round2_retry_summary.json").read_text()) \
    if (RESULTS / "round2_retry_summary.json").is_file() else {}
TIMING = json.loads((REPORTS / "round2_timing.json").read_text()) \
    if (REPORTS / "round2_timing.json").is_file() else {"phases": []}


def diag_rows(groups, src):
    out = [["group", "side", "target", "best t", "n sel", "k", "point", "CP-lower",
            "verdict", "n structs needed"]]
    for g in groups:
        r = src.get(g)
        if not r:
            continue
        for d in r["diagnoses"]:
            out.append([g, d["side"], f"{d['target']:.2f}", mev(d["best_threshold"]),
                        str(d["n_selected"]), str(d["k"]), f4(d["point"]), f4(d["cp_lower"]),
                        d["verdict"], str(d.get("n_structures_needed") or "-")])
    return out


def summary_rows(groups, src):
    out = [["group", "n usable", "rejected", "base rate", "stable side", "unstable side"]]
    for g in groups:
        r = src.get(g)
        if not r:
            continue
        out.append([g, str(r["n_usable"]), str(r["n_rejected"]), f4(r["base_rate"], 3),
                    cert_cell(dx(r, "stable")), cert_cell(dx(r, "unstable"))])
    return out


# --------------------------------------------------------------------------- content model
# One list of blocks, rendered twice: to markdown (the readable source) and to PDF.
#   ("h1"|"h2"|"body"|"small"|"note", text)   ("table", rows, widths)   ("pagebreak",)
# Text uses a tiny subset of inline markup understood by both renderers: **bold** and `code`.

B: list[tuple] = []


def h1(t): B.append(("h1", t))
def h2(t): B.append(("h2", t))
def body(t): B.append(("body", t))
def small(t): B.append(("small", t))
def note(t): B.append(("note", t))
def tbl(rows, widths): B.append(("table", rows, widths))
def brk(): B.append(("pagebreak",))


mm_ = 1.0  # widths are given in mm; the PDF renderer multiplies




def section_correction():
    h1("Correction, 18 September 2026 - which rows a threshold is certified on")
    body("**Every certification in this document is on all USABLE rows. The production bundle "
         "certifies on LABELABLE rows, and the two do not always agree.** This section records the "
         "difference and what it changes. Nothing below has been deleted or rewritten: the "
         "all-usable figures are correct for the population they describe, and are retained as the "
         "secondary diagnostic they are.")
    h2("The distinction")
    body("A usable row is one the energy-plausibility guard did not reject. A labelable row is one "
         "that would actually receive a label from the product: usable, and also surviving the "
         "weak-element exclusion and the structure-change exclusion "
         "(<font face='Courier'>route_structure_change</font>). "
         "<font face='Courier'>calibration.fit()</font> is explicitly documented to take \"only the "
         "rows that would actually receive a label\", and that is the population the frozen "
         "per-family thresholds were fitted on. This document's sections 13 to 18 used all usable "
         "rows, matching test 7's own family analysis, and therefore certified on a superset of the "
         "population the product labels.")
    body("Which is right depends on the question. For **how the engine behaves on a chemistry**, "
         "all usable rows is the honest denominator - excluding the structure-changed rows would be "
         "choosing the easy cases. For **what threshold to adopt**, labelable rows is the only "
         "correct footing, because the product never labels the others. The user has ruled that "
         "labelable is authoritative for certification; the all-usable figures stay as the "
         "diagnostic.")
    h2("What moves")
    rows = [["family", "all usable (this document)", "labelable (authoritative)", "changes the conclusion?"]]
    def two(name, tax_key, kind):
        src = TAX["children"] if kind == "child" else None
        if kind == "child":
            r = TAX["children"][tax_key]
            u, l = r["usable"], r["labelable"]
        else:
            r = TAX["parents"][tax_key]
            u, l = r["before"]["usable"], r["before"]["labelable"]
        def cell(m):
            s = m.get("stable_threshold")
            return (f"n={m['n']}, stable {mev(s)}, CP-lower {f4(m['precision_cp_lower'])}"
                    if s is not None else
                    f"n={m['n']}, stable not certified (ceiling bound {f4(m['stable_ceiling_cp_lower'])})")
        return [name, cell(u), cell(l)]
    rows.append(two("halide", "halide", "parent") + ["**yes** - a far looser threshold and recall 0.306 -> 0.599"])
    rows.append(two("sulfide", "sulfide", "child") + ["**yes** - certifies; it does not need ~6,416 more structures"])
    rows.append(two("carbide", "carbide", "child") + ["no - certifies on both footings, marginally"])
    rows.append(two("nitride", "nitride", "child") + ["no - certifies on neither"])
    rows.append(two("fluoride", "fluoride", "child") + ["no - certifies on neither"])
    tbl(rows, [20, 52, 52, 48])
    note("**Two conclusions in this document are superseded by the labelable footing.** "
         "Section 14's halide threshold of -70 meV/atom becomes -20 meV/atom, and its recall "
         "roughly doubles. Section 15's finding that sulfide is sample-size limited and would need "
         "about 6,416 calibration structures is an artefact of the footing: on labelable rows "
         "sulfide certifies a stable threshold at -30 meV/atom with a bound of 0.9047. The "
         "structure-changed rows that the product already refuses to label were what was dragging "
         "both families down. The master family table below is the all-usable version; the "
         "labelable version is in "
         "<font face='Courier'>reports/round2_taxonomy_decision.md</font>.")
    body("Nothing else in sections 13 to 18 changes sign or verdict under the labelable footing. "
         "Oxide remains without a stable-side path, nitride remains uncertified on the stable side, "
         "and the multi-start and retry results of sections 17 and 18 do not depend on the "
         "distinction at all, since neither certifies a threshold.")


def section_15():
    h1("15. The three new families, fully calibrated")
    small("Source: `reports/round2_phase3_families.md`. sulfide 4,000, nitride 2,423 and carbide "
          "1,876 calibration structures, drawn sequentially against a shared taken-set from the "
          "pool ids no earlier split had used. Same methodology as test 7 throughout.")
    body("Phase 1 diagnosed all three as sample-size limited, so all three were scaled to "
         "whatever the pool could supply. Only sulfide reached the 4,000 cap the brief named; "
         "nitride and carbide are the whole of what was available after the leakage guards.")
    tbl(summary_rows(["sulfide", "nitride", "carbide"], P3), [26, 20, 20, 20, 32, 32])
    h2("Diagnosis")
    tbl(diag_rows(["sulfide", "nitride", "carbide"], P3),
        [24, 15, 12, 15, 11, 9, 14, 15, 30, 22])
    body("**Carbide certifies both sides.** Its stable threshold is -20 meV/atom, its unstable "
         "threshold -10 meV/atom. At the ceiling threshold all 97 selected calls were truly "
         "stable, and the verdict is still read from the bound (0.9294), never from that 1.0000.")
    body("**Sulfide and nitride miss, narrowly, and the pool is spent.** Sulfide's bound reaches "
         "0.8747 and nitride's 0.8745 against the 0.90 target; both remain sample-size limited "
         "rather than precision limited, with point precisions of 0.9703 and 0.9859. Sulfide "
         "would need about 6,416 calibration structures against the 4,874 the draw could supply, "
         "and nitride about 3,106 against 2,423. Neither shortfall can be closed from this pool "
         "without dissolving a locked half or relaxing the reduced-formula leakage guard, and "
         "neither was done.")
    h2("What routing on the certified unstable thresholds actually costs")
    rows = [["group", "threshold", "share discarded without DFT", "truly stable lost", "(of)"]]
    for g in ("sulfide", "nitride", "carbide"):
        r = (P3.get(g) or {}).get("routing")
        if r:
            rows.append([g, mev(r["unstable_threshold"]), f"{r['discard_share']:.3f}",
                         f"{r['truly_stable_lost']:.3f}",
                         f"{r['n_truly_stable_discarded']} of {r['n_truly_stable']}"])
    if len(rows) > 1:
        tbl(rows, [26, 24, 48, 34, 32])
    note("**Unstable-side certification is not a small result for these families, and it is not a "
         "free one.** All three certify it, which is what turns 'send everything to DFT' into "
         "'discard most of it without DFT'. But more calibration data certifies a LOWER unstable "
         "threshold, which discards more - and loses more. At n = 500 these families discarded "
         "81-89% of candidates and lost 8-13% of the truly stable ones; at full n they discard "
         "90-93% and lose 25-35%. The round-1 caution therefore applies with more force, not "
         "less: a satisfied NPV target is not the same as keeping your discoveries, and both "
         "numbers belong in any proposal to route on these thresholds.")



def section_16():
    h1("16. Oxide subfamily split")
    small("Source: `reports/round2_phase4_oxide_subfamilies.md`. The existing 3,994-row oxide "
          "calibration set, split by transition-metal against main-group, by the highest formal "
          "cation oxidation state in the first charge-balanced assignment, and by mixed valence. "
          "No new structures were run.")
    body("Test 7's verdict was that oxide is precision limited: its point precision peaks at "
         "0.8750, below the 0.90 target, so the bound converges under target at any n. That is a "
         "statement about the family as a whole. This section asks whether some chemically "
         "coherent part of it behaves better.")
    body("Mixed valence is tested as 'no assignment of one integer oxidation state per element "
         "balances the charge' - the standard operational definition, which Fe3O4 fails and both "
         "FeO and Fe2O3 pass. Compositions pymatgen could not evaluate at all are counted in "
         "neither split, so the two splits' n need not sum to the parent's.")
    tbl(summary_rows(["oxide", "oxide:tm", "oxide:maingroup", "oxide:multi_tm", "oxide:single_tm",
                      "oxide:mixed_valence", "oxide:single_valence",
                      "oxide:ox_le2", "oxide:ox_3", "oxide:ox_4", "oxide:ox_ge5"], P4),
        [40, 18, 18, 20, 28, 28])
    h2("Diagnosis")
    tbl(diag_rows(["oxide", "oxide:tm", "oxide:maingroup", "oxide:multi_tm", "oxide:single_tm",
                   "oxide:mixed_valence", "oxide:single_valence",
                   "oxide:ox_le2", "oxide:ox_3", "oxide:ox_4", "oxide:ox_ge5"], P4),
        [36, 15, 12, 15, 11, 9, 14, 15, 28, 18])
    body("**No oxide subfamily certifies a stable threshold at 0.90.** At the 0.80 fallback the "
         "whole family still certifies at -20 meV/atom, the main-group oxides at -10 meV/atom "
         "and the +4-cation oxides at -20 meV/atom; nothing else clears 0.80 either.")
    h2("The same splits, Bonferroni-corrected over the eleven splits searched")
    body("The certification confidence above is corrected over the threshold grid, which is what "
         "makes picking the best threshold safe. It is not corrected for having searched eleven "
         "splits and reported the best. Correcting for that as well (level 0.99545) gives:")
    tbl(diag_rows(["oxide", "oxide:maingroup", "oxide:mixed_valence", "oxide:ox_4"], P4C),
        [36, 15, 12, 15, 11, 9, 14, 15, 28, 18])
    body("**Under the split correction nothing clears 0.80 either, including oxide itself.** Whole "
         "oxide keeps its 0.80 certification at the published level - it is the parent, not one of "
         "the searched splits, and test 7 certified it without any split multiplicity to correct "
         "for. But every subfamily that looked promising loses it, and the three that looked "
         "sample-size limited need 2,430, 16,020 and 1,719 structures rather than the figures "
         "above. The honest reading is that the oxide splits generated one hypothesis worth a "
         "pre-registered draw - main-group oxides - and no result.")
    note("**These splits are hypothesis-generating, not certified results.** The Clopper-Pearson "
         "level is Bonferroni-corrected over the threshold grid, which is what makes picking the "
         "best threshold safe - it is not corrected over the eleven splits searched here. A "
         "split that looks sample-size limited because it was the best of eleven would need its "
         "own pre-registered draw before any threshold from it could be certified. The "
         "split-corrected figures are reported alongside in the source report.")
    body("The one genuinely informative result is an inversion. The mixed-valence oxides, which "
         "are the half one would expect the engine to handle worst, are the better-behaved half "
         "on the stable side; the single-valence oxides are the precision-limited ones. That "
         "does not give oxide a viable threshold, but it does say the family's ceiling is not "
         "explained by mixed valence.")

def section_17():
    h1("17. Multi-start structure verification")
    small("Source: `reports/round2_phase5_multistart.md`, from `results/round2_multistart.json`. "
          "1,000 candidates sampled proportionally across all six groups run so far, each "
          "relaxed from three starting configurations instead of one.")
    body("Test 4 measured structure-finding by comparing one relaxation against a known target "
         "structure. A real candidate has no known target, so the analogue here is agreement "
         "between starts: if three entries into the same problem land in different minima, the "
         "single number the product reports is an artefact of where the relaxation began. "
         "Start B is a compressed cell (volume x 0.95) - the WBM stand-in for test 4's rescaled "
         "start, since a WBM candidate has no parent structure to predict a volume from - and "
         "start C is the fixed-seed rattle and strain of the production retry ladder.")
    rows = [["family", "n", "all 3 starts usable", "disagreement", "structure", "energy"]]
    for g, a in sorted(MS.get("by_family", {}).items()):
        rows.append([g, str(a["n"]), str(a["n_all_three_usable"]), f"{a['disagreement_rate']:.3f}",
                     f"{a['structure_disagreement']:.3f}", f"{a['energy_disagreement']:.3f}"])
    o = MS.get("overall", {})
    if o:
        rows.append(["**all**", f"**{o['n']}**", str(o["n_all_three_usable"]),
                     f"**{o['disagreement_rate']:.3f}**",
                     f"{o['structure_disagreement']:.3f}", f"{o['energy_disagreement']:.3f}"])
    tbl(rows, [30, 16, 34, 30, 28, 28])
    h2("By true hull-distance bin")
    rows = [["bin", "n", "disagreement", "structure", "energy", "median spread"]]
    for b in ["<0", "0-0.025", "0.025-0.1", "0.1-0.3", ">0.3"]:
        a = MS.get("by_bin", {}).get(b) or MS.get("by_bin", {}).get(b.replace("-", "–"))
        if a:
            rows.append([b, str(a["n"]), f"{a['disagreement_rate']:.3f}",
                         f"{a['structure_disagreement']:.3f}", f"{a['energy_disagreement']:.3f}",
                         f"{a['median_energy_spread_mev']:.1f} meV"])
    tbl(rows, [26, 16, 30, 28, 28, 30])
    body("**One candidate in five answers differently depending on where its relaxation "
         "started**, and the rate is not spread evenly. It is 5.6% in the 0-0.025 bin and 8.6% "
         "below the hull - the bins where 'likely stable' calls are actually made - and 50.9% "
         "above 0.3 eV/atom.")
    note("**This independently confirms the >0.3 eV/atom refusal rule from a different "
         "measurement.** Test 4 put the structure-finding rate above 0.3 eV/atom at 0.38 on a "
         "sample of 16, which is the thinnest evidence behind any rule in the product. This is "
         "169 candidates, needs no known target structure, and says the same thing: above 0.3 "
         "eV/atom the relaxation does not reliably find one answer, so the number attached to "
         "it does not describe one material.")
    body("The disagreement is mostly structural rather than energetic - 0.182 against 0.153 "
         "overall - and the median energy spread is 0.0 meV/atom everywhere except the >0.3 "
         "bin. Where the starts agree they agree very precisely; where they disagree they have "
         "found genuinely different minima rather than the same one to different tolerances.")



def section_18():
    h1("18. Retesting every failure found in phases 1-5")
    small("Source: `reports/round2_phase6_retry.md`, from `results/round2_retry.json`. Every "
          "candidate that failed to converge, was rejected by the energy-plausibility guard, "
          "disagreed across phase 5's starts, or did not end in the basin of the structure it "
          "was given.")
    body("**Nothing was loosened to make a failure pass.** fmax, the maximum-stress criterion "
         "and the guard are identical on every retry rung; only the starting point and the step "
         "cap change. A retried job either genuinely converges to a plausible, structure-matched "
         "result or it stays counted-and-excluded.")
    note("**The retry is the perturbed restart, not the ladder's first rung.** The production "
         "ladder's first rung continues from the previous relaxation's end point. For a "
         "candidate that already converged - which is nearly all of this set, since the "
         "dominant failure class is 'the relaxation left its start' rather than 'it failed' - "
         "that rung restarts at the point it converged to and converges again, testing nothing. "
         "Those candidates get the other rung: a fixed-seed rattle and strain of the ORIGINAL "
         "structure at the extended step cap, which is a different entry into the same basin "
         "question. The full ladder is used only for the candidates whose first attempt gave no "
         "usable result at all.")
    c = RT.get("by_class_input", {})
    if c:
        tbl([["failure class", "candidates"]] + [[k, str(v)] for k, v in sorted(c.items())],
            [60, 30])
        body("A candidate can be in several classes, so these do not sum to the "
             f"{RT.get('n_candidates', '')} retried.")
    rows = [["failure class", "n", "resolved", "genuine", "rate", "what 'resolved' means here"]]
    for cls, a in RT.get("by_class", {}).items():
        rows.append([cls, str(a["n"]), str(a["resolved"]), str(a["genuine"]),
                     f"{a['resolved_rate']:.3f}", a["meaning"]])
    if len(rows) > 1:
        tbl(rows, [32, 12, 18, 16, 14, 76])
    h2("By family")
    classes = list(RT.get("by_class", {}))
    rows = [["family", "n"] + [f"{c}<br/>resolved / genuine" for c in classes]]
    for fam, row in sorted(RT.get("by_family", {}).items()):
        cells = []
        for c in classes:
            v = row.get(c)
            cells.append(f"{v['resolved']} / {v['genuine']}" if v else "-")
        rows.append([fam, str(row["n"])] + cells)
    if len(rows) > 1:
        tbl(rows, [26] + [14] + [32] * len(classes))

    h2("What the retry recovered, and what it did not")
    body("**Hard failures are rare and mostly recoverable.** Six candidates out of the 18,599 "
         "relaxed across round 1 and round 2 failed to converge or were rejected by the guard - "
         "and all six are oxides. Four of the six converge to a plausible result on the retry; two "
         "do not, and stay counted-and-excluded. Those two are the engine's genuine limit on this "
         "set, not the method's.")
    body("**Multi-start disagreement is about half recoverable.** Of the 204 candidates whose "
         "starts disagreed, 111 have a lowest-energy minimum that at least two starts reach once "
         "the perturbed restart is added, which is what 'best of the multi-start attempts' is "
         "supposed to buy. The remaining 93 have a best result found by exactly one start, and no "
         "amount of retrying at fixed tolerances changes that: the model's surface has several "
         "minima there and nothing in the pipeline can say which is the material.")
    note("**'The relaxation left its start' is not a failure, and the retry is what proves it.** "
         "It is the largest class by far - 2,890 candidates - and only 4.1% of them end anywhere "
         "near their starting structure when restarted from a perturbation of it. The reason is "
         "that a WBM initial structure is a pre-DFT elemental-substitution guess, not a claimed "
         "minimum, so a relaxation leaving it is the expected behaviour rather than a fault. Test "
         "4 measured this quantity against a known DFT-relaxed target, where leaving really is a "
         "failure; carrying the same metric to WBM measures something else.")
    body("That has a concrete consequence for the product, and it is a reassuring one. The routing "
         "policy excludes a candidate whose relaxation changed the structure "
         "(<font face='Courier'>route_structure_change</font> defaults to true), and those "
         "exclusions are what the certified thresholds were fitted on. The 95.9% genuine rate says "
         "that exclusion is stable rather than flaky: a candidate excluded this way would be "
         "excluded again on a different run. It is a reproducible property of the structure and "
         "the engine, not of one optimiser trajectory.")
    body("The right structure-finding measure for a candidate with no known target is section 17's "
         "multi-start disagreement, not this class.")



def section_synthesis():
    h1("What the tests say when read together - what round 2 changed")
    body("The existing document closes on five numbered takeaways. These extend them; none is "
         "retracted.")

    h2("1. Coverage is still the binding constraint, but it is no longer stuck")
    body("Test 4's central finding was that the published precision had been measured almost "
         "entirely on f-electron chemistry, which barely appears in real use, and that 82% of "
         "real candidates went to DFT because their families had no certified threshold. Round "
         "2 moves four families off that list. Halide now certifies both sides. Carbide "
         "certifies both sides. Sulfide and nitride certify the unstable side and miss the "
         "stable side narrowly. Oxide still certifies only the unstable side.")

    h2("2. The sample-size / precision-limited distinction paid for itself, and needs a third term")
    body("Test 7 introduced it to decide where more compute was worth spending, and the "
         "prediction held: halide was called sample-size limited, 2,800 more structures were "
         "run, and the stable side certified. The phase 1 diagnostic then spent about 25 "
         "minutes of compute to decide where the next 14 hours should go, and was right about "
         "all four families it examined.")
    body("What round 2 adds is that 'sample-size limited' is not by itself an instruction to "
         "collect more data. Fluoride's point precision is above target, so the label applies - "
         "but reaching the bound would take 1,393,121 calibration structures, 6.5x WBM's whole "
         "unique-prototype pool. Sulfide and nitride are genuinely limited and genuinely out of "
         "reach: they need about 6,416 and 3,106 structures against the 4,874 and 2,423 their "
         "pools could supply. The useful question is not which of the two labels a family gets, "
         "but whether the indicated calibration set can actually be drawn.")

    h2("3. Chemistry families are the wrong grain in at least one place")
    body("Halide certifies at -70 meV/atom as one family. Split fluoride out and the remaining "
         "halides certify at -20 meV/atom - a far more inclusive threshold, labelling many more "
         "candidates - while fluoride certifies nothing at 0.90 and nothing at 0.80 either. One "
         "sub-chemistry was holding back a family it was lumped with, and the frozen taxonomy "
         "cannot see it.")
    body("The same move does not rescue oxide. Eleven splits were searched - transition metal "
         "against main group, formal cation oxidation state, mixed valence - and none certifies "
         "at 0.90. Oxide has no viable stable-side path at the published target, and the answer "
         "to test 7's open question is no.")

    h2("4. Structure-finding is measurable without a known target, and it says what test 4 said")
    body("The >0.3 eV/atom refusal rested on a structure-finding sample of n = 16, flagged as "
         "open work. Multi-start disagreement measures the same reliability on 1,000 candidates "
         "with no known target structure, and reaches 50.9% above 0.3 eV/atom against 5.6% in "
         "the 0-0.025 bin. Two independent measurements now support the refusal, and the "
         "disagreement rate is low exactly where the certified stable thresholds operate.")

    h2("5. The guards earned their place again, and so did distrusting my own code")
    body("The engine assertion aborted on a wrong HARNESS_MODEL in a negative test before any "
         "phase ran - the exact failure that produced a wrong certification verdict in test 7. "
         "The split's disjointness assertion caught 619 ids that a first, wrong draw had put in "
         "a calibration set and a locked half at the same time.")
    body("Three bugs in this round's own analysis code were caught by looking at the numbers "
         "rather than by any guard, and all three would have produced quietly plausible "
         "results. The mixed-valence split matched nothing because "
         "<font face='Courier'>oxi_state_guesses</font> returns a tuple and the test compared it "
         "to a list. The multi-start comparison excluded the calibration relaxation from all "
         "1,000 candidates because a None rejection round-trips through pandas as NaN and "
         "<font face='Courier'>not NaN</font> is False. The same NaN routed every retry to the "
         "wrong ladder rung. None of them raised; each produced a table that looked reasonable. "
         "The check that caught all three was reading a count that should not have been what it "
         "was - 0 mixed-valence oxides, 0 candidates with three usable starts, 0 perturbed "
         "restarts.")



def section_ledger():
    h1("Locked and unopened as of this document")
    L = json.loads((REPORTS / "round2_ledger.json").read_text()) if (REPORTS / "round2_ledger.json").is_file() else None
    if not L:
        return
    small(L["meaning"])
    rows = [["locked set", "n", "hash verifies", "accessor refuses without unlock",
             "ids with results in the store", "state"]]
    for r in L["sets"]:
        rows.append([r["set"], str(r["n"]), "yes" if r["hash_verifies"] else "**NO**",
                     "yes" if r["accessor_refuses_without_unlock"] else "**NO**",
                     str(r["n_ids_with_results_in_store"]), r["state"]])
    tbl(rows, [46, 12, 20, 32, 28, 30])
    body("Round 2 drew 11,099 new calibration structures and never passed "
         "<font face='Courier'>unlock=True</font> anywhere. Every phase asserted this before "
         "enqueueing anything, alongside the engine check. The one new locked half round 2 "
         "created - 874 sulfide ids - is listed above and has not been opened either.")
    note("**Sulfide could be certified at 0.90 by dissolving that half into its calibration "
         "set, and it was not.** Sulfide needs about 6,416 calibration structures and has "
         "4,000; adding the 874 would still leave it short, and would spend a held-out half "
         "for a result that would then have nothing to validate against. The same is true of "
         "relaxing the reduced-formula leakage guard, which dropped 4,111 candidates across "
         "the round-2 draw. Neither is a decision this document should make.")


def section_master():
    h1("The master family table, updated")
    small("Footing: all usable rows, as everywhere else in this document. See the correction "
          "section for the labelable figures, which are authoritative for adoption.")
    body("This is test 7's per-family table, in the same format, extended with every family round 2 "
         "touched. It supersedes the two-row version in section 7 of the existing document. Every "
         "figure is the certified threshold where one exists, and the pessimistic bound in every "
         "case; `n` is usable rows after guard rejections, which are counted and excluded.")
    rows = [["family", "n usable", "base rate", "stable side", "unstable side", "stable-side diagnosis"]]
    spec = [("oxide", P4, "oxide"),
            ("halide (combined, n=6,300)", P2, "halide_combined"),
            ("  of which fluoride", P2, "halide_combined:fluoride"),
            ("  of which non-fluoride", P2, "halide_combined:nonfluoride"),
            ("sulfide", P3, "sulfide"),
            ("nitride", P3, "nitride"),
            ("carbide", P3, "carbide")]
    for label, src, key in spec:
        r = src.get(key)
        if not r:
            continue
        s, u = dx(r, "stable"), dx(r, "unstable")
        if s.get("certified_threshold") is not None:
            stable = f"**{mev(s['certified_threshold'])}**<br/>CP-lower {f4(s['cp_lower'])}"
            diag = "certified"
        else:
            stable = f"not certified<br/>ceiling {f4(s.get('point'))}, CP-lower {f4(s.get('cp_lower'))}"
            n = s.get("n_structures_needed")
            diag = (f"{s.get('verdict')}<br/>needs ~{n:,} structures" if n else str(s.get("verdict")))
        ut = u.get("certified_threshold")
        unstable = (f"**{mev(ut)}**<br/>CP-lower {f4(u['cp_lower'])}" if ut is not None else "not certified")
        rt = r.get("routing")
        if rt:
            unstable += (f"<br/>discards {rt['discard_share']:.3f}, "
                         f"loses {rt['truly_stable_lost']:.3f} of stable")
        rows.append([label, f"{r['n_usable']:,}", f4(r["base_rate"], 3), stable, unstable, diag])
    tbl(rows, [34, 16, 16, 40, 46, 38])
    note("**fluoride and non-fluoride are rows of the same 6,300 structures, not extra data.** "
         "Fluoride is a subset of halide, so the two sub-rows partition the halide row rather than "
         "adding to it. They are shown because the split changes the answer: certifying halide "
         "whole buys -70 meV/atom, certifying it without fluoride buys -20 meV/atom.")
    body("f-electron and intermetallic are unchanged and are not reproduced here; see the existing "
         "document. Nothing in this table has been frozen into "
         "<font face='Courier'>data/calibration_bundle.json</font>, which still records the "
         "round-1 state.")


def section_timing():
    h1("Time against budget")
    body("The brief budgeted wall-clock per phase on an assumed 9.8 s per relaxation. That figure "
         "is section 1's engine-screening benchmark, measured on the screening subset's larger "
         "cells; WBM calibration structures average 8.6 atoms and the production engine relaxes "
         "them far faster. Measured on the completed round-1 run before any round-2 phase started: "
         "15,000 jobs in 57 minutes, or 0.23 s per job. The budgets were recomputed on that basis "
         "after phase 1, as the brief required, rather than being allowed to drift.")
    rows = [["phase", "budget", "actual", "what dominated"]]
    for p in TIMING.get("phases", []):
        rows.append([p.get("phase", ""), p.get("budget", "-"), p.get("actual", "-"), p.get("note", "")])
    if len(rows) > 1:
        tbl(rows, [34, 20, 20, 94])



def build_content():
    h1("Materials Harness - round 2")
    small(f"New families, the halide confirmation, the oxide splits, multi-start structure "
          f"verification and the failure retry. Generated {DATE}. Production engine {ENGINE}, "
          f"asserted at the start of every phase. Continues reports/test_results.pdf, which ends "
          f"at section 12.")

    h1("How to read this document")
    body("Six new tests are recorded here, numbered 13 to 18, continuing the existing document. "
         "Every convention of that document is kept and none is relaxed. Intervals are 95% and "
         "**verdicts are read from the pessimistic end**, never the point estimate. Rates whose "
         "sample could be all-correct use Clopper-Pearson bounds rather than a bootstrap. "
         "Rejected relaxations are counted and excluded, never dropped, so an exclusion cannot "
         "quietly improve a rate. Each section names the report file it came from.")
    body("One term is used throughout. A family is **sample-size limited** when its best "
         "achievable point precision is already above target and only the confidence bound falls "
         "short - more calibration data would certify it. It is **precision limited** when the "
         "point precision itself peaks below target, so the bound converges under target at any n. "
         "That distinction is test 7's, and it is what decides whether more compute is worth "
         "spending. This document adds a third reading: a family can be sample-size limited and "
         "still unreachable, when the calibration set it would need is larger than the pool it "
         "could be drawn from.")
    note("**The four families the brief named are not families in the frozen taxonomy.** "
         "`confidence.family()` resolves fluoride to halide, sulfide to chalcogenide, nitride to "
         "pnictide, and a metal carbide to 'other'; and 34-59% of the compounds containing each "
         "of those anions are also f-electron, which wins first-match. Round 2 therefore uses "
         "`round2.family2()`, which keeps f-electron, intermetallic and oxide exactly where they "
         "are and inserts the new anion families ahead of the rest. The frozen taxonomy, the "
         "frozen bundle and the round-1 certifications are untouched. Adopting any new family "
         "into production would carve it out of its parent, and the parent would have to be "
         "re-certified on its reduced population - a decision for the user, not this document.")

    h1("Summary of the round-2 tests")
    tbl([
        ["#", "Test", "What it answers", "Headline", "Verdict"],
        ["13", "Diagnostic pull,<br/>four new families",
         "Which families are worth a full calibration pull",
         "sulfide, nitride and carbide all sample-size limited; fluoride precision limited",
         "Three worth scaling,<br/>one not"],
        ["14", "Halide<br/>re-certification",
         "Does more data certify halide's stable side at 0.90",
         "n 3,500 -> 6,300: CP-lower 0.8803 -> 0.9028 at -70 meV",
         "**Certified**"],
        ["15", "New families<br/>certified",
         "Can sulfide, nitride and carbide be certified",
         "carbide certifies both sides; sulfide and nitride certify the unstable side and miss "
         "the stable side at 0.8747 and 0.8745",
         "One certified,<br/>two out of reach"],
        ["16", "Oxide subfamily<br/>split",
         "Does any oxide subfamily certify where the whole family cannot",
         "No split certifies at 0.90; three look sample-size limited",
         "No viable path<br/>at 0.90"],
        ["17", "Multi-start<br/>verification",
         "Does the answer depend on where the relaxation started",
         "1 candidate in 5 disagrees across starts; 0.056 in the 0-0.025 bin, 0.509 above 0.3 eV/atom",
         "Confirms the<br/>&gt;0.3 refusal"],
        ["18", "Failure retry<br/>pass",
         "How many failures are the method, how many are the engine",
         "4 of 6 hard failures resolved; 54% of multi-start disagreements; 4% of 'left its start'",
         "Mostly genuine,<br/>not fixable"],
    ], [8, 26, 38, 62, 28])
    brk()

    # ------------------------------------------------------------------ 13
    h1("13. Diagnostic pull - four new families")
    small("Source: `reports/round2_phase1_diagnostic.md`. Methodology inherited from test 7 without "
          "change: pool exclusion of every prior and locked id, per-family base rates preserved by a "
          "per-bin proportional draw, Clopper-Pearson bounds Bonferroni-corrected over the threshold "
          "grid, verdicts from the pessimistic end, rejections counted-and-excluded.")
    body("Before committing a full pull to nitride, carbide, fluoride and sulfide, roughly 500 "
         "structures of each were run and put through the same diagnosis that distinguished halide "
         "from oxide in test 7. The point of the test is to spend compute only where more data can "
         "change the answer.")
    note("**Fluoride was never drawn.** It is a strict subset of `confidence.family()`'s halide, so "
         "the round-1 halide calibration set already held 1,208 fluorides - more than a fresh draw "
         "of the remaining pool could have bought. It is diagnosed on those, as a halide subfamily, "
         "at zero additional compute. The same logic does not apply to the other three: sulfide, "
         "nitride and carbide are largely outside the families already run.")
    tbl(summary_rows(["sulfide@p1", "nitride@p1", "carbide@p1",
                      "halide:fluoride", "halide:nonfluoride"], P1),
        [34, 20, 20, 20, 32, 32])
    h2("Diagnosis")
    tbl(diag_rows(["sulfide@p1", "nitride@p1", "carbide@p1",
                   "halide:fluoride", "halide:nonfluoride"], P1),
        [30, 17, 13, 17, 13, 10, 15, 17, 30, 20])
    body("**All three newly drawn families are sample-size limited**, so all three were scaled in "
         "phase 3. Their point precisions at the ceiling threshold are 0.9444, 0.9714 and 1.0000 "
         "respectively, all above the 0.90 target; only the bound falls short, and only because "
         "500 structures yield 29 to 54 selected calls.")
    body("**Fluoride is not, and the result is the more interesting one.** At n = 1,208 its point "
         "precision peaks at 0.8767, below target, exactly as oxide does - and unlike oxide it does "
         "not clear the 0.80 fallback either. The non-fluoride halides, by contrast, reach 0.9556 "
         "and need only 1.12x more data. Fluoride is what was holding halide's stable side back.")
    brk()

    # ------------------------------------------------------------------ 14
    h1("14. Halide re-certification")
    small("Source: `reports/round2_phase2_halide.md`. 2,800 additional halide calibration "
          "candidates drawn from the pool ids neither the original split nor round 1 had touched, "
          "with every prior and locked id excluded by id and every candidate sharing a reduced "
          "formula with a locked-test id dropped.")
    body("Test 7 diagnosed halide as sample-size limited and predicted that roughly 1.8x more "
         "calibration structures would certify its stable side at 0.90. This is the direct test of "
         "that prediction. Recomputing test 7's own ceiling here gives 6,948 structures indicated, "
         "against the ~6,300 the brief asked for; 6,300 were run.")
    tbl(summary_rows(["halide", "halide_topup", "halide_combined",
                      "halide_combined:fluoride", "halide_combined:nonfluoride"], P2),
        [46, 18, 18, 18, 30, 30])
    h2("Diagnosis")
    tbl(diag_rows(["halide", "halide_topup", "halide_combined",
                   "halide_combined:fluoride", "halide_combined:nonfluoride"], P2),
        [42, 15, 12, 15, 11, 9, 14, 15, 24, 18])
    body("**The stable side certifies.** At n = 6,300 the combined halide calibration set carries a "
         "certified stable threshold of -70 meV/atom: 480 selected calls, 453 of them truly stable, "
         "point precision 0.9437, and a Clopper-Pearson lower bound of 0.9028 against the 0.90 "
         "target. The verdict is read from 0.9028, not from 0.9437.")
    body("It certified on slightly less data than indicated because the top-up's own precision came "
         "out a little higher than round 1's (0.9506 against 0.9401). That is luck in the right "
         "direction, not a method improvement, and it should not be read as evidence that the "
         "estimate was conservative.")
    note("**The split matters more than the total.** Certifying halide as one family buys a "
         "threshold of -70 meV/atom. Splitting fluoride out and certifying the rest buys -20 "
         "meV/atom on the non-fluoride halides - a far more inclusive rule, which labels many more "
         "candidates - while fluoride certifies nothing. Fluoride's own ceiling is 0.9029 on 175 "
         "calls, which is technically above target, but reaching the bound would take 1,393,121 "
         "calibration structures: 6.5x the whole 215,488-structure WBM unique-prototype pool. "
         "Sample-size limited and unreachable are not the same verdict, and fluoride is the second.")
    brk()

    # ------------------------------------------------------------------ 16 (15 is inserted before it at render time)
    section_correction()
    brk()
    section_15()
    brk()
    section_16()
    brk()
    section_17()
    brk()
    section_18()
    brk()
    section_master()
    brk()
    section_synthesis()
    brk()
    section_timing()
    section_ledger()


# --------------------------------------------------------------------------- renderers
import re


def _md_inline(t: str) -> str:
    t = re.sub(r"<font face='Courier'>(.+?)</font>", r"`\1`", t)
    t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&#183;", "·")
    return t.replace("<br/>", " ")


def to_markdown(blocks) -> str:
    L = []
    first = True
    for b in blocks:
        kind = b[0]
        if kind == "pagebreak":
            L.append("")
        elif kind == "h1":
            L.append(f"\n{'#' if first else '##'} {_md_inline(b[1])}\n")
            first = False
        elif kind == "h2":
            L.append(f"\n### {_md_inline(b[1])}\n")
        elif kind == "note":
            L.append("> " + _md_inline(b[1]).replace("\n", "\n> ") + "\n")
        elif kind in ("body", "small"):
            L.append(_md_inline(b[1]) + "\n")
        elif kind == "table":
            rows = b[1]
            L.append("| " + " | ".join(_md_inline(str(c)) for c in rows[0]) + " |")
            L.append("|" + "---|" * len(rows[0]))
            for r in rows[1:]:
                L.append("| " + " | ".join(_md_inline(str(c)) for c in r) + " |")
            L.append("")
    return "\n".join(L).replace("\n\n\n", "\n\n") + "\n"


_ASCII = {"–": "-", "—": " - ", "≤": "<=", "≥": ">=", "·": "-", "×": "x", "’": "'", "“": '"', "”": '"'}


def _pdf_inline(t: str) -> str:
    """reportlab's Helvetica is WinAnsi: anything outside it draws as a black box."""
    for k, v in _ASCII.items():
        t = t.replace(k, v)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", t)
    return t


def to_pdf(blocks, out_path):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    INK = colors.HexColor("#1a1a1a")
    MUTED = colors.HexColor("#5b6169")
    RULE = colors.HexColor("#d4d7dc")
    BAND = colors.HexColor("#f2f4f6")
    ACCENT = colors.HexColor("#1f4e79")
    WARN = colors.HexColor("#8a4b08")
    ss = getSampleStyleSheet()
    S = {
        "title": ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=24,
                                leading=28, textColor=INK, alignment=TA_LEFT, spaceAfter=4),
        "sub": ParagraphStyle("sub", parent=ss["Normal"], fontSize=11, leading=15, textColor=MUTED,
                              spaceAfter=18),
        "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15,
                             leading=19, textColor=ACCENT, spaceBefore=16, spaceAfter=7),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=10.5,
                             leading=14, textColor=INK, spaceBefore=11, spaceAfter=4),
        "body": ParagraphStyle("body", parent=ss["Normal"], fontSize=9.4, leading=13.6, textColor=INK,
                               spaceAfter=7),
        "small": ParagraphStyle("small", parent=ss["Normal"], fontSize=8.2, leading=11.4,
                                textColor=MUTED, spaceAfter=6),
        "cell": ParagraphStyle("cell", parent=ss["Normal"], fontSize=7.4, leading=9.8, textColor=INK),
        "cellh": ParagraphStyle("cellh", parent=ss["Normal"], fontSize=7.4, leading=9.8,
                                textColor=colors.white, fontName="Helvetica-Bold"),
    }

    def chrome(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 12 * mm, "Materials Harness - round 2 results")
        canvas.drawRightString(190 * mm, 12 * mm, f"page {doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
        canvas.restoreState()

    F = []
    first_h1 = True
    for b in blocks:
        kind = b[0]
        if kind == "pagebreak":
            F.append(PageBreak())
        elif kind == "h1":
            if first_h1:
                F.append(Paragraph(_pdf_inline(b[1]), S["title"]))
                first_h1 = False
            else:
                F.append(Paragraph(_pdf_inline(b[1]), S["h1"]))
        elif kind == "h2":
            F.append(Paragraph(_pdf_inline(b[1]), S["h2"]))
        elif kind == "body":
            F.append(Paragraph(_pdf_inline(b[1]), S["body"]))
        elif kind == "small":
            F.append(Paragraph(_pdf_inline(b[1]), S["sub" if len(F) < 2 else "small"]))
        elif kind == "note":
            t = Table([[Paragraph(_pdf_inline(b[1]), ParagraphStyle(
                "n", parent=S["body"], fontSize=8.6, leading=12.2, textColor=WARN))]],
                colWidths=[168 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdf6ec")),
                ("LINEBEFORE", (0, 0), (0, -1), 2.2, WARN),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            F += [t, Spacer(1, 7)]
        elif kind == "table":
            rows, widths = b[1], b[2]
            data = [[Paragraph(_pdf_inline(str(c)), S["cellh" if i == 0 else "cell"]) for c in r]
                    for i, r in enumerate(rows)]
            t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
            style = [("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                     ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
                     ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                     ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
            for i in range(2, len(rows), 2):
                style.append(("BACKGROUND", (0, i), (-1, i), BAND))
            t.setStyle(TableStyle(style))
            F += [t, Spacer(1, 8)]
    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm,
                            title="Materials Harness - round 2 results", author="Materials Harness")
    doc.build(F, onFirstPage=chrome, onLaterPages=chrome)




if __name__ == '__main__':
    build_content()
    md = REPORTS / 'round2_results.md'
    md.write_text(to_markdown(B))
    pdf = REPORTS / 'round2_results.pdf'
    to_pdf(B, pdf)
    print(f'written: {md}')
    print(f'written: {pdf}')
