"""harness/external_oqmd.py: the streaming dump parser and the entry-selection rule, on synthetic rows."""

from harness import external_oqmd as X


def test_values_parser_handles_escapes_commas_and_null():
    line = "INSERT INTO `x` VALUES (1,'a\\'b',NULL,2.5),(2,'c,(d)',3,-1e-05);"
    assert list(X.parse_values(line)) == [["1", "a'b", None, "2.5"], ["2", "c,(d)", "3", "-1e-05"]]


def test_atoms_regex_reads_element_fractional_coords_and_occupancy():
    line = ("INSERT INTO `atoms` VALUES (1,33803,5,'Ne',NULL,0,0,0,0,0,0,0,7.399,NULL,1,NULL),"
            "(2,33804,6,'H',NULL,0.5,0.25,-1e-3,0,0,0,0,0.435,NULL,0.5,NULL);")
    assert X._ATOM_ROW.findall(line) == [("1", "33803", "Ne", "0", "0", "0", "1"),
                                         ("2", "33804", "H", "0.5", "0.25", "-1e-3", "0.5")]


def test_settings_summary_keeps_functional_potentials_and_u():
    s = ("{'encut': 520.0, 'ldau': True, 'ldauu': [5.3, 0], 'potentials': [{'xc': 'PBE', 'name': 'Fe_pv'}, "
         "{'xc': 'PBE', 'name': 'O'}], 'ispin': 2, 'ismear': -5, 'nbands': 99}")
    assert X.settings_summary(s) == "xc=PBE;pots=Fe_pv,O;encut=520.0;ispin=2;ldau=True;ldauu=[5.3, 0];ismear=-5"


def test_representative_is_qmpys_lowest_delta_e_and_skips_duplicates_and_unlabelled():
    fes = [(10, 100, -0.5, 0.0), (10, 101, -0.6, -0.01), (11, 102, 0.1, None), (12, 103, 0.0, 0.1)]
    entries = {10: (10, 2, None), 11: (None, 1, None), 12: (10, 1, None)}   # 12 is a duplicate of 10
    assert X._representatives(fes, {}, entries) == {10: 101}
