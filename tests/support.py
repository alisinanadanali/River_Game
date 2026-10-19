"""Shared test helpers: configs with a few values changed, and whole games run through step."""

from collections.abc import Iterable
from dataclasses import dataclass

import yaml

from engine.actions import Actions
from engine.config import CONFIG_DIR, Config, build_config, deep_merge
from engine.events import Event, events_to_jsonl
from engine.rng import Rngs
from engine.state import GameState, new_game
from engine.step import step

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


def run(config: Config, seed: int, actions: Iterable[Actions], start: tuple[GameState, Rngs] | None = None) -> Trace:
    """Step once per entry of `actions`, from `start` or from new_game(config, seed)."""
    state, rngs = start if start is not None else new_game(config, seed)
    states, streams, events = [], [], []
    for tick_actions in actions:
        state, rngs, tick_events = step(state, tick_actions, rngs)
        states.append(state)
        streams.append(rngs)
        events.extend(tick_events)
    return Trace(tuple(states), tuple(streams), tuple(events))
