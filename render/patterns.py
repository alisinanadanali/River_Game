"""VISUALS §3: the safety-margin patterns on a top face (pygame), shared by the board and the HUD's depth badge."""

import pygame

from engine.events import DepthState

# Structural shapes, in px on a face (not model numbers)
DOT_STEP_PX = 16          # BİLEK: one dot every this many px each way
DOT_RADIUS_PX = 2
LINE_STEP_PX = 12         # DİZ, TEHLİKE: diagonal lines this far apart
LINE_PX = 2
MARK_SHARE = 0.6          # TEHLİKE "!": this share of the face's height
MARK_BAR_SHARE = 0.65     # the bar's share of the "!"
MARK_STROKE_PX = 4
MARK_PATCH_PX = 12        # the base-colour patch under the "!"
MARK_PAD_PX = 2


def draw_pattern(surface: pygame.Surface, rect: pygame.Rect, tier: DepthState, base, ink) -> None:
    """§3: the tier's pattern on a top face, denser with the danger: none, sparse dots, diagonal lines, a lattice
    with "!" (drawn on a patch of the base colour so it reads over the lattice)."""
    old = surface.get_clip()
    surface.set_clip(rect.clip(old))
    try:
        if tier is DepthState.ANKLE:
            for x in range(rect.left + DOT_STEP_PX // 2, rect.right, DOT_STEP_PX):
                for y in range(rect.top + DOT_STEP_PX // 2, rect.bottom, DOT_STEP_PX):
                    pygame.draw.circle(surface, ink, (x, y), DOT_RADIUS_PX)
        elif tier in (DepthState.KNEE, DepthState.SWEPT):
            _diagonals(surface, rect, ink, rising=True)
            if tier is DepthState.SWEPT:
                _diagonals(surface, rect, ink, rising=False)
                _exclamation(surface, rect, base, ink)
    finally:
        surface.set_clip(old)


def _diagonals(surface: pygame.Surface, rect: pygame.Rect, ink, rising: bool) -> None:
    h = rect.height
    for k in range(-h, rect.width + h, LINE_STEP_PX):
        x0 = rect.left + k
        start, end = ((x0, rect.bottom), (x0 + h, rect.top)) if rising else ((x0, rect.top), (x0 + h, rect.bottom))
        pygame.draw.line(surface, ink, start, end, LINE_PX)


def _exclamation(surface: pygame.Surface, rect: pygame.Rect, base, ink) -> None:
    """A "!" in the face's centre: a bar and a dot, on a patch of the base colour."""
    h = rect.height * MARK_SHARE
    patch = pygame.Rect(0, 0, MARK_PATCH_PX, round(h) + 2 * MARK_PAD_PX)
    patch.center = rect.center
    surface.fill(base, patch)
    bar = pygame.Rect(0, 0, MARK_STROKE_PX, round(h * MARK_BAR_SHARE))
    bar.midtop = (patch.centerx, patch.top + MARK_PAD_PX)
    dot = pygame.Rect(0, 0, MARK_STROKE_PX, MARK_STROKE_PX)
    dot.midbottom = (patch.centerx, patch.bottom - MARK_PAD_PX)
    surface.fill(ink, bar)
    surface.fill(ink, dot)
