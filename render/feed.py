"""VISUALS §5: the bottom bar's event feed. Pure: an event and the observation in, a Turkish line (or None) out.

Item names come from the observation (an item keeps its id and kind for the whole game). VISUALS' table is the
contract, checked line by line in tests/render/test_feed.py.
"""

from engine.events import (
    ActionRejected,
    DamReleased,
    DonkeySlipped,
    DonkeySwept,
    Event,
    ItemArrived,
    ItemBounced,
    ItemCaught,
    ItemDelivered,
    ItemDropped,
    ItemLost,
    ItemMissed,
    ItemReturnedToBank,
    ItemThrown,
    LifeLost,
    ProjectileKind,
    ReleaseReason,
    TempStoneVanished,
    WaveOrigin,
    WaveSpawned,
)
from engine.observe import Observation
from render.strings_tr import (
    DROP_CAUSES,
    FEED_ARRIVED,
    FEED_BOUNCED,
    FEED_CAUGHT,
    FEED_DAM_BURST,
    FEED_DAM_RELEASED,
    FEED_DELIVERED,
    FEED_DROPPED,
    FEED_HANDOFF,
    FEED_LIFE_LOST,
    FEED_LOST,
    FEED_MISSED,
    FEED_REJECTED,
    FEED_RETURNED,
    FEED_SLIPPED,
    FEED_STONE_VANISHED,
    FEED_SWEPT,
    FEED_WAVE,
    ITEM_NAMES,
    LOST_REASONS,
    MISS_REASONS,
    REJECT_REASONS,
    ROLE_NAMES,
    SIDE_NAMES,
    tr,
)

SPOKEN: frozenset[type[Event]] = frozenset({
    ItemArrived, ItemThrown, ItemCaught, ItemMissed, ItemBounced, ItemReturnedToBank, ItemDropped, ItemLost,
    ItemDelivered, DonkeySlipped, DonkeySwept, LifeLost, DamReleased, WaveSpawned, TempStoneVanished, ActionRejected,
})


def line(event: Event, obs: Observation) -> str | None:
    """VISUALS §5: the event's line, or None for a silent one."""
    def item(item_id: int) -> str:
        return ITEM_NAMES[obs.items[item_id].kind]

    match event:
        case ItemArrived():
            return FEED_ARRIVED.format(item=ITEM_NAMES[event.kind])
        case ItemThrown(kind=ProjectileKind.HANDOFF):
            return FEED_HANDOFF.format(item=item(event.item_id))
        case ItemCaught():
            return FEED_CAUGHT.format(item=item(event.item_id), side=SIDE_NAMES[event.side])
        case ItemMissed():
            return FEED_MISSED.format(item=item(event.item_id), reason=MISS_REASONS[event.reason])
        case ItemBounced():
            return FEED_BOUNCED.format(item=item(event.item_id), side=SIDE_NAMES[event.side])
        case ItemReturnedToBank():
            return FEED_RETURNED.format(item=item(event.item_id))
        case ItemDropped():
            return FEED_DROPPED.format(item=item(event.item_id), reason=DROP_CAUSES[event.cause])
        case ItemLost():
            return FEED_LOST.format(item=item(event.item_id), reason=LOST_REASONS[event.reason])
        case ItemDelivered():
            return FEED_DELIVERED.format(item=ITEM_NAMES[event.kind], points=event.points)
        case DonkeySlipped():
            return FEED_SLIPPED.format(side=SIDE_NAMES[event.side])
        case DonkeySwept():
            return FEED_SWEPT
        case LifeLost():
            return FEED_LIFE_LOST.format(lives=event.lives_left)
        case DamReleased():
            burst = event.reason is ReleaseReason.BURST
            return tr(FEED_DAM_BURST if burst else FEED_DAM_RELEASED, amplitude=event.amplitude)
        case WaveSpawned(origin=WaveOrigin.UPSTREAM):
            return tr(FEED_WAVE, amplitude=event.amplitude)
        case TempStoneVanished():
            return FEED_STONE_VANISHED
        case ActionRejected():
            return FEED_REJECTED.format(role=ROLE_NAMES[event.role], reason=REJECT_REASONS[event.reason])
    return None
