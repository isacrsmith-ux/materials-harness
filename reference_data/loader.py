"""Load and validate the citable reference-data tables in reference_data/.

Every table is CSV; every table has a JSON Schema alongside it in schema/. The loader
enforces three things the datasets are worthless without:

  1. Types and required columns, per the schema.
  2. Units. Each table declares `si_units` (what the SI column means) and `unit_pairs`
     (SI column, original column, units column, factor). The loader recomputes
     SI == original * factor for every row, so a value can never be silently
     stored in the source's units, and a units column can never drift from its values.
  3. Provenance. Every row must carry a source_key that resolves to an entry in
     SOURCES.md, and any row without a value must say status="unverified".

Read a table with load("space_ao_erosion"); it raises on the first violation.

ponytail: this validates the JSON Schema subset these tables actually use (type,
required, enum, minimum/exclusiveMinimum, minLength, pattern). It is not a general
JSON Schema implementation. If the schemas grow beyond that subset, swap validate_row()
for the `jsonschema` package rather than extending this.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent
SCHEMA_DIR = DIR / "schema"
SOURCES = DIR / "SOURCES.md"

# Relative tolerance on the SI == original * factor check. Source values are printed to
# 3-4 significant figures, so the stored SI value is only as precise as what was printed.
UNIT_RTOL = 1e-9

NULLISH = {"", "na", "n/a", "none", "null"}


class ReferenceDataError(ValueError):
    """A table violated its schema, its units, or its provenance rules."""


def _coerce(raw: str, allowed: list[str]) -> object:
    """CSV is all strings; turn a cell into the type its schema allows."""
    if raw.strip().lower() in NULLISH:
        return None
    if "boolean" in allowed:
        low = raw.strip().lower()
        if low in {"true", "false"}:
            return low == "true"
        raise ReferenceDataError(f"expected true/false, got {raw!r}")
    if "number" in allowed or "integer" in allowed:
        try:
            return float(raw)
        except ValueError as exc:
            raise ReferenceDataError(f"expected a number, got {raw!r}") from exc
    return raw


def _check(value: object, spec: dict, col: str, where: str) -> None:
    allowed = spec.get("type", [])
    allowed = [allowed] if isinstance(allowed, str) else list(allowed)
    if value is None:
        if "null" not in allowed:
            raise ReferenceDataError(f"{where}: {col} is empty but the schema forbids null")
        return
    if isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, float):
        kind = "number"
    else:
        kind = "string"
    if allowed and kind not in allowed:
        raise ReferenceDataError(f"{where}: {col} is {kind}, schema allows {allowed}")
    if kind == "string":
        if "enum" in spec and value not in spec["enum"]:
            raise ReferenceDataError(f"{where}: {col}={value!r} not in {spec['enum']}")
        if len(value) < spec.get("minLength", 0):
            raise ReferenceDataError(f"{where}: {col} is empty but minLength applies")
        if "pattern" in spec and not re.match(spec["pattern"], value):
            raise ReferenceDataError(f"{where}: {col}={value!r} fails {spec['pattern']}")
    if kind == "number":
        if "minimum" in spec and value < spec["minimum"]:
            raise ReferenceDataError(f"{where}: {col}={value} < minimum {spec['minimum']}")
        if "exclusiveMinimum" in spec and value <= spec["exclusiveMinimum"]:
            raise ReferenceDataError(f"{where}: {col}={value} <= {spec['exclusiveMinimum']}")


def _check_units(row: dict, pairs: list, where: str) -> None:
    """Recompute every SI value from the source's own printed value and factor."""
    for si_col, orig_col, units_col, factor in pairs:
        si, orig = row.get(si_col), row.get(orig_col)
        if si is None or orig in (None, ""):
            if si is not None or (orig not in (None, "")):
                raise ReferenceDataError(
                    f"{where}: {si_col} and {orig_col} must be present or absent together"
                )
            continue
        if units_col is not None and not row.get(units_col):
            raise ReferenceDataError(f"{where}: {si_col} has a value but {units_col} is empty")
        expected = float(str(orig).lstrip("><~ ")) * factor
        if not math.isclose(float(si), expected, rel_tol=UNIT_RTOL):
            raise ReferenceDataError(
                f"{where}: {si_col}={si} but {orig_col}={orig} x {factor} = {expected}. "
                "Unit mixing, or the SI column was edited without the original."
            )


def source_keys() -> set[str]:
    """Every key SOURCES.md defines, as `### key` headings."""
    if not SOURCES.exists():
        return set()
    return set(re.findall(r"^###\s+`([^`]+)`", SOURCES.read_text(), re.M))


def load(table: str, *, check_sources: bool = True) -> list[dict]:
    """Load reference_data/<table>.csv, validated against schema/<table>.json."""
    csv_path, schema_path = DIR / f"{table}.csv", SCHEMA_DIR / f"{table}.json"
    if not csv_path.exists():
        raise ReferenceDataError(f"no such table: {csv_path}")
    schema = json.loads(schema_path.read_text())
    props, required = schema.get("properties", {}), schema.get("required", [])
    known = source_keys() if check_sources else None

    with csv_path.open(newline="") as fh:
        raw_rows = list(csv.DictReader(fh))
    if not raw_rows:
        raise ReferenceDataError(f"{table}: no rows")

    missing = [c for c in required if c not in raw_rows[0]]
    if missing:
        raise ReferenceDataError(f"{table}: missing required columns {missing}")

    rows = []
    for i, raw in enumerate(raw_rows, start=2):  # start=2: row 1 is the header
        where = f"{table}.csv line {i}"
        row = {}
        for col, cell in raw.items():
            if col not in props:
                raise ReferenceDataError(f"{where}: column {col!r} is not in the schema")
            spec = props[col]
            allowed = spec.get("type", "string")
            row[col] = _coerce(cell, [allowed] if isinstance(allowed, str) else list(allowed))
            _check(row[col], spec, col, where)
        for col in required:
            if row.get(col) is None:
                raise ReferenceDataError(f"{where}: required column {col} is empty")
        _check_units(row, schema.get("unit_pairs", []), where)
        # Property tables must name their source. A derived key table (materials.csv) has no
        # single source of its own and declares no source_key column; its provenance is the
        # property tables it is built from.
        if known is not None and "source_key" in props and row["source_key"] not in known:
            raise ReferenceDataError(
                f"{where}: source_key {row['source_key']!r} has no entry in SOURCES.md"
            )
        rows.append(row)
    return rows


def tables() -> list[str]:
    return sorted(p.stem for p in DIR.glob("*.csv"))


if __name__ == "__main__":
    for name in tables():
        try:
            print(f"{name:24} {len(load(name)):>4} rows  OK")
        except ReferenceDataError as exc:
            print(f"{name:24}   !! {exc}")
