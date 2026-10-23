"""Tick: one step's work in progress, handed from stage to stage of the TICK.md pipeline (engine/step.py).

Kept apart from step.py so that rule modules (water.py, …) can write their stages as Tick -> Tick functions.
"""

import dataclasses
from dataclasses import dataclass

import numpy as np

from engine.actions import Actions
from engine.events import Event
from engine.rng import Rngs
from engine.state import GameState


@dataclass(frozen=True, kw_only=True, eq=False)
class Tick:
    """One step's work in progress, handed from stage to stage."""

    state: GameState
    actions: Actions
    rngs: Rngs
    t: int                             # the tick being processed: state.t when step began, even after step 11
    u_throw: np.ndarray | None = None  # R-02 block, set by step 0
    u_slip: np.ndarray | None = None   # R-02 block, set by step 0
    events: tuple[Event, ...] = ()

    def emit(self, event_type: type[Event], **fields) -> "Tick":
        """Append one event, numbered with this tick's t and the next seq (TICK.md step 12)."""
        event = event_type(t=self.t, seq=len(self.events), **fields)
        return dataclasses.replace(self, events=self.events + (event,))
