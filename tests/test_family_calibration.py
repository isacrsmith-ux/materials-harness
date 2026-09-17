"""Guards on the oxide/halide calibration queue.

Two failure modes this file exists to prevent, both silent:

1. A locked test id reaching the relaxation queue. splits.py is explicit that relaxing or scoring
   a test id before the final evaluation is a bug, not a shortcut — but nothing enforced it for the
   per-family split, whose four locked halves are new.
2. A reused structure-cache filename. ood.load_structures returns its cache file wholesale and
   ignores the `ids` argument whenever that file exists, so pointing the 7,500 family ids at the
   original calibration_init_structs.json returns the original 4,000 structures, warns at WARNING
   level, and enqueues nothing. That looks exactly like success.
"""

from __future__ import annotations

import json

import pytest

from harness import orchestrator, splits


@pytest.fixture(scope="module")
def family_ids() -> list[str]:
    return splits.family_calibration_ids("oxide") + splits.family_calibration_ids("halide")


# ------------------------------------------------------------------ the split's own invariants

def test_family_calibration_is_7500_unique_ids(family_ids):
    assert len(family_ids) == 7500
    assert len(set(family_ids)) == 7500


def test_family_test_ids_stay_locked():
    for fam in ("oxide", "halide"):
        with pytest.raises(PermissionError):
            splits.family_test_ids(fam)


def test_family_excluded_ids_returns_all_4000_locked_test_ids():
    """The exclusion accessor must see every locked id, or it cannot protect them."""
    locked = splits.family_excluded_ids()
    assert len(locked) == 4000


def test_family_excluded_ids_verifies_the_hash(tmp_path, monkeypatch):
    """A tampered split must not be able to quietly shrink the exclusion set."""
    split = json.loads(splits.FAMILY_SPLIT_FILE.read_text())
    split["families"]["oxide"]["test"]["ids"] = split["families"]["oxide"]["test"]["ids"][:10]
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(split))
    with pytest.raises(RuntimeError, match="do not match their recorded hash"):
        splits.family_excluded_ids(path=path)


def test_calibration_is_disjoint_from_every_locked_half(family_ids):
    """The original WBM test set, the original calibration, and both family test sets."""
    locked = splits.excluded_ids() | splits.family_excluded_ids()
    assert not (set(family_ids) & locked)


# ------------------------------------------------------------------------- the queueing guards

def test_refuses_to_queue_a_locked_test_id(monkeypatch, family_ids):
    """Inject one locked id into the calibration list; nothing may be enqueued."""
    locked_id = sorted(splits.family_excluded_ids())[0]
    monkeypatch.setattr(
        splits, "family_calibration_ids",
        lambda fam, *a, **k: ([locked_id] if fam == "oxide" else []),
    )
    with pytest.raises(RuntimeError, match="locked test or prior-split ids"):
        orchestrator.build_family_calibration_jobs({}, families=("oxide", "halide"))


def test_refuses_duplicate_ids(monkeypatch):
    monkeypatch.setattr(splits, "family_calibration_ids", lambda fam, *a, **k: ["wbm-1-10002"])
    with pytest.raises(RuntimeError, match="duplicates"):
        orchestrator.build_family_calibration_jobs({}, families=("oxide", "halide"))


def test_strict_mode_catches_a_reused_cache_filename(tmp_path, monkeypatch):
    """The exact hazard: a populated cache file for a DIFFERENT id set. Without strict this is a
    warning and an empty queue; with strict it is an error naming the cause."""
    from pymatgen.core import Lattice, Structure

    from harness.suites import ood

    # A real structure, stored under an id nobody asked for: exactly what the original
    # calibration cache looks like to a request for the family ids.
    other = Structure(Lattice.cubic(4.2), ["Mg", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    cache = tmp_path / "already_populated.json"
    cache.write_text(json.dumps({"wbm-1-99999": other.as_dict()}))

    monkeypatch.setattr(orchestrator, "_settings", lambda compute: ("tag", {}))
    monkeypatch.setattr(ood, "load_entries", lambda ids, cache_file=None: {})
    with pytest.raises(RuntimeError, match="cache filename was reused"):
        orchestrator.build_wbm_calibration_jobs(
            {}, ids=["wbm-1-10002", "wbm-1-10009"], init_cache=cache, cse_cache=cache, strict=True
        )


def test_family_caches_are_not_the_original_calibration_caches():
    """Distinct filenames are the whole mitigation; a rename that collides would restore the bug."""
    assert orchestrator.FAMILY_INIT_CACHE != "calibration_init_structs.json"
    assert orchestrator.FAMILY_CSE_CACHE != "calibration_cse.json"


def test_original_calibration_path_is_unchanged(monkeypatch):
    """Parameterising build_wbm_calibration_jobs must not have moved the original default."""
    seen = {}

    from harness.suites import ood

    def fake_structs(ids, cache_file=None):
        seen["init"] = cache_file
        seen["ids"] = ids
        return {}

    monkeypatch.setattr(orchestrator, "_settings", lambda compute: ("tag", {}))
    monkeypatch.setattr(ood, "load_structures", fake_structs)
    monkeypatch.setattr(ood, "load_entries", lambda ids, cache_file=None: {})
    orchestrator.build_wbm_calibration_jobs({})
    assert seen["init"].name == "calibration_init_structs.json"
    assert seen["ids"] == splits.calibration_ids()
