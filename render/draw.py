"""VISUALS §2, §3, §4.1: the frame (pygame). It draws a Scene and nothing else.

Order (§2): the background; the rows from the north bank to the south bank, each row's stones (top face in its
safety-margin colour with its pattern and marks, front face) then its water, then the swept donkey's ghost and
the characters drawn with that row, the donkey cut at its water line (§9.1); on top, the shadows of flying items and
the aim frame (Shrek's sprite reaches over the first river rows), the top bar, the HUD (§5) and the banner.
"""

import math
from dataclasses import dataclass

import pygame

from engine.config import Config
from engine.events import Role
from engine.stones import temp_at
from render.board import front_face, is_bank, life_share, stone_top_z, surface_z, tier_of, water_polygon
from render.characters.sprites import CharacterSprites, draw, load_character
from render.colour import tier_colour
from render.fonts import load_font
from render.hud_layout import FONT_PX as HUD_FONT_PX
from render.layout import Rect, board_rect, cell_center, cell_rect, rows_back_to_front
from render.panels import draw_hud
from render.patterns import LINE_PX, draw_pattern
from render.scene import Scene, banner, top_bar

FONT_PX = 20
AIM_FRAME_PX = 3          # the aim frame's line width
SHADOW_SHARE = 0.25       # a flying item's shadow: an ellipse this share of the tile, on its target cell
TEXT_MARGIN_PX = 12       # the top bar's text from the window's left edge
OPAQUE = 255
# VISUALS §3 marks, in px on a top face (structural shapes, not model numbers; the patterns: render/patterns.py)
CONTOUR_PX = 2            # mossy and temporary stones' contours
MOSS_TOP_PX, MOSS_LEFT_PX, MOSS_GAP_PX = 8, 8, 6
MOSS_WAVE_PX, MOSS_AMPLITUDE_PX = 16, 2   # "≈": one sine period over this width
DASH_PX, GAP_PX = 6, 4    # a temporary stone's dashed contour
LIFE_BAR_PX = 4
LIFE_BAR_MARGIN_PX = 4
SEAM_PX = 1               # pygame fills a polygon's edges: the east and south edges move in, so neighbours
                          # (east in the row, south in the next row's layer) do not share a twice-blended line
CHARACTER_ORDER = (Role.SHREK, Role.DONKEY)   # in one row the donkey is in front (both start on the south bank)


@dataclass(frozen=True)
class Assets:
    font: pygame.font.Font
    hud_font: pygame.font.Font
    sprites: dict[Role, CharacterSprites]


def load_assets(cfg: Config) -> Assets:
    return Assets(load_font(cfg, FONT_PX), load_font(cfg, HUD_FONT_PX),
                  {role: load_character(role, cfg) for role in Role})


def draw_scene(screen: pygame.Surface, assets: Assets, scene: Scene) -> None:
    obs = scene.obs
    cfg, palette, lay = obs.config, obs.config.render.palette, obs.config.render.layout
    screen.fill(palette.background)
    for r in rows_back_to_front(cfg):
        _row(screen, scene, r)
        ghost = scene.ghost
        if ghost is not None and ghost.row == r:
            draw(screen, assets.sprites[Role.DONKEY], ghost.look, ghost.feet, ghost.water_y)
        for role in CHARACTER_ORDER:
            if scene.rows[role] == r:
                draw(screen, assets.sprites[role], scene.looks[role], scene.feet[role],
                     scene.water_y if role is Role.DONKEY else None)
    for projectile in obs.projectiles:
        x, y = cell_center(cfg, *projectile.target, surface_z(obs, scene.levels, *projectile.target))
        w, h = lay.tile_w_px * SHADOW_SHARE * 2, lay.tile_h_px * SHADOW_SHARE * 2
        pygame.draw.ellipse(screen, palette.background, pygame.Rect(round(x - w / 2), round(y - h / 2), w, h))
    aim = (obs.shrek.aim_row, obs.shrek.col)
    pygame.draw.rect(screen, palette.text, _rect(cell_rect(cfg, *aim, surface_z(obs, scene.levels, *aim))),
                     AIM_FRAME_PX)
    text = assets.font.render(top_bar(scene), True, palette.text)
    screen.blit(text, (TEXT_MARGIN_PX, (lay.top_bar_px - text.get_height()) // 2))
    if scene.hud is not None:
        draw_hud(screen, assets.hud_font, scene.hud, cfg)
    line = banner(scene)
    if line is not None:
        text = assets.font.render(line, True, palette.text, palette.background)
        screen.blit(text, text.get_rect(center=screen.get_rect().center))


def _row(screen: pygame.Surface, scene: Scene, r: int) -> None:
    """One row, west to east: on a bank its top and front; in the river each stone's prism with its §3 colour,
    pattern and marks, then the row's water."""
    obs = scene.obs
    cfg, palette, lay = obs.config, obs.config.render.palette, obs.config.render.layout
    if is_bank(obs, r):
        for c in range(obs.world.cols):
            _prism(screen, cfg, r, c, lay.bank_z_cm, 0.0, pygame.Color(palette.bank))
        return
    water = []
    for c in range(obs.world.cols):
        top, level = stone_top_z(obs, r, c), scene.levels[c]
        if top is not None:
            colour = _stone_colour(scene, r, c)
            _prism(screen, cfg, r, c, top, level, colour)
            face = _rect(cell_rect(cfg, r, c, top))
            draw_pattern(screen, face, tier_of(obs, scene.levels, r, c), colour, palette.background)
            if obs.world.is_stone[r, c]:
                if obs.world.mossy[r, c]:
                    _moss(screen, face, palette.background)
            else:
                _temporary(screen, face, life_share(temp_at(obs.stones, r, c).h, cfg), palette)
        if top is None or top <= level:
            water.append(water_polygon(cfg, scene.levels, r, c))
    if water:
        _water(screen, cfg, water)


def _stone_colour(scene: Scene, r: int, c: int) -> pygame.Color:
    """§3: the tier colour of the previous tick blending into this tick's, by u (a new stone: this tick's)."""
    palette = scene.obs.config.render.palette
    now = tier_of(scene.obs, scene.obs.water.level, r, c)
    before = tier_of(scene.before, scene.before.water.level, r, c) or now
    return pygame.Color(tier_colour(palette, before)).lerp(pygame.Color(tier_colour(palette, now)), scene.u)


def _prism(screen: pygame.Surface, cfg: Config, r: int, c: int, top_z: float, level: float,
           colour: pygame.Color) -> None:
    """§2: the top face at top_z and, if it is above `level`, the darker front face down to it."""
    front = front_face(cfg, r, c, top_z, level)
    if front is not None:
        shade = cfg.render.layout.front_shade
        screen.fill([round(v * shade) for v in colour[:3]], _rect(front))
    screen.fill(colour, _rect(cell_rect(cfg, r, c, top_z)))


def _moss(surface: pygame.Surface, face: pygame.Rect, ink) -> None:
    """§3: a dark contour and a "≈" (two wavy lines) in the face's north-west corner."""
    pygame.draw.rect(surface, ink, face, CONTOUR_PX)
    for i in range(2):
        y0 = face.top + MOSS_TOP_PX + i * MOSS_GAP_PX
        points = [(face.left + MOSS_LEFT_PX + x, y0 + MOSS_AMPLITUDE_PX * math.sin(x * math.tau / MOSS_WAVE_PX))
                  for x in range(MOSS_WAVE_PX + 1)]
        pygame.draw.lines(surface, ink, False, points, LINE_PX)


def _temporary(surface: pygame.Surface, face: pygame.Rect, share: float, palette) -> None:
    """§3: a dashed contour and the life bar along the face's south edge (filled share in the text colour)."""
    for (x0, y0), (x1, y1) in ((face.topleft, face.topright), (face.topright, face.bottomright),
                               (face.bottomright, face.bottomleft), (face.bottomleft, face.topleft)):
        length = max(abs(x1 - x0), abs(y1 - y0))
        for s in range(0, length, DASH_PX + GAP_PX):
            e = min(s + DASH_PX, length)
            a = (x0 + (x1 - x0) * s / length, y0 + (y1 - y0) * s / length)
            b = (x0 + (x1 - x0) * e / length, y0 + (y1 - y0) * e / length)
            pygame.draw.line(surface, palette.background, a, b, CONTOUR_PX)
    bar = pygame.Rect(face.left + LIFE_BAR_MARGIN_PX, face.bottom - LIFE_BAR_MARGIN_PX - LIFE_BAR_PX,
                      face.width - 2 * LIFE_BAR_MARGIN_PX, LIFE_BAR_PX)
    surface.fill(palette.background, bar)
    surface.fill(palette.text, (bar.left, bar.top, round(share * bar.width), bar.height))


def _water(screen: pygame.Surface, cfg: Config, polygons: list[list[tuple[float, float]]]) -> None:
    """A row's water polygons on one transparent layer, blended onto the screen once (layout.water_alpha)."""
    lay = cfg.render.layout
    top = math.floor(min(y for polygon in polygons for _, y in polygon))   # whole px: the layer's offset
    bottom = max(y for polygon in polygons for _, y in polygon)
    left = math.floor(board_rect(cfg)[0])
    layer = pygame.Surface((cfg.map.cols * lay.tile_w_px + 1, math.ceil(bottom - top) + 1), pygame.SRCALPHA)
    rgba = (*pygame.Color(cfg.render.palette.water)[:3], round(OPAQUE * lay.water_alpha))
    for polygon in polygons:
        pygame.draw.polygon(layer, rgba, [(x - left, y - top) for x, y in _inset(polygon)])
    screen.blit(layer, (left, top))


def _inset(polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """board.water_polygon's six points (NW, N, NE, SE, S, SW) with the east and south edges SEAM_PX in."""
    east, south = {2, 3}, {3, 4, 5}
    return [(x - SEAM_PX * (i in east), y - SEAM_PX * (i in south)) for i, (x, y) in enumerate(polygon)]


def _rect(rect: Rect) -> pygame.Rect:
    x, y, w, h = rect
    return pygame.Rect(round(x), round(y), round(w), round(h))
