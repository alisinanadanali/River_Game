"""MODEL §1 O, ENTITIES.md Observation: what a controller sees. V0: both roles see the whole state except the
hidden fields listed in ENTITIES.md (the master seed, and the landing points drawn at a throw).

The central check rebuilds the state from an observation plus the hidden values. If that gives the state back,
the observation lost nothing else; the other tests show the hidden values really are gone.
"""

import dataclasses
import re
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.events import Role
from engine.evolve import evolve
from engine.items import Projectile
from engine.observe import HIDDEN, ProjectileView, WorldView, observe
from engine.state import GameState
from engine.world import World

from tests.support import config_with, run

ROOT = Path(__file__).resolve().parents[2]
ENTITIES = (ROOT / "docs" / "ENTITIES.md").read_text(encoding="utf-8")
CFG = config_with({"items": {"arrival_rate_per_tick": 0.3}})  # a full bank, so Shrek has something to throw
TICKS = CFG.time.game_length_ticks
VIEWS = {"world": (World, WorldView), "projectiles": (Projectile, ProjectileView)}

actions = st.builds(
    Actions,
    donkey=st.sampled_from(DonkeyAction),
    shrek=st.builds(ShrekAction, move=st.sampled_from(ShrekMove), aim=st.sampled_from(Aim), ability=st.sampled_from(Ability)),
)


def random_game(seed: int) -> list[Actions]:
    """The same kind of game hypothesis draws below, from a fixed numpy generator (for the guard tests)."""
    g = np.random.default_rng(seed)
    pick = lambda enum: list(enum)[g.integers(len(enum))]  # noqa: E731
    return [
        Actions(donkey=pick(DonkeyAction), shrek=ShrekAction(move=pick(ShrekMove), aim=pick(Aim), ability=pick(Ability)))
        for _ in range(TICKS)
    ]


def documented_hidden() -> frozenset[str]:
    section = ENTITIES.split("## Observation", 1)[1].split("\n## ", 1)[0]
    return frozenset(re.findall(r"^- `([^`]+)`$", section, flags=re.MULTILINE))


def names(cls) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def rebuild(obs, seed: int, landings: list[tuple[float, float]]) -> GameState:
    """The state an observation came from, given the hidden values: the seed and one landing per projectile."""
    world = World(**{n: getattr(obs.world, n) for n in names(WorldView)}, seed=seed)
    projectiles = tuple(
        Projectile(**{n: getattr(p, n) for n in names(ProjectileView)}, landing=landing)
        for p, landing in zip(obs.projectiles, landings, strict=True)
    )
    shared = {n: getattr(obs, n) for n in names(GameState) - {"world", "projectiles"}}
    return GameState(**shared, world=world, projectiles=projectiles)


def a_state_with_projectiles() -> GameState:
    for state in run(CFG, 5, random_game(5)).states:
        if len(state.projectiles) > 0:
            return state
    raise AssertionError("no projectile in the guard game")


# --- the hidden list -------------------------------------------------------------------------------------

def test_hidden_list_is_the_documented_one():
    assert HIDDEN == documented_hidden() == {"world.seed", "projectiles[].landing"}


@pytest.mark.parametrize("path", sorted(documented_hidden()))
def test_each_view_drops_exactly_its_hidden_field(path):
    owner, field = path.replace("[]", "").split(".")
    full, view = VIEWS[owner]
    assert field in names(full)                  # the doc names a real field
    assert names(view) == names(full) - {field}  # and the view keeps every other one


# --- nothing visible is lost, nothing hidden leaks -------------------------------------------------------

@given(seed=st.integers(0, 2**32 - 1), game=st.lists(actions, min_size=TICKS, max_size=TICKS))
def test_the_observation_plus_the_hidden_values_is_the_state(seed, game):
    for state in run(CFG, seed, game).states:
        obs = observe(state, Role.DONKEY)
        assert rebuild(obs, state.world.seed, [p.landing for p in state.projectiles]) == state


def test_random_games_reach_every_kind_of_sub_state():
    # Guards the property: rebuilding a state with no projectile, temporary stone, wave or item proves little.
    states = run(CFG, 5, random_game(5)).states
    assert any(s.projectiles for s in states)
    assert any(s.stones.temp for s in states)
    assert any(s.water.waves for s in states)
    assert any(s.dam.active for s in states)
    assert len(states[-1].items) > 0


def test_random_games_change_every_field_but_the_score():
    # The property above only checks fields that move. Random play never delivers an item, so the score stays 0:
    # a mutation that blanked the score survived until the test below was added.
    first, *rest = run(CFG, 5, random_game(5)).states
    moved = {n for n in names(GameState) if any(getattr(s, n) != getattr(first, n) for s in rest)}
    assert moved == names(GameState) - {"config", "world", "score"}  # world varies across seeds, not in a game


def test_a_scored_state_rebuilds_too():
    state = evolve(a_state_with_projectiles(), score=6)
    obs = observe(state, Role.SHREK)
    assert obs.score == 6
    assert rebuild(obs, state.world.seed, [p.landing for p in state.projectiles]) == state


def test_hidden_values_do_not_reach_the_observation():
    state = a_state_with_projectiles()
    other = evolve(
        state,
        world=evolve(state.world, seed=state.world.seed + 1),
        projectiles=tuple(evolve(p, landing=(p.landing[0] + 3.0, p.landing[1] - 2.0)) for p in state.projectiles),
    )
    assert other != state
    assert observe(other, Role.DONKEY) == observe(state, Role.DONKEY)


def test_a_visible_change_does_change_the_observation():
    # Guards the test above: observations are compared by content, so equality is not trivially true.
    state = a_state_with_projectiles()
    moved = evolve(state, projectiles=(evolve(state.projectiles[0], ticks_left=state.projectiles[0].ticks_left + 1),))
    assert observe(moved, Role.DONKEY) != observe(state, Role.DONKEY)
    assert observe(evolve(state, world=evolve(state.world, regen_attempt=9)), Role.DONKEY) != observe(state, Role.DONKEY)


# --- roles and sharing -----------------------------------------------------------------------------------

def test_v0_both_roles_see_the_same():
    state = a_state_with_projectiles()
    donkey, shrek = observe(state, Role.DONKEY), observe(state, Role.SHREK)
    assert (donkey.role, shrek.role) == (Role.DONKEY, Role.SHREK)
    assert evolve(shrek, role=Role.DONKEY) == donkey


def test_arrays_are_read_only():
    # The observation shares the state's arrays; a controller writing into one would change the game.
    obs = observe(a_state_with_projectiles(), Role.SHREK)
    w = obs.world
    for array in (w.is_stone, w.base_h, w.stiffness, w.mossy, obs.water.level, obs.stones.raise_h):
        with pytest.raises(ValueError, match="read-only"):
            array.flat[0] = array.flat[0]
