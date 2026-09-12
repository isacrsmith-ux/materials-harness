"""Bulk modulus: Birch–Murnaghan equation of state from MACE vs MP elastic K_VRH.

Materials: the MACE-relaxed control structures of the substitution targets plus the MACE-relaxed
experimental-check solids, deduplicated by MP id, wherever MP has a successful elasticity document.
Each EOS uses 9 volumes from 0.96 to 1.04 x V0 (±4 %), relaxing cell shape and positions at constant
volume at every point; a fit needs >= 7 converged, physical points.

Comparison notes (stated in the report):
  * MP's K_VRH comes from finite-difference elastic constants; the elasticity document does not
    state the functional. K_VRH is the Voigt–Reuss–Hill average; an EOS with relaxed cell shape
    corresponds to the Reuss bound, so K_Reuss is recorded too (identical for cubic crystals).
  * Only MP materials with elasticity data are computed; the rest are counted as "no reference".
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from harness import compare, mp_data, store
from harness.config import settings_tag
from harness.engine import EV_PER_A3_TO_GPA
from harness.jobs import eos_job
from harness.runner import run_pool

log = logging.getLogger(__name__)

SUITE = "bulk"
VOLUME_FACTORS = tuple(float(x) for x in np.linspace(0.96, 1.04, 9))
MIN_POINTS = 7
MAX_FIT_RMS_MEV = 1.0  # meV/atom; worse fits are flagged, not hidden

# Sanity bound on the MP REFERENCE, not on our result. No crystalline solid has a bulk modulus above
# diamond's (~443 GPa), so a K_VRH far above that is a broken elasticity document, not a hard case:
# MP gives potassium K_VRH = 33,306 GPa next to K_Reuss = 3.7 GPa for the same material. A reference
# like that measures MP's Voigt average, not the engine. Such rows are NAMED and reported both ways,
# never silently dropped.
MAX_PLAUSIBLE_K_GPA = 600.0


def reference_implausible(k_vrh) -> bool:
    return not (k_vrh is not None and np.isfinite(k_vrh) and 0.0 < k_vrh <= MAX_PLAUSIBLE_K_GPA)


def fit_birch_murnaghan(volumes, energies) -> dict:
    """Third-order Birch–Murnaghan fit of per-atom E(V). Returns B0 in GPa and fit diagnostics."""
    from ase.eos import EquationOfState

    v, e = np.asarray(volumes, float), np.asarray(energies, float)
    eos = EquationOfState(v, e, eos="birchmurnaghan")
    v0, e0, b = eos.fit()
    params = np.asarray(eos.eos_parameters, float)
    fitted = eos.func(v, *params)
    return {"v0": float(v0), "e0": float(e0), "b0_gpa": float(b * EV_PER_A3_TO_GPA), "bp": float(params[2]),
            "rms_mev": float(np.sqrt(np.mean((e - fitted) ** 2)) * 1000),
            "v0_in_range": bool(v.min() <= v0 <= v.max())}


def materials(tag: str) -> list[dict]:
    from harness.curation import resolve_pairs

    pairs = {p["pair_id"]: p for p in resolve_pairs()}
    out = {}
    for pl in store.load_payloads("substitution", tag=tag).values():
        if pl.get("kind") != "ctrl" or compare.rejection_reason(pl):
            continue
        p = pairs[pl["pair_id"]]
        out.setdefault(p["target_id"], {"mp_id": p["target_id"], "label": p["target_formula"], "family": p["family"],
                                         "source": "substitution target", "structure": pl["relaxed"],
                                         "flags": p["flags"], "space_relevant": p["space_relevant"]})
    for pl in store.load_payloads("experimental", tag=tag).values():
        mid = pl.get("pbe_material_id")
        if not mid or "relaxed" not in pl or mid in out or compare.rejection_reason(pl):
            continue
        s = pl["relaxed"]
        out[mid] = {"mp_id": mid, "label": pl["material"], "family": f"exp-{pl['structure']}",
                    "source": "experimental solid", "structure": s,
                    "flags": compare.system_flags(s.composition.elements), "space_relevant": False}
    return list(out.values())


def _record(job: dict, res: dict) -> None:
    m, el, key = job["material"], job["elastic"], job["job_key"]
    if res.get("status") != "ok":
        store.record_job(SUITE, key, res["status"], payload={"mp_id": m["mp_id"]}, error=res.get("error"),
                         runtime_s=res.get("job_wall_s"))
        log.warning("%s %s: %s", m["label"], res["status"], res.get("error"))
        return
    pts = res["points"]
    # Same rejection rule as every other suite (no DFT reference per EOS point, so the absolute
    # energy window applies and the energy-vs-reference half does not).
    for p in pts:
        if "error" not in p:
            p["rejection"] = compare.rejection_reason(p)
    good = [p for p in pts if "error" not in p and not p["rejection"]]
    runtime = sum(p.get("wall_time_s", 0.0) for p in pts)
    if len(good) < MIN_POINTS:
        err = f"only {len(good)}/{len(pts)} usable EOS points (need {MIN_POINTS})"
        store.record_job(SUITE, key, "failed", payload={"mp_id": m["mp_id"], "points": pts}, error=err, runtime_s=runtime)
        log.warning("%s: %s", m["label"], err)
        return
    fit = fit_birch_murnaghan([p["volume_per_atom"] for p in good], [p["energy_per_atom"] for p in good])
    k = el["bulk_modulus"]
    k_vrh, k_reuss, k_voigt = k.get("vrh"), k.get("reuss"), k.get("voigt")
    anisotropic = bool(k_voigt and k_reuss and abs(k_voigt - k_reuss) / k_reuss > 0.01)
    flags = {**m["flags"], "n_points": len(good), "fit_rms_mev": fit["rms_mev"], "bp": fit["bp"],
             "v0_in_range": fit["v0_in_range"], "fit_ok": fit["rms_mev"] <= MAX_FIT_RMS_MEV and fit["v0_in_range"],
             "anisotropic": anisotropic, "mp_warnings": el.get("warnings")}
    src = (f"{m['mp_id']} MP elasticity ({el.get('fitting_method')}, order {el.get('order')}, "
           f"db {el.get('database_version')}; functional not stated in the doc)")
    base = {"suite": SUITE, "job_key": key, "structure": f"{m['label']} ({m['mp_id']})", "formula": m["label"],
            "family": m["family"], "units": "GPa", "reference_provenance": "mp_computed", "flags": flags,
            "settings": res["metadata"], "runtime_s": runtime}
    rows = [{**base, "test": "B0_eos_vs_K_VRH", "simulated_value": fit["b0_gpa"], "reference_value": k_vrh,
             "reference_source": src + " K_VRH", "error_abs": fit["b0_gpa"] - k_vrh,
             "error_pct": compare.pct_error(fit["b0_gpa"], k_vrh)}]
    if k_reuss:
        rows.append({**base, "test": "B0_eos_vs_K_Reuss", "simulated_value": fit["b0_gpa"], "reference_value": k_reuss,
                     "reference_source": src + " K_Reuss", "error_abs": fit["b0_gpa"] - k_reuss,
                     "error_pct": compare.pct_error(fit["b0_gpa"], k_reuss)})
    store.record_results(rows)
    payload = {"mp_id": m["mp_id"], "label": m["label"], "family": m["family"], "source": m["source"],
               "space_relevant": m["space_relevant"], "spin_caveat": m["flags"].get("spin_caveat"),
               "b0_gpa": fit["b0_gpa"], "bp": fit["bp"], "k_vrh": k_vrh, "k_reuss": k_reuss, "k_voigt": k_voigt,
               "err_pct_vrh": compare.pct_error(fit["b0_gpa"], k_vrh),
               "err_pct_reuss": compare.pct_error(fit["b0_gpa"], k_reuss) if k_reuss else None,
               "anisotropic": anisotropic, "fit": fit, "n_points": len(good), "points": pts, "wall_time_s": runtime}
    store.record_job(SUITE, key, "ok", payload=payload, settings=res["metadata"], runtime_s=runtime)
    log.info("%-10s %-12s B0 %6.1f GPa  K_VRH %6.1f  err %+6.1f%%  B' %.2f  rms %.2f meV  %d pts  %.0fs",
             m["label"], m["mp_id"], fit["b0_gpa"], k_vrh, payload["err_pct_vrh"], fit["bp"], fit["rms_mev"],
             len(good), runtime)


def run(compute: dict, retry_failed: bool = False, limit: int | None = None) -> None:
    tag = settings_tag(compute["device"], compute["dtype"])
    mats = materials(tag)[: limit or None]
    done = store.completed_keys(SUITE, retry_failed=retry_failed)
    jobs, no_ref = [], []
    for m in mats:
        key = f"{m['mp_id']}@{tag}"
        if key in done:
            continue
        el = mp_data.elasticity(m["mp_id"])
        k = (el or {}).get("bulk_modulus") or {}
        if not el or el.get("state") != "successful" or not k.get("vrh"):
            no_ref.append(m["label"])
            store.record_job(SUITE, key, "skipped", payload={"mp_id": m["mp_id"], "label": m["label"]},
                             error="no successful MP elasticity document with K_VRH")
            continue
        jobs.append({"job_key": key, "material": m, "elastic": el, "structure": m["structure"],
                     "volume_factors": VOLUME_FACTORS, "device": compute["device"], "dtype": compute["dtype"]})
    log.info("bulk: %d materials, %d with MP K_VRH to compute, %d without reference: %s",
             len(mats), len(jobs), len(no_ref), no_ref)
    jobs.sort(key=lambda j: -len(j["structure"]))
    run_pool(eos_job, jobs, compute["workers"], compute["threads_per_worker"], on_result=_record)
    print_summary(tag)


def table(tag: str) -> pd.DataFrame:
    return pd.DataFrame([pl for pl in store.load_payloads(SUITE, tag=tag).values() if "b0_gpa" in pl])


def print_summary(tag: str) -> None:
    df = table(tag)
    if df.empty:
        print("No bulk-modulus results yet.")
        return
    ok = df[df.fit.map(lambda f: f["rms_mev"] <= MAX_FIT_RMS_MEV and f["v0_in_range"])]
    print(f"\n=== BULK MODULUS (settings {tag}) — n={len(df)} fitted, {len(df) - len(ok)} flagged fits ===")
    for label, sub in [("ALL", ok), ("no spin caveat", ok[ok.spin_caveat == False]),  # noqa: E712
                       ("spin caveat", ok[ok.spin_caveat == True]), ("space-relevant", ok[ok.space_relevant == True])]:  # noqa: E712
        if len(sub):
            print(f"{label:<16} n={len(sub):>2}  vs K_VRH: mean {sub.err_pct_vrh.mean():+.1f}%  MAE {sub.err_pct_vrh.abs().mean():.1f}%"
                  f"  |  vs K_Reuss: MAE {sub.err_pct_reuss.dropna().abs().mean():.1f}%")
    cols = ["label", "mp_id", "family", "b0_gpa", "k_vrh", "k_reuss", "err_pct_vrh", "err_pct_reuss", "bp",
            "anisotropic", "spin_caveat", "n_points"]
    print(df.sort_values("err_pct_vrh", key=abs, ascending=False)[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}"))
