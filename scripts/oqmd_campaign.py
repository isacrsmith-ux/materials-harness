#!/usr/bin/env python
"""OQMD external validation, stages 1-2 and the development tier (campaign 2026-09-24).

    python scripts/oqmd_campaign.py download            # pinned v1.8 dump, resumable, size + md5 + sha256
    python scripts/oqmd_campaign.py normalise           # dump -> cache/external/oqmd/*.parquet (one pass)
    python scripts/oqmd_campaign.py protostructures     # parallel, checkpointed, pauses on battery
    python scripts/oqmd_campaign.py overlap             # stage 1  -> reports/oqmd_overlap.{md,json}
    python scripts/oqmd_campaign.py hull-disagreement   # stage 2  -> reports/oqmd_hull_disagreement.{md,json}
    python scripts/oqmd_campaign.py lock                # lock the held-out half BEFORE any ML job
    python scripts/oqmd_campaign.py pilot-enqueue       # 500 development structures, production engine
    python scripts/oqmd_campaign.py plan                # size the draw from the pilot; frozen + committed
    python scripts/oqmd_campaign.py dev-enqueue         # the current HARNESS_MODEL over the frozen dev ids
    python scripts/oqmd_campaign.py dev-report          # reports/oqmd_development.{md,json}

Every raw OQMD byte stays under cache/external/oqmd/ (gitignored). Only ids, hashes, provenance and
aggregates are committed. The OQMD held-out half is locked here and nothing in this campaign opens it.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OQMD_DIR = ROOT / "cache" / "external" / "oqmd"
DUMP_URL = "https://static.oqmd.org/static/downloads/qmdb__v1_8__022026.sql.gz"
DUMP = OQMD_DIR / "qmdb__v1_8__022026.sql.gz"
# read from the storage bucket's own response headers on 2026-09-24T19:40:05Z
DUMP_SIZE = 21034479961
DUMP_MD5_B64 = "qQUGz1mu2YaF/LID0z0+bQ=="
DOWNLOAD_RECORD = OQMD_DIR / "download.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lock(name: str):
    OQMD_DIR.mkdir(parents=True, exist_ok=True)
    fh = open(OQMD_DIR / f"{name}.lock", "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # the driver treats exit code 75 (EX_TEMPFAIL) as 'not finished, retry later'
        print(f"{name} is already running in another process")
        sys.exit(75)
    return fh


def download() -> None:
    lk = _lock("download")  # noqa: F841 - held for the life of the process
    if DOWNLOAD_RECORD.is_file():
        rec = json.loads(DOWNLOAD_RECORD.read_text())
        if DUMP.is_file() and DUMP.stat().st_size == DUMP_SIZE:
            print(f"ok: v1.8 dump present and verified at {rec['verified_at']}, sha256 {rec['sha256']}")
            return
    while not (DUMP.is_file() and DUMP.stat().st_size >= DUMP_SIZE):
        have = DUMP.stat().st_size if DUMP.is_file() else 0
        print(f"[{now()}] downloading from byte {have:,} of {DUMP_SIZE:,}", flush=True)
        r = subprocess.run(["curl", "-sS", "-L", "-C", "-", "--retry", "20", "--retry-delay", "30",
                            "--retry-all-errors", "--speed-time", "120", "--speed-limit", "10000",
                            "-o", str(DUMP), DUMP_URL])
        if r.returncode and DUMP.is_file() and DUMP.stat().st_size == have:
            raise SystemExit(f"curl exit {r.returncode} with no progress; retry later")
    if DUMP.stat().st_size != DUMP_SIZE:
        raise SystemExit(f"ABORT - size {DUMP.stat().st_size} != published {DUMP_SIZE}; delete and retry")
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(DUMP, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            md5.update(chunk)
            sha.update(chunk)
    got_md5 = base64.b64encode(md5.digest()).decode()
    if got_md5 != DUMP_MD5_B64:
        DUMP.rename(DUMP.with_suffix(".corrupt"))
        raise SystemExit(f"ABORT - md5 {got_md5} != published {DUMP_MD5_B64}; moved aside, will re-download")
    DOWNLOAD_RECORD.write_text(json.dumps({
        "source": "OQMD v1.8 bulk MySQL dump, https://oqmd.org/download/",
        "url": DUMP_URL, "version": "v1.8 (database updated February 2026)",
        "size_bytes": DUMP_SIZE, "md5_base64_published": DUMP_MD5_B64,
        "sha256": sha.hexdigest(), "verified_at": now(),
        "licence": "CC BY 4.0, as stated on oqmd.org (home, documentation and download pages) read 2026-09-24T19:39:41Z",
    }, indent=1) + "\n")
    print(f"ok: downloaded and verified, sha256 {sha.hexdigest()}")


def normalise() -> None:
    """Two streaming passes over the pinned dump, both checkpointed, then the normalised table."""
    import pickle

    from harness import external_oqmd as X

    lk = _lock("normalise")  # noqa: F841
    if not DOWNLOAD_RECORD.is_file():
        print("the dump is not downloaded and verified yet")
        sys.exit(75)
    if X.ENTRIES.is_file() and X.STRUCTS.is_file():
        print(f"ok: {X.ENTRIES.name} exists")
        return
    if X.PASS1.is_file():
        p1 = pickle.loads(X.PASS1.read_bytes())
    else:
        p1 = X.pass1(log=lambda m: print(f"[{now()}] pass1 {m}", flush=True))
        X.PASS1.write_bytes(pickle.dumps(p1, protocol=5))
    if X.PASS2.is_file():
        atoms = pickle.loads(X.PASS2.read_bytes())
    else:
        need = {p1["calc"][c][2] for c in X._representatives(p1["fes"], p1["calc"], p1["entries"]).values()
                if c in p1["calc"]}
        atoms = X.pass2(need, log=lambda m: print(f"[{now()}] pass2 {m}", flush=True))
        X.PASS2.write_bytes(pickle.dumps(atoms, protocol=5))
    df, counts = X.normalise(p1, atoms, log=lambda m: print(f"[{now()}] {m}", flush=True))
    (OQMD_DIR / "normalise_counts.json").write_text(json.dumps(counts, indent=1) + "\n")
    print(f"ok: {counts['usable']:,} usable entries of {counts['entries_with_a_standard_fit_label']:,} labelled")


MBD_COMMIT = "71633e8bdfdfd41d56d64b1d777e5686d9eda3ec"
PROTO_DIR = OQMD_DIR / "protostructures"
WBM_PROTO_DIR = OQMD_DIR / "protostructures_wbm_check"
WBM_CHECK_N = 2000
BINS = ("<0", "0–0.025", "0.025–0.1", "0.1–0.3", ">0.3")
THRESHOLDS = (-0.02, 0.0, 0.01, 0.03)


def _worker(src: Path, out: Path) -> None:
    r = subprocess.run([str(ROOT / "uvw"), "run", "--python", "3.14", "--no-project", "--with",
                        f"matbench-discovery @ git+https://github.com/janosh/matbench-discovery@{MBD_COMMIT}",
                        "python", str(ROOT / "scripts" / "oqmd_protostructure_worker.py"), str(src), str(out), "12"],
                       cwd=ROOT)
    if r.returncode == 75:
        sys.exit(75)
    if r.returncode:
        raise SystemExit(f"protostructure worker exit {r.returncode}")


def _labels(d: Path) -> dict:
    out = {}
    for f in sorted(d.glob("labels_*.json")):
        for r in json.loads(f.read_text()):
            out[r["id"]] = r["label"]
    return out


def protostructures() -> None:
    """Label every usable OQMD structure, plus a WBM sample whose published labels test for drift
    between the pinned labeller and the one Matbench Discovery used for WBM and MP."""
    import gzip
    import random

    from harness.suites import ood
    from harness import external_oqmd as X

    lk = _lock("protostructures")  # noqa: F841
    if (OQMD_DIR / "protostructures.json").is_file():
        print("ok: protostructures.json exists")
        return
    wbm_src = OQMD_DIR / "wbm_label_check.jsonl.gz"
    if not wbm_src.is_file():
        summary = ood.load_summary()
        ids = sorted(random.Random(20260924).sample(sorted(summary.material_id), WBM_CHECK_N))
        cses = ood.load_entries(ids, OQMD_DIR / "wbm_label_check_cse.json")
        with gzip.open(wbm_src, "wt") as fh:
            for i, wid in enumerate(ids):
                st = cses[wid].structure
                fh.write(json.dumps({"id": i, "wbm_id": wid, "lattice": st.lattice.matrix.tolist(),
                                     "species": [sp.symbol for sp in st.species], "frac": st.frac_coords.tolist()}) + "\n")
    _worker(wbm_src, WBM_PROTO_DIR)
    _worker(X.STRUCTS, PROTO_DIR)
    labels = _labels(PROTO_DIR)
    (OQMD_DIR / "protostructures.json").write_text(json.dumps({str(k): v for k, v in labels.items()}))
    print(f"ok: {sum(v is not None for v in labels.values()):,} of {len(labels):,} OQMD structures labelled")


def _reduced(formula: str) -> str | None:
    from pymatgen.core import Composition

    try:
        return Composition(formula).reduced_formula
    except Exception:  # noqa: BLE001
        return None


def _frame():
    """Usable OQMD entries with protostructure labels and overlap flags."""
    import gzip

    import pandas as pd

    from harness import compare, external_oqmd as X, unseen
    from harness.suites import ood

    df = pd.read_parquet(X.ENTRIES)
    df = df[df.usable].copy()
    labels = json.loads((OQMD_DIR / "protostructures.json").read_text())
    df["proto"] = df.entry_id.astype(str).map(labels)
    df["bin"] = [compare.hull_bin(e, below_zero_bin=True) for e in df.stability]
    mp = pd.read_csv(unseen.MP_SNAPSHOT)
    mp["reduced"] = [_reduced(f) for f in mp.formula]
    wbm = ood.load_summary()
    wbm["reduced"] = [_reduced(f) for f in wbm.formula]
    df["mp_formula"] = df.formula.isin(set(mp.reduced))
    df["wbm_formula"] = df.formula.isin(set(wbm.reduced))
    df["mp_proto"] = df.proto.notna() & df.proto.isin(set(mp.wyckoff_spglib.dropna()))
    df["wbm_proto"] = df.proto.notna() & df.proto.isin(set(wbm.protostructure_spglib.dropna()))
    anon = lambda s: s.split(":")[0] if isinstance(s, str) else None  # noqa: E731
    df["mp_prototype_anonymous"] = df.proto.map(anon).isin({anon(x) for x in mp.wyckoff_spglib.dropna()})
    df["independent"] = ~df.mp_formula & ~df.wbm_formula
    return df, mp, wbm


def _drift() -> dict:
    """Agreement of the pinned labeller with WBM's published labels on the same (relaxed) structures."""
    import gzip

    from harness.suites import ood

    got = _labels(WBM_PROTO_DIR)
    with gzip.open(OQMD_DIR / "wbm_label_check.jsonl.gz", "rt") as fh:
        idx = {r["id"]: r["wbm_id"] for r in map(json.loads, fh)}
    pub = ood.load_summary().set_index("material_id").protostructure_spglib
    pairs = [(got.get(i), pub.get(w)) for i, w in idx.items()]
    ok = [a == b for a, b in pairs if a and isinstance(b, str)]
    return {"n": len(pairs), "compared": len(ok), "agree": int(sum(ok)),
            "agreement": sum(ok) / len(ok) if ok else None}


def overlap() -> None:
    """Stage 1: how much of OQMD is independent of the engines' training data and of WBM."""
    df, mp, wbm = _frame()
    fams = ("f-electron", "intermetallic", "oxide", "halide", "chalcogenide", "pnictide", "other")
    counts = json.loads((OQMD_DIR / "normalise_counts.json").read_text())
    per = {}
    for f in fams + ("ALL",):
        d = df if f == "ALL" else df[df.family == f]
        per[f] = {"usable": len(d),
                  "removed_mp_formula": int(d.mp_formula.sum()),
                  "removed_wbm_formula_only": int((~d.mp_formula & d.wbm_formula).sum()),
                  "mp_protostructure_match": int(d.mp_proto.sum()),
                  "wbm_protostructure_match": int(d.wbm_proto.sum()),
                  "unlabelled": int(d.proto.isna().sum()),
                  "independent": int(d.independent.sum()),
                  "independent_with_mp_anonymous_prototype": int((d.independent & d.mp_prototype_anonymous).sum()),
                  "independent_by_bin": {b: int((d.independent & (d.bin == b)).sum()) for b in BINS}}
    fl = df[df.formula.str.contains("F") & df.formula.map(lambda x: "F" in _elements(x))]
    payload = {"generated_at": now(), "source": "OQMD v1.8 dump, sha256 " + json.loads(DOWNLOAD_RECORD.read_text())["sha256"],
               "mp_snapshot": {"file": "2023-01-10-mp-energies.csv.gz",
                               "sha256": hashlib.sha256((ROOT / "cache/external/mp/2023-01-10-mp-energies.csv.gz").read_bytes()).hexdigest(),
                               "n": len(mp)},
               "wbm_summary_n": len(wbm), "labeller": f"matbench-discovery@{MBD_COMMIT}",
               "label_drift_check_on_wbm": _drift(), "filters": counts, "per_family": per,
               "independent_fluorides": int(fl.independent.sum()),
               "independent_fluorides_by_bin": {b: int((fl.independent & (fl.bin == b)).sum()) for b in BINS}}
    df.drop(columns=["settings"]).to_parquet(OQMD_DIR / "overlap.parquet")
    (ROOT / "reports" / "oqmd_overlap.json").write_text(json.dumps(payload, indent=1) + "\n")
    (ROOT / "reports" / "oqmd_overlap.md").write_text(_overlap_md(payload))
    print(f"ok: independent pool {per['ALL']['independent']:,} of {per['ALL']['usable']:,} usable")


def _elements(formula: str) -> set:
    from pymatgen.core import Composition

    return {e.symbol for e in Composition(formula).elements}


def _overlap_md(p: dict) -> str:
    c, P, D = p["filters"], p["per_family"], p["label_drift_check_on_wbm"]
    L = ["# OQMD overlap — stage 1 of the external-validation design", "",
         f"Generated {p['generated_at']} from the pinned {p['source']}. Every number is computed from that dump; "
         "no row is redistributed (row-level flags stay in gitignored `cache/external/oqmd/`).", "",
         "**What 'independent' means here.** An OQMD entry is independent when its reduced formula appears "
         f"neither in the Matbench Discovery MP snapshot of 2023-01-10 (n={p['mp_snapshot']['n']:,}, sha256 "
         f"`{p['mp_snapshot']['sha256'][:16]}…`), a proven superset of MPtrj and so of both engines' MP training "
         f"data, nor in WBM (n={p['wbm_summary_n']:,}). A protostructure label includes the elements, so a "
         "protostructure match implies a formula match: the protostructure columns say how many overlaps are "
         "*the same material*, and they are what stage 2 compares. Alexandria (the primary engine's other "
         "training source) is not checked here and cannot be, without redistributing it; see the caveat below.", "",
         "## Filters", "", "| step | entries |", "|---|---:|"]
    for k, v in c.items():
        L.append(f"| {k.replace('_', ' ')} | {v:,} |")
    L += ["", "## Overlap and the independent pool, per family", "",
          "| family | usable | same formula in MP snapshot | same formula in WBM only | same protostructure as an MP material | same protostructure as a WBM entry | **independent** | independent, anonymous prototype seen in MP |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for f, d in P.items():
        L.append(f"| {f} | {d['usable']:,} | {d['removed_mp_formula']:,} | {d['removed_wbm_formula_only']:,} | "
                 f"{d['mp_protostructure_match']:,} | {d['wbm_protostructure_match']:,} | **{d['independent']:,}** | "
                 f"{d['independent_with_mp_anonymous_prototype']:,} |")
    L += ["", "### Independent pool by OQMD hull-distance bin (eV/atom)", "",
          "| family | " + " | ".join(BINS) + " |", "|---|" + "---:|" * len(BINS)]
    for f, d in P.items():
        L.append(f"| {f} | " + " | ".join(f"{d['independent_by_bin'][b]:,}" for b in BINS) + " |")
    L += ["", f"Independent **fluorides** (any compound containing F, any family): **{p['independent_fluorides']:,}**; by bin "
          + ", ".join(f"{b}: {n:,}" for b, n in p["independent_fluorides_by_bin"].items()) + ".", "",
          "## Labeller check", "",
          f"Protostructure labels come from `get_protostructure_label` at {p['labeller']} (Python 3.14, ephemeral env). "
          "The MP and WBM labels they are compared with were computed by Matbench Discovery with an earlier version "
          f"of the same function. On {D['compared']:,} WBM structures labelled both ways, the labels agree for "
          f"**{D['agree']:,}** ({(D['agreement'] or 0):.4f}). Disagreement makes protostructure matches *under*-count, "
          "never over-count; the formula-based independence filter does not depend on labels at all.", "",
          "## Caveats", "",
          "* Independence is from the engines' **MP** training data (via the MPtrj superset) and from WBM. The primary "
          "engine is also trained on sAlex (subsampled Alexandria). Alexandria is not used or downloaded, so an "
          "OQMD composition that also occurs in Alexandria is not detected here. That residual risk applies to the "
          "production engine only, not the second engine (MPtrj only).",
          "* OQMD's labels come from OQMD's own DFT protocol and hull. What that does to a label is measured in "
          "stage 2 (`reports/oqmd_hull_disagreement.md`), not assumed.", ""]
    return "\n".join(L)


def hull_disagreement() -> None:
    """Stage 2, no ML: on the same materials, OQMD's hull distance against MP's MP2020-corrected one."""
    import numpy as np
    import pandas as pd

    from harness import compare, mp_data

    df, mp, _ = _frame()
    cache = ROOT / "cache" / "external" / "mp" / "thermo_GGA_GGA+U.parquet"
    if not cache.is_file():
        with mp_data._rester() as mpr:
            version = mpr.get_database_version()
            docs = mpr.materials.thermo.search(thermo_types=["GGA_GGA+U"],
                                               fields=["material_id", "formula_pretty", "energy_above_hull",
                                                       "decomposition_enthalpy"])
        th = pd.DataFrame([{"material_id": str(d.material_id), "e_above_hull": d.energy_above_hull,
                            "decomp": d.decomposition_enthalpy} for d in docs])
        th.attrs["version"] = version
        th.to_parquet(cache)
        (cache.with_suffix(".json")).write_text(json.dumps({"database_version": version, "retrieved_at": now(),
                                                            "n": len(th)}) + "\n")
    th = pd.read_parquet(cache)
    meta = json.loads(cache.with_suffix(".json").read_text())
    mp = mp.merge(th, on="material_id", how="inner")
    key = mp.groupby(["reduced", "wyckoff_spglib"]).decomp.min()
    d = df[df.mp_proto].copy()
    d["mp"] = [key.get((f, pr), np.nan) for f, pr in zip(d.formula, d.proto)]
    d = d[d.mp.notna()]
    # one row per MATERIAL: OQMD often holds several entries of one (formula, protostructure) - ICSD
    # copies and prototype decorations - and only one of them is the hull vertex. Per-entry figures
    # are kept as a secondary line; the primary comparison is material against material.
    per_entry = {f"{t * 1000:+.0f} meV": float(((d.stability <= t) != (d.mp <= t)).mean()) for t in THRESHOLDS}
    n_entries = len(d)
    d = (d.sort_values("stability").groupby(["formula", "proto"], as_index=False)
         .agg(entry_id=("entry_id", "first"), family=("family", "first"), stability=("stability", "min"),
              mp=("mp", "first"), n_oqmd_entries=("entry_id", "size")))
    d["bin"] = [compare.hull_bin(e, below_zero_bin=True) for e in d.stability]
    d["mp_bin"] = [compare.hull_bin(e, below_zero_bin=True) for e in d.mp]
    t0 = (d.stability <= 0) != (d.mp <= 0)
    near_zero = {"disagreements_at_0meV": int(t0.sum()),
                 "of_which_both_within_5meV_of_zero": int((t0 & (d.stability.abs() <= 0.005) & (d.mp.abs() <= 0.005)).sum()),
                 "of_which_oqmd_within_5meV_of_zero": int((t0 & (d.stability.abs() <= 0.005)).sum())}
    fams = ("f-electron", "intermetallic", "oxide", "halide", "chalcogenide", "pnictide", "other")
    per = {}
    for f in fams + ("ALL",):
        x = d if f == "ALL" else d[d.family == f]
        if not len(x):
            per[f] = {"n": 0}
            continue
        diff = x.stability - x.mp
        per[f] = {"n": len(x), "mae_ev": float(diff.abs().mean()), "median_signed_ev": float(diff.median()),
                  "spearman": float(x.stability.rank().corr(x.mp.rank())) if len(x) > 2 else None,
                  "matrix": {a: {b: int(((x.bin == a) & (x.mp_bin == b)).sum()) for b in BINS} for a in BINS},
                  "side_disagreement": {f"{t * 1000:+.0f} meV": {
                      "oqmd_stable_mp_not": int(((x.stability <= t) & (x.mp > t)).sum()),
                      "mp_stable_oqmd_not": int(((x.mp <= t) & (x.stability > t)).sum()),
                      "rate": float(((x.stability <= t) != (x.mp <= t)).mean())} for t in THRESHOLDS}}
    payload = {"generated_at": now(), "mp_database_version": meta["database_version"],
               "mp_thermo_retrieved_at": meta["retrieved_at"], "mp_thermo_docs": meta["n"],
               "matched_materials": len(d), "matched_oqmd_entries": n_entries,
               "match_rule": "same reduced formula AND same protostructure label; one row per material: the lowest "
               "OQMD stability and the lowest MP decomposition enthalpy on that key",
               "per_entry_side_disagreement_all": per_entry, "near_zero_sensitivity": near_zero,
               "oqmd_quantity": "formation_energies.stability, 'standard' fit (signed; negative = below the hull of the other phases)",
               "mp_quantity": "thermo GGA_GGA+U decomposition_enthalpy (signed; MP2020-corrected)",
               "per_family": per}
    d[["entry_id", "formula", "proto", "family", "stability", "mp", "n_oqmd_entries"]].to_parquet(OQMD_DIR / "stage2_matched.parquet")
    (ROOT / "reports" / "oqmd_hull_disagreement.json").write_text(json.dumps(payload, indent=1) + "\n")
    (ROOT / "reports" / "oqmd_hull_disagreement.md").write_text(_hull_md(payload))
    print(f"ok: {len(d):,} matched materials; ALL side disagreement at 0 meV {per['ALL'].get('side_disagreement', {}).get('+0 meV', {}).get('rate')}")


def _hull_md(p: dict) -> str:
    P = p["per_family"]
    A = P["ALL"]
    L = ["# OQMD against MP on the same materials — stage 2 (no ML)", "",
         f"Generated {p['generated_at']}. MP database version **{p['mp_database_version']}** "
         f"({p['mp_thermo_docs']:,} GGA/GGA+U thermo documents retrieved {p['mp_thermo_retrieved_at']}).", "",
         f"**{p['matched_materials']:,}** materials are in both databases ({p['matched_oqmd_entries']:,} OQMD entries; "
         f"{p['match_rule']}). "
         f"OQMD quantity: {p['oqmd_quantity']}. MP quantity: {p['mp_quantity']}. Both are signed, so the "
         "stable side can be compared at a negative threshold.", "",
         "## The ceiling this sets", ""]
    if A.get("n"):
        r = {k: v["rate"] for k, v in A["side_disagreement"].items()}
        L += [f"On the same materials the two databases put the material on **opposite sides** of the threshold "
              f"this often: " + ", ".join(f"{k}: **{v:.4f}**" for k, v in r.items()) + ". "
              f"Mean absolute difference {A['mae_ev'] * 1000:.1f} meV/atom, median signed difference (OQMD − MP) "
              f"{A['median_signed_ev'] * 1000:+.1f} meV/atom, Spearman {A['spearman']:.3f}.", "",
              "**This is a ceiling on what any OQMD evaluation of the harness can mean.** The harness's rules were "
              "certified against MP-convention labels. Where the two conventions disagree on a material's side, an "
              "OQMD 'error' is a convention difference, not a model failure, and an OQMD 'success' may be one too. "
              "An OQMD precision or NPV can therefore not be read as the rule's accuracy unless it is well clear of "
              "the disagreement rate at the matching threshold, and the development report splits these rows out "
              "for exactly that reason.", "",
              f"*Per OQMD entry instead of per material* the rates are higher ("
              + ", ".join(f"{k}: {v:.4f}" for k, v in p["per_entry_side_disagreement_all"].items())
              + "), because OQMD's duplicate entries of a material sit slightly above its hull vertex.", "",
              f"*Near zero.* Of the {p['near_zero_sensitivity']['disagreements_at_0meV']:,} materials on opposite sides "
              f"at exactly 0 meV, {p['near_zero_sensitivity']['of_which_oqmd_within_5meV_of_zero']:,} have an OQMD value "
              f"within 5 meV of zero and {p['near_zero_sensitivity']['of_which_both_within_5meV_of_zero']:,} have both "
              "values within 5 meV of zero: the 0 meV comparison is dominated by meV-scale differences at the hull, "
              "which is why the -20 and +10 meV rows are the ones that match the live rules.", ""]
    L += ["## Side disagreement per family and threshold", "",
          "| family | n | " + " | ".join(f"{t * 1000:+.0f} meV" for t in THRESHOLDS) + " | MAE (meV) | median OQMD−MP (meV) |",
          "|---|---:|" + "---:|" * (len(THRESHOLDS) + 2)]
    for f, x in P.items():
        if not x.get("n"):
            L.append(f"| {f} | 0 |" + " — |" * (len(THRESHOLDS) + 2))
            continue
        L.append(f"| {f} | {x['n']:,} | " + " | ".join(f"{v['rate']:.4f}" for v in x["side_disagreement"].values())
                 + f" | {x['mae_ev'] * 1000:.1f} | {x['median_signed_ev'] * 1000:+.1f} |")
    if A.get("n"):
        L += ["", "## Agreement matrix, all families (rows OQMD bin, columns MP bin, eV/atom)", "",
              "| OQMD \\ MP | " + " | ".join(BINS) + " |", "|---|" + "---:|" * len(BINS)]
        for a in BINS:
            L.append(f"| {a} | " + " | ".join(f"{A['matrix'][a][b]:,}" for b in BINS) + " |")
        L += ["", "Per-family matrices are in `reports/oqmd_hull_disagreement.json`.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    import oqmd_phase3 as P3                        # scripts/oqmd_phase3.py (lock, pilot, plan, runs, report)

    cmds = {"download": download, "normalise": normalise, "protostructures": protostructures,
            "overlap": overlap, "hull-disagreement": hull_disagreement, "lock": P3.lock,
            "pilot-enqueue": P3.pilot_enqueue, "plan": P3.plan, "dev-enqueue": P3.dev_enqueue,
            "prefetch-hull": P3.prefetch_hull, "dev-report": P3.dev_report}
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] not in cmds:
        print(f"{sys.argv[1]}: not implemented yet (implemented: {', '.join(cmds)})")
        sys.exit(75)
    cmds[sys.argv[1]]()
