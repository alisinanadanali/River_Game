"""What a controller sees (MODEL.md §1 O, ENTITIES.md Observation): act(observation) -> action.

V0: both roles see the whole state except HIDDEN, the fields that would give the future away. The observation
copies nothing: sub-states are shared with the state (arrays are read-only), and only the two objects that hold
a hidden field get a view type without it.
"""

import dataclasses
from dataclasses import dataclass

import numpy as np

from engine.config import Config
from engine.donkey import Donkey
from engine.events import GameOverReason, ProjectileKind, Role
from engine.items import Bank, Item, Projectile
from engine.shrek import Shrek
from engine.state import GameState
from engine.stones import Stones
from engine.water import Dam, Water
from engine.world import World, same_content

HIDDEN = frozenset({"world.seed", "projectiles[].landing"})  # ENTITIES.md Observation, read back by the tests


@dataclass(frozen=True, kw_only=True)
class WorldView:
    """World without `seed`: the five streams derive from it (R-01), so it would reveal every future draw."""

    rows: int
    cols: int
    is_stone: np.ndarray    # bool[R, C]   M-02
    base_h: np.ndarray      # float[R, C]  cm, M-03
    stiffness: np.ndarray   # float[R, C]  kg/cm, M-03
    mossy: np.ndarray       # bool[R, C]   M-03
    rocks_to_solve: int     # M-04
    regen_attempt: int      # M-05

    def __eq__(self, other):
        if not isinstance(other, WorldView):
            return NotImplemented
        return all(same_content(getattr(self, f.name), getattr(other, f.name)) for f in dataclasses.fields(self))

    __hash__ = None  # equal by content, and numpy arrays are not hashable


@dataclass(frozen=True, kw_only=True)
class ProjectileView:
    """Projectile without `landing`: drawn at the throw (S-04), shown only through step 4's events."""

    item_id: int
    kind: ProjectileKind
    target: tuple[int, int]  # the aim cell; (−1, col) for a handoff
    sigma: float             # cells
    ticks_left: int
    thrown_at: int


@dataclass(frozen=True, kw_only=True)
class Observation:
    """ENTITIES.md Observation: GameState field for field, with `world` and `projectiles` as views."""

    role: Role
    config: Config = dataclasses.field(repr=False)
    world: WorldView
    water: Water
    dam: Dam
    stones: Stones
    donkey: Donkey
    shrek: Shrek
    items: tuple[Item, ...]
    bank: Bank
    projectiles: tuple[ProjectileView, ...]
    t: int
    score: int
    game_over: GameOverReason | None


def observe(state: GameState, role: Role) -> Observation:
    """O (MODEL §1): what `role` sees of `state`. V0: the same for both roles, everything but HIDDEN."""
    return Observation(
        role=role,
        config=state.config,
        world=_world_view(state.world),
        water=state.water,
        dam=state.dam,
        stones=state.stones,
        donkey=state.donkey,
        shrek=state.shrek,
        items=state.items,
        bank=state.bank,
        projectiles=tuple(_projectile_view(p) for p in state.projectiles),
        t=state.t,
        score=state.score,
        game_over=state.game_over,
    )


def _world_view(world: World) -> WorldView:
    return WorldView(**{f.name: getattr(world, f.name) for f in dataclasses.fields(WorldView)})


def _projectile_view(p: Projectile) -> ProjectileView:
    return ProjectileView(**{f.name: getattr(p, f.name) for f in dataclasses.fields(ProjectileView)})
