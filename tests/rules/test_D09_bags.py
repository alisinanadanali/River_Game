"""D-09: two LIFO bags; an item goes into a side only if mass + m ≤ bag_max_kg_per_side and volume + v ≤
bag_max_volume_per_side. The limits are never exceeded (INV-05, tests/invariants/test_INV05_bag_capacity.py).
"""

import pytest

from engine.donkey import Bag, fits, pop, push

from tests.support import config_with

D = config_with({}).donkey  # 60 kg and 4 volume units per side


@pytest.mark.parametrize(
    ("bag", "mass", "volume", "ok"),
    [
        (Bag(), 50, 3, True),
        (Bag(), 60, 4, True),                                  # exactly full is allowed
        (Bag(), 61, 1, False),
        (Bag(), 10, 5, False),
        (Bag(items=(0,), mass=50.0, volume=3), 10, 1, True),
        (Bag(items=(0,), mass=50.0, volume=3), 10, 2, False),  # volume decides
        (Bag(items=(0,), mass=30.0, volume=2), 50, 1, False),  # mass decides
    ],
)
def test_fits(bag, mass, volume, ok):
    assert fits(bag, mass, volume, D) is ok


def test_push_and_pop_are_lifo():
    bag = push(push(Bag(), 3, 10.0, 1), 7, 30.0, 2)
    assert bag == Bag(items=(3, 7), mass=40.0, volume=3)
    top, rest = pop(bag, 30.0, 2)
    assert (top, rest) == (7, Bag(items=(3,), mass=10.0, volume=1))


def test_pop_of_an_empty_bag_is_a_bug():
    with pytest.raises(ValueError):
        pop(Bag(), 10.0, 1)
