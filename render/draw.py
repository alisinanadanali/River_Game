"""VISUALS §2, §4.1: the frame (pygame). It draws a Scene and nothing else.

Order (§2): the background; the rows from the north bank to the south bank, each row's stones (top face, front
face) then its water, then the characters drawn with that row; on top, the shadows of flying items and the aim frame
(Shrek's sprite reaches over the first river rows), the top bar and the banner.
"""

import math
from dataclasses import dataclass

import pygame

from engine.config import Config
from engine.events import Role
from render.board import front_face, is_bank, stone_top_z, surface_z, water_polygon
from render.characters.sprites import CharacterSprites, draw, load_character
from render.fonts import load_font
from render.layout import Rect, board_rect, cell_center, cell_rect, rows_back_to_front
from render.scene import Scene, banner, top_bar

FONT_PX = 20
AIM_FRAME_PX = 3          # the aim frame's line width
SHADOW_SHARE = 0.25       # a flying item's shadow: an ellipse this share of the tile, on its target cell
TEXT_MARGIN_PX = 12       # the top bar's text from the window's left edge
OPAQUE = 255
SEAM_PX = 1               # pygame fills a polygon's edges: the east and south edges move in, so neighbours
                          # (east in the row, south in the next row's layer) do not share a twice-blended line
CHARACTER_ORDER = (Role.SHREK, Role.DONKEY)   # in one row the donkey is in front (both start on the south bank)


@dataclass(frozen=True)
class Assets:
    font: pygame.font.Font
    sprites: dict[Role, CharacterSprites]


def load_assets(cfg: Config) -> Assets:
    return Assets(load_font(cfg, FONT_PX), {role: load_character(role, cfg) for role in Role})


def draw_scene(screen: pygame.Surface, assets: Assets, scene: Scene) -> None:
    obs = scene.obs
    cfg, palette, lay = obs.config, obs.config.render.palette, obs.config.render.layout
    screen.fill(palette.background)
    for r in rows_back_to_front(cfg):
        _row(screen, scene, r)
        for role in CHARACTER_ORDER:
            if scene.rows[role] == r:
                draw(screen, assets.sprites[role], scene.looks[role], scene.feet[role])
    for projectile in obs.projectiles:
        x, y = cell_center(cfg, *projectile.target, surface_z(obs, scene.levels, *projectile.target))
        w, h = lay.tile_w_px * SHADOW_SHARE * 2, lay.tile_h_px * SHADOW_SHARE * 2
        pygame.draw.ellipse(screen, palette.background, pygame.Rect(round(x - w / 2), round(y - h / 2), w, h))
    aim = (obs.shrek.aim_row, obs.shrek.col)
    pygame.draw.rect(screen, palette.text, _rect(cell_rect(cfg, *aim, surface_z(obs, scene.levels, *aim))),
                     AIM_FRAME_PX)
    text = assets.font.render(top_bar(scene), True, palette.text)
    screen.blit(text, (TEXT_MARGIN_PX, (lay.top_bar_px - text.get_height()) // 2))
    line = banner(scene)
    if line is not None:
        text = assets.font.render(line, True, palette.text, palette.background)
        screen.blit(text, text.get_rect(center=screen.get_rect().center))


def _row(screen: pygame.Surface, scene: Scene, r: int) -> None:
    """One row, west to east: on a bank its top and front; in the river each stone's prism, then the row's water."""
    obs = scene.obs
    cfg, palette, lay = obs.config, obs.config.render.palette, obs.config.render.layout
    if is_bank(obs, r):
        for c in range(obs.world.cols):
            _prism(screen, cfg, r, c, lay.bank_z_cm, 0.0, palette.bank)
        return
    water = []
    for c in range(obs.world.cols):
        top, level = stone_top_z(obs, r, c), scene.levels[c]
        if top is not None:
            _prism(screen, cfg, r, c, top, level, palette.dry)
        if top is None or top <= level:
            water.append(water_polygon(cfg, scene.levels, r, c))
    if water:
        _water(screen, cfg, water)


def _prism(screen: pygame.Surface, cfg: Config, r: int, c: int, top_z: float, level: float, colour: str) -> None:
    """§2: the top face at top_z and, if it is above `level`, the darker front face down to it."""
    front = front_face(cfg, r, c, top_z, level)
    if front is not None:
        shade = cfg.render.layout.front_shade
        screen.fill([round(v * shade) for v in pygame.Color(colour)[:3]], _rect(front))
    screen.fill(colour, _rect(cell_rect(cfg, r, c, top_z)))


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
