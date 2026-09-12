"""Phase 0 fixes: run-type rule, rescaled starts, best start, fallback ladder, mode (b) status, dispatch."""

import math

import pytest
from pymatgen.core import Lattice, Structure
from pymatgen.entries.computed_entries import ComputedStructureEntry

from harness import compare, config, engine, jobs, mp_data, store
from harness.suites import stability, substitution


# --- run type (GGA vs GGA+U) -------------------------------------------------------------------

def test_run_type_single_entry_is_used_as_is():
    assert mp_data.choose_run_type({"GGA": {}}, ["Fe", "O"]) == ("GGA", "only GGA present")
    assert mp_data.choose_run_type({"GGA+U": {}}, ["Si"])[0] == "GGA+U"


@pytest.mark.parametrize("els,want", [(["Fe", "O"], "GGA+U"), (["Ni", "F"], "GGA+U"), (["Li", "Mn", "O"], "GGA+U"),
                                      (["Fe", "S"], "GGA"), (["Al", "O"], "GGA"), (["W"], "GGA")])
def test_run_type_with_both_follows_mp2020_mixing(els, want):
    rt, rule = mp_data.choose_run_type({"GGA": {}, "GGA+U": {}}, els)
    assert rt == want and rule.startswith("both")


def test_run_type_without_pbe_entry_raises():
    with pytest.raises(KeyError):
        mp_data.choose_run_type({"R2SCAN": {}}, ["Si"])


def _thermo_doc(formula_species, order):
    s = Structure.from_spacegroup(225, Lattice.cubic(4.3), formula_species, [[0, 0, 0], [0.5, 0.5, 0.5]])
    ents = {"GGA": ComputedStructureEntry(s, -7.0 * len(s), parameters={"run_type": "GGA"}, entry_id="mp-x-GGA"),
            "GGA+U": ComputedStructureEntry(s, -6.5 * len(s), parameters={"run_type": "GGA+U"}, entry_id="mp-x-GGA+U")}
    return {"material_id": "mp-x", "thermo_type": "GGA_GGA+U", "energy_per_atom": -7.2, "energy_above_hull": 0.0,
            "is_stable": True, "entries": {k: ents[k].as_dict() for k in order}}


@pytest.mark.parametrize("order", [("GGA", "GGA+U"), ("GGA+U", "GGA")])
def test_pbe_from_thermo_never_takes_plain_gga_for_a_u_oxide(order):
    ref = mp_data._pbe_from_thermo(_thermo_doc(["Fe", "O"], order))
    assert ref["run_type"] == "GGA+U" and ref["functional"] == "PBE+U"
    assert ref["uncorrected_energy_per_atom"] == pytest.approx(-6.5)
    assert ref["run_type_rule"].startswith("both")
    assert mp_data._pbe_from_thermo(_thermo_doc(["Fe", "S"], order))["run_type"] == "GGA"


# --- rescaled substitution start ---------------------------------------------------------------

def _diamond(el, a):
    return Structure.from_spacegroup(227, Lattice.cubic(a), [el], [[0, 0, 0]])


def test_rescale_shrinks_si_to_c_and_keeps_geometry():
    si = _diamond("Si", 5.47)
    sub = compare.substitute(si, {"Si": "C"})
    out, info = compare.rescale_to_predicted_volume(sub, si)
    assert info["method"] is not None
    assert info["volume_factor"] == pytest.approx(out.volume / sub.volume)
    assert 0.15 < info["volume_factor"] < 0.5  # diamond C / Si volume per atom is ~0.28
    assert out.composition == sub.composition
    assert (abs(out.frac_coords - sub.frac_coords) < 1e-9).all()


def test_rescale_grows_nacl_to_kcl():
    nacl = Structure.from_spacegroup(225, Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    _, info = compare.rescale_to_predicted_volume(compare.substitute(nacl, {"Na": "K"}), nacl)
    assert info["volume_factor"] > 1.05


# --- best start --------------------------------------------------------------------------------

def test_best_start_prefers_lowest_converged():
    S = substitution.SUB_STARTS
    r = {"sub_E": -5.0, "sub_converged": True, "sub_rescaled_E": -5.1, "sub_rescaled_converged": True}
    assert substitution.best_start(r, S) == "sub_rescaled"
    r["sub_rescaled_converged"] = False  # lower but unusable: the converged start wins
    assert substitution.best_start(r, S) == "sub"
    r["sub_converged"] = False  # nothing usable: no best start (an unusable result is never promoted)
    assert substitution.best_start(r, S) is None
    assert substitution.best_start({"sub_E": -1.0, "sub_converged": True}, S) == "sub"
    assert substitution.best_start({}, S) is None
    # the guard flag ('usable': converged AND physical) outranks the bare convergence flag
    assert substitution.best_start({"sub_E": -9e9, "sub_converged": True, "sub_usable": False,
                                    "sub_rescaled_E": -5.0, "sub_rescaled_usable": True}, S) == "sub_rescaled"


def test_add_best_counts_no_usable_start():
    r = {"sub_E_raw": -9e9, "sub_E": None, "sub_usable": False}
    substitution._add_best(r, substitution.SUB_STARTS, "sub_best")
    assert r["sub_best_start"] is None and r["sub_best_rejection"] == "no usable start" and r["sub_best_dE_mev"] is None
    r = {}
    substitution._add_best(r, substitution.SUB_STARTS, "sub_best")
    assert r["sub_best_rejection"] is None  # nothing ran at all: not a rejection


def test_add_best_copies_winning_start():
    r = {"sub_E": -5.0, "sub_converged": True, "sub_vol_pct": 9.0, "sub_match": False,
         "sub_rescaled_E": -5.2, "sub_rescaled_converged": True, "sub_rescaled_vol_pct": 0.4, "sub_rescaled_match": True}
    substitution._add_best(r, substitution.SUB_STARTS, "sub_best")
    assert r["sub_best_start"] == "sub_rescaled" and r["sub_best_n_starts"] == 2
    assert r["sub_best_vol_pct"] == 0.4 and r["sub_best_match"] is True


def test_structure_outcome_labels():
    assert substitution.outcome(True) == substitution.SAME
    assert substitution.outcome(False) == substitution.DIFFERENT
    assert substitution.outcome(None) is None and substitution.outcome(float("nan")) is None


# --- fallback ladder ---------------------------------------------------------------------------

def test_ladder_never_loosens_convergence_criteria():
    for _, s, _ in config.FALLBACK_LADDER:
        assert s.fmax == config.DEFAULT_RELAX.fmax
        assert s.max_stress_gpa == config.DEFAULT_RELAX.max_stress_gpa
    assert config.LADDER_BUDGET_S > sum(s.timeout_s for _, s, _ in config.FALLBACK_LADDER)


def _ladder_job():
    s = _diamond("Si", 5.47)
    return {"rung1": {"relaxed": s, "energy_per_atom": -5.0, "converged": False, "n_steps": 500, "wall_time_s": 9.0},
            "original": s, "seed": 1, "device": "cpu", "dtype": "float64"}


def _fake_relax(converge_on, seen):
    def fake(structure, settings, device, dtype, **kw):
        seen.append((settings.optimizer, structure))
        if settings.optimizer == "timeout":
            raise engine.RelaxTimeout("x")
        return engine.RelaxResult(structure=structure, energy_per_atom=-5.1, converged=settings.optimizer in converge_on,
                                  n_steps=10, fmax_final=0.001, max_stress_gpa=0.0, wall_time_s=0.1, min_distance_ratio=1.0)
    return fake


def test_ladder_stops_at_first_converged_rung(monkeypatch):
    seen = []
    monkeypatch.setattr(engine, "relax", _fake_relax({"FIRE"}, seen))
    out = jobs.ladder_job(_ladder_job())
    assert out["rung"] == "fire" and out["converged"] and len(out["ladder"]) == 1
    assert [o for o, _ in seen] == ["FIRE"]


def test_ladder_records_every_rung_when_nothing_converges(monkeypatch):
    seen = []
    monkeypatch.setattr(engine, "relax", _fake_relax(set(), seen))
    job = _ladder_job()
    out = jobs.ladder_job(job)
    assert out["rung"] is None and not out["converged"]
    assert [h["rung"] for h in out["ladder"]] == [name for name, _, _ in config.FALLBACK_LADDER]
    perturbed = seen[1][1]  # the restart begins from a rattled copy of the original, not the original
    assert (abs(perturbed.cart_coords - job["original"].cart_coords) > 1e-6).any()


def test_ladder_keeps_rung1_when_every_rung_times_out(monkeypatch):
    monkeypatch.setattr(config, "FALLBACK_LADDER", tuple((n, s.__class__(optimizer="timeout"), m)
                                                        for n, s, m in config.FALLBACK_LADDER))
    monkeypatch.setattr(engine, "relax", _fake_relax(set(), []))
    job = _ladder_job()
    out = jobs.ladder_job(job)
    assert out["rung"] is None and out["energy_per_atom"] == -5.0 and out["relaxed"] is job["rung1"]["relaxed"]
    assert all(h["error"].startswith("RelaxTimeout") for h in out["ladder"])


# --- mode (b) status, dispatch, snapshots --------------------------------------------------------

def test_mode_b_status():
    assert stability.b_status_of(set(), []) == "complete"
    assert stability.b_status_of({"mp-1"}, []).startswith("scored")
    assert stability.b_status_of({"mp-1"}, ["mp-1"]).startswith("not scored")


def test_metrics_count_unscored():
    import pandas as pd

    m = stability.metrics(pd.DataFrame({"ref_e_hull": [0.0, 0.1, 0.2], "b_e_hull": [0.0, math.nan, 0.2]}), "b")
    assert m["n"] == 2 and m["n_unscored"] == 1


def test_run_job_dispatch(monkeypatch):
    monkeypatch.setitem(jobs.JOB_FUNCTIONS, "static", lambda j: {"kind": "static"})
    monkeypatch.setitem(jobs.JOB_FUNCTIONS, "relax", lambda j: {"kind": "relax"})
    assert jobs.run_job({"job_fn": "static"}) == {"kind": "static"}
    assert jobs.run_job({}) == {"kind": "relax"}
    assert substitution.job_fn("static") == "static" and substitution.job_fn("sub_rescaled") == "relax"


@pytest.mark.parametrize("e,wbm,label", [(0.0, False, "≤0.025"), (0.025, False, "≤0.025"), (0.05, False, "0.025–0.1"),
                                         (0.3, False, "0.1–0.3"), (0.31, False, ">0.3"), (-0.01, True, "<0"),
                                         (0.0, True, "0–0.025"), (1.2, True, ">0.3"), (float("nan"), False, None)])
def test_hull_bins(e, wbm, label):
    assert compare.hull_bin(e, below_zero_bin=wbm) == label


def test_eta_schedule_is_longest_first_list_scheduling():
    from harness.phase0 import _counterpart, _schedule

    assert _schedule([10, 1, 1, 1], 2) == 10
    assert _schedule([4, 3, 3, 2], 2) == 6
    assert _schedule([], 3) == 0
    assert _counterpart("P:a->b:sub_rescaled@t") == "P:a->b:sub@t"
    assert _counterpart("P:a->b:sub_rattled_rescaled@t") == "P:a->b:sub_rattled@t"


def test_undetermined_symmetry_falls_back_to_volume_only(monkeypatch):
    from pymatgen.symmetry import analyzer

    def boom(*a, **k):
        raise analyzer.SymmetryUndeterminedError("Unable to determine symmetry")

    monkeypatch.setattr(analyzer.SpacegroupAnalyzer, "__init__", boom)
    s = _diamond("Si", 5.47)
    cell = compare.conventional_cell(s)
    assert cell.spacegroup == 0 and cell.crystal_system == "undetermined"
    lat = compare.compare_lattices(s, s)
    assert lat["same_spacegroup"] is False and lat["max_abs_lattice_pct_err"] is None
    assert lat["vol_per_atom_pct_err"] == pytest.approx(0.0)


def test_requeue_failed(tmp_path):
    from harness import jobqueue as q

    db = tmp_path / "q.sqlite"
    q.enqueue([{"suite": "s", "job_key": "k@t", "inputs": {}}], db)
    (row,) = q.claim(1, "r", db)
    q.finish(row["id"], "failed", db, error="SymmetryUndeterminedError: x", attempts=2)
    assert q.requeue_failed(db) == 1
    (row,) = q.claim(1, "r", db)
    assert row["attempts"] == 0 and row["error"].startswith("requeued after: SymmetryUndeterminedError")


def test_substitution_ladder_failure_keeps_rung1(tmp_path):
    s = _diamond("Si", 5.47)
    rung1 = {"pair_id": "P", "kind": "ctrl", "relaxed": s, "energy_per_atom": -1.0, "converged": False, "n_steps": 500,
             "wall_time_s": 1.0, "energy_mev_vs_mp": 5.0}
    job = {"job_fn": "ladder", "suite": "unit", "pair": {"pair_id": "P"}, "kind": "ctrl", "rung1": rung1,
           "rung1_rejection": "not converged", "job_key": "P:a->b:ctrl:ladder@t", "record_key": "P:a->b:ctrl@t"}
    with store.using(tmp_path / "db.sqlite"):
        substitution._record(job, {"status": "timeout", "error": "hard timeout"})
        pls = store.load_payloads("unit")
        book = store.load_payloads("unit", status="timeout")
    kept = pls["P:a->b:ctrl@t"]
    assert kept["energy_per_atom"] == -1.0 and kept["ladder"] == [] and kept["ladder_error"] == "hard timeout"
    assert book["P:a->b:ctrl:ladder@t"]["kind"] == "ladder"  # bookkeeping row keeps the job's status


def test_store_using_reads_another_database(tmp_path):
    db = tmp_path / "snap.sqlite"
    with store.using(db):
        store.record_job("unit", "k@tag", "ok", payload={"x": 1})
        assert store.completed_keys("unit") == {"k@tag"}
    with store.using(tmp_path / "other.sqlite"):
        assert store.completed_keys("unit") == set()


def test_phase0_report_refuses_to_rebuild_against_a_changed_pair_set(monkeypatch):
    """The before/after halves are both built against the CURRENT auto pair list, so rebuilding after
    the pair set is regenerated would compare two different samples."""
    import pytest

    from harness import phase0

    monkeypatch.setattr(phase0.store, "load_payloads", lambda *a, **k: {f"pair-{i}:x:sub@t": {} for i in range(100)})
    monkeypatch.setattr("harness.pairgen.load_pairs", lambda: [{"pair_id": f"pair-{i}"} for i in range(50)])
    with pytest.raises(RuntimeError, match="auto pair set has changed"):
        phase0._assert_pair_set_unchanged("t")

    monkeypatch.setattr("harness.pairgen.load_pairs", lambda: [{"pair_id": f"pair-{i}"} for i in range(100)])
    phase0._assert_pair_set_unchanged("t")  # unchanged: no error
