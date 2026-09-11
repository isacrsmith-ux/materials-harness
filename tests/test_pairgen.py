"""Pair generator: one-element substitution detection, prototype grouping, priority ordering (offline)."""

from pymatgen.core import Composition

from harness import pairgen


def test_one_element_substitution():
    f = pairgen.one_element_substitution
    assert f({"Mg": 1, "O": 1}, {"Ca": 1, "O": 1}) == ("Mg", "Ca")
    assert f({"Mg": 1, "Al": 2, "O": 4}, {"Zn": 1, "Al": 2, "O": 4}) == ("Mg", "Zn")
    assert f({"Si": 1}, {"Ge": 1}) == ("Si", "Ge")
    assert f({"Mg": 1, "O": 1}, {"Mg": 1, "O": 1}) is None               # same composition
    assert f({"Ga": 1, "As": 1}, {"In": 1, "P": 1}) is None              # two substitutions
    assert f({"Al": 2, "O": 3}, {"Ti": 1, "O": 2}) is None               # different stoichiometry
    assert f({"Mg": 1, "Al": 2, "O": 4}, {"Al": 1, "Mg": 2, "O": 4}) is None  # swapped amounts


def _doc(mid, comp, sg=225, nsites=2, e=0.0, theoretical=False):
    return {"material_id": mid, "formula": Composition(comp).reduced_formula, "nsites": nsites, "sg_number": sg,
            "sg_symbol": "Fm-3m", "elements": list(comp), "composition_reduced": comp, "energy_above_hull": e,
            "theoretical": theoretical, "is_magnetic": False, "ordering": "NM",
            "total_magnetization_normalized_formula_units": 0.0}


def test_candidate_pairs_groups_by_prototype_and_orients_parent():
    docs = [_doc("mp-1", {"Mg": 1, "O": 1}), _doc("mp-2", {"Ca": 1, "O": 1}, e=0.05),
            _doc("mp-3", {"Ni": 1, "O": 1}, sg=186, nsites=4),  # another prototype: never paired with the rest
            _doc("mp-4", {"Mg": 1, "S": 1}), _doc("mp-5", {"Ca": 1, "S": 1})]
    cands = pairgen.candidate_pairs(docs)
    assert {(c["parent_id"], c["target_id"]) for c in cands} == {
        ("mp-1", "mp-2"),  # MgO -> CaO (MgO closer to the hull)
        ("mp-1", "mp-4"),  # MgO -> MgS (tie on hull energy -> lower id)
        ("mp-5", "mp-2"),  # CaS -> CaO (CaS closer to the hull)
        ("mp-4", "mp-5"),  # MgS -> CaS
    }  # MgO/CaS differ in two elements: not a pair
    by = {(c["parent_id"], c["target_id"]): c for c in cands}
    assert by[("mp-1", "mp-2")]["mapping"] == "Mg:Ca"
    assert by[("mp-1", "mp-2")]["space_relevant"] and not by[("mp-4", "mp-5")]["space_relevant"]
    only = pairgen.candidate_pairs(docs, supported={"Mg", "Ca", "O"})
    assert {(c["parent_id"], c["target_id"]) for c in only} == {("mp-1", "mp-2")}


def _cand(pid, tid, proto, space, known=2, e=0.0):
    return {"parent_id": pid, "target_id": tid, "prototype": proto, "space_relevant": space, "known_count": known,
            "e_hull_sum": e}


def test_chem_class():
    assert pairgen.chem_class("Cu3Au") == "metallic" and pairgen.chem_class("Fe") == "metallic"
    assert pairgen.chem_class("MgO") == "compound" and pairgen.chem_class("GaAs") == "compound"


def test_plausibility_ionic_and_metallic():
    ok = pairgen.plausibility("MgFe2O4", "MgMn2O4", "Fe:Mn")
    assert ok["scorer"].startswith("ionic") and ok["plausible"]
    bad = pairgen.plausibility("RbCl", "NCl", "Rb:N")  # the nonsense swap class seen in round 1
    assert not bad["plausible"]
    near = pairgen.plausibility("Cu3Au", "Ag3Au", "Cu:Ag")
    far = pairgen.plausibility("Cu3Au", "Cs3Au", "Cu:Cs")
    assert near["scorer"].startswith("Pettifor") and near["plausible"] and not far["plausible"]


def test_cell_quotas_sum_and_split():
    q = pairgen.cell_quotas(500, 0.10, 0.30)
    assert sum(q.values()) == 500
    assert q[("metallic", True)] + q[("metallic", False)] == 150 and q[("metallic", False)] == 15
    assert q[("compound", False)] == 35


def test_fill_stratified_caps_prototypes_and_reports_shortfall():
    def c(i, proto, plausible):
        return {"id": i, "prototype": proto, "plausible": plausible}

    streams = {"metallic": [c(i, "P", True) for i in range(10)] + [c(10, "Q", False)],
               "compound": [c(20 + i, f"R{i}", True) for i in range(5)]}
    quotas = {("metallic", True): 4, ("metallic", False): 2, ("compound", True): 3, ("compound", False): 1}
    classify = lambda x: ("metallic" if x["id"] < 20 else "compound", x["plausible"])  # noqa: E731
    accept = lambda x: (None, {"id": x["id"]}) if x["id"] != 21 else ("different prototype", None)  # noqa: E731
    picked, st = pairgen.fill_stratified(streams, quotas, classify, accept, max_per_prototype=3)
    assert len(picked[("metallic", True)]) == 3  # prototype P capped at 3
    assert len(picked[("metallic", False)]) == 1 and len(picked[("compound", True)]) == 3
    assert st["shortfall"] == {"metallic/plausible": 1, "metallic/implausible": 1, "compound/implausible": 1}
    assert st["counts"]["rejected: different prototype"] == 1 and st["counts"]["skipped: prototype cap"] >= 1
    # a shared counter carries the cap across bins: prototype P is already full
    shared = {"P": 3}
    picked2, _ = pairgen.fill_stratified({"metallic": [c(i, "P", True) for i in range(5)]},
                                         {("metallic", True): 2, ("metallic", False): 0}, classify, accept, 3, shared)
    assert picked2[("metallic", True)] == []


def test_prioritize_space_first_and_round_robin_across_prototypes():
    cands = [_cand("a1", "x", "A", True), _cand("a2", "x", "A", True, e=0.1), _cand("a3", "x", "A", True, e=0.2),
             _cand("b1", "x", "B", True, e=0.05), _cand("c1", "x", "C", False), _cand("c2", "x", "C", False, known=0)]
    order = [c["parent_id"] for c in pairgen.prioritize(cands)]
    assert order[:4] == ["a1", "b1", "a2", "a3"]  # one per prototype per round, space-relevant tier first
    assert order[4:] == ["c1", "c2"]              # then the non-space tier; known materials before theoretical
