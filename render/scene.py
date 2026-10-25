"""VISUALS §4.1: what one frame draws, and the skeleton's texts. Pure: no pygame, time already applied.

A Scene is built by the loop (game/view.py) from the session; render/draw.py draws it. It holds the observation,
never the state (ADR-005), plus what only the loop knows: where the characters are between ticks, their looks,
the mode, the pause and the seed.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from engine.events import Role
from engine.observe import Observation
from render.characters.animator import Look
from render.strings_tr import CAPTION, GAME_OVER_BANNER, GAME_OVER_REASONS, MODE_NAMES, PAUSED_BANNER, TOP_BAR

SECONDS_DECIMALS = 6  # the time left is rounded here before counting whole seconds up: 5 · 0.6 s is 3.0000000000000004


@dataclass(frozen=True)
class Scene:
    obs: Observation
    before: Observation                        # the previous tick's (colours blend from it, §3)
    u: float                                   # the share of a tick since the last one, [0, 1]
    levels: tuple[float, ...]                  # L(c), cm, interpolated between ticks
    feet: Mapping[Role, tuple[float, float]]   # px, interpolated between ticks
    rows: Mapping[Role, int]                   # the row each character is drawn with (VISUALS §2 order)
    looks: Mapping[Role, Look]
    mode: str                                  # game.session.Mode value (render does not import game, ADR-005)
    paused: bool
    seed: int


def seconds_left(obs: Observation) -> int:
    """The game's time left in whole seconds, counted up: 0 only when the time is over."""
    time = obs.config.time
    return math.ceil(round((time.game_length_ticks - obs.t) * time.tick_seconds, SECONDS_DECIMALS))


def top_bar(scene: Scene) -> str:
    obs = scene.obs
    return TOP_BAR.format(seconds=seconds_left(obs), score=obs.score, lives=obs.donkey.lives,
                          mode=MODE_NAMES[scene.mode])


def banner(scene: Scene) -> str | None:
    """The line across the middle: the game's end, else the pause, else none."""
    obs = scene.obs
    if obs.game_over is not None:
        return GAME_OVER_BANNER.format(reason=GAME_OVER_REASONS[obs.game_over.value], score=obs.score)
    return PAUSED_BANNER if scene.paused else None


def caption(seed: int) -> str:
    return CAPTION.format(seed=seed)
