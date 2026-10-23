"""D-01: on stone i the donkey stands at e_i = h_i + r_i(t) − (m_D + M_bag) / k_i (temporary stones: tests/rules/test_S07_*)."""

import pytest

from engine.actions import Actions
from engine.donkey import Bag, effective_height

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
LINE = ["..#..", "..m..", "..#.."]  # (1, 2) is mossy


def test_model_examples():
    # MODEL D-01: 260 kg on 50 kg/cm sinks 5.2 cm; 320 kg on a mossy 25 kg/cm stone sinks 12.8 cm.
    assert effective_height(10.0, 260.0, 50.0) == pytest.approx(10.0 - 5.2)
    assert effective_height(0.0, 320.0, 25.0) == pytest.approx(-12.8)


def depth_after_one_tick(**donkey):
    trace = run(CFG, 1, [Actions()], start=set_up(CFG, LINE, donkey=donkey))
    return trace.states[0].donkey.depth


def test_unloaded_donkey_on_a_normal_stone():
    # Still water: L = 0, so d = −e = −(10 − 200/50).
    assert depth_after_one_tick(row=0, col=2) == pytest.approx(-6.0)


def test_mossy_stone_is_softer():
    assert depth_after_one_tick(row=1, col=2) == pytest.approx(-(10.0 - 200 / 25))


def test_bags_add_to_the_load():
    bags = {"bag_left": Bag(items=(0,), mass=40.0, volume=1), "bag_right": Bag(items=(1,), mass=20.0, volume=1)}
    assert depth_after_one_tick(row=0, col=2, **bags) == pytest.approx(-(10.0 - 260 / 50))
