"""MODEL.md §1: A_D has 7 discrete actions, A_S is the multi-discrete triple (move, aim, ability), 3·3·4 = 36."""

import dataclasses
import itertools

import pytest

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove


def test_donkey_actions_in_model_doc_order():
    # The order is the RL encoding (index = action id), so it is part of the contract.
    assert [a.value for a in DonkeyAction] == [
        "NOOP", "MOVE_N", "MOVE_S", "MOVE_E", "MOVE_W", "STANCE_LEFT", "STANCE_RIGHT",
    ]


def test_shrek_components_in_model_doc_order():
    assert [m.value for m in ShrekMove] == ["NONE", "W", "E"]
    assert [a.value for a in Aim] == ["NONE", "UP", "DOWN"]
    assert [a.value for a in Ability] == ["NONE", "THROW", "ROCK", "DAM"]


def test_shrek_has_36_distinct_actions():
    combos = {ShrekAction(move=m, aim=a, ability=b) for m, a, b in itertools.product(ShrekMove, Aim, Ability)}
    assert len(combos) == 36


def test_defaults_do_nothing():
    assert ShrekAction() == ShrekAction(move=ShrekMove.NONE, aim=Aim.NONE, ability=Ability.NONE)
    assert Actions() == Actions(donkey=DonkeyAction.NOOP, shrek=ShrekAction())


@pytest.mark.parametrize("value", [ShrekAction(), Actions()])
def test_actions_are_frozen(value):
    field = dataclasses.fields(value)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(value, field, None)


def test_actions_are_hashable():
    # Usable as dict keys / set members, e.g. a Q-table indexed by action.
    assert len({Actions(), Actions(), Actions(donkey=DonkeyAction.MOVE_N)}) == 2
