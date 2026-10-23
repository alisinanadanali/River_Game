"""S-03: at most one ability per tick; walking is invalid while the dam is held this tick (test_S08_*); an ability
with cooldown > 0 or an unmet condition is a no-op (ActionRejected) and spends no cooldown. Cooldowns count down in
step 11, so a cooldown of n means usable again n ticks after use. (ROCK: test_S07_*; THROW: test_S04_*.)
"""

import dataclasses

from engine.actions import Ability, Actions, ShrekAction
from engine.shrek import Shrek, cool_down
from engine.state import new_game

from tests.support import run, still

CFG = still()


def test_the_action_space_allows_one_ability():
    # A ShrekAction has a single ability component, so two abilities in one tick cannot even be written.
    assert [f.name for f in dataclasses.fields(ShrekAction)] == ["move", "aim", "ability"]


def test_cooldowns_count_down_to_zero_in_step_11():
    state, rngs = new_game(CFG, 1)
    state = dataclasses.replace(state, shrek=dataclasses.replace(state.shrek, throw_cooldown=3, rock_cooldown=1))
    trace = run(CFG, 1, [Actions()] * 4, start=(state, rngs))
    assert [(s.shrek.throw_cooldown, s.shrek.rock_cooldown) for s in trace.states] == [(2, 0), (1, 0), (0, 0), (0, 0)]


def test_cool_down_is_pure():
    shrek = Shrek(col=0, aim_row=0, throw_cooldown=2, rock_cooldown=0)
    assert cool_down(shrek) == Shrek(col=0, aim_row=0, throw_cooldown=1, rock_cooldown=0)
    assert shrek.throw_cooldown == 2
    assert cool_down(Shrek(col=0, aim_row=0)) == Shrek(col=0, aim_row=0)


def test_the_dam_has_no_cooldown():
    trace = run(CFG, 1, [Actions(shrek=ShrekAction(ability=Ability.DAM))] * 3)
    assert {(s.shrek.throw_cooldown, s.shrek.rock_cooldown) for s in trace.states} == {(0, 0)}
