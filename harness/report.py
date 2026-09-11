"""Validation report: reports/validation_report.md + figures + scorecard.json + results/results.parquet.

Round-2 structure. Every metric is stratified by hull-distance bin (compare.HULL_BINS_MP / HULL_BINS_WBM),
shown with its median next to its mean and a 95 % bootstrap interval, and every verdict comes from the
pessimistic end of that interval (upper bound of an error, lower bound of a score). Results that relaxed
into a different structure are reported separately from results that stayed in the target structure;
results rejected by the convergence / sanity guard are counted, never averaged in. Stability decisions,
threshold sweeps and cost optimisation use the WBM CALIBRATION set only; the locked test set is never read
here (the report asserts that no test id has a result).
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pymatgen.core import Composition

import harness  # noqa: F401  (cache env vars before matplotlib)
from harness import compare, store
from harness import metrics as M
from harness.config import (CONFIG_DIR, DEFAULT_RELAX, FIG_DIR, MODEL, REPORTS_DIR, RESULTS_DIR, ROOT,
                            load_compute_config, settings_tag)
from harness.platform_check import machine_info

log = logging.getLogger(__name__)

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
KNOWN, NEW, PBE = SERIES

# (good, caution, lower_is_better). Verdicts are taken at the pessimistic end of the 95 % interval.
VERDICT_RULES = {
    "energy_mae_mev": (30.0, 60.0, True),
    "volume_mae_pct": (1.0, 2.0, True),
    "e_hull_mae_mev": (30.0, 60.0, True),
    "precision": (0.80, 0.60, False),
    "npv": (0.95, 0.90, False),
    "bulk_mae_pct": (10.0, 20.0, True),
    "mace_minus_pbe_pct": (0.5, 1.0, True),
}
N_BOOT = M.N_BOOT
MIN_ELEMENT_COUNT = 20
MAGNETIC_MOMENT_MIN = 0.05  # μB/site in the PBE calculation
SWEEP = tuple(round(x, 3) for x in np.arange(-0.20, 0.2001, 0.01))
COSTS_FILE = CONFIG_DIR / "costs.json"

# Matbench Discovery, MACE-MP-0 (checkpoint 2023-12-03-mace-128-L1_epoch-199), unique-prototype subset.
# Source: models/mace/mace-mp-0.yml in github.com/janosh/matbench-discovery (read 2026-09-11).
MBD_MACE_MP0 = {"F1": 0.669, "DAF": 3.777, "precision": 0.577, "recall": 0.796, "accuracy": 0.878,
                "MAE (eV/atom)": 0.057, "RMSE (eV/atom)": 0.101, "R2": 0.697,
                "protocol": "FIRE, fmax 0.05 eV/Å, ≤ 500 steps, FrechetCellFilter"}
MBD_SOURCE = "Matbench Discovery, models/mace/mace-mp-0.yml (unique-prototype subset)"


def boot_ci(x, f=M.MAE, seed: int = 0):
    return M.boot_ci(x, f, N_BOOT, seed)


def verdict(metric: str, value: float) -> str:
    good, caution, lower = VERDICT_RULES[metric]
    return M.verdict(value, good, caution, lower)


def verdict_ci(metric: str, ci) -> str:
    """Verdict at the pessimistic end of the interval, with the bound it was judged on."""
    good, caution, lower = VERDICT_RULES[metric]
    v = M.verdict_ci(ci, good, caution, lower)
    return v


def _md(df: pd.DataFrame, floatfmt=".2f") -> str:
    return df.to_markdown(index=False, floatfmt=floatfmt) if len(df) else "_no data_"


def _ci(t, spec="{:.1f}") -> str:
    return M.fmt_ci(t, spec)


def _costs() -> dict:
    c = {"cost_false_positive": 1.0, "cost_missed_stable": 1.0, "sensitivity_ratios": [0.25, 0.5, 1, 2, 4, 10]}
    if COSTS_FILE.is_file():
        c.update({k: v for k, v in json.loads(COSTS_FILE.read_text()).items() if not k.startswith("_")})
    return c


# --- figures ---------------------------------------------------------------------------------------------

def _fig(w=5.4, h=5.0, ncols=1):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 9})
    fig, axes = plt.subplots(1, ncols, figsize=(w, h), dpi=150, squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    for ax in axes[0]:
        ax.set_facecolor(SURFACE)
        for side, sp in ax.spines.items():
            sp.set_visible(side in ("left", "bottom"))
            sp.set_color(AXIS)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=AXIS, labelcolor=INK2)
    return fig, list(axes[0]), plt


def parity(path, panels, xlabel, ylabel, title) -> str:
    k = len(panels)
    fig, axes, plt = _fig(w=4.1 * k + 0.4, h=4.6, ncols=k)
    xs = np.concatenate([np.asarray(p[1], float) for p in panels])
    ys = np.concatenate([np.asarray(p[2], float) for p in panels])
    ok = np.isfinite(xs) & np.isfinite(ys)
    lo, hi = float(np.percentile(np.r_[xs[ok], ys[ok]], 0.5)), float(np.percentile(np.r_[xs[ok], ys[ok]], 99.5))
    pad = (hi - lo) * 0.05 or 0.1
    lo, hi = lo - pad, hi + pad
    for ax, (name, x, y, color) in zip(axes, panels):
        ax.plot([lo, hi], [lo, hi], color=MUTED, linewidth=1, zorder=1)
        ax.scatter(x, y, s=12, color=color, alpha=0.6, edgecolors="none", zorder=3)
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_aspect("equal")
        ax.set_xlabel(xlabel, color=INK2)
        ax.set_title(f"{name} (n={len(x)})", color=INK, loc="left", fontsize=9)
    axes[0].set_ylabel(ylabel, color=INK2)
    fig.suptitle(title + " (axes clipped to the 0.5–99.5 % range)", x=0.01, ha="left", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return path.name


def pr_curve(path, sweep: pd.DataFrame, marks: dict) -> str:
    fig, axes, plt = _fig(w=5.6, h=4.6)
    ax = axes[0]
    ax.plot(sweep.recall, sweep.precision, color=NEW, linewidth=1.8, zorder=2)
    for label, thr in marks.items():
        r = sweep.iloc[(sweep.threshold - thr).abs().argmin()]
        ax.scatter([r.recall], [r.precision], s=40, color=INK, zorder=3)
        ax.annotate(f"{label}: {thr * 1000:+.0f} meV/atom", (r.recall, r.precision), textcoords="offset points",
                    xytext=(6, 4), fontsize=7, color=INK2)
    ax.set_xlabel("recall (share of truly stable materials called stable)", color=INK2)
    ax.set_ylabel("precision (share of stable calls that are right)", color=INK2)
    ax.set_title("Stable-call precision vs recall, threshold swept (WBM calibration set)", color=INK, loc="left", fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return path.name


# --- data ------------------------------------------------------------------------------------------------

def _wbm_outcomes(tag: str, df: pd.DataFrame) -> pd.Series:
    """MACE-relaxed vs WBM DFT-relaxed structure (species-aware StructureMatcher, defaults), cached per tag."""
    from harness.suites import ood

    cache = RESULTS_DIR / f"wbm_structure_match_{tag}.json"
    have = json.loads(cache.read_text()) if cache.is_file() else {}
    todo = [w for w in df.wbm_id if w not in have]
    if todo:
        cses = ood.load_entries(sorted(set(df.wbm_id)), ood.WBM_DIR / "calibration_cse.json")
        rel = dict(zip(df.wbm_id, df.relaxed))
        for w in todo:
            have[w] = bool(compare.relaxed_into_target(rel[w], cses[w].structure)) if w in cses else None
        cache.write_text(json.dumps(have))
    from harness.suites.substitution import outcome

    return df.wbm_id.map(lambda w: outcome(have.get(w)))


def _start_changed(tag: str, df: pd.DataFrame) -> pd.Series:
    """Did the relaxation leave its starting (WBM initial) structure? The signal a real candidate has — the
    DFT-relaxed structure is not known for new materials. Cached per settings tag."""
    from harness.suites import ood

    cache = RESULTS_DIR / f"wbm_start_match_{tag}.json"
    have = json.loads(cache.read_text()) if cache.is_file() else {}
    todo = [w for w in df.wbm_id if w not in have]
    if todo:
        starts = ood.load_structures(sorted(set(df.wbm_id)), cache_file=ood.WBM_DIR / "calibration_init_structs.json")
        rel = dict(zip(df.wbm_id, df.relaxed))
        for w in todo:
            have[w] = (not compare.relaxed_into_target(rel[w], starts[w])) if w in starts else None
        cache.write_text(json.dumps(have))
    return df.wbm_id.map(have.get)


def collect(tag: str) -> dict:
    from harness import pairgen, splits
    from harness.suites import bulk, experimental, ood, stability, substitution

    def safe(fn, *a, **k):
        try:
            return fn(*a, **k)
        except Exception as exc:  # noqa: BLE001 — a missing suite must not break the report
            log.warning("report: %s unavailable: %s", getattr(fn, "__qualname__", fn), exc)
            return pd.DataFrame()

    au = safe(substitution.pair_table, tag, suite="substitution_auto", pairs=pairgen.load_pairs())
    if len(au):
        au["bin"] = au.target_e_hull.astype(float).map(compare.hull_bin)
    oo = safe(ood.table, tag)
    split = splits.load_split() if splits.SPLIT_FILE.is_file() else None
    wb, wb_rej = pd.DataFrame(), pd.DataFrame()
    if len(oo) and split:
        leaked = set(oo.wbm_id) & set(split["test"]["ids"])
        if leaked:
            raise RuntimeError(f"{len(leaked)} locked WBM test ids have results — the test set must not be run before the final evaluation")
        cal = oo[oo.wbm_id.isin(set(split["calibration"]["ids"]))]
        wb_rej = cal[cal.rejection.notna()]
        wb = cal[cal.rejection.isna()].copy()
        wb["bin"] = wb.each_true.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
        wb["pred_bin"] = wb.each_pred.map(lambda e: compare.hull_bin(e, below_zero_bin=True))
        wb["outcome"] = _wbm_outcomes(tag, wb)
        wb["structure_changed"] = _start_changed(tag, wb)
    from harness.suites import mode_b

    mb = safe(mode_b.table, tag)
    jobs = store.load_table("jobs")
    jobs = jobs[jobs.job_key.str.endswith(f"@{tag}")] if len(jobs) else jobs
    return {"au": au, "cu": safe(substitution.pair_table, tag), "wb": wb, "wb_rej": wb_rej, "split": split,
            "st": safe(stability.target_table, tag), "ex": safe(experimental.table, tag), "bk": safe(bulk.table, tag),
            "jobs": jobs, "pair_meta": pairgen.load_meta(), "mb": mb}


# --- tables -----------------------------------------------------------------------------------------------

def stratified_table(df: pd.DataFrame, bins, e_col: str, v_col: str | None = None, split: str | None = None,
                     rej_col: str | None = None, bin_col: str = "bin") -> pd.DataFrame:
    """Per bin (and per value of `split`): n, rejected, energy MAE / median / mean signed with CIs, volume
    MAE / median with CIs, and the energy verdict from the pessimistic bound."""
    rows = []
    for b in bins:
        g = df[df[bin_col] == b]
        parts = [(None, g)] if not split else [(o, g[g[split] == o]) for o in sorted(g[split].dropna().unique())]
        for o, sub in parts:
            s = M.error_summary(sub[e_col], N_BOOT)
            row = {"bin": b}
            if split:
                row[split.replace("_", " ")] = o
            row.update({"n": s["n"]})
            if rej_col and rej_col in sub:
                row["rejected (guard)"] = int(sub[rej_col].map(lambda x: isinstance(x, str)).sum())
            row.update({"energy MAE": _ci(s["mae"]), "energy median |err|": _ci(s["median_abs"]),
                        "mean signed": _ci(s["mean_signed"], "{:+.1f}")})
            if v_col:
                v = M.error_summary(sub[v_col], N_BOOT)
                row.update({"volume MAE %": _ci(v["mae"], "{:.2f}"), "volume median %": _ci(v["median_abs"], "{:.2f}")})
            row["energy verdict (pessimistic)"] = verdict_ci("energy_mae_mev", s["mae"]) if s["n"] else "no data"
            rows.append(row)
    return pd.DataFrame(rows)


def rejected_counts(df: pd.DataFrame, bins, cols: dict) -> pd.DataFrame:
    rows = []
    for b in bins:
        g = df[df.bin == b]
        rows.append({"bin": b, "pairs": len(g), **{label: int(g[c].map(lambda x: isinstance(x, str)).sum()) if c in g else 0
                                                   for label, c in cols.items()}})
    return pd.DataFrame(rows)


# likely-cause rules: checked in this order, the first two before anything about the chemistry
def likely_cause(formula: str, true_e_hull: float | None, outcome: str | None, magnetic_pbe: bool | None, source: str) -> str:
    from harness.suites.substitution import DIFFERENT

    els = {e.symbol for e in Composition(formula).elements}
    causes = []
    if true_e_hull is not None and np.isfinite(true_e_hull) and true_e_hull > 0.3:
        causes.append("far above the hull (> 0.3 eV/atom): a hypothetical structure that need not be a minimum for the model")
    if outcome == DIFFERENT:
        causes.append("relaxed into a different structure")
    if els & compare.F_ELECTRON:
        causes.append(f"f-electron chemistry ({', '.join(sorted(els & compare.F_ELECTRON))})")
    if magnetic_pbe:
        causes.append("magnetic in the PBE calculation (MACE has no spin)")
    elif els & compare.MAGNETIC_PRONE and els & {"O", "F"}:
        causes.append(f"+U transition-metal oxide/fluoride ({', '.join(sorted(els & compare.MAGNETIC_PRONE))})")
    if source == "WBM":
        causes.append("new composition/prototype (not in MPtrj)")
    return "; ".join(causes) or "no flag — generic model error"


# --- report ---------------------------------------------------------------------------------------------

def _git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return "unknown"


def previous_scorecard(out_dir: Path) -> Path | None:
    out_dir = Path(out_dir).resolve()
    is_run = out_dir.parent == REPORTS_DIR.resolve()
    runs = sorted(p for p in REPORTS_DIR.glob("*/scorecard.json")
                  if p.parent.resolve() != out_dir and (not is_run or p.parent.name < out_dir.name))
    if runs:
        return runs[-1]
    base = REPORTS_DIR / "scorecard.json"
    return base if base.is_file() and REPORTS_DIR.resolve() != out_dir else None


def comparison_lines(out_dir: Path, cur: dict) -> list[str]:
    prev_path = previous_scorecard(out_dir)
    if prev_path is None:
        return []
    prev = json.loads(prev_path.read_text())
    rows = [{"metric": k, "previous": prev[k], "this run": cur[k]} for k in cur
            if k in prev and isinstance(cur[k], (int, float)) and isinstance(prev[k], (int, float)) and k != "generated_at"]
    if not rows:
        return []
    return ["### Compared with the previous scorecard", "", f"Previous: `{prev_path.parent.name}` (settings `{prev.get('settings_tag')}`)."
            + (" **Settings differ.**" if prev.get("settings_tag") != cur.get("settings_tag") else ""), "",
            _md(pd.DataFrame(rows), ".3f"), ""]


def write_report(out_dir: Path | None = None, compare_previous: bool = False) -> str:
    compute = load_compute_config()
    tag = settings_tag(compute["device"], compute["dtype"])
    out_dir = Path(out_dir) if out_dir else REPORTS_DIR
    fig_dir = FIG_DIR if out_dir.resolve() == REPORTS_DIR.resolve() else out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    d = collect(tag)
    au, cu, wb, st, ex, bk, jobs = d["au"], d["cu"], d["wb"], d["st"], d["ex"], d["bk"], d["jobs"]
    costs = _costs()
    score: dict = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "settings_tag": tag,
                   "commit": _git_commit(), "model": MODEL["name"]}
    body: list[str] = []
    verdict_lines: list[str] = []

    # ---------- 1. what was scored ----------
    body += ["## 1. What was scored, and what was not", ""]
    split = d["split"]
    if split:
        body += [f"* **WBM split** (`data/wbm_split.json`, seed {split['seed']}, made {split['created_at'][:10]} before any tuning): "
                 f"calibration {split['calibration']['n']:,} ids, locked test {split['test']['n']:,} ids (sha256 "
                 f"`{split['test']['sha256'][:12]}…`), both in the pool's hull-bin proportions. **Every stability decision, "
                 "threshold and cost optimum below uses the calibration set only. The test set has not been run; it is "
                 "evaluated once, at the very end.**",
                 f"* WBM calibration: {len(wb):,} usable relaxations, {len(d['wb_rej'])} rejected by the convergence / sanity "
                 f"guard (counted, not scored), {split['calibration']['n'] - len(wb) - len(d['wb_rej'])} without a result yet."]
    pm = d["pair_meta"]
    if pm:
        short = {b: s["shortfall"] for b, s in pm.get("per_bin", {}).items() if s.get("shortfall")}
        body += [f"* **MP substitution pairs:** {pm.get('accepted', 0):,} pairs sampled per target hull bin "
                 f"(design: {json.dumps({k: pm['config'][k] for k in ('per_bin', 'implausible_frac', 'metallic_frac', 'max_per_prototype')})}); "
                 f"sampling shortfalls (cell ran out of candidates under the prototype cap): {short or 'none'}."]
    if len(au):
        body += ["", "Results rejected by the guard (not converged or unphysical), per bin — excluded from every statistic:", "",
                 _md(rejected_counts(au, compare.HULL_BINS_MP, {"ctrl rejected": "ctrl_rejection",
                                                                 "no usable substitution start": "sub_best_rejection"})), ""]
    if len(jobs):
        bad = jobs[jobs.status.isin(["failed", "timeout"])]
        body += [f"Failed or timed-out jobs at this settings tag: {len(bad)}"
                 + (f" ({bad.groupby('suite').size().to_dict()})" if len(bad) else "") + ".", ""]

    # ---------- 2. known materials by bin ----------
    body += ["## 2. Known materials (Materials Project substitution pairs), by target hull distance", "",
             "Energies in meV/atom against MP's uncorrected PBE/PBE+U energy; volume in % against the PBE cell. "
             "*Same structure* = the relaxed result still matches the MP target (StructureMatcher, default tolerances); "
             "*relaxed into a different structure* is a different failure and is never mixed into the first.", ""]
    if len(au):
        for title, e, v, split_col in (("MP target relaxed with MACE (control)", "ctrl_dE_mev", "ctrl_vol_pct", "ctrl_outcome"),
                                        ("Substituted parent relaxed — best of two starts (the product's use case)",
                                         "sub_best_dE_mev", "sub_best_vol_pct", "sub_best_outcome")):
            body += [f"**{title}:**", "", _md(stratified_table(au, compare.HULL_BINS_MP, e, v, split_col)), ""]
        body += ["**Single point at the PBE structure** (model energy error with no relaxation in the way):", "",
                 _md(stratified_table(au, compare.HULL_BINS_MP, "static_dE_mev")), ""]
        rows = []
        for b in compare.HULL_BINS_MP:
            g = au[au.bin == b]
            for label, sub in (("metallic", g[g.chem_class == "metallic"]), ("compound", g[g.chem_class == "compound"]),
                               ("plausible swap", g[g.plausible == True]), ("implausible swap", g[g.plausible == False])):  # noqa: E712
                s = M.error_summary(sub.sub_best_dE_mev, N_BOOT)
                same = (sub.sub_best_outcome == "same structure").mean() if len(sub) else np.nan
                rows.append({"bin": b, "stratum": label, "n": s["n"], "energy MAE": _ci(s["mae"]),
                             "energy median |err|": _ci(s["median_abs"]), "stays in target structure": f"{same:.0%}" if np.isfinite(same) else "n/a"})
        body += ["**By chemistry class and swap plausibility** (substituted parent, best start):", "", _md(pd.DataFrame(rows)), ""]
        same = au[au.ctrl_outcome == "same structure"]
        for b in compare.HULL_BINS_MP:
            s = M.error_summary(same[same.bin == b].ctrl_dE_mev, N_BOOT)
            score[f"mp_same_structure_energy_mae_{b}"] = s["mae"][0]
            score[f"mp_same_structure_energy_mae_upper_{b}"] = s["mae"][2]

    # ---------- 3. new materials by bin ----------
    body += ["## 3. New materials (WBM calibration set), by hull distance against the MP hull", ""]
    if len(wb):
        body += ["Energy error MACE − DFT (meV/atom, uncorrected), relaxed from WBM's unrelaxed structure:", "",
                 _md(stratified_table(wb, compare.HULL_BINS_WBM, "de_mev", None, "outcome")), "",
                 "Single point at WBM's DFT-relaxed structure:", "",
                 _md(stratified_table(wb, compare.HULL_BINS_WBM, "de_static_mev")), ""]
        for b in compare.HULL_BINS_WBM:
            s = M.error_summary(wb[wb.bin == b].de_mev, N_BOOT)
            score[f"wbm_energy_mae_{b}"] = s["mae"][0]
            score[f"wbm_energy_mae_upper_{b}"] = s["mae"][2]
        diff_share = wb.groupby("bin").outcome.apply(lambda o: (o == "relaxed into a different structure").mean())

    # ---------- 4. stability decisions ----------
    body += ["## 4. Stability decisions on new materials (WBM calibration set only)", "",
             "Positive class = stable (reference energy above the MP hull ≤ 0). A material is called stable when its predicted "
             "hull distance (DFT hull distance + MACE − DFT energy, the Matbench Discovery construction) is ≤ the decision "
             "threshold. NPV = how often an 'unstable' call is right; DAF = precision ÷ share of stable materials. "
             "Intervals: 95 % bootstrap; **the verdict column uses the lower bound.**", ""]
    opt = dm0 = dmo = None
    if len(wb):
        pe, te = wb.each_pred.values, wb.each_true.values
        sweep = M.threshold_sweep(pe, te, SWEEP)
        opt = M.cost_optimal_threshold(sweep, costs["cost_false_positive"], costs["cost_missed_stable"])
        dm0 = M.decision_metrics(pe, te, 0.0, N_BOOT)
        dmo = M.decision_metrics(pe, te, opt["threshold"], N_BOOT)
        dm_explore = M.decision_metrics(pe, te, -0.05, N_BOOT)
        rows = []
        for label, dm in ((f"{0:+.0f} meV/atom (on-hull)", dm0), (f"{opt['threshold'] * 1000:+.0f} meV/atom (cost-optimal)", dmo),
                          ("−50 meV/atom (round-1 exploration)", dm_explore)):
            rows.append({"threshold": label, "called stable": dm["called_stable"], "precision": _ci(dm["precision_ci"], "{:.2f}"),
                         "recall": _ci(dm["recall_ci"], "{:.2f}"), "F1": _ci(dm["f1_ci"], "{:.2f}"), "NPV": _ci(dm["npv_ci"], "{:.3f}"),
                         "DAF": _ci(dm["daf_ci"], "{:.2f}"), "precision verdict (lower bound)": verdict_ci("precision", dm["precision_ci"])})
        body += [f"Share of stable materials in the calibration set: {dm0['prevalence']:.3f} (n={dm0['n']:,}).", "",
                 _md(pd.DataFrame(rows)), ""]
        sens = []
        for ratio in costs["sensitivity_ratios"]:
            o = M.cost_optimal_threshold(sweep, 1.0, float(ratio))
            sens.append({"missed stable ÷ wasted lab test": ratio, "optimal threshold (meV/atom)": o["threshold"] * 1000,
                         "precision": o["precision"], "recall": o["recall"], "expected cost per candidate": o["expected_cost"]})
        body += [f"**Cost-based operating point.** Costs from `config/costs.json`: wasted lab test = {costs['cost_false_positive']}, "
                 f"missed stable material = {costs['cost_missed_stable']} (**placeholders — set real numbers**). Expected cost per "
                 "screened candidate = (false positives × wasted-test cost + false negatives × missed-material cost) ÷ N, minimised "
                 "over the threshold sweep. How the optimum moves with the cost ratio:", "", _md(pd.DataFrame(sens), ".3f"), ""]
        figs_pr = pr_curve(fig_dir / "precision_recall.png", sweep, {"0": 0.0, "cost-optimal": opt["threshold"], "−50": -0.05})
        body += [f"![Precision–recall, calibration set](figures/{figs_pr})", ""]
        pick = sweep[sweep.threshold.isin([round(x, 3) for x in np.arange(-0.15, 0.1501, 0.025)])].copy()
        for col in ("called_stable", "tp", "fp", "fn"):
            pick[col] = pick[col].astype(int).astype(str)  # counts print as integers
        body += ["Threshold sweep (calibration set):", "",
                 _md(pick[["threshold", "called_stable", "tp", "fp", "fn", "precision", "recall", "f1", "npv", "daf"]], ".3f"), ""]
        thr = opt["threshold"]
        rows = []
        for b in compare.HULL_BINS_WBM:
            g = wb[wb.bin == b]
            called = (g.each_pred <= thr + M.ON_HULL_TOL).astype(float)
            rows.append({"true bin": b, "n": len(g), "called stable": _ci(M.boot_ci(called, M.MEAN, N_BOOT), "{:.2f}"),
                         "reads as": "recall" if b == "<0" else "false-positive rate"})
        body += [f"**Where the calls go wrong, by TRUE hull distance** (share called stable at {thr * 1000:+.0f} meV/atom). Precision "
                 "cannot be computed per true bin (all members share one label); this shows which unstable bins leak into "
                 "'stable' calls:", "", _md(pd.DataFrame(rows)), ""]
        rows = []
        for b in compare.HULL_BINS_WBM:
            g = wb[wb.pred_bin == b]
            truly = (g.each_true <= M.ON_HULL_TOL).astype(float)
            rows.append({"PREDICTED bin": b, "n": len(g), "truly stable": _ci(M.boot_ci(truly, M.MEAN, N_BOOT), "{:.2f}")})
        body += ["**How often a prediction is right, by PREDICTED hull distance** (the view a user has of a new candidate):", "",
                 _md(pd.DataFrame(rows)), ""]
        score.update({"wbm_precision_opt": dmo["precision"], "wbm_precision_opt_lower": dmo["precision_ci"][1],
                      "wbm_recall_opt": dmo["recall"], "wbm_f1_opt": dmo["f1"], "wbm_npv_opt": dmo["npv"],
                      "wbm_threshold_opt_mev": thr * 1000, "wbm_f1_0": dm0["f1"], "wbm_precision_0": dm0["precision"],
                      "wbm_daf_0": dm0["daf"]})

        # ---------- 5. Matbench Discovery ----------
        e_err = wb.each_pred - wb.each_true
        r2 = 1 - np.sum(e_err ** 2) / np.sum((wb.each_true - wb.each_true.mean()) ** 2)
        ours = {"F1": dm0["f1"], "DAF": dm0["daf"], "precision": dm0["precision"], "recall": dm0["recall"],
                "accuracy": dm0["accuracy"], "MAE (eV/atom)": float(e_err.abs().mean()),
                "RMSE (eV/atom)": float(np.sqrt((e_err ** 2).mean())), "R2": float(r2)}
        cis = {"F1": dm0["f1_ci"], "DAF": dm0["daf_ci"], "precision": dm0["precision_ci"], "recall": dm0["recall_ci"],
               "accuracy": dm0["accuracy_ci"], "MAE (eV/atom)": M.boot_ci(e_err, M.MAE, N_BOOT)}
        rows = [{"metric": k, "Matbench Discovery (published)": MBD_MACE_MP0[k], "this harness (calibration set)": ours[k],
                 "95 % CI": _ci(cis[k], "{:.3f}") if k in cis else "", "published value inside CI": (
                     "yes" if k in cis and cis[k][1] <= MBD_MACE_MP0[k] <= cis[k][2] else "no" if k in cis else "")}
                for k in ours]
        body += ["## 5. Cross-check against the published Matbench Discovery numbers", "",
                 f"Same model checkpoint, same hull-distance construction, threshold 0. Published: {MBD_SOURCE}; their relaxation: "
                 f"{MBD_MACE_MP0['protocol']}. Ours: {DEFAULT_RELAX.optimizer} + {DEFAULT_RELAX.cell_filter}, fmax "
                 f"{DEFAULT_RELAX.fmax} eV/Å **and** |stress| ≤ {DEFAULT_RELAX.max_stress_gpa} GPa, fallback ladder on failure.", "",
                 _md(pd.DataFrame(rows), ".3f"), "",
                 "Where a published value lies outside our interval, the likely reasons are, in order: (1) our tighter relaxation "
                 "(5× smaller force tolerance plus an explicit stress criterion) lets structures relax further, which lowers "
                 "energies of high-energy structures and moves borderline calls; (2) sampling — ours is a 4,000-structure "
                 "calibration set, theirs the full 215,488; (3) guard-rejected structures are excluded here and counted above.", ""]

    # ---------- 6. mode (a) vs mode (b), curated ----------
    if len(st):
        from harness.suites import stability as st_mod

        rows = []
        for mode, col in (("a (MACE target, DFT competitors)", "a"), ("b (every phase MACE, strict)", "b")):
            m = st_mod.metrics(st, col)
            rows.append({"mode": mode, "scored": m["n"], "unscored": m["n_unscored"], "e_hull MAE meV/atom": m["mae_ev"] * 1000,
                         "accuracy@0": m["thr0.0"]["accuracy"], "accuracy@0.1": m["thr0.1"]["accuracy"]})
        if "b_sub_e_hull" in st:
            alt = st.assign(bsub_e_hull=st.b_e_hull.where(np.isfinite(st.b_e_hull.astype(float)), st.b_sub_e_hull))
            m = st_mod.metrics(alt, "bsub")
            rows.append({"mode": "b + stand-in polymorph (flagged, not mode b)", "scored": m["n"], "unscored": m["n_unscored"],
                         "e_hull MAE meV/atom": m["mae_ev"] * 1000, "accuracy@0": m["thr0.0"]["accuracy"],
                         "accuracy@0.1": m["thr0.1"]["accuracy"]})
        body += ["## 6. Curated stability gate: mode (a) vs mode (b)", "",
                 "50 curated known materials (all within 0.3 eV/atom of the hull). Mode (b) is not scored when one of the MP reference "
                 "hull's own phases has no usable MACE relaxation (MACE-MP-0 collapses solid O₂, the oxygen corner of every oxide "
                 "hull here). Mode (b) on new materials is Phase 4.", "", _md(pd.DataFrame(rows), ".3f"), ""]

    # ---------- 6b. mode (b) on new materials ----------
    mb = d.get("mb", pd.DataFrame())
    if len(mb):
        body += ["## 6b. New materials in mode (b): every competing phase relaxed with the engine", "",
                 f"{len(mb)} WBM calibration systems (data/mode_b_sample.json: a fixed number per hull bin, one structure per "
                 "chemical system). Reference = WBM DFT entry on the current MP GGA/GGA+U hull, MP2020 re-applied to every entry "
                 "with this pymatgen (so it differs slightly from WBM's shipped hull distance). Mode (a): engine-relaxed target vs "
                 "MP DFT phases. Mode (b): engine-relaxed target vs engine-relaxed MP phases within "
                 f"{0.1:.1f} eV/atom of the MP hull, against the reference on the same phases. Errors in meV/atom.", "",
                 "Status of the mode (b) hulls: " + ", ".join(f"{k}: {v}" for k, v in mb.b_status.value_counts().items()) + ".", ""]
        rows = []
        for b in compare.HULL_BINS_WBM:
            g = mb[mb.bin == b]
            ra, rb, rs = (M.error_summary(g[c], N_BOOT) for c in ("a_err_mev", "b_err_mev", "b_sub_err_mev"))
            rows.append({"bin (reference)": b, "systems": len(g), "mode (a) MAE": _ci(ra["mae"]), "mode (a) median": _ci(ra["median_abs"]),
                         "mode (b) scored": rb["n"], "mode (b) MAE": _ci(rb["mae"]), "mode (b) median": _ci(rb["median_abs"]),
                         "stand-in only (flagged)": rs["n"], "mode (b) verdict (upper bound)": verdict_ci("e_hull_mae_mev", rb["mae"])})
        body += [_md(pd.DataFrame(rows)), ""]
        rows = []
        for mode, col, ref in (("a", "a_signed", "ref_signed"), ("b", "b_signed", "ref_window_signed")):
            ok = mb[np.isfinite(mb[col].astype(float))]
            dm = M.decision_metrics(ok[col].values, ok[ref].values, 0.0, N_BOOT)
            rows.append({"mode": mode, "scored": dm["n"], "precision": _ci(dm["precision_ci"], "{:.2f}"),
                         "recall": _ci(dm["recall_ci"], "{:.2f}"), "F1": _ci(dm["f1_ci"], "{:.2f}"), "NPV": _ci(dm["npv_ci"], "{:.3f}")})
        body += ["Stable calls at 0 eV/atom on these systems (the sample over-represents stable materials by design — one bin in "
                 "five is '<0' — so precision here is not the population precision of section 4):", "", _md(pd.DataFrame(rows)), ""]
        both = mb[np.isfinite(mb.b_err_mev.astype(float))]
        rows = []
        for b in list(compare.HULL_BINS_WBM) + ["all"]:
            g = both if b == "all" else both[both.bin == b]
            diff = M.boot_ci(g.b_err_mev.abs() - g.a_err_mev.abs(), M.MEAN, N_BOOT)
            rows.append({"bin": b, "systems scored in both": len(g), "|b| − |a| mean": _ci(diff, "{:+.1f}"),
                         "mode (b) closer": f"{(g.b_err_mev.abs() < g.a_err_mev.abs()).mean():.0%}" if len(g) else "n/a",
                         "mean signed a": g.a_err_mev.mean(), "mean signed b": g.b_err_mev.mean()})
        body += ["**Paired comparison** on systems scored in both modes (meV/atom; positive = mode (b) worse):", "",
                 _md(pd.DataFrame(rows), ".1f"), ""]
        mode_b_diff = M.boot_ci(both.b_err_mev.abs() - both.a_err_mev.abs(), M.MEAN, N_BOOT)
        score["mode_b_minus_a_abs_mev"] = mode_b_diff[0]
        for b in compare.HULL_BINS_WBM:
            s = M.error_summary(mb[mb.bin == b].b_err_mev, N_BOOT)
            score[f"mode_b_mae_{b}"] = s["mae"][0]

    # ---------- 6c. confidence and routing (calibration, cross-validated) ----------
    if len(wb) > 200:
        from harness import confidence as C
        from harness import routing as R

        cv = C.crossval_coverage(wb, C.ALPHA, k=5)
        wbr = wb.assign(structure_changed=wb.structure_changed.fillna(False))
        dec = R.crossval_routing(wbr, C.ALPHA, k=5, certified=True)
        rs = R.routing_summary(dec)
        rs_conf = R.routing_summary(R.crossval_routing(wbr, C.ALPHA, k=5, certified=False))
        pol_all = R.RoutingPolicy(weak_elements=R.weak_elements_from(wbr))
        rule_all = C.fit_decision(wbr[R.labelable(wbr, pol_all)])
        def _thr(v):
            return "—" if v is None else f"{v * 1000:+.0f}"

        thr_text = "; ".join(f"{fam}: stable ≤ {_thr(t['stable'])}, unstable > {_thr(t['unstable'])} meV/atom (n={t['n']})"
                             for fam, t in sorted(rule_all.thresholds.items())) or "none certified"
        prec_conf = rs_conf["precision of 'likely stable'"]
        thr_text += f"; weak elements: {', '.join(sorted(pol_all.weak_elements)) or 'none'}"
        (RESULTS_DIR / f"routing_rule_{tag}.json").write_text(json.dumps(
            {"thresholds": rule_all.thresholds, "weak_elements": sorted(pol_all.weak_elements),
             "target_precision": rule_all.target_precision, "target_npv": rule_all.target_npv, "conf": rule_all.conf}, indent=1))
        reasons = pd.Series([x for r in dec[dec.label == R.SEND_TO_DFT].reasons for x in r.split("; ")])
        reason_counts = reasons.str.replace(r"\(.*", "", regex=True).str.replace(r"\d+ meV/atom", "", regex=True).str.strip().value_counts()
        body += ["## 6c. Confidence and routing (calibration set, 5-fold cross-validated)", "",
                 f"Mondrian split-conformal bounds for the true hull distance, each one-sided at {1 - C.ALPHA:.0%} (a 'stable' call "
                 "uses only the upper bound, an 'unstable' call only the lower bound); groups = chemistry family × predicted hull "
                 f"bin (fallback to family, then all, below {C.MIN_GROUP} members). Chosen over isotonic calibration because it "
                 "guarantees coverage per group without assuming a monotone, well-behaved error — this model's error is biased "
                 "and heavy-tailed (see `harness/confidence.py`). Coverage measured on held-out folds (targets: each bound "
                 f"≥ {1 - C.ALPHA:.2f}, interval ≥ {1 - 2 * C.ALPHA:.2f}):", "", _md(cv, ".3f"), "",
                 "**Why the labels do not come from these bounds.** Routing on them was tried first: the bounds hold ~90 % of the "
                 f"time per group, yet only {prec_conf:.0%} of the candidates whose upper bound fell "
                 "below 0 were truly stable — marginal coverage does not control the error rate among the candidates a rule "
                 "selects. The labels therefore use per-family thresholds certified directly on that quantity (Learn-then-Test "
                 f"style): the loosest threshold whose 'stable' calls have precision ≥ {C.TARGET_PRECISION:.0%}, and the most "
                 f"inclusive whose 'unstable' calls have NPV ≥ {C.TARGET_NPV:.0%}, each with a one-sided Clopper–Pearson bound at "
                 f"{C.CERT_CONF:.0%} confidence, Bonferroni-corrected over the {len(C.DEC_GRID)}-point threshold grid. Families "
                 f"with fewer than {C.MIN_FAMILY} labelable calibration structures get no label (DFT).", "",
                 "Each held-out structure gets one label from rules fitted on the other folds: 'send to DFT' if it contains a "
                 "known-weak element (MAE lower bound > 60 meV/atom, or fewer than 20 calibration compounds), if its relaxation "
                 "left the starting structure, or if its prediction lies between the certified thresholds; otherwise 'likely "
                 "stable' / 'likely unstable'. The second engine's disagreement signal is added once a second engine has run.", "",
                 _md(pd.DataFrame({"quantity": list(rs), "certified thresholds (used)": list(rs.values()),
                                   "conformal bounds (rejected)": [rs_conf.get(k) for k in rs]}), ".3f"), "",
                 f"Certified thresholds fitted on the whole calibration set (what the product would use): {thr_text}.", "",
                 "Why candidates were sent to DFT (a candidate can have several reasons): " +
                 ", ".join(f"{k}: {v}" for k, v in reason_counts.items()) + ".", ""]
        rel = C.empirical_reliability(wb, 0.0, 500)
        rel = rel.assign(**{"call right": rel["call right"].map(lambda c: _ci(c, "{:.2f}"))})
        body += ["**How often a plain threshold-0 call is right, by chemistry family and predicted hull distance** "
                 "(observed on the calibration set; the product shows this next to every prediction):", "", _md(rel), ""]
        score.update({f"routing_{k}": v for k, v in rs.items() if isinstance(v, (int, float))})

    # ---------- 7. per element, magnetism ----------
    body += ["## 7. Errors by element and by magnetism", "",
             f"Error attributed to every element of a compound; elements in fewer than {MIN_ELEMENT_COUNT} compounds are counted, "
             "not shown. Sorted by the upper bound of the MAE.", ""]
    el_tables = {}
    if len(wb):
        t, below = M.per_element(wb, "formula", "de_mev", MIN_ELEMENT_COUNT, N_BOOT)
        el_tables["wbm"] = t
        body += [f"**New materials (WBM calibration, relaxed energy):** {len(t)} elements shown, {below} below the minimum count.", "",
                 _md(_el_md(t)), ""]
    if len(au):
        same = au[au.ctrl_outcome == "same structure"].assign(formula=lambda x: x.target_formula)
        t, below = M.per_element(same, "formula", "ctrl_dE_mev", MIN_ELEMENT_COUNT, N_BOOT)
        el_tables["mp"] = t
        body += [f"**Known materials (MP pairs, control, same structure):** {len(t)} elements shown, {below} below the minimum count.", "",
                 _md(_el_md(t)), ""]
        mag = au.assign(mag=au.pbe_magmom_per_site.map(
            lambda m: "unknown" if m is None or not np.isfinite(m) else "magnetic in PBE" if m > MAGNETIC_MOMENT_MIN else "non-magnetic in PBE"))
        body += [f"**Magnetic vs non-magnetic (MP pairs; moment > {MAGNETIC_MOMENT_MIN} μB/site in the PBE calculation), control "
                 "energy, same structure only:**", "",
                 _md(stratified_table(mag[mag.ctrl_outcome == "same structure"], compare.HULL_BINS_MP, "ctrl_dE_mev", None, "mag")), "",
                 "WBM entries carry no magnetic moments, so new materials cannot be split this way.", ""]

    # ---------- 8. worst cases ----------
    worst = []
    if len(wb):
        for r in wb.reindex(wb.de_mev.abs().sort_values(ascending=False).index).head(10).itertuples():
            worst.append({"case": f"{r.formula} ({r.wbm_id})", "set": "new (WBM)", "true e_hull": r.each_true, "energy error": r.de_mev,
                          "likely cause": likely_cause(r.formula, r.each_true, r.outcome, None, "WBM")})
    if len(au):
        for r in au.reindex(au.ctrl_dE_mev.astype(float).abs().sort_values(ascending=False).index).head(10).itertuples():
            mag_ = r.pbe_magmom_per_site is not None and np.isfinite(r.pbe_magmom_per_site) and r.pbe_magmom_per_site > MAGNETIC_MOMENT_MIN
            worst.append({"case": f"{r.target_formula} ({r.target_id})", "set": "known (MP)", "true e_hull": r.target_e_hull,
                          "energy error": r.ctrl_dE_mev, "likely cause": likely_cause(r.target_formula, r.target_e_hull, r.ctrl_outcome, mag_, "MP")})
    if worst:
        body += ["## 8. Worst cases", "", "Likely causes by fixed rules, checked in this order: far above the hull, relaxed into a "
                 "different structure, then chemistry.", "", _md(pd.DataFrame(worst), ".3f"), ""]

    # ---------- 9. experiment ----------
    if len(ex):
        rows = []
        for status, label in (("rt", "room temperature (Lucero 2012)"), ("zero_k", "0 K extrapolated (Lucero 2012)"),
                              ("zpae_removed", "0 K, zero-point expansion removed (Csonka 2009)")):
            for metal in (True, False):
                g = ex[(ex.status == status) & (ex.get("metal", False) == metal)]
                if len(g):
                    rows.append({"set": label, "class": "metals" if metal else "non-metals", "n": len(g),
                                 "MACE vs exp mean %": g.a_err_pct.mean(), "MACE vs exp MAE %": g.a_err_pct.abs().mean(),
                                 "PBE vs exp mean %": g.a_pbe_err_pct.mean(), "MACE − PBE mean %": g.a_mace_vs_pbe_pct.mean()})
        body += ["## 9. Lattice constants against experiment", "",
                 "Room-temperature and 0 K values include thermal and zero-point expansion; the Csonka set removes the zero-point "
                 "anharmonic expansion, so it is the fair target for a static 0 K calculation. PBE overestimates by ~1 %, and MACE "
                 "inherits that. **Coverage gap:** oxides are represented by MgO only, and no bcc transition metals (V, Nb, Ta, Mo, W, "
                 "Fe) have a verified source in the harness yet.", "", _md(pd.DataFrame(rows)), ""]
        if "metal" in ex:
            body += [_md(ex.sort_values("a_err_pct", key=abs, ascending=False)[
                ["material", "structure", "status", "a_exp", "a_mace", "a_pbe", "a_err_pct", "a_pbe_err_pct", "a_mace_vs_pbe_pct"]].head(20), ".3f"), ""]

    # ---------- 10. bulk modulus ----------
    if len(bk):
        ok = bk[bk.fit.map(lambda f: f["rms_mev"] <= 1.0 and f["v0_in_range"])]
        ci = M.boot_ci(ok.err_pct_vrh, M.MAE, N_BOOT)
        body += ["## 10. Bulk modulus (curated known materials)", "",
                 f"Birch–Murnaghan fits vs MP elastic K_VRH: MAE {_ci(ci, '{:.1f}')} % (n={len(ok)}), verdict "
                 f"{verdict_ci('bulk_mae_pct', ci)} (pessimistic bound). Not stratified by hull distance: every material is on or "
                 "near the hull.", ""]

    # ---------- 11. runtime ----------
    if len(jobs):
        ok = jobs[jobs.status == "ok"].dropna(subset=["runtime_s"])
        rt = ok.groupby("suite").runtime_s.agg(structures="size", median="median", p90=lambda v: v.quantile(0.9), total_h=lambda v: v.sum() / 3600)
        body += ["## 11. Runtime and job outcomes", "", _md(rt.reset_index(), ".1f"), "",
                 _md(jobs.groupby(["suite", "status"]).size().unstack(fill_value=0).reset_index(), ".0f"), ""]

    # ---------- plain-language verdict ----------
    verdict_lines += ["## Verdict in plain language", ""]
    verdict_lines.append(f"* **Engine evaluated:** {MODEL['name']} (the only engine run so far; Phase 3 compares others). "
                         "All statements below use the pessimistic end of the 95 % interval.")
    if opt and dmo:
        verdict_lines.append(
            f"* **Threshold:** call a new material stable when its predicted energy above hull is ≤ {opt['threshold'] * 1000:+.0f} meV/atom "
            f"(cost-optimal on the calibration set at the placeholder costs). At that threshold **at least "
            f"{dmo['precision_ci'][1]:.0%} of 'stable' calls are right** (point {dmo['precision']:.0%}) and at least "
            f"{dmo['recall_ci'][1]:.0%} of truly stable materials are found (point {dmo['recall']:.0%}); 'unstable' calls are "
            f"right at least {dmo['npv_ci'][1]:.1%} of the time. Precision verdict: {verdict_ci('precision', dmo['precision_ci'])}.")
    if len(wb):
        parts = []
        for b in compare.HULL_BINS_WBM:
            s = M.error_summary(wb[wb.bin == b].de_mev, N_BOOT)
            parts.append(f"{b}: ≤ {s['mae'][2]:.0f} meV/atom ({verdict_ci('energy_mae_mev', s['mae'])})")
        verdict_lines.append("* **Energy error on new materials, upper bound by true hull distance:** " + "; ".join(parts) + ".")
        if "diff_share" in locals():
            same_mae = wb[wb.outcome == "same structure"].de_mev.abs().mean()
            diff_mae = wb[wb.outcome == "relaxed into a different structure"].de_mev.abs().mean()
            verdict_lines.append("* **Relaxation changes the structure** for " + ", ".join(
                f"{diff_share.get(b, np.nan):.0%} ({b})" for b in compare.HULL_BINS_WBM)
                + f" of new materials; those results carry {diff_mae / same_mae:.1f}× the energy error of the rest "
                  f"({diff_mae:.0f} vs {same_mae:.0f} meV/atom MAE) and should go to DFT, not to the lab.")
    if len(au):
        parts = []
        same = au[au.ctrl_outcome == "same structure"]
        for b in compare.HULL_BINS_MP:
            s = M.error_summary(same[same.bin == b].ctrl_dE_mev, N_BOOT)
            parts.append(f"{b}: ≤ {s['mae'][2]:.0f} ({verdict_ci('energy_mae_mev', s['mae'])})")
        verdict_lines.append("* **Known materials that keep their structure, energy error upper bound (meV/atom):** " + "; ".join(parts) + ".")
    if "wbm" in el_tables and len(el_tables["wbm"]):
        t = el_tables["wbm"]
        good = [r.element for r in t.itertuples() if r.MAE[2] <= VERDICT_RULES["energy_mae_mev"][0]]
        bad = [r.element for r in t.itertuples() if r.MAE[1] > VERDICT_RULES["energy_mae_mev"][1]]
        verdict_lines.append(f"* **Chemistries (new materials, ≥ {MIN_ELEMENT_COUNT} compounds):** error upper bound ≤ 30 meV/atom for "
                             f"{', '.join(good) or 'no element'}; error lower bound > 60 meV/atom (not trustworthy) for "
                             f"{', '.join(bad) or 'no element'}.")
    if "mode_b_diff" in locals() and np.isfinite(mode_b_diff[0]):
        lo, hi = mode_b_diff[1], mode_b_diff[2]
        if lo > 0:
            txt = (f"relaxing every competing phase with the engine makes the hull-distance error **larger** by "
                   f"{_ci(mode_b_diff, '{:+.1f}')} meV/atom per system than placing the engine's energy on the MP DFT hull (mode a). "
                   "On new materials the error belongs to the new structure and does not cancel against the competitors; "
                   "mode (a) is the better construction for the product, and it needs no competitor relaxations.")
        elif hi < 0:
            txt = f"mode (b) reduces the hull-distance error by {_ci(mode_b_diff, '{:+.1f}')} meV/atom per system versus mode (a)."
        else:
            txt = f"mode (b) and mode (a) are not distinguishable ({_ci(mode_b_diff, '{:+.1f}')} meV/atom per system)."
        verdict_lines.append(f"* **Hull construction for new materials:** {txt}")
    verdict_lines.append("* **Not yet shown:** the locked WBM test set (final evaluation) and other engines (Phase 3: downloads awaiting approval).")
    verdict_lines.append("")

    # ---------- write ----------
    mi = machine_info()
    head = [f"# Validation report — {MODEL['name']}", "",
            f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · commit `{score['commit']}` · settings tag `{tag}` · "
            f"model `{MODEL['file']}` · {compute['device']}/{compute['dtype']} · {mi['chip']} · macOS {mi['macos']}", "",
            f"Relaxation: {DEFAULT_RELAX.cell_filter} + {DEFAULT_RELAX.optimizer}, fmax {DEFAULT_RELAX.fmax} eV/Å, |stress| ≤ "
            f"{DEFAULT_RELAX.max_stress_gpa} GPa, ≤ {DEFAULT_RELAX.max_steps} steps, fallback ladder on failure. Bins: energy above hull "
            "(eV/atom) — MP targets on the GGA/GGA+U hull, WBM against the MP hull (with a '<0' bin). Brackets: 95 % bootstrap "
            "intervals; verdicts from the pessimistic end.", ""]
    L = head + verdict_lines + (comparison_lines(out_dir, score) if compare_previous else []) + body
    L += ["## Files", "", "* `results/results.sqlite` — every job and result with provenance and settings",
          "* `results/results.parquet` — the results table", "* `data/wbm_split.json` — the calibration / locked-test split",
          "* `figures/` and `scorecard.json` next to this report", ""]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "validation_report.md"
    out.write_text("\n".join(L) + "\n")
    (out_dir / "scorecard.json").write_text(json.dumps({k: (float(v) if isinstance(v, (np.floating, float)) else v)
                                                         for k, v in score.items()}, indent=1, default=str) + "\n")
    res = store.load_table("results")
    if len(res):
        res["settings_tag"] = res.job_key.map(lambda k: k.rsplit("@", 1)[1] if "@" in k else "pre-tag")
        res.to_parquet(RESULTS_DIR / "results.parquet", index=False)
    log.info("report written: %s", out)
    return str(out.relative_to(ROOT)) if out.resolve().is_relative_to(ROOT) else str(out)


def _el_md(t: pd.DataFrame) -> pd.DataFrame:
    if not len(t):
        return t
    return pd.DataFrame({"element": t.element, "n": t.n, "MAE meV/atom": t.MAE.map(_ci),
                         "mean signed": t["mean signed"].map(lambda c: _ci(c, "{:+.1f}")),
                         "verdict (upper bound)": t.MAE.map(lambda c: verdict_ci("energy_mae_mev", c))})
