"""ADR-008: the pydantic schema accepts default.yaml and rejects unknown, missing, mistyped or out-of-range keys.

Ranges come from the comments in config/default.yaml (the oracle for valid values).
"""

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


def with_value(data: dict, dotted: str, value) -> dict:
    """Deep copy of `data` with the key at `dotted` set to `value`."""
    data = copy.deepcopy(data)
    *parents, leaf = dotted.split(".")
    node = data
    for key in parents:
        node = node[key]
    node[leaf] = value
    return data


def without(data: dict, dotted: str) -> dict:
    data = copy.deepcopy(data)
    *parents, leaf = dotted.split(".")
    node = data
    for key in parents:
        node = node[key]
    del node[leaf]
    return data


# --- default.yaml itself -----------------------------------------------------------

def test_default_yaml_is_valid(raw):
    cfg = validate_config(raw)
    assert cfg.meta.profile == "percolation_edge"
    assert cfg.map.rows == 9 and cfg.map.cols == 9
    assert cfg.map.stone_base_h_cm == (0.0, 20.0)                 # list in YAML, immutable tuple here
    assert cfg.items.types["watermelon"].mass_kg == 50
    assert cfg.controls.keymaps.shrek_default.THROW == 228        # Right Ctrl (CONTROLS.md §1)
    assert cfg.render.palette.water == "#0072B2"


def test_config_is_frozen(raw):
    cfg = validate_config(raw)
    with pytest.raises(ValidationError):
        cfg.map.rows = 12


# --- unknown keys (typos) ------------------------------------------------------------

@pytest.mark.parametrize(
    "dotted",
    ["colour", "map.stone_densty", "items.types.watermelon.colour", "controls.keymaps.donkey.JUMP", "render.layout.tile_px"],
)
def test_unknown_key_is_rejected(raw, dotted):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        validate_config(with_value(raw, dotted, 1))


# --- missing keys: the schema has no defaults ---------------------------------------------

@pytest.mark.parametrize("dotted", ["map.rows", "water.ou_sigma_cm", "render.palette.water", "logging", "meta.profile"])
def test_missing_key_is_rejected(raw, dotted):
    with pytest.raises(ValidationError, match="Field required"):
        validate_config(without(raw, dotted))


# --- ranges from the default.yaml comments ------------------------------------------------

@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("meta.config_version", 2),
        ("time.tick_seconds", 0.2),             # (0.2, 2.0]
        ("time.tick_seconds", 2.5),
        ("time.game_length_ticks", 0),          # ≥ 1
        ("time.lives", 0),
        ("map.rows", 2),                        # ≥ 3
        ("map.cols", 2),
        ("map.stone_density", 1.1),             # [0, 1]
        ("map.stone_density", -0.1),
        ("map.path_guarantee", "always"),       # none | path | max_rocks
        ("map.max_regen_attempts", 0),          # ≥ 1
        ("map.stiffness_kg_per_cm", 0),         # > 0
        ("map.mossy_prob", 1.5),
        ("map.mossy_slip_multiplier", 0.5),     # ≥ 1
        ("water.ou_theta_per_tick", 0),         # (0, 1)
        ("water.ou_theta_per_tick", 1),
        ("water.ou_sigma_cm", -1),              # ≥ 0
        ("water.wave_rate_per_tick", -0.01),
        ("water.wave_amp_mean_cm", 0),          # > 0
        ("water.wave_speed_cols_per_tick", 0),
        ("water.wave_width_cols", 0),
        ("donkey.mass_kg", 0),                  # > 0
        ("donkey.bag_max_volume_per_side", 0),  # ≥ 1
        ("donkey.slow_move_ticks", 0),
        ("donkey.knee_drop_prob", 1.01),
        ("donkey.slip_kappa", -1),
        ("donkey.stance_max_ticks", 1),         # ≥ 2
        ("shrek.throw_cooldown_ticks", -1),     # ≥ 0
        ("shrek.throw_flight_ticks", 0),        # ≥ 1
        ("shrek.catch_radius_cells", 0),        # > 0
        ("shrek.rock_sink_cm_per_tick", 0),
        ("items.arrival_rate_per_tick", -0.1),
        ("items.bank_capacity", 0),
        ("items.types.watermelon.prob", 1.2),   # a probability
        ("controls.shrek_keymap", "dvorak"),    # default | alt
        ("controls.keymaps.donkey.MOVE_N", 512),  # SDL scancodes are 0…511
        ("controls.keymaps.global.PAUSE", -1),
        ("render.palette.water", "blue"),       # #RRGGBB
    ],
)
def test_out_of_range_is_rejected(raw, dotted, value):
    with pytest.raises(ValidationError):
        validate_config(with_value(raw, dotted, value))


@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("time.tick_seconds", 2.0),             # upper bound is inclusive
        ("map.rows", 3),
        ("map.stone_density", 0.0),
        ("map.stone_density", 1.0),
        ("donkey.stance_max_ticks", 2),
        ("shrek.throw_cooldown_ticks", 0),
        ("controls.keymaps.donkey.MOVE_N", 511),
    ],
)
def test_boundary_values_are_accepted(raw, dotted, value):
    validate_config(with_value(raw, dotted, value))


# --- strict types: no silent coercion ------------------------------------------------------

@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("map.rows", "9"),                      # string is not an int
        ("map.rows", 9.5),
        ("map.rows", True),                     # bool is not an int
        ("controls.tactical_mode", "yes"),
        ("controls.tactical_mode", 1),
        ("map.stone_base_h_cm", [0, 20, 40]),   # exactly two values
    ],
)
def test_wrong_type_is_rejected(raw, dotted, value):
    with pytest.raises(ValidationError):
        validate_config(with_value(raw, dotted, value))


def test_int_is_accepted_where_float_is_expected(raw):
    # YAML `stiffness_kg_per_cm: 50` has no decimal point; it is still a valid float.
    assert validate_config(raw).map.stiffness_kg_per_cm == 50.0
