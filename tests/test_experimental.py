"""Experimental-check prototypes and reference table (offline)."""

import pytest

from harness import compare
from harness.suites import experimental as ex


def row(material, formula, structure, a, c=None, status="rt"):
    return {"material": material, "formula": formula, "structure": structure, "a_exp": a, "c_exp": c,
            "status": status, "note": ""}


@pytest.mark.parametrize("r,sg,natoms", [
    (row("Si", "Si", "di", 5.430), 227, 8),
    (row("GaAs", "GaAs", "zb", 5.648), 216, 8),
    (row("MgO", "MgO", "rs", 4.207), 225, 8),
    (row("AlN", "AlN", "wu", 3.111, 4.981), 186, 4),
])
def test_prototypes_have_right_symmetry_and_lattice(r, sg, natoms):
    s = ex.build(r)
    cell = compare.conventional_cell(s)
    assert cell.spacegroup == sg
    assert len(s) == natoms
    assert cell.a == pytest.approx(r["a_exp"], abs=1e-6)
    if r["c_exp"]:
        assert cell.c == pytest.approx(r["c_exp"], abs=1e-6)
    assert s.composition.reduced_formula == r["formula"] or s.composition.reduced_formula == "Si"


@pytest.mark.parametrize("r,sg,natoms", [(row("Cu", "Cu", "fcc", 3.595), 225, 4), (row("Na", "Na", "bcc", 4.210), 229, 2)])
def test_metal_prototypes(r, sg, natoms):
    s = ex.build(r)
    cell = compare.conventional_cell(s)
    assert cell.spacegroup == sg and len(s) == natoms and cell.a == pytest.approx(r["a_exp"], abs=1e-6)


def test_csonka_table_matches_source():
    rows = ex.load_csonka()
    assert len(rows) == 24  # Table II: 24 test solids
    assert sum(r["metal"] for r in rows) == 14 and all(r["status"] == "zpae_removed" for r in rows)
    by = {r["material"]: r for r in rows}
    assert by["Cu"]["a_exp"] == 3.595 and by["MgO"]["a_exp"] == 4.184  # printed Expt. - ZPAE values
    assert by["Sr"]["structure"] == "fcc" and by["Ba"]["structure"] == "bcc"


def test_zincblende_puts_cation_on_origin():
    s = ex.build(row("GaAs", "GaAs", "zb", 5.648))
    assert str(s[0].specie) == "Ga"  # less electronegative element at (0,0,0)


def test_wurtzite_requires_c():
    with pytest.raises(ValueError):
        ex.build(row("beta-GaN", "GaN", "wu", 4.523))


def test_reference_table_counts_match_source():
    rows = [r for r in ex.load_table() if r["citation"] == ex.CITATION]
    assert len(rows) == 40  # SC40
    by = {s: sum(r["status"] == s for r in rows) for s in ("rt", "zero_k", "ambiguous")}
    assert by == {"rt": 33, "zero_k": 6, "ambiguous": 1}
    assert {r["material"] for r in rows if r["status"] == "zero_k"} == {"Ge", "Si", "beta-SiC", "GaAs", "C", "MgO"}
    assert all(r["c_exp"] for r in rows if r["structure"] == "wu" and r["status"] != "ambiguous")
