"""INV-06: lives go down only in a tick with DonkeySwept, and then by exactly 1 (hypothesis, random actions)."""

from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Actions, DonkeyAction
from engine.events import DonkeySwept, LifeLost
from engine.state import new_game

from tests.support import config_with, run

# Rough water and a donkey that mostly heads north: random games that really lose lives.
CFG = config_with({"water": {"wave_rate_per_tick": 0.3, "wave_amp_mean_cm": 20}})
TICKS = CFG.time.game_length_ticks

donkey_actions = st.sampled_from([DonkeyAction.MOVE_N] * 4 + list(DonkeyAction))
games = st.lists(st.builds(Actions, donkey=donkey_actions), min_size=TICKS, max_size=TICKS)


def lives_story(seed, game):
    trace = run(CFG, seed, game)
    lives = [new_game(CFG, seed)[0].donkey.lives] + [s.donkey.lives for s in trace.states]
    swept = [sum(isinstance(e, DonkeySwept) for e in trace.events if e.t == t) for t in range(len(trace.states))]
    return trace, lives, swept


@given(seed=st.integers(0, 2**32 - 1), game=games)
def test_INV06_lives_drop_by_one_exactly_when_swept(seed, game):
    trace, lives, swept = lives_story(seed, game)
    for t, n in enumerate(swept):
        assert n in (0, 1)
        assert lives[t] - lives[t + 1] == n
    # Every LifeLost tells the lives left after its tick, and comes with a DonkeySwept.
    for e in trace.events:
        if isinstance(e, LifeLost):
            assert e.lives_left == lives[e.t + 1] and swept[e.t] == 1


def test_these_games_really_lose_lives():
    # Guards the property: on this water a donkey walking north is swept within a game.
    _, lives, swept = lives_story(1, [Actions(donkey=DonkeyAction.MOVE_N)] * TICKS)
    assert sum(swept) >= 1 and lives[-1] < lives[0]
