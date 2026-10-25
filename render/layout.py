"""VISUALS §4, §4.1: where things are on the screen. Pure: px from render.layout, no pygame.

The walking skeleton's board is flat: VISUALS §2 with z = 0. Row −1 (south bank) is at the bottom, row R (north
bank) on top, column 0 on the west; a cell is tile_w × tile_h. Positions may be fractional (between two cells while
a tick is interpolated).
"""

from engine.config import Config
from engine.events import Role

BANK_ROWS = 2                 # the south bank (row −1) and the north bank (row R) around the river's R rows
SHREK_FEET_SOUTH = 0.5        # Shrek stands this share of tile_h south of his cell's centre: the bank's south edge

Rect = tuple[float, float, float, float]  # left, top, width, height (px)


def map_area(cfg: Config) -> Rect:
    """§4: the window minus the top and bottom bars and the two side panels."""
    lay, (w, h) = cfg.render.layout, cfg.render.window_px
    return (lay.side_panel_px, lay.top_bar_px, w - 2 * lay.side_panel_px, h - lay.top_bar_px - lay.bottom_bar_px)


def board_rect(cfg: Config) -> Rect:
    """The river and both banks, centred in the map area."""
    lay = cfg.render.layout
    w, h = cfg.map.cols * lay.tile_w_px, (cfg.map.rows + BANK_ROWS) * lay.tile_h_px
    ax, ay, aw, ah = map_area(cfg)
    return (ax + (aw - w) / 2, ay + (ah - h) / 2, w, h)


def cell_rect(cfg: Config, row: float, col: float) -> Rect:
    """§2 with z = 0: x = x0 + c · tile_w, y = y0 + (R − r) · tile_h (y0 the board's top, the north bank's row)."""
    lay = cfg.render.layout
    x0, y0, _, _ = board_rect(cfg)
    return (x0 + col * lay.tile_w_px, y0 + (cfg.map.rows - row) * lay.tile_h_px, lay.tile_w_px, lay.tile_h_px)


def cell_center(cfg: Config, row: float, col: float) -> tuple[float, float]:
    x, y, w, h = cell_rect(cfg, row, col)
    return (x + w / 2, y + h / 2)


def feet(cfg: Config, role: Role, cell: tuple[float, float]) -> tuple[float, float]:
    """§4.1: the donkey's feet on its cell's centre, Shrek's on his bank cell's south edge (they never overlap)."""
    x, y = cell_center(cfg, *cell)
    if role is Role.SHREK:
        return (x, y + SHREK_FEET_SOUTH * cfg.render.layout.tile_h_px)
    return (x, y)
