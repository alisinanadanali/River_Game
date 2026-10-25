"""VISUALS §4.1, §9.3: the view, drawing's state between frames, and the scene a frame draws. Pure, time passed in.

After each frame the view follows the session: every tick of the frame updates both animators with its events
(several tactical ticks in one frame all see the frame's last observation). A restart (F5) starts a new view.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from engine.events import Role
from engine.observe import observe
from game.session import Session
from render.characters.animator import Animator, look, new_animator, update
from render.interpolation import lerp, tick_progress
from render.layout import feet
from render.scene import Scene


@dataclass(frozen=True)
class View:
    animators: Mapping[Role, Animator]
    restarts: int                      # the session's restarts this view belongs to


def new_view(session: Session, now_s: float) -> View:
    animators = {role: new_animator(role, observe(session.state, role), now_s) for role in Role}
    return View(animators, session.restarts)


def follow(view: View, session: Session, now_s: float) -> View:
    """The frame's ticks, in order; a new view after a restart."""
    if session.restarts != view.restarts:
        return new_view(session, now_s)
    if not session.ticks:
        return view
    animators = dict(view.animators)
    for role in Role:
        obs = observe(session.state, role)
        for record in session.ticks:
            animators[role] = update(animators[role], obs, record.events, now_s, session.config)
    return View(animators, view.restarts)


def progress(session: Session) -> float:
    """u ∈ [0, 1]: the share of a tick since the last one (ADR-002 interpolation)."""
    return tick_progress(session.since_tick_s, 0.0, session.config.time.tick_seconds)


def scene(view: View, session: Session, now_s: float) -> Scene:
    """§4.1: the observation, the characters' feet between the previous and the current cell, looks and status."""
    cfg, u = session.config, progress(session)
    before, now = session.previous, session.state
    cells = {
        Role.SHREK: ((-1, before.shrek.col), (-1, now.shrek.col)),
        Role.DONKEY: ((before.donkey.row, before.donkey.col), (now.donkey.row, now.donkey.col)),
    }
    return Scene(
        obs=observe(now, Role.DONKEY),                      # V0: both roles see the same (observe.py)
        feet={role: feet(cfg, role, lerp(a, b, u)) for role, (a, b) in cells.items()},
        looks={role: look(view.animators[role], now_s, cfg) for role in Role},
        mode=session.mode.value,
        paused=session.paused,
        seed=session.seed,
    )
