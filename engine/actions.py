"""Action spaces (MODEL.md §1): A_D for the donkey, the multi-discrete triple A_S for Shrek.

Enum order is the RL encoding (index = action id) and must follow MODEL.md; the flat 36-action Shrek encoding
belongs to the RL wrapper, not here. Values are the names, so replay lines stay readable.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class DonkeyAction(StrEnum):
    NOOP = "NOOP"
    MOVE_N = "MOVE_N"
    MOVE_S = "MOVE_S"
    MOVE_E = "MOVE_E"
    MOVE_W = "MOVE_W"
    STANCE_LEFT = "STANCE_LEFT"
    STANCE_RIGHT = "STANCE_RIGHT"


class ShrekMove(StrEnum):
    NONE = "NONE"
    W = "W"
    E = "E"


class Aim(StrEnum):
    NONE = "NONE"
    UP = "UP"
    DOWN = "DOWN"


class Ability(StrEnum):
    NONE = "NONE"
    THROW = "THROW"
    ROCK = "ROCK"
    DAM = "DAM"


@dataclass(frozen=True, kw_only=True)
class ShrekAction:
    move: ShrekMove = ShrekMove.NONE
    aim: Aim = Aim.NONE
    ability: Ability = Ability.NONE


@dataclass(frozen=True, kw_only=True)
class Actions:
    """TICK.md step 1 input: one action per role for this tick. The defaults do nothing."""

    donkey: DonkeyAction = DonkeyAction.NOOP
    shrek: ShrekAction = field(default_factory=ShrekAction)
