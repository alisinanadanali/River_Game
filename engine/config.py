"""Validated, immutable game configuration (ADR-008).

default.yaml + optional profile (differences only) -> deep merge -> pydantic validation -> frozen Config.
Valid ranges are the ones stated in the config/default.yaml comments; a field whose comment states no range
is only type-checked. No field has a default: a missing key is an error, never a number made up in code.
"""

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.canonical import canonical_json

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

CONFIG_VERSION = 1        # meta.config_version this schema reads
SDL_NUM_SCANCODES = 512   # SDL scancodes are 0 … 511
PROB_SUM_ABS_TOL = 1e-9   # item probabilities must sum to 1 within this (MODEL.md §9)


def deep_merge(base: dict, override: dict) -> dict:
    """ADR-008: merge `override` onto `base` recursively; the inputs are not modified.

    Where both sides hold a dict, merge inside it; anything else (scalar, list, type clash) is replaced
    by the override's value. Unknown keys are kept: rejecting them is validation's job.
    The result shares no dicts or lists with either input.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# --- field types -------------------------------------------------------------------

Prob = Annotated[float, Field(ge=0, le=1)]
PosFloat = Annotated[float, Field(gt=0)]
NonNegFloat = Annotated[float, Field(ge=0)]
PosInt = Annotated[int, Field(ge=1)]
NonNegInt = Annotated[int, Field(ge=0)]
Scancode = Annotated[int, Field(ge=0, lt=SDL_NUM_SCANCODES)]
HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
Fraction = Annotated[float, Field(ge=0, le=1)]          # a share of an image's width or height
Squash = Annotated[float, Field(ge=0, lt=1)]            # scale 1 ± this stays > 0
OpenRatio = Annotated[float, Field(gt=0, lt=1)]


class StrictModel(BaseModel):
    """Unknown keys rejected, no type coercion (except int -> float), immutable after loading."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


# --- sections (one per top-level key of default.yaml) -----------------------------------

class MetaConfig(StrictModel):
    config_version: Literal[CONFIG_VERSION]
    profile: str


class TimeConfig(StrictModel):
    tick_seconds: Annotated[float, Field(gt=0.2, le=2.0)]
    game_length_ticks: PosInt
    lives: PosInt                              # D-07


class MapConfig(StrictModel):
    rows: Annotated[int, Field(ge=3)]          # M-01
    cols: Annotated[int, Field(ge=3)]
    stone_density: Prob                        # M-02
    path_guarantee: Literal["none", "path", "max_rocks"]   # M-04
    max_rocks_to_solve: int
    max_regen_attempts: PosInt                 # M-05
    stone_base_h_cm: tuple[float, float]       # M-03
    stiffness_kg_per_cm: PosFloat
    mossy_prob: Prob
    mossy_stiffness_kg_per_cm: PosFloat
    mossy_slip_multiplier: Annotated[float, Field(ge=1)]   # D-03

    @model_validator(mode="after")
    def _base_range_ordered(self):
        """M-03: stone base height is U[lo, hi], so lo ≤ hi."""
        lo, hi = self.stone_base_h_cm
        if lo > hi:
            raise ValueError(f"stone_base_h_cm [{lo}, {hi}]: lo must be ≤ hi")
        return self


class WaterConfig(StrictModel):
    ou_theta_per_tick: Annotated[float, Field(gt=0, lt=1)]  # W-01
    ou_mu_cm: float
    ou_sigma_cm: NonNegFloat
    wave_rate_per_tick: NonNegFloat            # W-02
    wave_amp_mean_cm: PosFloat
    wave_speed_cols_per_tick: PosFloat         # W-03
    wave_width_cols: PosFloat
    wave_spawn_offset_widths: float
    wave_cull_offset_widths: float
    flow_speed_cols_per_tick: float            # I-04


class DamConfig(StrictModel):
    downstream_drop_cm: float                  # W-04
    q_max_cm_cols: float                       # W-05


class DonkeyConfig(StrictModel):
    mass_kg: PosFloat                          # D-01, D-02
    bag_max_kg_per_side: PosFloat              # D-09
    bag_max_volume_per_side: PosInt
    depth_ankle_cm: float                      # D-04
    depth_knee_cm: float
    depth_swept_cm: float
    slow_move_ticks: PosInt                    # D-05
    knee_drop_prob: Prob                       # D-06
    slip_base_prob: Prob                       # D-03
    slip_kappa: NonNegFloat
    stance_max_ticks: Annotated[int, Field(ge=2)]   # D-08
    respawn_delay_ticks: int                   # D-07

    @model_validator(mode="after")
    def _depths_increase(self):
        """D-04: ankle < knee < swept."""
        if not self.depth_ankle_cm < self.depth_knee_cm < self.depth_swept_cm:
            raise ValueError(
                f"depth thresholds must increase: depth_ankle_cm {self.depth_ankle_cm} < "
                f"depth_knee_cm {self.depth_knee_cm} < depth_swept_cm {self.depth_swept_cm}"
            )
        return self


class ShrekConfig(StrictModel):
    throw_cooldown_ticks: NonNegInt            # S-03
    throw_flight_ticks: PosInt                 # S-04
    throw_sigma0_cells: NonNegFloat
    throw_sigma_per_row_cells: float
    throw_sigma_per_kg_cells: float
    catch_radius_cells: PosFloat               # S-05
    bank_load_ticks: int                       # S-06
    rock_cooldown_ticks: int                   # S-07
    rock_max_active: int
    rock_initial_h_cm: float
    rock_sink_cm_per_tick: PosFloat
    rock_vanish_h_cm: float
    rock_stiffness_kg_per_cm: PosFloat
    rock_raise_cm: float
    rock_raise_decay_cm_per_tick: float


class ItemType(StrictModel):
    mass_kg: float
    volume: int
    points: int
    floats: bool
    prob: Prob


class ItemsConfig(StrictModel):
    arrival_rate_per_tick: NonNegFloat         # I-01
    bank_capacity: PosInt                      # I-02
    types: dict[str, ItemType]

    @model_validator(mode="after")
    def _probs_sum_to_one(self):
        """I-01: an arriving item's type is drawn from items.types.*.prob."""
        total = math.fsum(t.prob for t in self.types.values())
        if not math.isclose(total, 1.0, rel_tol=0, abs_tol=PROB_SUM_ABS_TOL):
            raise ValueError(f"items.types.*.prob must sum to 1, got {total}")
        return self


class RewardsConfig(StrictModel):
    """METRICS.md §4; read by envs/, never by the engine (ADR-009)."""

    delivered_points: float
    caught: float
    lost: float
    life_lost: float
    rejected: float


class DonkeyKeys(StrictModel):
    MOVE_N: Scancode
    MOVE_W: Scancode
    MOVE_S: Scancode
    MOVE_E: Scancode
    STANCE_LEFT: Scancode
    STANCE_RIGHT: Scancode
    NOOP: Scancode


class ShrekKeys(StrictModel):
    MOVE_W: Scancode
    MOVE_E: Scancode
    AIM_UP: Scancode
    AIM_DOWN: Scancode
    THROW: Scancode
    ROCK: Scancode
    DAM: Scancode
    NONE: Scancode


class GlobalKeys(StrictModel):
    TOGGLE_DEBUG: Scancode
    TOGGLE_TACTICAL: Scancode
    PAUSE: Scancode
    RESTART: Scancode


class Keymaps(StrictModel):
    donkey: DonkeyKeys
    shrek_default: ShrekKeys
    shrek_alt: ShrekKeys
    global_: GlobalKeys = Field(alias="global")   # `global` is a Python keyword; no default despite the `=`

    @model_validator(mode="after")
    def _no_scancode_bound_twice(self):
        """CONTROLS.md §1–§3: within the active key set (donkey + one Shrek layout + global) each key does one thing."""
        for layout in ("shrek_default", "shrek_alt"):
            seen: dict[int, str] = {}
            for group in ("donkey", layout, "global_"):
                for action, code in getattr(self, group).model_dump().items():
                    if code in seen:
                        raise ValueError(f"scancode {code} bound to both {seen[code]} and {group}.{action}")
                    seen[code] = f"{group}.{action}"
        return self


class ControlsConfig(StrictModel):
    tactical_mode: bool
    shrek_keymap: Literal["default", "alt"]    # CONTROLS.md §2
    keymaps: Keymaps


class LayoutConfig(StrictModel):
    top_bar_px: int
    bottom_bar_px: int
    side_panel_px: int
    tile_w_px: int
    tile_h_px: int
    px_per_cm: float
    water_alpha: float
    z_room_cm: NonNegFloat                     # VISUALS §2: room above the board
    bank_z_cm: float                           # the banks' drawn height (the model: always dry)
    front_shade: Fraction                      # a front face's colour = its top's × this


class HudConfig(StrictModel):
    """VISUALS §5."""

    warn_share: Annotated[float, Field(gt=0, le=1)]    # bank queue (above) and dam (reaching) warnings
    blink_hz: PosFloat                                 # the dam warning's blinking
    feed_seconds: PosFloat                             # an event line's life in the bottom bar
    feed_max: PosInt                                   # lines kept
    slip_prob_tiers: tuple[float, float, float]        # balance bar: p_slip below each → DRY, ANKLE, KNEE colour

    @model_validator(mode="after")
    def _tiers_increase(self):
        p = self.slip_prob_tiers
        if not 0 < p[0] < p[1] < p[2] <= 1:
            raise ValueError(f"slip_prob_tiers must increase within (0, 1], got {list(p)}")
        return self


class PaletteConfig(StrictModel):
    dry: HexColor
    ankle: HexColor
    knee: HexColor
    danger: HexColor
    water: HexColor
    background: HexColor                       # VISUALS §4.1: the window, the banks, text
    bank: HexColor
    text: HexColor


class PoseImage(StrictModel):
    """VISUALS §9.1: one pose image of a character, read from a local file (ADR-012)."""

    file: str                                  # relative to the project root
    anchor: tuple[Fraction, Fraction]          # the feet, as a share of the image (x, y)
    faces: Literal["left", "right"]
    scale: PosFloat                            # × the character's height_px


class ShrekPoses(StrictModel):
    idle: PoseImage
    throw: PoseImage
    dam: PoseImage


class DonkeyPoses(StrictModel):
    idle: PoseImage
    happy: PoseImage


class CharacterLook(StrictModel):
    """VISUALS §9: on-screen height, and the abstract shape drawn when an image is missing (§9.4)."""

    height_px: PosFloat
    fallback_color: HexColor
    fallback_size_px: tuple[PosInt, PosInt]


class ShrekLook(CharacterLook):
    poses: ShrekPoses


class DonkeyLook(CharacterLook):
    poses: DonkeyPoses


class CharactersConfig(StrictModel):
    shrek: ShrekLook
    donkey: DonkeyLook


class AnimationConfig(StrictModel):
    """VISUALS §9.2: clip timings (wall-clock seconds) and amplitudes (px, degrees, ratios)."""

    breath_period_s: PosFloat                  # IDLE
    breath_scale: Squash
    scared_shake_px: NonNegFloat               # SCARED
    scared_shake_hz: PosFloat
    wade_period_s: PosFloat                    # WADE
    wade_bob_px: NonNegFloat
    dam_shake_px: NonNegFloat                  # DAM
    dam_shake_hz: PosFloat
    hop_height_px: NonNegFloat                 # HOP; flight time is time.tick_seconds
    land_s: PosFloat
    land_squash: Squash
    throw_s: PosFloat                          # THROW
    throw_windup_ratio: OpenRatio
    throw_squash: Squash
    slip_s: PosFloat                           # SLIP_LEFT, SLIP_RIGHT
    slip_tilt_deg: NonNegFloat
    slip_wobble_hz: PosFloat
    happy_s: PosFloat                          # HAPPY, CHEER
    happy_bounce_px: NonNegFloat
    happy_bounces: PosInt
    respawn_s: PosFloat                        # RESPAWN
    swept_s: PosFloat                          # SWEPT
    swept_slide_px: NonNegFloat
    swept_tilt_deg: NonNegFloat


class RenderConfig(StrictModel):
    window_px: tuple[int, int]
    fps: int
    layout: LayoutConfig
    font: str
    font_mono: str
    palette: PaletteConfig
    hud: HudConfig                             # VISUALS §5
    debug_overlay: bool
    forecast_ticks: int
    characters: CharactersConfig               # VISUALS §9
    animation: AnimationConfig


class MetricsConfig(StrictModel):
    critical_horizon_ticks: int                # METRICS.md §3
    dam_anticipation_lead_ticks: int


class LoggingConfig(StrictModel):
    events_jsonl: bool
    replay: bool
    dir: str


class Config(StrictModel):
    meta: MetaConfig
    time: TimeConfig
    map: MapConfig
    water: WaterConfig
    dam: DamConfig
    donkey: DonkeyConfig
    shrek: ShrekConfig
    items: ItemsConfig
    rewards: RewardsConfig
    controls: ControlsConfig
    render: RenderConfig
    metrics: MetricsConfig
    logging: LoggingConfig

    @model_validator(mode="after")
    def _guaranteed_map_is_solvable(self):
        """M-04, MODEL A.6: a map needing k rocks is solvable in one crossing only if k ≤ rock_max_active."""
        if self.map.path_guarantee == "max_rocks" and self.map.max_rocks_to_solve > self.shrek.rock_max_active:
            raise ValueError(
                f"map.max_rocks_to_solve {self.map.max_rocks_to_solve} > "
                f"shrek.rock_max_active {self.shrek.rock_max_active}"
            )
        return self


def validate_config(data: dict) -> Config:
    """ADR-008: validate a merged config dict.

    Goes through JSON so strict mode reads YAML lists as tuples (Python-mode strict would reject a list
    for a tuple field) while still refusing "9" for an int or true for an int.
    """
    return Config.model_validate_json(json.dumps(data))


def config_hash(cfg: Config) -> str:
    """EVENTS.md log header: "sha256:" + SHA-256 of the validated config's canonical JSON.

    Taken from the model, not the YAML text, so comments, key order and 50 vs 50.0 do not change it.
    """
    canonical = canonical_json(cfg.model_dump(mode="json", by_alias=True))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_config(default: dict, profile: dict | None = None, name: str | None = None) -> Config:
    """ADR-008: deep-merge profile `name` onto `default`, then validate. Pure: dicts in, Config out.

    With no `name`, `default` is validated alone. A profile must say which profile it is
    (meta.profile == name), so a copied file cannot end up in replays under the wrong name.
    """
    if name is None:
        return validate_config(default)
    if not isinstance(profile, dict):
        raise ValueError(f"profile {name!r} must be a mapping, got {type(profile).__name__}")
    cfg = validate_config(deep_merge(default, profile))
    if cfg.meta.profile != name:
        raise ValueError(f"profile {name!r} has meta.profile {cfg.meta.profile!r}; they must match")
    return cfg


def load_config(profile: str | None = None, config_dir: Path = CONFIG_DIR) -> Config:
    """Read default.yaml and profiles/<profile>.yaml from `config_dir` and build the Config.

    The only file I/O in engine/; it runs once at start-up, never inside step.
    """
    default = _read_yaml(config_dir / "default.yaml")
    if profile is None:
        return build_config(default)
    available = sorted(p.stem for p in (config_dir / "profiles").glob("*.yaml"))
    if profile not in available:
        raise ValueError(f"unknown profile {profile!r}; expected one of {available}")
    return build_config(default, _read_yaml(config_dir / "profiles" / f"{profile}.yaml"), profile)


def _read_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
