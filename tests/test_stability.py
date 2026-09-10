"""Offline tests for the stability-gate math (toy phase diagrams, no MACE, no network)."""

import math

import pandas as pd
import pytest
from pymatgen.analysis.phase_diagram import PDEntry
from pymatgen.core import Composition, Lattice, Structure
from pymatgen.entries.computed_entries import ComputedEntry, ComputedStructureEntry

from harness.suites import stability


def pd_entry(formula, e_per_atom):
    c = Composition(formula)
    return PDEntry(c, e_per_atom * c.num_atoms)


def test_material_id_parsing():
    e = ComputedEntry("Fe", -8.0, entry_id="mp-13-GGA")
    assert stability.material_id(e) == "mp-13"
    e = ComputedEntry("FeO", -8.0, entry_id="mp-19009-GGA+U")
    assert stability.material_id(e) == "mp-19009"
    # MP's current format: EntryID object (a dict after the cache round-trip) with the NEW id,
    # while data["material_id"] carries the LEGACY id. The new id must win.
    e = ComputedEntry("Ag", -2.8, entry_id={"identifier": "mp-aaaaaprp", "suffix": "GGA", "separator": "-"},
                      data={"material_id": "mp-10597"})
    assert stability.material_id(e) == "mp-aaaaaprp"
    # MACE entries built by mace_entry() keep the MP id in data and use a "mace:" entry_id.
    e = ComputedEntry("Fe", -8.0, entry_id="mace:Fe->Cr:sub", data={"material_id": "mp-aaaaaaan"})
    assert stability.material_id(e) == "mp-aaaaaaan"


def test_signed_hull_energy_above_and_below():
    competitors = [pd_entry("A", 0.0), pd_entry("B", 0.0), pd_entry("AB", -1.0)]
    assert stability.signed_hull_energy(competitors, pd_entry("AB", -0.9)) == pytest.approx(0.1)
    assert stability.signed_hull_energy(competitors, pd_entry("AB", -1.1)) == pytest.approx(-0.1)
    # With the AB competitor removed, the target is measured against the elements only.
    assert stability.signed_hull_energy(competitors[:2], pd_entry("AB", -0.9)) == pytest.approx(-0.9)


def test_signed_hull_energy_off_stoichiometry():
    competitors = [pd_entry("A", 0.0), pd_entry("B", 0.0), pd_entry("AB", -1.0)]
    # AB2 on the tie line AB-B sits at -2/3 eV/atom.
    assert stability.signed_hull_energy(competitors, pd_entry("AB2", -2 / 3)) == pytest.approx(0.0, abs=1e-9)


def _lif():
    return Structure.from_spacegroup(225, Lattice.cubic(4.03), ["Li", "F"], [[0, 0, 0], [0.5, 0.5, 0.5]])


def test_mace_entry_inherits_parameters_and_gets_identical_correction():
    s = _lif()
    params = {"run_type": "GGA", "is_hubbard": False, "hubbards": {}}
    data = {"oxidation_states": {"Li": 1.0, "F": -1.0}, "material_id": "mp-1138"}
    mp = ComputedStructureEntry(s, -4.9 * len(s), parameters=params, data=data, entry_id="mp-1138-GGA")
    mace = stability.mace_entry(mp, s, -4.8, label="LiF")
    assert mace.energy == pytest.approx(-4.8 * len(s))
    assert mace.parameters == params and mace.parameters is not mp.parameters
    assert mace.data["material_id"] == "mp-1138" and mace.data["source"] == "mace"
    p_mp, p_mace = stability.process([mp]), stability.process([mace])
    assert len(p_mp) == len(p_mace) == 1
    corr_mp, corr_mace = p_mp[0].correction, p_mace[0].correction
    assert corr_mp != 0  # fluoride anion correction applied
    assert corr_mace == pytest.approx(corr_mp)
    assert p_mace[0].energy - p_mp[0].energy == pytest.approx(0.1 * len(s))


def test_metrics_mae_and_classification():
    df = pd.DataFrame({"ref_e_hull": [0.0, 0.0, 0.05, 0.2], "a_e_hull": [0.0, 0.03, 0.0, 0.15]})
    m = stability.metrics(df, "a")
    assert m["n"] == 4
    assert m["mae_ev"] == pytest.approx((0 + 0.03 + 0.05 + 0.05) / 4)
    t0 = m["thr0.0"]  # predicted stable: rows 0, 2 ; truly stable: rows 0, 1
    assert (t0["tp"], t0["fp"], t0["fn"], t0["tn"]) == (1, 1, 1, 1)
    t1 = m["thr0.1"]  # predicted stable: 0,1,2 ; truly stable: 0,1,2
    assert t1["precision"] == 1.0 and t1["recall"] == 1.0 and t1["accuracy"] == 1.0


def test_metrics_skip_nan_rows():
    df = pd.DataFrame({"ref_e_hull": [0.0, 0.1], "b_e_hull": [float("nan"), 0.1]})
    m = stability.metrics(df, "b")
    assert m["n"] == 1 and m["mae_ev"] == pytest.approx(0.0)
    assert not math.isnan(m["thr0.1"]["accuracy"])
