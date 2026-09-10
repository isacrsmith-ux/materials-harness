"""Offline tests for MP data normalisation."""

from pymatgen.core import Element

from harness.mp_data import str_keys


def test_str_keys_converts_element_keys_recursively():
    raw = {"oxidation_states": {Element("Li"): 1.0, Element("F"): -1.0}, "nested": [{Element("O"): 2}], "x": 3}
    out = str_keys(raw)
    assert out == {"oxidation_states": {"Li": 1.0, "F": -1.0}, "nested": [{"O": 2}], "x": 3}
    assert all(isinstance(k, str) for k in out["oxidation_states"])


def test_element_keyed_oxidation_states_are_invisible_to_string_lookup():
    # This is why str_keys exists: MP2020Compatibility does data["oxidation_states"].get("F", 0).
    element_keyed = {Element("Li"): 1.0, Element("F"): -1.0}
    assert element_keyed.get("F", 0) == 0          # silently missed
    assert str_keys(element_keyed).get("F", 0) == -1.0
