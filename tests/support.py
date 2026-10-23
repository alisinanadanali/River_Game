"""Shared test helpers: configs with a few values changed, and whole games run through step."""

import dataclasses
import hashlib
import itertools
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import yaml

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import CONFIG_DIR, Config, build_config, deep_merge
from engine.events import Event, events_to_jsonl
from engine.rng import Rngs
from engine.state import GameState, new_game
from engine.step import step
from engine.world import World, rocks_to_solve

with open(CONFIG_DIR / "default.yaml", encoding="utf-8") as _f:
    DEFAULT = yaml.safe_load(_f)


def config_with(overrides: dict) -> Config:
    """The default config with `overrides` deep-merged on top and validated like any profile."""
    return build_config(deep_merge(DEFAULT, overrides))


@dataclass(frozen=True)
class Trace:
    """Everything a run produced: the state and streams after each tick, and all events in order."""

    states: tuple[GameState, ...]
    rngs: tuple[Rngs, ...]
    events: tuple[Event, ...]

    @property
    def jsonl(self) -> bytes:
        """INV-02: the event log as it would be written to disk (UTF-8 JSONL)."""
        return events_to_jsonl(self.events).encode("utf-8")

    def digest(self) -> str:
        """SHA-256 over the event log, every state and every stream state, to compare runs across processes."""
        h = hashlib.sha256(self.jsonl)
        h.update(repr((self.states, self.rngs)).encode("utf-8"))
        return h.hexdigest()


def run(config: Config, seed: int, actions: Iterable[Actions], start: tuple[GameState, Rngs] | None = None) -> Trace:
    """Step once per entry of `actions`, from `start` or from new_game(config, seed), until the game ends."""
    state, rngs = start if start is not None else new_game(config, seed)
    states, streams, events = [], [], []
    for tick_actions in actions:
        if state.game_over is not None:
            break  # the last life was lost (D-07); step would raise GameFinishedError
        state, rngs, tick_events = step(state, tick_actions, rngs)
        states.append(state)
        streams.append(rngs)
        events.extend(tick_events)
    return Trace(tuple(states), tuple(streams), tuple(events))


# Still water: B stays at μ = 0 and no wave arrives, so L(c) = 0 everywhere and depths are exact.
STILL = {"water": {"ou_sigma_cm": 0.0, "wave_rate_per_tick": 0.0}, "items": {"arrival_rate_per_tick": 0.0}}


def still(overrides: dict | None = None) -> Config:
    """config_with(STILL + overrides): still water and no item arrivals unless the overrides say otherwise."""
    return config_with(deep_merge(STILL, overrides or {}))


def make_world(config: Config, rows: list[str], base_h: float | dict[tuple[int, int], float] = 10.0) -> World:
    """A hand-made World. rows[r] is river row r (rows[0] next to the south bank), one character per column:
    '.' water, '#' stone, 'm' mossy stone. base_h is one height for every stone or {(row, col): h}.
    """
    is_stone = np.array([[ch in "#m" for ch in line] for line in rows], dtype=bool)
    if is_stone.shape != (config.map.rows, config.map.cols):
        raise ValueError(f"map is {is_stone.shape}, config says {(config.map.rows, config.map.cols)}")
    mossy = np.array([[ch == "m" for ch in line] for line in rows], dtype=bool)
    heights = np.full(is_stone.shape, np.nan)
    for r, c in zip(*np.nonzero(is_stone), strict=True):
        heights[r, c] = base_h.get((int(r), int(c)), 10.0) if isinstance(base_h, dict) else base_h
    m = config.map
    stiffness = np.where(is_stone, np.where(mossy, m.mossy_stiffness_kg_per_cm, m.stiffness_kg_per_cm), np.nan)
    for grid in (is_stone, heights, stiffness, mossy):
        grid.flags.writeable = False
    return World(rows=is_stone.shape[0], cols=is_stone.shape[1], is_stone=is_stone, base_h=heights,
                 stiffness=stiffness, mossy=mossy, rocks_to_solve=rocks_to_solve(is_stone), seed=0, regen_attempt=0)


def set_up(config: Config, rows: list[str], base_h=10.0, seed: int = 1, **fields) -> tuple[GameState, Rngs]:
    """new_game(config, seed) on the hand-made map `rows`; `fields` replace GameState fields (e.g. donkey=...).

    Values given as dicts are applied to the current sub-state: donkey={"row": 0} moves the donkey only.
    """
    state, rngs = new_game(config, seed)
    changes = {"world": make_world(config, rows, base_h)}
    for name, value in fields.items():
        changes[name] = dataclasses.replace(getattr(state, name), **value) if isinstance(value, dict) else value
    return dataclasses.replace(state, **changes), rngs


def scripted_actions(n: int) -> list[Actions]:
    """A fixed, varied action script of length n: every donkey action against a rotation of Shrek actions."""
    shrek = [
        ShrekAction(),
        ShrekAction(move=ShrekMove.E, aim=Aim.UP, ability=Ability.THROW),
        ShrekAction(move=ShrekMove.W, ability=Ability.ROCK),
        ShrekAction(aim=Aim.DOWN, ability=Ability.DAM),
        ShrekAction(move=ShrekMove.E),
    ]
    pairs = zip(itertools.cycle(DonkeyAction), itertools.cycle(shrek))
    return [Actions(donkey=d, shrek=s) for d, s in itertools.islice(pairs, n)]


HOLD_DAM = Actions(shrek=ShrekAction(ability=Ability.DAM))  # S-08: hold the dam this tick
