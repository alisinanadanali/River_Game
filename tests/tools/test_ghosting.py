"""Ghosting test core (CONTROLS.md §6).

Expected scancodes are written out by hand from the CONTROLS.md §1/§2 tables,
not read from config: the doc is the oracle, config and code must agree with it.
"""

import pytest

from tools.ghosting import COMBOS, combo_scancodes, evaluate, load_keymaps

# CONTROLS.md §6, in table order. Values: SDL scancodes from §1 (default) and §2 (alt).
EXPECTED = {
    "W+UP+THROW": ({26, 82, 228}, {26, 12, 24}),
    "D+RIGHT+DAM": ({7, 79, 40}, {7, 15, 44}),
    "Q+DOWN+ROCK": ({20, 81, 229}, {20, 14, 18}),
    "W+D+LEFT+UP": ({26, 7, 80, 82}, {26, 7, 13, 12}),
    "E+DAM+UP": ({8, 40, 82}, {8, 44, 12}),
    "A+S+THROW+ROCK": ({4, 22, 228, 229}, {4, 22, 24, 18}),
}


@pytest.fixture(scope="module")
def keymaps():
    return load_keymaps()


def test_combo_list_matches_controls_doc():
    assert [c.id for c in COMBOS] == list(EXPECTED)


@pytest.mark.parametrize("combo", COMBOS, ids=lambda c: c.id)
def test_default_layout_scancodes(combo, keymaps):
    assert combo_scancodes(combo, keymaps, "default") == EXPECTED[combo.id][0]


@pytest.mark.parametrize("combo", COMBOS, ids=lambda c: c.id)
def test_alt_layout_scancodes(combo, keymaps):
    assert combo_scancodes(combo, keymaps, "alt") == EXPECTED[combo.id][1]


def test_unknown_layout_is_rejected(keymaps):
    with pytest.raises(ValueError):
        combo_scancodes(COMBOS[0], keymaps, "dvorak")


@pytest.mark.parametrize("layout", ["shrek_default", "shrek_alt"])
def test_layouts_share_no_scancodes(layout, keymaps):
    groups = [keymaps["donkey"], keymaps[layout], keymaps["global"]]
    codes = [code for group in groups for code in group.values()]
    assert len(codes) == len(set(codes)), "two actions are bound to the same key"


# --- evaluate(pressed, required) -> (ok, missing) -------------------------------

def test_evaluate_all_keys_detected():
    assert evaluate({26, 82, 228}, frozenset({26, 82, 228})) == (True, frozenset())


def test_evaluate_reports_missing_keys():
    assert evaluate({26, 82}, frozenset({26, 82, 228})) == (False, frozenset({228}))


def test_evaluate_ignores_extra_keys():
    assert evaluate({26, 82, 228, 4}, frozenset({26, 82, 228})) == (True, frozenset())


def test_evaluate_nothing_pressed():
    required = frozenset({4, 22, 228, 229})
    assert evaluate(set(), required) == (False, required)


def test_evaluate_missing_is_frozenset():
    _, missing = evaluate([26], frozenset({26, 82}))  # any iterable of pressed codes
    assert isinstance(missing, frozenset)
