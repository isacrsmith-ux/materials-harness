"""Unit tests for pair-curation helpers (no network)."""

import csv

from harness import curation


def test_parse_mapping_single_and_double():
    assert curation.parse_mapping("Si:Ge") == {"Si": "Ge"}
    assert curation.parse_mapping("Si:B;C:N") == {"Si": "B", "C": "N"}
    assert curation.parse_mapping(" Ca:Ce ; F:O ;") == {"Ca": "Ce", "F": "O"}


def test_is_space_relevant():
    for f in ["Al2O3", "SiC", "AlN", "GaN", "TiO2", "LiF", "MgF2", "ZrC"]:
        assert curation.is_space_relevant(f), f
    for f in ["Ge", "C", "GaAs", "KCl", "ZnSe"]:
        assert not curation.is_space_relevant(f), f


def test_candidate_file_is_well_formed():
    with curation.CANDIDATES.open() as fh:
        rows = list(csv.DictReader(fh))
    assert 30 <= len(rows) <= 50
    families = {r["family"] for r in rows}
    for fam in ["rocksalt", "zincblende", "wurtzite", "fluorite", "perovskite", "spinel", "corundum"]:
        assert fam in families
    assert any(f.startswith("elemental") for f in families)
    assert len({(r["parent"], r["target"]) for r in rows}) == len(rows), "duplicate pairs"
    space = sum(curation.is_space_relevant(r["target"]) for r in rows)
    assert space >= len(rows) / 3
