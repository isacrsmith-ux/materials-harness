"""Phase 3 of the 2026-09-24 campaign: lock the OQMD held-out half, pilot, frozen plan, development
runs and the DEVELOPMENT / CALIBRATION TIER report. Called through scripts/oqmd_campaign.py.

Nothing here opens the held-out half. `lock` writes it, hashes it and commits it BEFORE any ML job is
queued; every later step reads only development ids and asserts they are disjoint from it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oqmd_campaign import OQMD_DIR, BINS, DOWNLOAD_RECORD, _lock, now  # noqa: E402

SEED = 20260924
FAMILIES = ("f-electron", "intermetallic", "oxide", "halide", "chalcogenide", "pnictide", "other")
# Frozen allocation (campaign brief, Phase 3.3): weight the families that cannot say 'likely stable';
# f-electron and pnictide get a smaller descriptive share as a cross-convention check of the live rules.
WEIGHTS = {"intermetallic": 0.25, "oxide": 0.20, "halide": 0.15, "chalcogenide": 0.15, "other": 0.15,
           "f-electron": 0.05, "pnictide": 0.05}
FLUORIDE_SHARE_OF_HALIDE = 0.6       # oversample fluorides inside halide, as far as the pool allows
PILOT_N = 500
BUDGET_H = 35.0                      # both engines together, the middle of the brief's 30-40 h
PLAN_JSON = ROOT / "data" / "oqmd_dev_plan.json"
PLAN_MD = ROOT / "reports" / "oqmd_dev_plan.md"
PILOT_JSON = ROOT / "data" / "oqmd_pilot_ids.json"
N_FAMILY_SIDE = 12                   # 5 non-stable-labelling families + fluoride, both sides


def _git_commit(paths: list[str], msg: str) -> str:
    subprocess.run(["git", "add", "--", *paths], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet", "--", *paths], cwd=ROOT).returncode == 0:
        return "nothing to commit"
    msg += "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
    r = subprocess.run(["git", "commit", "-q", "-m", msg, "--", *paths], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"git commit failed: {(r.stdout + r.stderr)[-1500:]}")
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()


def _is_fluoride(formula: str) -> bool:
    from pymatgen.core import Composition

    return "F" in {e.symbol for e in Composition(formula).elements}


# --- lock -----------------------------------------------------------------------------------------

def lock() -> None:
    """Stratified family x bin split of the INDEPENDENT pool; half locked, half development."""
    import pandas as pd

    from harness import external_oqmd as X, felectron_eval, pnictide_eval, round4
    from harness.suites import ood

    lk = _lock("lock")  # noqa: F841
    if X.SPLIT_FILE.is_file():
        # 'exists' is not 'committed': a blocked commit must not be skipped on the retry
        sha = _git_commit(["data/oqmd_split.json", "data/locked_sets_registry.json"],
                          "Lock the OQMD external held-out half (retry of a blocked commit)")
        print(f"ok: {X.SPLIT_FILE.name} exists (locked {X.load_split()['created_at']}; commit: {sha})")
        return
    df = pd.read_parquet(OQMD_DIR / "overlap.parquet")
    pool = df[df.independent & df.family.notna() & df.bin.notna()]
    # formula guard against every existing protected (locked or opened held-out) set
    protected = round4._locked_test_ids() | pnictide_eval.excluded_ids() | felectron_eval.excluded_ids()
    summary = ood.load_summary().set_index("material_id")
    from pymatgen.core import Composition

    pf = {Composition(summary.loc[w].formula).reduced_formula for w in protected if w in summary.index}
    clash = set(pool.formula) & pf
    if clash:
        raise SystemExit(f"ABORT - {len(clash)} pool formulas are protected-set formulas, e.g. {sorted(clash)[:5]}")
    rng = random.Random(SEED)
    held, dev, strata = [], [], {}
    for (fam, b), g in sorted(pool.groupby(["family", "bin"])):
        ids = sorted(int(i) for i in g.entry_id)
        rng.shuffle(ids)
        h = len(ids) // 2
        held += ids[:h]
        dev += ids[h:]
        strata[f"{fam}|{b}"] = {"pool": len(ids), "heldout": h, "development": len(ids) - h}
    assert not set(held) & set(dev)
    out = {"created_at": now(),
           "state": "LOCKED, UNOPENED. Nothing in the 2026-09-24 campaign opens the held-out half.",
           "source": {"dump": "OQMD v1.8", "sha256": json.loads(DOWNLOAD_RECORD.read_text())["sha256"]},
           "pool": "usable OQMD entries (converged, ordered, <= 40 atoms, labelled) whose reduced formula is in "
                   "neither the MP 2023-01-10 snapshot (MPtrj superset) nor WBM",
           "stratification": "family (confidence.family, unchanged) x OQMD stability bin; per stratum a seeded "
                             "shuffle, floor(n/2) held out",
           "seed": SEED, "formula_guard": {"protected_formulas_checked": len(pf), "clashes": 0},
           "strata": strata,
           "heldout": {"n": len(held), "sha256": X._sha(held), "ids": sorted(held)},
           "development": {"n": len(dev), "sha256": X._sha(dev), "ids": sorted(dev)}}
    X.SPLIT_FILE.write_text(json.dumps(out, indent=1) + "\n")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "freeze_spec_v2.py")], cwd=ROOT,
                       capture_output=True, text=True)
    print(r.stdout[-1500:])
    if r.returncode or "OQMD external held-out" not in r.stdout:
        raise SystemExit("registry regeneration did not register the OQMD half")
    sha = _git_commit(["data/oqmd_split.json", "data/locked_sets_registry.json"],
                      f"Lock the OQMD external held-out half before any ML job: {len(held):,} ids, NOT opened\n\n"
                      f"Stratified family x stability-bin split of the independent OQMD v1.8 pool; held-out sha256 "
                      f"{out['heldout']['sha256'][:16]}..., development {len(dev):,} ids. Registered in "
                      "data/locked_sets_registry.json; external_oqmd.heldout_ids() raises without unlock=True. "
                      "No OQMD evaluation is pre-registered.")
    print(f"ok: locked {len(held):,} held-out ids, {len(dev):,} development ids (commit {sha})")


# --- pilot, plan ----------------------------------------------------------------------------------

def _dev_frame():
    import pandas as pd

    from harness import external_oqmd as X

    dev = set(X.development_ids())
    assert not dev & X.excluded_heldout_ids(), "development ids overlap the locked half"
    df = pd.read_parquet(OQMD_DIR / "overlap.parquet")
    d = df[df.entry_id.isin(dev)].copy()
    d["fluoride"] = d.formula.map(_is_fluoride)
    return d


def _allocate(d, n_total: int) -> dict:
    """Frozen weights, capped by availability, surplus redistributed over uncapped families."""
    avail = d.family.value_counts().to_dict()
    alloc = {f: 0 for f in WEIGHTS}
    left, active = n_total, dict(WEIGHTS)
    while left > 0 and active:
        tot = sum(active.values())
        give = {f: int(left * w / tot) for f, w in active.items()} or {}
        if not any(give.values()):
            give = {max(active, key=active.get): left}
        for f, g in give.items():
            g = min(g, avail.get(f, 0) - alloc[f])
            alloc[f] += g
            left -= g
        active = {f: w for f, w in active.items() if alloc[f] < avail.get(f, 0)}
    return alloc


def _draw(d, alloc: dict, rng: random.Random, must: set) -> list[int]:
    """Per family: fluorides first for halide (up to their share), then per-bin proportional."""
    out = []
    for fam, n in alloc.items():
        g = d[d.family == fam]
        keep = [i for i in g.entry_id if i in must]
        pools = [g]
        if fam == "halide":
            fl = g[g.fluoride]
            nf = min(len(fl), int(round(n * FLUORIDE_SHARE_OF_HALIDE)))
            pools = [(fl, nf), (g[~g.fluoride], n - nf)]
        else:
            pools = [(g, n)]
        for sub, k in pools:
            k -= sum(1 for i in keep if i in set(sub.entry_id))
            shares = sub.bin.value_counts(normalize=True)
            for b in BINS:
                cand = sorted(int(i) for i in sub[(sub.bin == b)].entry_id if i not in must)
                rng.shuffle(cand)
                out += cand[:max(0, int(round(k * shares.get(b, 0))))]
        out += keep
    return sorted(set(out))


def pilot_enqueue() -> None:
    from harness import config, jobqueue, store
    from harness import external_oqmd as X
    from harness.config import QUEUE_DB, load_compute_config

    if PILOT_JSON.is_file():
        ids = json.loads(PILOT_JSON.read_text())["ids"]
        _git_commit(["data/oqmd_pilot_ids.json"], "OQMD pilot ids (retry of a blocked commit)")
    else:
        d = _dev_frame()
        ids = _draw(d, _allocate(d, PILOT_N), random.Random(SEED + 1), set())
        PILOT_JSON.write_text(json.dumps({"created_at": now(), "n": len(ids), "sha256": X._sha(ids),
                                          "note": "pilot: 500 development ids by the frozen weights; they are part "
                                                  "of the development draw, not extra", "ids": ids}, indent=1) + "\n")
        _git_commit(["data/oqmd_pilot_ids.json"], f"OQMD pilot: {len(ids)} development ids (no held-out id)")
    _enqueue(ids)


def _enqueue(ids: list[int]) -> None:
    from harness import config, jobqueue, orchestrator as O, store
    from harness import external_oqmd as X
    from harness.config import QUEUE_DB, load_compute_config

    assert not set(ids) & X.excluded_heldout_ids(), "a held-out id reached the queue"
    compute = load_compute_config()
    tag, settings = O._settings(compute)
    settings = {**settings, "model": config.MODEL["file"]}
    jobs = X.build_jobs(ids, compute, tag, settings)
    done = store.completed_keys(X.SUITE, retry_failed=True)
    print(f"ok: enqueue {jobqueue.enqueue(jobs, QUEUE_DB, done_keys=done)} ({len(jobs)} jobs, tag {tag})")


def _runtimes(tag: str, keys: set | None = None):
    import numpy as np

    from harness import store

    with store.connect() as con:
        rows = con.execute("SELECT job_key, status, runtime_s FROM jobs WHERE suite='oqmd'").fetchall()
    r = [(k, s, t) for k, s, t in rows if k.endswith("@" + tag) and (keys is None or k in keys)]
    ok = np.array([t for _, s, t in r if s == "ok" and t is not None], float)
    return {"n": len(r), "ok": int(len(ok)), "failed": sum(1 for _, s, _ in r if s != "ok"),
            "median_s": float(np.median(ok)) if len(ok) else None, "mean_s": float(ok.mean()) if len(ok) else None,
            "p95_s": float(np.percentile(ok, 95)) if len(ok) else None}


def _engine_ratio() -> dict:
    """Second-engine / production-engine mean job time, measured on the Phase-1 f-electron jobs."""
    import numpy as np

    from harness import felectron_eval, store

    ids = set(felectron_eval.load()["test"]["ids"])
    with store.connect() as con:
        rows = con.execute("SELECT job_key, runtime_s FROM jobs WHERE suite='ood' AND status='ok'").fetchall()
    t = {"c2480e74": [], "207ccc81": []}
    for k, s in rows:
        wid, _, tag = k.partition("@")
        if wid.split(":")[0] in ids and tag in t and s is not None:
            t[tag].append(s)
    source = "Phase-1 f-electron held-out jobs (runtime only; no outcome is read)"
    if not t["c2480e74"] or not t["207ccc81"]:
        # Phase 3 must not depend on Phase 1: fall back to every WBM job both engines have run
        source = "all WBM 'ood' jobs run under both engines (Phase-1 runtimes unavailable)"
        for k, s in rows:
            tag = k.partition("@")[2]
            if tag in t and s is not None:
                t[tag].append(s)
    a, b = float(np.mean(t["c2480e74"])), float(np.mean(t["207ccc81"]))
    return {"production_mean_s": a, "second_mean_s": b, "ratio": b / a, "n": [len(t["c2480e74"]), len(t["207ccc81"])],
            "source": source}


def plan() -> None:
    """Size the draw from the pilot, freeze the ids and the arithmetic, and COMMIT before queueing."""
    from harness import external_oqmd as X
    from harness.config import load_compute_config, load_unattended_config
    from harness.orchestrator import layout

    if PLAN_JSON.is_file():
        sha = _git_commit(["data/oqmd_dev_plan.json", "reports/oqmd_dev_plan.md"],
                          "Freeze the OQMD development plan (retry of a blocked commit)")
        print(f"ok: plan frozen at {json.loads(PLAN_JSON.read_text())['created_at']} (commit: {sha})")
        return
    pilot = json.loads(PILOT_JSON.read_text())["ids"]
    rt = _runtimes("c2480e74", {X.job_key(i, "c2480e74") for i in pilot})
    if rt["ok"] < 0.9 * len(pilot):
        raise SystemExit(f"pilot incomplete: {rt}")
    ratio = _engine_ratio()
    workers, _ = layout("full", load_compute_config(), load_unattended_config())
    per_struct_prod_h = rt["mean_s"] / workers / 3600          # wall hours per structure, 1 engine
    per_struct_both_h = per_struct_prod_h * (1 + ratio["ratio"])
    n_budget = int(BUDGET_H / per_struct_both_h)
    d = _dev_frame()
    n = min(n_budget, len(d))
    alloc = _allocate(d, n)
    ids = _draw(d, alloc, random.Random(SEED + 2), set(pilot))
    fam = Counter(d.set_index("entry_id").loc[ids].family)
    nfl = int(d.set_index("entry_id").loc[ids].fluoride.sum())
    est_h = len(ids) * per_struct_both_h
    payload = {"created_at": now(), "tier": "DEVELOPMENT / CALIBRATION - licenses nothing",
               "pilot": {"n": len(pilot), **rt, "tag": "c2480e74"}, "engine_cost_ratio": ratio,
               "workers": workers, "budget_h_both_engines": BUDGET_H,
               "arithmetic": {"wall_h_per_structure_production": per_struct_prod_h,
                              "wall_h_per_structure_both": per_struct_both_h,
                              "n_from_budget": n_budget, "development_pool": len(d),
                              "n_chosen": len(ids), "estimated_wall_h_both": est_h,
                              "capped_by": "pool" if n_budget >= len(d) else "budget"},
               "weights": WEIGHTS, "fluoride_share_of_halide": FLUORIDE_SHARE_OF_HALIDE,
               "allocation": dict(fam), "fluorides": nfl, "seed": SEED + 2,
               "ids": {"n": len(ids), "sha256": X._sha(ids), "ids": ids}}
    PLAN_JSON.write_text(json.dumps(payload, indent=1) + "\n")
    PLAN_MD.write_text(_plan_md(payload))
    sha = _git_commit(["data/oqmd_dev_plan.json", "reports/oqmd_dev_plan.md"],
                      f"Freeze the OQMD development plan before the full draw is queued: {len(ids):,} ids\n\n"
                      "Sized from the 500-structure pilot and the measured engine cost ratio; weights, allocation "
                      "and ids fixed here. DEVELOPMENT tier; the held-out half is untouched.")
    print(f"ok: plan frozen, {len(ids):,} structures, est. {est_h:.1f} h both engines (commit {sha})")


def _plan_md(p: dict) -> str:
    a, r, pi = p["arithmetic"], p["engine_cost_ratio"], p["pilot"]
    L = ["# OQMD development plan — frozen before the full draw was queued", "",
         f"Frozen {p['created_at']}. **{p['tier']}.** The OQMD held-out half is locked "
         "(`data/oqmd_split.json`) and nothing here reads it.", "",
         "## Pilot (production engine, 500 development structures)", "",
         f"| jobs | ok | failed | median s | mean s | p95 s |", "|---:|---:|---:|---:|---:|---:|",
         f"| {pi['n']} | {pi['ok']} | {pi['failed']} | {pi['median_s']:.2f} | {pi['mean_s']:.2f} | {pi['p95_s']:.2f} |", "",
         "The **mean** is used for sizing: the median understates a relaxation-heavy queue (HANDOFF).", "",
         "## Arithmetic", "",
         f"* second / production engine mean job time = {r['second_mean_s']:.2f} / {r['production_mean_s']:.2f} "
         f"= **{r['ratio']:.3f}** ({r['source']}; n = {r['n'][0]:,} / {r['n'][1]:,})",
         f"* {p['workers']} workers: wall hours per structure = {pi['mean_s']:.2f} s / {p['workers']} / 3600 "
         f"= {a['wall_h_per_structure_production']:.3e} h (production), x (1 + {r['ratio']:.3f}) = "
         f"{a['wall_h_per_structure_both']:.3e} h (both engines)",
         f"* budget {p['budget_h_both_engines']} h / {a['wall_h_per_structure_both']:.3e} h = **{a['n_from_budget']:,}** structures",
         f"* development pool = {a['development_pool']:,}; chosen = **{a['n_chosen']:,}** (capped by {a['capped_by']}); "
         f"estimated {a['estimated_wall_h_both']:.1f} h of AC compute for both engines", "",
         "## Weights and allocation", "",
         "Weighted toward the families that cannot say *likely stable*; f-electron and pnictide at a small "
         "descriptive share, as a cross-convention check of the two live stable rules. Weights are capped by "
         "availability and the surplus redistributed over the uncapped families. Within halide, fluorides take "
         f"up to {p['fluoride_share_of_halide']:.0%} of the allocation (WBM cannot settle the fluoride question). "
         "Within a family, draws are proportional to the OQMD stability-bin mix of that family's development pool.", "",
         "| family | weight | drawn |", "|---|---:|---:|"]
    for f, w in p["weights"].items():
        L.append(f"| {f} | {w} | {p['allocation'].get(f, 0):,} |")
    L += ["", f"Fluorides in the draw: **{p['fluorides']:,}**.", "",
          f"Ids: n = {p['ids']['n']:,}, sha256 `{p['ids']['sha256']}` (in `data/oqmd_dev_plan.json`). The 500 pilot "
          "ids are included, not extra.", ""]
    return "\n".join(L)


def dev_enqueue() -> None:
    """Queue the CURRENT HARNESS_MODEL over the frozen development ids."""
    from harness import config
    from harness import external_oqmd as X

    p = json.loads(PLAN_JSON.read_text())
    ids = p["ids"]["ids"]
    if X._sha(ids) != p["ids"]["sha256"]:
        raise SystemExit("ABORT - the frozen development ids do not match their hash")
    _enqueue(ids)
    if config.ACTIVE_MODEL == "mace-mpa-0-medium" and not (OQMD_DIR / "prefetch.done").is_file():
        # network-bound MP hull prefetch, detached so it overlaps the runners and survives this process
        log = open(ROOT / "logs" / "oqmd_prefetch.log", "a")
        subprocess.Popen([sys.executable, str(ROOT / "scripts" / "oqmd_campaign.py"), "prefetch-hull"],
                         cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
        print("started the detached MP hull prefetch (logs/oqmd_prefetch.log)")


def prefetch_hull() -> None:
    """Warm the MP GGA/GGA+U entry cache for every development chemical system (network only)."""
    from pymatgen.core import Composition

    from harness import mp_data

    lk = _lock("prefetch")  # noqa: F841
    import pandas as pd

    p = json.loads(PLAN_JSON.read_text())
    df = pd.read_parquet(OQMD_DIR / "overlap.parquet", columns=["entry_id", "formula"])
    forms = df[df.entry_id.isin(set(p["ids"]["ids"]))].formula
    systems = sorted({"-".join(sorted(e.symbol for e in Composition(f).elements)) for f in forms})
    failed = {}
    for i, cs in enumerate(systems, 1):
        try:
            mp_data.entries_in_chemsys(cs)
        except Exception as exc:  # noqa: BLE001 - recorded; the report counts these rows as 'no MP hull'
            failed[cs] = f"{type(exc).__name__}: {exc}"[:200]
        if i % 200 == 0:
            print(f"[{now()}] prefetched {i:,}/{len(systems):,} chemical systems ({len(failed)} failed)", flush=True)
    (OQMD_DIR / "prefetch.done").write_text(json.dumps({"at": now(), "systems": len(systems), "failed": failed}))
    print(f"ok: {len(systems):,} chemical systems prefetched, {len(failed)} failed")


# --- the development report -----------------------------------------------------------------------

MP_INDEX = ROOT / "cache" / "external" / "mp" / "gga_ggau_pd_index.pkl"
MP_INDEX_META = ROOT / "cache" / "external" / "mp" / "gga_ggau_pd_index.json"


def _correct_chunk(dicts: list) -> list:
    """MP2020-process raw MP entry dicts exactly as hull.process does; keep (id, elements, composition,
    corrected energy). MP2020 corrections are per entry, so chunking cannot change them."""
    from pymatgen.entries.computed_entries import ComputedStructureEntry

    from harness import hull, mp_data

    ents = []
    for d in dicts:
        e = ComputedStructureEntry.from_dict(d)
        e.data = mp_data.str_keys(e.data)
        ents.append(e)
    out = []
    for e in hull.process(ents):
        out.append((hull.material_id(e), tuple(sorted(el.symbol for el in e.composition.elements)),
                    e.composition.as_dict(), float(e.energy)))
    return out


def mp_bulk() -> None:
    """Every MP GGA/GGA+U thermo document's entries, once, MP2020-corrected, indexed by element set.
    This is what mp_data.entries_in_chemsys fetches one system at a time (get_entries_in_chemsys with
    thermo_types=[GGA_GGA+U] = every entry of every thermo doc whose chemsys is a subsystem); it is
    VALIDATED against that path on cached systems before the report may use it."""
    import pickle
    from concurrent.futures import ProcessPoolExecutor

    from harness import hull, mp_data

    lk = _lock("mp_bulk")  # noqa: F841
    if MP_INDEX_META.is_file() and json.loads(MP_INDEX_META.read_text()).get("validated"):
        print("ok: MP bulk index exists and is validated")
        return
    raw = ROOT / "cache" / "external" / "mp" / "thermo_GGA_GGA+U_entries.pkl"
    if raw.is_file():
        dicts, version = pickle.loads(raw.read_bytes())
    else:
        with mp_data._rester() as mpr:
            version = mpr.get_database_version()
            docs = mpr.materials.thermo.search(thermo_types=["GGA_GGA+U"], fields=["material_id", "entries"])
        dicts = [e for doc in docs for e in doc.model_dump()["entries"].values()]
        raw.write_bytes(pickle.dumps((dicts, version), protocol=5))
        print(f"[{now()}] fetched {len(docs):,} thermo docs, {len(dicts):,} entries (MP {version})", flush=True)
    chunks = [dicts[i:i + 2000] for i in range(0, len(dicts), 2000)]
    index: dict = {}
    with ProcessPoolExecutor(max_workers=4) as ex:        # gentle: a runner is usually busy
        for out in ex.map(_correct_chunk, chunks):
            for mid, els, comp, energy in out:
                index.setdefault(els, []).append((mid, comp, energy))
    # validation against the per-system product path, on systems already in the on-disk cache
    cached = _cached_systems()
    pick = cached[:40] + random.Random(SEED).sample(cached[40:], min(20, max(0, len(cached) - 40)))
    checked, bad = 0, []
    for cs in pick:
        want = sorted((hull.material_id(e), round(float(e.energy), 6)) for e in hull.mp_competitors(cs))
        got = sorted((mid, round(en, 6)) for mid, _, en in _competitors(index, cs))
        checked += 1
        if want != got:
            bad.append(cs)
    meta = {"mp_database_version": version, "built_at": now(), "entries": sum(len(v) for v in index.values()),
            "element_sets": len(index), "validated_on_systems": checked, "mismatches": bad,
            "validated": checked >= 20 and not bad}
    MP_INDEX.write_bytes(pickle.dumps(index, protocol=5))
    MP_INDEX_META.write_text(json.dumps(meta, indent=1) + "\n")
    if not meta["validated"]:
        raise SystemExit(f"MP bulk index does NOT reproduce the product path: {meta}")
    print(f"ok: MP bulk index validated on {checked} systems, {meta['entries']:,} entries")


def _cached_systems() -> list[str]:
    """Chemical systems already fetched one-by-one through mp_data (the prefetch), largest first."""
    import re

    systems = set()
    for f in (ROOT / "cache" / "mp" / "entries_chemsys").glob("*.json"):
        with open(f) as fh:
            m = re.search(r'"chemsys": "([^"]+)"', fh.read(400))
        if m:
            systems.add(m.group(1))
    return sorted(systems, key=lambda s: (-s.count("-"), s))


def _competitors(index: dict, chemsys: str) -> list:
    from itertools import combinations

    els = sorted(chemsys.split("-"))
    out = []
    for k in range(1, len(els) + 1):
        for sub in combinations(els, k):
            out += index.get(sub, [])
    return out


def _place_group(args):
    """Mode (a) for every result of one (chemsys, formula) group: MP GGA/GGA+U hull, MP2020, the group's
    own reduced formula removed from MP (the material is scored as new). One PhaseDiagram per group.
    `comp` is the list of (mp id, composition, MP2020-corrected energy) from the validated bulk index."""
    chemsys, formula, rows, comp = args
    from pymatgen.analysis.phase_diagram import PDEntry, PhaseDiagram
    from pymatgen.core import Composition

    from harness import hull

    comp = [PDEntry(Composition(c), en, name=mid) for mid, c, en in comp]
    corners = {e.composition.elements[0].symbol for e in comp if len(e.composition.elements) == 1}
    if set(chemsys.split("-")) - corners:
        return [(k, None, "no MP hull: IncompleteHullError") for k, _, _ in rows]
    keep = [e for e in comp if e.composition.reduced_formula != formula]
    try:
        pd_ = PhaseDiagram(keep)
    except Exception as exc:  # noqa: BLE001
        return [(k, None, f"phase diagram failed: {type(exc).__name__}") for k, _, _ in rows]
    out = []
    for key, structure, e in rows:
        try:
            ent = hull.process([hull.product_entry(structure, e, formula)])
            if not ent:
                out.append((key, None, "MP2020 rejected the entry"))
                continue
            _, s = pd_.get_decomp_and_e_above_hull(ent[0], allow_negative=True)
            out.append((key, float(s), None))
        except Exception as exc:  # noqa: BLE001
            out.append((key, None, f"placement failed: {type(exc).__name__}"))
    return out


def _predictions(tag: str, ids: set):
    """entry_id -> (pred, structure_changed, reason) for one engine; reason None when usable."""
    from concurrent.futures import ProcessPoolExecutor

    from pymatgen.core import Composition

    from harness import external_oqmd as X, store

    pls = store.load_payloads(X.SUITE, tag=tag)
    groups, res = {}, {}
    for k, pl in pls.items():
        eid = pl["entry_id"]
        if eid not in ids:
            continue
        if pl.get("rejection"):
            res[eid] = (None, pl.get("structure_changed"), f"guard: {pl['rejection']}")
            continue
        cs = "-".join(sorted(e.symbol for e in Composition(pl["formula"]).elements))
        groups.setdefault((cs, pl["formula"]), []).append((eid, pl["relaxed"], pl["e_engine"]))
        res[eid] = (None, pl.get("structure_changed"), "pending")
    import pickle

    index = pickle.loads(MP_INDEX.read_bytes())
    work = [(cs, f, rows, _competitors(index, cs)) for (cs, f), rows in groups.items()]
    with ProcessPoolExecutor(max_workers=12) as ex:
        for out in ex.map(_place_group, work, chunksize=16):
            for eid, pred, why in out:
                res[eid] = (pred, res[eid][1], why)
    return res


def _consistency(d, matched) -> list[str]:
    """Per development row: are the stage-2 materials in its chemical (sub)systems on the same side of
    the hull in OQMD and MP? 'consistent' / 'inconsistent' / 'not assessable'."""
    from itertools import combinations

    from pymatgen.core import Composition

    by_cs = {}
    for r in matched.itertuples():
        cs = tuple(sorted(e.symbol for e in Composition(r.formula).elements))
        bad = abs(r.stability - r.mp) > 0.025 or ((r.stability <= 0) != (r.mp <= 0))
        by_cs[cs] = by_cs.get(cs, False) or bad
    out = []
    for f in d.formula:
        els = sorted(e.symbol for e in Composition(f).elements)
        seen = [by_cs[c] for k in range(1, len(els) + 1) for c in combinations(els, k) if c in by_cs]
        out.append("not assessable" if not seen else ("inconsistent" if any(seen) else "consistent"))
    return out


def _side(sub, stable_t, unstable_t):
    from harness import confidence as C
    from harness import metrics as M

    tol = M.ON_HULL_TOL
    r = {}
    if stable_t is not None:
        sel = sub.each_pred <= stable_t + tol
        n, k = int(sel.sum()), int(sub.stable[sel].sum())
        r["stable"] = {"t": stable_t, "calls": n, "correct": k, "precision": k / n if n else None,
                       "cp95": C.cp_lower(k, n, 0.95) if n else None, "call_rate": n / len(sub) if len(sub) else None}
    if unstable_t is not None:
        sel = sub.each_pred > unstable_t + tol
        if stable_t is not None:
            sel &= ~(sub.each_pred <= stable_t + tol)
        n, k = int(sel.sum()), int((~sub.stable[sel]).sum())
        r["unstable"] = {"t": unstable_t, "calls": n, "correct": k, "npv": k / n if n else None,
                         "cp95": C.cp_lower(k, n, 0.95) if n else None, "call_rate": n / len(sub) if len(sub) else None}
    return r


def dev_report() -> None:
    import pandas as pd

    from harness import calibration as CAL, confidence as C, metrics as M, routing as R
    from harness import external_oqmd as X

    if not (MP_INDEX_META.is_file() and json.loads(MP_INDEX_META.read_text()).get("validated")):
        mp_bulk()
    p = json.loads(PLAN_JSON.read_text())
    ids = set(p["ids"]["ids"])
    assert not ids & X.excluded_heldout_ids()
    a, b = _predictions("c2480e74", ids), _predictions("207ccc81", ids)
    ov = pd.read_parquet(OQMD_DIR / "overlap.parquet").set_index("entry_id").loc[sorted(ids)]
    d = pd.DataFrame({"entry_id": sorted(ids)})
    d["formula"] = ov.formula.values
    d["family"] = ov.family.values
    d["each_true"] = ov.stability.values
    d["bin_true"] = ov.bin.values
    d["fluoride"] = d.formula.map(_is_fluoride)
    d["each_pred"] = d.entry_id.map(lambda i: a.get(i, (None,))[0])
    d["structure_changed"] = d.entry_id.map(lambda i: a.get(i, (None, None))[1])
    d["why_unusable"] = d.entry_id.map(lambda i: a.get(i, (None, None, "no production result"))[2])
    d["pred_2"] = d.entry_id.map(lambda i: b.get(i, (None,))[0])
    d["stable"] = d.each_true <= M.ON_HULL_TOL
    matched = pd.read_parquet(OQMD_DIR / "stage2_matched.parquet")
    d["hull_consistency"] = _consistency(d, matched)
    usable = d[d.each_pred.notna()].copy()
    usable["each_pred"] = usable.each_pred.astype(float)
    usable["pred_2"] = pd.to_numeric(usable.pred_2)

    bundle = CAL.load()
    live = {}
    for path, second in (("A", False), ("B", True)):
        pol = bundle.policy(with_second_engine=second, max_trustworthy_hull=None)
        th = bundle.rule(second).thresholds
        L = usable[R.labelable(usable, pol)]
        live[path] = {"labelable": len(L), "families": {}}
        for fam in FAMILIES:
            g = L[L.family == fam]
            t = th.get(fam) or {}
            live[path]["families"][fam] = {
                "n": len(g), "base_rate": float(g.stable.mean()) if len(g) else None,
                "rule": {"stable": t.get("stable"), "unstable": t.get("unstable")},
                "all": _side(g, t.get("stable"), t.get("unstable")),
                "by_hull_consistency": {c: {"n": int((g.hull_consistency == c).sum()),
                                            **_side(g[g.hull_consistency == c], t.get("stable"), t.get("unstable"))}
                                        for c in ("consistent", "inconsistent", "not assessable")}}
    # does a threshold LOOK certifiable (development tier, grid x family-side corrected)?
    conf = 1 - 0.05 / N_FAMILY_SIDE
    level = 1 - 0.05 / (len(C.DEC_GRID) * N_FAMILY_SIDE)
    sizing = _sizer()
    looks = {}
    polA = bundle.policy(with_second_engine=False, max_trustworthy_hull=None)
    LA = usable[R.labelable(usable, polA)]
    heldout_n = Counter()
    split = X.load_split()
    for key, v in split["strata"].items():
        heldout_n[key.split("|")[0]] += v["heldout"]
    groups = {f: LA[LA.family == f] for f in ("intermetallic", "oxide", "halide", "chalcogenide", "other")}
    groups["fluoride (any family)"] = LA[LA.fluoride]
    for name, g in groups.items():
        rec = {"n": len(g)}
        for side, target in (("stable", C.TARGET_PRECISION), ("unstable", C.TARGET_NPV)):
            t = C.certify(g.each_pred, g.stable, target, side, conf) if len(g) else None
            r = {"threshold": t}
            if t is not None:
                s = _side(g, t if side == "stable" else None, t if side == "unstable" else None)[side]
                k, n = s["correct"], s["calls"]
                p_hat, lo = k / n, C.cp_lower(k, n, level)
                r |= {"calls": n, "point": p_hat, "cp_lower_corrected": lo, "call_rate": n / len(g)}
                for label, truth in (("at_dev_point", p_hat), ("at_dev_lower_bound", lo)):
                    need = sizing(truth, target, 0.9875, 0.80)
                    r[f"heldout_structures_for_80pct_power_{label}"] = (
                        None if need is None else int(need / (n / len(g)) + 0.999))
            rec[side] = r
        looks[name] = rec
    payload ={"generated_at": now(), "tier": "DEVELOPMENT / CALIBRATION TIER (licenses nothing)",
               "plan_sha256": p["ids"]["sha256"], "n_planned": len(ids),
               "usable": len(usable), "unusable_reasons": d[d.each_pred.isna()].why_unusable.fillna("none")
               .str.split(":").str[0].value_counts().to_dict(),
               "missing_second_engine": int(usable.pred_2.isna().sum()),
               "hull_consistency_counts": d.hull_consistency.value_counts().to_dict(),
               "live_rules": live, "looks_certifiable": looks,
               "looks_certifiable_levels": {"certify_conf": conf, "bound_level": level,
                                            "family_side_selections": N_FAMILY_SIDE, "grid": len(C.DEC_GRID)},
               "heldout_available_by_family": dict(heldout_n),
               "fluorides": {"in_development_draw": int(d.fluoride.sum()), "usable": int(usable.fluoride.sum()),
                             "labelable_A": int(LA.fluoride.sum())}}
    (ROOT / "reports" / "oqmd_development.json").write_text(json.dumps(payload, indent=1, default=str) + "\n")
    (ROOT / "reports" / "oqmd_development.md").write_text(_dev_md(payload))
    sha = _git_commit(["reports/oqmd_development.md", "reports/oqmd_development.json"],
                      "Evidence (DEVELOPMENT tier, licenses nothing): OQMD development report\n\n"
                      "Live production rules (bundle unchanged) against OQMD labels per family x path, split by "
                      "stage-2 hull consistency; development-tier certifiability and held-out sizing; fluorides.")
    print(f"ok: development report written (commit {sha})")


def _sizer():
    spec = importlib.util.spec_from_file_location("intermetallic_sizing", ROOT / "scripts" / "intermetallic_sizing.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.calls_needed


def _fmt(x, nd=4):
    return "—" if x is None else f"{x:.{nd}f}"


def _dev_md(p: dict) -> str:
    L = ["# OQMD development results", "",
         f"> **{p['tier']}.** Every number here is scored on the rows it describes. Nothing in this report is a "
         "held-out result, and nothing here changes `data/calibration_bundle.json`. The OQMD held-out half is locked "
         "and unopened.", "",
         f"Generated {p['generated_at']} over the frozen plan (sha256 `{p['plan_sha256'][:16]}…`, "
         f"{p['n_planned']:,} structures). Usable with a production-engine prediction on MP's hull: "
         f"**{p['usable']:,}**; missing a second-engine prediction: {p['missing_second_engine']:,}. "
         "Unusable, by reason: " + ", ".join(f"{k} {v:,}" for k, v in p["unusable_reasons"].items()) + ".", "",
         "**How to read this.** The prediction is the product's own: the engine's relaxed energy placed on the "
         "Materials Project GGA/GGA+U hull with MP2020 corrections (mode (a)), the material's own formula removed "
         "from MP. The label is OQMD's hull distance on OQMD's hull. Where those two hulls disagree about the "
         "competing phases, a 'wrong' call is a convention difference, not a model error — which is why every "
         "table is split by stage-2 hull consistency (`reports/oqmd_hull_disagreement.md`). Counts: "
         + ", ".join(f"{k} {v:,}" for k, v in p["hull_consistency_counts"].items()) + ".", ""]
    for path in ("A", "B"):
        lv = p["live_rules"][path]
        L += [f"## Live production rules, Path {path} ({'no' if path == 'A' else 'with'} second engine) — labelable {lv['labelable']:,}", "",
              "| family | n | OQMD stable share | rule (stable / unstable) | stable calls | precision | CP95 (descriptive) | unstable calls | NPV | CP95 (descriptive) |",
              "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
        for fam, x in lv["families"].items():
            s, u = x["all"].get("stable", {}), x["all"].get("unstable", {})
            rule = "/".join("none" if v is None else f"{v * 1000:+.0f}" for v in (x["rule"]["stable"], x["rule"]["unstable"]))
            L.append(f"| {fam} | {x['n']:,} | {_fmt(x['base_rate'], 3)} | {rule} | {s.get('calls', '—')} | "
                     f"{_fmt(s.get('precision'))} | {_fmt(s.get('cp95'))} | {u.get('calls', '—')} | "
                     f"{_fmt(u.get('npv'))} | {_fmt(u.get('cp95'))} |")
        L += ["", f"### Path {path}, split by hull consistency (precision / NPV; calls in brackets)", "",
              "| family | consistent | inconsistent | not assessable |", "|---|---|---|---|"]
        for fam, x in lv["families"].items():
            cells = []
            for c in ("consistent", "inconsistent", "not assessable"):
                y = x["by_hull_consistency"][c]
                parts = []
                if "stable" in y:
                    parts.append(f"S {_fmt(y['stable']['precision'], 3)} ({y['stable']['calls']})")
                if "unstable" in y:
                    parts.append(f"U {_fmt(y['unstable']['npv'], 3)} ({y['unstable']['calls']})")
                cells.append(f"n={y['n']:,}: " + ("; ".join(parts) or "no rule"))
            L.append(f"| {fam} | " + " | ".join(cells) + " |")
        L.append("")
    lv = p["looks_certifiable_levels"]
    L += ["## Does a threshold *look* certifiable? (development tier, Path A)", "",
          f"`certify` over the {lv['grid']}-point grid with a {lv['family_side_selections']}-fold family x side correction "
          f"(bound level {lv['bound_level']:.6f}). A threshold found here was **selected on these rows**; it is a "
          "hypothesis for a pre-registration, not a result. Held-out sizing uses 0.9875 (four hypotheses) and 80% "
          "power, at the development point estimate and, pessimistically, at the development lower bound.", "",
          "| group | n | side | threshold | calls | point | corrected bound | held-out n (80%, at point) | held-out n (80%, at bound) |",
          "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for name, rec in p["looks_certifiable"].items():
        for side in ("stable", "unstable"):
            r = rec.get(side, {})
            t = r.get("threshold")
            L.append(f"| {name} | {rec['n']:,} | {side} | {'none' if t is None else f'{t * 1000:+.0f} meV'} | "
                     f"{r.get('calls', '—')} | {_fmt(r.get('point'))} | {_fmt(r.get('cp_lower_corrected'))} | "
                     f"{r.get('heldout_structures_for_80pct_power_at_dev_point', '—')} | "
                     f"{r.get('heldout_structures_for_80pct_power_at_dev_lower_bound', '—')} |")
    L += ["", "Held-out OQMD entries available per family (locked half): "
          + ", ".join(f"{k} {v:,}" for k, v in p["heldout_available_by_family"].items()) + ".", "",
          "## Fluorides", "",
          f"Fluorides in the development draw: {p['fluorides']['in_development_draw']:,}; usable "
          f"{p['fluorides']['usable']:,}; labelable on Path A {p['fluorides']['labelable_A']:,}. The 'fluoride (any "
          "family)' row above answers whether OQMD gives enough independent fluorides to size the study that "
          "`reports/fluoride_followup_power.md` says WBM cannot: compare its held-out n with the independent "
          "fluoride count in `reports/oqmd_overlap.md`, half of which is locked.", "",
          "## What this does not do", "",
          "It does not certify anything, change any threshold, or open the held-out half. Every bound is "
          "descriptive. A future OQMD held-out test would need its own pre-registration, fixed thresholds and "
          "the hull-consistency caveat built in.", ""]
    return "\n".join(L)
