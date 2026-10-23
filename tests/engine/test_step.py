"""TICK.md: step(state, actions, rngs) -> (new_state, new_rngs, events) runs steps 0 … 12 in this order (ADR-011)."""

import re
from pathlib import Path

import pytest

from engine.actions import Actions
from engine.config import load_config
from engine.events import GameOver, GameOverReason
from engine.rng import make_rngs
from engine.state import new_game
from engine.step import PIPELINE, GameFinishedError, step

from tests.support import config_with, run

CFG = load_config()
TICK_DOC = (Path(__file__).resolve().parents[2] / "docs" / "TICK.md").read_text(encoding="utf-8")


def tick_doc_summary() -> dict[int, str]:
    """TICK.md summary table: step number -> its Rules (Kurallar) column, as written."""
    rows = re.findall(r"^\| (\d+) \| [^|]+ \| ([^|]+) \|", TICK_DOC, flags=re.MULTILINE)
    return {int(number): rules.strip() for number, rules in rows}


# --- the pipeline matches TICK.md -------------------------------------------------------

def test_tick_doc_has_steps_0_to_12():
    assert list(tick_doc_summary()) == list(range(13))


def test_pipeline_has_one_stage_per_tick_step():
    assert len(PIPELINE) == len(tick_doc_summary())


@pytest.mark.parametrize("number", range(13))
def test_stage_n_says_it_is_tick_step_n(number):
    doc = PIPELINE[number].__doc__ or ""
    assert doc.startswith(f"TICK.md step {number}:"), PIPELINE[number].__name__


@pytest.mark.parametrize("number", range(13))
def test_stage_cites_the_rules_of_its_tick_row(number):
    # A rule moved to another step in TICK.md must move in the code too, and the other way round.
    rules = tick_doc_summary()[number]
    doc = PIPELINE[number].__doc__ or ""
    assert f"Rules: {rules}." in doc, f"{PIPELINE[number].__name__} should cite 'Rules: {rules}.'"


def test_stage_names_are_unique():
    assert len({stage.__name__ for stage in PIPELINE}) == len(PIPELINE)


# --- what one step does -----------------------------------------------------------------------

def test_one_step_advances_the_clock():
    state, rngs = new_game(CFG, 42)
    new_state, _, events = step(state, Actions(), rngs)
    assert new_state.t == 1 and events == ()


def test_inputs_are_not_changed():
    state, rngs = new_game(CFG, 42)
    step(state, Actions(), rngs)
    assert (state, rngs) == new_game(CFG, 42)


def test_returns_new_streams():
    # ADR-011 risk: a step that returned the old streams would repeat the same numbers every tick.
    state, rngs = new_game(CFG, 42)
    _, rngs1, _ = step(state, Actions(), rngs)
    _, rngs2, _ = step(state, Actions(), rngs1)
    assert len({rngs, rngs1, rngs2}) == 3


def test_events_is_a_tuple():
    # Returned events cannot be appended to by a consumer.
    state, rngs = new_game(CFG, 42)
    assert isinstance(step(state, Actions(), rngs)[2], tuple)


def test_config_is_carried_along():
    state, rngs = new_game(CFG, 42)
    assert step(state, Actions(), rngs)[0].config is CFG


# --- game over by time (TICK.md step 11) ------------------------------------------------------

SHORT = config_with({"time": {"game_length_ticks": 3}})


def test_game_over_on_the_last_tick():
    trace = run(SHORT, 42, [Actions()] * 3)
    assert [s.t for s in trace.states] == [1, 2, 3]
    assert [s.game_over for s in trace.states] == [None, None, GameOverReason.TIME]
    assert trace.events == (GameOver(t=2, seq=0, reason=GameOverReason.TIME, score=0),)


def test_step_after_game_over_is_an_error():
    trace = run(SHORT, 42, [Actions()] * 3)
    with pytest.raises(GameFinishedError):
        step(trace.states[-1], Actions(), trace.rngs[-1])


def test_one_tick_game():
    trace = run(config_with({"time": {"game_length_ticks": 1}}), 42, [Actions()])
    assert trace.events == (GameOver(t=0, seq=0, reason=GameOverReason.TIME, score=0),)


def test_full_default_game_ends_at_its_length():
    trace = run(CFG, 42, [Actions()] * CFG.time.game_length_ticks)
    assert trace.states[-1].t == CFG.time.game_length_ticks
    assert [e.type for e in trace.events if e.type == "GameOver"] == ["GameOver"]
    assert trace.events[-1].type == "GameOver"


def test_streams_differ_between_seeds():
    state, _ = new_game(CFG, 0)
    assert step(state, Actions(), make_rngs(1))[1] != step(state, Actions(), make_rngs(2))[1]
