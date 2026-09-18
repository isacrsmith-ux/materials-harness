"""Tests for the reference-data loader.

The point of the loader is that a wrong number cannot get in quietly, so the tests are
mostly about what it REJECTS. The live-table tests check invariants the source states
about itself, so they fail if an extraction silently changes.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import loader  # noqa: E402
from loader import ReferenceDataError  # noqa: E402


# --------------------------------------------------------------------------- fixtures

SCHEMA = {
    "si_units": {"length_m": "m"},
    "unit_pairs": [["length_m", "length_original_cm", "original_units", 0.01]],
    "required": ["material_key", "length_m", "source_key", "status"],
    "properties": {
        "material_key": {"type": "string", "minLength": 1},
        "length_m": {"type": ["number", "null"], "exclusiveMinimum": 0},
        "length_original_cm": {"type": ["string", "null"]},
        "original_units": {"type": ["string", "null"], "enum": ["cm"]},
        "source_key": {"type": "string", "minLength": 1},
        "status": {"type": "string", "enum": ["verified", "unverified", "disputed"]},
    },
}

GOOD = {
    "material_key": "x",
    "length_m": "0.05",
    "length_original_cm": "5.0",
    "original_units": "cm",
    "source_key": "a_source",
    "status": "verified",
}


@pytest.fixture
def table(tmp_path, monkeypatch):
    """Write a throwaway table + schema and point the loader at it."""

    def build(rows, schema=None):
        (tmp_path / "schema").mkdir(exist_ok=True)
        (tmp_path / "schema" / "t.json").write_text(json.dumps(schema or SCHEMA))
        with (tmp_path / "t.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        monkeypatch.setattr(loader, "DIR", tmp_path)
        monkeypatch.setattr(loader, "SCHEMA_DIR", tmp_path / "schema")
        monkeypatch.setattr(loader, "source_keys", lambda: {"a_source"})
        return tmp_path

    return build


# ------------------------------------------------------------------------ unit safety

def test_accepts_consistent_units(table):
    table([GOOD])
    assert loader.load("t")[0]["length_m"] == 0.05


def test_rejects_value_left_in_source_units(table):
    """The failure this whole loader exists to prevent: 5.0 cm stored as 5.0 m."""
    table([{**GOOD, "length_m": "5.0"}])
    with pytest.raises(ReferenceDataError, match="Unit mixing"):
        loader.load("t")


def test_rejects_si_edited_without_original(table):
    table([{**GOOD, "length_m": "0.07"}])
    with pytest.raises(ReferenceDataError, match="Unit mixing"):
        loader.load("t")


def test_rejects_missing_units_column(table):
    table([{**GOOD, "original_units": ""}])
    with pytest.raises(ReferenceDataError, match="original_units is empty"):
        loader.load("t")


def test_rejects_half_present_pair(table):
    """An optional value present in source units but missing its SI counterpart (or the
    reverse) is a half-converted row. Uses a schema where the pair is optional, so the
    required-column check does not mask the unit check."""
    optional = {**SCHEMA, "required": ["material_key", "source_key", "status"]}
    table([{**GOOD, "length_m": "", "length_original_cm": "5.0"}], schema=optional)
    with pytest.raises(ReferenceDataError, match="present or absent together"):
        loader.load("t")


def test_unit_check_tolerates_bound_markers(table):
    """'> 5.0' is a lower bound; the marker must not break the arithmetic check."""
    table([{**GOOD, "length_original_cm": "> 5.0"}])
    assert loader.load("t")[0]["length_m"] == 0.05


# ----------------------------------------------------------------------- schema rules

def test_rejects_unknown_column(table):
    table([{**GOOD, "smuggled": "1"}])
    with pytest.raises(ReferenceDataError, match="not in the schema"):
        loader.load("t")


def test_rejects_bad_enum(table):
    table([{**GOOD, "status": "probably fine"}])
    with pytest.raises(ReferenceDataError, match="not in"):
        loader.load("t")


def test_rejects_empty_required_value(table):
    table([{**GOOD, "length_m": "", "length_original_cm": ""}])
    with pytest.raises(ReferenceDataError, match="required column length_m is empty"):
        loader.load("t")


def test_rejects_non_numeric(table):
    table([{**GOOD, "length_m": "about five"}])
    with pytest.raises(ReferenceDataError, match="expected a number"):
        loader.load("t")


def test_rejects_negative_where_forbidden(table):
    table([{**GOOD, "length_m": "-0.05", "length_original_cm": "-5.0"}])
    with pytest.raises(ReferenceDataError, match="<= 0"):
        loader.load("t")


# ------------------------------------------------------------------------- provenance

def test_rejects_unknown_source_key(table, monkeypatch):
    table([{**GOOD, "source_key": "invented"}])
    monkeypatch.setattr(loader, "source_keys", lambda: {"a_source"})
    with pytest.raises(ReferenceDataError, match="no entry in SOURCES.md"):
        loader.load("t")


def test_every_source_key_in_shipped_tables_is_documented():
    documented = loader.source_keys()
    assert documented, "SOURCES.md defines no source keys"
    for name in loader.tables():
        for row in loader.load(name, check_sources=False):
            if "source_key" not in row:
                continue  # derived key table; provenance lives in the property tables
            assert row["source_key"] in documented, f"{name}: {row['source_key']} undocumented"


# ----------------------------------------------------------------- the shipped tables

def test_all_shipped_tables_validate():
    assert loader.tables(), "no tables present"
    for name in loader.tables():
        assert loader.load(name), f"{name} is empty"


def test_misse_matches_what_the_report_says_about_itself():
    """NASA/TM-2006-214482 states 41 samples and 'partial or complete erosion of 6 of the
    41'. If a parser change breaks either count, the extraction is wrong."""
    rows = loader.load("space_ao_erosion")
    assert len(rows) == 41
    assert sum(r["is_lower_bound"] for r in rows) == 6
    assert sum(r["is_fluence_witness"] for r in rows) == 2


def test_lower_bounds_kept_as_flags_not_folded_into_values():
    rows = loader.load("space_ao_erosion")
    for r in rows:
        assert not str(r["erosion_yield_original"]).startswith(">"), (
            "the '>' marker belongs in is_lower_bound, and the numeric column must stay numeric"
        )
        if r["is_lower_bound"]:
            assert r["erosion_yield_m3_per_atom"] > 0


def test_witness_samples_are_flagged_as_circular():
    """The Kapton H rows define the fluence; using them as validation targets is circular,
    so they must carry both the flag and an explanation."""
    rows = loader.load("space_ao_erosion")
    witness = [r for r in rows if r["is_fluence_witness"]]
    assert {r["sample_id"] for r in witness} == {"2-E5-30", "2-E5-33"}
    for r in witness:
        assert "calibration" in (r["note"] or "").lower()


# ---------------------------------------------------------- lattice constants (oxides)

def test_lattice_constants_never_invent_a_temperature():
    """The table is 'room temperature', but most crystallographic sources state no
    temperature at all. Those rows must say so, not carry an assumed 293 K."""
    rows = loader.load("lattice_constants")
    for r in rows:
        if r["temperature_status"] == "not_stated_in_source":
            assert r["temperature_k"] is None, (
                f"cod-{r['cod_id']}: temperature present but the source states none"
            )
        else:
            assert r["temperature_k"] is not None


def test_lattice_constants_every_row_has_a_stated_uncertainty():
    for r in loader.load("lattice_constants"):
        unc = float(r["a_uncertainty_angstrom"])
        assert unc > 0, f"cod-{r['cod_id']}: uncertainty must be positive"


def test_lattice_constants_each_row_cites_its_own_paper():
    """COD is the aggregator; the citation that matters is the original determination."""
    for r in loader.load("lattice_constants"):
        assert r["doi"].startswith("10."), f"cod-{r['cod_id']}: {r['doi']!r} is not a DOI"


def test_quality_flags_match_the_stated_uncertainties():
    for r in loader.load("lattice_constants"):
        rel = float(r["a_uncertainty_angstrom"]) / float(r["a_original_angstrom"])
        expected = (
            "low_precision" if rel > 1e-3
            else "implausible_precision" if rel < 1e-6
            else "ok"
        )
        assert r["quality_flag"] == expected, f"cod-{r['cod_id']}: flag disagrees with uncertainty"


def test_no_parametric_series_survived_filtering():
    """A single paper contributing 3+ determinations of one phase whose cell walks across
    them is a pressure or temperature scan, and must have been rejected."""
    import statistics as st
    from collections import defaultdict

    groups = defaultdict(list)
    for r in loader.load("lattice_constants"):
        groups[(r["formula"], r["space_group"], r["doi"])].append(r)
    for key, members in groups.items():
        if len(members) < 3:
            continue
        a = [float(m["a_original_angstrom"]) for m in members]
        spread = (max(a) - min(a)) / st.mean(a) * 1e6
        assert spread <= 1000, f"{key}: {len(members)} entries spanning {spread:.0f} ppm"


def test_phase_grouping_uses_cell_setting():
    """Corundum in the rhombohedral setting (a=5.12, alpha=55.28) and the hexagonal setting
    (a=4.75) are one phase in two conventions. Grouping on the space group NUMBER alone
    would compare their lattice constants and report a ~76000 ppm false disagreement, so
    the setting suffix must be part of the key."""
    import statistics as st
    from collections import defaultdict

    rows = [r for r in loader.load("lattice_constants") if r["quality_flag"] == "ok"]

    by_setting = defaultdict(list)
    for r in rows:
        by_setting[(r["formula"], r["space_group"])].append(r)
    for key, members in by_setting.items():
        if len(members) < 2:
            continue
        a = [float(m["a_original_angstrom"]) for m in members]
        spread = (max(a) - min(a)) / st.mean(a) * 1e6
        assert spread < 5000, (
            f"{key}: {spread:.0f} ppm between determinations of one phase in one setting - "
            "either a contaminated row survived filtering, or the grouping key is wrong"
        )


def test_materials_table_keys_are_unique_and_join():
    """materials.csv is the shared key table: duplicate keys would silently fan out a join."""
    import csv as _csv

    path = loader.DIR / "materials.csv"
    rows = list(_csv.DictReader(path.open()))
    keys = [r["material_key"] for r in rows]
    assert len(keys) == len(set(keys)), "duplicate material_key in materials.csv"

    phases = {(r["formula"], r["space_group"]) for r in loader.load("lattice_constants")}
    covered = {(r["formula"], r["space_group"]) for r in rows}
    assert phases == covered, f"materials.csv misses {phases - covered}"
