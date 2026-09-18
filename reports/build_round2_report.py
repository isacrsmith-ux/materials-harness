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
         "See section 15",
         "See section 15"],
        ["16", "Oxide subfamily<br/>split",
         "Does any oxide subfamily certify where the whole family cannot",
         "No split certifies at 0.90; three look sample-size limited",
         "No viable path<br/>at 0.90"],
        ["17", "Multi-start<br/>verification",
         "Does the answer depend on where the relaxation started",
         "See section 17",
         "See section 17"],
        ["18", "Failure retry<br/>pass",
         "How many failures are the method, how many are the engine",
         "See section 18",
         "See section 18"],
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
    B.append(("__section16__", section_16))
