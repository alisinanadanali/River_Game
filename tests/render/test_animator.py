"""VISUALS §9.3: the clip state machine. The event → clip table and its priorities are read from VISUALS."""

import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.events import (
    CatchSource,
    DepthState,
    DonkeyMoved,
    DonkeyMoveStarted,
    DonkeyRespawned,
    DonkeySlipped,
    DonkeySwept,
    ItemCaught,
    ItemDelivered,
    ItemThrown,
    ProjectileKind,
    RaiseTarget,
    Role,
    ShrekMoved,
    Side,
    SweptCause,
    TempStoneRaised,
    TempStoneSpawned,
)
from engine.evolve import evolve
from engine.observe import observe
from engine.state import new_game
from engine.step import step
from render.characters.animator import (
    Animator,
    Playing,
    ghost_look,
    look,
    loop_clip,
    new_animator,
    one_shot_clip,
    update,
)
from render.characters.pose import CLIPS_OF, Clip, duration_s, pose
from tests.support import config_with

VISUALS = Path(__file__).resolve().parents[2] / "docs" / "VISUALS.md"
CFG = config_with({"time": {"tick_seconds": 0.5}})
STATE, _ = new_game(CFG, 1)
OBS = observe(STATE, Role.DONKEY)  # V0: both roles see the same

EXAMPLES = {  # one event of every type the §9.3 table names
    "DonkeyRespawned": DonkeyRespawned(t=0, seq=0, col=4),
    "DonkeySlipped": DonkeySlipped(t=0, seq=0, side=Side.LEFT, p_slip=0.1, delta=0.2, mossy=False),
    "ItemThrown": ItemThrown(t=0, seq=0, item_id=0, kind=ProjectileKind.THROW, from_col=4, target=(0, 4),
                             sigma=0.2, flight_ticks=2),
    "TempStoneSpawned": TempStoneSpawned(t=0, seq=0, stone_id=0, row=0, col=4, h=20.0),
    "TempStoneRaised": TempStoneRaised(t=0, seq=0, row=0, col=4, delta_cm=10.0, target=RaiseTarget.STONE),
    "DonkeyMoved": DonkeyMoved(t=0, seq=0, from_cell=(0, 4), to_cell=(0, 5)),
    "DonkeyMoveStarted": DonkeyMoveStarted(t=0, seq=0, from_cell=(0, 4), to_cell=(0, 3), ticks=2),
    "ShrekMoved": ShrekMoved(t=0, seq=0, from_col=4, to_col=3),
    "ItemCaught": ItemCaught(t=0, seq=0, item_id=0, side=Side.LEFT, source=CatchSource.FLIGHT, miss_distance=0.1),
    "ItemDelivered": ItemDelivered(t=0, seq=0, item_id=0, kind="apple_crate", points=1),
    "DonkeySwept": DonkeySwept(t=0, seq=0, row=3, col=6, depth_cm=21.0, cause=SweptCause.DEPTH, items_dropped=0),
}


def event_table() -> list[tuple[str, Clip | None, Clip | None, int | None]]:
    """VISUALS §9.3 one-shot rows: (event type, donkey clip, Shrek clip, priority); None where the row has none."""
    section = VISUALS.read_text(encoding="utf-8").split("### 9.3", 1)[1].split("### 9.4", 1)[0]
    section = section.split("**Tek seferlik klip", 1)[1]

    def clip(cell: str) -> Clip | None:
        m = re.fullmatch(r"`(\w+)`", cell.replace("<side>", "LEFT"))  # the examples slip to the left
        return Clip(m[1]) if m else None

    rows = []
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        priority = int(cells[3]) if cells[3].isdigit() else None
        for name in re.findall(r"`(\w+)", cells[0]):
            rows.append((name, clip(cells[1]), clip(cells[2]), priority))
    return rows


TABLE = event_table()
PRIORITY = {clip: p for _, d, s, p in TABLE for clip in (d, s) if clip is not None}


def same(a, b) -> bool:
    """Two transforms equal up to float rounding (now − start is not exact: 5.3 − 5.0 = 0.2999…)."""
    return a.image == b.image and all(
        getattr(a, f) == pytest.approx(getattr(b, f)) for f in ("dx_px", "dy_px", "scale_x", "scale_y", "angle_deg", "alpha")
    )


def at(anim: Animator, now_s: float) -> Clip:
    return look(anim, now_s, CFG).clip


# --- the tables in VISUALS §9.3 --------------------------------------------------------------------------------

def test_every_event_in_the_table_has_an_example():
    assert {name for name, *_ in TABLE} == set(EXAMPLES)


@pytest.mark.parametrize(("name", "donkey", "shrek", "priority"), TABLE, ids=[row[0] for row in TABLE])
def test_event_starts_the_clip_in_the_table(name, donkey, shrek, priority):
    assert one_shot_clip(Role.DONKEY, [EXAMPLES[name]]) == donkey
    assert one_shot_clip(Role.SHREK, [EXAMPLES[name]]) == shrek


def test_slip_to_the_right():
    right = evolve(EXAMPLES["DonkeySlipped"], side=Side.RIGHT)
    assert one_shot_clip(Role.DONKEY, [right]) is Clip.SLIP_RIGHT


@pytest.mark.parametrize("role", list(Role))
def test_the_highest_priority_of_a_tick_wins_in_any_order(role):
    for a in EXAMPLES.values():
        for b in EXAMPLES.values():
            clips = [c for c in (one_shot_clip(role, [a]), one_shot_clip(role, [b])) if c is not None]
            if clips:  # within a role every one-shot clip has its own priority, so the winner is unique
                assert one_shot_clip(role, [a, b]) == one_shot_clip(role, [b, a]) == max(clips, key=PRIORITY.get)


def test_no_events_no_clip():
    assert one_shot_clip(Role.DONKEY, []) is None


@pytest.mark.parametrize(
    ("donkey", "dam_active", "donkey_loop", "shrek_loop"),
    [
        ({}, False, Clip.IDLE, Clip.IDLE),
        ({"depth_state": DepthState.ANKLE}, False, Clip.IDLE, Clip.IDLE),
        ({"depth_state": DepthState.KNEE}, False, Clip.SCARED, Clip.IDLE),
        ({"depth_state": DepthState.KNEE, "move_remaining": 1, "move_target": (1, 4)}, False, Clip.WADE, Clip.IDLE),
        ({"move_remaining": 1, "move_target": (1, 4)}, True, Clip.WADE, Clip.DAM),   # WADE comes first
    ],
)
def test_loop_comes_from_the_state(donkey, dam_active, donkey_loop, shrek_loop):
    state = evolve(STATE, donkey=evolve(STATE.donkey, **donkey), dam=evolve(STATE.dam, active=dam_active))
    obs = observe(state, Role.DONKEY)
    assert (loop_clip(Role.DONKEY, obs), loop_clip(Role.SHREK, obs)) == (donkey_loop, shrek_loop)


# --- update and look over time ---------------------------------------------------------------------------------

def test_new_animator_plays_its_loop_facing_east():
    anim = new_animator(Role.DONKEY, OBS, now_s=3.0)
    assert anim.loop == Playing(Clip.IDLE, 3.0) and anim.one_shot is None and anim.facing_right
    assert same(look(anim, 3.7, CFG).transform, pose(Clip.IDLE, 0.7, CFG))


def test_a_one_shot_plays_then_the_loop_comes_back():
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), OBS, [EXAMPLES["DonkeyMoved"]], 10.0, CFG)
    hop = duration_s(Clip.HOP, CFG)
    assert at(anim, 10.0) is Clip.HOP
    assert same(look(anim, 10.2, CFG).transform, pose(Clip.HOP, 0.2, CFG))
    assert at(anim, 10.0 + hop - 1e-6) is Clip.HOP
    end = 10.0 + hop + 1e-9                                    # (10 + 0.62) − 10 is 0.6199…: just past it
    assert at(anim, end) is Clip.IDLE
    assert same(look(anim, end, CFG).transform, pose(Clip.IDLE, end, CFG))  # the loop's time ran on meanwhile


def test_lower_priority_does_not_cut_a_running_clip():
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), OBS, [EXAMPLES["DonkeySlipped"]], 1.0, CFG)
    anim = update(anim, OBS, [EXAMPLES["DonkeyMoved"]], 1.5, CFG)   # HOP (2) < SLIP (3)
    assert anim.one_shot == Playing(Clip.SLIP_LEFT, 1.0)


def test_equal_or_higher_priority_cuts():
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), OBS, [EXAMPLES["DonkeyMoved"]], 1.0, CFG)
    assert update(anim, OBS, [EXAMPLES["DonkeyMoved"]], 1.5, CFG).one_shot == Playing(Clip.HOP, 1.5)
    assert update(anim, OBS, [EXAMPLES["DonkeySlipped"]], 1.5, CFG).one_shot == Playing(Clip.SLIP_LEFT, 1.5)


def test_after_a_clip_ends_any_clip_starts():
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), OBS, [EXAMPLES["DonkeySlipped"]], 1.0, CFG)
    later = 1.0 + duration_s(Clip.SLIP_LEFT, CFG)
    assert update(anim, OBS, [EXAMPLES["ItemCaught"]], later, CFG).one_shot == Playing(Clip.HAPPY, later)


def test_a_tick_without_events_changes_nothing_but_the_loop():
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), OBS, [EXAMPLES["DonkeyMoved"]], 1.0, CFG)
    assert update(anim, OBS, [], 1.5, CFG) == anim


def test_loop_restarts_only_when_it_changes():
    knee = observe(evolve(STATE, donkey=evolve(STATE.donkey, depth_state=DepthState.KNEE)), Role.DONKEY)
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), knee, [], 2.0, CFG)
    assert anim.loop == Playing(Clip.SCARED, 2.0)
    assert update(anim, knee, [], 2.5, CFG).loop == Playing(Clip.SCARED, 2.0)


@pytest.mark.parametrize(
    ("event", "facing_right"),
    [
        (DonkeyMoved(t=0, seq=0, from_cell=(0, 4), to_cell=(0, 3)), False),
        (DonkeyMoved(t=0, seq=0, from_cell=(0, 4), to_cell=(1, 4)), None),       # north: unchanged
        (DonkeyMoveStarted(t=0, seq=0, from_cell=(0, 4), to_cell=(0, 3), ticks=2), False),
        (DonkeyMoveStarted(t=0, seq=0, from_cell=(0, 4), to_cell=(0, 5), ticks=2), True),
    ],
)
def test_donkey_faces_its_last_sideways_move(event, facing_right):
    for start in (True, False):
        anim = evolve(new_animator(Role.DONKEY, OBS, 0.0), facing_right=start)
        expected = start if facing_right is None else facing_right
        assert update(anim, OBS, [event], 1.0, CFG).facing_right is expected


def test_shrek_faces_where_he_walks_and_ignores_the_donkey():
    anim = new_animator(Role.SHREK, OBS, 0.0)
    assert update(anim, OBS, [EXAMPLES["ShrekMoved"]], 1.0, CFG).facing_right is False   # 4 → 3: west
    assert update(anim, OBS, [EXAMPLES["DonkeyMoveStarted"]], 1.0, CFG).facing_right is True


def test_the_last_sideways_move_of_a_tick_wins():
    west, east = ShrekMoved(t=0, seq=0, from_col=4, to_col=3), ShrekMoved(t=0, seq=1, from_col=3, to_col=4)
    assert update(new_animator(Role.SHREK, OBS, 0.0), OBS, [west, east], 1.0, CFG).facing_right is True


# --- the swept donkey's ghost ----------------------------------------------------------------------------------

def test_sweep_leaves_a_ghost_while_the_donkey_respawns():
    events = [EXAMPLES["DonkeySwept"], EXAMPLES["DonkeyRespawned"]]
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), OBS, events, 5.0, CFG)
    ghost, cell = ghost_look(anim, 5.3, CFG)
    assert cell == (3, 6) and ghost.clip is Clip.SWEPT
    assert same(ghost.transform, pose(Clip.SWEPT, 0.3, CFG))
    assert at(anim, 5.3) is Clip.RESPAWN                       # the donkey itself, on the bank
    assert ghost_look(anim, 5.0 + duration_s(Clip.SWEPT, CFG), CFG) is None


def test_nothing_cuts_the_ghost():
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), OBS, [EXAMPLES["DonkeySwept"]], 5.0, CFG)
    anim = update(anim, OBS, [EXAMPLES["DonkeyMoved"], EXAMPLES["DonkeyRespawned"]], 5.5, CFG)
    assert anim.ghost == Playing(Clip.SWEPT, 5.0, cell=(3, 6))


def test_a_new_sweep_replaces_the_ghost():
    anim = update(new_animator(Role.DONKEY, OBS, 0.0), OBS, [EXAMPLES["DonkeySwept"]], 5.0, CFG)
    again = evolve(EXAMPLES["DonkeySwept"], row=1, col=2)
    assert update(anim, OBS, [again], 5.5, CFG).ghost == Playing(Clip.SWEPT, 5.5, cell=(1, 2))


def test_shrek_has_no_ghost():
    anim = update(new_animator(Role.SHREK, OBS, 0.0), OBS, [EXAMPLES["DonkeySwept"]], 5.0, CFG)
    assert anim.ghost is None and ghost_look(anim, 5.1, CFG) is None


# --- whole games -----------------------------------------------------------------------------------------------

TICKS = 120
games = st.lists(
    st.builds(
        Actions,
        donkey=st.sampled_from(DonkeyAction),
        shrek=st.builds(ShrekAction, move=st.sampled_from(ShrekMove), aim=st.sampled_from(Aim),
                        ability=st.sampled_from(Ability)),
    ),
    min_size=TICKS, max_size=TICKS,
)


@given(st.integers(0, 2**31 - 1), games, st.lists(st.floats(0, 1), min_size=TICKS, max_size=TICKS))
def test_random_games_always_have_a_drawable_look(seed, actions, frame_shares):
    state, rngs = new_game(CFG, seed)
    obs = observe(state, Role.DONKEY)
    anims = {role: new_animator(role, obs, 0.0) for role in Role}
    tick_s = CFG.time.tick_seconds
    for n, (tick_actions, share) in enumerate(zip(actions, frame_shares, strict=True)):
        if state.game_over is not None:
            break
        state, rngs, events = step(state, tick_actions, rngs)
        obs, now = observe(state, Role.DONKEY), (n + 1) * tick_s
        anims = {role: update(a, obs, events, now, CFG) for role, a in anims.items()}
        frame = now + share * tick_s
        for role, anim in anims.items():
            seen = look(anim, frame, CFG)
            assert seen.clip in CLIPS_OF[role]
            assert 0 <= seen.transform.alpha <= 1
            assert anim.loop.clip == loop_clip(role, obs)
        swept = [e for e in events if isinstance(e, DonkeySwept)]
        if swept:
            assert anims[Role.DONKEY].ghost == Playing(Clip.SWEPT, now, cell=(swept[-1].row, swept[-1].col))
