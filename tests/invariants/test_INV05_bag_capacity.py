"""INV-05: no bag ever holds more than bag_max_kg_per_side or bag_max_volume_per_side (hypothesis, random play).

A huge catch radius and no throw cooldown make catches frequent, so bags fill and the limit really binds;
each bag's stored mass and volume must also equal the sum over the items it holds.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.events import ItemBounced, ItemCaught
from engine.items import ItemStatus

from tests.support import config_with, run

CFG = config_with({
    "items": {"arrival_rate_per_tick": 1.0},
    "shrek": {"catch_radius_cells": 30.0, "throw_cooldown_ticks": 0},
})
D = CFG.donkey
TICKS = CFG.time.game_length_ticks

actions = st.builds(
    Actions,
    donkey=st.sampled_from([DonkeyAction.STANCE_LEFT, DonkeyAction.STANCE_RIGHT, DonkeyAction.MOVE_N] + list(DonkeyAction)),
    shrek=st.builds(ShrekAction, move=st.just(ShrekMove.NONE), aim=st.sampled_from(Aim),
                    ability=st.sampled_from([Ability.THROW] * 3 + list(Ability))),
)


def check(state):
    types = CFG.items.types
    for bag in (state.donkey.bag_left, state.donkey.bag_right):
        assert bag.mass <= D.bag_max_kg_per_side and bag.volume <= D.bag_max_volume_per_side
        assert bag.mass == pytest.approx(sum(types[state.items[i].kind].mass_kg for i in bag.items))
        assert bag.volume == sum(types[state.items[i].kind].volume for i in bag.items)
        assert all(state.items[i].status is ItemStatus.IN_BAG for i in bag.items)


@given(seed=st.integers(0, 2**32 - 1), game=st.lists(actions, min_size=TICKS, max_size=TICKS))
def test_INV05_bags_never_overflow(seed, game):
    for state in run(CFG, seed, game).states:
        check(state)


def test_bags_really_fill_up():
    # Guards the property: on the first stone, in stance, catching every throw, the bags fill and items bounce.
    # A stance is taken every 4 ticks only: renewing it every tick would make every landing "too late" (D-08).
    stance = {0: DonkeyAction.STANCE_LEFT, 4: DonkeyAction.STANCE_RIGHT}
    plan = [Actions(donkey=DonkeyAction.MOVE_N)] + [
        Actions(donkey=stance.get(t % 8, DonkeyAction.NOOP), shrek=ShrekAction(ability=Ability.THROW)) for t in range(80)
    ]
    all_stones = config_with({
        "map": {"path_guarantee": "path", "stone_density": 1.0},
        "items": {"arrival_rate_per_tick": 1.0},
        "shrek": {"catch_radius_cells": 30.0, "throw_cooldown_ticks": 0},
    })
    trace = run(all_stones, 1, plan)
    assert any(isinstance(e, ItemCaught) for e in trace.events)
    assert any(isinstance(e, ItemBounced) for e in trace.events)
