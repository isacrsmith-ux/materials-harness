"""Polymorph ranking: the scoring logic, on structures small enough to reason about by hand."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pymatgen.core import Lattice, Structure

from harness.suites import polymorph as P


def cell(a: float = 4.0, species=("Si", "Si")) -> Structure:
    return Structure(Lattice.cubic(a), list(species), [[0, 0, 0], [0.5, 0.5, 0.5]])


def forms(e_dft, e_model, formula="SiO2", rejections=None, structures=None):
    n = len(e_dft)
    rejections = rejections or [None] * n
    structures = structures or [cell(4.0 + 0.5 * i) for i in range(n)]
    return pd.DataFrame({"formula": [formula] * n, "material_id": [f"mp-{i}" for i in range(n)],
                         "e_dft_per_atom": list(e_dft), "energy_per_atom": list(e_model),
                         "rejection": rejections, "kept_structure": [True] * n,
                         "relaxed": structures})


DOC = {"sets": [{"formula": "SiO2", "n_forms": 4, "hull_bin": "≤0.025", "chem_class": "compound",
                 "dft_gap_mev": 20.0, "dft_spread_mev": 100.0}]}


def test_ranks_the_ground_state_first_when_the_engine_agrees():
    df = forms(e_dft=[-5.00, -4.98, -4.95], e_model=[-6.00, -5.97, -5.90])
    r = P.rank(df, DOC).iloc[0]
    assert r.status == "scored" and r.ground_state_first
    assert r.spearman == pytest.approx(1.0)
    assert r.gap_err_mev == pytest.approx([10.0, 50.0])  # model gaps 30, 100 vs DFT 20, 50


def test_catches_the_engine_picking_the_wrong_ground_state():
    df = forms(e_dft=[-5.00, -4.98, -4.95], e_model=[-5.90, -6.00, -5.95])
    r = P.rank(df, DOC).iloc[0]
    assert not r.ground_state_first
    assert r.picked == "mp-1" and r.truth == "mp-0"
    assert r.spearman < 1.0


def test_a_tie_in_the_dft_energies_counts_as_a_hit_for_either_form():
    df = forms(e_dft=[-5.0, -5.0, -4.9], e_model=[-5.9, -6.0, -5.8])
    assert P.rank(df, DOC).iloc[0].ground_state_first


def test_rejected_relaxations_are_excluded_and_counted_never_averaged_in():
    df = forms(e_dft=[-5.00, -4.98, -4.95, -4.90],
               e_model=[-5.00, -4.97, -4.90, -1131.0],
               rejections=[None, None, None, "implausible energy (-1131 eV/atom outside [-20, 5])"])
    r = P.rank(df, DOC).iloc[0]
    assert r.n_relaxed == 4 and r.n_usable == 3 and r.n_rejected == 1
    assert r.ground_state_first  # the impossible energy did not become the "ground state"
    assert len(r.gap_err_mev) == 2


def test_a_composition_with_too_few_usable_forms_is_not_scored():
    df = forms(e_dft=[-5.0, -4.9, -4.8], e_model=[-5.0, -4.9, -4.8],
               rejections=[None, "not converged", "not converged"])
    r = P.rank(df, DOC).iloc[0]
    assert r.status.startswith("not scored") and "ground_state_first" not in r.index[r.notna()].tolist()


def test_counts_forms_the_relaxation_collapsed_into_one_structure():
    same = cell(4.0)
    df = forms(e_dft=[-5.00, -4.98, -4.95], e_model=[-5.00, -4.98, -4.95],
               structures=[same, same.copy(), cell(6.0, ("Si", "O"))])
    assert P.rank(df, DOC).iloc[0].forms_collapsed == 1


def test_dedupe_drops_repeated_mp_structures_keeping_the_lowest_energy_one():
    s = cell(4.0)
    kept, dropped = P._dedupe([{"structure": s, "e_dft_per_atom": -4.0},
                               {"structure": s.copy(), "e_dft_per_atom": -5.0},
                               {"structure": cell(6.0, ("Si", "O")), "e_dft_per_atom": -3.0}])
    assert dropped == 1 and len(kept) == 2
    assert kept[0]["e_dft_per_atom"] == -5.0


@pytest.mark.parametrize("mev,expected", [(0, "≤10"), (10, "≤10"), (10.1, "10–50"), (50, "10–50"),
                                          (200, "50–200"), (201, ">200"), (float("nan"), "unknown")])
def test_gap_bins(mev, expected):
    assert P._gap_bin(mev) == expected


def test_verdict_rules_exist_for_every_headline_quantity():
    from harness.report import VERDICT_RULES

    for metric in ("ground_state_hit_rate", "spearman", "gap_mae_mev"):
        assert metric in VERDICT_RULES


def test_report_writes_a_complete_page_from_a_small_result_set(tmp_path, monkeypatch):
    """End-to-end smoke test of the report path against a throwaway results database.

    Catches the class of bug that only shows up after a long run: a missing column, an empty group, a
    verdict rule that is not registered.
    """
    import json

    from harness import store
    from harness.config import settings_tag

    sets = {"created_at": "2026-09-12T00:00:00+00:00", "seed": 1,
            "design": {"window_ev": 0.2, "min_forms": 3, "max_forms": 8, "max_atoms": 40,
                       "n_requested": 2, "sampling": "fixed-seed random draw"},
            "eligible_compositions": 10, "n": 2, "n_relaxations": 6,
            "dropped": {"duplicate structure in MP": 1},
            "sets": [{"formula": "SiO2", "n_forms": 3, "composition_e_hull": 0.0, "hull_bin": "≤0.025",
                      "chem_class": "compound", "dft_gap_mev": 20.0, "dft_spread_mev": 100.0,
                      "forms": [{"material_id": f"mp-{i}"} for i in range(3)]},
                     {"formula": "TiO2", "n_forms": 3, "composition_e_hull": 0.05, "hull_bin": "0.025–0.1",
                      "chem_class": "compound", "dft_gap_mev": 120.0, "dft_spread_mev": 150.0,
                      "forms": [{"material_id": f"mp-{i}"} for i in range(3, 6)]}]}
    sets_file = tmp_path / "polymorph_sets.json"
    sets_file.write_text(json.dumps(sets))
    monkeypatch.setattr(P, "SETS_FILE", sets_file)

    tag = settings_tag("cpu", "float32")
    with store.using(tmp_path / "results.sqlite"):
        for formula, base, es in (("SiO2", 0, [(-5.00, -6.00), (-4.98, -5.97), (-4.95, -5.90)]),
                                  ("TiO2", 3, [(-7.00, -8.00), (-6.88, -7.80), (-6.85, -7.84)])):
            for i, (e_dft, e_model) in enumerate(es):
                store.record_job(P.SUITE, f"{formula}:mp-{base + i}@{tag}", "ok", payload={
                    "formula": formula, "material_id": f"mp-{base + i}", "relaxed": cell(4.0 + 0.5 * i),
                    "energy_per_atom": e_model, "e_dft_per_atom": e_dft, "rejection": None,
                    "kept_structure": True, "sg_number": 1, "n_atoms": 2}, settings={"settings_tag": tag})
        out = tmp_path / "polymorph.md"
        assert P.report(tag=tag, out=out)
    text = out.read_text()
    for heading in ("# Polymorph ranking", "## Headline", "ground state ranked first",
                    "Spearman", "## Caveats", "not scored" if False else "## The set"):
        assert heading in text
    assert "nan" not in text.lower().replace("nan-", "")  # no NaN leaks into a published table
