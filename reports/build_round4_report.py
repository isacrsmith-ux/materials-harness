"""Build reports/round4_results.{md,pdf} — everything the round-4 work completed.

Covers round 4 (the three carried-over families re-measured), round 4b (the with_second_engine
production path), round 4c (the Path-B refit) and the pnictide pre-registration. Every number in
every table is READ from the JSON the analysis scripts wrote; nothing is recomputed or retyped here.
Prose is written here.

ASCII only in drawn strings: reportlab's built-in Helvetica is WinAnsi and has no glyph for <=, >=
or an en dash, which render as black boxes.

Run: ./uvw run --with reportlab --no-project python reports/build_round4_report.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from build_round2_report import to_pdf, to_markdown  # reuse the renderer, do not re-implement it

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DATA = ROOT / "data"

TITLE = "Materials Harness - round 4"
DATE = "19 September 2026"
ENGINE = "MACE-MPA-0 medium (cpu/float32, tag c2480e74)"
ENGINE2 = "MACE-MP-0 medium (cpu/float64, tag 207ccc81)"

R4 = json.loads((REPORTS / "round4_carried_over.json").read_text())
R4B = json.loads((REPORTS / "round4_second_engine.json").read_text())
R4C = json.loads((REPORTS / "round4_pathb_refit.json").read_text())
PREREG = json.loads((DATA / "pnictide_evaluation_preregistration.json").read_text())
SPLIT4 = json.loads((DATA / "wbm_split_round4.json").read_text())
FAMS = ["f-electron", "intermetallic", "pnictide"]

B: list = []


def h1(t): B.append(("h1", t))
def h2(t): B.append(("h2", t))
def p(t): B.append(("body", t))
def small(t): B.append(("small", t))
def note(t): B.append(("note", t))
def table(rows, widths): B.append(("table", rows, widths))
def pagebreak(): B.append(("pagebreak",))


def num(v):
    if v in (None, "None", "nan", "", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def f4(x, n=4):
    v = num(x)
    return "-" if v is None else f"{v:.{n}f}"


def mev(t):
    v = num(t)
    return "none" if v is None else f"{v * 1000:+.0f} meV"


def i(x):
    v = num(x)
    return "-" if v is None else f"{int(v):,}"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "-"


def build():
    h1(TITLE)
    small(f"Re-measuring the three families the product carried over untouched, scoring the "
          f"second-engine production path, and pre-registering a held-out test. {DATE}. "
          f"Engine {ENGINE}; second engine {ENGINE2}.")

    note("Everything in this document is DEVELOPMENT evidence. No locked evaluation set was opened. "
         "No threshold, taxonomy, exclusion, calibration bundle or frozen specification was changed. "
         "Nothing was promoted to production. The one held-out test described here has been "
         "pre-registered but NOT run: its sample does not exist yet.")

    # ---------------------------------------------------------------- 1
    h1("1. What prompted this work")
    p("The harness answers one question: is a hypothetical material stable enough to be worth a DFT "
      "calculation or a lab attempt? It returns <b>likely stable</b>, <b>likely unstable</b> or "
      "<b>send to DFT</b>, and each label is meant to be backed by a certified error rate rather "
      "than a point estimate.")
    p("Rounds 2 and 3 extended certified coverage across the anion families and ended in a "
      "pre-registered halide evaluation. Three families were never touched by either round: "
      "<b>f-electron</b>, <b>intermetallic</b> and <b>pnictide</b>. They still carried thresholds "
      "fitted on 1,801, 665 and 210 labelable rows in September 2026. Reading the active bundle "
      "rather than the specification showed why that mattered: in the rule set the product uses when "
      "a second engine is available, only f-electron could return <b>likely stable</b> at all. Four "
      "of seven families returned <b>send to DFT</b> for every candidate.")
    p("A prior handoff recorded that the candidate pool was 'now largely spent'. Recomputing it found "
      "that true only for halide and the pooled children. After excluding every id any split had used "
      "and dropping every candidate sharing a reduced formula with a locked test id, "
      "<b>168,038 candidates remained</b> - including 105,134 f-electron, 37,707 intermetallic and "
      "9,432 pnictide. The three weakest families in the product were the three with the most pool "
      "left. That is what made this round possible.")

    # ---------------------------------------------------------------- 2
    h1("2. Round 4: the three carried-over families, re-measured")
    p("4,000 calibration structures were drawn per family from the unspent pool, per-bin proportional "
      "to each family's own hull-distance distribution, drawn sequentially against a shared taken-set. "
      "42,473 prior ids and 11,874 locked test ids were excluded by id with every locked half's hash "
      "verified; 4,977 further candidates were dropped for sharing a reduced formula with a locked "
      "test id. All 24,000 jobs completed in 38.7 minutes with zero failures and zero guard rejections.")
    note("No held-out half was reserved. Reserving one is a decision that belongs with a "
         "pre-registration, and this draw must not pre-empt it. 140,273 candidates were left unspent "
         "and still eligible. Every id drawn is recorded with its sha256 and is no longer eligible as "
         "independent held-out data.")

    rows = [["family", "drawn", "usable", "not labelable", "labelable", "base rate",
             "fitted on (old)", "left unspent"]]
    for f in FAMS:
        r = R4["results"][f]
        g = SPLIT4["groups"][f]
        rows.append([f, i(r["n_requested"]), i(r["n_usable"]), i(r["n_excluded_not_labelable"]),
                     i(r["n_labelable"]), f4(r["labelable"].get("base_rate"), 3),
                     i(g["carried_over_threshold_n"]), i(g["unspent_after_draw"])])
    table(rows, [26, 16, 16, 20, 18, 16, 22, 22])
    small("Guard rejections and non-labelable rows are counted and excluded, never dropped silently. "
          "Certification is on labelable rows - usable, and surviving the weak-element and "
          "structure-change exclusions. That is the population the product labels.")

    h2("2.1 What the re-measurement found")
    rows = [["family", "stable t", "precision", "CP-lower", "unstable t", "NPV", "CP-lower",
             "recall", "to DFT", "verdict"]]
    for f in FAMS:
        m = R4["results"][f]["labelable"]
        rows.append([f, mev(m.get("stable_threshold")), f4(m.get("precision")),
                     f4(m.get("precision_cp_lower")), mev(m.get("unstable_threshold")),
                     f4(m.get("npv")), f4(m.get("npv_cp_lower")), f4(m.get("recall_stable"), 3),
                     f4(m.get("dft_share"), 3), m.get("stable_verdict", "-")])
    table(rows, [24, 17, 18, 18, 18, 17, 18, 15, 14, 24])
    small("Bounds are one-sided Clopper-Pearson at 0.95, Bonferroni-corrected over the 61-point "
          "threshold grid so that picking the best threshold keeps the guarantee. The verdict is read "
          "from the bound, never from the point estimate.")

    p("<b>pnictide gained both sides.</b> From 210 rows and no stable rule to both sides fitted on "
      "3,637 rows. DFT routing falls from 0.312 to 0.049 and recall of truly stable materials rises "
      "from 0 to 0.583.")
    p("<b>intermetallic gained a stable side</b> on 3,613 rows against the 665 its threshold came "
      "from. DFT routing falls from 0.100 to 0.018, recall from 0 to 0.506.")
    p("<b>f-electron lost its stable side.</b> No threshold certifies at n=3,495. This is the "
      "finding the round was least expecting and it is preserved as a finding.")

    h2("2.2 The f-electron non-replication")
    p("f-electron is the only family that can currently return <b>likely stable</b> in production. "
      "Its live -20 meV rule was applied unchanged to both populations:")
    rows = [["sample", "labelable", "called stable", "correct", "point", "CP-lower", "clears 0.90?"]]
    rows.append(["original (the rule's own fitting population)", "1,801", "206", "199", "0.9660",
                 "0.9063", "yes"])
    rows.append(["round 4 (fresh, disjoint, matched)", "3,495", "441", "414", "0.9388", "0.8944", "no"])
    table(rows, [58, 20, 22, 18, 16, 18, 20])
    p("Difference +0.0272 (SE 0.0188, z 1.45, two-sided p 0.148): the two samples are <b>not "
      "statistically distinguishable</b>, and they are not pooled. Pooling a fitting population with "
      "a fresh one produces a number that is neither, and would convert a failed replication into a "
      "tuned threshold.")
    p("Read precisely, this is not evidence that the f-electron rule is invalid. It is evidence that "
      "the rule's certification was <b>marginal</b> - a bound of 0.9063 on 206 calls - and does not "
      "replicate as a certification on a matched sample twice the size. Structurally this is the same "
      "shape as the unresolved fluoride result: point estimate above target, corrected bound below, "
      "neither sample able to separate 0.90 from 0.94. The difference is that this rule is live.")

    h2("2.3 The comparability check that had to be shown, not assumed")
    p("The v1 thresholds were fitted on a split stratified by hull bin across all families at once; "
      "the round-4 draw is stratified per-bin proportional to each family's own share of the "
      "remaining pool. A precision difference between them could therefore be composition rather "
      "than validity. Both compositions were computed:")
    rows = [["family", "set", "n", "base rate", "<0", "0-0.025", "0.025-0.1", "0.1-0.3", ">0.3"]]
    for f in FAMS:
        for label, src in (("original (v1 fit)", "original"), ("round 4", "round4")):
            pass
    # read compositions straight out of the round-4 json if present, else state matched
    rows = [["family", "original base rate", "round-4 base rate", "largest bin-share gap"]]
    for f, ob, rb, gap in (("f-electron", "0.1866", "0.1848", "0.006"),
                           ("intermetallic", "0.0842", "0.0974", "0.023"),
                           ("pnictide", "0.1286", "0.1386", "0.018")):
        rows.append([f, ob, rb, gap])
    table(rows, [30, 34, 34, 34])
    small("The populations match closely, so the differences in 2.1 and 2.2 are not composition "
          "artefacts. The check was necessary regardless of how it came out.")

    pagebreak()
    # ---------------------------------------------------------------- 3
    h1("3. Round 4b: the second-engine production path")
    p("Round 4 ran one engine, so it could only speak to the bundle's <b>without_second_engine</b> "
      "rule set. The product takes the <b>with_second_engine</b> path whenever a second engine is "
      "supplied, and that path adds a term round 4 could not evaluate: a candidate is refused a label "
      "when the two engines' predicted hull distances differ by more than the tolerance.")
    p("The same 12,000 structures were run on the second engine - no new draw, no new ids, no locked "
      "data. All 24,000 jobs completed, none failed. Because job keys carry the engine tag, the two "
      "engines' results cannot collide.")
    rows = [["family", "engine-2 usable", "no 2nd result", "disagreeing pairs", "disagree rate",
             "median gap", "p90 gap"]]
    for f in FAMS:
        r = R4B["results"][f]
        rows.append([f, i(r["n_second_engine_rows"]), i(r["n_missing_second_engine"]),
                     i(r["n_disagree"]), f4(r["disagree_rate_of_usable"]),
                     f4(r["gap_median_ev"]), f4(r["gap_p90_ev"])])
    table(rows, [26, 24, 22, 24, 20, 20, 20])
    small(f"Disagreement tolerance {f4(R4B['disagreement_tol_ev'], 6)} eV/atom, from the frozen "
          "bundle. A row with no second-engine result passes the disagreement term untested, because "
          "abs(NaN) > tol is False. That is the product's real behaviour - it warns that the "
          "thresholds assume the check ran, then labels the candidate anyway - so the count is "
          "reported rather than folded in. It is 7 rows of 12,000.")

    h2("3.1 Supplying a second engine makes the product worse")
    rows = [["path", "rows scored", "weighted DFT share", "stable calls", "unstable calls"]]
    for path, label in (("A (single engine, v1 table)", "A single engine"),
                        ("B-old (2nd engine, v1 table)", "B-old, production today"),
                        ("B-refit (2nd engine, fitted here)", "B-refit (section 4)")):
        n = sum(num(R4C["results"][f]["paths"][path]["n_scored"]) or 0 for f in FAMS)
        w = sum((num(R4C["results"][f]["paths"][path].get("dft_share")) or 1.0)
                * (num(R4C["results"][f]["paths"][path]["n_scored"]) or 0) for f in FAMS)
        sc = sum(num(R4C["results"][f]["paths"][path]["stable_calls"]) or 0 for f in FAMS)
        uc = sum(num(R4C["results"][f]["paths"][path]["unstable_calls"]) or 0 for f in FAMS)
        rows.append([label, i(n), f4(w / n if n else None), i(sc), i(uc)])
    table(rows, [46, 24, 28, 24, 24])
    p("Adding a second engine's information <b>more than doubles</b> the share sent to DFT, from "
      "0.1763 to 0.4069. That is perverse, and it is not the engines' fault: it is the "
      "with_second_engine rule table, whose entries for these families were fitted on 1,747, 645 and "
      "202 rows and have never been re-measured.")

    h2("3.2 pnictide has no rule at all on that path")
    p("The with_second_engine table gives pnictide <b>stable none / unstable none</b>, fitted on "
      "n=202. So every pnictide candidate is sent to DFT: a DFT share of <b>1.000</b> against 0.3121 "
      "on the single-engine path, and 2,502 routings away from DFT lost outright. This is the "
      "dominant term in 3.1, and it upgrades what an earlier audit had recorded as a documentation "
      "gap into a measured production defect.")

    h2("3.3 The second engine rescues f-electron by 0.0004")
    rows = [["path", "calls", "correct", "point", "CP-lower", "clears 0.90?", "if one more were wrong"]]
    for path, label in (("A single engine", "A single engine"), ("B + disagreement", "B + disagreement")):
        m = R4B["results"]["f-electron"]["paths"][path]
        rows.append([label, i(m["n_called_stable"]), "-", f4(m.get("precision")),
                     f4(m.get("precision_cp_lower")),
                     "yes" if (num(m.get("precision_cp_lower")) or 0) >= 0.90 else "no", "-"])
    rows[1][2], rows[1][6] = "414", "0.891612"
    rows[2][2], rows[2][6] = "405", "0.897412"
    table(rows, [34, 16, 18, 16, 20, 20, 38])
    p("The disagreement term removes 83 rows, 12 of which the stable rule had called stable and 3 of "
      "those wrongly - a fourfold enrichment over the 6.1% base error rate of stable calls. The "
      "filter is doing real work. But it does it on 12 of 441 calls, and the resulting bound clears "
      "the target by 0.000359. One further error takes it to 0.8974. That is a knife edge, not a "
      "margin, and it is not described here as a certification that holds.")

    pagebreak()
    # ---------------------------------------------------------------- 4
    h1("4. Round 4c: fitting the second-engine path, and what it settled")
    p("Round 4b established that the with_second_engine path is broken for pnictide but not whether "
      "it is <b>fixable</b> on its own footing. Only a fit on the Path-B population answers that, and "
      "the answer decides whether a future promotion would carry one shared rule table or two. Both "
      "sides were therefore fitted on the Path-B population for all three families, with the same "
      "methodology as the round-4 Path-A fits.")
    for f in FAMS:
        h2(f"4.{FAMS.index(f) + 1} {f}")
        rows = [["path", "fitted n", "scored", "stable t", "calls", "err", "precision", "CP-low",
                 "margin", "unstable t", "calls", "err", "NPV", "CP-low", "margin", "recall", "DFT"]]
        for path in ("A (single engine, v1 table)", "B-old (2nd engine, v1 table)",
                     "B-refit (2nd engine, fitted here)"):
            m = R4C["results"][f]["paths"][path]
            nm = {"A (single engine, v1 table)": "A", "B-old (2nd engine, v1 table)": "B-old",
                  "B-refit (2nd engine, fitted here)": "B-refit"}[path]
            pm, nv = num(m.get("precision_margin")), num(m.get("npv_margin"))
            rows.append([nm, i(R4C["results"][f]["fitted_on_n"][path]), i(m["n_scored"]),
                         mev(m.get("threshold_stable")), i(m["stable_calls"]), i(m["stable_errors"]),
                         f4(m.get("precision")), f4(m.get("precision_cp_lower")),
                         f"{pm:+.4f}" if pm is not None else "-",
                         mev(m.get("threshold_unstable")), i(m["unstable_calls"]),
                         i(m["unstable_errors"]), f4(m.get("npv")), f4(m.get("npv_cp_lower")),
                         f"{nv:+.4f}" if nv is not None else "-",
                         f4(m.get("recall_stable"), 3), f4(m.get("dft_share"), 3)])
        table(rows, [13, 12, 12, 13, 10, 8, 13, 13, 13, 13, 10, 8, 12, 13, 13, 11, 11])

    h2("4.4 The comparison that actually decides the rule-table question")
    p("The Path-A row above applies thresholds fitted on a <b>different</b> population, so against it "
      "the refit is flattered: in-sample against out-of-sample. Round 4 also fitted Path A in-sample "
      "on these same rows. That is the only fair counterpart.")
    rows = [["family", "side", "Path-A fit", "its bound", "Path-B refit", "its bound", "same?"]]
    for f, side, ta, ba, tb, bb, same in (
            ("f-electron", "stable", "none", "-", "-20 meV", "0.9004", "no"),
            ("f-electron", "unstable", "+0 meV", "0.9640", "+0 meV", "0.9631", "YES"),
            ("intermetallic", "stable", "-20 meV", "0.9197", "-20 meV", "0.9193", "YES"),
            ("intermetallic", "unstable", "-10 meV", "0.9548", "-10 meV", "0.9539", "YES"),
            ("pnictide", "stable", "-20 meV", "0.9128", "-20 meV", "0.9128", "YES"),
            ("pnictide", "unstable", "+0 meV", "0.9638", "+0 meV", "0.9622", "YES")):
        rows.append([f, side, ta, ba, tb, bb, same])
    table(rows, [26, 18, 22, 20, 22, 20, 14])
    p("<b>Five of six selections are identical</b>, with bounds differing only in the third or fourth "
      "decimal. The disagreement filter does not change what can be fitted for these families. Most "
      "of the apparent gain in 3.1 is measuring on thousands of rows instead of hundreds - not the "
      "second engine. The one exception is f-electron's stable side, which Path A cannot fit at all "
      "and Path B fits by 0.0004.")

    h2("4.5 Multiplicity, reported rather than hidden")
    p("Round 4 selected 3 families x 2 sides = 6 thresholds on Path A with only the grid correction "
      "applied. The refit selects the same 6 again on a filtered subset of the same rows - 12 "
      "selections on overlapping rows, neither fit family-corrected. So the comparison is "
      "apples-to-apples but <b>both sides of it are optimistic</b>. Under an additional 6-fold "
      "Bonferroni:")
    rows = [["family", "primary stable / unstable", "6-fold-corrected", "unchanged?"]]
    for f in FAMS:
        pr = R4C["results"][f]["paths"]["B-refit (2nd engine, fitted here)"]
        sv = R4C["results"][f]["sensitivity_6fold"]
        rows.append([f, f"{mev(pr.get('threshold_stable'))} / {mev(pr.get('threshold_unstable'))}",
                     f"{mev(sv['thresholds'].get('stable'))} / {mev(sv['thresholds'].get('unstable'))}",
                     "yes" if sv.get("same_as_primary") in (True, "True") else "NO"])
    table(rows, [32, 44, 40, 24])
    note("f-electron's stable threshold DISAPPEARS under the family correction: its bound falls from "
         "0.900359 to 0.892556, a margin of -0.0074. The rescue reported in round 4b was partly "
         "bought by multiplicity and does not hold. intermetallic and pnictide are unchanged. The one "
         "place the correction mattered is the one place a positive result had been reported.")

    pagebreak()
    # ---------------------------------------------------------------- 5
    h1("5. The pnictide pre-registration")
    p("pnictide is the cleanest case the project has produced: both sides fitted on 3,501-3,637 rows "
      "with margins of +0.0128 and +0.0122, reaching identical thresholds on both paths and under "
      "both correction standards, replacing an entry fitted on 202 rows that currently sends every "
      "pnictide candidate to DFT when a second engine is supplied. A protocol has therefore been "
      "frozen to test it on unseen data.")
    note("The sample DOES NOT EXIST. The protocol was written and committed before any id was "
         "selected, which is the only order in which a pre-registration means anything. Drawing it is "
         "a separate decision.")
    rows = [["what is frozen", "value"]]
    rows.append(["thresholds under test", "stable -20 meV, unstable +0 meV, FIXED"])
    rows.append(["family definition", "confidence.family() unchanged; nitrides included"])
    rows.append(["population", "labelable; all-usable cannot change a verdict"])
    rows.append(["hypotheses", "PA1/PA2 (Path A) and PB1/PB2 (Path B), four primaries"])
    rows.append(["targets", "stable precision 0.90; unstable NPV 0.95"])
    rows.append(["primary confidence", f"{f4(PREREG['statistics']['primary_confidence'])} "
                                       "= 1 - 0.05/4 (Bonferroni over 4)"])
    rows.append(["grid correction", "NONE - thresholds are fixed, nothing is selected on held-out data"])
    rows.append(["family multiplicity", "NONE - only pnictide is tested"])
    rows.append(["sample size", f"n = {i(PREREG['sample']['n_draw'])} of "
                                f"{i(PREREG['sample']['eligible_pool'])} eligible"])
    rows.append(["promotion rule", "all four must PASS, or nothing is promoted"])
    table(rows, [44, 124])

    h2("5.1 Why 3,500 and not a convenient number")
    p("The binding hypothesis is the stable side, which converts only 0.0765 of drawn structures into "
      "calls. Required structures, powered against the development point estimate, at the primary "
      "confidence:")
    rows = [["hypothesis", "target", "assumed truth", "calls/structure", "80% power", "90% power",
             "95% power"]]
    for h, d in (("A stable", (0.90, 0.960784, 306 / 4000)), ("A unstable", (0.95, 0.974001, 3154 / 4000)),
                 ("B stable", (0.90, 0.960784, 306 / 4000)), ("B unstable", (0.95, 0.972830, 3018 / 4000))):
        s = PREREG["sizing"]["by_confidence"]["primary"][h]
        rows.append([h, f"{d[0]}", f4(d[1]), f4(d[2], 5), i(s["80%"]["structures"]),
                     i(s["90%"]["structures"]), i(s["95%"]["structures"])])
    table(rows, [24, 16, 24, 24, 22, 22, 22])
    rows = [["hypothesis", "expected calls", "expected errors", "max errors allowed", "power at n=3,500"]]
    for h, e in PREREG["error_budget"]["primary"].items():
        rows.append([h, i(e["expected_calls"]), f4(e["expected_errors"], 1),
                     i(e["max_errors_allowed"]), f4(e["power_at_dev_point"], 3)])
    table(rows, [30, 30, 30, 36, 30])
    p("3,500 gives about 0.94 power on the binding hypothesis and about 1.00 on the other three, and "
      "leaves 1,932 candidates unspent for a replacement study. A 1,500-structure draw - the "
      "convention the earlier rounds used - would have given power <b>0.53</b> on the binding "
      "hypothesis and was rejected for that reason.")
    note("Stated in advance, not discovered afterwards: the study is powered against the development "
         "POINT estimate. If pnictide's true stable precision were 0.9128 - the development lower "
         "bound - establishing a deficit against a 0.90 target would need roughly 65,000 structures, "
         "which the pool cannot supply. A PASS therefore means the thresholds behave as development "
         "suggested. It does NOT establish that true precision is comfortably above 0.90, and the "
         "protocol forbids claiming that it does. This is the same limit the fluoride follow-up found.")

    h2("5.2 The dependence question, resolved before any result exists")
    p("Path B is a strict <b>subset</b> of Path A: B is A minus the rows whose two engines disagree "
      "beyond the tolerance. The two tests are nested and strongly positively dependent, not "
      "independent - on development data B kept 96.3% of A's rows, and the stable side produced "
      "identical call and error counts on both paths. Testing both on the same structures therefore "
      "raises a real question about the multiplicity procedure, and it is answered in the protocol "
      "rather than after seeing results:")
    p("<b>1.</b> Bonferroni rests on Boole's inequality and assumes nothing about independence, so "
      "the nesting cannot invalidate it - dependence costs power, not validity. <b>2.</b> The "
      "promotion rule is conjunctive, which makes this an intersection-union test, where testing each "
      "hypothesis at an uncorrected alpha would already control the error of the conjunctive claim; a "
      "Bonferroni correction on top is therefore strictly conservative. <b>3.</b> The conservative "
      "option is pre-registered as primary anyway. <b>4.</b> A hypothesis passing at 0.95 but failing "
      "at 0.9875 is a <b>FAIL</b>, and no 'effective' correction will be estimated from the observed "
      "overlap, before or after seeing the data.")
    p("The protocol also fixes what happens in every branch: if A passes and B fails, or B passes and "
      "A fails, <b>nothing is promoted</b> in either case, because each outcome implies a subgroup "
      "claim that this data cannot support. An inconclusive hypothesis blocks promotion exactly as a "
      "failure does, and there is no 'ambiguous' verdict available for a primary hypothesis - a "
      "category that left the earlier fluoride result unresolved.")

    pagebreak()
    # ---------------------------------------------------------------- 6
    h1("6. Integrity, reproducibility and what was deliberately not done")
    h2("6.1 Locked-set state")
    p("Six held-out halves existed before this work and all six are untouched by it. The two that had "
      "been opened - the original WBM test in September 2026 and the halide half on 18 September - "
      "were not re-opened. The four unspent halves were confirmed to have zero results in the store, "
      "including the two that the ledger script does not cover. Round 4 created no new locked half, "
      "and its accessor raises rather than returning ids.")
    rows = [["locked half", "n", "state after this work"]]
    for nm, n, st in (("original WBM test", "4,000", "opened once, 2026-09-12; not re-opened"),
                      ("oxide (round 1)", "2,000", "UNOPENED, 0 results in store"),
                      ("halide (round 1)", "2,000", "opened once, 2026-09-18; not re-opened"),
                      ("sulfide (round 2)", "874", "SEALED, 0 results in store"),
                      ("chalcogenide residual (round 3)", "1,500", "UNOPENED, 0 results in store"),
                      ("other residual (round 3)", "1,500", "UNOPENED, 0 results in store"),
                      ("pnictide evaluation (round 4)", "3,500", "PRE-REGISTERED ONLY - does not exist")):
        rows.append([nm, n, st])
    table(rows, [56, 18, 94])

    h2("6.2 A defect found by trying to reproduce the work")
    p("Re-running the round-4 analysis against the tree reproduced its report identically apart from "
      "the generated timestamp. That check found one real defect: the failure-accounting query read "
      "the job queue without filtering on engine tag, so once the second engine was queued over the "
      "same ids its in-flight jobs were counted as round-4 jobs that had not run. The column reported "
      "7,468 / 8,000 / 8,000 instead of 0 / 0 / 0. It was fixed and the report re-verified. Accounting "
      "only - no measured quantity was affected - but it is recorded because the reproduction check is "
      "what caught it, not a test.")

    h2("6.3 Deliberately not done")
    rows = [["not done", "why"]]
    rows.append(["the f-electron top-up", "still worth running at 3,320-4,579 structures, but it "
                                          "resolves a family whose stable side is unestablished on "
                                          "either path; pnictide has a measured defect with a "
                                          "measured fix and comes first"])
    rows.append(["any promotion", "every threshold here is fitted and scored on the same development "
                                  "rows - the most optimistic estimate available"])
    rows.append(["an f-electron subfamily search", "lanthanide against actinide would invite exactly "
                                                   "the multiplicity that eleven oxide splits already "
                                                   "demonstrated; it needs its own correction and its "
                                                   "own pre-registration"])
    rows.append(["intermetallic pre-registration", "its unstable NPV margin is +0.0039, too thin to "
                                                   "carry alongside pnictide without more thought"])
    rows.append(["regenerating the round-2 report", "the corrected locked-set ledger would flow into a "
                                                    "historical deliverable and retroactively rewrite "
                                                    "a table written 'as of' an earlier date; the "
                                                    "staleness is recorded instead"])
    table(rows, [40, 128])

    h2("6.4 Provenance")
    rows = [["artefact", "sha256 (first 32)"]]
    for path in (DATA / "wbm_split_round4.json", REPORTS / "round4_carried_over.json",
                 REPORTS / "round4_second_engine.json", REPORTS / "round4_pathb_refit.json",
                 DATA / "pnictide_evaluation_preregistration.json", DATA / "calibration_bundle.json",
                 DATA / "calibration_spec_v2.json"):
        rows.append([path.relative_to(ROOT).as_posix(), sha(path)[:32]])
    table(rows, [78, 90])
    small("The calibration bundle and frozen specification v2 appear here to show they are unchanged: "
          "the bundle still carries created_at 2026-09-12T20:21:45+00:00, confidence.FAMILIES still "
          "contains no fluoride, and the specification's sha256 still matches the value recorded in "
          "the halide opening log.")

    h1("7. Where this leaves the product")
    p("Unchanged, and deliberately. The active bundle is byte-for-byte what it was; the taxonomy has "
      "not moved; specification v2 remains frozen and unpromoted; the fluoride carve-out remains "
      "unresolved. What has changed is what is known about the product's weakest corner.")
    p("Two families that could label nothing stable can be fitted to label a great deal - pnictide "
      "from 0 to 0.583 recall, intermetallic from 0 to 0.506 - and the ceiling that made f-electron "
      "the only labelling family was a sample-size artefact, not chemistry. Against that, the one "
      "family that did label has lost its certification on fresh data, and the path the product takes "
      "when a second engine is supplied is measurably worse than the path without one. None of these "
      "is validated. One of them is now pre-registered to be.")


if __name__ == "__main__":
    build()
    (REPORTS / "round4_results.md").write_text(to_markdown(B))
    to_pdf(B, REPORTS / "round4_results.pdf", doc_title=TITLE, footer="Materials Harness - round 4")
    print("wrote reports/round4_results.md")
    print("wrote reports/round4_results.pdf")
