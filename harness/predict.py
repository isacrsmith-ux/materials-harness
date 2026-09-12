"""The product: one candidate in, one decision out.

Everything else in this repository is a benchmark — a dataset in, a report out. This module is the
single call a scientist makes:

    from harness import predict
    p = predict.predict("mp-2657", "Ti:Zr")          # parent material + element swap
    p = predict.predict_structure(my_structure)      # or a finished candidate

It reuses the validated pieces rather than restating them. The substitution start ladder is
`compare.substitute` + `compare.rescale_to_predicted_volume` and the winner is chosen by
`substitution.best_start`, exactly as the suite does. The relaxation is `jobs.relax_job` at
`config.DEFAULT_RELAX`, with `jobs.ladder_job` behind it, so a candidate goes through the same
fallback ladder the calibration results did. The guard is `compare.rejection_reason`. The hull
distance is `hull.e_above_hull_mode_a` — mode (a), the construction the report recommends for new
materials. The label comes from `routing.route` with the thresholds `calibration.load()` froze from
the calibration set; nothing is fitted here, per call or otherwise.

WHAT THE PRODUCT REFUSES TO LABEL (label "needs DFT", with the reason):
  * a predicted hull distance above MAX_TRUSTWORTHY_HULL_EV (0.3 eV/atom) — the report's verdict up
    there is 'not trustworthy' for every engine, so a number with a wide bar is worse than a refusal;
  * a relaxation that left the starting structure — those results carry 4.6x the energy error;
  * a chemistry on the known-weak element list (Be, Pm, Pu, Tc);
  * a prediction between the certified per-family thresholds, or in a family with no certified rule;
  * disagreement between the two engines beyond the certified tolerance;
  * anything the physical-sanity guard rejects, and any chemistry whose MP reference hull cannot be
    built (see hull.IncompleteHullError).
A refusal is a product outcome, not an error: the Prediction is complete, with `label = "needs DFT"`
and `e_above_hull_mev` still reported when it exists, so the scientist can see what was computed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pymatgen.core import Structure

from harness import calibration, compare, config, hull
from harness import routing as R
from harness.calibration import PRODUCTION_ENGINE, SECOND_ENGINE
from harness.config import DEFAULT_RELAX, settings_tag

log = logging.getLogger(__name__)

LIKELY_STABLE, LIKELY_UNSTABLE, NEEDS_DFT = R.LIKELY_STABLE, R.LIKELY_UNSTABLE, "needs DFT"
# eV/atom. reports/validation_report.md: energy error upper bound 97 meV/atom above 0.3 eV/atom —
# 'not trustworthy' — and 15 % of those relaxations leave their starting structure.
MAX_TRUSTWORTHY_HULL_EV = 0.3
STARTS = ("sub", "sub_rescaled")


@dataclass
class Prediction:
    """One candidate's answer. `to_json()` is the machine-readable form; fields are exactly these."""

    structure: str | None            # relaxed candidate, CIF
    e_above_hull_mev: float | None   # predicted, mode (a): engine energy on the MP DFT hull
    label: str                       # "likely stable" | "likely unstable" | "needs DFT"
    confidence: dict | None          # observed hit rate for this family x predicted bin (calibration)
    reasons: list                    # why it routed that way
    properties: dict                 # volume/atom, lattice constants, bulk modulus where supported
    provenance: dict                 # engine, checkpoint sha256, settings tag, commit, timestamp
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int | None = 1) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @property
    def needs_dft(self) -> bool:
        return self.label == NEEDS_DFT


# --- inputs ---------------------------------------------------------------------------------------

def as_structure(source) -> tuple[Structure, str]:
    """(structure, description) from a Structure, an MP id, a CIF string, or a path to a structure file.

    An MP id resolves to that material's PBE/PBE+U structure (`mp_data.pbe_reference`) — never the
    summary endpoint's r2SCAN cell, which is a different calculation (see harness/mp_data.py).
    """
    if isinstance(source, Structure):
        return source, f"supplied structure ({source.composition.reduced_formula})"
    text = str(source).strip()
    if text.startswith("mp-"):
        from harness import mp_data

        ref = mp_data.pbe_reference(text)
        return ref["structure"], f"{text} {ref['formula']} ({ref['functional']} structure from Materials Project)"
    if "\n" in text or text.lstrip().startswith("data_"):
        return Structure.from_str(text, fmt="cif"), "supplied CIF"
    path = Path(text)
    if path.is_file():
        return Structure.from_file(path), f"structure file {path.name}"
    raise ValueError(f"cannot read a structure from {text[:80]!r}: expected an mp-id, a CIF string, "
                     f"a path to a structure file, or a pymatgen Structure")


def parse_substitution(substitution) -> dict:
    """{'Sr': 'Ba'} from a dict or from 'Sr:Ba', 'Sr:Ba;O:S' or 'Sr:Ba,O:S'."""
    from harness.curation import parse_mapping

    if isinstance(substitution, dict):
        return {str(k): str(v) for k, v in substitution.items()}
    return parse_mapping(str(substitution).replace(",", ";"))


# --- relaxation -----------------------------------------------------------------------------------

def _compute(engine) -> dict:
    """Worker layout for an engine, from its benchmarked compute config."""
    key = engine[0]
    path = config.compute_config_path(key)
    if path.is_file():
        return json.loads(path.read_text())
    from harness.platform_check import core_counts

    return {"workers": 1, "threads_per_worker": core_counts()["performance"]}


def _run(jobs: list, engine) -> list:
    """Run relaxation jobs on `engine`, in this process when it is already the active model.

    A different model needs its own process: mace_mp() sets torch's global default dtype, and the
    production engine (cpu/float32) and the second engine (cpu/float64) would otherwise corrupt each
    other's numbers. `run_pool` spawns workers and `HARNESS_MODEL` selects the model inside them.
    """
    from harness.jobs import run_job
    from harness.runner import run_pool, safe_call

    key, device, dtype = engine
    for j in jobs:
        j.setdefault("device", device)
        j.setdefault("dtype", dtype)
    if config.ACTIVE_MODEL == key:
        return _checked([safe_call(run_job, j) for j in jobs], key)
    compute = _compute(engine)
    out: dict = {}
    run_pool(run_job, jobs, workers=max(1, min(len(jobs), compute.get("workers") or 1)),
             threads=compute.get("threads_per_worker") or 1,
             on_result=lambda j, r: out.__setitem__(id(j), r), extra_env={"HARNESS_MODEL": key})
    return _checked([out.get(id(j), {"status": "failed", "error": "worker produced no result"}) for j in jobs], key)


def _checked(results: list, key: str) -> list:
    """Every result must come from the model that was asked for.

    Engine selection is per process (`HARNESS_MODEL`), so a wrong model is a silent wrong answer rather
    than an error. Each relaxation records the model it actually used, and that is what is checked here.
    """
    for r in results:
        got = (r.get("metadata") or {}).get("model_key")
        if r.get("status") == "ok" and got != key:
            raise RuntimeError(f"relaxation ran {got!r}, not the requested engine {key!r} — engine "
                               f"selection did not take effect in the worker")
    return results


def relax_candidates(starts: dict, engine, use_ladder: bool = True) -> dict:
    """Relax every start (label -> starting structure) and, where the guard rejects rung 1, run the
    same fallback ladder the calibration results went through. Returns label -> result dict."""
    labels = list(starts)
    jobs = [{"job_fn": "relax", "structure": starts[k]} for k in labels]
    results = dict(zip(labels, _run(jobs, engine)))
    if not use_ladder:
        return results
    retry = [k for k, r in results.items()
             if r.get("status") == "ok" and compare.rejection_reason(r) is not None]
    if retry:
        ladder = [{"job_fn": "ladder", "rung1": results[k], "original": starts[k],
                   "seed": compare.stable_seed(k)} for k in retry]
        for k, r in zip(retry, _run(ladder, engine)):
            if r.get("status") == "ok":
                results[k] = {**r, "ladder_of": results[k]}
    return results


def _best(results: dict) -> tuple[str | None, dict]:
    """The lowest-energy usable start, by the suite's own rule (substitution.best_start)."""
    from harness.suites.substitution import best_start

    row = {}
    for k, r in results.items():
        if r.get("status") == "ok":
            row[f"{k}_E"] = r["energy_per_atom"]
            row[f"{k}_usable"] = compare.rejection_reason(r) is None
    win = best_start(row, tuple(results))
    return win, ({} if win is None else results[win])


# --- properties -----------------------------------------------------------------------------------

def _properties(structure: Structure) -> tuple[dict, list]:
    """Volume per atom, density and conventional-cell lattice constants. Nothing is guessed: when
    spglib cannot determine the symmetry there are no conventional lattice constants to report, and
    the key is absent rather than filled with the raw cell."""
    cell = compare.conventional_cell(structure)
    props = {"formula": structure.composition.reduced_formula, "n_atoms": len(structure),
             "volume_per_atom_A3": compare.volume_per_atom(structure),
             "density_g_cm3": float(structure.density)}
    warnings = []
    if cell.spacegroup:
        props["spacegroup"] = cell.spacegroup
        props["crystal_system"] = cell.crystal_system
        props["lattice_constants"] = {"a": cell.a, "b": cell.b, "c": cell.c,
                                      "alpha": cell.alpha, "beta": cell.beta, "gamma": cell.gamma,
                                      "units": "Å and degrees, conventional standard cell (symprec %.2f)"
                                               % compare.SYMPREC}
    else:
        warnings.append("spglib could not determine the symmetry of the relaxed cell; no conventional "
                        "lattice constants are reported")
    return props, warnings


def bulk_modulus(structure: Structure, engine=PRODUCTION_ENGINE) -> dict:
    """Birch-Murnaghan bulk modulus of a relaxed structure: 9 constant-volume relaxations, then the
    suite's own fit (`bulk.eos_bulk_modulus`). Off by default — it costs nine more relaxations.

    The report's verdict on this quantity is 'use with caution': 11.9 % MAE against MP's K_VRH
    (upper bound 16.8 %, n=82), and an EOS with relaxed cell shape is a Reuss-like average, so it is
    not comparable with a Voigt one. Both statements travel with the number.
    """
    from harness.suites import bulk

    jobs = [{"job_fn": "eos", "structure": structure, "volume_factors": bulk.VOLUME_FACTORS}]
    res = _run(jobs, engine)[0]
    if res.get("status") != "ok":
        return {"error": res.get("error", "EOS failed")}
    eos = bulk.eos_bulk_modulus(res["points"])
    if eos["fit"] is None:
        return {"error": eos["error"], "n_points": eos["n_points"]}
    return {"b0_gpa": eos["fit"]["b0_gpa"], "bp": eos["fit"]["bp"], "n_points": eos["n_points"],
            "fit_rms_mev": eos["fit"]["rms_mev"], "fit_ok": eos["fit_ok"],
            "method": "third-order Birch-Murnaghan, 9 volumes 0.96-1.04 V0, cell shape relaxed at fixed volume",
            "caveat": ("reports/validation_report.md §10: 11.9 % MAE vs MP K_VRH (upper bound 16.8 %, n=82) — "
                       "'use with caution'; a relaxed-shape EOS is a Reuss-like average, MP's K_VRH is a "
                       "Voigt-Reuss-Hill one")}


# --- the call -------------------------------------------------------------------------------------

def _provenance(engine, second, bundle, started_at, starts, parent_desc, extra) -> dict:
    key, device, dtype = engine
    m = config.MODELS[key]
    out = {"engine": m["name"], "engine_key": key, "checkpoint": m["file"],
           "checkpoint_sha256": m["sha256"], "device": device, "dtype": dtype,
           "settings_tag": settings_tag(device, dtype, model=key), "relax_settings": DEFAULT_RELAX.as_dict(),
           "harness_commit": calibration.harness_commit(),
           "timestamp": started_at.isoformat(timespec="seconds"),
           "wall_time_s": (datetime.now(timezone.utc) - started_at).total_seconds(),
           "calibration_bundle": {"created_at": bundle.raw["created_at"],
                                  "harness_commit": bundle.raw["harness_commit"],
                                  "calibration_ids_sha256": bundle.raw["calibration_set"]["ids_sha256"],
                                  "rules": bundle.rule_name(second is not None)},
           "parent": parent_desc, **(starts or {}),
           "hull": "mode (a): engine energy on the Materials Project GGA/GGA+U hull, MP2020 corrections"}
    if second:
        skey = second[0]
        out["second_engine"] = {"engine": config.MODELS[skey]["name"], "engine_key": skey,
                                "checkpoint_sha256": config.MODELS[skey]["sha256"],
                                "device": second[1], "dtype": second[2],
                                "settings_tag": settings_tag(second[1], second[2], model=skey)}
    return out | extra


def _refused(label_reasons, warnings, props, prov, structure=None, e_hull_mev=None, confidence=None) -> Prediction:
    return Prediction(structure=structure.to(fmt="cif") if structure is not None else None,
                      e_above_hull_mev=e_hull_mev, label=NEEDS_DFT, confidence=confidence,
                      reasons=label_reasons, properties=props, provenance=prov, warnings=warnings)


def predict(parent_structure, substitution=None, *, engine=None, second_engine=SECOND_ENGINE,
            use_ladder: bool = True, with_bulk_modulus: bool = False, bundle=None,
            exclude_mp_ids=()) -> Prediction:
    """One candidate, one decision.

    parent_structure  an MP id ('mp-2657'), a CIF string, a path, or a pymatgen Structure
    substitution      'Sr:Ba', 'Sr:Ba;O:S' or {'Sr': 'Ba'}; None means parent_structure IS the
                      finished candidate (identical to predict_structure)
    engine            (registry key, device, dtype); default the production engine, MACE-MPA-0 medium
    second_engine     the disagreement engine; None runs one engine and uses the rule certified for
                      that configuration (never measured on the locked test set — see docs/predict.md)
    exclude_mp_ids    EVALUATION ONLY: MP materials to leave out of the reference hull, so a material
                      Materials Project already has can be scored as if it were new
                      (harness/hull.py: e_above_hull_mode_a). Empty for a real candidate.
    """
    if substitution is None:
        return predict_structure(parent_structure, engine=engine, second_engine=second_engine,
                                 use_ladder=use_ladder, with_bulk_modulus=with_bulk_modulus, bundle=bundle,
                                 exclude_mp_ids=exclude_mp_ids)
    engine = engine or PRODUCTION_ENGINE
    parent, parent_desc = as_structure(parent_structure)
    mapping = parse_substitution(substitution)
    sub = compare.substitute(parent, mapping)
    rescaled, info = compare.rescale_to_predicted_volume(sub, parent)
    starts = {"sub": sub}
    warnings = []
    if info.get("method"):
        starts["sub_rescaled"] = rescaled
    else:
        warnings.append("no volume predictor succeeded, so the rescaled start does not exist "
                        f"({'; '.join(info.get('failed_methods') or []) or 'no reason recorded'})")
    return _predict(starts, engine=engine, second_engine=second_engine, use_ladder=use_ladder,
                    with_bulk_modulus=with_bulk_modulus, bundle=bundle, warnings=warnings,
                    exclude_mp_ids=exclude_mp_ids, parent_desc=f"{parent_desc}, substitution {mapping}",
                    start_info={"sub": {"method": "parent volume (unscaled)", "volume_factor": 1.0},
                                "sub_rescaled": info})


def predict_structure(structure, *, engine=None, second_engine=SECOND_ENGINE, use_ladder: bool = True,
                      with_bulk_modulus: bool = False, bundle=None, exclude_mp_ids=()) -> Prediction:
    """The second form: a finished candidate structure, relaxed and decided as it stands."""
    s, desc = as_structure(structure)
    return _predict({"as_given": s}, engine=engine or PRODUCTION_ENGINE, second_engine=second_engine,
                    use_ladder=use_ladder, with_bulk_modulus=with_bulk_modulus, bundle=bundle,
                    warnings=[], exclude_mp_ids=exclude_mp_ids, parent_desc=desc,
                    start_info={"as_given": {"method": "supplied structure, unchanged"}})


def _predict(starts: dict, *, engine, second_engine, use_ladder, with_bulk_modulus, bundle, warnings,
             parent_desc, start_info, exclude_mp_ids=()) -> Prediction:
    started_at = datetime.now(timezone.utc)
    bundle = bundle or calibration.load()
    warnings = list(warnings)
    fitted_on = (bundle.raw["engine"]["key"], bundle.raw["engine"]["device"], bundle.raw["engine"]["dtype"])
    if tuple(engine) != fitted_on:
        warnings.append(f"engine {tuple(engine)} is not the engine the calibration bundle was fitted on "
                        f"({fitted_on}); its thresholds and confidence do not apply to this engine")
    prov = lambda extra=None: _provenance(engine, second_engine, bundle, started_at,  # noqa: E731
                                          extra_start, parent_desc, extra or {})
    extra_start = None

    results = relax_candidates(starts, engine, use_ladder=use_ladder)
    win, best = _best(results)
    tried = {k: (start_info.get(k) or {}) | {"outcome": _outcome_of(results[k])} for k in results}
    extra_start = {"starts": tried}
    if win is None:
        why = "; ".join(f"{k}: {_outcome_of(r)}" for k, r in results.items())
        return _refused([f"no usable relaxation of this candidate ({why})"], warnings, {}, prov())
    extra_start["start_used"] = win

    relaxed = best["relaxed"]
    formula = relaxed.composition.reduced_formula
    props, prop_warnings = _properties(relaxed)
    warnings += prop_warnings
    changed = not compare.relaxed_into_target(relaxed, starts[win])

    try:
        placed = hull.e_above_hull_mode_a(relaxed, best["energy_per_atom"], label=formula,
                                          exclude_ids=exclude_mp_ids)
    except (hull.IncompleteHullError, ValueError) as exc:
        return _refused([f"no Materials Project reference hull for this chemistry ({exc})"],
                        warnings, props, prov(), structure=relaxed)
    pred = placed["signed"]

    pred_2 = None
    if second_engine is not None:
        second = relax_candidates({win: starts[win]}, second_engine, use_ladder=use_ladder)[win]
        if second.get("status") == "ok" and compare.rejection_reason(second) is None:
            try:
                pred_2 = hull.e_above_hull_mode_a(second["relaxed"], second["energy_per_atom"],
                                                 label=f"{formula}:second", exclude_ids=exclude_mp_ids)["signed"]
            except (hull.IncompleteHullError, ValueError) as exc:
                warnings.append(f"second engine could not be placed on the hull ({exc}); "
                                "the disagreement check did not run")
        else:
            warnings.append(f"second engine produced no usable result ({_outcome_of(second)}); "
                            "the disagreement check did not run")
        if pred_2 is None:
            warnings.append("the certified thresholds in use assume the disagreement check ran; "
                            "this candidate was decided without it")

    policy = bundle.policy(with_second_engine=second_engine is not None,
                           max_trustworthy_hull=MAX_TRUSTWORTHY_HULL_EV)
    rule = bundle.rule(with_second_engine=second_engine is not None)
    candidate = R.Candidate(id=formula, formula=formula, pred_e_hull=pred, pred_e_hull_2=pred_2,
                            structure_changed=changed)
    decision = R.route(candidate, bundle.conformal, policy, rule)
    label = NEEDS_DFT if decision.label == R.SEND_TO_DFT else decision.label
    reasons = list(decision.reasons) + _uncertifiable(formula, rule)

    confidence = bundle.reliability(formula, pred)
    if confidence is None:
        warnings.append(f"no calibration cell for {formula}'s chemistry family and predicted hull bin; "
                        "no observed hit rate can be quoted")
    if with_bulk_modulus:
        props["bulk_modulus"] = bulk_modulus(relaxed, engine)
    extra = {"hull_details": placed, "conformal_interval": decision.interval,
             "predicted_hull_second_engine_mev": None if pred_2 is None else pred_2 * 1000,
             "relaxation": {"energy_per_atom_ev": best["energy_per_atom"],
                            "converged": best["converged"], "n_steps": best["n_steps"],
                            "fmax_final": best["fmax_final"], "max_stress_gpa": best["max_stress_gpa"],
                            "wall_time_s": best["wall_time_s"], "rung": best.get("rung", "default"),
                            "structure_changed": changed}}
    return Prediction(structure=relaxed.to(fmt="cif"), e_above_hull_mev=pred * 1000, label=label,
                      confidence=confidence, reasons=reasons, properties=props,
                      provenance=prov(extra), warnings=warnings)


def _uncertifiable(formula: str, rule) -> list:
    """A family for which neither side could be certified is a different situation from a prediction
    that happens to fall between two thresholds, and says so."""
    from harness.confidence import family

    fam = family(formula)
    th = rule.thresholds.get(fam)
    if th and th["stable"] is None and th["unstable"] is None:
        return [f"no threshold could be certified on either side for the {fam} family at "
                f"{rule.target_precision:.0%} precision / {rule.target_npv:.0%} NPV "
                f"(n={th['n']} labelable calibration structures)"]
    return []


def _outcome_of(result: dict) -> str:
    if result.get("status") != "ok":
        return f"{result.get('status', 'failed')}: {result.get('error')}"
    return compare.rejection_reason(result) or "usable"


# --- human-readable output -------------------------------------------------------------------------

def render(p: Prediction) -> str:
    """The default CLI output: the decision, the number, the confidence, and every reason."""
    props = p.properties
    L = [f"candidate       {props.get('formula', '?')}"
         + (f"  ({props['n_atoms']} atoms, SG {props['spacegroup']}, {props['crystal_system']})"
            if props.get("spacegroup") else ""),
         f"decision        {p.label.upper()}"]
    if p.e_above_hull_mev is not None:
        L.append(f"hull distance   {p.e_above_hull_mev:+.0f} meV/atom (predicted, mode (a))")
    second = (p.provenance or {}).get("predicted_hull_second_engine_mev")
    if second is not None:
        L.append(f"second engine   {second:+.0f} meV/atom "
                 f"({(p.provenance.get('second_engine') or {}).get('engine', 'second engine')})")
    if p.confidence:
        c = p.confidence
        L.append(f"confidence      a plain '{c['call']}' call for {c['family']} in the {c['predicted_bin']} "
                 f"predicted bin was right {c['hit_rate']:.0%} of the time "
                 f"[{c['ci95'][0]:.0%}, {c['ci95'][1]:.0%}] on {c['n']} calibration structures")
    else:
        L.append("confidence      not available for this chemistry family and predicted bin")
    if p.reasons:
        L.append("why")
        L += [f"  - {r}" for r in p.reasons]
    if props.get("lattice_constants"):
        lc = props["lattice_constants"]
        L.append(f"lattice         a={lc['a']:.4f} b={lc['b']:.4f} c={lc['c']:.4f} Å, "
                 f"α={lc['alpha']:.2f} β={lc['beta']:.2f} γ={lc['gamma']:.2f}°")
    if props.get("volume_per_atom_A3") is not None:
        L.append(f"volume          {props['volume_per_atom_A3']:.3f} Å³/atom "
                 f"({props['density_g_cm3']:.3f} g/cm³)")
    bm = props.get("bulk_modulus")
    if bm and bm.get("b0_gpa") is not None:
        L.append(f"bulk modulus    {bm['b0_gpa']:.1f} GPa  ({bm['n_points']} EOS points; {bm['caveat']})")
    elif bm:
        L.append(f"bulk modulus    not reported ({bm.get('error')})")
    prov = p.provenance or {}
    L.append(f"engine          {prov.get('engine')} · {prov.get('device')}/{prov.get('dtype')} · "
             f"settings {prov.get('settings_tag')} · harness {prov.get('harness_commit')}")
    for w in p.warnings:
        L.append(f"warning         {w}")
    return "\n".join(L)
