"""Action validation (TICK.md step 1; S-03, D-05, S-08).

Each rejected component becomes a no-op (NOOP / NONE) and is reported once with ActionRejected, so the later
stages only ever see valid actions and need no defensive checks.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from engine.actions import DonkeyAction
from engine.events import ActionRejected, Component, RejectReason, Role

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports engine/donkey.py
    from engine.tick import Tick


def validate_stage(tick: Tick) -> Tick:
    """TICK.md step 1: the donkey's input is ignored during a slow move (D-05)."""
    actions = tick.actions
    if tick.state.donkey.move_remaining > 0 and actions.donkey is not DonkeyAction.NOOP:
        tick = tick.emit(ActionRejected, role=Role.DONKEY, component=Component.ACTION, reason=RejectReason.BUSY_MOVING)
        actions = dataclasses.replace(actions, donkey=DonkeyAction.NOOP)
    return tick if actions is tick.actions else dataclasses.replace(tick, actions=actions)
