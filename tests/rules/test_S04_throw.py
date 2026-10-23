"""S-04: THROW sends the head of the bank queue towards the aim cell. The landing point is drawn at the throw:
landing = target + σ·(z₁, z₂) with z = u_throw (rng_throw block) and σ = σ₀ + σ₁·(aim_row + 1) + σ₂·m.
The projectile does not move in its throw tick, so with throw_flight_ticks = 2 a throw at t lands at t + 2.
"""

import pytest

from engine.actions import Ability, Actions, Aim, ShrekAction
from engine.events import ActionRejected, DamReleased, ItemThrown, ProjectileKind, RejectReason
from engine.items import Bank, Item, ItemStatus
from engine.rng import draw_blocks
from engine.shrek import throw_sigma

from tests.support import HOLD_DAM, config_with, run, set_up, still

CFG = still()
SH = CFG.shrek
LINE = ["...." + "#" + "...."] * 9
THROW = Actions(shrek=ShrekAction(ability=Ability.THROW))


def loaded(kinds=("watermelon",), cfg=CFG, **fields):
    """Hand-made map with these items waiting on the bank (ids 0, 1, …)."""
    items = tuple(Item(id=i, kind=k, status=ItemStatus.ON_BANK) for i, k in enumerate(kinds))
    return set_up(cfg, LINE, items=items, bank=Bank(queue=tuple(range(len(kinds)))), **fields)


def of(trace, kind):
    return [e for e in trace.events if isinstance(e, kind)]


@pytest.mark.parametrize(("aim_row", "mass"), [(0, 10.0), (4, 30.0), (8, 50.0)])
def test_sigma(aim_row, mass):
    assert throw_sigma(aim_row, mass, SH) == pytest.approx(
        SH.throw_sigma0_cells + SH.throw_sigma_per_row_cells * (aim_row + 1) + SH.throw_sigma_per_kg_cells * mass
    )


def test_throw_takes_the_head_of_the_queue():
    start = loaded(("watermelon", "apple_crate"), donkey={"col": 0})  # donkey away: no handoff
    trace = run(CFG, 1, [THROW], start=start)
    (thrown,) = of(trace, ItemThrown)
    assert (thrown.item_id, thrown.kind, thrown.from_col, thrown.target) == (0, ProjectileKind.THROW, 4, (0, 4))
    assert thrown.flight_ticks == SH.throw_flight_ticks
    assert thrown.sigma == pytest.approx(throw_sigma(0, 50.0, SH))
    state = trace.states[0]
    assert state.bank.queue == (1,) and state.items[0].status is ItemStatus.IN_FLIGHT
    (p,) = state.projectiles
    assert (p.item_id, p.thrown_at, p.ticks_left) == (0, 0, SH.throw_flight_ticks)  # not moved in its tick


def test_landing_is_drawn_from_this_ticks_throw_block():
    state, rngs = loaded(donkey={"col": 0})
    u_throw, _, _ = draw_blocks(rngs)  # TICK.md step 0 of the same tick
    sigma = throw_sigma(0, 50.0, SH)
    trace = run(CFG, 1, [THROW], start=(state, rngs))
    assert trace.states[0].projectiles[0].landing == pytest.approx((0 + sigma * u_throw[0], 4 + sigma * u_throw[1]))


def test_aim_comes_first():
    trace = run(CFG, 1, [Actions(shrek=ShrekAction(aim=Aim.UP, ability=Ability.THROW))], start=loaded(donkey={"col": 0}))
    assert of(trace, ItemThrown)[0].target == (1, 4)


def test_cooldown_after_a_throw():
    n = SH.throw_cooldown_ticks
    trace = run(CFG, 1, [THROW] * (n + 1), start=loaded(("apple_crate",) * 3, donkey={"col": 0}))
    assert [e.t for e in of(trace, ItemThrown)] == [0, n]
    assert [(e.t, e.reason) for e in of(trace, ActionRejected)] == [(t, RejectReason.COOLDOWN) for t in range(1, n)]


def test_empty_queue_is_rejected_and_spends_no_cooldown():
    trace = run(CFG, 1, [THROW], start=set_up(CFG, LINE))
    assert [e.reason for e in of(trace, ActionRejected)] == [RejectReason.QUEUE_EMPTY]
    assert trace.states[0].shrek.throw_cooldown == 0 and of(trace, ItemThrown) == []


def test_release_and_throw_in_one_tick():
    trace = run(CFG, 1, [HOLD_DAM, THROW], start=loaded(donkey={"col": 0}))
    assert [type(e) for e in trace.events if e.t == 1][:3][0] is DamReleased
    assert [e.t for e in of(trace, ItemThrown)] == [1]


def test_lands_two_ticks_later():
    cfg = config_with({"water": {"wave_rate_per_tick": 0.0}, "items": {"arrival_rate_per_tick": 0.0}})
    trace = run(cfg, 1, [THROW, Actions(), Actions()], start=loaded(cfg=cfg, donkey={"col": 0}))
    assert [len(s.projectiles) for s in trace.states] == [1, 1, 0]
    assert trace.states[2].items[0].status is not ItemStatus.IN_FLIGHT
