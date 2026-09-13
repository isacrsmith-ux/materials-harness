"""The unseen-real-materials test set: real Materials Project materials the engine never trained on.

Every stability number in this repository comes from WBM, which is random elemental substitution into
MP prototypes. That is not what a user brings us, and our own 'implausible swap' stratum sometimes
scores better than the plausible one — which says the WBM distribution is not measuring what we think
it measures. This module builds a different test: real MP materials, each reached the way the product
reaches a candidate (a known parent prototype plus one element substitution), scored end to end
through `harness.predict`.

WHAT "NEVER IN THE TRAINING DATA" MEANS HERE
--------------------------------------------
The production engine, MACE-MPA-0 medium, trained on MPtrj + sAlex. MPtrj is "all GGA/GGA+U
static/relaxation trajectories from the 2022.9 version of the Materials Project", so

    MPtrj  ⊆  {materials in MP at 2022.9}  ⊆  {materials in MP at 2023-01-10}

and a material absent from an MP snapshot dated after 2022.9 **cannot** be in MPtrj. We therefore
exclude every material id in Matbench Discovery's own MP reference snapshot,
`2023-01-10-mp-energies.csv.gz` (154,718 ids, 6.8 MB, figshare doi:10.6084/m9.figshare.22715158) —
a proven superset of MPtrj, not an approximation of it. The full MPtrj release is 12.2 GB of JSON
(or a 1.5 GB extxyz mirror) and its exact id list would only ever be a *subset* of what we exclude,
so downloading it could only make the exclusion weaker. `reports/unseen_test.md` states this, and
states what remains uncertain (sAlex, and four `mvc-` ids — see `residual_uncertainty` below).

Snapshot ids are legacy (`mp-10597`); this harness sees the new format (`mp-aaaaaprp`). The two are
the same integer written in base 26 over 'a'-'z', which `legacy_material_id` implements and
`tests/test_unseen.py` verifies against the live MP API.
"""

from __future__ import annotations

import hashlib
import json
import logging
import string
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pymatgen.core import Composition

from harness import compare, mp_data, pairgen
from harness.config import DATA_DIR, EXTERNAL_CACHE_DIR

log = logging.getLogger(__name__)

UNSEEN_FILE = DATA_DIR / "unseen_test.json"
MP_SNAPSHOT = EXTERNAL_CACHE_DIR / "mp" / "2023-01-10-mp-energies.csv.gz"
MP_SNAPSHOT_URL = "https://ndownloader.figshare.com/files/49083124"
MP_SNAPSHOT_SOURCE = ("Matbench Discovery MP reference snapshot 2023-01-10 "
                      "(figshare doi:10.6084/m9.figshare.22715158, file 49083124)")
MAX_ATOMS = 40            # the auto-pair sampler's cap; cells above it are far slower to relax
MAX_PER_PROTOTYPE = 5     # the auto-pair sampler's cap, so no prototype dominates
ALPHABET = string.ascii_lowercase
PRODUCTION_KEY = "mace-mpa-0-medium"


# --- what the engine has seen ---------------------------------------------------------------------

def legacy_material_id(new_id: str) -> str:
    """'mp-aaaaadyf' -> 'mp-2657'. MP's new id format is the legacy integer in base 26 over 'a'-'z'."""
    prefix, _, body = new_id.partition("-")
    if not body or set(body) - set(ALPHABET):
        raise ValueError(f"{new_id!r} is not a new-format MP id")
    n = 0
    for ch in body:
        n = n * 26 + ALPHABET.index(ch)
    return f"{prefix}-{n}"


def new_material_id(legacy_id: str, width: int = 8) -> str:
    """'mp-2657' -> 'mp-aaaaadyf' (the inverse of legacy_material_id)."""
    prefix, _, number = legacy_id.partition("-")
    n, body = int(number), ""
    for _ in range(width):
        body = ALPHABET[n % 26] + body
        n //= 26
    if n:
        raise ValueError(f"{legacy_id!r} does not fit in {width} base-26 digits")
    return f"{prefix}-{body}"


def trained_ids() -> tuple[set, dict]:
    """Legacy ids of every MP material in the 2023-01-10 snapshot, with provenance for the report."""
    if not MP_SNAPSHOT.is_file():
        raise FileNotFoundError(
            f"{MP_SNAPSHOT} missing. It is 6.8 MB:\n"
            f"  mkdir -p {MP_SNAPSHOT.parent} && curl -L -o {MP_SNAPSHOT} {MP_SNAPSHOT_URL}")
    ids = set(pd.read_csv(MP_SNAPSHOT).material_id)
    digest = hashlib.sha256(MP_SNAPSHOT.read_bytes()).hexdigest()
    prefixes = defaultdict(int)
    for i in ids:
        prefixes[i.split("-")[0]] += 1
    return ids, {"source": MP_SNAPSHOT_SOURCE, "file": MP_SNAPSHOT.name, "sha256": digest,
                 "n_ids": len(ids), "id_prefixes": dict(prefixes),
                 "argument": ("MPtrj is built from the MP 2022.9 release, so every MPtrj material is in this "
                              "later snapshot; excluding all of it is a proven superset of excluding MPtrj")}


# --- what else must be excluded --------------------------------------------------------------------

def wbm_prototypes() -> set:
    """(reduced formula, space group number) of every WBM structure — the granularity at which two
    entries are the same material. Formula alone would also drop genuinely different polymorphs."""
    from harness.suites import ood

    s = ood.load_summary()
    sg = s.protostructure_spglib.str.split("_").str[2]
    return set(zip(s.formula.map(lambda f: Composition(f).reduced_formula), sg))


def already_used_ids() -> set:
    """Every MP id already used as a parent or a target in the curated or auto-generated pair sets."""
    from harness.curation import resolve_pairs

    used = set()
    for p in pairgen.load_pairs() + resolve_pairs():
        used.add(p["parent_id"])
        used.add(p["target_id"])
    return used


def wbm_split_ids() -> set:
    """Calibration + locked-test WBM ids. A different id namespace from MP's, so this can only ever be
    empty against MP candidates — checked rather than assumed."""
    from harness import splits

    if not splits.SPLIT_FILE.is_file():
        return set()
    split = splits.load_split()
    return set(split["calibration"]["ids"]) | set(split["test"]["ids"])


# --- building the set ------------------------------------------------------------------------------

def _flip(c: dict) -> dict:
    """Swap parent and target of a candidate pair (and invert the substitution)."""
    src, dst = c["mapping"].split(":")
    return {**c, "parent_id": c["target_id"], "target_id": c["parent_id"],
            "parent_formula": c["target_formula"], "target_formula": c["parent_formula"],
            "mapping": f"{dst}:{src}"}


def _parent_rank(c: dict, by_id: dict) -> tuple:
    """The auto-pair sampler's own preference: experimentally known first, then closest to the hull."""
    p = by_id[c["parent_id"]]
    return (int(bool(p.get("theoretical"))), float(p.get("energy_above_hull") or 9e9), c["parent_id"])


def candidates(max_atoms: int = MAX_ATOMS) -> tuple[dict, dict]:
    """target id -> its candidate pairs (best parent first), plus the counts behind every exclusion."""
    seen, seen_meta = trained_ids()
    hull = mp_data.bulk_gga_hull()
    docs = [{**d, "energy_above_hull": hull[d["material_id"]]}
            for d in mp_data.bulk_summary(max_atoms) if d["material_id"] in hull]
    by_id = {d["material_id"]: d for d in docs}
    unseen = {d["material_id"] for d in docs if legacy_material_id(d["material_id"]) not in seen}

    wbm_fs, used, split_ids = wbm_prototypes(), already_used_ids(), wbm_split_ids()
    excluded = {"in the MP 2023-01-10 snapshot (could be in MPtrj)": len(docs) - len(unseen)}
    keep, drop_counts = set(), defaultdict(int)
    for mid in unseen:
        d = by_id[mid]
        key = (Composition(d["composition_reduced"]).reduced_formula, str(d["sg_number"]))
        if key in wbm_fs:
            drop_counts["same (formula, space group) as a WBM structure"] += 1
        elif mid in used:
            drop_counts["already a parent or target in the curated / auto pair sets"] += 1
        elif mid in split_ids:
            drop_counts["in data/wbm_split.json"] += 1
        else:
            keep.add(mid)
    excluded |= dict(drop_counts)

    cands = pairgen.candidate_pairs(docs, pairgen.supported_elements())
    by_target: dict[str, list] = defaultdict(list)
    for c in cands:
        p, t = c["parent_id"], c["target_id"]
        if t in keep and p not in unseen:
            by_target[t].append(c)
        elif p in keep and t not in unseen:
            f = _flip(c)
            by_target[f["target_id"]].append(f)
    for t in by_target:
        by_target[t].sort(key=lambda c: _parent_rank(c, by_id))
    stats = {"mp_materials_with_gga_hull": len(docs), "not_in_the_snapshot": len(unseen),
             "excluded": excluded, "eligible_targets": len(keep),
             "targets_with_a_seen_parent_of_the_same_prototype": len(by_target),
             "candidate_pairs": sum(len(v) for v in by_target.values()), "snapshot": seen_meta}
    return by_target, stats


def build(max_atoms: int = MAX_ATOMS, max_per_prototype: int = MAX_PER_PROTOTYPE,
          cap_per_bin: int | None = None, path=UNSEEN_FILE, force: bool = False) -> dict:
    """Freeze the unseen test set: one verified (parent, substitution) per unseen target, hashed.

    Verification is `pairgen._check` — the same StructureMatcher prototype confirmation, cell-size cap
    and composition check the auto-pair sampler applies, on the PBE structures. The first parent that
    passes wins. Nothing is dropped silently: every rejection is counted by reason.
    """
    if path.is_file() and not force:
        raise FileExistsError(f"{path} exists; the unseen test set is built once (force=True to rebuild)")
    by_target, stats = candidates(max_atoms)
    order = sorted(by_target, key=lambda t: (len(by_target[t]), t))  # fewest options first: no target is starved
    rejected: dict[str, int] = defaultdict(int)
    proto_count: dict[str, int] = defaultdict(int)
    per_bin: dict[str, int] = defaultdict(int)
    pairs = []
    for i in range(0, len(order), 300):
        chunk = order[i:i + 300]
        mp_data.prefetch_pbe({x[k] for t in chunk for x in by_target[t] for k in ("parent_id", "target_id")})
        for t in chunk:
            for c in by_target[t]:
                if proto_count[c["prototype"]] >= max_per_prototype:
                    rejected["prototype cap reached"] += 1
                    continue
                reason, pair = pairgen._check(c, max_atoms)
                if pair is None:
                    rejected[reason] += 1
                    continue
                b = compare.hull_bin(pair["target_e_above_hull"])
                if cap_per_bin is not None and per_bin[b] >= cap_per_bin:
                    rejected[f"bin {b} cap reached"] += 1
                    break
                pl = pairgen.plausibility(pair["parent_formula"], pair["target_formula"], pair["mapping"])
                pair |= {"source": "unseen", "note": "real MP material absent from the MP 2023-01-10 snapshot",
                         "target_bin": b, "chem_class": pairgen.chem_class(pair["target_formula"]),
                         "plausibility": pl, "plausible": pl["plausible"],
                         "target_legacy_id": legacy_material_id(pair["target_id"]),
                         "parent_legacy_id": legacy_material_id(pair["parent_id"]),
                         "n_parent_options": len(by_target[t])}
                pairs.append(pair)
                proto_count[c["prototype"]] += 1
                per_bin[b] += 1
                break
        log.info("unseen set: %d/%d targets examined, %d accepted", min(i + 300, len(order)), len(order), len(pairs))
    pairs.sort(key=lambda p: p["target_id"])
    target_ids = [p["target_id"] for p in pairs]
    doc = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": ("real Materials Project materials that cannot be in the engine's MPtrj training data, "
                    "each reached from a known parent prototype by one element substitution, scored end to "
                    "end through harness.predict"),
        "n": len(pairs), "sha256": hashlib.sha256(",".join(sorted(target_ids)).encode()).hexdigest(),
        "hash_of": "the target material ids, sorted, comma-joined",
        "locked": True, "design": {"max_atoms": max_atoms, "max_per_prototype": max_per_prototype,
                                   "cap_per_bin": cap_per_bin,
                                   "stratification": ("reported by the target's MP GGA/GGA+U hull bin, the bins the "
                                                      "pair sampler uses; the pool is taken whole rather than "
                                                      "subsampled, so there is no sampling design to bias")},
        "by_bin": {b: per_bin[b] for b in compare.HULL_BINS_MP},
        "by_chem_class": dict(pd.Series([p["chem_class"] for p in pairs]).value_counts()) if pairs else {},
        "plausible_swaps": int(sum(p["plausible"] for p in pairs)),
        "selection": stats, "rejected": dict(rejected),
        "residual_uncertainty": [
            "MACE-MPA-0 also trained on sAlex (subsampled Alexandria). Alexandria was filtered against WBM "
            "prototypes by its authors, not against Materials Project, so an Alexandria structure with the "
            "same prototype as one of these targets could have been in training. This test therefore shows "
            "that the targets are not in MPtrj; it cannot show that they are absent from sAlex.",
            "The snapshot holds 4 'mvc-' ids, which the base-26 id decoding cannot match. If MP later "
            "re-encoded those four materials into the mp- namespace they would not be excluded.",
            "A material that was in MP at 2022.9 and was deprecated before 2023-01-10 would be missing from "
            "the snapshot. Such a material could be in MPtrj and would not be excluded here.",
            "The parents are ordinary known MP materials and are expected to be in the training data. That is "
            "the realistic case: a scientist starts from something known. Only the target must be unseen.",
        ],
        "pairs": pairs,
    }
    path.write_text(json.dumps(doc, indent=1, default=str) + "\n")
    return {k: v for k, v in doc.items() if k != "pairs"}


def load(path=UNSEEN_FILE) -> dict:
    doc = json.loads(path.read_text())
    ids = sorted(p["target_id"] for p in doc["pairs"])
    if hashlib.sha256(",".join(ids).encode()).hexdigest() != doc["sha256"]:
        raise RuntimeError("data/unseen_test.json does not match its recorded hash")
    return doc


# --- running the set through the product -----------------------------------------------------------
# Scored END TO END through harness.predict, not through a suite: each worker is handed the parent's
# MP prototype and the substitution and has to build the candidate itself. The target's DFT-relaxed
# cell and its DFT energy are never given to the pipeline; they are only read in the parent process,
# afterwards, to score what came back.

RUN_FILE = DATA_DIR / "unseen_test_run.json"
OPEN_LOG = DATA_DIR / "unseen_test_log.json"


def predict_job(job: dict) -> dict:
    """Worker side: one full product call. Top-level so the spawn-based pool can pickle it."""
    from harness import predict as P

    p = P.predict(job["parent_id"], job["mapping"],
                  second_engine=None if job.get("one_engine") else P.SECOND_ENGINE,
                  exclude_mp_ids=(job["target_id"],))
    return {"prediction": p.to_dict()}


def build_jobs(pairs: list[dict], one_engine: bool = False) -> list[dict]:
    return [{"job_key": p["pair_id"], "parent_id": p["parent_id"], "target_id": p["target_id"],
             "mapping": p["mapping"], "one_engine": one_engine, "n_atoms": p["n_atoms_target"]}
            for p in pairs]


def prefetch(pairs: list[dict]) -> dict:
    """Warm every Materials Project query the run needs, in this process.

    Workers would otherwise hit the MP API concurrently on a cache miss. This also means the timed run
    measures relaxation, not downloads.
    """
    mp_data.prefetch_pbe({p[k] for p in pairs for k in ("parent_id", "target_id")})
    systems = sorted({"-".join(sorted(e.symbol for e in Composition(p["target_formula"]).elements)) for p in pairs})
    for i, cs in enumerate(systems, 1):
        mp_data.entries_in_chemsys(cs)
        if i % 25 == 0:
            log.info("prefetched MP entries for %d/%d chemical systems", i, len(systems))
    return {"chemical_systems": len(systems), "materials": len({p[k] for p in pairs for k in ("parent_id", "target_id")})}


def eta(pairs: list[dict], workers: int, per_candidate_s: float, ladder_fraction: float = 0.02,
        ladder_s: float = 609.0) -> dict:
    """Wall-clock estimate for a run, from measured per-candidate cost (see reports/unseen_test.md)."""
    n = len(pairs)
    base = n * per_candidate_s
    tail = n * ladder_fraction * ladder_s
    return {"n": n, "workers": workers, "per_candidate_s": round(per_candidate_s, 1),
            "serial_hours": round((base + tail) / 3600, 2),
            "wall_hours": round((base + tail) / workers / 3600, 2),
            "wall_hours_without_ladder_tail": round(base / workers / 3600, 2),
            "ladder_allowance": f"{ladder_fraction:.0%} of candidates x {ladder_s:.0f} s"}


def opened() -> bool:
    return OPEN_LOG.is_file()


def open_once(note: str = "") -> dict:
    """Record that the frozen set is being run. Refused if it has been opened before."""
    if OPEN_LOG.is_file():
        raise RuntimeError(f"{OPEN_LOG} exists: the unseen test set is opened once")
    doc = load()
    rec = {"opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sha256": doc["sha256"],
           "n": doc["n"], "note": note,
           "rule": "scored end to end through harness.predict with the frozen calibration bundle; no threshold refitted"}
    OPEN_LOG.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def run(workers: int | None = None, threads: int | None = None, one_engine: bool = False,
        pairs: list[dict] | None = None, out=RUN_FILE) -> str:
    """Score the frozen set end to end. Results are appended as they arrive, so a stop is not a loss."""
    from harness.config import compute_config_path
    from harness.runner import run_pool

    frozen = pairs is None
    if frozen:
        pairs = load()["pairs"]
        if not opened():
            open_once()
    compute = json.loads(compute_config_path(PRODUCTION_KEY).read_text())
    workers = workers or compute["workers"]
    threads = threads or compute["threads_per_worker"]
    done = {r["job_key"] for r in _load_run(out)} if out.is_file() else set()
    jobs = [j for j in build_jobs(pairs, one_engine) if j["job_key"] not in done]
    jobs.sort(key=lambda j: -j["n_atoms"])
    log.info("unseen run: %d candidates (%d already done) on %d workers x %d threads",
             len(jobs), len(done), workers, threads)
    results = list(_load_run(out)) if out.is_file() else []

    def record(job, res):
        results.append({"job_key": job["job_key"], "target_id": job["target_id"], "parent_id": job["parent_id"],
                        "mapping": job["mapping"], "status": res.get("status"), "error": res.get("error"),
                        "wall_s": res.get("job_wall_s"), **({"prediction": res["prediction"]} if res.get("status") == "ok" else {})})
        out.write_text(json.dumps({"results": results}, indent=1, default=str) + "\n")
        if len(results) % 10 == 0:
            log.info("unseen run: %d/%d complete", len(results), len(results) + len(jobs) - len(results) + len(done))

    run_pool(predict_job, jobs, workers, threads, on_result=record,
             extra_env={"HARNESS_MODEL": PRODUCTION_KEY})
    return str(out)


def _load_run(path=RUN_FILE) -> list:
    return json.loads(path.read_text())["results"] if path.is_file() else []


# --- scoring ----------------------------------------------------------------------------------------
# The DFT truth is read HERE, in the parent process, after the pipeline has answered. Two references
# per target, both from Materials Project's GGA/GGA+U data:
#   the uncorrected PBE energy per atom  -> the energy error
#   the hull distance with the target's OWN entry removed -> the true hull distance, the same quantity
#     WBM's `each_true` is (a WBM material is not in the MP hull either), and the ground truth for
#     'truly stable'. MP's stored energy_above_hull is computed WITH the material in the hull, so it is
#     0 for every hull vertex and can never be negative; it is not that quantity.

def reference(target_id: str) -> dict:
    """MP truth for one target: uncorrected PBE energy, DFT structure, hull distance without itself."""
    from harness import hull as H

    ref = mp_data.pbe_reference(target_id)
    structure = ref["structure"]
    chemsys = "-".join(sorted(e.symbol for e in structure.composition.elements))
    processed = H.process(mp_data.entries_in_chemsys(chemsys))
    target = [e for e in processed if H.material_id(e) == target_id]
    competitors = [e for e in processed if H.material_id(e) != target_id]
    out = {"target_id": target_id, "formula": ref["formula"], "structure": structure,
           "e_dft_per_atom": ref["uncorrected_energy_per_atom"], "mp_e_above_hull": ref["energy_above_hull"],
           "n_competitors": len(competitors)}
    if not target:
        out["true_signed"] = float("nan")
        out["reference_error"] = f"{target_id} is not among the MP2020-processed entries of {chemsys}"
        return out
    try:
        out["true_signed"] = H.signed_hull_energy(competitors, target[0])
    except ValueError as exc:
        out["true_signed"] = float("nan")
        out["reference_error"] = f"hull without {target_id} could not be built: {exc}"
    return out


def score(results: list | None = None, pairs: list | None = None) -> "pd.DataFrame":
    """One row per candidate: what the product said, what MP says, and whether they agree."""
    from pymatgen.core import Structure

    from harness import compare as C
    from harness import metrics as M

    results = _load_run() if results is None else results
    pairs = load()["pairs"] if pairs is None else pairs
    by_id = {p["pair_id"]: p for p in pairs}
    rows = []
    for r in results:
        pair = by_id.get(r["job_key"], {})
        row = {"pair_id": r["job_key"], "target_id": r["target_id"], "parent_id": r["parent_id"],
               "mapping": r["mapping"], "status": r["status"], "error": r.get("error"),
               "wall_s": r.get("wall_s"), "formula": pair.get("target_formula"),
               "design_bin": pair.get("target_bin"), "chem_class": pair.get("chem_class"),
               "plausible": pair.get("plausible"), "n_atoms": pair.get("n_atoms_target")}
        ref = reference(r["target_id"])
        row |= {"e_dft_per_atom": ref["e_dft_per_atom"], "each_true": ref["true_signed"],
                "reference_error": ref.get("reference_error")}
        if r["status"] == "ok":
            p = r["prediction"]
            prov = p["provenance"]
            row |= {"label": p["label"], "reasons": "; ".join(p["reasons"]),
                    "each_pred": None if p["e_above_hull_mev"] is None else p["e_above_hull_mev"] / 1000.0,
                    "warnings": "; ".join(p["warnings"])}
            relax = prov.get("relaxation") or {}
            row["e_model_per_atom"] = relax.get("energy_per_atom_ev")
            row["structure_changed"] = relax.get("structure_changed")
            row["start_used"] = prov.get("start_used")
            row["pred_2"] = prov.get("predicted_hull_second_engine_mev")
            if ref.get("structure") is not None:
                # No structure at all is a structure not found, not a missing measurement: the pipeline
                # was asked for one and did not produce it.
                if p["structure"] is None:
                    row["structure_found"] = False
                else:
                    relaxed = Structure.from_str(p["structure"], fmt="cif")
                    row["structure_found"] = bool(C.relaxed_into_target(relaxed, ref["structure"]))
            if row["e_model_per_atom"] is not None and row["e_dft_per_atom"] is not None:
                row["de_mev"] = (row["e_model_per_atom"] - row["e_dft_per_atom"]) * 1000.0
        rows.append(row)
    df = pd.DataFrame(rows)
    if not len(df):
        return df
    df["truly_stable"] = df.each_true <= M.ON_HULL_TOL
    df["bin"] = df.each_true.map(lambda e: C.hull_bin(e, below_zero_bin=True))
    if "each_pred" in df:
        df["hull_err_mev"] = (df.each_pred - df.each_true) * 1000.0
    return df


# --- report -----------------------------------------------------------------------------------------

def _routing(df: "pd.DataFrame") -> dict:
    """The same summary final_test.md prints, over the product's labels."""
    from harness import routing as R

    d = df.dropna(subset=["label"]).copy()
    d["label"] = d.label.replace({"needs DFT": R.SEND_TO_DFT})
    return R.routing_summary(d[["label", "truly_stable"]])


def family_mix(formulas) -> "pd.Series":
    from harness.confidence import family

    return pd.Series([family(f) for f in formulas]).value_counts(normalize=True)


def family_comparison(labelled: "pd.DataFrame") -> "pd.DataFrame":
    """The chemistry each set is actually made of, against the thresholds that could fire on it.

    This is the table that decides how much the WBM precision can say about real chemistry: a family
    with no certified threshold on a side can never receive that label, whatever the engine predicts.
    """
    from harness import calibration, splits

    test = calibration.calibration_table(ids=set(splits.load_split()["test"]["ids"]),
                                         init_cache="test_init_structs.json")
    rule = calibration.load().rule(with_second_engine=True).thresholds

    def thr(fam, side):
        t = (rule.get(fam) or {}).get(side)
        return "none" if t is None else f"{t * 1000:+.0f}"

    unseen_mix, wbm_mix = family_mix(labelled.formula), family_mix(test.formula)
    rows = []
    for fam in sorted(set(unseen_mix.index) | set(wbm_mix.index), key=lambda f: -unseen_mix.get(f, 0)):
        rows.append({"chemistry family": fam,
                     "this unseen set": f"{unseen_mix.get(fam, 0):.0%}",
                     "locked WBM test": f"{wbm_mix.get(fam, 0):.0%}",
                     "certified 'stable' threshold (meV/atom)": thr(fam, "stable"),
                     "certified 'unstable' threshold (meV/atom)": thr(fam, "unstable")})
    return pd.DataFrame(rows)


def locked_test_counts(max_trustworthy_hull: float | None = None) -> dict:
    """(successes, calls) for 'likely stable' and 'likely unstable' on the locked WBM test set.

    Recomputed here so the comparison uses the SAME interval estimator on both sides. Re-running the
    frozen rules over cached results changes nothing about the locked test: it re-reads an evaluation
    that has already happened.
    """
    from harness import calibration, splits
    from harness import routing as R

    b = calibration.load()
    test_ids = set(splits.load_split()["test"]["ids"])
    test = calibration.calibration_table(ids=test_ids, init_cache="test_init_structs.json")
    second = calibration.calibration_table(calibration.SECOND_ENGINE, test_ids,
                                           "test_init_structs.json").set_index("wbm_id").each_pred
    test = test.assign(pred_2=test.wbm_id.map(second))
    pol = b.policy(with_second_engine=True, max_trustworthy_hull=max_trustworthy_hull)
    rule = b.rule(with_second_engine=True)
    rows = []
    for r in test.itertuples():
        d = R.route(R.Candidate(r.wbm_id, r.formula, r.each_pred, r.pred_2, bool(r.structure_changed)),
                    b.conformal, pol, rule)
        rows.append({"label": d.label, "truly_stable": r.each_true <= 1e-6})
    dec = pd.DataFrame(rows)
    st, un = dec[dec.label == R.LIKELY_STABLE], dec[dec.label == R.LIKELY_UNSTABLE]
    return {"stable": (int(st.truly_stable.sum()), len(st)),
            "unstable": (int((~un.truly_stable).sum()), len(un)),
            "dft_share": float((dec.label == R.SEND_TO_DFT).mean()), "n": len(dec)}


def locked_test_mix() -> "pd.Series":
    """Hull-bin proportions of the locked WBM test set — the mix the published precision is measured at."""
    from harness import calibration, compare as C, splits

    test = calibration.calibration_table(ids=set(splits.load_split()["test"]["ids"]),
                                         init_cache="test_init_structs.json")
    return test.each_true.map(lambda e: C.hull_bin(e, below_zero_bin=True)).value_counts(normalize=True)


def reweighted(df: "pd.DataFrame", weights: "pd.Series", n_boot: int = 2000, seed: int = 0) -> dict:
    """Precision / NPV / DFT share the unseen set would show at another set's hull-bin mix.

    Precision depends on prevalence, and this set's prevalence is not WBM's: it is built from real MP
    materials, which are overwhelmingly near the hull. Comparing the raw numbers with final_test.md
    would compare two different base rates. Weights are renormalised over the bins present here.
    """
    from harness import routing as R

    rng = np.random.default_rng(seed)
    d = df.dropna(subset=["label"]).copy()
    d["label"] = d.label.replace({"needs DFT": R.SEND_TO_DFT})
    bins = [b for b in weights.index if (d.bin == b).any()]
    w = np.array([weights[b] for b in bins], float)
    w = w / w.sum()
    groups = [d[d.bin == b] for b in bins]

    def rates(samples):
        tp = fp = tn = fn = dft = 0.0
        for wi, g in zip(w, samples):
            st, un = g.label == R.LIKELY_STABLE, g.label == R.LIKELY_UNSTABLE
            tp += wi * float((st & g.truly_stable).mean())
            fp += wi * float((st & ~g.truly_stable).mean())
            tn += wi * float((un & ~g.truly_stable).mean())
            fn += wi * float((un & g.truly_stable).mean())
            dft += wi * float((g.label == R.SEND_TO_DFT).mean())
        return {"precision of 'likely stable'": tp / (tp + fp) if tp + fp else float("nan"),
                "NPV of 'likely unstable'": tn / (tn + fn) if tn + fn else float("nan"),
                "share sent to DFT": dft}

    point = rates(groups)
    draws = {k: [] for k in point}
    for _ in range(n_boot):
        boot = [g.iloc[rng.integers(0, len(g), len(g))] for g in groups]
        r = rates(boot)
        for k, v in r.items():
            draws[k].append(v)
    out = {}
    for k, v in point.items():
        a = np.asarray([x for x in draws[k] if np.isfinite(x)], float)
        out[k] = (v, float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))) if a.size else (v, float("nan"), float("nan"))
    out["_bins_used"] = bins
    out["_weights"] = dict(zip(bins, w))
    return out


def report(out=None) -> str:
    """Write reports/unseen_test.md from the frozen set's one run."""
    from harness import calibration, compare as C
    from harness import predict as P
    from harness import metrics as M
    from harness import routing as R
    from harness.config import REPORTS_DIR, ROOT

    doc = load()
    df = score()
    ok = df[df.status == "ok"]
    # A candidate whose own MP reference hull cannot be built has no truth to be scored against. It is
    # counted and named in the report, never silently treated as "not stable".
    labelled = ok.dropna(subset=["label", "each_true"])
    rs = _routing(labelled)
    mix = locked_test_mix()
    rw = reweighted(labelled, mix)
    fam_tbl = family_comparison(labelled)
    opened_at = json.loads(OPEN_LOG.read_text())["opened_at"] if opened() else "not recorded"
    bundle = calibration.load()
    bins = [b for b in C.HULL_BINS_WBM if (labelled.bin == b).any()]

    st = labelled[labelled.label == "likely stable"]
    un = labelled[labelled.label == "likely unstable"]
    # Clopper-Pearson, not bootstrap: with 22 calls and no errors among them a bootstrap returns
    # [1.00, 1.00], and a verdict taken from that bound would be an artifact of the estimator.
    prec = M.proportion_ci(int(st.truly_stable.sum()), len(st))
    npv = M.proportion_ci(int((~un.truly_stable).sum()), len(un))
    wbm = locked_test_counts(max_trustworthy_hull=None)
    wbm_product = locked_test_counts(max_trustworthy_hull=P.MAX_TRUSTWORTHY_HULL_EV)
    wbm_prec = M.proportion_ci(*wbm["stable"])
    wbm_npv = M.proportion_ci(*wbm["unstable"])
    wbm_p_prec = M.proportion_ci(*wbm_product["stable"])
    wbm_p_npv = M.proportion_ci(*wbm_product["unstable"])

    # structure-finding rate, per bin
    found = labelled.dropna(subset=["structure_found"])
    sf = pd.DataFrame([{"bin": b, "n": int((found.bin == b).sum()),
                        "found the target structure": M.fmt_ci(M.boot_ci(found[found.bin == b].structure_found.astype(float), M.MEAN), "{:.2f}"),
                        "relaxation left its start": f"{labelled[labelled.bin == b].structure_changed.fillna(False).mean():.0%}"}
                       for b in bins])
    sf.loc[len(sf)] = ["all", len(found), M.fmt_ci(M.boot_ci(found.structure_found.astype(float), M.MEAN), "{:.2f}"),
                       f"{labelled.structure_changed.fillna(False).mean():.0%}"]

    # energy error, per bin, same structure vs relaxed elsewhere
    def err_rows(sub, label):
        rows = []
        for b in bins:
            g = sub[(sub.bin == b) & sub.de_mev.notna()]
            if not len(g):
                continue
            rows.append({"bin": b, "outcome": label, "n": len(g),
                         "energy MAE": M.fmt_ci(M.boot_ci(g.de_mev, M.MAE)),
                         "median |err|": M.fmt_ci(M.boot_ci(g.de_mev, M.MEDIAN_ABS)),
                         "trimmed mean": M.fmt_ci(M.boot_ci(g.de_mev, M.TRIMMED_MAE))})
        return rows

    energy = pd.DataFrame(err_rows(found[found.structure_found], "same structure")
                          + err_rows(found[~found.structure_found], "relaxed elsewhere"))
    hull_err = pd.DataFrame([{"bin": b, "n": int(((labelled.bin == b) & labelled.hull_err_mev.notna()).sum()),
                              "hull-distance MAE": M.fmt_ci(M.boot_ci(labelled[labelled.bin == b].hull_err_mev, M.MAE)),
                              "median |err|": M.fmt_ci(M.boot_ci(labelled[labelled.bin == b].hull_err_mev, M.MEDIAN_ABS)),
                              "trimmed mean": M.fmt_ci(M.boot_ci(labelled[labelled.bin == b].hull_err_mev, M.TRIMMED_MAE))}
                             for b in bins])
    reasons = pd.Series([x for r in labelled[labelled.label == "needs DFT"].reasons for x in str(r).split("; ")])
    reason_counts = reasons.str.replace(r"\(.*", "", regex=True).str.replace(r"[-+]?\d+ meV/atom", "", regex=True).str.strip().value_counts()

    out = out or REPORTS_DIR / "unseen_test.md"
    wbm_ci = {"raw": (wbm_prec, wbm_npv, wbm["dft_share"]),
              "product": (wbm_p_prec, wbm_p_npv, wbm_product["dft_share"]),
              "counts": wbm, "product_counts": wbm_product}
    L = _markdown(doc, df, ok, labelled, rs, prec, npv, rw, mix, sf, energy, hull_err, reason_counts,
                  opened_at, bundle, bins, fam_tbl, wbm_ci)
    out.write_text("\n".join(L) + "\n")
    return str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out)


STABLE, UNSTABLE, DFT_SHARE = "precision of 'likely stable'", "NPV of 'likely unstable'", "share sent to DFT"


def _md(df: "pd.DataFrame", floatfmt: str = ".3f") -> str:
    return df.to_markdown(index=False, floatfmt=floatfmt)


def _selection_table(doc: dict) -> list:
    sel = doc["selection"]
    rows = [f"| MP materials ≤ {doc['design']['max_atoms']} atoms with a GGA/GGA+U hull | {sel['mp_materials_with_gga_hull']:,} |"]
    rows += [f"| − {k} | −{v:,} |" for k, v in sel["excluded"].items()]
    rows += [f"| eligible unseen targets | {sel['eligible_targets']:,} |",
             f"| … with a *seen* parent of the same prototype | {sel['targets_with_a_seen_parent_of_the_same_prototype']:,} |",
             f"| … surviving prototype confirmation and the {doc['design']['max_per_prototype']}-per-prototype cap "
             f"| **{doc['n']}** |"]
    return ["| step | materials |", "|:--|--:|"] + rows


def _markdown(doc, df, ok, labelled, rs, prec, npv, rw, mix, sf, energy, hull_err, reason_counts,
              opened_at, bundle, bins, fam_tbl, wbm_ci) -> list:
    from harness import metrics as M

    sel, n = doc["selection"], doc["n"]
    failed = df[df.status != "ok"]
    no_ref = ok[ok.each_true.isna()]
    prevalence = float(labelled.truly_stable.mean())
    wbm_prevalence = float(mix.get("<0", 0.0))
    def _cell(v):
        if isinstance(v, float) and not np.isfinite(v):
            return "undefined"
        return f"{v:.3f}" if isinstance(v, float) else f"{v:,}"

    rs_tbl = pd.DataFrame({"quantity": list(rs), "value": [_cell(v) for v in rs.values()]})
    snap = sel["snapshot"]
    prec_s, npv_s = M.fmt_ci(prec, "{:.2f}"), M.fmt_ci(npv, "{:.3f}")
    (w_prec, w_npv, w_dft), (wp_prec, wp_npv, wp_dft) = wbm_ci["raw"], wbm_ci["product"]
    wc, wpc = wbm_ci["counts"], wbm_ci["product_counts"]
    _st = labelled[labelled.label == "likely stable"]
    _un = labelled[labelled.label == "likely unstable"]
    n_prec_k, n_prec_n = int(_st.truly_stable.sum()), len(_st)
    n_npv_k, n_npv_n = int((~_un.truly_stable).sum()), len(_un)
    def _degenerate(ci) -> bool:
        return bool(np.isfinite(ci[1]) and ci[1] == ci[2])

    rw_prec = M.fmt_ci(rw[STABLE], "{:.2f}") + (" †" if _degenerate(rw[STABLE]) else "")
    rw_npv = M.fmt_ci(rw[UNSTABLE], "{:.3f}") + (" †" if _degenerate(rw[UNSTABLE]) else "")
    rw_dft = M.fmt_ci(rw[DFT_SHARE], "{:.3f}")
    dagger = _degenerate(rw[STABLE]) or _degenerate(rw[UNSTABLE])

    L = [f"# The unseen-real-materials test — {bundle.raw['engine']['name']}", "",
         f"Opened once ({opened_at}). {n} real Materials Project materials that cannot be in the engine's MPtrj "
         f"training data, each reached the way a user reaches a candidate — a known parent prototype plus one "
         f"element substitution — and scored **end to end through `harness.predict`**, never through a suite. "
         f"The pipeline was never given the target's DFT-relaxed cell or its DFT energy. Frozen id list "
         f"`data/unseen_test.json`, sha256 `{doc['sha256'][:16]}…`. No threshold was refitted: every rule comes "
         f"from the calibration bundle already frozen for the product.", "",
         "## 1. Why this test exists", "",
         "Every stability number in this repository comes from WBM — random elemental substitution into MP "
         "prototypes. That is not what a user brings us, and our own 'implausible swap' stratum sometimes scores "
         "better than the plausible one, which says the WBM distribution is not measuring what we think it "
         "measures. Here every target is a material that really exists in Materials Project, so every "
         "substitution is one that DFT actually realised.", "",
         "## 2. What counts as unseen", "",
         f"MACE-MPA-0 trained on MPtrj + sAlex. MPtrj is built from the Materials Project 2022.9 release, so every "
         f"MPtrj material appears in any later MP snapshot. We exclude every one of the {snap['n_ids']:,} ids in "
         f"Matbench Discovery's MP reference snapshot `{snap['file']}` — figshare "
         f"doi:10.6084/m9.figshare.22715158 file 49083124, sha256 `{snap['sha256'][:16]}…`.", "",
         "That is a **proven superset** of MPtrj, not an approximation of it. The full MPtrj release is 12.2 GB of "
         "JSON (1.5 GB as an extxyz mirror) and its exact id list could only ever be a *subset* of what is "
         "excluded here — downloading it would make the exclusion weaker, not stronger, so it was not downloaded.", "",
         "Snapshot ids are legacy (`mp-10597`); this harness sees the new format (`mp-aaaaaprp`). The two are the "
         "same integer written in base 26 over 'a'–'z' (`unseen.legacy_material_id`), verified against the live MP "
         "API in `tests/test_unseen.py`.", ""]
    L += _selection_table(doc)
    L += ["", "Rejections while verifying: " + ", ".join(f"{k}: {v}" for k, v in doc["rejected"].items()) + ".", "",
          "Composition of the frozen set: "
          + ", ".join(f"{k} {v}" for k, v in doc["by_bin"].items()) + " by MP hull bin; "
          + ", ".join(f"{k} {int(v)}" for k, v in doc["by_chem_class"].items()) + " by chemistry class; "
          f"{doc['plausible_swaps']} of {n} swaps score as plausible on the pair sampler's own "
          "plausibility model.", "",
          "**Residual uncertainty — stated, not assumed:**", ""]
    L += [f"* {u}" for u in doc["residual_uncertainty"]]
    L += ["", "## 3. What the pipeline was given", "",
          "`predict(parent_mp_id, 'A:B')` — the parent's PBE structure and the substitution, nothing else. It built "
          "both starts itself (`sub`, `sub_rescaled`), relaxed them with the production engine through the same "
          "fallback ladder the calibration results went through, chose the lower-energy usable one, placed its "
          "energy on the Materials Project hull (mode (a)), ran the second engine for the disagreement check, and "
          "labelled the result with the frozen certified thresholds.", "",
          "One thing had to differ from a real call: the target **is** in Materials Project, so its own MP entry "
          "was removed from the reference hull (`exclude_mp_ids`). Otherwise the candidate would be scored against "
          "a hull that already contains it. That is the same removal `stability.evaluate_target` makes for mode "
          "(a), and it is the situation WBM's numbers are in — a WBM material is not in the MP hull either. The "
          "DFT truth below is computed on the same hull, so prediction and truth are commensurate.", "",
          "## 4. Routing — the same quantities as `reports/final_test.md`", ""]
    if len(failed) or len(no_ref):
        parts = [f"{len(df)} candidates ran"]
        if len(failed):
            parts.append(f"{len(failed)} failed outright")
        if len(no_ref):
            parts.append(f"{len(no_ref)} have no usable MP reference hull for scoring")
        L += ["; ".join(parts) + f"; {len(labelled)} are scored below.", ""]
    from harness import routing as R

    degenerate = R.degenerate_stable_label(rs)
    L += [_md(rs_tbl), "",
          (f"**{R.NO_STABLE_LABEL}** on this set — not one candidate cleared a certified stable threshold, so "
           f"the precision of 'likely stable' is undefined here, not zero. 'Likely unstable' NPV: {npv_s} "
           f"(target {bundle.rule(True).target_npv:.0%}). Section 4b says why."
           if degenerate else
           f"'Likely stable' precision: {prec_s} (target {bundle.rule(True).target_precision:.0%}); 'likely "
           f"unstable' NPV: {npv_s} (target {bundle.rule(True).target_npv:.0%})."), "",
          "### Side by side with the locked WBM test set", "",
          "Every rate here is a Clopper–Pearson interval on the actual call counts, on both sides. A "
          "bootstrap collapses to [1.00, 1.00] on a sample with no errors in it — which is exactly this "
          "set's 'likely stable' calls — and a verdict read off that bound would be an artifact of the "
          "estimator rather than a statement about the engine. The locked test's rates are recomputed the "
          "same way from its own counts, so the two columns are comparable; `reports/final_test.md` "
          "publishes bootstrap intervals, which is why its numbers read slightly narrower there.", "",
          "| quantity | locked WBM test | same, with the product's > 0.3 eV/atom refusal | "
          "this unseen set (raw) | this unseen set, reweighted to the WBM bin mix |",
          "|:--|:--|:--|:--|:--|",
          f"| precision of 'likely stable' | {M.fmt_ci(w_prec, '{:.2f}')} ({wc['stable'][0]}/{wc['stable'][1]}) "
          f"| {M.fmt_ci(wp_prec, '{:.2f}')} ({wpc['stable'][0]}/{wpc['stable'][1]}) "
          f"| **{prec_s}** ({n_prec_k}/{n_prec_n}) | {rw_prec} |",
          f"| NPV of 'likely unstable' | {M.fmt_ci(w_npv, '{:.3f}')} ({wc['unstable'][0]}/{wc['unstable'][1]}) "
          f"| {M.fmt_ci(wp_npv, '{:.3f}')} ({wpc['unstable'][0]}/{wpc['unstable'][1]}) "
          f"| **{npv_s}** ({n_npv_k}/{n_npv_n}) | {rw_npv} |",
          f"| share sent to DFT | {w_dft:.3f} | {wp_dft:.3f} | **{rs[DFT_SHARE]:.3f}** | {rw_dft} |",
          f"| prevalence of truly stable | {wbm_prevalence:.3f} | {wbm_prevalence:.3f} | **{prevalence:.3f}** "
          f"| {wbm_prevalence:.3f} |", ""]
    if dagger:
        L += ["† The reweighting resamples within each hull bin, and every 'likely stable' call in every bin "
              "here was correct — so that resampling cannot produce an error either, and the interval "
              "collapses just as the plain bootstrap does. Read the Clopper–Pearson column for the bound that "
              "means something; the reweighted point value still corrects the base rate, which is what it is "
              "for.", ""]
    L += [
          "**Why the reweighted column exists.** Precision depends on the base rate. This set is real Materials "
          f"Project materials, and MP adds mostly near-hull materials, so {prevalence:.0%} of these targets are truly "
          f"stable against {wbm_prevalence:.0%} of the locked WBM test set. Comparing the raw numbers would compare two "
          "different base rates and flatter whichever set holds more stable materials. The last column reweights "
          "this set's per-bin results to the locked test set's hull-bin mix (bins used: "
          f"{', '.join(rw['_bins_used'])}), so the two are commensurate. Both columns are shown; neither is hidden.", "",
          "Why candidates were sent to DFT (a candidate can have several reasons): "
          + ", ".join(f"{k}: {v}" for k, v in reason_counts.items()) + ".", "",
          "### 4b. The two sets are not the same chemistry — and that decides what can be compared at all", "",
          "The certified thresholds are per chemistry family, and a family with no certified threshold on a side "
          "can never receive that label, whatever the engine predicts. So the comparison above is only as "
          "meaningful as the overlap between the two populations' chemistries:", "",
          fam_tbl.to_markdown(index=False), "",
          "Read that table before reading any precision number on this page. Random elemental substitution into "
          "MP prototypes produces rare-earth intermetallics in bulk, which is why the locked WBM test set is "
          "mostly f-electron — and f-electron is the **only** family in which a 'likely stable' threshold could "
          "be certified at all. What Materials Project actually adds is complex oxides and halides, where "
          "neither side is certified. The published precision was therefore measured almost entirely on a "
          "chemistry that barely appears in this set.", "",
          "## 5. Structure-finding rate — did the pipeline arrive at the right structure at all?", "",
          "Nothing in the harness measured this before, and it is a product outcome rather than a diagnostic: if "
          "the relaxation lands somewhere else, every number attached to it describes a material the user did not "
          "ask about. Species-aware StructureMatcher at default tolerances against the target's MP PBE structure, "
          "parsed back from the CIF the product actually returns. 'Relaxation left its start' is the product's own "
          "refusal signal, which needs no DFT structure and is what a real candidate is judged on.", "",
          _md(sf), "",
          "## 6. Energy error against MP's uncorrected PBE energy", "",
          "Split by whether the pipeline found the target structure, because the two are different failures and "
          "are never mixed. MAE with its median and 10 % trimmed mean beside it, per the reporting rule. "
          "meV/atom.", "",
          _md(energy), "",
          "### Predicted hull distance against the true hull distance (meV/atom)", "", _md(hull_err), ""]
    L += _verdict_section(labelled, rw, prec, npv, rs, sf, prevalence, wbm_prevalence, bundle, wbm_ci)
    return L


def _verdict_section(labelled, rw, prec, npv, rs, sf, prevalence, wbm_prevalence, bundle, wbm_ci) -> list:
    """The plain answer: does the WBM precision hold up on real chemistry?"""
    from harness import metrics as M
    from harness.report import VERDICT_RULES, verdict_ci

    found_all = sf.iloc[-1]["found the target structure"]
    n_stable = int((labelled.label == "likely stable").sum())
    n_unstable = int((labelled.label == "likely unstable").sum())
    prec_verdict = verdict_ci("precision", prec) if n_stable else "no data"
    npv_verdict = verdict_ci("npv", npv) if n_unstable else "no data"
    w_prec, w_npv, w_dft = wbm_ci["raw"]
    L = ["## 7. Does the WBM precision hold up on real chemistry?", "",
         "Compared at the Clopper–Pearson lower bound on both sides. A bootstrap is degenerate on a sample "
         "with no errors in it (see §4), so a verdict read off one would be an artifact.", "",
         holds_up(prec, w_prec, "Precision of 'likely stable'"), "",
         holds_up(npv, w_npv, "NPV of 'likely unstable'"), "",
         f"At WBM's base rate, after reweighting: precision {M.fmt_ci(rw[STABLE], '{:.2f}')}, "
         f"NPV {M.fmt_ci(rw[UNSTABLE], '{:.3f}')}. The reweighting corrects the base rate, which is what it "
         f"is for, but its interval is resampled within bins — so where every call in every bin was correct "
         f"it collapses for exactly the reason the plain bootstrap does, and the bound above is the one to "
         f"read.", "",
         "Read at face value:", "",
         f"* `likely stable` was awarded to {n_stable} of {len(labelled)} candidates; precision "
         f"{M.fmt_ci(prec, '{:.2f}')} — **{prec_verdict}** at the pessimistic bound "
         f"(trustworthy ≥ {VERDICT_RULES['precision'][0]:.2f}, caution ≥ {VERDICT_RULES['precision'][1]:.2f}).",
         f"* `likely unstable` was awarded to {n_unstable}; NPV {M.fmt_ci(npv, '{:.3f}')} — **{npv_verdict}** "
         f"(trustworthy ≥ {VERDICT_RULES['npv'][0]:.2f}, caution ≥ {VERDICT_RULES['npv'][1]:.2f}).",
         f"* {rs[DFT_SHARE]:.0%} of candidates were sent to DFT, against {w_dft:.0%} on the locked WBM test set "
         f"({wbm_ci['product'][2]:.0%} once the product's > 0.3 eV/atom refusal is applied there too). That is "
         f"the largest difference between the two populations, and §4b says why.",
         f"* The pipeline arrived at the right structure {found_all} of the time, measured here for the first "
         f"time. Nothing in the WBM numbers speaks to this: a WBM candidate starts from WBM's own initial "
         f"structure, while a real candidate is built from a parent prototype and can land anywhere.", "",
         "### What this set cannot settle", "",
         f"* {len(labelled)} candidates is a tenth of the locked test set, and the near-hull bins carry most of "
         f"them. Intervals here are correspondingly wide, and the thinnest bins should not be read as verdicts.",
         f"* The base rate differs by a factor of {prevalence / wbm_prevalence:.1f} "
         f"({prevalence:.0%} truly stable here against {wbm_prevalence:.0%} on WBM), because Materials Project "
         f"adds mostly near-hull materials. The reweighted point values are the comparable ones; the raw column "
         f"is what a user screening this population would actually see. Neither column's interval is any "
         f"narrower than 22 and 38 calls allow.",
         "* Absence from MPtrj is proven; absence from sAlex is not (see §2).", ""]
    return L


def holds_up(unseen_ci: tuple, wbm_ci: tuple, label: str) -> str:
    """Does a rate measured here hold up against the same rate on the locked WBM test set?

    Compared at the pessimistic (lower) bound, like every other verdict in this project, and reported
    as three outcomes, never two: it holds, it does not, or the two sets cannot be told apart. Both
    bounds are Clopper-Pearson on the actual call counts — a bootstrap collapses to [1, 1] on a sample
    with no errors in it, and a verdict read off that bound would be an artifact (see
    metrics.proportion_ci).
    """
    if not np.isfinite(unseen_ci[0]):
        return f"**{label}: no answer** — no call of that kind was made on this set, so the rate is undefined."
    lo, hi = unseen_ci[1], unseen_ci[2]
    wbm_lo, wbm_point = wbm_ci[1], wbm_ci[0]
    if lo >= wbm_lo:
        return (f"**{label}: it holds up.** The lower bound here ({lo:.2f}) is at or above the lower bound on the "
                f"locked WBM test set ({wbm_lo:.2f}).")
    if hi < wbm_lo:
        return (f"**{label}: it does not hold up.** The whole interval here ([{lo:.2f}, {hi:.2f}]) lies below the "
                f"lower bound on the locked WBM test set ({wbm_lo:.2f}).")
    return (f"**{label}: not distinguishable.** The interval here ([{lo:.2f}, {hi:.2f}]) straddles the WBM lower "
            f"bound ({wbm_lo:.2f}); this set is too small to tell the two apart. The pessimistic reading is that "
            f"the rate could be as low as {lo:.2f}, against {wbm_point:.2f} on WBM.")
