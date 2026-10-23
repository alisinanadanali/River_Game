"""ENTITIES.md GameState: an immutable value; new_game builds tick 0 and the five R-01 streams from a seed."""

import dataclasses

import pytest

from engine.config import load_config
from engine.rng import make_rngs
from engine.state import GameState, new_game
from engine.world import generate_world

CFG = load_config()


def test_tick_zero():
    state, _ = new_game(CFG, 42)
    assert (state.t, state.score, state.game_over) == (0, 0, None)


def test_carries_its_config():
    # step(state, actions, rngs) has no config argument (ADR-011); the rules read it from the state.
    state, _ = new_game(CFG, 42)
    assert state.config is CFG


def test_world_comes_from_the_seed():
    state, rngs = new_game(CFG, 42)
    world, after_world = generate_world(CFG.map, 42, make_rngs(42))
    assert state.world == world and rngs == after_world


def test_only_the_world_stream_is_used_before_tick_zero():
    _, rngs = new_game(CFG, 42)
    fresh = make_rngs(42)
    assert rngs.world != fresh.world
    assert (rngs.water, rngs.items, rngs.throw, rngs.slip) == (fresh.water, fresh.items, fresh.throw, fresh.slip)


def test_same_inputs_equal_states():
    assert new_game(CFG, 7) == new_game(CFG, 7)


def test_other_profile_other_state():
    state, _ = new_game(CFG, 7)
    hard, _ = new_game(load_config("hard"), 7)
    assert state != hard


def test_state_is_frozen():
    state, _ = new_game(CFG, 42)
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.t = 5


def test_fields_are_keyword_only():
    with pytest.raises(TypeError):
        GameState(CFG, None, None, None, 0, 0, None)


def test_repr_leaves_out_the_config():
    # A state is printed in every failing assertion; the full config would bury the fields that matter.
    state, _ = new_game(CFG, 42)
    assert "config" not in repr(state) and "t=0" in repr(state)


@pytest.mark.parametrize("seed", [-1, 1.5, "42", True])
def test_bad_seed_is_rejected(seed):
    with pytest.raises((TypeError, ValueError)):
        new_game(CFG, seed)
