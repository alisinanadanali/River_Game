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
