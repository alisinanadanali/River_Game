"""tools/bench.py (ROADMAP Phase 0 speed criterion, ADR-011): µs per tick, ticks per second, per TICK.md step.

Timing itself cannot be asserted in an ordinary test (it depends on the machine and its load), so the mechanics
are checked with a fake clock, the per-step loop is checked to be step itself, and the one real speed assertion
is marked `perf` and left out of the default run (uv run pytest -m perf).
"""

import itertools

import pytest

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekMove
from engine.config import load_config
from engine.state import new_game
from engine.step import PIPELINE, step
from tools import bench
from tools.bench import ROADMAP_TICKS_PER_S, Result, main, measure, random_actions, stage_labels, timed_step

from tests.support import scripted_actions

CFG = load_config()


def fake_clock(seconds_per_call: float):
    """A clock that moves on by the same amount at every call."""
    ticks = itertools.count()
    return lambda: next(ticks) * seconds_per_call


# --- what is measured is the real step ---------------------------------------------------------------------

def test_the_timed_pipeline_is_step():
    state, rngs = new_game(CFG, 3)
    totals = [0.0] * len(PIPELINE)
    for actions in scripted_actions(200):
        expected = step(state, actions, rngs)
        got = timed_step(state, actions, rngs, totals, fake_clock(1e-6))
        assert got[0] == expected[0] and got[1] == expected[1] and got[2] == expected[2]
        state, rngs = expected[0], expected[1]
    assert totals == pytest.approx([200e-6] * len(PIPELINE))  # one clock step per stage and tick


def test_stage_labels_follow_tick_md():
    labels = stage_labels()
    assert len(labels) == len(PIPELINE) == 13
    assert [label.split(":")[0] for label in labels] == [f"{n:>2}" for n in range(13)]
    assert labels[5] == " 5: water" and labels[0] == " 0: RNG blocks"


def test_random_actions_are_fixed_and_use_every_component():
    a, b = random_actions(3000, seed=0), random_actions(3000, seed=0)
    assert a == b and a != random_actions(3000, seed=1)
    assert {x.donkey for x in a} == set(DonkeyAction)
    assert {x.shrek.move for x in a} == set(ShrekMove)
    assert {x.shrek.aim for x in a} == set(Aim)
    assert {x.shrek.ability for x in a} == set(Ability)


# --- the arithmetic, with a fake clock -----------------------------------------------------------------------

def test_microseconds_per_tick_and_ticks_per_second():
    result = measure(CFG, [Actions()] * 100, repeats=3, clock=fake_clock(1e-4))
    assert result.us_per_tick == pytest.approx(100.0)
    assert result.ticks_per_s == pytest.approx(10_000.0)
    assert result.ticks == 100


def test_observing_both_roles_is_inside_the_timed_region():
    # The RL loop is step + observe(donkey) + observe(shrek): three timed calls per tick instead of one.
    result = measure(CFG, [Actions()] * 50, repeats=1, roles=2, clock=fake_clock(1e-4))
    assert result.us_per_tick == pytest.approx(300.0)


def test_finished_games_are_restarted():
    result = measure(CFG, [Actions()] * 700, repeats=1, clock=fake_clock(1e-6))
    assert (result.ticks, result.games) == (700, 3)  # 300 + 300 + 100


def test_the_best_repeat_is_reported():
    # Interference only ever adds time, so the fastest repeat is the closest to the code's own cost.
    assert Result(us_per_tick=80.0, ticks=10, games=1).ticks_per_s == pytest.approx(12_500.0)
    clocks = iter([fake_clock(3e-4), fake_clock(1e-4), fake_clock(2e-4)])
    result = measure(CFG, [Actions()] * 20, repeats=3, clock_factory=lambda: next(clocks))
    assert result.us_per_tick == pytest.approx(100.0)


# --- the command line ----------------------------------------------------------------------------------------

def test_main_reports_and_passes_above_the_roadmap_line(monkeypatch, capsys):
    monkeypatch.setattr(bench, "measure", lambda *a, **k: Result(us_per_tick=120.0, ticks=3000, games=10))
    assert main(["--ticks", "100"]) == 0
    out = capsys.readouterr().out
    assert "8 333 tick/sn" in out and f"{ROADMAP_TICKS_PER_S:,}".replace(",", " ") in out


def test_main_fails_below_the_roadmap_line(monkeypatch, capsys):
    monkeypatch.setattr(bench, "measure", lambda *a, **k: Result(us_per_tick=250.0, ticks=3000, games=10))
    assert main(["--ticks", "100"]) == 1
    assert "✗" in capsys.readouterr().out


def test_main_prints_every_stage(capsys):
    assert main(["--ticks", "60", "--repeats", "1", "--stages"]) in (0, 1)  # speed is not this test's business
    out = capsys.readouterr().out
    assert all(label in out for label in stage_labels())


# --- the speed itself (uv run pytest -m perf) ----------------------------------------------------------------

@pytest.mark.perf
def test_random_play_meets_the_roadmap_speed():
    result = measure(CFG, random_actions(3000, seed=0), repeats=5)
    assert result.ticks_per_s >= ROADMAP_TICKS_PER_S, f"{result.us_per_tick:.1f} µs/tick"
