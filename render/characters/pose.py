"""Puppet clips (VISUALS §9.2): pose(clip, elapsed_s, config) -> Transform. Pure: no pygame, time passed in."""

import math
from dataclasses import dataclass
from enum import StrEnum

from engine.config import Config
from engine.events import Role


class Clip(StrEnum):
    IDLE = "IDLE"
    SCARED = "SCARED"
    WADE = "WADE"
    DAM = "DAM"
    HOP = "HOP"
    THROW = "THROW"
    SLIP_LEFT = "SLIP_LEFT"
    SLIP_RIGHT = "SLIP_RIGHT"
    HAPPY = "HAPPY"
    CHEER = "CHEER"
    RESPAWN = "RESPAWN"
    SWEPT = "SWEPT"


@dataclass(frozen=True)
class Transform:
    """VISUALS §9.1: what is done to a pose image this frame; the defaults leave it as it is."""

    image: str = "idle"
    dx_px: float = 0.0
    dy_px: float = 0.0       # screen axis: negative is up
    scale_x: float = 1.0
    scale_y: float = 1.0
    angle_deg: float = 0.0   # about the feet, counter-clockwise (pygame)
    alpha: float = 1.0


LOOPS = frozenset({Clip.IDLE, Clip.SCARED, Clip.WADE, Clip.DAM})
CLIPS_OF = {  # VISUALS §9.2 "Rol"; the SWEPT ghost is the donkey's
    Role.SHREK: frozenset({Clip.IDLE, Clip.DAM, Clip.HOP, Clip.THROW, Clip.CHEER}),
    Role.DONKEY: frozenset({
        Clip.IDLE, Clip.SCARED, Clip.WADE, Clip.HOP, Clip.SLIP_LEFT, Clip.SLIP_RIGHT, Clip.HAPPY, Clip.RESPAWN,
        Clip.SWEPT,
    }),
}
IMAGES = {Clip.DAM: "dam", Clip.THROW: "throw", Clip.HAPPY: "happy"}  # every other clip uses "idle"
SLIP_SIGN = {Clip.SLIP_LEFT: 1.0, Clip.SLIP_RIGHT: -1.0}                # left = counter-clockwise


def duration_s(clip: Clip, cfg: Config) -> float | None:
    """A one-shot clip's length in seconds; None for a loop."""
    a = cfg.render.animation
    return {
        Clip.HOP: cfg.time.tick_seconds + a.land_s,  # the flight lasts one tick, like the position's interpolation
        Clip.THROW: a.throw_s,
        Clip.SLIP_LEFT: a.slip_s,
        Clip.SLIP_RIGHT: a.slip_s,
        Clip.HAPPY: a.happy_s,
        Clip.CHEER: a.happy_s,
        Clip.RESPAWN: a.respawn_s,
        Clip.SWEPT: a.swept_s,
    }.get(clip)


def is_done(clip: Clip, elapsed_s: float, cfg: Config) -> bool:
    """A one-shot clip is done once its duration has passed; a loop never is."""
    d = duration_s(clip, cfg)
    return d is not None and elapsed_s >= d


def pose(clip: Clip, elapsed_s: float, cfg: Config) -> Transform:
    """VISUALS §9.2: the transform `elapsed_s` seconds into `clip`. Before 0 is the start, after the end the end."""
    a = cfg.render.animation
    d = duration_s(clip, cfg)
    t = max(0.0, elapsed_s if d is None else min(elapsed_s, d))
    u = 0.0 if d is None else t / d
    image = IMAGES.get(clip, "idle")
    match clip:
        case Clip.IDLE:
            return _breath(t, a, image)
        case Clip.SCARED:
            breath = _breath(t, a, image)
            return Transform(image, dx_px=_wave(a.scared_shake_px, a.scared_shake_hz, t),
                             scale_x=breath.scale_x, scale_y=breath.scale_y)
        case Clip.WADE:
            return Transform(image, dy_px=-a.wade_bob_px * abs(math.sin(math.pi * t / a.wade_period_s)))
        case Clip.DAM:
            return Transform(image, dx_px=_wave(a.dam_shake_px, a.dam_shake_hz, t))
        case Clip.HOP:
            flight = cfg.time.tick_seconds
            if t < flight:
                v = t / flight
                return Transform(image, dy_px=-4 * a.hop_height_px * v * (1 - v))
            return _squashed(image, a.land_squash * math.sin(math.pi * (t - flight) / a.land_s))
        case Clip.THROW:
            r = a.throw_windup_ratio
            if u < r:
                return _squashed(image, a.throw_squash * math.sin(math.pi / 2 * u / r))
            w = (u - r) / (1 - r)
            return _squashed(image, a.throw_squash * math.cos(math.pi * w) * (1 - w))
        case Clip.SLIP_LEFT | Clip.SLIP_RIGHT:
            wobble = math.cos(2 * math.pi * a.slip_wobble_hz * t)
            return Transform(image, angle_deg=SLIP_SIGN[clip] * a.slip_tilt_deg * (1 - u) * wobble)
        case Clip.HAPPY | Clip.CHEER:
            return Transform(image, dy_px=-a.happy_bounce_px * abs(math.sin(a.happy_bounces * math.pi * u)))
        case Clip.RESPAWN:
            return Transform(image, alpha=u)
        case Clip.SWEPT:
            return Transform(image, dx_px=a.swept_slide_px * u, angle_deg=-a.swept_tilt_deg * u, alpha=1 - u)
    raise ValueError(f"no pose for clip {clip!r}")


def _breath(t: float, a, image: str) -> Transform:
    """IDLE: scale_y = 1 + a·sin(2πt/T), scale_x = 1/scale_y."""
    return _squashed(image, -a.breath_scale * math.sin(2 * math.pi * t / a.breath_period_s))


def _squashed(image: str, q: float) -> Transform:
    """scale_y = 1 − q (q < 0 stretches), scale_x = 1/scale_y: the area stays the same."""
    return Transform(image, scale_x=1 / (1 - q), scale_y=1 - q)


def _wave(amplitude: float, hz: float, t: float) -> float:
    return amplitude * math.sin(2 * math.pi * hz * t)
