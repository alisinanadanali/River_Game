"""VISUALS §4.1: the walking skeleton's frame (pygame). It draws a Scene and nothing else.

Order: background, the board (banks, stones, water), the shadows of flying items, the characters, the aim frame
(on top: Shrek's sprite reaches over the first river rows), the top bar and the banner.
"""

from dataclasses import dataclass

import pygame

from engine.config import Config
from engine.donkey import stone_under
from engine.events import Role
from render.characters.sprites import CharacterSprites, draw, load_character
from render.fonts import load_font
from render.layout import cell_center, cell_rect
from render.scene import Scene, banner, top_bar

FONT_PX = 20
AIM_FRAME_PX = 3          # the aim frame's line width
SHADOW_SHARE = 0.25       # a flying item's shadow: an ellipse this share of the tile, on its target cell
TEXT_MARGIN_PX = 12       # the top bar's text from the window's left edge


@dataclass(frozen=True)
class Assets:
    font: pygame.font.Font
    sprites: dict[Role, CharacterSprites]


def load_assets(cfg: Config) -> Assets:
    return Assets(load_font(cfg, FONT_PX), {role: load_character(role, cfg) for role in Role})


def draw_scene(screen: pygame.Surface, assets: Assets, scene: Scene) -> None:
    obs = scene.obs
    cfg, palette = obs.config, obs.config.render.palette
    screen.fill(palette.background)
    _board(screen, scene)
    lay = cfg.render.layout
    for projectile in obs.projectiles:
        x, y = cell_center(cfg, *projectile.target)
        w, h = lay.tile_w_px * SHADOW_SHARE * 2, lay.tile_h_px * SHADOW_SHARE * 2
        pygame.draw.ellipse(screen, palette.background, pygame.Rect(round(x - w / 2), round(y - h / 2), w, h))
    for role in (Role.SHREK, Role.DONKEY):                  # the donkey in front of Shrek (south bank start)
        draw(screen, assets.sprites[role], scene.looks[role], scene.feet[role])
    pygame.draw.rect(screen, palette.text, _rect(cell_rect(cfg, obs.shrek.aim_row, obs.shrek.col)), AIM_FRAME_PX)
    text = assets.font.render(top_bar(scene), True, palette.text)
    screen.blit(text, (TEXT_MARGIN_PX, (lay.top_bar_px - text.get_height()) // 2))
    line = banner(scene)
    if line is not None:
        text = assets.font.render(line, True, palette.text, palette.background)
        screen.blit(text, text.get_rect(center=screen.get_rect().center))


def _board(screen: pygame.Surface, scene: Scene) -> None:
    obs = scene.obs
    cfg, palette = obs.config, obs.config.render.palette
    rows, cols = obs.world.rows, obs.world.cols
    for c in range(cols):
        for r in (-1, rows):
            screen.fill(palette.bank, _rect(cell_rect(cfg, r, c)))
        for r in range(rows):
            colour = palette.water if stone_under(obs, r, c) is None else palette.dry
            screen.fill(colour, _rect(cell_rect(cfg, r, c)))


def _rect(rect: tuple[float, float, float, float]) -> pygame.Rect:
    x, y, w, h = rect
    return pygame.Rect(round(x), round(y), round(w), round(h))
