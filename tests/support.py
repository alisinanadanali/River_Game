"""Shared test helpers: configs with a few values changed, and whole games run through step."""

import dataclasses
import hashlib
import itertools
from collections.abc import Iterable
from dataclasses import dataclass

import yaml

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import CONFIG_DIR, Config, build_config, deep_merge
from engine.events import Event, ReleaseReason, events_to_jsonl
from engine.rng import Rngs
from engine.state import GameState, new_game
from engine.step import step
from engine.tick import Tick
from engine.water import release_dam, start_dam

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
    """Step once per entry of `actions`, from `start` or from new_game(config, seed)."""
    state, rngs = start if start is not None else new_game(config, seed)
    states, streams, events = [], [], []
    for tick_actions in actions:
        state, rngs, tick_events = step(state, tick_actions, rngs)
        states.append(state)
        streams.append(rngs)
        events.extend(tick_events)
    return Trace(tuple(states), tuple(streams), tuple(events))


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


def press_dam(state: GameState, hold: bool, col: int) -> tuple[GameState, tuple[Event, ...]]:
    """Stand-in for S-08 (TICK.md step 2a) until Phase 0 step 7 wires the DAM action into step.

    Call before step(). hold=True starts the dam at `col` unless it is active or burst-locked; hold=False
    releases an active dam (reason manual) and clears the burst lock. Events carry t = state.t.
    """
    dam = state.dam
    if hold and not dam.active and not dam.burst_lock:
        return dataclasses.replace(state, dam=start_dam(dam, col, state.t)), ()
    if not hold and dam.active:
        tick = release_dam(Tick(state=state, actions=Actions(), rngs=None, t=state.t), ReleaseReason.MANUAL)
        return tick.state, tick.events
    if not hold and dam.burst_lock:
        return dataclasses.replace(state, dam=dataclasses.replace(dam, burst_lock=False)), ()
    return state, ()
