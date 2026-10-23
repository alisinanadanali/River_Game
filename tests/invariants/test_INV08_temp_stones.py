"""INV-08 (stone part): at the end of every tick there are at most rock_max_active temporary stones (hypothesis).

Random Shrek play with no rock cooldown, so the limit is hit often; the Q part is in test_INV03_INV04_INV08_water.py.
"""

from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, ShrekAction, ShrekMove
from engine.events import ActionRejected, RejectReason

from tests.support import config_with, run

CFG = config_with({"shrek": {"rock_cooldown_ticks": 0}})
TICKS = CFG.time.game_length_ticks

shrek_actions = st.builds(
    ShrekAction,
    move=st.sampled_from(ShrekMove),
    aim=st.sampled_from(Aim),
    ability=st.sampled_from([Ability.ROCK] * 3 + list(Ability)),
)
games = st.lists(st.builds(Actions, shrek=shrek_actions), min_size=TICKS, max_size=TICKS)


@given(seed=st.integers(0, 2**32 - 1), game=games)
def test_INV08_temporary_stones_never_exceed_the_limit(seed, game):
    for state in run(CFG, seed, game).states:
        assert len(state.stones.temp) <= CFG.shrek.rock_max_active
        ids = [s.id for s in state.stones.temp]
        assert ids == sorted(set(ids)) and all(i < state.stones.next_temp_id for i in ids)


def test_the_limit_is_really_reached():
    # Guards the property: rocks every tick on rows of water must run into rock_limit.
    up = Actions(shrek=ShrekAction(aim=Aim.UP, ability=Ability.ROCK))
    events = run(CFG, 1, [up] * 20).events
    assert any(isinstance(e, ActionRejected) and e.reason is RejectReason.ROCK_LIMIT for e in events)
