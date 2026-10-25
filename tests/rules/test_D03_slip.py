"""D-03: when a move starts from a stone with something in the bags, the donkey slips if u_slip[0] < p_slip,
p_slip = min(1, p₀ + κ·δ²·μ) (μ = mossy_slip_multiplier on a mossy permanent stone, else 1; no check when leaving a
bank). The top item of the heavy side falls into the cell being left (DonkeySlipped, ItemDropped(slip), I-04);
the move still happens.
"""

import math

import pytest

from engine.actions import Actions, DonkeyAction
from engine.donkey import Bag, Side, slip_probability, slip_risk
from engine.events import DonkeyMoved, DonkeySlipped, DropCause, ItemDropped, ItemFloated
from engine.items import Item, ItemStatus
from engine.rng import draw_blocks
from engine.step import step
from engine.stones import TempStone

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
D = CFG.donkey
LINE = ["..#m.", "..#..", "..#.."]  # (0, 3) is mossy
E, W, N = (Actions(donkey=a) for a in (DonkeyAction.MOVE_E, DonkeyAction.MOVE_W, DonkeyAction.MOVE_N))
WATERMELON_LEFT = {"bag_left": Bag(items=(0,), mass=50.0, volume=3)}
ITEMS = (Item(id=0, kind="watermelon", status=ItemStatus.IN_BAG),)


def always(cfg_extra=None):
    """A config where every check slips (p₀ = 1)."""
    return still({"map": {"rows": 3, "cols": 5}, "donkey": {"slip_base_prob": 1.0}, **(cfg_extra or {})})


def test_formula_and_cap():
    assert slip_probability(0.2, 1.0, D) == pytest.approx(D.slip_base_prob + D.slip_kappa * 0.04)
    assert slip_probability(0.2, 3.0, D) == pytest.approx(D.slip_base_prob + D.slip_kappa * 0.04 * 3)
    assert slip_probability(0.9, 3.0, D) == 1.0


def test_a_slip_drops_the_top_of_the_heavy_side_into_the_cell_left():
    cfg = always()
    start = set_up(cfg, LINE, items=ITEMS, donkey={"row": 0, "col": 2, **WATERMELON_LEFT})
    trace = run(cfg, 1, [N], start=start)
    names = [type(e).__name__ for e in trace.events]
    assert names[:4] == ["DonkeySlipped", "ItemDropped", "ItemFloated", "DonkeyMoved"]
    slipped = trace.events[0]
    assert (slipped.side, slipped.mossy) == (Side.LEFT, False) and slipped.p_slip == 1.0
    assert slipped.delta == pytest.approx(-50 / 250)
    assert [(e.item_id, e.side, e.cause) for e in trace.events if isinstance(e, ItemDropped)] == [(0, Side.LEFT, DropCause.SLIP)]
    assert [(e.row, e.x) for e in trace.events if isinstance(e, ItemFloated)] == [(0, 2.0)]  # the cell left
    assert (trace.states[0].donkey.row, trace.states[0].donkey.bag_left) == (1, Bag())


def test_no_slip_when_leaving_a_bank():
    cfg = always()
    start = set_up(cfg, LINE, items=ITEMS, donkey=WATERMELON_LEFT)
    trace = run(cfg, 1, [N], start=start)
    assert not any(isinstance(e, DonkeySlipped) for e in trace.events)


def test_no_slip_with_empty_bags():
    cfg = always()
    trace = run(cfg, 1, [N], start=set_up(cfg, LINE, donkey={"row": 0, "col": 2}))
    assert not any(isinstance(e, DonkeySlipped) for e in trace.events)


def test_no_slip_on_a_rejected_move():
    cfg = always()
    trace = run(cfg, 1, [W], start=set_up(cfg, LINE, items=ITEMS, donkey={"row": 0, "col": 2, **WATERMELON_LEFT}))
    assert not any(isinstance(e, DonkeySlipped) for e in trace.events)


def test_u_slip_0_decides():
    # p = p₀ + κ·0.04 = 0.09 for a 50 kg imbalance: compare with this tick's u_slip[0].
    for seed in range(40):
        state, rngs = set_up(CFG, LINE, seed=seed, items=ITEMS, donkey={"row": 0, "col": 2, **WATERMELON_LEFT})
        _, u_slip, _ = draw_blocks(rngs)
        trace = run(CFG, seed, [E], start=(state, rngs))
        p = slip_probability(-0.2, 1.0, D)
        assert any(isinstance(e, DonkeySlipped) for e in trace.events) is bool(u_slip[0] < p)


def test_mossy_stone_uses_the_multiplier():
    cfg = always()
    start = set_up(cfg, LINE, items=ITEMS, donkey={"row": 0, "col": 3, **WATERMELON_LEFT})
    slipped = next(e for e in run(cfg, 1, [W], start=start).events if isinstance(e, DonkeySlipped))
    assert slipped.mossy is True


@pytest.mark.parametrize(("col", "mu"), [(3, 3.0), (2, 1.0)])
def test_the_multiplier_reaches_p_slip(col, mu):
    # p₀ = 0, κ = 8, δ = −0.2: p = 0.32·μ, so the event shows which μ the engine used (found by a mutation:
    # with p₀ = 1 every p is capped at 1 and μ cannot be seen).
    cfg = still({"map": {"rows": 3, "cols": 5}, "donkey": {"slip_base_prob": 0.0, "slip_kappa": 8.0}})
    move = W if col == 3 else E
    for seed in range(20):
        start = set_up(cfg, LINE, seed=seed, items=ITEMS, donkey={"row": 0, "col": col, **WATERMELON_LEFT})
        slipped = [e for e in run(cfg, seed, [move], start=start).events if isinstance(e, DonkeySlipped)]
        if slipped:
            assert slipped[0].p_slip == pytest.approx(8.0 * 0.04 * mu)
            return
    raise AssertionError("no slip in 20 seeds")


def test_a_temporary_stone_has_multiplier_one():
    stone = TempStone(id=0, row=1, col=3, h=20.0, spawned_at=0)
    cfg = always()
    start = set_up(cfg, LINE, items=ITEMS, donkey={"row": 1, "col": 3, **WATERMELON_LEFT},
                   stones={"temp": (stone,), "next_temp_id": 1})
    slipped = next(e for e in run(cfg, 1, [W], start=start).events if isinstance(e, DonkeySlipped))
    assert slipped.mossy is False


def test_balanced_bags_use_the_coin():
    items = (Item(id=0, kind="potato_sack", status=ItemStatus.IN_BAG), Item(id=1, kind="potato_sack", status=ItemStatus.IN_BAG))
    bags = {"bag_left": Bag(items=(0,), mass=30.0, volume=2), "bag_right": Bag(items=(1,), mass=30.0, volume=2)}
    cfg = always()
    sides = set()
    for seed in range(30):
        state, rngs = set_up(cfg, LINE, seed=seed, items=items, donkey={"row": 0, "col": 2, **bags})
        _, u_slip, _ = draw_blocks(rngs)
        slipped = next(e for e in run(cfg, seed, [N], start=(state, rngs)).events if isinstance(e, DonkeySlipped))
        assert slipped.side is (Side.LEFT if u_slip[1] < 0.5 else Side.RIGHT)
        sides.add(slipped.side)
    assert sides == {Side.LEFT, Side.RIGHT}


def test_the_move_still_happens():
    cfg = always()
    trace = run(cfg, 1, [N], start=set_up(cfg, LINE, items=ITEMS, donkey={"row": 0, "col": 2, **WATERMELON_LEFT}))
    assert [(e.from_cell, e.to_cell) for e in trace.events if isinstance(e, DonkeyMoved)] == [((0, 2), (1, 2))]


def test_slip_rate_through_the_engine():
    # 3000 independent first steps off a stone with 50 kg on the left: slip frequency within 4 SE of 0.09.
    n, slips = 3000, 0
    state, rngs = set_up(CFG, LINE, items=ITEMS, donkey={"row": 0, "col": 2, **WATERMELON_LEFT})
    for _ in range(n):
        _, rngs, events = step(state, E, rngs)
        slips += any(isinstance(e, DonkeySlipped) for e in events)
    p = slip_probability(-0.2, 1.0, D)
    assert abs(slips / n - p) < 4 * math.sqrt(p * (1 - p) / n)


# --- slip_risk: the next move's p_slip, without drawing (read by the HUD, VISUALS §5) ------------------------------

KAPPA8 = still({"map": {"rows": 3, "cols": 5}, "donkey": {"slip_base_prob": 0.0, "slip_kappa": 8.0}})
TEMP = TempStone(id=0, row=1, col=3, h=20.0, spawned_at=0)


@pytest.mark.parametrize(("donkey", "temp", "expected"), [
    ({**WATERMELON_LEFT}, (), (0.0, False)),                                    # on the bank
    ({"row": 0, "col": 2}, (), (0.0, False)),                                  # empty bags
    ({"row": 0, "col": 2, **WATERMELON_LEFT}, (), (8.0 * 0.04, False)),
    ({"row": 0, "col": 3, **WATERMELON_LEFT}, (), (8.0 * 0.04 * 3.0, True)),   # mossy
    ({"row": 1, "col": 3, **WATERMELON_LEFT}, (TEMP,), (8.0 * 0.04, False)),   # a temporary stone
])
def test_slip_risk_is_the_next_moves_p_slip(donkey, temp, expected):
    state, _ = set_up(KAPPA8, LINE, items=ITEMS, donkey=donkey, stones={"temp": temp, "next_temp_id": len(temp)})
    p, mossy = slip_risk(state.world, state.donkey, KAPPA8)
    assert (p, mossy) == (pytest.approx(expected[0]), expected[1])


def test_slip_risk_is_what_the_engine_draws_against():
    for seed in range(20):
        start = set_up(KAPPA8, LINE, seed=seed, items=ITEMS, donkey={"row": 0, "col": 3, **WATERMELON_LEFT})
        slipped = [e for e in run(KAPPA8, seed, [W], start=start).events if isinstance(e, DonkeySlipped)]
        if slipped:
            assert (slipped[0].p_slip, slipped[0].mossy) == slip_risk(start[0].world, start[0].donkey, KAPPA8)
            return
    raise AssertionError("no slip in 20 seeds")
