"""INV-02 as a property (hypothesis): for any seed and any action sequence, a game is reproducible bit for bit.

ROADMAP Phase 0 acceptance: >= 200 seeds x 300 ticks with random actions, met by the `full` hypothesis profile
(tests/conftest.py). Each example plays one full default game twice, and once more from a random saved tick
(ADR-011 branching).
"""

from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import load_config

from tests.support import run

CFG = load_config()
TICKS = CFG.time.game_length_ticks

seeds = st.integers(min_value=0, max_value=2**64 - 1)
actions = st.builds(
    Actions,
    donkey=st.sampled_from(DonkeyAction),
    shrek=st.builds(
        ShrekAction, move=st.sampled_from(ShrekMove), aim=st.sampled_from(Aim), ability=st.sampled_from(Ability)
    ),
)
games = st.lists(actions, min_size=TICKS, max_size=TICKS)


@given(seed=seeds, game=games, k=st.integers(min_value=1, max_value=TICKS - 1))
def test_any_game_replays_bit_for_bit(seed, game, k):
    a = run(CFG, seed, game)
    b = run(CFG, seed, game)
    assert a.jsonl == b.jsonl
    assert a.states == b.states and a.rngs == b.rngs

    # A game lost by lives (D-07) is shorter; branching from its last state must then yield nothing more.
    k = min(k, len(a.states))
    rest = run(CFG, seed, game[k:], start=(a.states[k - 1], a.rngs[k - 1]))
    assert rest.states == a.states[k:] and rest.rngs == a.rngs[k:]
    assert rest.events == tuple(e for e in a.events if e.t >= k)


@given(seed=seeds)
def test_any_seed_plays_a_full_game(seed):
    # A donkey that never leaves the bank cannot be swept: every game runs to its length and ends by time once.
    trace = run(CFG, seed, [Actions()] * TICKS)
    assert [s.t for s in trace.states] == list(range(1, TICKS + 1))
    assert [(e.type, e.t) for e in trace.events if e.type == "GameOver"] == [("GameOver", TICKS - 1)]
