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


@dataclass(frozen=True, kw_only=True)
class GameOver(Event):
    """TICK.md steps 7 (lives) and 11 (time). The tick it ended in is the common field `t`."""

    reason: GameOverReason
    score: int


def event_to_json(event: Event) -> str:
    """ADR-010: one event as one canonical JSON line (no trailing newline)."""
    return canonical_json({"type": event.type, **dataclasses.asdict(event)})


def events_to_jsonl(events: Iterable[Event]) -> str:
    """ADR-010: events as JSONL text, one line per event, each line ending in a newline."""
    return "".join(event_to_json(event) + "\n" for event in events)
