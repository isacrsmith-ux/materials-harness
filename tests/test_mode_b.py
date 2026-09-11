"""Mode (b) on WBM systems: reference / mode (a) / mode (b) hull energies on a synthetic A-B system (offline)."""

import pytest
from pymatgen.core import Lattice, Structure
from pymatgen.entries.computed_entries import ComputedStructureEntry

from harness import mp_data
from harness.suites import mode_b


def _cse(species, e_per_atom, mid):
    s = Structure(Lattice.cubic(3.0 + len(species)), species, [[i / len(species)] * 3 for i in range(len(species))])
    return ComputedStructureEntry(s, e_per_atom * len(s), parameters={"run_type": "GGA", "is_hubbard": False, "hubbards": {}},
                                  data={"oxidation_states": {}}, entry_id={"identifier": mid, "suffix": "GGA"})


def test_evaluate_on_toy_system(monkeypatch):
    # MP phases: Li (0), Na (0), LiNa (-0.1 eV/atom): on the hull. Target Li2Na = WBM entry.
    mp = [_cse(["Li"], 0.0, "mp-1"), _cse(["Na"], 0.0, "mp-2"), _cse(["Li", "Na"], -0.1, "mp-3")]
    monkeypatch.setattr(mp_data, "entries_in_chemsys", lambda cs: mp)
    monkeypatch.setattr(mode_b, "process", lambda entries: list(entries))  # no MP2020 terms in this toy system
    target = _cse(["Li", "Li", "Na"], -0.05, "wbm-x")
    # model: every MP phase and the target 20 meV/atom lower than DFT (a uniform offset cancels in mode b)
    comps = {m: {"relaxed": e.structure, "energy_per_atom": e.energy_per_atom - 0.02, "converged": True,
                 "min_distance_ratio": 1.0} for e, m in zip(mp, ("mp-1", "mp-2", "mp-3"))}
    mace = {"relaxed": target.structure, "e_mace": -0.07}
    ev = mode_b.evaluate("wbm-x", "Li-Na", target, mace, comps, shipped=0.0)
    # hull at Li2Na: 2/3 Li + 1/3 LiNa... hull energy = -0.1 * (2/3) = -0.0667 eV/atom
    assert ev["ref_signed"] == pytest.approx(-0.05 + 0.2 / 3, abs=1e-9)
    assert ev["a_signed"] == pytest.approx(-0.07 + 0.2 / 3, abs=1e-9)       # model target vs DFT hull: offset shows
    assert ev["b_signed"] == pytest.approx(ev["ref_window_signed"], abs=1e-9)  # uniform offset cancels in mode b
    assert ev["b_status"] == "complete"


def test_evaluate_not_scored_when_hull_phase_missing(monkeypatch):
    mp = [_cse(["Li"], 0.0, "mp-1"), _cse(["Na"], 0.0, "mp-2"), _cse(["Li", "Na"], -0.1, "mp-3")]
    monkeypatch.setattr(mp_data, "entries_in_chemsys", lambda cs: mp)
    monkeypatch.setattr(mode_b, "process", lambda entries: list(entries))
    target = _cse(["Li", "Li", "Na"], -0.05, "wbm-x")
    comps = {"mp-1": {"relaxed": mp[0].structure, "energy_per_atom": 0.0, "converged": True, "min_distance_ratio": 1.0},
             "mp-2": {"relaxed": mp[1].structure, "energy_per_atom": 0.0, "converged": False, "min_distance_ratio": 1.0}}
    ev = mode_b.evaluate("wbm-x", "Li-Na", target, {"relaxed": target.structure, "e_mace": -0.05}, comps, 0.0)
    assert ev["b_status"].startswith("not scored") and ev["missing"] == ["mp-3"] and "mp-2" in ev["rejected"]
    assert ev["b_signed"] != ev["b_signed"]  # NaN: not scored
