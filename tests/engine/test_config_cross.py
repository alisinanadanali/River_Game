"""MODEL.md §9: cross-field config rules, checked on the merged config."""

import copy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from engine.config import validate_config

DEFAULT_YAML = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


@pytest.fixture(scope="module")
def raw():
    with open(DEFAULT_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def edited(raw: dict, **sections) -> dict:
    """Deep copy of `raw` with `section={key: value}` updates, e.g. edited(raw, map={"rows": 5})."""
    data = copy.deepcopy(raw)
    for section, values in sections.items():
        data[section].update(values)
    return data


# --- max_rocks_to_solve ≤ rock_max_active (M-04, MODEL A.6) ------------------------------

def test_more_rocks_to_solve_than_can_be_active(raw):
    # hard.yaml sets both to 3; forgetting rock_max_active leaves the default 2.
    with pytest.raises(ValidationError, match="max_rocks_to_solve"):
        validate_config(edited(raw, map={"max_rocks_to_solve": 3}))


def test_rocks_to_solve_equal_to_active_is_fine(raw):
    validate_config(edited(raw, map={"max_rocks_to_solve": 3}, shrek={"rock_max_active": 3}))


def test_rocks_to_solve_unused_without_max_rocks_guarantee(raw):
    validate_config(edited(raw, map={"max_rocks_to_solve": 3, "path_guarantee": "path"}))


# --- depth thresholds are ordered (D-04) ----------------------------------------------------

@pytest.mark.parametrize(
    ("ankle", "knee", "swept"),
    [(0, 0, 20), (0, 8, 8), (10, 8, 20), (0, 25, 20)],
)
def test_depth_thresholds_must_increase(raw, ankle, knee, swept):
    depths = {"depth_ankle_cm": ankle, "depth_knee_cm": knee, "depth_swept_cm": swept}
    with pytest.raises(ValidationError, match="depth"):
        validate_config(edited(raw, donkey=depths))


# --- stone base height range (M-03) ---------------------------------------------------------

def test_stone_base_range_reversed(raw):
    with pytest.raises(ValidationError, match="stone_base_h_cm"):
        validate_config(edited(raw, map={"stone_base_h_cm": [20, 0]}))


def test_stone_base_range_single_point_is_fine(raw):
    validate_config(edited(raw, map={"stone_base_h_cm": [10, 10]}))


# --- item probabilities sum to 1 (I-01) -------------------------------------------------------

def with_probs(raw: dict, apple: float, potato: float, melon: float) -> dict:
    data = copy.deepcopy(raw)
    for name, p in zip(("apple_crate", "potato_sack", "watermelon"), (apple, potato, melon)):
        data["items"]["types"][name]["prob"] = p
    return data


@pytest.mark.parametrize("probs", [(0.5, 0.3, 0.1), (0.5, 0.3, 0.3), (0.0, 0.0, 0.0)])
def test_item_probs_must_sum_to_one(raw, probs):
    with pytest.raises(ValidationError, match="prob"):
        validate_config(with_probs(raw, *probs))


def test_item_probs_float_rounding_is_tolerated(raw):
    validate_config(with_probs(raw, 0.1 + 0.2, 0.5, 0.2))   # 0.1 + 0.2 = 0.30000000000000004


def test_no_item_types(raw):
    data = copy.deepcopy(raw)
    data["items"]["types"] = {}
    with pytest.raises(ValidationError, match="prob"):
        validate_config(data)


# --- no scancode bound twice (CONTROLS.md §1–§3) ---------------------------------------------

@pytest.mark.parametrize(
    ("group", "action", "code"),
    [
        ("donkey", "NOOP", 26),              # X -> W, already MOVE_N
        ("shrek_default", "ROCK", 228),      # Right Shift -> Right Ctrl, already THROW
        ("shrek_alt", "DAM", 4),             # Space -> A, already donkey MOVE_W
        ("global", "RESTART", 82),           # F5 -> Up, already shrek_default AIM_UP
    ],
)
def test_scancode_bound_twice(raw, group, action, code):
    data = copy.deepcopy(raw)
    data["controls"]["keymaps"][group][action] = code
    with pytest.raises(ValidationError, match=f"scancode {code}"):
        validate_config(data)


def test_layouts_may_reuse_each_others_keys(raw):
    # Only one Shrek layout is active at a time: shrek_alt may bind a key shrek_default uses.
    data = copy.deepcopy(raw)
    data["controls"]["keymaps"]["shrek_alt"]["NONE"] = 56     # '.' is shrek_default NONE too
    validate_config(data)


# --- render.hud (VISUALS §5) -------------------------------------------------------------------------------------

def hud_edited(raw, **hud):
    data = copy.deepcopy(raw)
    data["render"]["hud"].update(hud)
    return data


@pytest.mark.parametrize("tiers", [[0.1, 0.03, 0.25], [0.03, 0.03, 0.25], [0.03, 0.1], [0.0, 0.1, 0.25], [0.03, 0.1, 1.5]])
def test_slip_prob_tiers_are_three_increasing_probabilities(raw, tiers):
    with pytest.raises(ValidationError, match="slip_prob_tiers"):
        validate_config(hud_edited(raw, slip_prob_tiers=tiers))


@pytest.mark.parametrize(("key", "value"), [("warn_share", 0.0), ("warn_share", 1.2), ("blink_hz", 0.0)])
def test_hud_ranges(raw, key, value):
    with pytest.raises(ValidationError, match=key):
        validate_config(hud_edited(raw, **{key: value}))
