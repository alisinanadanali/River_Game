"""The donkey (MODEL.md §4, D-01 … D-10; TICK.md steps 3, 7 and 10).

The donkey walks the stone graph (M-01) carrying two LIFO bags. Each rule is a small pure function; the stages
chain them in TICK.md order and emit the events.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from engine.config import Config


class DepthState(StrEnum):
    """D-04. SWEPT is never stored: the donkey respawns in the same tick (D-07)."""

    DRY = "DRY"
    ANKLE = "ANKLE"
    KNEE = "KNEE"
    SWEPT = "SWEPT"


class Side(StrEnum):
    """D-08 stance and D-09 bag side."""

    NONE = "NONE"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


@dataclass(frozen=True, kw_only=True)
class Bag:
    """ENTITIES.md Bag: item ids, the last one on top (LIFO). Mass and volume are kept in step with the items."""

    items: tuple[int, ...] = ()
    mass: float = 0.0     # kg
    volume: int = 0


@dataclass(frozen=True, kw_only=True)
class Donkey:
    """ENTITIES.md Donkey. Rows −1 and R are the banks."""

    row: int
    col: int
    lives: int
    depth_state: DepthState = DepthState.DRY
    depth: float | None = None                    # cm, d = L − e (D-04); None on a bank
    move_target: tuple[int, int] | None = None    # D-05 slow move
    move_remaining: int = 0                       # ticks
    stance: Side = Side.NONE                      # D-08
    stance_since: int | None = None               # tick
    bag_left: Bag = Bag()
    bag_right: Bag = Bag()


def initial_donkey(config: Config) -> Donkey:
    """D-05: the donkey starts on the south bank in column ⌊C/2⌋, next to Shrek, with all its lives (D-07)."""
    return Donkey(row=-1, col=config.map.cols // 2, lives=config.time.lives)
