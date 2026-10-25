"""Ghosting test core (CONTROLS.md §6).

Expected scancodes are written out by hand from the CONTROLS.md §1/§2 tables,
not read from config: the doc is the oracle, config and code must agree with it.
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.config import CONFIG_DIR
from tools.ghosting import (
    COMBOS,
    HOLD_MS,
    HoldTracker,
    Result,
    combo_scancodes,
    evaluate,
    load_keymaps,
    results_table,
)

DEFAULT_YAML = CONFIG_DIR / "default.yaml"
CONTROLS = Path(__file__).resolve().parents[2] / "docs" / "CONTROLS.md"

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


def test_reasons_are_the_controls_doc_column():
    section = re.search(r"^## 6\..*?(?=^## )", CONTROLS.read_text(encoding="utf-8"), re.M | re.S)[0]
    column = [m[1] for m in re.finditer(r"^\| [^|]+ \| ([^|]+?) \| [☑☐] \|", section, re.M)]  # "Neden kritik"
    assert [c.reason for c in COMBOS] == column


@pytest.mark.parametrize("combo", COMBOS, ids=lambda c: c.id)
def test_default_layout_scancodes(combo, keymaps):
    assert combo_scancodes(combo, keymaps, "default") == EXPECTED[combo.id][0]


@pytest.mark.parametrize("combo", COMBOS, ids=lambda c: c.id)
def test_alt_layout_scancodes(combo, keymaps):
    assert combo_scancodes(combo, keymaps, "alt") == EXPECTED[combo.id][1]


def test_keymaps_come_from_the_validated_config(tmp_path):
    # A key bound twice (X -> W) is caught by engine.config, so the ghosting tool never tests a broken map.
    text = DEFAULT_YAML.read_text(encoding="utf-8").replace("NOOP: 27", "NOOP: 26")
    (tmp_path / "default.yaml").write_text(text, encoding="utf-8")
    (tmp_path / "profiles").mkdir()
    with pytest.raises(ValidationError, match="scancode 26"):
        load_keymaps(config_dir=tmp_path)


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


# --- HoldTracker: all keys held without a break for HOLD_MS ---------------------

def test_hold_ms_matches_controls_doc():
    assert HOLD_MS == 3000  # CONTROLS.md §6: "en az 3 saniye basılı tut"


def test_hold_not_done_before_duration():
    t = HoldTracker(hold_ms=3000)
    assert t.update(True, now_ms=1000) is False
    assert t.update(True, now_ms=3999) is False


def test_hold_done_exactly_at_duration():
    t = HoldTracker(hold_ms=3000)
    t.update(True, now_ms=1000)
    assert t.update(True, now_ms=4000) is True


def test_hold_resets_when_a_key_drops():
    t = HoldTracker(hold_ms=3000)
    t.update(True, now_ms=0)
    t.update(False, now_ms=2500)               # one key ghosted for a moment
    assert t.update(True, now_ms=3000) is False  # timer restarted at 3000
    assert t.update(True, now_ms=6000) is True


def test_hold_never_done_while_not_ok():
    t = HoldTracker(hold_ms=3000)
    assert t.update(False, now_ms=0) is False
    assert t.update(False, now_ms=10_000) is False


def test_hold_progress():
    t = HoldTracker(hold_ms=3000)
    assert t.progress(now_ms=0) == 0.0         # nothing held yet
    t.update(True, now_ms=1000)
    assert t.progress(now_ms=2500) == 0.5
    assert t.progress(now_ms=9000) == 1.0      # clamped
    t.update(False, now_ms=9000)
    assert t.progress(now_ms=9000) == 0.0


# --- results_table(layout, results) -> Markdown for CONTROLS.md §6 --------------

def test_results_table():
    results = [
        Result("W+UP+THROW", ok=True, missing=frozenset()),
        Result("A+S+THROW+ROCK", ok=False, missing=frozenset({229, 4})),
    ]
    assert results_table("default", results) == (
        "| Kombinasyon | default | Eksik scancode |\n"
        "|---|---|---|\n"
        "| W+UP+THROW | ☑ |  |\n"
        "| A+S+THROW+ROCK | ✗ | 4, 229 |"
    )
