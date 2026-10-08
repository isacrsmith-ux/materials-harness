"""Aerospace lit session Phase B: Cu oxide thickness vs atomic-oxygen fluence, and the EOIM-3 null set. Data only.

No engine is used. Reads the gitignored row table cache/external/aerospace/durability_rows_v2.csv (built by
scripts/aerospace_ingest.py) and the committed Phase 2 oxide formation energies, then writes:

    reports/aerospace_cu_fluence.json / .md                           names, parameter counts, residual summaries,
                                                                      the null-set observation. No row value,
                                                                      no fitted constant.
    cache/external/aerospace/cu_fluence_side_by_side.md  (gitignored) the rows and the fitted constants.

Run:  .venv/bin/python scripts/aerospace_cu_fluence.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from ase.data import atomic_masses
from ase.units import _Nav, _amu  # _amu in kg

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "external" / "aerospace"
ROWS = CACHE / "durability_rows_v2.csv"
TRANSCRIPTION = CACHE / "transcription_v2.json"
PHASE2 = ROOT / "reports" / "aerospace_durability_development.json"
OUT_JSON = ROOT / "reports" / "aerospace_cu_fluence.json"
OUT_MD = ROOT / "reports" / "aerospace_cu_fluence.md"
SIDE = CACHE / "cu_fluence_side_by_side.md"
SOURCE_ACCURACY = 0.30  # de Rooij p. 487: "not better than +-30%"
# Materials whose NAME identifies the Phase 2 element(s). Alloys whose composition the source does not give are left unmapped.
MAP = {"6061-T6 Al": ["Al"], "Titanium": ["Ti"], "Molybdenum": ["Mo"], "Tungsten": ["W"], "Nb-1Zr": ["Nb"],
       "Mo-13Re": ["Mo"], "W/Nb composite": ["W", "Nb"]}
FORMS = {  # name: (parameters, description)
    "stated_logarithmic": (2, "T = A*log(B*F), the form printed in de Rooij Fig. 8; linear in ln F, so it is also the 'linear-log' form"),
    "inverse_logarithmic": (2, "1/T = a - b*ln F, the other low-temperature law the text names (p. 487); fitted in 1/T"),
    "parabolic": (1, "T^2 = k*F, the diffusion-limited law with fluence standing in for time"),
    "linear": (1, "T = k*F, constant reaction probability"),
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_rows() -> list[dict]:
    out = []
    for r in csv.DictReader(ROWS.open()):
        for k in ("value", "fluence_atoms_per_cm2", "detection_limit"):
            r[k] = float(r[k]) if r[k] not in ("", "None") else None
        r["is_upper_bound"] = r["is_upper_bound"] == "True"
        out.append(r)
    return out


def fit(form: str, F: np.ndarray, T: np.ndarray) -> tuple[np.ndarray, dict]:
    lnF = np.log(F)
    if form == "stated_logarithmic":
        b, a = np.polyfit(lnF, T, 1)
        pred, const = a + b * lnF, {"a_A": a, "b_A_per_efold": b, "A": b, "B": float(np.exp(a / b)) if b else None}
    elif form == "inverse_logarithmic":
        b, a = np.polyfit(lnF, 1 / T, 1)
        pred, const = 1 / (a + b * lnF), {"a": a, "b": b}
    elif form == "parabolic":
        s = float((T * np.sqrt(F)).sum() / F.sum())
        pred, const = s * np.sqrt(F), {"k_A2_per_cm-2": s * s}
    else:
        k = float((T * F).sum() / (F * F).sum())
        pred, const = k * F, {"k_A_per_cm-2": k}
    return pred, const


def summarise(form: str, F: np.ndarray, T: np.ndarray) -> tuple[dict, dict]:
    pred, const = fit(form, F, T)
    p = FORMS[form][0]
    rel = (T - pred) / T
    return ({"form": form, "parameters": p, "n": int(len(T)), "dof": int(len(T) - p),
             "rmse_A": round(float(np.sqrt(np.mean((T - pred) ** 2))), 1),
             "relative_rms_pct": round(100 * float(np.sqrt(np.mean(rel ** 2))), 1),
             "max_abs_relative_residual_pct": round(100 * float(np.abs(rel).max()), 1),
             "points_within_source_accuracy": int((np.abs(rel) <= SOURCE_ACCURACY).sum()),
             "prediction_finite_and_positive": bool(np.all(np.isfinite(pred)) and np.all(pred > 0))},
            {**const, "pred_A": pred.tolist()})


def main() -> None:
    rows = load_rows()
    t = json.loads(TRANSCRIPTION.read_text())
    dr = {r["specimen_id"]: r for r in rows if r["source_key"] == "ntrs_19930001392" and r["quantity"] == "oxide_thickness_average_A"}
    flu_all = {r["specimen_id"]: r["fluence_as_printed"] for r in t["rows"] if r["doc"] == "ntrs_19930001392"}
    rk = {r["quantity"]: r for r in rows if r["source_key"] == "ntrs_19930019095" and r["specimen_id"] == "C9-16"}
    # --- data variants. 1 Angstrom = 0.1 nm.
    base = [(s, dr[s]["fluence_atoms_per_cm2"], dr[s]["value"]) for s in ("C06", "D07", "E10")]
    e02 = ("E02", 1.37e19, dr["E02"]["value"])  # the exponent is printed '09'; reading it as 19 is an inference, labelled
    raikar = ("C9-16 (Raikar)", rk["cu2o_thickness_nm"]["fluence_atoms_per_cm2"], rk["cu2o_thickness_nm"]["value"] * 10)
    assert dr["E02"]["fluence_atoms_per_cm2"] is None and dr["D01"]["value"] is None
    variants = {
        "V1_as_printed": ("de Rooij strips with a readable fluence (E02's exponent is printed '09' and is not read)", base),
        "V2_E02_read_as_1e19": ("V1 plus E02 with its exponent read as 19 (an inference, not stated by the source)", base + [e02]),
        "V3_with_Raikar": ("V1 plus the Raikar Cu2O thin-film point (a different sample type; see 'same hardware?')", base + [raikar]),
        "V4_all": ("V1 plus E02 read as 1e19 plus Raikar", base + [e02, raikar]),
    }
    results, constants = {}, {}
    for vname, (desc, pts) in variants.items():
        F = np.array([p[1] for p in pts], float)
        T = np.array([p[2] for p in pts], float)
        results[vname] = {"description": desc, "n": len(pts), "fluence_span_decades": round(float(np.log10(F.max() / F.min())), 2), "fits": []}
        for form in FORMS:
            s, c = summarise(form, F, T)
            results[vname]["fits"].append(s)
            constants[(vname, form)] = c
    # --- same hardware?  (facts read from the two sources; locators in the report text)
    film_consumed = rk["cu_consumed_nm"]["value"] / rk["film_thickness_unexposed_nm"]["value"]
    # --- how little of the incident oxygen the oxide holds: O atoms per cm2 in the oxide (source Table 1: Cu2O, one O per formula unit)
    tb = t["check_inputs"]["raikar"]["table1"]["Cu2O"]
    n_o = lambda d_A: tb["rho"] * d_A * 1e-8 / tb["M"] * _Nav  # atoms/cm2
    kept = [n_o(p[2]) / p[1] for p in base]
    # --- null set: Lewis EOIM-3 upper bounds beside the Phase 2 formation energies
    p2 = json.loads(PHASE2.read_text())["oxide_formation_per_O_eV"]
    m_o_g = atomic_masses[8] * _amu * 1e3
    area, per_sample = t["check_inputs"]["morton"]["area_cm2"], t["check_inputs"]["morton"]["per_sample_fluence"]
    mass_if_all_kept_mg = per_sample * m_o_g * 1e3
    lim = 0.1
    lewis = [r for r in rows if r["source_key"] == "ntrs_19970025577" and r["quantity"] == "dm_mg"]
    msfc = [r for r in rows if r["source_key"] == "ntrs_19950021220" and r["quantity"] == "dm_mg"]
    pure = {"Cu", "Au", "Ni", "Nb", "Ag", "Ta", "W", "V"}
    table = []
    for mat, els in MAP.items():
        rs = [r for r in lewis if r["material"] == mat]
        table.append({"material": mat, "phase2_elements": els, "flight_samples": len(rs),
                      "at_or_under_upper_bound": sum(r["is_upper_bound"] for r in rs), "quantified": sum(not r["is_upper_bound"] for r in rs),
                      "most_negative_oxide_per_O_eV": {e: {"oxide": p2["mace-mpa-0-medium"][e]["most_negative"],
                                                            "MP": round(p2["mace-mpa-0-medium"][e]["most_negative_mp"], 3),
                                                            "MPA-0": round(p2["mace-mpa-0-medium"][e]["most_negative_engine"], 3)} for e in els}})
    unmapped = sorted({r["material"] for r in lewis} - set(MAP))
    msfc_el = {}
    for e in sorted(pure):
        rs = [r for r in msfc if r["material"] == e]
        if rs:
            msfc_el[e] = {"flight_samples": len(rs), "above_2x_printed_uncertainty": sum(abs(r["value"]) > 0.04 for r in rs),
                          "most_negative_oxide_per_O_eV_MP": round(p2["mace-mpa-0-medium"][e]["most_negative_mp"], 3)}
    null = {
        "table": table, "unmapped_materials": unmapped,
        "unmapped_reason": "alloy composition is not given in the source, or an alloying element has no Phase 2 oxide energy",
        "detection_limit_mg": lim, "lewis_flight_samples": len(lewis),
        "lewis_at_or_under_upper_bound": sum(r["is_upper_bound"] for r in lewis),
        "lewis_quantified": sum(not r["is_upper_bound"] for r in lewis),
        "per_sample_fluence_atoms": per_sample,
        "mass_gain_if_every_incident_O_stuck_mg": round(mass_if_all_kept_mg, 2),
        "upper_bound_net_retained_fraction_of_incident_O_pct": round(100 * lim / mass_if_all_kept_mg, 1),
        "msfc_eoim3_pure_metal_rows_by_element": msfc_el,
    }
    # --- numbers the prose quotes, all computed here
    e10 = dr["E10"]
    rk_vs_e10 = raikar[2] / e10["value"]
    rk_fluence_ratio = raikar[1] / e10["fluence_atoms_per_cm2"]
    gain_el = {e for r in lewis if not r["is_upper_bound"] and r["value"] >= lim for e in MAP[r["material"]]}
    nogain_el = sorted({e for els in MAP.values() for e in els} - gain_el)
    ef = {e: p2["mace-mpa-0-medium"][e]["most_negative_engine"] for e in ("Al", "Ti", "Mo", "W", "Nb", "Cu", "Ag")}
    nogain_range = (min(ef[e] for e in nogain_el), max(ef[e] for e in nogain_el))
    aes_o = [r for r in rows if r["source_key"] == "ntrs_19970025577" and r["quantity"] == "aes_oxygen_signal_change_pct" and r["value"] is not None]
    aes_up = sum(r["value"] > 0 for r in aes_o)
    n_lewis_mat = len({r["material"] for r in lewis})
    gain_rows = sum(1 for r in lewis if not r["is_upper_bound"] and r["value"] >= lim)
    oxide_mg = [n_o(p_[2]) * area * m_o_g * 1e3 for p_ in base]  # O in a Cu2O film of each strip's thickness, on a Lewis disc
    msfc_unc = 0.02
    one_p = [f for v in results.values() for f in v["fits"] if f["parameters"] == 1]
    two_p = {v: {f["form"]: f for f in results[v]["fits"] if f["parameters"] == 2} for v in results}
    rm = lambda v: two_p[v]["stated_logarithmic"]["rmse_A"]
    ratio_2p = max(max(a["rmse_A"], b["rmse_A"]) / min(a["rmse_A"], b["rmse_A"]) for a, b in
                   ((t_["stated_logarithmic"], t_["inverse_logarithmic"]) for t_ in two_p.values()))
    assert all(f["points_within_source_accuracy"] < f["n"] for f in one_p)  # the prose below says so
    within = {form: [v for v in results if all(f["points_within_source_accuracy"] == f["n"] for f in results[v]["fits"] if f["form"] == form)]
              for form in ("stated_logarithmic", "inverse_logarithmic")}
    n_below = sum(r["is_upper_bound"] for r in lewis)
    null.update({"cu_like_oxide_O_mass_on_a_lewis_disc_mg": [float(f"{min(oxide_mg):.2e}"), float(f"{max(oxide_mg):.2e}")],
                 "detection_limit_over_largest_cu_like_oxide_mass": round(lim / max(oxide_mg)),
                 "msfc_2sigma_mg": 2 * msfc_unc,
                 "msfc_2sigma_over_largest_cu_like_oxide_mass": round(2 * msfc_unc / max(oxide_mg))})
    null.update({"elements_with_no_gain_at_or_above_limit": nogain_el, "elements_with_a_gain_at_or_above_limit": sorted(gain_el),
                 "aes_oxygen_signal_rows": len(aes_o), "aes_oxygen_signal_rows_rising": aes_up})
    # --- committed JSON
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {"tier": "development / descriptive, no verdict", "generated_at": now, "rows_v2_sha256": sha(ROWS),
           "variants": results, "forms": {k: {"parameters": v[0], "description": v[1]} for k, v in FORMS.items()},
           "fluence_exponent_E02": "printed 09; excluded from V1, read as 19 only in V2 and V4, labelled an inference",
           "raikar_fraction_of_film_copper_converted_pct": round(100 * film_consumed, 0),
           "raikar_over_nearest_strip_thickness_ratio": round(rk_vs_e10, 2), "raikar_over_nearest_strip_fluence_ratio": round(rk_fluence_ratio, 2),
           "oxygen_retained_in_oxide_fraction_of_incident_range": [float(f"{min(kept):.1e}"), float(f"{max(kept):.1e}")],
           "null_set": null}
    OUT_JSON.write_text(json.dumps(out, indent=1) + "\n")

    # --- gitignored side-by-side with values and constants
    L = ["# Cu oxide thickness vs fluence - rows and fitted constants (GITIGNORED; do not commit)", "",
         f"Generated {now} from `durability_rows_v2.csv` (sha256 `{sha(ROWS)}`).", "",
         "| specimen | fluence as printed | fluence used | thickness (A) | source |", "|---|---|---:|---:|---|"]
    for s in ("D01", "E02", "C06", "D07", "E10"):
        v = dr[s]["value"]
        L.append(f"| {s} | {flu_all[s]} | {dr[s]['fluence_atoms_per_cm2']} | {v} | de Rooij Table II (average) |")
    L.append(f"| C9-16 Cu2O | 8.72 x 10^21 | {raikar[1]} | {raikar[2]} (92 nm) | Raikar p. 1173 (derived) |")
    L += ["", "Raikar film: 68 nm before, 105.3 nm after, 55 nm of Cu converted (81% of the film).", "",
          "## Fitted constants", "", "| variant | form | constants | prediction at each point (A) |", "|---|---|---|---|"]
    for (v, f), c in constants.items():
        L.append(f"| {v} | {f} | " + ", ".join(f"{k}={x:.4g}" for k, x in c.items() if k != "pred_A" and x is not None) +
                 " | " + ", ".join(f"{x:.0f}" for x in c["pred_A"]) + " |")
    L += ["", "## Oxygen held in the oxide, as a fraction of the incident fluence", ""]
    L += [f"- {p[0]}: {k:.2e}" for p, k in zip(base, kept)]
    SIDE.write_text("\n".join(L) + "\n")

    # --- committed markdown
    def fits_table(v):
        rr = ["| form | parameters | n | dof | RMSE (A) | relative RMS | max relative residual | points within the source's +-30% |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for f in results[v]["fits"]:
            rr.append(f"| {f['form']} | {f['parameters']} | {f['n']} | {f['dof']} | {f['rmse_A']} | {f['relative_rms_pct']}% | "
                      f"{f['max_abs_relative_residual_pct']}% | {f['points_within_source_accuracy']} of {f['n']} |")
        return "\n".join(rr)
    md = f"""# Cu oxide thickness vs atomic-oxygen fluence, and the EOIM-3 null set

> **DEVELOPMENT / DESCRIPTIVE TIER. No verdict.** Chosen as the working first target by Isac on 2026-10-07,
> development tier, revisitable (open decision 3 of `reports/aerospace_durability_development.md`, provisionally
> answered). No engine was run. Row values and fitted constants stay in the gitignored
> `cache/external/aerospace/cu_fluence_side_by_side.md`; this report carries names, counts and residual summaries only.

Generated {now} by `scripts/aerospace_cu_fluence.py` from the gitignored row table (sha256 `{sha(ROWS)}`).

## The data, and whether it is one dataset

- **de Rooij** (NTRS 19930001392): copper grounding strips from the Ultra-Heavy Cosmic Ray Experiment trays
  (p. 479), oxide thickness by X-ray (TFOS), Auger-XPS depth profile and, for one strip, colour; Table II's
  average is what the source plots. Four strips have a thickness; D01 has none (a silicone-derived oxide).
  The source states +-30% at best (p. 487).
- **Raikar et al.** (NTRS 19930019095): one 68 nm sputtered Cu film on fused silica from experiment A0114, leading-edge
  row 9, tray C9 (pp. 1170, 1177). Its Cu2O thickness is *derived* from profilometry and XRD with theoretical densities.
- **Same hardware? No.** Different experiments (UHCRE trays 1, 2, 6, 7, 10 against A0114's C9), different sample
  forms (grounding strips against a sputtered film), different trays (the nearest in fluence is strip E10 from tray 10;
  Raikar's is tray C9, row 9), and different thickness methods. They share the spacecraft, the six years and the **modelled** fluence-per-location
  scale: neither source measured fluence on its samples. de Rooij's are stated maxima, and Raikar's paper cites no source
  for its value. Raikar also says his result is consistent with de Rooij's [10]. So they are
  two samples, but **not independent confirmation of the fluence scale**.
- **Raikar's film is nearly used up.** {out['raikar_fraction_of_film_copper_converted_pct']:.0f}% of its copper is
  converted, so growth there may be limited by supply, not by transport. It is not a like-for-like bulk-strip point.
  Its Cu2O thickness is {out['raikar_over_nearest_strip_thickness_ratio']}x that of strip E10 at {out['raikar_over_nearest_strip_fluence_ratio']}x the
  fluence, outside the +-30% de Rooij states for his own method, so the two do not agree quantitatively.
- **Not usable as fluence-resolved rows:** the E02 strip, whose fluence exponent is printed "09" (read as 10^9 or 10^19
  only as a labelled inference); the Raikar solid-Cu CuO overlayer (2-3 nm, probably formed after return to Earth).

## Fits (n is 3 to 5; fitted constants are in the gitignored file)

Four forms, each fitted by unweighted least squares: {", ".join(f"`{k}` ({v[0]} parameter{'s' if v[0] > 1 else ''})" for k, v in FORMS.items())}.
The source states only the first, and gives no constants. "Linear-log" is the same family as the stated form (it is
linear in ln F), so it is not fitted twice; the inverse-logarithmic law, which the source's text names, stands in
as the comparison. The inverse-log fit is done in 1/T, the parabolic and linear fits in T; residuals below are in
thickness.

### V1: de Rooij strips as printed (n = {results['V1_as_printed']['n']}, {results['V1_as_printed']['fluence_span_decades']} decades of fluence)

{fits_table('V1_as_printed')}

### V2: with E02 read as 10^19 (an inference) (n = {results['V2_E02_read_as_1e19']['n']})

{fits_table('V2_E02_read_as_1e19')}

### V3: V1 plus the Raikar point (n = {results['V3_with_Raikar']['n']})

{fits_table('V3_with_Raikar')}

### V4: everything (n = {results['V4_all']['n']})

{fits_table('V4_all')}

**What this supports.** The two one-parameter forms (parabolic, linear) leave at least one point outside the source's
+-30% in every variant, and their worst-case residual never falls below {min(f['max_abs_relative_residual_pct'] for f in one_p)}%: thickness
rises more slowly than the square root of fluence over this span. The two-parameter forms put every point within the source's
+-30% in: the stated form, {", ".join(within['stated_logarithmic']) or "no variant"}; the inverse-log form, {", ".join(within['inverse_logarithmic']) or "no variant"}. With
{min(f['dof'] for v in results.values() for f in v['fits'] if f['parameters'] == 2)} to {max(f['dof'] for v in results.values() for f in v['fits'] if f['parameters'] == 2)} degrees of freedom a small residual mostly counts parameters; it is not evidence for the form. They
**cannot be separated from each other** (their RMSEs differ by at most a factor {ratio_2p:.1f} in any variant). Adding the
Raikar point raises the stated form's RMSE from {rm('V1_as_printed')} A to {rm('V3_with_Raikar')} A, because that film does not lie on the
strips' curve. The oxide holds between {out['oxygen_retained_in_oxide_fraction_of_incident_range'][0]:.0e} and
{out['oxygen_retained_in_oxide_fraction_of_incident_range'][1]:.0e} of the incident O atoms (the three strips with a readable
fluence, using the source's own Cu2O density and formula weight): almost every atom that arrives does not stay as oxide.

## What the harness cannot do here

Its engines return **static energies**, not oxidation rates. Cu2O growth over years in LEO is a kinetic,
transport-limited process: O adsorption and reflection at hyperthermal energy, diffusion of ions and electrons
through a growing scale, sputtering, and re-oxidation after return to Earth. None of that is a static energy,
and the Phase 0 memo found the engines unusable below about 1.25 A, where impacts happen. **Nothing here
predicts a thickness, and a formation energy for Cu2O would say the oxide is favoured, which the flight data
already show.** The only thing the harness could add is a static input to a kinetic model (for example point-defect
energies in Cu2O). That was not computed, not validated, and is not claimed.

## The null set, and what it can and cannot say

Descriptive only; not a rule.

- **Lewis EOIM-3 (NTRS 19970025577):** {null['lewis_flight_samples']} flight samples of {n_lewis_mat} metals at 60 and 200 C, a stated
  detection limit of <{null['detection_limit_mg']} mg, and a per-sample fluence of {null['per_sample_fluence_atoms']:.2e} atoms. **{null['lewis_at_or_under_upper_bound']} are
  stored as upper bounds, {null['lewis_quantified']} as measured** (one at the limit, one a gain). If every incident
  atom stuck, a sample would gain about {null['mass_gain_if_every_incident_O_stuck_mg']} mg, so the limit
  corresponds to **net retention of under {null['upper_bound_net_retained_fraction_of_incident_O_pct']}% of incident O atoms**.
- **Beside the Phase 2 oxide formation energies** (per O atom, MP-corrected convention; most negative stable oxide,
  from `reports/aerospace_durability_development.json`):

| material (named) | flight samples | at or under the limit | measured | element: most negative oxide, MP / MPA-0 (eV per O) |
|---|---:|---:|---:|---|
""" + "\n".join(
        f"| {r['material']} | {r['flight_samples']} | {r['at_or_under_upper_bound']} | {r['quantified']} | " +
        "; ".join(f"{e}: {v['oxide']}, {v['MP']} / {v['MPA-0']}" for e, v in r["most_negative_oxide_per_O_eV"].items()) + " |"
        for r in table) + f"""

  Not mapped ({", ".join(unmapped)}): the composition is not in the source, or an alloying element has no Phase 2 oxide energy
  (no Fe, Cr, Zr, Re, Zn, Co were computed).

- **What the set shows.** No sample of {", ".join(nogain_el)} shows a mass gain at or above the limit (Al's one quantified sample is
  a *loss* at the limit); {", ".join(sorted(gain_el))} has one sample that does, at 60 C and not at 200 C, which the source does not explain.
  The most negative oxide energies of the no-gain set run from {nogain_range[0]:.2f} to {nogain_range[1]:.2f} eV per O (MPA-0). Cu (Cu2O,
  {ef['Cu']:.2f}) and Ag (Ag2O, {ef['Ag']:.2f}) are less favoured by {min(ef['Cu'], ef['Ag']) - nogain_range[1]:.1f} eV per O or more. Within this set,
  **the oxide formation energy does not order the observed mass change**: {n_below} of {len(lewis)} samples are at or under the limit whatever the metal's energy,
  and the one gain is on {sorted(gain_el)[0]} ({ef[sorted(gain_el)[0]]:.2f}), whose energy is within {abs(ef['W'] - ef['Mo']):.2f} eV of Mo ({ef['Mo']:.2f}), where none is seen.
- **But the limit cannot see oxide growth, so this is a weak observation.** An O-containing Cu2O film as thick as the LDEF strips
  reached (the three strips with a readable fluence, the source's own density and formula weight), on a {area} cm2 Lewis disc, holds
  {null['cu_like_oxide_O_mass_on_a_lewis_disc_mg'][0]:.1e} to {null['cu_like_oxide_O_mass_on_a_lewis_disc_mg'][1]:.1e} mg of oxygen: about
  **{null['detection_limit_over_largest_cu_like_oxide_mass']}x below the {null['detection_limit_mg']} mg limit** (and {null['msfc_2sigma_over_largest_cu_like_oxide_mass']}x below
  twice the MSFC set's +-0.02 mg). So a null at this limit is what *any* metal that oxidises like Cu on LDEF would give. The data cannot show that
  Al or Ti oxidise less than Cu does; they bound gross uptake or loss, not film growth. The Lewis memorandum's own account (p. 1,
  introduction) is that aluminium and silicon form protective oxides that resist further oxidation and that silver's oxide spalls
  off and is lost. Those are kinetic and mechanical statements the formation energy does not contain, and this report did not test them.
- **Within one experiment** (the MSFC EOIM-3 pure-metal rows, printed uncertainty +-0.02 mg), samples above twice that
  uncertainty, by element: {", ".join(f"{e} {v['above_2x_printed_uncertainty']} of {v['flight_samples']}" for e, v in null['msfc_eoim3_pure_metal_rows_by_element'].items())}.
  Those mass changes are larger than any Cu-like oxide could add, so **they are not oxide growth of that size**; this analysis does not say what
  they are. The two EOIM-3 sets use different hardware and different detection limits, so they are not pooled.
- **Limits of the comparison.** Different fluences (EOIM-3 about 10^20, LDEF 10^19 to 10^22), a single temperature pair, formation
  energy for the *bulk* oxide only, and surface chemistry that the mass limit cannot see: {null['aes_oxygen_signal_rows_rising']} of the {null['aes_oxygen_signal_rows']}
  Lewis Auger oxygen-signal readings rose, even where the mass change was below the limit.

## Open decisions

1. **Is Cu2O vs fluence still the first target?** With n of 3 to 5, two non-independent sources and no printed
   constants, it can serve as a descriptive reference but not as a validation target for these engines. This is
   in `HANDOFF.md` as an open decision.
2. **Whether to fetch the *Oxidation of Metals* paper** (Raikar, Gregory, Peters, 1994), the likeliest source of
   more Cu points. It is publisher-copyrighted and was not fetched.
"""
    OUT_MD.write_text(md)
    print(json.dumps({"variants": {k: v["n"] for k, v in results.items()}, "null_limit_pct": null["upper_bound_net_retained_fraction_of_incident_O_pct"]}))


if __name__ == "__main__":
    main()
