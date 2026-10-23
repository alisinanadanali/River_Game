"""MODEL Appendix A.6 (rock lifetime) reproduced with the engine itself: lifetime 25 ticks, a loaded donkey stays
DRY on a fresh temporary stone for about 15 ticks, and with cooldown 15 two stones overlap for 10 ticks.
"""

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction
from engine.donkey import Bag, DepthState

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
SH = CFG.shrek
OPEN = ["....#", ".....", "..#.."]
ROCK = Actions(shrek=ShrekAction(ability=Ability.ROCK))


def test_lifetime_is_25_ticks():
    assert (SH.rock_initial_h_cm - SH.rock_vanish_h_cm) / SH.rock_sink_cm_per_tick == 25
    trace = run(CFG, 1, [ROCK] + [Actions()] * 30, start=set_up(CFG, OPEN))
    assert sum(len(s.stones.temp) for s in trace.states) == 25


def test_a_loaded_donkey_stays_dry_for_about_15_ticks():
    # 200 + 60 kg on 50 kg/cm sinks 5.2 cm: DRY while h(t) > 5.2 cm in still water. The stone already sinks in its
    # first tick (S-07, step 6), so the engine gives 14 DRY ticks where the appendix rounds to ≈ 15.
    bag = Bag(items=(0,), mass=60.0, volume=1)
    step_on = Actions(donkey=DonkeyAction.MOVE_N, shrek=ShrekAction(ability=Ability.ROCK))
    trace = run(CFG, 1, [step_on] + [Actions()] * 20, start=set_up(CFG, OPEN, donkey={"bag_left": bag}))
    dry = [s.donkey.depth_state is DepthState.DRY for s in trace.states]
    assert dry.index(False) == 14
    assert abs(dry.index(False) - 15) <= 1


def test_cooldown_15_gives_10_ticks_of_overlap():
    second = Actions(shrek=ShrekAction(aim=Aim.UP, ability=Ability.ROCK))
    plan = [ROCK] + [Actions()] * (SH.rock_cooldown_ticks - 1) + [second] + [Actions()] * 30
    trace = run(CFG, 1, plan, start=set_up(CFG, OPEN))
    assert sum(len(s.stones.temp) == 2 for s in trace.states) == 25 - SH.rock_cooldown_ticks == 10
