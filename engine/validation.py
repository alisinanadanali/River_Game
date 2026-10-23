"""Action validation (TICK.md step 1; S-03, D-05, S-08).

Each rejected component becomes a no-op (NOOP / NONE) and is reported once with ActionRejected, so the later
stages only ever see valid actions and need no defensive checks.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from engine.actions import Ability, DonkeyAction, ShrekMove
from engine.events import ActionRejected, Component, RejectReason, Role

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports engine/donkey.py
    from engine.tick import Tick


def validate_stage(tick: Tick) -> Tick:
    """TICK.md step 1: the donkey first (D-05), then Shrek (S-08, S-03)."""
    return _validate_shrek(_validate_donkey(tick))


def _validate_donkey(tick: Tick) -> Tick:
    """D-05: the donkey's input is ignored during a slow move; NOOP is not a rejection."""
    actions = tick.actions
    if tick.state.donkey.move_remaining > 0 and actions.donkey is not DonkeyAction.NOOP:
        tick = tick.emit(ActionRejected, role=Role.DONKEY, component=Component.ACTION, reason=RejectReason.BUSY_MOVING)
        tick = dataclasses.replace(tick, actions=dataclasses.replace(actions, donkey=DonkeyAction.NOOP))
    return tick


def _validate_shrek(tick: Tick) -> Tick:
    """S-08 burst lock, then S-03: no walking while the dam is held this tick, cooldowns."""
    state, action = tick.state, tick.actions.shrek
    valid = action
    if state.dam.burst_lock:
        if action.ability is Ability.DAM:
            tick = _reject(tick, Component.ABILITY, RejectReason.BURST_LOCK)
            valid = dataclasses.replace(valid, ability=Ability.NONE)
        else:  # S-08: DAM was let go, so the next DAM may start a dam again
            dam = dataclasses.replace(state.dam, burst_lock=False)
            tick = dataclasses.replace(tick, state=dataclasses.replace(state, dam=dam))
    if valid.ability is Ability.DAM and valid.move is not ShrekMove.NONE:
        tick = _reject(tick, Component.MOVE, RejectReason.DAM_ACTIVE)
        valid = dataclasses.replace(valid, move=ShrekMove.NONE)
    cooldown = {Ability.THROW: state.shrek.throw_cooldown, Ability.ROCK: state.shrek.rock_cooldown}
    if cooldown.get(valid.ability, 0) > 0:
        tick = _reject(tick, Component.ABILITY, RejectReason.COOLDOWN)
        valid = dataclasses.replace(valid, ability=Ability.NONE)
    if valid is action:
        return tick
    return dataclasses.replace(tick, actions=dataclasses.replace(tick.actions, shrek=valid))


def _reject(tick: Tick, component: Component, reason: RejectReason) -> Tick:
    return tick.emit(ActionRejected, role=Role.SHREK, component=component, reason=reason)
