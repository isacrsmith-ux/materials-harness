"""The oxide/halide split is a NEW calibration task: it must not reuse a single id or composition
that the original calibration / locked test set already spent."""

import hashlib
import json

import pandas as pd
import pytest

from harness import splits
from harness.confidence import family


METALS = ("Li", "Na", "K", "Rb", "Cs", "Mg", "Ca", "Sr", "Ba", "Zn",
          "Al", "Ga", "In", "Sn", "Pb", "Ti", "Zr", "Hf", "V", "Nb")


def _summary(n=1200):
    """A stand-in WBM summary: oxides, halides and intermetallics across the hull range, with enough
    distinct compositions that the locked-composition guard has something to leave behind."""
    rows = []
    for i in range(n):
        fam, m, k = i % 3, METALS[(i // 3) % len(METALS)], (i // (3 * len(METALS))) % 4 + 2
        f = f"{m}{k}O3" if fam == 0 else f"{m}{k}Cl5" if fam == 1 else f"{m}{k}Ni7"
        rows.append({"material_id": f"wbm-{i}", "formula": f, "unique_prototype": True,
                     "e_above_hull_mp2020_corrected_ppd_mp": (i % 40) / 100.0 - 0.05,
                     "uncorrected_energy_from_cse": -1.0, "n_sites": 4,
                     "e_form_per_atom_mp2020_corrected": -1.0, "e_correction_per_atom_mp2020": 0.0})
    return pd.DataFrame(rows)


def _prior(tmp_path, summary, cal_ids, test_ids):
    p = tmp_path / "wbm_split.json"
    p.write_text(json.dumps({
        "calibration": {"n": len(cal_ids), "ids": sorted(cal_ids)},
        "test": {"n": len(test_ids), "ids": sorted(test_ids), "locked": True,
                 "sha256": hashlib.sha256(",".join(sorted(test_ids)).encode()).hexdigest()}}))
    return p


def test_family_split_excludes_every_spent_id_and_locked_composition(tmp_path):
    s = _summary()
    spent_cal = [f"wbm-{i}" for i in range(0, 60)]
    spent_test = [f"wbm-{i}" for i in range(60, 120)]
    prior = _prior(tmp_path, s, spent_cal, spent_test)
    out = splits.make_family_split(s, sizes={"oxide": {"calibration": 20, "test": 10},
                                             "halide": {"calibration": 20, "test": 10}},
                                   path=tmp_path / "fam.json", prior_path=prior)
    spent = set(spent_cal) | set(spent_test)
    from pymatgen.core import Composition
    locked = {Composition(f).reduced_formula
              for f in s[s.material_id.isin(spent)].formula}
    assert out["dropped_sharing_locked_test_formula"] > 0, "composition guard never fired — test proves nothing"
    assert out["excluded_prior_ids"] == len(spent)
    for fam, d in out["families"].items():
        ids = set(d["calibration"]["ids"]) | set(d["test"]["ids"])
        assert not ids & spent, f"{fam} reused a spent id"
        assert not set(d["calibration"]["ids"]) & set(d["test"]["ids"])
        drawn = s[s.material_id.isin(ids)]
        assert {family(f) for f in drawn.formula} == {fam}, f"{fam} drew another family's chemistry"
        assert not {Composition(f).reduced_formula for f in drawn.formula} & locked, \
            f"{fam} drew a composition the locked test set already holds"


def test_family_test_ids_are_locked_and_hash_checked(tmp_path):
    s = _summary()
    prior = _prior(tmp_path, s, [f"wbm-{i}" for i in range(0, 60)], [f"wbm-{i}" for i in range(60, 120)])
    p = tmp_path / "fam.json"
    out = splits.make_family_split(s, sizes={"oxide": {"calibration": 20, "test": 10},
                                             "halide": {"calibration": 20, "test": 10}},
                                   path=p, prior_path=prior)
    with pytest.raises(PermissionError):
        splits.family_test_ids("oxide", path=p)
    assert splits.family_test_ids("oxide", unlock=True, path=p) == out["families"]["oxide"]["test"]["ids"]

    d = json.loads(p.read_text())
    d["families"]["oxide"]["test"]["ids"].append("wbm-tampered")
    p.write_text(json.dumps(d))
    with pytest.raises(RuntimeError):
        splits.family_test_ids("oxide", unlock=True, path=p)


def test_made_once(tmp_path):
    s = _summary()
    prior = _prior(tmp_path, s, [f"wbm-{i}" for i in range(0, 60)], [f"wbm-{i}" for i in range(60, 120)])
    kw = {"sizes": {"oxide": {"calibration": 20, "test": 10}, "halide": {"calibration": 20, "test": 10}},
          "path": tmp_path / "fam.json", "prior_path": prior}
    splits.make_family_split(s, **kw)
    with pytest.raises(splits.SplitExists):
        splits.make_family_split(s, **kw)


def test_tampered_prior_hash_is_refused(tmp_path):
    s = _summary()
    prior = _prior(tmp_path, s, [f"wbm-{i}" for i in range(0, 60)], [f"wbm-{i}" for i in range(60, 120)])
    d = json.loads(prior.read_text())
    d["test"]["ids"] = d["test"]["ids"][:-1]  # shrinking the exclusion set must not go unnoticed
    prior.write_text(json.dumps(d))
    with pytest.raises(RuntimeError):
        splits.make_family_split(s, path=tmp_path / "fam.json", prior_path=prior)
