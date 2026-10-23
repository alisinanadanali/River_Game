"""engine/evolve.py: a fast dataclasses.replace for the engine's frozen state objects (ROADMAP Phase 0 speed)."""

import dataclasses

import pytest

from engine.config import load_config
from engine.evolve import evolve
from engine.state import new_game

STATE, RNGS = new_game(load_config(), 42)


def test_same_result_as_dataclasses_replace():
    assert evolve(STATE, t=7, score=3) == dataclasses.replace(STATE, t=7, score=3)


def test_the_original_is_not_changed():
    evolve(STATE, t=7)
    assert STATE.t == 0


def test_the_copy_is_a_new_frozen_object_of_the_same_type():
    copy = evolve(STATE, t=7)
    assert copy is not STATE and type(copy) is type(STATE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        copy.t = 8


def test_unknown_field_is_an_error():
    # A typo would otherwise add an attribute that __eq__ ignores: a silent bug in INV-02 comparisons.
    with pytest.raises(TypeError, match="scroe"):
        evolve(STATE, scroe=1)


def test_no_changes_still_copies():
    assert evolve(STATE) == STATE and evolve(STATE) is not STATE


def test_works_on_content_compared_objects():
    # World and Water define their own __eq__ over numpy arrays.
    assert evolve(STATE.water, next_wave_id=5) == dataclasses.replace(STATE.water, next_wave_id=5)
