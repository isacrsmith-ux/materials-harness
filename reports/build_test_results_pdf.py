"""Build reports/test_results.pdf — every test run in this project and its results.

Every number here is transcribed from a report file in reports/ or measured in-session; the
source is named under each section. Nothing is recomputed or estimated here.

ASCII only in drawn strings: reportlab's built-in Helvetica uses WinAnsiEncoding, which has no
glyph for <=, >=, rho or kappa, and they render as black boxes.

Run: ./uvw run --with reportlab --no-project python reports/build_test_results_pdf.py

reportlab is deliberately NOT a project dependency: this script is the only thing that
needs it, and "uvw run --with" supplies it for the one command.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "test_results.pdf"

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5b6169")
RULE = colors.HexColor("#d4d7dc")
BAND = colors.HexColor("#f2f4f6")
ACCENT = colors.HexColor("#1f4e79")
WARN = colors.HexColor("#8a4b08")

ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold",
                            fontSize=24, leading=28, textColor=INK, alignment=TA_LEFT,
                            spaceAfter=4),
    "sub": ParagraphStyle("sub", parent=ss["Normal"], fontSize=11, leading=15,
                          textColor=MUTED, spaceAfter=18),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                         fontSize=15, leading=19, textColor=ACCENT, spaceBefore=16,
                         spaceAfter=7),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                         fontSize=10.5, leading=14, textColor=INK, spaceBefore=11,
                         spaceAfter=4),
    "body": ParagraphStyle("body", parent=ss["Normal"], fontSize=9.4, leading=13.6,
                           textColor=INK, spaceAfter=7),
    "small": ParagraphStyle("small", parent=ss["Normal"], fontSize=8.2, leading=11.4,
                            textColor=MUTED, spaceAfter=6),
    "cell": ParagraphStyle("cell", parent=ss["Normal"], fontSize=8.1, leading=10.6,
                           textColor=INK),
    "cellb": ParagraphStyle("cellb", parent=ss["Normal"], fontSize=8.1, leading=10.6,
                            textColor=INK, fontName="Helvetica-Bold"),
    "cellh": ParagraphStyle("cellh", parent=ss["Normal"], fontSize=8.1, leading=10.6,
                            textColor=colors.white, fontName="Helvetica-Bold"),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def note(text):
    """A callout for a caveat that must travel with the numbers above it."""
    t = Table([[Paragraph(text, ParagraphStyle(
        "n", parent=S["body"], fontSize=8.6, leading=12.2, textColor=WARN))]],
        colWidths=[168 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdf6ec")),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, WARN),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def table(rows, widths, align_right=(), bold_rows=()):
    data = []
    for r_i, row in enumerate(rows):
        out = []
        for c_i, cell in enumerate(row):
            if r_i == 0:
                out.append(Paragraph(str(cell), S["cellh"]))
            else:
                st = "cellb" if r_i in bold_rows else "cell"
                out.append(Paragraph(str(cell), S[st]))
        data.append(out)
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(2, len(rows), 2):
        style.append(("BACKGROUND", (0, i), (-1, i), BAND))
    for c in align_right:
        style.append(("ALIGN", (c, 1), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def chrome(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, "Materials Harness - test results")
    canvas.drawRightString(190 * mm, 12 * mm, f"page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
    canvas.restoreState()


F = []   # flowables
add = F.append

# ----------------------------------------------------------------- title + summary
add(P("Materials Harness", "title"))
add(P("Every test run to date, and what each one found<br/>"
      "Generated 17 September 2026 &#183; production engine MACE-MPA-0 medium "
      "(cpu/float32, settings tag c2480e74) &#183; second engine MACE-MP-0 medium "
      "(cpu/float64, tag 207ccc81)", "sub"))

add(P("How to read this document", "h1"))
add(P("Ten tests and two publication audits are recorded here. The tests are not "
      "interchangeable: three measure accuracy against DFT, two measure whether the product's "
      "<i>decisions</i> are safe, one measures whether the pipeline finds the right structure at "
      "all, and the rest check data integrity and engine provenance. The last two sections are "
      "not experiments - they audit what this repository may lawfully publish, and what it "
      "actually exposed when it was published. Each section names the report file it came from.", "body"))
add(P("Two conventions run throughout. Intervals are 95% and <b>verdicts are read from the "
      "pessimistic end</b>, never the point estimate. Rates whose sample could be all-correct "
      "use Clopper-Pearson intervals rather than a bootstrap, because a bootstrap collapses to "
      "[1.00, 1.00] on an error-free sample and would report an artifact of the estimator as a "
      "result.", "body"))

add(P("Summary of every test and audit", "h1"))
add(table([
    ["#", "Test", "What it answers", "Headline", "Verdict"],
    ["1", "Engine screening<br/>(Phase 3)", "Which engine should be the product",
     "MACE-MPA-0: F1 0.852, precision 0.853, MAE 28 meV/atom",
     "Adopted"],
    ["2", "Validation scorecard<br/>(calibration)", "Accuracy and routing on 3,998 WBM candidates",
     "Precision 0.826, NPV 0.971, 43% to DFT", "Use with caution"],
    ["3", "Locked WBM test<br/>(one-time)", "Do the frozen rules hold out of sample",
     "Precision 0.960, NPV 0.988, 41% to DFT", "Passed"],
    ["4", "Unseen real materials", "Does it work on chemistry never trained on",
     "Precision 1.00 [0.85, 1.00] on 22 calls; 82% to DFT", "Not distinguishable<br/>from WBM"],
    ["5", "Polymorph ranking", "Which form of a composition wins",
     "Ground state first 0.69; gap MAE 19.4 meV/atom", "Use with caution"],
    ["6", "Cost operating point", "Where to set the threshold given costs",
     "-35 meV/atom; precision 0.94, recall 0.45", "Policy-derived,<br/>not measured"],
    ["7", "Oxide/halide<br/>calibration (new)", "Can these families be certified at all",
     "Unstable side certified for both; stable side neither",
     "Split result"],
    ["8", "Energy-plausibility<br/>guard", "Was a bad result corrupting the statistics",
     "One impossible energy (-1131 eV/atom) found and excluded", "Fixed"],
    ["9", "Leakage check<br/>(SevenNet-Omni)", "Is a rival engine's win trustworthy",
     "~1% of training undocumented", "Not adopted"],
    ["10", "Reference data<br/>collection (new)", "Citable experimental data for future suites",
     "89 rows across 2 properties; experimental floor ~0.09%", "Delivered"],
    ["11", "Licensing and<br/>attribution audit", "What may lawfully be published, and under what",
     "One real gap (MP attribution); ASE is the one LGPL dependency",
     "Gaps closed"],
    ["12", "Pre-publication<br/>audit", "Does anything private reach a public repository",
     "0 secrets in history; a personal email reached the public repo",
     "Closed, with one<br/>real failure"],
], [8 * mm, 26 * mm, 38 * mm, 62 * mm, 28 * mm]))

add(PageBreak())

# ------------------------------------------------------------------------- 1 and 2
add(P("1. Engine screening - choosing the production model", "h1"))
add(P("Source: <font face='Courier'>reports/phase3/candidates.md</font>, "
      "<font face='Courier'>screening.md</font>. Paired comparison on a fixed subset "
      "(125 MP pairs per hull bin plus 500 WBM calibration structures). The locked test set "
      "was not used.", "small"))
add(P("<b>The F1, DAF, precision and MAE columns below are the engines' <i>published</i> "
      "Matbench Discovery scores</b>, read from the model metadata files, not measurements made "
      "by this harness. This harness's own measurement of the adopted engine is F1 0.832 "
      "[0.808, 0.853] (section 2), which contains the published 0.852 - reproducing the "
      "benchmark is itself one of the results. The two numbers are different quantities and "
      "should not be compared as if one contradicted the other.", "body"))
add(table([
    ["Engine", "F1", "DAF", "Precision", "MAE<br/>meV/atom", "Compliant", "Speed on this Mac"],
    ["MACE-MP-0 medium", "0.669", "3.777", "0.577", "57", "yes", "8.6 s/relaxation"],
    ["MACE-MPA-0 medium", "0.852", "5.582", "0.853", "28", "yes", "9.8 s/relaxation"],
    ["eSEN-30M-OAM", "0.925", "6.069", "0.928", "18", "yes", "92.3 s/relaxation"],
    ["SevenNet-Omni", "0.906", "5.954", "0.910", "21", "unverified", "73.6 s/relaxation"],
], [36 * mm, 14 * mm, 14 * mm, 20 * mm, 20 * mm, 22 * mm, 38 * mm],
    bold_rows=(2,)))
add(P("<b>Decision: MACE-MPA-0 medium.</b> eSEN-30M-OAM scores better on every accuracy metric "
      "but runs roughly 9x slower, which puts a full run at about a week on this machine and "
      "makes it unusable here. SevenNet-Omni is faster than eSEN but its training provenance is "
      "unverified (test 9). MACE-MP-0 is retained as a second engine, used only for the "
      "disagreement signal.", "body"))

add(P("2. Validation scorecard - calibration set", "h1"))
add(P("Source: <font face='Courier'>reports/validation_report.md</font>. 3,998 usable WBM "
      "calibration relaxations. Every threshold in the product is fitted here and nowhere else.", "small"))
add(table([
    ["Quantity", "MACE-MP-0", "MACE-MPA-0", "Change"],
    ["Precision at optimal threshold", "0.686", "0.826", "+0.140"],
    ["Recall at optimal threshold", "0.534", "0.838", "+0.304"],
    ["F1", "0.600", "0.832", "+0.232"],
    ["NPV", "0.919", "0.971", "+0.052"],
    ["Discovery acceleration factor", "3.607", "5.411", "+1.804"],
    ["Share routed to DFT", "0.636", "0.433", "-0.203"],
    ["Energy MAE, 0-0.025 bin", "26.0", "11.0", "-15.0"],
    ["Energy MAE, &gt;0.3 bin", "124.3", "84.3", "-40.0"],
], [62 * mm, 28 * mm, 28 * mm, 24 * mm], align_right=(1, 2, 3)))
add(P("Energy error grows sharply with distance from the hull: trustworthy below "
      "0.1 eV/atom (11-19 meV/atom), but 97 meV/atom above 0.3 eV/atom, which is why the "
      "product refuses to rule on candidates in that range.", "body"))
add(P("A second finding settled a design question: relaxing every competing phase with the "
      "engine (mode b) makes hull-distance error <i>worse</i> by 1.9 [0.8, 3.2] meV/atom than "
      "placing the engine's energy on the DFT hull (mode a). On new materials the error belongs "
      "to the new structure and does not cancel against competitors. Mode (a) is used, and it "
      "needs no competitor relaxations at all.", "body"))

add(PageBreak())

# ------------------------------------------------------------------------------- 3
add(P("3. Locked WBM test - the one-time evaluation", "h1"))
add(P("Source: <font face='Courier'>reports/final_test.md</font>. Opened once on "
      "2026-09-12. 3,999 usable relaxations, 1 rejected by the guard. Every rule was fitted on "
      "the calibration set before this set was touched.", "small"))
add(table([
    ["Routing quantity", "Value"],
    ["n", "3,999"],
    ["likely stable", "224"],
    ["likely unstable", "2,146"],
    ["send to DFT", "1,629"],
    ["precision of 'likely stable'", "0.960 [0.93, 0.98] - target 0.90"],
    ["NPV of 'likely unstable'", "0.988 [0.984, 0.993] - target 0.95"],
    ["share sent to DFT", "0.407"],
    ["truly stable found as 'likely stable'", "0.352"],
    ["truly stable wrongly called 'likely unstable'", "0.041"],
], [72 * mm, 62 * mm], bold_rows=(5, 6)))
add(P("<b>Both targets were met out of sample</b>, and precision came in above its calibration "
      "value rather than below it. This is the single strongest result in the project.", "body"))
add(P("Energy error by hull bin (test set)", "h2"))
add(table([
    ["Hull bin (eV/atom)", "n", "Energy MAE", "median |err|", "trimmed mean"],
    ["&lt;0", "611", "15.3 [13.0, 18.5]", "8.1", "10.2"],
    ["0-0.025", "416", "11.0 [9.7, 12.5]", "6.7", "8.1"],
    ["0.025-0.1", "1,120", "14.1 [13.3, 15.1]", "9.3", "11.3"],
    ["0.1-0.3", "1,334", "30.2 [27.6, 32.9]", "16.4", "20.0"],
    ["&gt;0.3", "518", "86.7 [73.0, 103.1]", "32.9", "51.5"],
], [32 * mm, 16 * mm, 38 * mm, 26 * mm, 26 * mm], align_right=(1,)))

# ------------------------------------------------------------------------------- 4
add(P("4. Unseen real materials - the hardest test", "h1"))
add(P("Source: <font face='Courier'>reports/unseen_test.md</font>. 325 real Materials Project "
      "materials that cannot be in the engine's MPtrj training data, each reached the way a user "
      "reaches a candidate - a known parent prototype plus one element substitution - and scored "
      "end to end through the product, never through a suite.", "small"))
add(table([
    ["Quantity", "Locked WBM test", "This unseen set", "Reweighted to<br/>WBM bin mix"],
    ["precision of 'likely stable'", "0.96 [0.93, 0.98]<br/>(215/224)",
     "1.00 [0.85, 1.00]<br/>(22/22)", "1.00 [1.00, 1.00]"],
    ["NPV of 'likely unstable'", "0.988 [0.983, 0.992]<br/>(2121/2146)",
     "0.947 [0.823, 0.994]<br/>(36/38)", "0.980 [0.945, 1.000]"],
    ["share sent to DFT", "0.407", "0.815", "0.793 [0.729, 0.851]"],
    ["prevalence of truly stable", "0.153", "0.274", "0.153"],
], [46 * mm, 38 * mm, 38 * mm, 38 * mm]))
add(P("<b>Energy accuracy survives on real chemistry</b> - 7.1 meV/atom MAE in the below-hull "
      "bin where the structure was found correctly. <b>The decision rates are not "
      "distinguishable from WBM's</b>, but only because 22 and 38 calls cannot tell them apart; "
      "this is an absence of evidence, not evidence of equivalence.", "body"))
add(P("The finding that matters most, though, is about <i>coverage</i> rather than accuracy: "
      "the share of candidates sent to DFT doubled, from 41% to 82%.", "body"))
add(note("<b>Why the DFT share doubled - the central structural finding of this project.</b> "
         "Certified thresholds are per chemistry family, and a family with no certified "
         "threshold can never receive that label whatever the engine predicts. The locked WBM "
         "test set is 53% f-electron, and f-electron was the <i>only</i> family in which a "
         "'likely stable' threshold could be certified at all. What Materials Project actually "
         "adds is complex oxides and halides - 48% and 12% of this set, against 5% and 5% of "
         "WBM - and neither family had any certified threshold. <b>The published precision was "
         "measured almost entirely on a chemistry that barely appears in real use.</b> "
         "Test 7 is the direct response to this."))
add(P("Structure-finding rate - measured here for the first time", "h2"))
add(P("A product outcome rather than a diagnostic: if the relaxation lands somewhere else, "
      "every number attached to it describes a material the user did not ask about. Nothing in "
      "the WBM numbers speaks to this, because a WBM candidate starts from WBM's own initial "
      "structure.", "body"))
add(table([
    ["Hull bin", "n", "found the target structure", "relaxation left its start"],
    ["&lt;0", "89", "0.89 [0.82, 0.96]", "11%"],
    ["0-0.025", "83", "0.86 [0.78, 0.93]", "16%"],
    ["0.025-0.1", "105", "0.74 [0.67, 0.83]", "26%"],
    ["0.1-0.3", "32", "0.94 [0.84, 1.00]", "6%"],
    ["&gt;0.3", "16", "0.38 [0.12, 0.62]", "50%"],
    ["all", "325", "0.81 [0.77, 0.85]", "18%"],
], [26 * mm, 16 * mm, 48 * mm, 40 * mm], align_right=(1,), bold_rows=(6,)))
add(P("The 0.38 rate above 0.3 eV/atom is the real justification for the product's refusal to "
      "rule in that range - not the energy error, which had been the stated reason.", "body"))

add(PageBreak())

# ------------------------------------------------------------------------------- 5
add(P("5. Polymorph ranking", "h1"))
add(P("Source: <font face='Courier'>reports/polymorph.md</font>. 297 Materials Project "
      "compositions with 3-8 known polymorphs inside a 0.2 eV/atom window. A scientist rarely "
      "asks whether one exact structure is stable - they ask which form of a composition wins.", "small"))
add(table([
    ["Quantity", "Value", "Verdict"],
    ["ground state ranked first", "0.69 [0.63, 0.74]", "use with caution"],
    ["Spearman rho of the full ordering", "0.66 [0.60, 0.71]", "use with caution"],
    ["error on energy gaps from the ground state", "19.4 [17.3, 21.7] meV/atom", "trustworthy"],
    ["... median |error|", "8.2 [7.2, 9.0] meV/atom", "-"],
], [62 * mm, 48 * mm, 32 * mm]))
add(P("Random guessing would be right about 26% of the time, so 0.69 is real skill. But the "
      "result is strongly conditional on difficulty: where the DFT gap to the runner-up is under "
      "10 meV/atom, the ground state is picked first only 0.55 [0.47, 0.62] of the time - close "
      "to a coin flip, and below the engine's own error on new materials. Above a 50 meV/atom "
      "gap it reaches 0.87.", "body"))
add(note("<b>In 14% of compositions the relaxation drove two distinct forms into the same "
         "structure.</b> Their relative ranking is meaningless whatever the energies say, and a "
         "product that reports an ordering without disclosing this is reporting noise as a "
         "result. Also: these are known materials the engine trained on, so this measures "
         "ranking skill on material it has already seen."))

# ------------------------------------------------------------------------------- 6
add(P("6. Cost-based operating point", "h1"))
add(P("Source: <font face='Courier'>reports/costs.md</font>. Computed on the 3,998 usable WBM "
      "calibration structures; the locked test set is never re-optimised against.", "small"))
add(P("<b>Threshold -35 meV/atom</b>: precision 0.94 [0.91, 0.97], recall 0.45 [0.42, 0.49], "
      "NPV 0.910, DAF 6.18. 294 of 3,998 candidates called stable, 17 of them wrong, and 333 "
      "stable materials missed.", "body"))
add(note("<b>These three cost coefficients are not the same kind of number, and the report is "
         "explicit about it.</b> A wasted lab test = 1 is a normalisation baseline, fixed by "
         "definition. A missed stable material = 0.11 is <i>policy-derived, not empirical</i>: it "
         "is the ratio implied by the already-frozen 90% precision target, (1-0.9)/0.9, not a "
         "measurement of what a missed material costs. cost_dft = 0.02 is an order-of-magnitude "
         "estimate whose denominator - what one synthesis and characterisation attempt actually "
         "costs - has no defensible source in this project. Conclusions depending on it should be "
         "reported across 0.005-0.1. The sensitivity table, not the point estimate, is the "
         "trustworthy part of that page."))
add(P("Read the other way, the 90% precision target is itself a cost claim: it assumes a wasted "
      "lab test is nine times worse than missing a stable material. If that is not the view, the "
      "target should move, not just the threshold.", "body"))

add(PageBreak())

# ------------------------------------------------------------------------------- 7
add(P("7. Oxide and halide calibration - new, 17 September 2026", "h1"))
add(P("Run in this session. A new calibration task built to answer the coverage gap that test 4 "
      "exposed: 4,000 oxide and 3,500 halide calibration candidates, drawn only from pool ids the "
      "original split never used, with 8,000 prior ids excluded and 655 candidates dropped for "
      "sharing a reduced formula with a locked-test id. 15,000 jobs, 0 failures.", "small"))
add(P("Before this run, oxide (n=185) and halide (n=143) certified <b>nothing</b> on either "
      "side - every candidate in roughly 60% of real MP additions went to DFT by default. The "
      "question was whether more data would fix that.", "body"))
add(table([
    ["Family", "n usable", "base rate", "stable side", "unstable side"],
    ["oxide", "3,994", "0.112", "not certified",
     "+0 meV<br/>NPV 0.9781, CP-lower 0.9692"],
    ["halide", "3,500", "0.232", "not certified",
     "+0 meV<br/>NPV 0.9644, CP-lower 0.9516"],
], [24 * mm, 22 * mm, 22 * mm, 30 * mm, 60 * mm]))
add(P("<b>The unstable side now certifies for both families.</b> Routing impact: 88.1% of oxide "
      "candidates and 74.7% of halide candidates can be discarded without DFT, against roughly "
      "100% going to DFT before.", "body"))
add(P("The stable side failed for both - but for two different reasons, and the distinction "
      "decides what to do next:", "h2"))
add(table([
    ["Family", "Best point precision", "CP-lower", "Diagnosis", "What would fix it"],
    ["halide", "0.9401 (t=-70 meV)", "0.8803",
     "<b>Sample-size limited.</b> True precision is already above the 0.90 target; only the "
     "confidence bound falls short.",
     "~1.8x more halide calibration structures (~6,300 vs 3,500). The pool holds 10,095."],
    ["oxide", "0.8798 (t=-30 meV)", "0.7938",
     "<b>Precision limited.</b> Point precision peaks below target, so the bound converges "
     "to something under 0.90 regardless of n.",
     "Nothing, at 0.90. It certifies at a 0.80 target (t=-20 meV); 0.85 does not certify."],
], [18 * mm, 30 * mm, 18 * mm, 50 * mm, 52 * mm]))
add(note("<b>A satisfied NPV target is not the same as keeping your discoveries.</b> Both "
         "families clear NPV 0.95, but because the base rates are low, discarding 88.1% of oxide "
         "candidates still loses <b>17.3% of all truly stable oxides</b> (77 of 446); halide "
         "loses 11.4% (93 of 813). Both numbers should be quoted whenever this threshold is "
         "proposed for routing."))
add(P("A methodological caution came out of this run", "h2"))
add(P("The calibration was first run on the wrong engine - MACE-MP-0 rather than the production "
      "MACE-MPA-0 - because <font face='Courier'>HARNESS_MODEL</font> defaults to the former when "
      "unset, and the run still reported zero failures. On that weaker engine, halide's precision "
      "ceiling looked like 0.8313 and the conclusion would have been that <i>neither</i> family "
      "could ever be certified. The production engine is far more accurate on this chemistry "
      "(halide MAE 27.9 vs 59.9 meV/atom; over-stabilisation -10.9 vs -44.8), and that moved "
      "halide's ceiling above target. <b>A certification verdict cannot be generalised across "
      "engines.</b>", "body"))

add(PageBreak())

# ----------------------------------------------------------------------------- 8, 9
add(P("8. Energy-plausibility guard", "h1"))
add(P("Source: <font face='Courier'>reports/guard_fix.md</font>.", "small"))
add(P("One converged relaxation with a physically impossible energy - <b>-1131.01 eV/atom</b> "
      "against an MP reference of -4.09 - was being averaged into the reported statistics. It had "
      "converged cleanly: max stress 0.0096 GPa inside the 0.01 limit, final fmax 0.0018 eV/A "
      "inside the 0.01 limit, and it even matched the expected structure. The relaxation had "
      "fallen into a spurious short-range minimum of the model's potential-energy surface, just "
      "wide enough to keep the nearest-neighbour ratio above the collapse cut at 0.514. Neither "
      "existing guard - convergence, or minimum interatomic distance - could see it, and a single "
      "row dominated every mean it entered. Two more results in the same class were found by "
      "sweeping the whole database.", "body"))
add(P("Nothing was loosened to produce the corrected numbers: no settings tag changed, no "
      "tolerance moved, no hard case was dropped. The guard only ever moves a result from "
      "<i>scored</i> to <i>counted-and-excluded</i>.", "body"))

add(P("9. Training-data leakage check - SevenNet-Omni", "h1"))
add(P("Source: <font face='Courier'>reports/leakage_check.md</font>. SevenNet-Omni outscored the "
      "adopted engine on the screening subset; this asks whether that win is real or an artifact "
      "of WBM structures being in its training data.", "small"))
add(table([
    ["Portion of training data", "WBM-filtered?", "Evidence"],
    ["OMat24 (~46%)", "yes", "dataset authors filtered on WBM prototype labels and say so"],
    ["sAlex (3D Alexandria)", "yes", "same"],
    ["Alexandria 1D/2D, MatPES, MAD (~1%)", "not documented", "a 3D WBM prototype in a 1D/2D "
     "trajectory is structurally unlikely, but unverified"],
], [50 * mm, 28 * mm, 82 * mm]))
add(P("<b>Verdict: the win is probably real, but the engine was not adopted.</b> Its registry "
      "status stays 'unverified' - no longer unexamined, but honest. Settling it needs no "
      "relaxations and no GPU: compute AFLOW protostructure labels for the 8,000 WBM ids in the "
      "split and intersect them with the undocumented training portions.", "body"))
add(note("<b>A definitional trap worth knowing.</b> 'Compliant' in this project means training "
         "data verified free of WBM, which is this project's definition and not Matbench "
         "Discovery's. By the leaderboard's stricter rule - train on the sanctioned set only - "
         "MACE-MPA-0 and eSEN-30M-OAM are non-compliant too, despite being marked True here. "
         "That column must not be read as a leaderboard compliance flag."))

# ------------------------------------------------------------------------------ 10
add(P("10. Reference data collection - new, 17 September 2026", "h1"))
add(P("Source: <font face='Courier'>reference_data/COVERAGE.md</font>, "
      "<font face='Courier'>SOURCES.md</font>. Citable experimental data for property suites to "
      "be validated later. Gathering and verification only - no simulation was run and no "
      "existing suite was modified.", "small"))
add(table([
    ["Property", "Rows", "Materials", "Source", "Licence"],
    ["Oxide lattice constants (RT)", "48", "22 formulae<br/>30 phases",
     "Crystallography Open Database", "CC0 - commercial OK"],
    ["Atomic oxygen erosion", "41", "39 polymers",
     "NASA/TM-2006-214482 (MISSE 2 PEACE)", "US Gov - public domain"],
    ["Outgassing (TML/CVCM)", "0", "-", "NASA database - blocked by CAPTCHA; "
     "RP-1124 scans OCR to noise", "-"],
], [42 * mm, 14 * mm, 26 * mm, 46 * mm, 34 * mm]))
add(P("<b>The cross-check result is the useful output.</b> Where two independent experiments of "
      "the same phase disagree by x, chasing simulation accuracy below x is not measurable. "
      "Across 8 oxide phases with two or more independent determinations, the spread in the "
      "lattice parameter is a <b>median 926 ppm (0.093%) and at worst 1,991 ppm (0.199%)</b>. "
      "So a simulation targeting 1% sits comfortably above the experimental floor, and targeting "
      "better than about 0.1% is chasing noise between experiments.", "body"))
add(P("Two data-integrity findings came out of building it:", "h2"))
add(P("<b>The Materials Project was deliberately excluded as a source.</b> Its elasticity data is "
      "DFT-computed, and the production engine is trained on MP data, so using it as a reference "
      "would measure agreement with the engine's own training distribution rather than with "
      "reality. Independent experimental values are the only ones that add information.", "body"))
add(P("<b>COD needs curation, not just querying.</b> Raw formula matching returned 100 rows, of "
      "which 52 were contaminated. COD's structured pressure field is null even for explicit "
      "diamond-anvil studies - one ZnO series records a cell temperature and no pressure at all, "
      "while its title says 'High-pressure X-ray investigation'. Compression and in-situ heating "
      "series masquerade as repeat measurements, formula matching pulls in unrelated compounds "
      "(one SiO2 hit was a zeolite), and doped samples sit under the parent formula - the first "
      "Al2O3 hit is ruby.", "body"))
add(P("Licence position: the generated tables, schemas and prose are CC BY 4.0 "
      "(<font face='Courier'>reference_data/LICENSE</font>); the loader and extractors are "
      "Apache-2.0 with the rest of the project's code. Two public-domain sources are vendored "
      "verbatim under <font face='Courier'>reference_data/raw/</font> so the build reproduces "
      "offline - the NASA memorandum and the cached COD responses - and both are excluded from "
      "this project's grants, keeping their own status.", "body"))
add(note("<b>Licensing trap, verified at source.</b> The NIST Chemistry WebBook is Standard "
         "Reference Database 69 and is <i>copyrighted</i> - 'All rights reserved', secured under "
         "15 U.S.C. 290e - even though the numbers are free to read, and NIST reserves the right "
         "to charge for access in future. Individual facts are not copyrightable but the "
         "compilation is, so from any NIST SRD product this collection stores a small number of "
         "cited values and never a bulk table. No NIST SRD data is used in any shipped table."))

add(PageBreak())

# ---------------------------------------------------------------------------- 11
add(P("11. Licensing and attribution audit", "h1"))
add(P("Source: <font face='Courier'>reports/licensing.md</font>. What this repository uses, what "
      "it redistributes, what each licence requires, and whether it complies. Written for "
      "publication review. Not legal advice; close judgements are flagged as close.", "small"))
add(P("What is actually redistributed", "h2"))
add(P("'Redistributes' means a file in the repository contains a third party's values, not just "
      "code that fetches them. That distinction does most of the work here.", "body"))
add(table([
    ["Asset", "Licence", "Redistributed?", "Position"],
    ["Materials Project - ids, formulas,<br/>hull distances, PBE energies",
     "CC BY 4.0", "yes - derived values<br/>throughout data/ and reports/",
     "Adaptations, so attribution required"],
    ["WBM / Matbench Discovery",
     "CC BY 4.0", "ids only - structures and<br/>energies are gitignored",
     "Fine; the reader downloads from figshare"],
    ["MPtrj (engine training set)", "MIT", "no - never downloaded",
     "Cited only"],
    ["Experimental lattice constants<br/>(40 + 29 rows)", "journal copyright",
     "yes - transcribed with citation", "The closest call in the document"],
    ["Model checkpoints", "MIT, except eSEN<br/>(OMat24, gated)", "no - URL + SHA-256 only",
     "Must stay that way"],
], [44 * mm, 24 * mm, 46 * mm, 54 * mm]))
add(P("The experimental tables are the one close call. Individual measured values are facts and "
      "are not copyrightable, but copyright can reach the <i>selection and arrangement</i> of a "
      "table, and two specific tables are reproduced substantially. The assessment is low risk and "
      "standard scientific practice - these are benchmark reference sets that exist to be reused, "
      "and both files carry the full citation. Reducing the risk to zero would mean shipping a "
      "script that reconstructs them from papers the reader fetches, which costs reproducibility "
      "for anyone without journal access. Deliberately not done.", "body"))
add(P("Dependencies - one matters commercially", "h2"))
add(P("Every dependency is permissive <b>except ASE, which is LGPL-2.1-or-later</b>. LGPL's "
      "obligations attach to <i>distributing</i> the library, which this repository does not do: "
      "it declares a dependency and the user's package manager fetches it. Code that imports ASE "
      "is not made copyleft by that. The obligation bites on shipping a bundle - a PyInstaller "
      "binary, a Docker image, a vendored wheel - at which point the recipient must be able to "
      "replace their copy of ASE. Nothing to do for this repository; it is the one dependency to "
      "plan around for a commercial product.", "body"))
add(P("Gaps found, and their current state", "h2"))
add(table([
    ["Requirement", "At audit", "Verified 17 Sep 2026"],
    ["Materials Project attribution and licence notice", "MISSING - the only real gap",
     "<b>Closed</b> - NOTICE and README block present"],
    ["WBM / Matbench Discovery attribution", "missing (same fix)", "<b>Closed</b>"],
    ["A licence for this project's own code", "none",
     "<b>Closed</b> - Apache-2.0 at root"],
    ["Experimental tables: citation", "present", "unchanged"],
    ["Checkpoints not redistributed; gated eSEN respected", "yes", "unchanged"],
    ["Nothing third-party vendored", "yes", "unchanged"],
], [58 * mm, 46 * mm, 64 * mm]))
add(P("The report offered five licensing options and recommended <b>Apache-2.0 for the code and "
      "CC BY 4.0 for reports/ and data/</b> - matching the inputs, giving corporate users the "
      "patent grant that bare MIT does not, and keeping the inspectability that publishing is "
      "for. That recommendation was adopted: LICENSE (Apache-2.0), NOTICE with the licence split, "
      "and data/LICENSE and reports/LICENSE (CC BY 4.0) are all present.", "body"))
add(note("<b>A permissive licence is not a moat, and the report says so plainly.</b> The code is "
         "a harness whose entire value is that the numbers can be checked, so a licence that "
         "prevents checking removes the reason to publish. No dependency is copyleft-in-"
         "distribution and no input dataset requires share-alike, so nothing forced the choice - "
         "Apache-2.0 does not stop a competitor using the harness, and no permissive licence "
         "would."))

add(PageBreak())

# ---------------------------------------------------------------------------- 12
add(P("12. Pre-publication audit", "h1"))
add(P("Source: <font face='Courier'>reports/publish_audit.md</font>. Audit of the repository "
      "before it was made public. <b>At audit</b> (commit 82a77c1): 28 commits across 2 branches, "
      "127 tracked files - those counts are left unedited in the source report as the record of "
      "what was actually scanned. <b>As published</b> it has 30 commits and 141 tracked files, "
      "and the commit author email has been rewritten.", "small"))
add(P("Credential sweep - scope, then result", "h2"))
add(P("The scope is the point. The sweep covered all 28 commits on all branches, <b>all 437 "
      "objects in the object database</b> including 277 blobs - a superset of 'every file in "
      "every commit', because it includes objects no ref points at - 0 dangling blobs, the reflog "
      "(58 entries, all already on refs), and 34,035 working-tree files including caches.", "body"))
add(table([
    ["Check", "Result"],
    ["MP_API_KEY value anywhere in git history", "<b>0 blobs</b> (searched by exact value, all 277)"],
    ["MP_API_KEY value in the working tree", "1 file: .env - gitignored, never tracked"],
    [".env (any flavour) in history", "no - only .env.example, empty placeholders"],
    ["Hugging Face token", "none - the gated checkpoint left no token behind"],
    ["Private keys, cloud creds, PATs, JWTs, DB strings", "none"],
    ["URLs with embedded credentials", "none"],
], [78 * mm, 88 * mm]))
add(P("gitleaks reported exactly one history finding and it is a false positive: the string "
      "<font face='Courier'>MP2020Compatibility</font> in a code comment, long and mixed-case "
      "enough to trip a generic entropy rule. Roughly 40 further working-tree hits are all inside "
      "gitignored third-party cache.", "body"))
add(P("The audit also disclosed a mistake it made itself: its own pattern matcher echoed a "
      "13-character prefix of the live API key into the session transcript. 19 of 32 characters "
      "remained unknown, so the risk was low - and it recommended rotating the key anyway, on the "
      "grounds that the value of an audit is not having to reason about how low 'low' is.", "body"))
add(P("Honesty of the public claims", "h2"))
add(P("Stale reports were stamped rather than quietly deleted: a 'not the production engine' "
      "banner on the baseline scorecard, a 'superseded' banner on the pre-guard Phase 0 report, "
      "and a placeholder-costs warning on the cost page. <b>All three banners are emitted by the "
      "generators, not pasted into the files</b>, so regenerating a report cannot silently drop "
      "them. Every README figure is a pessimistic bound linked to the section it came from.", "body"))
add(P("The finding that matters most - and it is a failure", "h2"))
add(note("<b>A personal email address reached the published repository.</b> The repository was "
         "pushed and made public on 2026-09-14. About twenty minutes later an independent "
         "re-verification found the owner's personal address in the published <i>history</i> - two "
         "occurrences inside the audit document itself, in the commit where it quoted the address "
         "while explaining the email decision. A later commit reworded those lines, so the tip was "
         "clean and <b>every check in the chain was blind to it</b>: the verification step read "
         "commit metadata, which was correct; the preflight used git grep, which reads tracked "
         "content at HEAD, where the address no longer appeared; and gitleaks does not flag email "
         "addresses at all, so its green tick was accurate and irrelevant. Nothing in the chain "
         "scanned historical file content. That is the defect."))
add(P("<b>Response.</b> The repository was set private within an exposure window of roughly 20 "
      "minutes, with 0 forks, 0 stars and 0 watchers. A second filter-branch pass redacted the "
      "string across history and commit messages, verified to 0 matches across all 513 objects "
      "reachable from both branches, with the HEAD tree hash and the full 142-file manifest "
      "unchanged - only the one historical commit's tree moved. The remote was replaced by "
      "delete-and-recreate rather than force-push, because GitHub keeps orphaned commits "
      "reachable by SHA after a force-push.", "body"))
add(P("<b>Fix.</b> The preflight script now scans every blob, tree and commit reachable from HEAD, "
      "the branches and the tags - file content <i>and</i> commit metadata - rather than the "
      "working tree alone. It was regression-tested against the pre-redaction history: the old "
      "check reports clean, the new one names the offending blob and file and exits 1.", "body"))
add(P("<b>The general lesson, worth more than the specific fix: a check that reads HEAD cannot "
      "clear a history. Anything published as history has to be audited as history.</b>", "body"))
add(P("Left open deliberately", "h2"))
add(table([
    ["Item", "Status"],
    ["Install gitleaks locally", "not done - CI covers it"],
    ["Drop data/auto_pairs_v1.json (1.31 MB, superseded)",
     "<b>kept</b> - results.parquet holds results for 1,982 v1-only pairs; deleting it would "
     "orphan them"],
    ["Replace the two experimental CSVs with a reconstruct-from-paper script",
     "not done - costs reproducibility, assessed low risk"],
    ["Expire refs/original/", "kept as the in-repo rollback path; not published by an ordinary push"],
], [66 * mm, 100 * mm]))

add(PageBreak())

# -------------------------------------------------------------------- cross-cutting
add(P("What the tests say when read together", "h1"))
add(P("1. The product is accurate where it matters, and honest about where it is not", "h2"))
add(P("Energy error is trustworthy below 0.1 eV/atom from the hull (7-14 meV/atom on real "
      "unseen chemistry) and untrustworthy above 0.3 eV/atom (87-291 meV/atom). Both decision "
      "targets were met out of sample on the locked test set, with precision 0.960 against a "
      "0.90 target.", "body"))

add(P("2. Coverage, not accuracy, is the binding constraint", "h2"))
add(P("The single most consequential finding across all ten tests is that the headline precision "
      "was measured on a chemistry that barely appears in real use. The locked WBM test is 53% "
      "f-electron and f-electron was the only family that could certify a stable threshold; what "
      "Materials Project actually adds is oxides and halides. On real unseen materials the DFT "
      "share doubled to 82% for exactly this reason. Test 7 addressed it directly and got a "
      "split answer: halide is fixable with about 1.8x more calibration data, oxide is not "
      "fixable at a 0.90 target at all.", "body"))

add(P("3. Structure-finding is a distinct failure mode, and it was invisible until recently", "h2"))
add(P("The pipeline returns the material actually asked for 0.81 [0.77, 0.85] of the time, and "
      "only 0.38 [0.12, 0.62] of the time above 0.3 eV/atom. No WBM-derived number speaks to "
      "this, because a WBM candidate starts from WBM's own structure. Where the relaxation lands "
      "elsewhere, energy error is roughly 20x higher (414.6 vs 24.9 meV/atom in the top bin).", "body"))

add(P("4. Several headline numbers rest on assumptions that are not measurements", "h2"))
add(P("The cost coefficient for a missed stable material is derived from the precision target "
      "rather than measured, so the two cannot be used to justify each other. The compute-to-"
      "experiment cost ratio has no sourced denominator. 'Compliant' means something narrower "
      "here than on the Matbench Discovery leaderboard. Each of these is documented at its "
      "source, and none should be quoted as established.", "body"))

add(P("5. Methodological guards that earned their place", "h2"))
add(P("Three habits caught real errors during this work. <b>Clopper-Pearson rather than "
      "bootstrap</b> on rates whose sample could be all-correct - a bootstrap was caught "
      "producing a false verdict on an error-free sample. <b>Pessimistic-end verdicts</b>, which "
      "keep a favourable point estimate from overstating a thin sample. <b>Counting rejected "
      "results rather than dropping them</b> - the energy-plausibility guard moves a result from "
      "scored to counted-and-excluded, so exclusions can never quietly improve a mean.", "body"))

add(P("6. The same discipline was applied to what gets published, and it still failed once", "h2"))
add(P("The publication audits are cut from the same cloth as the tests: define the scope "
      "explicitly, then report what was found rather than what was hoped for. The credential "
      "sweep covered every object in the database rather than every file at HEAD, and found "
      "nothing. The licensing review named one real gap - missing Materials Project attribution - "
      "rather than declaring compliance, and that gap is now closed under Apache-2.0 and CC BY "
      "4.0.", "body"))
add(P("And it still missed something: a personal email address reached the public repository "
      "inside history, because every check in the chain read HEAD or commit metadata and none "
      "read historical file content. The exposure was twenty minutes with no forks. The failure "
      "is recorded in the audit document in full, alongside the fix, rather than being quietly "
      "corrected - which is the same convention the test reports follow when a result is "
      "unflattering.", "body"))

add(Spacer(1, 10))
add(P("Locked and unopened as of this document: the original WBM locked test set (4,000 ids) has "
      "been opened once, on 2026-09-12. The two per-family locked test halves created on "
      "2026-09-17 - 2,000 oxide and 2,000 halide - remain closed, and no code path in this "
      "session passed unlock=True.", "small"))

doc = SimpleDocTemplate(
    str(OUT), pagesize=A4,
    leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
    title="Materials Harness - test results", author="materials-harness",
    subject="Every test run to date and its results",
)
doc.build(F, onFirstPage=chrome, onLaterPages=chrome)
print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
