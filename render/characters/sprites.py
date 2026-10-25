"""Pose images and their drawing (VISUALS §9.1, §9.4): local files, or the abstract shape when one is missing."""

import math
from dataclasses import dataclass
from pathlib import Path

import pygame

from engine.config import Config
from engine.events import Role
from render import PROJECT_ROOT
from render.characters.animator import Look

# VISUALS §9.4 fallback shapes, as shares of the shape's width w (structural, not model numbers)
SHREK_CORNER = 0.25                  # corner radius of Shrek's square, × min(w, h)
EYE_AT = (0.68, 0.35)                # the eye on the east side shows which way the shape faces; (× w, × h)
EYE_RADIUS = 0.08                    # × w
EYE_SHADE = 0.3                      # the eye is the body colour × this
EARS = (                             # the donkey's left ear (x × w, y × w below the circle's top; apex at y = 0)
    (0.25, 0.30),
    (0.45, 0.10),
    (0.15, None),
)


@dataclass(frozen=True)
class PoseSprite:
    surface: pygame.Surface            # already at its on-screen size: height_px · scale (or fallback_size_px)
    anchor: tuple[float, float]        # the feet, px inside `surface`
    faces_right: bool


@dataclass(frozen=True)
class CharacterSprites:
    role: Role
    poses: dict[str, PoseSprite]       # pose name (idle, throw, …) → sprite
    missing: tuple[str, ...]           # pose files that could not be read; any → every pose is the fallback shape

    @property
    def is_fallback(self) -> bool:
        return bool(self.missing)


def load_character(role: Role, cfg: Config, root: Path = PROJECT_ROOT) -> CharacterSprites:
    """VISUALS §9.1: every pose of `role` at its on-screen size; all fallback shapes if any file is unreadable."""
    look = getattr(cfg.render.characters, role.value)
    poses = dict(look.poses)
    images, missing = {}, []
    for name, pose_cfg in poses.items():
        try:
            images[name] = pygame.image.load(str(root / pose_cfg.file))
        except (OSError, pygame.error):
            missing.append(pose_cfg.file)
    if missing:
        shape = fallback_surface(role, cfg)
        w, h = shape.get_size()
        sprite = PoseSprite(shape, (w / 2, h), faces_right=True)
        return CharacterSprites(role, {name: sprite for name in poses}, tuple(missing))
    sprites = {}
    for name, pose_cfg in poses.items():
        image = images[name]
        if pygame.display.get_surface() is not None:
            image = image.convert_alpha()
        h = max(1, round(look.height_px * pose_cfg.scale))
        w = max(1, round(image.get_width() * h / image.get_height()))
        ax, ay = pose_cfg.anchor
        sprites[name] = PoseSprite(pygame.transform.smoothscale(image, (w, h)), (ax * w, ay * h),
                                   faces_right=pose_cfg.faces == "right")
    return CharacterSprites(role, sprites, ())


def fallback_surface(role: Role, cfg: Config) -> pygame.Surface:
    """VISUALS §9.4: Shrek a rounded square, the donkey a circle with two ears; an eye on the east side."""
    look = getattr(cfg.render.characters, role.value)
    w, h = look.fallback_size_px
    colour = pygame.Color(look.fallback_color)
    shape = pygame.Surface((w, h), pygame.SRCALPHA)
    if role is Role.SHREK:
        pygame.draw.rect(shape, colour, shape.get_rect(), border_radius=round(min(w, h) * SHREK_CORNER))
    else:
        top = h - w                                                   # the circle sits on the bottom edge
        pygame.draw.circle(shape, colour, (w / 2, h - w / 2), w / 2)
        for mirror in (False, True):
            ear = [((1 - x) * w if mirror else x * w, 0 if y is None else top + y * w) for x, y in EARS]
            pygame.draw.polygon(shape, colour, ear)
    eye = pygame.Color(*(round(c * EYE_SHADE) for c in colour[:3]))
    pygame.draw.circle(shape, eye, (EYE_AT[0] * w, EYE_AT[1] * h if role is Role.SHREK else h - w * (1 - EYE_AT[1])),
                       max(1, EYE_RADIUS * w))
    return shape


def rotated_anchor(anchor: tuple[float, float], size: tuple[int, int], angle_deg: float,
                   rotated_size: tuple[int, int]) -> tuple[float, float]:
    """Where `anchor` (px in a `size` image) lands in the image rotated by `angle_deg` counter-clockwise.

    pygame rotates about the centre and grows the image to `rotated_size`; screen y points down, so a point
    (x, y) from the centre goes to (x·cos θ + y·sin θ, −x·sin θ + y·cos θ).
    """
    theta = math.radians(angle_deg)
    vx, vy = anchor[0] - size[0] / 2, anchor[1] - size[1] / 2
    rx = vx * math.cos(theta) + vy * math.sin(theta)
    ry = -vx * math.sin(theta) + vy * math.cos(theta)
    return rotated_size[0] / 2 + rx, rotated_size[1] / 2 + ry


def draw(target: pygame.Surface, sprites: CharacterSprites, look: Look, feet: tuple[float, float],
         water_y: float | None = None) -> pygame.Rect:
    """VISUALS §9.1: the pose image with the look's transform, its anchor on `feet` (+ dx, dy), nothing drawn
    below `water_y`. Order: mirror, squash, rotate about the feet, fade. Returns the area drawn on."""
    sprite = sprites.poses[look.transform.image]
    tr = look.transform
    if tr.alpha <= 0:
        return pygame.Rect(round(feet[0]), round(feet[1]), 0, 0)
    surface, (ax, ay) = sprite.surface, sprite.anchor
    if look.facing_right != sprite.faces_right:
        surface, ax = pygame.transform.flip(surface, True, False), surface.get_width() - ax
    if tr.scale_x != 1 or tr.scale_y != 1:
        w = max(1, round(surface.get_width() * tr.scale_x))
        h = max(1, round(surface.get_height() * tr.scale_y))
        ax, ay = ax * w / surface.get_width(), ay * h / surface.get_height()
        surface = pygame.transform.smoothscale(surface, (w, h))
    if tr.angle_deg:
        rotated = pygame.transform.rotozoom(surface, tr.angle_deg, 1)
        ax, ay = rotated_anchor((ax, ay), surface.get_size(), tr.angle_deg, rotated.get_size())
        surface = rotated
    if tr.alpha < 1:
        if surface is sprite.surface:
            surface = surface.copy()  # never fade the loaded image itself
        surface.set_alpha(round(255 * tr.alpha))
    at = (round(feet[0] + tr.dx_px - ax), round(feet[1] + tr.dy_px - ay))
    if water_y is None:
        return target.blit(surface, at)
    old = target.get_clip()
    target.set_clip(old.clip(pygame.Rect(old.x, old.y, old.width, max(0, round(water_y) - old.y))))
    try:
        return target.blit(surface, at)
    finally:
        target.set_clip(old)
