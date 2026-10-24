"""S-07: ROCK lands, without noise and in the same tick, on the aim cell.
Water cell → a temporary stone at h = rock_initial_h_cm (if fewer than rock_max_active exist, else ActionRejected);
permanent stone → r_i += rock_raise_cm; temporary stone → h += rock_raise_cm. In step 6 temporary stones sink
(also in their first tick) and vanish once h < rock_vanish_h_cm; r_i decays to 0. A donkey on a vanished stone
is swept (D-04); so is one whose slow move ends on it (D-05).
"""

import pytest

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.donkey import Bag, DepthState
from engine.events import (
    ActionRejected, DonkeyMoved, DonkeySwept, RaiseTarget, RejectReason, SweptCause, TempStoneRaised,
    TempStoneSpawned, TempStoneVanished,
)
from engine.stones import TempStone, temp_at

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
SH = CFG.shrek
LINE = ["..#..", ".....", "..#.."]  # Shrek and the donkey start in column 2, aiming at (0, 2): a stone
OPEN = ["....#", ".....", "..#.."]  # (0, 2) is water
ROCK = Actions(shrek=ShrekAction(ability=Ability.ROCK))
NOOP = Actions()
LIFETIME = 25  # MODEL A.6: born at 20 cm, sinks 1 cm/tick, gone below −5 cm


def of(trace, kind):
    return [e for e in trace.events if isinstance(e, kind)]


def test_rock_on_water_makes_a_temporary_stone():
    trace = run(CFG, 1, [ROCK], start=set_up(CFG, OPEN))
    assert of(trace, TempStoneSpawned) == [
        TempStoneSpawned(t=0, seq=0, stone_id=0, row=0, col=2, h=SH.rock_initial_h_cm)
    ]
    (stone,) = trace.states[0].stones.temp
    assert (stone.id, stone.row, stone.col, stone.spawned_at) == (0, 0, 2, 0)
    assert stone.h == SH.rock_initial_h_cm - SH.rock_sink_cm_per_tick  # step 6 of the same tick
    assert trace.states[0].stones.next_temp_id == 1


def test_rock_and_step_in_the_same_tick():
    # TICK.md timing example: step 2 (rock) comes before step 3 (move), so the move is valid.
    trace = run(CFG, 1, [Actions(donkey=DonkeyAction.MOVE_N, shrek=ShrekAction(ability=Ability.ROCK))],
                start=set_up(CFG, OPEN))
    assert [(e.from_cell, e.to_cell) for e in of(trace, DonkeyMoved)] == [((-1, 2), (0, 2))]
    assert of(trace, ActionRejected) == []


def test_the_aim_cell_after_walking_and_aiming():
    action = Actions(shrek=ShrekAction(move=ShrekMove.E, aim=Aim.UP, ability=Ability.ROCK))
    trace = run(CFG, 1, [action], start=set_up(CFG, OPEN))
    assert [(e.row, e.col) for e in of(trace, TempStoneSpawned)] == [(1, 3)]


def test_lifetime_matches_appendix_a6():
    trace = run(CFG, 1, [ROCK] + [NOOP] * 30, start=set_up(CFG, OPEN))
    alive = [len(s.stones.temp) for s in trace.states]
    assert alive == [1] * LIFETIME + [0] * 6
    assert [(e.t, e.stone_id, e.row, e.col, e.under_donkey) for e in of(trace, TempStoneVanished)] == [
        (LIFETIME, 0, 0, 2, False)
    ]


def test_rock_on_a_permanent_stone_raises_it_and_the_raise_decays():
    trace = run(CFG, 1, [ROCK] + [NOOP] * 12, start=set_up(CFG, LINE))
    assert [(e.row, e.col, e.delta_cm, e.target) for e in of(trace, TempStoneRaised)] == [
        (0, 2, SH.rock_raise_cm, RaiseTarget.STONE)
    ]
    raises = [float(s.stones.raise_h[0, 2]) for s in trace.states]
    assert raises == [9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.0]  # floor 0
    assert trace.states[0].stones.temp == ()


def test_the_raise_lifts_the_donkey():
    # D-01: e = h + r − load/k. Still water, h = 10, r = 9 after the rock tick: d = −(19 − 4).
    trace = run(CFG, 1, [ROCK], start=set_up(CFG, LINE, donkey={"row": 0, "col": 2}))
    assert trace.states[0].donkey.depth == pytest.approx(-15.0)


def test_rock_on_a_temporary_stone_refreshes_it():
    cfg = still({"map": {"rows": 3, "cols": 5}, "shrek": {"rock_cooldown_ticks": 0}})
    trace = run(cfg, 1, [ROCK, NOOP, ROCK], start=set_up(cfg, OPEN))
    assert [s.stones.temp[0].h for s in trace.states] == [19.0, 18.0, 27.0]
    assert [(e.t, e.target) for e in of(trace, TempStoneRaised)] == [(2, RaiseTarget.TEMP_STONE)]
    assert len(of(trace, TempStoneSpawned)) == 1


def test_cooldown_after_a_rock():
    n = SH.rock_cooldown_ticks
    trace = run(CFG, 1, [ROCK] * (n + 1), start=set_up(CFG, OPEN))
    rejected = [(e.t, e.reason) for e in of(trace, ActionRejected)]
    assert rejected == [(t, RejectReason.COOLDOWN) for t in range(1, n)]
    assert [e.t for e in of(trace, TempStoneRaised)] == [n]  # usable again n ticks after use (refresh)
    assert trace.states[0].shrek.rock_cooldown == n - 1


def test_rock_limit_blocks_spawning_only():
    cfg = still({"map": {"rows": 3, "cols": 5}, "shrek": {"rock_cooldown_ticks": 0, "rock_max_active": 2}})
    up, east = ShrekAction(aim=Aim.UP, ability=Ability.ROCK), ShrekAction(move=ShrekMove.E, ability=Ability.ROCK)
    plan = [ROCK, Actions(shrek=up), Actions(shrek=east), ROCK]  # (0,2), (1,2), (1,3) refused, then (1,3) again
    trace = run(cfg, 1, plan, start=set_up(cfg, OPEN))
    assert [(e.row, e.col) for e in of(trace, TempStoneSpawned)] == [(0, 2), (1, 2)]
    assert [(e.t, e.reason) for e in of(trace, ActionRejected)] == [(2, RejectReason.ROCK_LIMIT), (3, RejectReason.ROCK_LIMIT)]
    # Raising an existing stone is still allowed with the limit reached: walk back west, onto (1, 2).
    back = Actions(shrek=ShrekAction(move=ShrekMove.W, ability=Ability.ROCK))
    more = run(cfg, 1, [back], start=(trace.states[-1], trace.rngs[-1]))
    assert [e.target for e in of(more, TempStoneRaised)] == [RaiseTarget.TEMP_STONE]


def test_a_refused_rock_spends_no_cooldown():
    cfg = still({"map": {"rows": 3, "cols": 5, "path_guarantee": "none"}, "shrek": {"rock_max_active": 1}})
    start = set_up(cfg, OPEN, stones={"temp": (TempStone(id=0, row=1, col=2, h=20.0, spawned_at=0),), "next_temp_id": 1})
    trace = run(cfg, 1, [ROCK], start=start)
    assert [e.reason for e in of(trace, ActionRejected)] == [RejectReason.ROCK_LIMIT]
    assert trace.states[0].shrek.rock_cooldown == 0


def test_temp_at():
    stones = run(CFG, 1, [ROCK], start=set_up(CFG, OPEN)).states[0].stones
    assert temp_at(stones, 0, 2).id == 0 and temp_at(stones, 0, 3) is None


def test_a_donkey_on_a_vanishing_stone_is_swept():
    stone = TempStone(id=0, row=0, col=2, h=SH.rock_vanish_h_cm, spawned_at=0)  # sinks below the limit this tick
    start = set_up(CFG, OPEN, donkey={"row": 0, "col": 2}, stones={"temp": (stone,), "next_temp_id": 1})
    trace = run(CFG, 1, [NOOP], start=start)
    assert [type(e) for e in trace.events][:2] == [TempStoneVanished, DonkeySwept]
    assert of(trace, TempStoneVanished)[0].under_donkey
    swept = of(trace, DonkeySwept)[0]
    assert (swept.cause, swept.depth_cm, swept.row, swept.col) == (SweptCause.STONE_VANISHED, None, 0, 2)


def test_a_slow_move_onto_a_stone_that_vanishes_ends_in_the_water():
    # 2026-10-23 decision (D-05): the target is not checked again on arrival.
    cfg = still({"map": {"rows": 3, "cols": 5}})
    stone = TempStone(id=0, row=1, col=2, h=SH.rock_vanish_h_cm, spawned_at=0)  # gone in step 6 of tick 0
    start = set_up(cfg, ["..#..", ".....", "....."], {(0, 2): 2.0},
                   donkey={"row": 0, "col": 2, "depth_state": DepthState.ANKLE},
                   stones={"temp": (stone,), "next_temp_id": 1})
    trace = run(cfg, 1, [Actions(donkey=DonkeyAction.MOVE_N), NOOP], start=start)
    assert [e.t for e in of(trace, TempStoneVanished)] == [0]
    assert [(e.t, e.to_cell) for e in of(trace, DonkeyMoved)] == [(1, (1, 2))]
    assert [(e.t, e.cause) for e in of(trace, DonkeySwept)] == [(1, SweptCause.STONE_VANISHED)]


def test_a_temporary_stone_carries_the_donkey():
    # D-01 on a temporary stone: e = h(t) − load / rock_stiffness. Still water, h = 19 after the rock tick.
    # A rock stiffness unlike the map's 50 kg/cm, so that using the wrong one shows (found by a mutation).
    cfg = still({"map": {"rows": 3, "cols": 5}, "shrek": {"rock_stiffness_kg_per_cm": 40}})
    trace = run(cfg, 1, [Actions(donkey=DonkeyAction.MOVE_N, shrek=ShrekAction(ability=Ability.ROCK))],
                start=set_up(cfg, OPEN))
    assert trace.states[0].donkey.depth == pytest.approx(-(19.0 - 200 / 40))


def test_a_loaded_donkey_stays_dry_on_a_fresh_stone_for_14_ticks():
    # MODEL A.6: 200 + 60 kg on 50 kg/cm sinks 5.2 cm, DRY while h(t) > 5.2 cm in still water. The stone already
    # sinks in its first tick (step 6), so the engine gives 14 DRY ticks where the appendix rounds to ≈ 15.
    bag = Bag(items=(0,), mass=60.0, volume=1)
    step_on = Actions(donkey=DonkeyAction.MOVE_N, shrek=ShrekAction(ability=Ability.ROCK))
    trace = run(CFG, 1, [step_on] + [NOOP] * 20, start=set_up(CFG, OPEN, donkey={"bag_left": bag}))
    dry = [s.donkey.depth_state is DepthState.DRY for s in trace.states]
    assert dry.index(False) == 14


def test_two_stones_a_cooldown_apart_overlap_for_lifetime_minus_cooldown():
    # MODEL A.6: with cooldown 15, two temporary stones stand together for 25 − 15 = 10 ticks.
    second = Actions(shrek=ShrekAction(aim=Aim.UP, ability=Ability.ROCK))
    plan = [ROCK] + [NOOP] * (SH.rock_cooldown_ticks - 1) + [second] + [NOOP] * 30
    trace = run(CFG, 1, plan, start=set_up(CFG, OPEN))
    assert sum(len(s.stones.temp) == 2 for s in trace.states) == LIFETIME - SH.rock_cooldown_ticks == 10
