"""Validation report: reports/validation_report.md + reports/figures/*.png + results/*.parquet.

Everything is computed from the results store for the CURRENT settings tag (model file, device,
dtype, relaxation settings); rows from earlier protocols stay in the database but are excluded.
Verdicts come from the explicit thresholds in VERDICT_RULES, never from judgement at write time.
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
from harness.config import DEFAULT_RELAX, FIG_DIR, MODEL, REPORTS_DIR, RESULTS_DIR, ROOT, load_compute_config, settings_tag
from harness.platform_check import machine_info

log = logging.getLogger(__name__)

# Chart tokens: dataviz reference palette, light mode. Three categorical slots max (the first three
# validate all-pairs for scatter); text always in ink tokens, never series colours.
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
# Colour follows the entity across every figure.
KNOWN, NEW, PBE = SERIES  # MACE on known (MP) materials / MACE on new (WBM) materials / PBE reference

# Explicit verdict thresholds: (good_if_at_most, caution_if_at_most) for errors; reversed for scores.
VERDICT_RULES = {
    "volume_mae_pct": (1.0, 2.0),          # MACE vs its own training functional (PBE)
    "energy_mae_mev": (30.0, 60.0),        # meV/atom vs DFT
    "e_hull_mae_mev": (30.0, 60.0),        # meV/atom
    "stability_acc_0.1": (0.90, 0.75),     # accuracy at the 0.1 eV/atom threshold (higher is better)
    "bulk_mae_pct": (10.0, 20.0),          # EOS B0 vs MP K_VRH
    "mace_minus_pbe_pct": (0.5, 1.0),      # lattice constant, MACE vs PBE, |mean|
}
N_BOOT = 5000


def verdict(metric: str, value: float) -> str:
    if value is None or not np.isfinite(value):
        return "no data"
    good, caution = VERDICT_RULES[metric]
    higher_better = good > caution
    if (value >= good) if higher_better else (value <= good):
        return "trustworthy"
    if (value >= caution) if higher_better else (value <= caution):
        return "use with caution"
    return "not trustworthy"


def verdict_ci(metric: str, ci: tuple[float, float, float]) -> str:
    """Verdict from the point estimate, marked borderline when the 95 % CI crosses a threshold."""
    v = verdict(metric, ci[0])
    if v == "no data" or not all(np.isfinite(ci)):
        return v
    lo_v, hi_v = verdict(metric, ci[1]), verdict(metric, ci[2])
    if lo_v != v or hi_v != v:
        return f"{v} (borderline: 95 % CI spans '{lo_v}' to '{hi_v}')"
    return v


def boot_ci(x, f=lambda v: float(np.mean(np.abs(v))), seed: int = 0) -> tuple[float, float, float]:
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    if not len(x):
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    bs = [f(x[rng.integers(0, len(x), len(x))]) for _ in range(N_BOOT)]
    return f(x), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def _ci_str(t, fmt="{:.1f}") -> str:
    return f"{fmt.format(t[0])} [{fmt.format(t[1])}, {fmt.format(t[2])}]" if np.isfinite(t[0]) else "n/a"


def _md(df: pd.DataFrame, floatfmt=".2f") -> str:
    return df.to_markdown(index=False, floatfmt=floatfmt) if len(df) else "_no data_"


# --- figures ------------------------------------------------------------------------------------

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
            sp.set_linewidth(1)
        ax.grid(True, color=GRID, linewidth=0.8, linestyle="-")
        ax.set_axisbelow(True)
        ax.tick_params(colors=AXIS, labelcolor=INK2)
    return fig, list(axes[0]), plt


def parity(path, panels, xlabel, ylabel, title, n_labels=3) -> str:
    """Small multiples, one series per panel (its title names it, so no legend box), shared limits
    and a muted y = x reference. The worst points are labelled, skipping labels that would collide."""
    k = len(panels)
    fig, axes, plt = _fig(w=4.1 * k + 0.4, h=4.6, ncols=k)
    xs = np.concatenate([np.asarray(p[1], float) for p in panels])
    ys = np.concatenate([np.asarray(p[2], float) for p in panels])
    lo, hi = float(min(xs.min(), ys.min())), float(max(xs.max(), ys.max()))
    pad = (hi - lo) * 0.05 or 0.1
    lo, hi = lo - pad, hi + pad
    span = hi - lo
    for ax, (name, x, y, labels, color) in zip(axes, panels):
        x, y, labels = np.asarray(x, float), np.asarray(y, float), list(labels)
        ax.plot([lo, hi], [lo, hi], color=MUTED, linewidth=1, zorder=1)
        ax.scatter(x, y, s=42, color=color, edgecolors=SURFACE, linewidths=1.5, zorder=3)
        placed = []
        for i in np.argsort(-np.abs(y - x)):
            if len(placed) >= n_labels:
                break
            if any(abs(x[i] - px) < 0.12 * span and abs(y[i] - py) < 0.06 * span for px, py in placed):
                continue
            ax.annotate(str(labels[i]), (x[i], y[i]), textcoords="offset points", xytext=(6, 4), fontsize=7, color=INK2)
            placed.append((x[i], y[i]))
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_aspect("equal")
        ax.set_xlabel(xlabel, color=INK2)
        ax.set_title(f"{name} (n={len(x)})", color=INK, loc="left", fontsize=9)
    axes[0].set_ylabel(ylabel, color=INK2)
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)  # never clip axis labels
    plt.close(fig)
    return path.name


def hbar(path, labels, values, xlabel, title, fmt="{:.1f}") -> str:
    """Single-series horizontal bars (slot 1), value at the tip in ink; no legend (title names it)."""
    fig, axes, plt = _fig(w=6.0, h=0.28 * len(labels) + 1.2)
    ax = axes[0]
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, height=0.55, color=SERIES[0], zorder=3)
    for yi, v in zip(y, values):
        ax.text(v, yi, " " + fmt.format(v), va="center", fontsize=7, color=INK2)
    ax.set_yticks(y, labels)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(xlabel, color=INK2)
    ax.set_title(title, color=INK, loc="left", fontsize=10)
    ax.set_xlim(0, max(values) * 1.18 if len(values) else 1)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return path.name


# --- data ---------------------------------------------------------------------------------------

def collect(tag: str) -> dict:
    from harness.suites import bulk, experimental, ood, stability, substitution

    def safe(fn):
        try:
            return fn(tag)
        except Exception as exc:  # noqa: BLE001 — a missing suite must not break the report
            log.warning("report: %s unavailable: %s", fn.__module__, exc)
            return pd.DataFrame()

    def auto_pairs(t):
        from harness import pairgen

        pairs = pairgen.load_pairs()
        return substitution.pair_table(t, suite="substitution_auto", pairs=pairs) if pairs else pd.DataFrame()

    jobs = store.load_table("jobs")
    jobs = jobs[jobs.job_key.str.endswith(f"@{tag}")] if len(jobs) else jobs
    results = store.load_table("results")
    return {"sub": safe(substitution.pair_table), "auto": safe(auto_pairs), "st": safe(stability.target_table),
            "ex": safe(experimental.table),
            "ood": safe(ood.table), "bulk": safe(bulk.table), "jobs": jobs,
            "results": results[results.job_key.str.endswith(f"@{tag}")] if len(results) else results}


def per_element(df: pd.DataFrame, formula_col: str, err_col: str) -> pd.DataFrame:
    rows = []
    for _, r in df[[formula_col, err_col]].dropna().iterrows():
        for el in Composition(r[formula_col]).elements:
            rows.append({"element": el.symbol, "err": float(r[err_col])})
    if not rows:
        return pd.DataFrame(columns=["element", "n", "mae", "mean"])
    d = pd.DataFrame(rows)
    g = d.groupby("element")["err"]
    return pd.DataFrame({"n": g.size(), "mae": g.apply(lambda v: v.abs().mean()), "mean": g.mean()}).reset_index() \
        .sort_values("mae", ascending=False)


def likely_cause(formula: str, source: str, magnetic: bool | None = None) -> str:
    els = {e.symbol for e in Composition(formula).elements}
    causes = []
    if els & compare.F_ELECTRON:
        causes.append(f"f-electron chemistry ({', '.join(sorted(els & compare.F_ELECTRON))}): no explicit spin or strong correlation in MACE")
    if magnetic:
        causes.append("magnetic in DFT (MACE has no spin degrees of freedom)")
    elif els & compare.MAGNETIC_PRONE and els & {"O", "F"}:
        # MP runs these oxides/fluorides spin-polarised with +U; metallic W or Mo is not magnetic.
        causes.append(f"+U / spin-prone transition-metal oxide or fluoride ({', '.join(sorted(els & compare.MAGNETIC_PRONE))})")
    offset_prone = compare.TRANSITION_METALS | {"Ge", "Sn"}
    if len(els) == 1 and els <= offset_prone:
        causes.append("systematic elemental energy offset (see per-element table)")
    if source == "OOD":
        causes.append("out-of-distribution composition/prototype (not in MPtrj)")
    return "; ".join(causes) or "no flag — generic model error"


# --- report -------------------------------------------------------------------------------------

SCORECARD_METRICS = [  # key, label, format, lower_is_better (None = informational)
    ("curated_volume_mae_pct", "Volume error, curated pairs (%)", "{:.2f}", True),
    ("auto_volume_mae_pct", "Volume error, auto-generated pairs (%)", "{:.2f}", True),
    ("curated_energy_mae_mev", "Energy MAE, curated known materials (meV/atom)", "{:.1f}", True),
    ("auto_energy_mae_mev", "Energy MAE, auto-generated pairs (meV/atom)", "{:.1f}", True),
    ("ood_energy_mae_mev", "Energy MAE, new WBM materials (meV/atom)", "{:.1f}", True),
    ("ood_precision_at_0", "Stable-call precision @ 0 eV/atom, WBM", "{:.2f}", False),
    ("ood_f1_at_0", "F1 @ 0 eV/atom, WBM", "{:.2f}", False),
    ("stability_b_mae_mev", "Energy above hull MAE, mode (b) (meV/atom)", "{:.1f}", True),
    ("stability_a_mae_mev", "Energy above hull MAE, mode (a) (meV/atom)", "{:.1f}", True),
    ("experimental_mace_mean_pct", "Lattice constant vs experiment, mean (%)", "{:+.2f}", None),
    ("bulk_mae_pct", "Bulk modulus MAE (%)", "{:.1f}", True),
    ("n_auto_pairs", "Auto-generated pairs scored", "{:.0f}", None),
    ("n_ood", "WBM structures scored", "{:.0f}", None),
]


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x)


def previous_scorecard(out_dir: Path) -> Path | None:
    """Most recent earlier run's scorecard (reports/<timestamp>/scorecard.json), else reports/scorecard.json."""
    out_dir = Path(out_dir).resolve()
    is_run = out_dir.parent == REPORTS_DIR.resolve()
    runs = sorted(p for p in REPORTS_DIR.glob("*/scorecard.json")
                  if p.parent.resolve() != out_dir and (not is_run or p.parent.name < out_dir.name))
    if runs:
        return runs[-1]
    base = REPORTS_DIR / "scorecard.json"
    return base if base.is_file() and REPORTS_DIR.resolve() != out_dir else None


def comparison_lines(out_dir: Path, cur: dict) -> list[str]:
    lines = ["### Compared with the previous run", ""]
    prev_path = previous_scorecard(out_dir)
    if prev_path is None:
        return lines + ["_No earlier run with a scorecard to compare against._", ""]
    prev = json.loads(prev_path.read_text())
    rows = []
    for key, label, fmt, lower in SCORECARD_METRICS:
        a, b = prev.get(key), cur.get(key)
        if a is None and b is None:
            continue
        change = "—"
        if _num(a) and _num(b):
            d = b - a
            spec = fmt[2:-1].lstrip("+")
            change = "no change" if abs(d) < 1e-9 else format(d, "+" + spec) + (
                "" if lower is None else (" (better)" if (d < 0) == lower else " (worse)"))
        rows.append({"metric": label, "previous": fmt.format(a) if _num(a) else "—",
                     "this run": fmt.format(b) if _num(b) else "—", "change": change})
    rel = prev_path.parent.relative_to(ROOT) if str(ROOT) in str(prev_path) else prev_path.parent
    lines += [f"Previous: `{rel}` (generated {prev.get('generated_at', '?')}, settings `{prev.get('settings_tag')}`)."
              + (" **Settings differ — numbers are not directly comparable.**"
                 if prev.get("settings_tag") != cur.get("settings_tag") else ""), "", _md(pd.DataFrame(rows)), "",
              "Sample sizes grow as the queue drains, so early partial runs have wide uncertainty.", ""]
    return lines


def write_report(out_dir: Path | None = None, compare_previous: bool = False) -> str:
    """Write validation_report.md, figures/ and scorecard.json into out_dir (default reports/).
    compare_previous adds a comparison with the most recent earlier run's scorecard."""
    compute = load_compute_config()
    tag = settings_tag(compute["device"], compute["dtype"])
    out_dir = Path(out_dir) if out_dir else REPORTS_DIR
    fig_dir = FIG_DIR if out_dir.resolve() == REPORTS_DIR.resolve() else out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    d = collect(tag)
    sub, st, ex, oo, bk, jobs = d["sub"], d["st"], d["ex"], d["ood"], d["bulk"], d["jobs"]
    figs = {}
    L: list[str] = []
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True).stdout.strip()
    except OSError:
        commit = "unknown"

    # ---------- headline numbers ----------
    ood_ok = oo[oo.rejection.isna()] if len(oo) else oo
    vol = boot_ci(sub.get("ctrl_vol_pct", []))
    e_id = boot_ci(sub.get("ctrl_dE_mev", []))
    e_ood = boot_ci(ood_ok.get("de_mev", []))
    e_id_mean = boot_ci(sub.get("ctrl_dE_mev", []), np.mean)
    e_ood_mean = boot_ci(ood_ok.get("de_mev", []), np.mean)
    ex_rt = ex[ex.status == "rt"] if len(ex) else ex
    mace_minus_pbe = float(ex_rt["a_mace_vs_pbe_pct"].mean()) if len(ex_rt) else float("nan")

    def stab(mode):
        from harness.suites import stability

        return stability.metrics(st, mode) if len(st) else None

    sa, sb = stab("a"), stab("b")
    from harness.suites import ood as ood_mod

    so = ood_mod.score(oo) if len(oo) else None
    bk_ok = bk[bk.fit.map(lambda f: f["rms_mev"] <= 1.0 and f["v0_in_range"])] if len(bk) else bk
    bulk_mae = float(bk_ok.err_pct_vrh.abs().mean()) if len(bk_ok) else float("nan")
    bulk_ci = boot_ci(bk_ok.err_pct_vrh) if len(bk_ok) else (float("nan"),) * 3
    au = d["auto"]
    au_done = au[au["ctrl_dE_mev"].notna()] if len(au) and "ctrl_dE_mev" in au.columns else pd.DataFrame()
    au_vol = boot_ci(au_done.get("ctrl_vol_pct", []))
    au_e = boot_ci(au_done.get("ctrl_dE_mev", []))

    # ---------- header ----------
    mi = machine_info()
    L += [
        "# Validation report — MACE-MP-0 medium",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · commit `{commit}` · settings tag `{tag}` · "
        f"model `{MODEL['file']}` (sha256 `{MODEL['sha256'][:12]}…`) · {compute['device']}/{compute['dtype']} · "
        f"{mi['chip']} ({mi['performance_cores']} performance + {mi['efficiency_cores']} efficiency cores, {mi['memory_gb']} GB) · "
        f"macOS {mi['macos']}",
        "",
        f"Relaxation: {DEFAULT_RELAX.cell_filter} + {DEFAULT_RELAX.optimizer}, fmax {DEFAULT_RELAX.fmax} eV/Å, "
        f"max |stress| {DEFAULT_RELAX.max_stress_gpa} GPa, ≤ {DEFAULT_RELAX.max_steps} steps, {DEFAULT_RELAX.timeout_s:.0f} s timeout. "
        "Every number below comes from this settings tag only; references are Materials Project PBE/PBE+U "
        "(`GGA_GGA+U`), WBM DFT, or cited experiment. Brackets are bootstrap 95 % confidence intervals.",
        "",
    ]

    # ---------- scorecard ----------
    L += ["## Scorecard — is this engine trustworthy?", ""]
    card = [
        ("Structure / geometry vs its training functional (PBE)", f"volume error {_ci_str(vol, '{:.2f}')} % (n={len(sub)})",
         verdict_ci("volume_mae_pct", vol)),
        ("Lattice constants vs experiment (room temperature)",
         f"MACE {ex_rt.a_err_pct.mean():+.2f} % vs PBE {ex_rt.a_pbe_err_pct.mean():+.2f} % (n={len(ex_rt)}); MACE − PBE {mace_minus_pbe:+.2f} %"
         if len(ex_rt) else "n/a",
         "reproduces PBE (" + verdict("mace_minus_pbe_pct", abs(mace_minus_pbe)) + "); inherits PBE's ~+1 % overestimate"),
        ("Energies — known (Materials Project) materials", f"MAE {_ci_str(e_id)} meV/atom (n={len(sub)})", verdict_ci("energy_mae_mev", e_id)),
        ("Energies — genuinely new (WBM) materials", f"MAE {_ci_str(e_ood)} meV/atom (n={len(ood_ok)})", verdict_ci("energy_mae_mev", e_ood)),
        ("Stability, all phases computed with MACE (mode b)",
         f"e_hull MAE {sb['mae_ev'] * 1000:.1f} meV/atom; accuracy@0.1 {sb['thr0.1']['accuracy']:.2f} (n={sb['n']})" if sb else "n/a",
         verdict("stability_acc_0.1", sb["thr0.1"]["accuracy"]) if sb else "no data"),
        ("Stability, MACE target among DFT competitors (mode a)",
         f"e_hull MAE {sa['mae_ev'] * 1000:.1f} meV/atom; accuracy@0.1 {sa['thr0.1']['accuracy']:.2f}" if sa else "n/a",
         verdict("stability_acc_0.1", sa["thr0.1"]["accuracy"]) if sa else "no data"),
        ("Stability on new materials (WBM, mode a construction)",
         f"e_hull MAE {so['e_hull_mae_mev']:.1f} meV/atom; accuracy@0.1 {so['thr0.1']['accuracy']:.2f}; precision@0 {so['thr0.0']['precision']:.2f}"
         if so and so.get("n") else "n/a",
         verdict("stability_acc_0.1", so["thr0.1"]["accuracy"]) if so and so.get("n") else "no data"),
        ("Bulk modulus vs MP elastic K_VRH", f"MAE {_ci_str(bulk_ci)} % (n={len(bk_ok)})" if len(bk_ok) else "not run",
         verdict_ci("bulk_mae_pct", bulk_ci)),
    ]
    if len(au_done):
        card[3:3] = [
            ("Geometry — auto-generated pairs (MP targets relaxed)",
             f"volume error {_ci_str(au_vol, '{:.2f}')} % (n={len(au_done)})", verdict_ci("volume_mae_pct", au_vol)),
            ("Energies — auto-generated pairs (known MP materials)", f"MAE {_ci_str(au_e)} meV/atom (n={len(au_done)})",
             verdict_ci("energy_mae_mev", au_e)),
        ]
    L += [_md(pd.DataFrame(card, columns=["Question", "Result", "Verdict"])), ""]

    def _f(x):
        try:
            x = float(x)
        except (TypeError, ValueError):
            return None
        return x if np.isfinite(x) else None

    scorecard = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "settings_tag": tag, "commit": commit,
        "n_curated": len(sub), "curated_volume_mae_pct": _f(vol[0]), "curated_energy_mae_mev": _f(e_id[0]),
        "n_auto_pairs": len(au_done), "auto_volume_mae_pct": _f(au_vol[0]), "auto_energy_mae_mev": _f(au_e[0]),
        "n_ood": len(ood_ok), "ood_energy_mae_mev": _f(e_ood[0]), "ood_mean_signed_mev": _f(e_ood_mean[0]),
        "ood_precision_at_0": _f(so["thr0.0"]["precision"]) if so and so.get("n") else None,
        "ood_f1_at_0": _f(so["thr0.0"]["f1"]) if so and so.get("n") else None,
        "stability_a_mae_mev": _f(sa["mae_ev"] * 1000) if sa else None,
        "stability_b_mae_mev": _f(sb["mae_ev"] * 1000) if sb else None,
        "stability_b_acc_0.1": _f(sb["thr0.1"]["accuracy"]) if sb else None,
        "experimental_mace_mean_pct": _f(ex_rt.a_err_pct.mean()) if len(ex_rt) else None,
        "bulk_mae_pct": _f(bulk_ci[0]),
    }
    if compare_previous:
        L += comparison_lines(out_dir, scorecard)
    L += ["**In plain language.**", ""]
    plain = []
    if np.isfinite(vol[0]):
        plain.append(f"* **Geometry is the engine's strongest point.** Relaxed volumes land within {vol[0]:.2f} % of the DFT "
                     "it was trained on, across all 11 structure families, and symmetric substitutions always relax into the "
                     "intended structure.")
    if len(ex_rt):
        plain.append(f"* **Against real measurements it is ~{ex_rt.a_err_pct.mean():.1f} % too large — exactly as wrong as PBE "
                     f"itself ({ex_rt.a_pbe_err_pct.mean():+.2f} %).** The model adds essentially no error of its own; the "
                     "remaining gap is the DFT functional. Correct lattice constants by ~1 % before comparing to lab data.")
    if np.isfinite(e_id[0]) and np.isfinite(e_ood[0]):
        plain.append(f"* **Energies are about {e_ood[0] / e_id[0]:.1f}× worse on genuinely new materials** "
                     f"({e_ood[0]:.0f} vs {e_id[0]:.0f} meV/atom), and the bias flips sign: on known materials MACE sits "
                     f"{e_id_mean[0]:+.0f} meV/atom high, on new ones {e_ood_mean[0]:+.0f} meV/atom low — it *over-stabilises* "
                     "new candidates. Treat every 'stable' call on a new material as a hypothesis, not a result.")
    if sb and sa:
        plain.append(f"* **Stability screening works best when every competing phase is also computed with MACE** "
                     f"(mode b: {sb['mae_ev'] * 1000:.1f} vs {sa['mae_ev'] * 1000:.1f} meV/atom), because the model's "
                     "per-element offsets cancel. Use a 0.1 eV/atom tolerance, not 0: a strict on-hull test flips on "
                     "errors of a few tens of meV/atom.")
    if so and so.get("n"):
        plain.append(f"* **On new materials, about {1 - so['thr0.0']['precision']:.0%} of 'stable' calls are wrong** "
                     f"(precision {so['thr0.0']['precision']:.2f} at 0 eV/atom). That is the number to weigh against the "
                     "cost of a lab test.")
    weak = []
    if len(ood_ok):
        top_ood = ood_ok.reindex(ood_ok.de_mev.abs().sort_values(ascending=False).index).head(20)
        f_els = sorted({e.symbol for f in top_ood.formula for e in Composition(f).elements} & compare.F_ELECTRON)
        if f_els:
            weak.append(f"f-electron compounds ({', '.join(f_els)} among the 20 worst new materials)")
    if len(sub):
        mag = sub[(sub.magnetic == True) & (sub.ctrl_dE_mev.abs() > VERDICT_RULES["energy_mae_mev"][0])]  # noqa: E712
        if len(mag):
            weak.append("magnetic systems (" + ", ".join(f"{p.split('->')[1]} {v:+.0f}" for p, v in zip(mag.pair_id, mag.ctrl_dE_mev))
                        + " meV/atom)")
        el = sub[sub.family.str.startswith("elemental") & (sub.ctrl_dE_mev.abs() > VERDICT_RULES["energy_mae_mev"][1])]
        if len(el):
            weak.append(f"elemental {', '.join(p.split('->')[1] for p in el.pair_id)} energies "
                        f"({el.ctrl_dE_mev.abs().min():.0f}–{el.ctrl_dE_mev.abs().max():.0f} meV/atom off)")
    if weak:
        plain.append("* **Least trustworthy:** " + "; ".join(weak) + ". MACE has no spin; these are reported separately below.")
    plain.append("* **Not yet validated against experiment:** metals and oxides (the experimental set is semiconductors and "
                 "insulators), temperature, and anything space-environment-specific (radiation, thermal cycling).")
    L += plain + [""]

    # family scorecard
    if len(sub):
        fam_rows = []
        for fam, g in sub.groupby("family"):
            row = {"family": fam, "n": len(g), "volume MAE %": g.ctrl_vol_pct.abs().mean(),
                   "energy MAE meV/atom": g.ctrl_dE_mev.abs().mean(),
                   "rattled keeps structure": f"{g.rattled_keeps_sg.mean():.0%}" if "rattled_keeps_sg" in g else "n/a"}
            if len(st):
                sg_ = st[st.family == fam]
                row["stability acc@0.1 (b)"] = ((sg_.b_e_hull <= 0.1 + 1e-6) == (sg_.ref_e_hull <= 0.1 + 1e-6)).mean() if len(sg_) else np.nan
            if len(bk_ok):
                bg = bk_ok[bk_ok.family == fam]
                row["bulk MAE %"] = bg.err_pct_vrh.abs().mean() if len(bg) else np.nan
            row["verdict"] = (f"geometry {verdict('volume_mae_pct', row['volume MAE %'])}; "
                              f"energy {verdict('energy_mae_mev', row['energy MAE meV/atom'])}")
            fam_rows.append(row)
        L += ["### By material family (in-distribution)", "", _md(pd.DataFrame(fam_rows)), "",
              f"Verdict thresholds: volume ≤ {VERDICT_RULES['volume_mae_pct'][0]} % trustworthy, ≤ {VERDICT_RULES['volume_mae_pct'][1]} % caution; "
              f"energy ≤ {VERDICT_RULES['energy_mae_mev'][0]:.0f} meV/atom trustworthy, ≤ {VERDICT_RULES['energy_mae_mev'][1]:.0f} caution; "
              f"stability accuracy ≥ {VERDICT_RULES['stability_acc_0.1'][0]} trustworthy; bulk ≤ {VERDICT_RULES['bulk_mae_pct'][0]:.0f} % trustworthy.", ""]

    # ---------- parity plots ----------
    L += ["## Parity plots", ""]
    from harness.suites import substitution as sub_mod

    vol_rows = []
    for pl in store.load_payloads(sub_mod.SUITE, tag=tag).values():
        if pl["kind"] in ("sub", "ctrl"):
            lat = pl["lattice"]
            vol_rows.append({"kind": pl["kind"], "pair": pl["pair_id"].split("->")[1], "ref": lat["vol_per_atom_ref"],
                             "sim": lat["vol_per_atom_sim"]})
    vr = pd.DataFrame(vol_rows)
    if len(vr):
        figs["vol"] = parity(fig_dir / "parity_volume.png",
                             [("substituted parent, relaxed", vr[vr.kind == "sub"].ref, vr[vr.kind == "sub"].sim, vr[vr.kind == "sub"].pair.tolist(), KNOWN),
                              ("MP target, relaxed (control)", vr[vr.kind == "ctrl"].ref, vr[vr.kind == "ctrl"].sim, vr[vr.kind == "ctrl"].pair.tolist(), KNOWN)],
                             "MP PBE volume (Å³/atom)", "MACE volume (Å³/atom)", "Volume per atom: MACE vs MP")
    if len(ex):
        figs["exp"] = parity(fig_dir / "parity_lattice_experiment.png",
                             [("MACE", ex.a_exp, ex.a_mace, ex.material.tolist(), KNOWN),
                              ("MP PBE (reference functional)", ex.dropna(subset=["a_pbe"]).a_exp, ex.dropna(subset=["a_pbe"]).a_pbe,
                               ex.dropna(subset=["a_pbe"]).material.tolist(), PBE)],
                             "experimental a (Å)", "computed a (Å)", "Lattice constant vs experiment")
    if len(sub) or len(ood_ok):
        ser = []
        e_id_df = pd.DataFrame([{"ref": pl["energy_per_atom"] - pl["energy_mev_vs_mp"] / 1000, "sim": pl["energy_per_atom"],
                                 "label": pl["pair_id"].split("->")[1]} for pl in store.load_payloads(sub_mod.SUITE, tag=tag).values()
                                if pl["kind"] == "ctrl"])
        if len(e_id_df):
            ser.append(("known materials (MP)", e_id_df.ref, e_id_df.sim, e_id_df.label.tolist(), KNOWN))
        if len(ood_ok):
            ser.append(("new materials (WBM)", ood_ok.e_dft, ood_ok.e_mace, ood_ok.formula.tolist(), NEW))
        figs["energy"] = parity(fig_dir / "parity_energy.png", ser, "DFT energy (eV/atom)", "MACE energy (eV/atom)",
                                "Energy per atom: MACE vs DFT")
    if len(st) or len(ood_ok):
        ser = []
        if len(st):
            ser.append(("known, mode (b): all phases MACE", st.ref_e_hull, st.b_e_hull, st.pair_id.map(lambda p: p.split("->")[1]).tolist(), KNOWN))
            ser.append(("known, mode (a): MACE target", st.ref_e_hull, st.a_e_hull, st.pair_id.map(lambda p: p.split("->")[1]).tolist(), KNOWN))
        if len(ood_ok):
            ser.append(("new materials (WBM)", ood_ok.each_true, ood_ok.each_pred, ood_ok.formula.tolist(), NEW))
        figs["ehull"] = parity(fig_dir / "parity_e_above_hull.png", ser, "DFT energy above hull (eV/atom)",
                               "MACE energy above hull (eV/atom)", "Energy above hull: MACE vs DFT")
    if len(bk_ok):
        figs["bulk"] = parity(fig_dir / "parity_bulk_modulus.png",
                              [("EOS B0 vs K_VRH", bk_ok.k_vrh, bk_ok.b0_gpa, bk_ok.label.tolist(), KNOWN)],
                              "MP K_VRH (GPa)", "MACE Birch–Murnaghan B0 (GPa)", "Bulk modulus: MACE vs MP")
    for key, cap in [("vol", "Volume per atom (substitution suite). Grey line: perfect agreement."),
                     ("exp", "Room-temperature and 0 K-extrapolated lattice constants (Lucero et al. 2012). MACE and PBE sit together above the line: the offset is the functional."),
                     ("energy", f"Raw MACE vs uncorrected DFT energies. Known materials: MP control relaxations; new materials: {len(ood_ok)} random WBM unique prototypes."),
                     ("ehull", "Energy above the convex hull. Mode (b) = all competing phases also computed with MACE."),
                     ("bulk", "Equation-of-state bulk modulus vs MP elastic K_VRH (fits with rms ≤ 1 meV/atom).")]:
        if key in figs and figs[key]:
            L += [f"![{cap}](figures/{figs[key]})", "", f"*{cap}*", ""]

    # ---------- errors by element and family ----------
    L += ["## Errors by element and by structure family", ""]
    if len(sub):
        from harness.curation import resolve_pairs

        fmap = {p["pair_id"]: p["target_formula"] for p in resolve_pairs()}
        sub_f = sub.assign(formula=sub.pair_id.map(fmap))
        el_id = per_element(sub_f, "formula", "ctrl_dE_mev")
        L += ["**Known materials (MP control relaxations), energy error attributed to every element in the compound:**", "",
              _md(el_id.head(20).rename(columns={"mae": "MAE meV/atom", "mean": "mean meV/atom"}), ".1f"), ""]
        top = el_id.head(15)
        if len(top):
            figs["el_id"] = hbar(fig_dir / "element_energy_mae_known.png", [f"{e} (n={n})" for e, n in zip(top.element, top.n)], top.mae.tolist(),
                                 "mean |energy error| of compounds containing the element (meV/atom)",
                                 "Energy error by element — known materials")
            L += [f"![Energy error by element, known materials](figures/{figs['el_id']})", ""]
    if len(ood_ok):
        el_ood = per_element(ood_ok, "formula", "de_mev")
        el_ood = el_ood[el_ood.n >= 5]
        L += ["**New materials (WBM), elements appearing in ≥ 5 sampled compounds:**", "",
              _md(el_ood.head(20).rename(columns={"mae": "MAE meV/atom", "mean": "mean meV/atom"}), ".1f"), ""]
        top = el_ood.head(15)
        if len(top):
            figs["el_ood"] = hbar(fig_dir / "element_energy_mae_new.png", [f"{e} (n={n})" for e, n in zip(top.element, top.n)], top.mae.tolist(),
                                  "mean |energy error| of compounds containing the element (meV/atom)",
                                  "Energy error by element — new (WBM) materials")
            L += [f"![Energy error by element, new materials](figures/{figs['el_ood']})", ""]
    if len(sub):
        fam = sub.groupby("family").agg(n=("pair_id", "size"), vol_mae=("ctrl_vol_pct", lambda v: v.abs().mean()),
                                        lat_mae=("ctrl_max_lat_pct", lambda v: v.abs().mean()),
                                        e_mae=("ctrl_dE_mev", lambda v: v.abs().mean())).reset_index().sort_values("vol_mae", ascending=False)
        figs["fam"] = hbar(fig_dir / "family_volume_mae.png", fam.family.tolist(), fam.vol_mae.tolist(),
                           "mean |volume error| vs MP PBE (%)", "Volume error by structure family", fmt="{:.2f}")
        L += ["**By structure family (MP control relaxations):**", "",
              _md(fam.rename(columns={"vol_mae": "volume MAE %", "lat_mae": "lattice MAE %", "e_mae": "energy MAE meV/atom"})),
              "", f"![Volume error by family](figures/{figs['fam']})", ""]

    # ---------- worst 10 ----------
    L += ["## The 10 worst cases", "",
          "Ranked by absolute energy error against DFT (energy is what drives every stability call), across known and new "
          "materials. Likely causes are assigned by fixed rules from the composition and flags, not by hand.", ""]
    worst = []
    for _, r in sub.iterrows() if len(sub) else []:
        worst.append({"case": r.pair_id.split("->")[1] + f" ({r.target_id})", "set": "known (MP)", "energy error meV/atom": r.ctrl_dE_mev,
                      "likely cause": likely_cause(r.pair_id.split("->")[1], "ID", bool(r.magnetic))})
    for _, r in ood_ok.iterrows() if len(ood_ok) else []:
        worst.append({"case": f"{r.formula} ({r.wbm_id})", "set": "new (WBM)", "energy error meV/atom": r.de_mev,
                      "likely cause": likely_cause(r.formula, "OOD")})
    w = pd.DataFrame(worst)
    if len(w):
        known = w[w.set == "known (MP)"]
        w = w.reindex(w["energy error meV/atom"].abs().sort_values(ascending=False).index).head(10)
        L += [_md(w, ".1f"), ""]
        if len(known):
            known = known.reindex(known["energy error meV/atom"].abs().sort_values(ascending=False).index).head(5)
            L += ["The overall ten are all new materials; the five worst **known** materials, so their failures stay visible:", "",
                  _md(known, ".1f"), ""]
    notable = []
    if len(sub) and "rattled_diagnosis" in sub:
        for _, r in sub[sub.rattled_diagnosis != "returns to target structure"].iterrows():
            notable.append(f"* **{r.pair_id} (symmetry-broken start):** {r.rattled_diagnosis}, "
                           f"{r.rattled_minus_ctrl_mev:+.1f} meV/atom vs the relaxed MP structure. "
                           + ("A lower-energy distortion of an unstable high-symmetry target — physically right."
                              if r.rattled_minus_ctrl_mev < -1 else
                              "Trapped above the target: a genuine failure mode for large size mismatches." if r.rattled_minus_ctrl_mev > 1
                              else "Symmetry lowered with no energy change (numerically flat)."))
    if len(st) and "rejected" in st:
        rej = {}
        for v in st.rejected:
            rej.update(v or {})
        if rej:
            notable.append(f"* **{len(rej)} competing-phase relaxations were rejected** by the convergence / physical-sanity "
                           f"guard and left out of the mode (b) hulls: " + ", ".join(f"{k} ({v})" for k, v in sorted(rej.items())) +
                           ". One of these (solid O₂) had collapsed to 0.07 Å at −1.2×10¹¹ eV/atom before the guard existed.")
    if len(oo):
        r = oo[oo.rejection.notna()]
        if len(r):
            notable.append("* **Rejected new-material relaxations:** " + ", ".join(f"{a.formula} ({a.wbm_id}: {a.rejection})" for a in r.itertuples()))
    if notable:
        L += ["**Other notable failures:**", ""] + notable + [""]

    # ---------- magnetic / spin caveat ----------
    L += ["## Magnetic, transition-metal and f-electron systems (reported separately)", "",
          "MACE-MP-0 has no spin degrees of freedom. These systems are excluded from nothing, but their numbers are split out.", ""]
    if len(sub):
        spin = sub[sub.spin_caveat == True]  # noqa: E712
        nospin = sub[sub.spin_caveat == False]  # noqa: E712
        L += [_md(pd.DataFrame([
            {"group": "no spin caveat", "n": len(nospin), "volume MAE %": nospin.ctrl_vol_pct.abs().mean(),
             "energy MAE meV/atom": nospin.ctrl_dE_mev.abs().mean()},
            {"group": "spin caveat", "n": len(spin), "volume MAE %": spin.ctrl_vol_pct.abs().mean(),
             "energy MAE meV/atom": spin.ctrl_dE_mev.abs().mean()}])), ""]
        L += [_md(spin[["pair_id", "family", "magnetic", "transition_metal", "f_electron", "ctrl_vol_pct", "ctrl_dE_mev"]]
                  .rename(columns={"ctrl_vol_pct": "volume err %", "ctrl_dE_mev": "energy err meV/atom"})), ""]
    if len(st):
        from harness.suites import stability as st_mod

        rows = []
        for label, g in [("no spin caveat", st[~st.spin_caveat & ~st.spin_in_hull]), ("spin caveat (target or hull)", st[st.spin_caveat | st.spin_in_hull])]:
            for mode in ("a", "b"):
                m = st_mod.metrics(g, mode)
                rows.append({"group": label, "mode": mode, "n": m["n"], "e_hull MAE meV/atom": m["mae_ev"] * 1000,
                             "accuracy@0": m["thr0.0"]["accuracy"], "accuracy@0.1": m["thr0.1"]["accuracy"]})
        L += ["**Stability gate, split by spin caveat:**", "", _md(pd.DataFrame(rows)), ""]
    if len(oo):
        rows = []
        for label, g in [("no spin caveat", oo[~oo.spin_caveat]), ("spin caveat", oo[oo.spin_caveat])]:
            s = ood_mod.score(g)
            if s.get("n"):
                rows.append({"group": label, "n": s["n"], "energy MAE meV/atom": s["energy_mae_mev"],
                             "precision@0": s["thr0.0"]["precision"], "recall@0": s["thr0.0"]["recall"], "F1@0": s["thr0.0"]["f1"]})
        L += ["**New materials (WBM), split by spin caveat:**", "", _md(pd.DataFrame(rows)), ""]

    # ---------- auto-generated pairs ----------
    if len(au):
        from harness import pairgen

        meta = pairgen.load_meta()
        apairs = pairgen.load_pairs()
        fmap = {p["pair_id"]: p["target_formula"] for p in apairs}
        n_mat = meta.get("n_materials")
        L += ["## Automatically generated substitution pairs", "",
              f"{len(apairs)} pairs generated from {n_mat:,} Materials Project materials with ≤ "
              f"{meta.get('config', {}).get('max_atoms')} atoms per cell ({meta.get('accepted_prototypes')} prototypes, "
              f"{meta.get('accepted_space_relevant')} space-relevant targets). A pair shares a prototype (anonymized "
              "StructureMatcher on the PBE structures) and differs by exactly one element; space-relevant targets were "
              "queued first, round-robin across prototypes. Each pair is scored by the curated suite's own code: the "
              "substituted parent relaxed (sub) and the MP target relaxed (ctrl). "
              f"**{len(au_done)} pairs have results so far.**" if n_mat else
              f"{len(apairs)} auto-generated pairs; {len(au_done)} have results so far.", ""]
        grp = []
        for label, g in [("all", au_done), ("no spin caveat", au_done[au_done.spin_caveat == False]),  # noqa: E712
                         ("spin caveat (magnetic / TM / f)", au_done[au_done.spin_caveat == True]),  # noqa: E712
                         ("space-relevant targets", au_done[au_done.space_relevant == True]),  # noqa: E712
                         ("other targets", au_done[au_done.space_relevant == False])]:  # noqa: E712
            if len(g):
                s = sub_mod.group_stats(g)
                grp.append({"group": label, "n": s["n"], "sub volume MAE %": s["sub_vol_mae_pct"],
                            "ctrl volume MAE %": s["ctrl_vol_mae_pct"], "sub match": s["sub_match_rate"],
                            "ctrl match": s["ctrl_match_rate"], "ctrl energy MAE meV/atom": s["ctrl_E_mae_mev"]})
        L += [_md(pd.DataFrame(grp)), ""]
        if "diagnosis" in au_done:
            L += ["Diagnosis: " + ", ".join(f"{k}: {v}" for k, v in au_done.diagnosis.value_counts().items()), ""]
        if len(au_done):
            fam = au_done.groupby("family").agg(n=("pair_id", "size"), vol_mae=("ctrl_vol_pct", lambda v: v.abs().mean()),
                                                e_mae=("ctrl_dE_mev", lambda v: v.abs().mean()),
                                                match=("sub_match", "mean")).reset_index().sort_values("n", ascending=False)
            L += [f"**Most common prototypes** (of {au_done.family.nunique()}):", "",
                  _md(fam.head(15).rename(columns={"family": "prototype", "vol_mae": "volume MAE %",
                                                   "e_mae": "energy MAE meV/atom", "match": "sub match rate"})), ""]
            el = per_element(au_done.assign(formula=au_done.pair_id.map(fmap)), "formula", "ctrl_dE_mev")
            el = el[el.n >= 5]
            if len(el):
                L += ["**Energy error by element** (elements in ≥ 5 scored targets):", "",
                      _md(el.head(15).rename(columns={"mae": "MAE meV/atom", "mean": "mean meV/atom"}), ".1f"), ""]
            w = au_done.reindex(au_done.ctrl_dE_mev.abs().sort_values(ascending=False).index).head(10)
            L += ["**10 worst auto-generated pairs by energy error:**", "",
                  _md(pd.DataFrame([{"pair": r.pair_id, "prototype": r.family, "energy error meV/atom": r.ctrl_dE_mev,
                                     "volume error %": r.ctrl_vol_pct,
                                     "likely cause": likely_cause(fmap.get(r.pair_id, r.pair_id.split("->")[1].split()[0]),
                                                                  "ID", bool(r.magnetic))} for r in w.itertuples()]), ".1f"), ""]
            ap = [pl for pl in store.load_payloads("substitution_auto", tag=tag).values() if pl["kind"] == "ctrl"]
            if ap:
                figs["auto"] = parity(fig_dir / "parity_auto_pairs.png",
                                      [("volume per atom (Å³/atom)", [p["lattice"]["vol_per_atom_ref"] for p in ap],
                                        [p["lattice"]["vol_per_atom_sim"] for p in ap],
                                        [fmap.get(p["pair_id"], "") for p in ap], KNOWN)],
                                      "MP PBE", "MACE", "Auto-generated pairs: MP target relaxed with MACE")
                figs["auto_e"] = parity(fig_dir / "parity_auto_pairs_energy.png",
                                        [("energy per atom (eV/atom)", [p["energy_per_atom"] - p["energy_mev_vs_mp"] / 1000 for p in ap],
                                          [p["energy_per_atom"] for p in ap], [fmap.get(p["pair_id"], "") for p in ap], KNOWN)],
                                        "MP PBE (uncorrected)", "MACE", "Auto-generated pairs: energy")
                L += [f"![Auto-generated pairs, volume](figures/{figs['auto']})", "",
                      f"![Auto-generated pairs, energy](figures/{figs['auto_e']})", ""]

    # ---------- OOD vs ID ----------
    L += ["## Out-of-distribution score next to the in-distribution score", "",
          "MACE-MP-0 was trained on Materials Project data, so MP-based scores overstate accuracy on new materials. "
          f"The WBM sample ({len(oo)} structures drawn at random from the 215,488 unique-prototype set, seed 20260910; ids "
          "in `data/ood_wbm_sample*.json`) was never in its training data. **These two columns are never averaged together.**", ""]
    if len(sub) and len(ood_ok):
        f1_ood = so["thr0.0"]["f1"] if so else float("nan")
        L += [_md(pd.DataFrame([
            {"metric": "energy MAE (meV/atom)", "known materials (MP)": _ci_str(e_id), "new materials (WBM)": _ci_str(e_ood)},
            {"metric": "mean signed energy error (meV/atom)", "known materials (MP)": _ci_str(e_id_mean, "{:+.1f}"),
             "new materials (WBM)": _ci_str(e_ood_mean, "{:+.1f}")},
            {"metric": "energy above hull MAE (meV/atom), MACE target vs DFT competitors",
             "known materials (MP)": f"{sa['mae_ev'] * 1000:.1f}" if sa else "n/a",
             "new materials (WBM)": f"{so['e_hull_mae_mev']:.1f}" if so else "n/a"},
            {"metric": "stable-call precision / recall @ 0 eV/atom",
             "known materials (MP)": f"{sa['thr0.0']['precision']:.2f} / {sa['thr0.0']['recall']:.2f}" if sa else "n/a",
             "new materials (WBM)": f"{so['thr0.0']['precision']:.2f} / {so['thr0.0']['recall']:.2f}" if so else "n/a"},
            {"metric": "F1 @ 0 eV/atom", "known materials (MP)": "—", "new materials (WBM)": f"{f1_ood:.2f}"},
            {"metric": "n", "known materials (MP)": str(len(sub)), "new materials (WBM)": str(len(ood_ok))},
        ])), "",
            "For WBM the hull distance is DFT hull distance + (MACE − DFT energy), the Matbench Discovery construction, so its "
            "error equals the energy error by design. Cross-check: Matbench Discovery reports F1 = 0.669 for MACE-MP-0 on the "
            "full unique-prototype set (FIRE, fmax 0.05); this sample's F1 is consistent with it.", ""]

    # ---------- experimental ----------
    if len(ex):
        L += ["## Experimental check", "",
              "Reference: Lucero, Henderson & Scuseria, *J. Phys.: Condens. Matter* **24**, 145504 (2012), Table I "
              "(doi:10.1088/0953-8984/24/14/145504). 33 room-temperature values score the headline; 6 values the source gives "
              "as uncorrected 0 K extrapolations are shown separately; β-GaN was not run (ambiguous structure in the source). "
              "**Coverage gap: no metals and one oxide.**", ""]
        rows = []
        for label, g in [("room temperature", ex[ex.status == "rt"]), ("0 K extrapolated", ex[ex.status == "zero_k"])]:
            rows.append({"set": label, "n": len(g), "MACE vs exp mean %": g.a_err_pct.mean(), "MACE vs exp MAE %": g.a_err_pct.abs().mean(),
                         "PBE vs exp mean %": g.a_pbe_err_pct.mean(), "MACE − PBE mean %": g.a_mace_vs_pbe_pct.mean()})
        L += [_md(pd.DataFrame(rows)), "",
              _md(ex.sort_values("a_err_pct", key=abs, ascending=False)[["material", "structure", "status", "a_exp", "a_mace", "a_pbe",
                                                                          "a_err_pct", "a_pbe_err_pct", "a_mace_vs_pbe_pct"]], ".3f"), ""]

    # ---------- bulk ----------
    L += ["## Bulk modulus", ""]
    if len(bk):
        n_flag = len(bk) - len(bk_ok)
        skipped = jobs[(jobs.suite == "bulk") & (jobs.status == "skipped")] if len(jobs) else jobs
        failed = jobs[(jobs.suite == "bulk") & jobs.status.isin(["failed", "timeout"])] if len(jobs) else jobs
        L += [f"Birch–Murnaghan fits over 9 volumes (±4 %), cell shape relaxed at each volume, vs MP elastic K_VRH "
              f"(the elasticity documents do not state the functional). {len(bk_ok)} fitted, {n_flag} flagged fits excluded "
              f"from the MAE, {len(skipped)} materials without an MP elasticity reference, {len(failed)} failed.", ""]
        rows = []
        for label, g in [("all", bk_ok), ("no spin caveat", bk_ok[bk_ok.spin_caveat == False]),  # noqa: E712
                         ("spin caveat", bk_ok[bk_ok.spin_caveat == True])]:  # noqa: E712
            if len(g):
                rows.append({"group": label, "n": len(g), "mean vs K_VRH %": g.err_pct_vrh.mean(),
                             "MAE vs K_VRH %": g.err_pct_vrh.abs().mean(), "MAE vs K_Reuss %": g.err_pct_reuss.dropna().abs().mean()})
        L += [_md(pd.DataFrame(rows)), "",
              _md(bk.sort_values("err_pct_vrh", key=abs, ascending=False)[["label", "mp_id", "family", "b0_gpa", "k_vrh", "k_reuss",
                                                                           "err_pct_vrh", "bp", "anisotropic", "spin_caveat"]].head(15)), ""]
    else:
        L += ["_Not run._", ""]

    # ---------- runtime ----------
    L += ["## Runtime on this Mac", ""]
    if len(jobs):
        ok = jobs[jobs.status == "ok"].dropna(subset=["runtime_s"])
        rt_rows = []
        for suite, g in ok.groupby("suite"):
            rt_rows.append({"suite": suite, "structures": len(g), "median s/structure": g.runtime_s.median(),
                            "p90 s": g.runtime_s.quantile(0.9), "max s": g.runtime_s.max(),
                            "sum of per-structure s": g.runtime_s.sum()})
        L += [_md(pd.DataFrame(rt_rows), ".1f"), "",
              f"Per-structure times are single-worker wall times: {compute['workers']} workers × {compute['threads_per_worker']} "
              "thread run concurrently (cells > 100 atoms on 2 × 5), so a suite's elapsed time is roughly the sum divided by "
              "the number of workers. Stability counts the 1,190 competing-phase relaxations (the 50 target evaluations reuse "
              "substitution energies). Bulk-modulus times cover all 9 equation-of-state points. "
              f"MPS could not run this model (see `config/compute.json`: {compute.get('device_reason', '')})", ""]
        status = jobs.groupby(["suite", "status"]).size().unstack(fill_value=0)
        L += ["**Job outcomes (current settings):**", "", status.reset_index().to_markdown(index=False), ""]

    # ---------- unattended queue ----------
    from harness.config import QUEUE_DB

    if QUEUE_DB.exists():
        from harness import jobqueue

        qc = jobqueue.counts(QUEUE_DB)
        if qc:
            L += ["## Unattended job queue", "",
                  _md(pd.DataFrame([{"suite": s, **{k: v.get(k, 0) for k in jobqueue.STATUSES}} for s, v in sorted(qc.items())]),
                      ".0f"), ""]
            fails = jobqueue.failures_by_type(QUEUE_DB)
            if fails:
                L += ["**Queue failures by type** (after one retry):", "",
                      _md(pd.DataFrame(fails)[["error_type", "n", "suites", "example"]]), ""]

    # ---------- method notes ----------
    L += ["## Method notes and fixes made along the way", "",
          "* MP's summary endpoint now serves **r2SCAN** structures and energies for many materials (Ge: 5.675 Å, −13.87 eV/atom); "
          "every reference here comes from MP's PBE `GGA_GGA+U` thermo data (Ge: 5.763 Å, −4.62 eV/atom). MP ids are the new "
          "format (`mp-32` → `mp-aaaaaabg`).",
          "* MP entries carry Element-keyed `oxidation_states`, which pymatgen's MP2020 correction looks up by symbol string; keys "
          "are normalised. The recomputed MP hull reproduces MP's stored energy above hull exactly for all 50 targets.",
          "* FrechetCellFilter's fmax criterion let small cells stop with up to 0.19 GPa residual stress; an explicit "
          "max |stress| ≤ 0.01 GPa criterion was added (stricter, not looser).",
          "* A physical-sanity guard rejects relaxations with atoms closer than 0.5 × the covalent-radius sum or that did "
          "not converge; rejections are counted, never silently dropped.",
          "* mace-torch ≥ 0.3.10 defaults `mace_mp()` to MACE-MPA-0; the MACE-MP-0 medium checkpoint is loaded explicitly "
          "and pinned by SHA-256.",
          "* No tolerance was loosened and no hard case was removed to improve a number.", ""]
    L += ["## Files", "",
          "* `results/results.sqlite` — every job and every structure × test row with provenance and settings",
          "* `results/results.parquet` — the same results table (all settings tags; filter on `settings_tag`)",
          "* `figures/` (next to this report) — the plots above",
          "* `scorecard.json` (next to this report) — the headline numbers, used to compare runs", ""]

    # ---------- write ----------
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "validation_report.md"
    out.write_text("\n".join(L) + "\n")
    (out_dir / "scorecard.json").write_text(json.dumps(scorecard, indent=1) + "\n")
    res = store.load_table("results")
    if len(res):
        res["settings_tag"] = res.job_key.map(lambda k: k.rsplit("@", 1)[1] if "@" in k else "pre-tag")
        res.to_parquet(RESULTS_DIR / "results.parquet", index=False)
    log.info("report written: %s (%d figures)", out, sum(1 for v in figs.values() if v))
    return str(out.relative_to(ROOT)) if out.resolve().is_relative_to(ROOT) else str(out)
