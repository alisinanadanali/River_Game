"""Which clip each character plays (VISUALS §9.3): loops from the state, one-shots from the events.

Pure and immutable like the engine: update() returns a new Animator, time is an argument (seconds on the wall
clock), nothing here imports pygame. Called once per tick with that tick's events and the new observation, and
look() once per frame.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from engine.config import Config
from engine.evolve import evolve
from engine.events import (
    DepthState,
    DonkeyMoved,
    DonkeyMoveStarted,
    DonkeyRespawned,
    DonkeySlipped,
    DonkeySwept,
    Event,
    ItemCaught,
    ItemDelivered,
    ItemThrown,
    Role,
    ShrekMoved,
    Side,
    TempStoneRaised,
    TempStoneSpawned,
)
from engine.observe import Observation
from render.characters.pose import Clip, Transform, is_done, pose


ONE_SHOTS = {  # VISUALS §9.3: event type → clip, per role (DonkeySlipped depends on its side, see _clip_for)
    Role.DONKEY: {DonkeyRespawned: Clip.RESPAWN, DonkeyMoved: Clip.HOP, ItemCaught: Clip.HAPPY,
                  ItemDelivered: Clip.HAPPY},
    Role.SHREK: {ItemThrown: Clip.THROW, TempStoneSpawned: Clip.THROW, TempStoneRaised: Clip.THROW,
                 ShrekMoved: Clip.HOP, ItemCaught: Clip.CHEER, ItemDelivered: Clip.CHEER},
}
SLIPS = {Side.LEFT: Clip.SLIP_LEFT, Side.RIGHT: Clip.SLIP_RIGHT}
PRIORITY = {
    Clip.RESPAWN: 4, Clip.SLIP_LEFT: 3, Clip.SLIP_RIGHT: 3, Clip.THROW: 3, Clip.HOP: 2, Clip.HAPPY: 1, Clip.CHEER: 1,
}


@dataclass(frozen=True)
class Playing:
    clip: Clip
    started_s: float
    cell: tuple[int, int] | None = None  # the ghost's cell (DonkeySwept row, col); None for the character itself


@dataclass(frozen=True)
class Animator:
    role: Role
    loop: Playing
    one_shot: Playing | None = None
    facing_right: bool = True            # VISUALS §9.1: both start facing east, downstream
    ghost: Playing | None = None         # the swept donkey's SWEPT clip, drawn at ghost.cell


@dataclass(frozen=True)
class Look:
    """What to draw this frame: the clip (for display), its transform and which way the character faces."""

    clip: Clip
    transform: Transform
    facing_right: bool


def loop_clip(role: Role, obs: Observation) -> Clip:
    """VISUALS §9.3: the first matching row of the loop table."""
    if role is Role.SHREK:
        return Clip.DAM if obs.dam.active else Clip.IDLE
    if obs.donkey.move_remaining > 0:
        return Clip.WADE
    return Clip.SCARED if obs.donkey.depth_state is DepthState.KNEE else Clip.IDLE


def one_shot_clip(role: Role, events: Iterable[Event]) -> Clip | None:
    """VISUALS §9.3: the highest-priority one-shot clip of a tick's events for `role`, or None."""
    clips = [c for c in (_clip_for(role, e) for e in events) if c is not None]
    return max(clips, key=PRIORITY.__getitem__, default=None)


def _clip_for(role: Role, event: Event) -> Clip | None:
    if role is Role.DONKEY and isinstance(event, DonkeySlipped):
        return SLIPS[event.side]
    return ONE_SHOTS[role].get(type(event))


def new_animator(role: Role, obs: Observation, now_s: float) -> Animator:
    return Animator(role=role, loop=Playing(loop_clip(role, obs), now_s))


def update(anim: Animator, obs: Observation, events: Iterable[Event], now_s: float, cfg: Config) -> Animator:
    """One tick: the new observation picks the loop, the tick's events the one-shot, the facing and the ghost."""
    events = tuple(events)
    changes = {}
    loop = loop_clip(anim.role, obs)
    if loop is not anim.loop.clip:
        changes["loop"] = Playing(loop, now_s)
    clip = one_shot_clip(anim.role, events)
    if clip is not None and _may_start(anim.one_shot, clip, now_s, cfg):
        changes["one_shot"] = Playing(clip, now_s)
    facing = _facing(anim.role, events, anim.facing_right)
    if facing is not anim.facing_right:
        changes["facing_right"] = facing
    if anim.role is Role.DONKEY:
        swept = [e for e in events if isinstance(e, DonkeySwept)]
        if swept:
            changes["ghost"] = Playing(Clip.SWEPT, now_s, cell=(swept[-1].row, swept[-1].col))
    return evolve(anim, **changes) if changes else anim


def _may_start(running: Playing | None, clip: Clip, now_s: float, cfg: Config) -> bool:
    """VISUALS §9.3: a clip cuts the running one if its priority is at least as high, or the running one is done."""
    if running is None or is_done(running.clip, now_s - running.started_s, cfg):
        return True
    return PRIORITY[clip] >= PRIORITY[running.clip]


def _facing(role: Role, events: tuple[Event, ...], facing_right: bool) -> bool:
    """VISUALS §9.1: the direction of the role's last sideways move this tick; unchanged without one."""
    for e in events:
        if role is Role.DONKEY and isinstance(e, DonkeyMoved | DonkeyMoveStarted):
            step = e.to_cell[1] - e.from_cell[1]
        elif role is Role.SHREK and isinstance(e, ShrekMoved):
            step = e.to_col - e.from_col
        else:
            continue
        if step:
            facing_right = step > 0
    return facing_right


def look(anim: Animator, now_s: float, cfg: Config) -> Look:
    """The running one-shot, or the loop once it is done."""
    shot = anim.one_shot
    playing = shot if shot is not None and not is_done(shot.clip, now_s - shot.started_s, cfg) else anim.loop
    return Look(playing.clip, pose(playing.clip, now_s - playing.started_s, cfg), anim.facing_right)


def ghost_look(anim: Animator, now_s: float, cfg: Config) -> tuple[Look, tuple[int, int]] | None:
    """The swept donkey's ghost and its cell while its clip runs; None otherwise."""
    ghost = anim.ghost
    if ghost is None or is_done(ghost.clip, now_s - ghost.started_s, cfg):
        return None
    return Look(ghost.clip, pose(ghost.clip, now_s - ghost.started_s, cfg), anim.facing_right), ghost.cell
