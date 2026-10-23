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


class ItemStatus(StrEnum):
    """I-03, ENTITIES.md item life cycle."""

    ON_BANK = "ON_BANK"
    IN_FLIGHT = "IN_FLIGHT"
    IN_BAG = "IN_BAG"
    FLOATING = "FLOATING"
    DELIVERED = "DELIVERED"
    LOST = "LOST"


class LostReason(StrEnum):
    BANK_OVERFLOW = "bank_overflow"  # I-02
    SANK = "sank"                    # I-04
    DRIFTED_OFF = "drifted_off"      # I-04
    OFF_MAP = "off_map"              # S-05


class ProjectileKind(StrEnum):
    THROW = "THROW"      # S-04
    HANDOFF = "HANDOFF"  # S-06


class CatchSource(StrEnum):
    FLIGHT = "flight"      # S-05
    HANDOFF = "handoff"    # S-06
    FLOATING = "floating"  # I-05


class MissReason(StrEnum):
    NO_STANCE = "no_stance"
    STANCE_TOO_LATE = "stance_too_late"
    OUT_OF_RADIUS = "out_of_radius"
    DONKEY_ON_BANK = "donkey_on_bank"


class ReturnCause(StrEnum):
    HANDOFF_CANCELLED = "handoff_cancelled"  # S-06
    LANDED_ON_BANK = "landed_on_bank"        # S-05


class DropCause(StrEnum):
    KNEE = "knee"    # D-06
    SLIP = "slip"    # D-03
    SWEPT = "swept"  # D-07


class RaiseTarget(StrEnum):
    STONE = "stone"            # a permanent stone: r_i += rock_raise_cm
    TEMP_STONE = "temp_stone"  # a temporary stone: h += rock_raise_cm


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


@dataclass(frozen=True, kw_only=True)
class DamStarted(Event):
    """TICK.md step 2(a): Shrek began holding the dam at column c_d = col (S-08, W-04)."""

    col: int


@dataclass(frozen=True, kw_only=True)
class TempStoneSpawned(Event):
    """TICK.md step 2(d): ROCK on water made a temporary stone (S-07)."""

    stone_id: int
    row: int
    col: int
    h: float  # cm, rock_initial_h_cm


@dataclass(frozen=True, kw_only=True)
class TempStoneRaised(Event):
    """TICK.md step 2(d): ROCK on a stone raised it by delta_cm (S-07)."""

    row: int
    col: int
    delta_cm: float
    target: RaiseTarget


@dataclass(frozen=True, kw_only=True)
class TempStoneVanished(Event):
    """TICK.md step 6: the temporary stone sank below rock_vanish_h_cm (S-07); a donkey on it is swept in step 7."""

    stone_id: int
    row: int
    col: int
    under_donkey: bool


@dataclass(frozen=True, kw_only=True)
class ItemArrived(Event):
    """TICK.md step 9: a new item at the bank (I-01); queue_len is the queue length after it was handled (I-02)."""

    item_id: int
    kind: str
    queue_len: int


@dataclass(frozen=True, kw_only=True)
class ItemLost(Event):
    """TICK.md steps 3, 4, 7, 8, 9: the item is gone for good. origin is its status before (None on arrival)."""

    item_id: int
    reason: LostReason
    origin: ItemStatus | None


@dataclass(frozen=True, kw_only=True)
class ItemThrown(Event):
    """TICK.md step 2(d): the head of the queue left Shrek's hands (S-04 THROW, S-06 HANDOFF)."""

    item_id: int
    kind: ProjectileKind
    from_col: int
    target: tuple[int, int]
    sigma: float        # cells; 0 for a handoff
    flight_ticks: int


@dataclass(frozen=True, kw_only=True)
class ItemCaught(Event):
    """TICK.md steps 4 (flight, handoff) and 8 (floating): the item went into the `side` bag."""

    item_id: int
    side: Side
    source: CatchSource
    miss_distance: float  # cells from the donkey's cell


@dataclass(frozen=True, kw_only=True)
class ItemMissed(Event):
    """TICK.md step 4: a thrown item was not caught (S-05); reason is the first condition that failed."""

    item_id: int
    landing: tuple[float, float]
    miss_distance: float
    reason: MissReason


@dataclass(frozen=True, kw_only=True)
class ItemBounced(Event):
    """TICK.md step 4: the catch was good but the `side` bag had no room; the item falls into the water (S-05)."""

    item_id: int
    side: Side


@dataclass(frozen=True, kw_only=True)
class ItemReturnedToBank(Event):
    """TICK.md step 4: back at the end of the queue (S-05 landed on the bank, S-06 handoff cancelled)."""

    item_id: int
    cause: ReturnCause


@dataclass(frozen=True, kw_only=True)
class ItemDropped(Event):
    """TICK.md steps 3 (slip) and 7 (knee, swept): an item fell from the `side` bag (D-03, D-06, D-07)."""

    item_id: int
    side: Side
    cause: DropCause


@dataclass(frozen=True, kw_only=True)
class ItemFloated(Event):
    """TICK.md steps 3, 4, 7: an item in the water that floats, at (row, x) (I-04)."""

    item_id: int
    row: int
    x: float


@dataclass(frozen=True, kw_only=True)
class ItemSank(Event):
    """TICK.md steps 3, 4, 7: an item in the water that does not float; ItemLost(sank) follows (I-04)."""

    item_id: int
    row: int
    col: int


@dataclass(frozen=True, kw_only=True)
class ItemDelivered(Event):
    """TICK.md step 10: an item reached the north bank in a bag (D-10); points go to the score."""

    item_id: int
    kind: str
    points: int


@dataclass(frozen=True, kw_only=True)
class DonkeySlipped(Event):
    """TICK.md step 3: the donkey slipped starting a move (D-03); the top item of `side` falls (ItemDropped)."""

    side: Side
    p_slip: float
    delta: float   # δ, D-02
    mossy: bool    # left a mossy permanent stone
