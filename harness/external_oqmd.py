"""OQMD as an external validation source: normalisation, filters and family assignment.

Modelled on `harness/unseen.py`. The source is the pinned OQMD v1.8 bulk MySQL dump (CC BY 4.0), read
by streaming its INSERT statements; no MySQL server is involved. Nothing here is redistributed: every
file this module writes lives under cache/external/oqmd/ (gitignored). What the campaign commits is
ids, hashes, provenance and aggregates.

One ENTRY is one OQMD material. Its label is the formation energy row of OQMD's 'standard' fit for the
entry's own calculation: `delta_e` (formation energy, eV/atom) and `stability` (hull distance, eV/atom,
negative = below the hull of the other phases). Its structure is that calculation's OUTPUT structure.

Filters (every one counted, see `filters`):
  converged     the labelled calculation reports converged = 1
  ordered       every site occupancy is 1 (no partial occupancy)
  max_atoms     natoms <= MAX_ATOMS (40, the harness's cap)
  labelled      delta_e and stability both present
Family: `confidence.family` with its existing precedence. No taxonomy change.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterator

from harness.config import ROOT

OQMD_DIR = ROOT / "cache" / "external" / "oqmd"
DUMP = OQMD_DIR / "qmdb__v1_8__022026.sql.gz"
MAX_ATOMS = 40
SOURCE = "OQMD v1.8 (February 2026) bulk dump, oqmd.org/download, CC BY 4.0"

_CREATE = re.compile(r"^CREATE TABLE `(\w+)`")
_COLUMN = re.compile(r"^\s+`(\w+)`\s")
_TOKEN = re.compile(r"'((?:[^'\\]|\\.)*)'|(NULL)|([^,()']+)|(\()|(\))")
_UNESC = re.compile(r"\\(.)")
_ESC = {"n": "\n", "t": "\t", "r": "\r", "0": "\0"}


def unescape(s: str) -> str:
    return _UNESC.sub(lambda m: _ESC.get(m.group(1), m.group(1)), s)


def stream(path: Path = DUMP) -> Iterator[str]:
    """Decompressed lines of the dump. gzip runs in its own process, so decompression and parsing
    overlap on two cores."""
    p = subprocess.Popen(["gzip", "-dc", str(path)], stdout=subprocess.PIPE, bufsize=1 << 24)
    try:
        for raw in p.stdout:
            yield raw.decode("latin-1")
    finally:
        p.stdout.close()
        p.wait()


def parse_values(line: str) -> Iterator[list]:
    """Rows of one `INSERT INTO t VALUES (...),(...);` line, as lists of str | None. Strings are
    unescaped; numbers are returned as their text (the caller converts what it keeps)."""
    body = line[line.index(" VALUES ") + 8:]
    row: list | None = None
    for m in _TOKEN.finditer(body):
        s, null, bare, op, cl = m.groups()
        if op:
            row = []
        elif cl:
            if row is not None:
                yield row
            row = None
        elif row is not None:
            if s is not None:
                row.append(unescape(s) if "\\" in s else s)
            elif null:
                row.append(None)
            else:
                row.append(bare.strip())


def table_of(line: str) -> str | None:
    if line.startswith("INSERT INTO `"):
        return line[13:line.index("`", 13)]
    return None


def schema(lines: Iterator[str]) -> Iterator[tuple[str, list[str]]]:
    """(table, column names) from CREATE TABLE blocks as they stream past."""
    table, cols = None, []
    for line in lines:
        m = _CREATE.match(line)
        if m:
            table, cols = m.group(1), []
            continue
        if table is None:
            continue
        c = _COLUMN.match(line)
        if c:
            cols.append(c.group(1))
        elif line.startswith(")"):
            yield table, cols
            table = None


# --- the two streaming passes ---------------------------------------------------------------------
#
# mysqldump writes tables alphabetically, so `atoms` streams before `structures` and before we know
# which structures matter. Pass 1 reads calculations -> formation_energies -> structures (the needed
# output structures only); pass 2 reads the atoms of exactly those structures.

PASS1 = OQMD_DIR / "pass1.pkl"
PASS2 = OQMD_DIR / "atoms.pkl"
WANT = {
    "calculations": ["id", "label", "entry_id", "output_id", "settings", "energy_pa", "converged", "natoms"],
    "calculations_hubbard_set": ["calculation_id", "hubbard_id"],
    "calculations_potential_set": ["calculation_id", "potential_id"],
    "hubbards": ["id", "element_id", "u", "l", "convention"],
    "potentials": ["id", "name", "xc", "paw", "us"],
    "entries": ["id", "duplicate_of_id", "natoms", "label"],
    "formation_energies": ["id", "entry_id", "calculation_id", "fit_id", "delta_e", "stability"],
    "structures": ["id", "natoms", "x1", "x2", "x3", "y1", "y2", "y3", "z1", "z2", "z3"],
}
FIT = "standard"


_XC = re.compile(r"'xc': '([^']*)'")
_POT = re.compile(r"'name': '([^']*)'")
_KEY = {k: re.compile(rf"'{k}': ([^,}}]+)") for k in ("encut", "ispin", "ldau", "ismear")}
_LDAUU = re.compile(r"'ldauu': \[([^\]]*)\]")


def settings_summary(text: str) -> str:
    """A compact, deduplicable summary of one calculation's VASP settings: functional(s), PAW
    potentials, cutoff, spin, +U values, smearing. The full text is ~1 kB and nearly unique per
    calculation (it carries nbands), so storing it for 5.8M calculations would cost gigabytes."""
    xc = sorted(set(_XC.findall(text)))
    pots = sorted(set(_POT.findall(text)))
    kv = {k: (m.group(1).strip().strip("'") if (m := r.search(text)) else None) for k, r in _KEY.items()}
    u = _LDAUU.search(text)
    return (f"xc={'/'.join(xc) or '?'};pots={','.join(pots)};encut={kv['encut']};ispin={kv['ispin']};"
            f"ldau={kv['ldau']};ldauu=[{u.group(1).strip() if u else ''}];ismear={kv['ismear']}")


def _f(x):
    return None if x is None else float(x)


def _i(x):
    return None if x is None else int(x)


def pass1(path: Path = DUMP, log=print) -> dict:
    """Everything except atoms. Keeps only compact columns; calculation settings are deduplicated."""
    cols: dict[str, list[str]] = {}
    cur_table, cur_cols = None, []
    calc: dict[int, tuple] = {}
    settings_ix: dict[str, int] = {}
    hub_of: dict[int, list] = {}
    pot_of: dict[int, list] = {}
    hubbards, potentials, entries, fes = {}, {}, {}, []
    need_structs: set[int] | None = None
    structs: dict[int, tuple] = {}
    n_lines = 0
    for line in stream(path):
        m = _CREATE.match(line)
        if m:
            cur_table, cur_cols = m.group(1), []
            continue
        if cur_table is not None:
            c = _COLUMN.match(line)
            if c:
                cur_cols.append(c.group(1))
                continue
            if line.startswith(")"):
                cols[cur_table] = cur_cols
                cur_table = None
                continue
        t = table_of(line)
        if t not in WANT:
            continue
        n_lines += 1
        ix = [cols[t].index(k) for k in WANT[t]]
        if t == "structures" and need_structs is None:
            # formation_energies has streamed: pick each entry's representative calculation now
            need_structs = {calc[c][2] for c in _representatives(fes, calc, entries).values()
                            if c in calc and calc[c][2] is not None}
            log(f"structures needed: {len(need_structs):,}")
        for r in parse_values(line):
            v = [r[i] for i in ix]
            if t == "calculations":
                sid = settings_ix.setdefault(settings_summary(v[4] or ""), len(settings_ix))
                # (label, entry_id, output_id, settings_id, energy_pa, converged, natoms)
                calc[int(v[0])] = (v[1], _i(v[2]), _i(v[3]), sid, _f(v[5]), _i(v[6]), _i(v[7]))
            elif t == "calculations_hubbard_set":
                hub_of.setdefault(int(v[0]), []).append(int(v[1]))
            elif t == "calculations_potential_set":
                pot_of.setdefault(int(v[0]), []).append(int(v[1]))
            elif t == "hubbards":
                hubbards[int(v[0])] = (v[1], _f(v[2]), _i(v[3]), v[4])
            elif t == "potentials":
                potentials[int(v[0])] = (v[1], v[2], v[3], v[4])
            elif t == "entries":
                entries[int(v[0])] = (_i(v[1]), _i(v[2]), v[3])
            elif t == "formation_energies":
                if v[3] == FIT:
                    fes.append((_i(v[1]), _i(v[2]), _f(v[4]), _f(v[5])))
            elif t == "structures":
                sid = int(v[0])
                if sid in need_structs:
                    structs[sid] = (_i(v[1]), *(float(x) for x in v[2:11]))
        if n_lines % 500 == 0:
            log(f"{n_lines:,} INSERT lines parsed (at {t})")
    return {"columns": cols, "calc": calc, "settings": list(settings_ix), "hub_of": hub_of,
            "pot_of": pot_of, "hubbards": hubbards, "potentials": potentials, "entries": entries,
            "fes": fes, "structs": structs}


def _representatives(fes: list, calc: dict, entries: dict) -> dict[int, int]:
    """entry_id -> calculation_id, qmpy's own rule: the standard-fit formation energy with the lowest
    delta_e (Entry.energy), among rows that carry a stability. Duplicate entries are dropped."""
    best: dict[int, tuple] = {}
    for entry_id, calc_id, de, stab in fes:
        if entry_id is None or de is None or stab is None:
            continue
        e = entries.get(entry_id)
        if e is not None and e[0] not in (None, entry_id):
            continue                                   # a duplicate_of another entry
        if entry_id not in best or de < best[entry_id][0]:
            best[entry_id] = (de, calc_id)
    return {k: v[1] for k, v in best.items()}


_ATOM_ROW = re.compile(r"\((\d+),(\d+|NULL),(?:\d+|NULL),(?:'(\w+)'|NULL),(?:-?\d+|NULL),"
                       r"([-\d.eE+]+),([-\d.eE+]+),([-\d.eE+]+),(?:[^,]*,){6}([-\d.eE+]+),")


def pass2(structure_ids: set[int], path: Path = DUMP, log=print) -> dict[int, list]:
    """Atoms of the given structures: structure_id -> [(element, x, y, z, occupancy)] (fractional)."""
    out: dict[int, list] = {}
    seen_atoms = False
    n = 0
    for line in stream(path):
        if line.startswith("INSERT INTO `atoms` "):
            seen_atoms = True
            for aid, sid, el, x, y, z, occ in _ATOM_ROW.findall(line):
                if sid != "NULL" and int(sid) in structure_ids:
                    out.setdefault(int(sid), []).append((el, float(x), float(y), float(z), float(occ)))
            n += 1
            if n % 500 == 0:
                log(f"{n:,} atoms lines, {len(out):,} structures collected")
        elif seen_atoms and line.startswith("INSERT INTO"):
            break                                      # atoms are contiguous; stop reading the dump
    return out


# --- normalised table -----------------------------------------------------------------------------

ENTRIES = OQMD_DIR / "entries.parquet"
STRUCTS = OQMD_DIR / "structures.jsonl.gz"


def normalise(p1: dict, atoms: dict, log=print) -> tuple["pd.DataFrame", dict]:
    """One row per OQMD entry with a standard-fit label; every filter recorded as a column and
    counted. Returns (frame, counts). Structures of rows passing every filter go to STRUCTS."""
    import gzip
    import json

    import pandas as pd
    from pymatgen.core import Composition

    from harness import confidence as C

    reps = _representatives(p1["fes"], p1["calc"], p1["entries"])
    fe_of = {}
    for entry_id, calc_id, de, stab in p1["fes"]:
        if reps.get(entry_id) == calc_id and entry_id not in fe_of:
            fe_of[entry_id] = (de, stab)
    counts = {"entries_in_dump": len(p1["entries"]),
              "entries_with_a_standard_fit_label": len(reps)}
    rows, n_written = [], 0
    with gzip.open(STRUCTS, "wt") as out:
        for entry_id, calc_id in reps.items():
            c = p1["calc"].get(calc_id)
            de, stab = fe_of[entry_id]
            row = {"entry_id": entry_id, "calculation_id": calc_id, "delta_e": de, "stability": stab,
                   "calc_label": c[0] if c else None, "converged": bool(c and c[5] == 1),
                   "settings": p1["settings"][c[3]] if c else None, "structure_id": c[2] if c else None}
            st = p1["structs"].get(row["structure_id"])
            at = atoms.get(row["structure_id"], [])
            row["has_structure"] = bool(st) and len(at) > 0 and len(at) == (st[0] or len(at))
            row["natoms"] = len(at)
            row["ordered"] = bool(at) and all(a[4] == 1.0 for a in at)
            row["le_max_atoms"] = 0 < len(at) <= MAX_ATOMS
            try:
                comp = Composition({a[0]: 0 for a in at} | _counts(at)) if at else None
                row["formula"] = comp.reduced_formula if comp else None
                row["family"] = C.family(row["formula"]) if comp else None
            except Exception:  # noqa: BLE001 - an unparseable species, counted below
                row["formula"], row["family"] = None, None
            row["usable"] = (row["has_structure"] and row["converged"] and row["ordered"]
                             and row["le_max_atoms"] and row["formula"] is not None)
            if row["usable"]:
                out.write(json.dumps({"id": entry_id, "lattice": [list(st[1:4]), list(st[4:7]), list(st[7:10])],
                                      "species": [a[0] for a in at], "frac": [a[1:4] for a in at]}) + "\n")
                n_written += 1
            rows.append(row)
    df = pd.DataFrame(rows)
    counts |= {"has_structure": int(df.has_structure.sum()),
               "and_converged": int((df.has_structure & df.converged).sum()),
               "and_ordered": int((df.has_structure & df.converged & df.ordered).sum()),
               "and_le_40_atoms": int((df.has_structure & df.converged & df.ordered & df.le_max_atoms).sum()),
               "usable": int(df.usable.sum()), "structures_written": n_written}
    df.to_parquet(ENTRIES)
    log(json.dumps(counts))
    return df, counts


def _counts(atoms: list) -> dict:
    out: dict = {}
    for a in atoms:
        out[a[0]] = out.get(a[0], 0) + 1
    return out


# --- the OQMD job suite, the locked half and its accessor ------------------------------------------

SUITE = "oqmd"
SPLIT_FILE = ROOT / "data" / "oqmd_split.json"
OPEN_LOG = ROOT / "data" / "oqmd_heldout_log.json"


def job_key(entry_id: int, tag: str) -> str:
    return f"oqmd-{entry_id}@{tag}"


def build_jobs(entry_ids: list[int], compute: dict, tag: str, settings: dict) -> list[dict]:
    """One relaxation per entry from OQMD's DFT-relaxed structure, at DEFAULT_RELAX (the product's)."""
    import gzip
    import json

    from pymatgen.core import Lattice, Structure

    want = set(entry_ids)
    ref = {}
    import pandas as pd

    df = pd.read_parquet(ENTRIES, columns=["entry_id", "formula", "family", "delta_e", "stability"])
    for r in df[df.entry_id.isin(want)].itertuples():
        ref[r.entry_id] = {"formula": r.formula, "family": r.family, "delta_e": r.delta_e, "stability": r.stability}
    jobs = []
    with gzip.open(STRUCTS, "rt") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["id"] not in want:
                continue
            s = Structure(Lattice(rec["lattice"]), rec["species"], rec["frac"])
            key = job_key(rec["id"], tag)
            jobs.append({"suite": SUITE, "job_key": key, "n_atoms": len(s), "model": settings.get("model"),
                         "settings": settings, "priority": len(s),
                         "inputs": {"job_key": key, "suite": SUITE, "entry_id": rec["id"], "structure": s,
                                    "ref": ref[rec["id"]]}})
    missing = want - {j["inputs"]["entry_id"] for j in jobs}
    if missing:
        raise RuntimeError(f"{len(missing)} requested OQMD entries have no normalised structure")
    return jobs


def _record(job: dict, res: dict) -> None:
    """Runner-side recorder: the relaxation and the product's own guard. Hull placement is done later,
    in bulk, against MP's hull (mode (a)) - it needs network and is shared across rows."""
    from harness import compare, store

    key, eid = job["job_key"], job["entry_id"]
    if res.get("status") != "ok":
        store.record_job(SUITE, key, res["status"], payload={"entry_id": eid}, error=res.get("error"),
                         runtime_s=res.get("job_wall_s"))
        return
    relaxed = res["relaxed"]
    rejection = compare.rejection_reason(res)
    if relaxed.composition.reduced_formula != job["ref"]["formula"]:
        rejection = rejection or f"composition mismatch ({relaxed.composition.reduced_formula})"
    try:
        changed = not compare.relaxed_into_target(relaxed, job["structure"])
    except Exception:  # noqa: BLE001 - matcher failure is recorded, never guessed
        changed = None
    store.record_job(SUITE, key, "ok", payload={
        "entry_id": eid, "formula": job["ref"]["formula"], "family": job["ref"]["family"],
        "stability": job["ref"]["stability"], "e_engine": res["energy_per_atom"], "converged": res["converged"],
        "n_steps": res["n_steps"], "rejection": rejection, "structure_changed": changed, "relaxed": relaxed,
        "wall_time_s": res["wall_time_s"]}, settings=res.get("metadata"), runtime_s=res.get("job_wall_s"))


def _sha(ids) -> str:
    import hashlib

    return hashlib.sha256(",".join(sorted(str(i) for i in ids)).encode()).hexdigest()   # as freeze_spec_v2.sha


def load_split(path=SPLIT_FILE) -> dict:
    import json

    return json.loads(path.read_text())


def heldout_ids(unlock: bool = False, path=SPLIT_FILE) -> list[int]:
    """The OQMD held-out half. Locked: nothing in the 2026-09-24 campaign may pass unlock=True, and a
    future evaluation needs its own pre-registration first."""
    if not unlock:
        raise PermissionError("the OQMD held-out half is locked (external_oqmd.heldout_ids(unlock=True)) "
                              "and may only be opened by a pre-registered evaluation")
    t = load_split(path)["heldout"]
    if _sha(t["ids"]) != t["sha256"]:
        raise RuntimeError("OQMD held-out ids do not match their recorded hash")
    return t["ids"]


def excluded_heldout_ids(path=SPLIT_FILE) -> set[int]:
    """The held-out ids as an EXCLUSION filter only (for any later development draw)."""
    if not path.exists():
        return set()
    t = load_split(path)["heldout"]
    if _sha(t["ids"]) != t["sha256"]:
        raise RuntimeError("OQMD held-out ids do not match their recorded hash")
    return set(t["ids"])


def development_ids(path=SPLIT_FILE) -> list[int]:
    t = load_split(path)["development"]
    if _sha(t["ids"]) != t["sha256"]:
        raise RuntimeError("OQMD development ids do not match their recorded hash")
    return t["ids"]


def is_opened() -> bool:
    return OPEN_LOG.is_file()
