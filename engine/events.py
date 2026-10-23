"""Event catalogue (EVENTS.md, ADR-009): the engine's only output channel.

Every event is a frozen, keyword-only dataclass carrying the common fields `t` (tick) and `seq` (order within
the tick); its `type` is the class name. Event classes are added together with the rule that emits them;
adding one or changing a field bumps EVENT_SCHEMA_VERSION.
"""

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from engine.canonical import canonical_json

EVENT_SCHEMA_VERSION = 1  # EVENTS.md log header; fixed at the first release (v0.1.0)


@dataclass(frozen=True, kw_only=True)
class Event:
    t: int    # tick the event happened in (the state's t when step began)
    seq: int  # TICK.md step 12: position in that tick's event list, 0, 1, 2, …

    type: ClassVar[str]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.type = cls.__name__


class GameOverReason(StrEnum):
    TIME = "time"
    LIVES = "lives"


class WaveOrigin(StrEnum):
    UPSTREAM = "UPSTREAM"  # W-02
    DAM = "DAM"            # W-05


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


class Role(StrEnum):
    DONKEY = "donkey"
    SHREK = "shrek"


class Component(StrEnum):
    """ActionRejected: which part of an action was turned into a no-op."""

    ACTION = "action"    # the donkey's single action
    MOVE = "move"        # Shrek's move
    ABILITY = "ability"  # Shrek's ability


class RejectReason(StrEnum):
    COOLDOWN = "cooldown"
    DAM_ACTIVE = "dam_active"
    QUEUE_EMPTY = "queue_empty"
    ROCK_LIMIT = "rock_limit"
    NO_STONE = "no_stone"
    BUSY_MOVING = "busy_moving"
    BURST_LOCK = "burst_lock"


class StanceReason(StrEnum):
    SET = "set"
    MOVED = "moved"
    EXPIRED = "expired"
    SWEPT = "swept"


class SweptCause(StrEnum):
    DEPTH = "depth"                    # d ≥ d₂ (D-04)
    STONE_VANISHED = "stone_vanished"  # no stone under the donkey (S-07, D-05)


class ReleaseReason(StrEnum):
    MANUAL = "manual"  # S-08: Shrek let go of DAM (TICK.md step 2a)
    BURST = "burst"    # W-05: Q reached Q_max (TICK.md step 5e)


@dataclass(frozen=True, kw_only=True)
class GameOver(Event):
    """TICK.md steps 7 (lives) and 11 (time). The tick it ended in is the common field `t`."""

    reason: GameOverReason
    score: int


@dataclass(frozen=True, kw_only=True)
class WaveSpawned(Event):
    """TICK.md steps 2 (manual dam release) and 5: a new wave (W-02 upstream, W-05 dam)."""

    wave_id: int
    amplitude: float  # cm
    x: float          # columns
    origin: WaveOrigin


@dataclass(frozen=True, kw_only=True)
class WaveAbsorbed(Event):
    """TICK.md step 5(c): the held dam swallowed a wave crossing c_d (W-06)."""

    wave_id: int
    volume: float   # cm·columns, A·s·√(2π)
    dam_col: int


@dataclass(frozen=True, kw_only=True)
class DamReleased(Event):
    """TICK.md steps 2(a) (manual) and 5(e) (burst): the stored volume leaves as a DAM wave (W-05)."""

    col: int
    volume: float       # Q released, cm·columns
    amplitude: float    # of the DAM wave, cm
    accumulated: float  # this episode's Σ q_in
    absorbed: float     # this episode's Σ absorbed wave volume
    held_ticks: int
    reason: ReleaseReason


@dataclass(frozen=True, kw_only=True)
class WaveExited(Event):
    """TICK.md step 5(g): the wave passed (C − 1) + k_cull·s and was removed (W-03)."""

    wave_id: int


def event_to_json(event: Event) -> str:
    """ADR-010: one event as one canonical JSON line (no trailing newline)."""
    return canonical_json({"type": event.type, **dataclasses.asdict(event)})


def events_to_jsonl(events: Iterable[Event]) -> str:
    """ADR-010: events as JSONL text, one line per event, each line ending in a newline."""
    return "".join(event_to_json(event) + "\n" for event in events)


@dataclass(frozen=True, kw_only=True)
class ShrekMoved(Event):
    """TICK.md step 2(b): Shrek walked one column along the south bank (S-01)."""

    from_col: int
    to_col: int


@dataclass(frozen=True, kw_only=True)
class ShrekAimed(Event):
    """TICK.md step 2(c): the aim row changed (S-02)."""

    row: int


@dataclass(frozen=True, kw_only=True)
class ActionRejected(Event):
    """TICK.md steps 1 and 3: one component of an action became a no-op. For diagnosis, never for rewards."""

    role: Role
    component: Component
    reason: RejectReason


@dataclass(frozen=True, kw_only=True)
class DonkeyMoveStarted(Event):
    """TICK.md step 3: a slow move from ANKLE or KNEE began; the donkey arrives `ticks` ticks after it (D-05)."""

    from_cell: tuple[int, int]
    to_cell: tuple[int, int]
    ticks: int


@dataclass(frozen=True, kw_only=True)
class DonkeyMoved(Event):
    """TICK.md step 3: the donkey arrived in to_cell (D-05)."""

    from_cell: tuple[int, int]
    to_cell: tuple[int, int]


@dataclass(frozen=True, kw_only=True)
class DonkeyStance(Event):
    """TICK.md steps 3 (set, moved), 7 (swept) and 11 (expired): the stance changed (D-08)."""

    side: Side
    reason: StanceReason


@dataclass(frozen=True, kw_only=True)
class DonkeyDepthChanged(Event):
    """TICK.md step 7: the depth state changed between DRY, ANKLE and KNEE (D-04). depth_cm is None on a bank."""

    old: DepthState
    new: DepthState
    depth_cm: float | None
    row: int
    col: int


@dataclass(frozen=True, kw_only=True)
class DonkeySwept(Event):
    """TICK.md step 7: the donkey was swept away (D-04, D-07). depth_cm is None when no stone was under it."""

    row: int
    col: int
    depth_cm: float | None
    cause: SweptCause
    items_dropped: int


@dataclass(frozen=True, kw_only=True)
class LifeLost(Event):
    """TICK.md step 7: one life lost to a sweep (D-07, INV-06)."""

    lives_left: int


@dataclass(frozen=True, kw_only=True)
class DonkeyRespawned(Event):
    """TICK.md step 7: back on the south bank in the column it was swept from (D-07)."""

    col: int
