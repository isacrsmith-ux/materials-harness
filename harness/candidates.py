"""Phase 3 candidate table: published scores, compliance, license, Apple Silicon support and the measured
CPU vs MPS speed / precision (config/benchmark-<model>.json) for every registry model."""

from __future__ import annotations

import json

import pandas as pd

from harness.config import CONFIG_DIR, DATA_DIR, MODELS, REPORTS_DIR, ROOT

OUT = REPORTS_DIR / "phase3" / "candidates.md"


def _bench(key: str) -> dict | None:
    p = CONFIG_DIR / f"benchmark-{key}.json"
    return json.loads(p.read_text()) if p.is_file() else None


def _settings_text(b: dict | None) -> str:
    if not b:
        return "not benchmarked"
    parts = []
    for lab, s in (b["device_benchmark"].get("settings") or {}).items():
        if s["failures"]:
            parts.append(f"{lab}: cannot run ({(s['first_error'] or '')[:60]})")
        else:
            parts.append(f"{lab}: {s['mean_relax_speedup']:.2f}× vs reference, {'agrees' if s['all_agree'] else 'DISAGREES'}")
    ref = b["device_benchmark"]["per_structure"]
    n = len(ref)
    return f"{n} structures; " + "; ".join(parts)


def _ref_speed(b: dict | None) -> str:
    if not b:
        return "—"
    ps = b["device_benchmark"]["per_structure"]
    ref_key = next(k for k in next(iter(ps.values())) if k.startswith("cpu_"))
    walls = [v[ref_key]["relax_wall_s"] for v in ps.values() if v.get(ref_key, {}).get("relax_wall_s")]
    best = (b.get("pool_benchmark") or {}).get("best") or {}
    return (f"{sum(walls) / len(walls):.1f} s/relaxation ({ref_key.replace('_', '/')}, 1 worker × {b['device_benchmark']['threads']} threads); "
            f"pool {best.get('s_per_structure', float('nan')):.2f} s/structure on {best.get('workers')}×{best.get('threads_per_worker')}")


def table() -> pd.DataFrame:
    from harness.config import compute_config_path

    pub = json.loads((DATA_DIR / "mbd_published.json").read_text())
    rows = []
    for key, m in MODELS.items():
        p, b = pub.get(key, {}), _bench(key)
        cp = compute_config_path(key)
        in_use = json.loads(cp.read_text()) if cp.is_file() else None
        rows.append({"model": m["name"], "F1": p.get("F1"), "DAF": p.get("DAF"), "precision": p.get("precision"),
                     "MAE meV/atom": (p.get("MAE_eV") or float("nan")) * 1000, "κ_SRME": p.get("kappa_SRME"),
                     "compliant (no WBM in training)": m["compliant"], "license": m["license"],
                     "runs on this Mac": "yes" if b else ("gated: needs Hugging Face login" if m.get("gated") else "not yet"),
                     "setting in use": f"{in_use['device']}/{in_use['dtype']}" if in_use else "—",
                     "benchmark recommends": f"{b['device']}/{b['dtype']}" if b else "—",
                     "CPU vs MPS (agreement within tolerance)": _settings_text(b), "speed": _ref_speed(b)})
    return pd.DataFrame(rows)


def write() -> str:
    pub = json.loads((DATA_DIR / "mbd_published.json").read_text())
    ex = pd.DataFrame([{"model": k, "F1": v["F1"], "excluded because": v["reason"]} for k, v in pub["_excluded"].items()])
    L = ["# Phase 3 — candidate engines", "",
         f"Published scores: {pub['_source']}. Speed and precision: `python -m harness benchmark` on this Mac (5 rattled "
         "cells of 40–108 atoms; a faster setting is accepted only if it matches the reference within 1 meV/atom, 0.1 % "
         "volume, 0.005 Å and 0.005 eV/Å on every structure).", "",
         table().to_markdown(index=False, floatfmt=".3f"), "",
         "The baseline keeps CPU/float64 although CPU/float32 agrees and is faster: switching would change its settings tag "
         "and orphan every existing result. The other engines run their recommended setting; float32 agreeing with the "
         "reference within 1 meV/atom on every benchmark structure is what makes the cross-model comparison fair.", "",
         "**Not run:**", "", ex.to_markdown(index=False), ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n")
    return str(OUT.relative_to(ROOT))
