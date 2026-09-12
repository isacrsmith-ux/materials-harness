"""The product's contract, its refusal rules, and one golden end-to-end run.

The refusal tests drive the real frozen calibration bundle (data/calibration_bundle.json) — the same
thresholds a user's prediction is decided by — with a stubbed engine and a stubbed hull placement, so
they check the decision logic without spending a relaxation. The golden test at the bottom is the one
that spends relaxations: it runs a WBM calibration structure through predict() end to end and requires
the answer the calibration run recorded for it. That is what stops a refactor changing the product's
answers without anyone noticing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from harness import calibration, hull
from harness import predict as P
from harness import routing as R

GOLDEN = json.loads((Path(__file__).parent / "data" / "predict_golden.json").read_text())
CONTRACT_FIELDS = {"structure", "e_above_hull_mev", "label", "confidence", "reasons", "properties",
                   "provenance", "warnings"}


@pytest.fixture(scope="module")
def bundle():
    return calibration.load()


def cubic(*species, a: float = 4.0) -> Structure:
    """A cell with the right chemistry; the tests never look at its energy."""
    n = len(species)
    coords = [[i / n, i / n, i / n] for i in range(n)]
    return Structure(Lattice.cubic(a), list(species), coords)


def stub_engine(monkeypatch, energy: float = -5.0, converged: bool = True, relaxed=None, status: str = "ok"):
    """Replace the relaxations with a canned result (no engine is loaded)."""
    def _run(jobs, engine):
        out = []
        for j in jobs:
            if status != "ok":
                out.append({"status": status, "error": "stubbed failure"})
                continue
            out.append({"status": "ok", "relaxed": relaxed if relaxed is not None else j["structure"],
                        "energy_per_atom": energy, "converged": converged, "n_steps": 3, "fmax_final": 0.001,
                        "max_stress_gpa": 0.001, "min_distance_ratio": 1.2, "wall_time_s": 0.1,
                        "metadata": {"model_key": engine[0]}})
        return out

    monkeypatch.setattr(P, "_run", _run)


def stub_hull(monkeypatch, e_above_hull: float, second: float | None = None, raises=None):
    """Replace the MP hull placement with a chosen predicted hull distance (eV/atom)."""
    seen = {"n": 0}

    def _placed(structure, energy_per_atom, label="candidate", exclude_ids=()):
        if raises is not None:
            raise raises
        seen["n"] += 1
        value = second if (second is not None and seen["n"] > 1) else e_above_hull
        return {"signed": value, "e_above_hull": max(value, 0.0), "chemsys": "stub",
                "n_mp_entries": 42, "mp2020_corrections": {}, "construction": "stub"}

    monkeypatch.setattr(hull, "e_above_hull_mode_a", _placed)


# --- contract ---------------------------------------------------------------------------------------

def test_prediction_serialises_to_exactly_the_contract_fields(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle)
    d = json.loads(p.to_json())
    assert set(d) == CONTRACT_FIELDS
    assert d["label"] in (P.LIKELY_STABLE, P.LIKELY_UNSTABLE, P.NEEDS_DFT)
    assert isinstance(d["reasons"], list) and isinstance(d["warnings"], list)
    assert d["structure"].startswith("# generated using pymatgen") or "data_" in d["structure"]
    assert Structure.from_str(d["structure"], fmt="cif") is not None


def test_provenance_pins_engine_checkpoint_settings_and_calibration(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05)
    prov = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle).provenance
    assert prov["engine_key"] == calibration.PRODUCTION_ENGINE[0]
    assert prov["checkpoint_sha256"] == calibration.MODELS[calibration.PRODUCTION_ENGINE[0]]["sha256"]
    assert prov["settings_tag"] and prov["harness_commit"] and prov["timestamp"]
    assert prov["calibration_bundle"]["calibration_ids_sha256"] == bundle.raw["calibration_set"]["ids_sha256"]
    assert prov["calibration_bundle"]["rules"] == "without_second_engine"


def test_confidence_is_the_calibration_cell_not_a_per_call_fit(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05)
    c = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle).confidence
    assert c["family"] == "f-electron" and c["predicted_bin"] == "<0"
    frozen = [r for r in bundle.raw["reliability"] if r["family"] == "f-electron" and r["predicted_bin"] == "<0"][0]
    assert (c["n"], c["hit_rate"], c["ci95"]) == (frozen["n"], frozen["hit_rate"], frozen["ci95"])


def test_properties_are_reported_not_guessed(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05)
    props = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle).properties
    assert props["n_atoms"] == 3 and props["volume_per_atom_A3"] == pytest.approx(64 / 3)
    assert set(props["lattice_constants"]) >= {"a", "b", "c", "alpha", "beta", "gamma"}
    assert "bulk_modulus" not in props  # nine extra relaxations: only on request, never guessed


def test_substitution_parsing_and_structure_sources():
    assert P.parse_substitution("Sr:Ba") == {"Sr": "Ba"}
    assert P.parse_substitution("Sr:Ba,O:S") == {"Sr": "Ba", "O": "S"}
    assert P.parse_substitution("Sr:Ba;O:S") == {"Sr": "Ba", "O": "S"}
    assert P.parse_substitution({"Sr": "Ba"}) == {"Sr": "Ba"}
    s = cubic("Na", "Cl")
    assert P.as_structure(s)[0] is s
    assert P.as_structure(s.to(fmt="cif"))[0].composition.reduced_formula == "NaCl"
    with pytest.raises(ValueError):
        P.as_structure("not-a-structure")


# --- refusal rules ------------------------------------------------------------------------------------

def test_labels_a_confident_stable_candidate(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05)  # below the f-electron certified stable threshold (-20 meV/atom)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle)
    assert p.label == P.LIKELY_STABLE and p.e_above_hull_mev == pytest.approx(-50.0)


def test_labels_a_confident_unstable_candidate(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, 0.05)  # above the f-electron certified unstable threshold (+10 meV/atom)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle)
    assert p.label == P.LIKELY_UNSTABLE


def test_refuses_above_the_trusted_hull_range(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, P.MAX_TRUSTWORTHY_HULL_EV + 0.01)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle)
    assert p.label == P.NEEDS_DFT
    assert any("above the trusted range" in r for r in p.reasons)
    assert p.e_above_hull_mev == pytest.approx(310.0)  # the number is still shown, just not labelled


def test_does_not_refuse_just_below_the_trusted_hull_range(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, P.MAX_TRUSTWORTHY_HULL_EV)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle)
    assert not any("above the trusted range" in r for r in p.reasons)


def test_refuses_when_the_relaxation_left_the_starting_structure(monkeypatch, bundle):
    start = cubic("Th", "Bi", "Pd")
    # A different arrangement of the same atoms. (StructureMatcher normalises volume, so a cell that
    # merely breathed is still the same structure — that is the same signal the report measures.)
    moved = Structure(Lattice.orthorhombic(4.0, 5.5, 7.0), ["Th", "Bi", "Pd"],
                      [[0, 0, 0], [0.5, 0.2, 0.1], [0.1, 0.6, 0.45]])
    stub_engine(monkeypatch, relaxed=moved)
    stub_hull(monkeypatch, -0.05)
    p = P.predict_structure(start, second_engine=None, bundle=bundle)
    assert p.label == P.NEEDS_DFT
    assert any("changed the structure" in r for r in p.reasons)


def test_refuses_known_weak_chemistry(monkeypatch, bundle):
    assert "Pu" in bundle.weak_elements
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05)
    p = P.predict_structure(cubic("Pu", "Bi", "Pd"), second_engine=None, bundle=bundle)
    assert p.label == P.NEEDS_DFT
    assert any("known-weak chemistry" in r and "Pu" in r for r in p.reasons)


def test_refuses_between_the_certified_thresholds(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, 0.0)  # f-electron: certified stable ≤ -20, unstable > +10 meV/atom
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle)
    assert p.label == P.NEEDS_DFT
    assert any("between the certified thresholds" in r for r in p.reasons)


def test_refuses_a_family_with_no_certified_threshold(monkeypatch, bundle):
    assert bundle.rule(with_second_engine=False).thresholds["halide"]["stable"] is None
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05)
    p = P.predict_structure(cubic("Na", "Cl"), second_engine=None, bundle=bundle)
    assert p.label == P.NEEDS_DFT
    assert any("could be certified on either side" in r for r in p.reasons)


def test_refuses_when_the_two_engines_disagree(monkeypatch, bundle):
    tol = bundle.disagreement_tol
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05, second=-0.05 + tol + 0.01)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), bundle=bundle)
    assert p.label == P.NEEDS_DFT
    assert any("engines disagree" in r for r in p.reasons)


def test_agreeing_engines_do_not_refuse(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05, second=-0.05 + bundle.disagreement_tol - 0.01)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), bundle=bundle)
    assert p.label == P.LIKELY_STABLE
    assert p.provenance["calibration_bundle"]["rules"] == "with_second_engine"


def test_refuses_when_no_relaxation_is_usable(monkeypatch, bundle):
    stub_engine(monkeypatch, converged=False)
    stub_hull(monkeypatch, -0.05)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle, use_ladder=False)
    assert p.label == P.NEEDS_DFT and p.structure is None and p.e_above_hull_mev is None
    assert any("no usable relaxation" in r for r in p.reasons)


def test_refuses_an_implausible_energy_without_any_dft_reference(monkeypatch, bundle):
    """The reference-free half of the shared guard (compare.rejection_reason) applies in the product."""
    stub_engine(monkeypatch, energy=-1131.0)
    stub_hull(monkeypatch, -0.05)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), second_engine=None, bundle=bundle, use_ladder=False)
    assert p.label == P.NEEDS_DFT
    assert any("implausible energy" in r for r in p.reasons)


def test_refuses_when_the_reference_hull_cannot_be_built(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05, raises=hull.IncompleteHullError("no reference for Yb"))
    p = P.predict_structure(cubic("Yb", "In", "Au"), second_engine=None, bundle=bundle)
    assert p.label == P.NEEDS_DFT and p.e_above_hull_mev is None
    assert any("no Materials Project reference hull" in r for r in p.reasons)
    assert p.structure is not None  # the relaxed structure is still returned


def test_warns_when_the_engine_is_not_the_calibrated_one(monkeypatch, bundle):
    stub_engine(monkeypatch)
    stub_hull(monkeypatch, -0.05)
    p = P.predict_structure(cubic("Th", "Bi", "Pd"), engine=("mace-mp-0-medium", "cpu", "float64"),
                            second_engine=None, bundle=bundle)
    assert any("not the engine the calibration bundle was fitted on" in w for w in p.warnings)


# --- the frozen bundle is the published one ------------------------------------------------------------

def test_bundle_matches_the_published_calibration_tables(bundle):
    """Guards against a silent refit: these are the numbers in reports/validation_report.md §6c and
    reports/final_test.md."""
    assert sorted(bundle.weak_elements) == ["Be", "Pm", "Pu", "Tc"]
    assert bundle.disagreement_tol * 1000 == pytest.approx(165.3, abs=0.1)
    without = bundle.rule(with_second_engine=False).thresholds
    assert without["f-electron"] == {"stable": -0.02, "unstable": 0.01, "n": 1801}
    assert without["intermetallic"]["unstable"] == 0.0
    assert without["oxide"]["unstable"] == 0.03 and without["pnictide"]["unstable"] == 0.05
    assert bundle.raw["calibration_set"]["n_usable"] == 3998
    halide = [r for r in bundle.raw["reliability"] if r["family"] == "halide" and r["predicted_bin"] == "<0"][0]
    assert halide["n"] == 65 and halide["hit_rate"] == pytest.approx(0.72, abs=0.005)


def test_the_trusted_range_refusal_is_off_for_every_suite():
    """The validation suites' certified numbers must not move because the product refuses something."""
    assert R.RoutingPolicy().max_trustworthy_hull is None
    cal_policy = calibration.fit.__doc__
    assert "applied when a candidate is routed, not when the thresholds are certified" in cal_policy


# --- golden end-to-end (runs the engine) ----------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("wbm_id", sorted(GOLDEN["cases"]))
def test_golden_calibration_structure_end_to_end(wbm_id):
    """predict() on a WBM calibration structure must give what the calibration run recorded for it."""
    from harness.config import ACTIVE_MODEL
    from harness.suites import ood

    if ACTIVE_MODEL != GOLDEN["engine"]:
        pytest.skip(f"set HARNESS_MODEL={GOLDEN['engine']} to run the golden test in-process")
    case = GOLDEN["cases"][wbm_id]
    start = ood.load_structures([wbm_id], cache_file=ood.WBM_DIR / "golden_init.json")[wbm_id]
    p = P.predict_structure(start, second_engine=None if case["label"] != "likely stable" else P.SECOND_ENGINE)
    assert p.properties["formula"] == case["formula"]
    assert p.e_above_hull_mev == pytest.approx(case["e_above_hull_mev"], abs=0.5)
    assert p.label == case["label"]
    assert p.provenance["settings_tag"] == GOLDEN["settings_tag"]
