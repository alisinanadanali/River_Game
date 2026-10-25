"""VISUALS §5 "Alt şerit": the event feed. The doc's table is the oracle: which events speak, their example lines,
their reason names, and that speaking plus silent events are the engine's whole catalogue."""

import re
from pathlib import Path

import pytest

from engine import events as ev
from engine.events import (
    ActionRejected,
    CatchSource,
    Component,
    DamReleased,
    DonkeySlipped,
    DonkeySwept,
    DropCause,
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
    LostReason,
    MissReason,
    ProjectileKind,
    RejectReason,
    ReleaseReason,
    ReturnCause,
    Role,
    Side,
    SweptCause,
    TempStoneVanished,
    WaveOrigin,
    WaveSpawned,
)
from engine.items import Item, ItemStatus
from engine.observe import observe
from render.feed import SPOKEN, line
from render.strings_tr import DROP_CAUSES, LOST_REASONS, MISS_REASONS, REJECT_REASONS
from tests.support import set_up, still

VISUALS = Path(__file__).resolve().parents[2] / "docs" / "VISUALS.md"
CFG = still({"map": {"rows": 3, "cols": 5}})
ITEMS = (Item(id=0, kind="apple_crate", status=ItemStatus.ON_BANK), Item(id=1, kind="watermelon", status=ItemStatus.IN_BAG))
OBS = observe(set_up(CFG, ["..#..", "..#..", "..#.."], items=ITEMS)[0], Role.DONKEY)
T = {"t": 0, "seq": 0}

EXAMPLES = [  # (event, the line the doc shows for it)
    (ItemArrived(**T, item_id=0, kind="apple_crate", queue_len=1), "Elma kasası kıyıya geldi"),
    (ItemThrown(**T, item_id=0, kind=ProjectileKind.HANDOFF, from_col=2, target=(-1, 2), sigma=0.0, flight_ticks=2),
     "Elma kasası teslim ediliyor"),
    (ItemCaught(**T, item_id=0, side=Side.LEFT, source=CatchSource.FLIGHT, miss_distance=0.1),
     "Eşek Elma kasası yakaladı (sol heybe)"),
    (ItemMissed(**T, item_id=0, landing=(1.0, 2.0), miss_distance=1.0, reason=MissReason.NO_STANCE),
     "Elma kasası ıskalandı: duruş yok"),
    (ItemBounced(**T, item_id=0, side=Side.LEFT), "Elma kasası sol heybeye sığmadı"),
    (ItemReturnedToBank(**T, item_id=0, cause=ReturnCause.LANDED_ON_BANK), "Elma kasası kıyıya döndü"),
    (ItemDropped(**T, item_id=0, side=Side.LEFT, cause=DropCause.SLIP), "Elma kasası düştü: kayma"),
    (ItemLost(**T, item_id=0, reason=LostReason.SANK, origin=ItemStatus.FLOATING), "Elma kasası kayboldu: battı"),
    (ItemDelivered(**T, item_id=0, kind="apple_crate", points=1), "Elma kasası teslim edildi, +1"),
    (DonkeySlipped(**T, side=Side.LEFT, p_slip=0.1, delta=-0.2, mossy=False), "Eşek kaydı (sol)"),
    (DonkeySwept(**T, row=1, col=2, depth_cm=25.0, cause=SweptCause.DEPTH, items_dropped=0), "Eşek sürüklendi!"),
    (LifeLost(**T, lives_left=2), "Can gitti, 2 kaldı"),
    (DamReleased(**T, col=4, volume=100.0, amplitude=27.0, accumulated=100.0, absorbed=0.0, held_ticks=20,
                 reason=ReleaseReason.MANUAL), "Baraj bırakıldı: 27 cm dalga"),
    (DamReleased(**T, col=4, volume=150.0, amplitude=40.0, accumulated=150.0, absorbed=0.0, held_ticks=30,
                 reason=ReleaseReason.BURST), "Baraj patladı: 40 cm dalga"),
    (WaveSpawned(**T, wave_id=0, amplitude=12.0, x=-4.5, origin=WaveOrigin.UPSTREAM), "Yukarıdan 12 cm dalga geliyor"),
    (TempStoneVanished(**T, stone_id=0, row=1, col=3, under_donkey=False), "Geçici taş battı"),
    (ActionRejected(**T, role=Role.SHREK, component=Component.ABILITY, reason=RejectReason.COOLDOWN),
     "Shrek: bekleme sürüyor"),
]
QUIET_CASES = [  # events of a speaking type that stay silent (VISUALS: "yalnız …")
    ItemThrown(**T, item_id=0, kind=ProjectileKind.THROW, from_col=2, target=(1, 2), sigma=0.3, flight_ticks=2),
    WaveSpawned(**T, wave_id=1, amplitude=27.0, x=4.0, origin=WaveOrigin.DAM),
]


def feed_section() -> str:
    text = VISUALS.read_text(encoding="utf-8")
    return re.search(r"^\*\*Alt şerit: olay akışı\*\*.*?(?=^\*\*Harita üstü)", text, re.M | re.S)[0]


def table() -> dict[str, str]:
    """event name → its 'Satır' cell."""
    return dict(re.findall(r"^\| `(\w+)` \| (.*) \|$", feed_section(), re.M))


def silent() -> set[str]:
    para = re.search(r"^Sessiz.*?(?=\n\n)", feed_section(), re.M | re.S)[0]
    return set(re.findall(r"`(\w+)`", para))


def catalogue() -> set[str]:
    return {name for name, obj in vars(ev).items()
            if isinstance(obj, type) and issubclass(obj, ev.Event) and obj is not ev.Event}


def test_speaking_and_silent_events_are_the_whole_catalogue():
    spoken, quiet = set(table()), silent()
    assert not spoken & quiet
    assert spoken | quiet == catalogue()


def test_the_feed_speaks_for_exactly_the_tables_events():
    assert {t.__name__ for t in SPOKEN} == set(table())


@pytest.mark.parametrize(("event", "expected"), EXAMPLES, ids=lambda x: type(x).__name__ if not isinstance(x, str) else "")
def test_each_line_is_the_docs_example(event, expected):
    assert line(event, OBS) == expected
    assert f"`{expected}`" in table()[type(event).__name__]


def test_every_speaking_type_has_an_example():
    assert {type(e).__name__ for e, _ in EXAMPLES} == set(table())


@pytest.mark.parametrize("event", QUIET_CASES, ids=lambda e: f"{type(e).__name__}-{getattr(e, 'origin', getattr(e, 'kind', ''))}")
def test_some_events_of_a_speaking_type_stay_silent(event):
    assert line(event, OBS) is None


@pytest.mark.parametrize(("event", "names", "enum"), [
    ("ItemMissed", MISS_REASONS, MissReason), ("ItemDropped", DROP_CAUSES, DropCause),
    ("ItemLost", LOST_REASONS, LostReason), ("ActionRejected", REJECT_REASONS, RejectReason),
])
def test_reasons_are_named_in_the_docs_order(event, names, enum):
    assert list(names) == list(enum)
    listed = re.search(r"\(neden: (.*?)\)", table()[event])[1].split(", ")
    assert listed == list(names.values())


def test_the_item_is_named_by_its_id():
    caught = ItemCaught(**T, item_id=1, side=Side.RIGHT, source=CatchSource.FLOATING, miss_distance=0.0)
    assert line(caught, OBS) == "Eşek Karpuz yakaladı (sağ heybe)"


def test_a_silent_event_says_nothing():
    assert line(ev.ShrekMoved(**T, from_col=1, to_col=2), OBS) is None
