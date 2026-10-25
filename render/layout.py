"""VISUALS §2, §4, §4.1: where things are on the screen. Pure: px from render.layout, no pygame.

The 3/4 oblique projection: x = x0 + c · tile_w, y = y0 + (R − 1 − r) · tile_h − z · px_per_cm, with (x0, y0) the
top-left corner of row R − 1 at z = 0 and z in cm on the engine's scale (relative to μ, may be negative). Row −1
(south bank) is at the bottom, row R (north bank) on top. Rows and columns may be fractional (between two cells
while a tick is interpolated).
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
    """§2: the river, both banks and the room above them for rising z, centred in the map area."""
    lay = cfg.render.layout
    w = cfg.map.cols * lay.tile_w_px
    h = (cfg.map.rows + BANK_ROWS) * lay.tile_h_px + _room_px(cfg)
    ax, ay, aw, ah = map_area(cfg)
    return (ax + (aw - w) / 2, ay + (ah - h) / 2, w, h)


def cell_rect(cfg: Config, row: float, col: float, z: float = 0.0) -> Rect:
    """§2: the cell at height z (its top face, if something stands there)."""
    lay = cfg.render.layout
    x, y, _, _ = board_rect(cfg)
    x0, y0 = x, y + _room_px(cfg) + lay.tile_h_px            # row R − 1 at z = 0, under the room and the north bank
    return (x0 + col * lay.tile_w_px, y0 + (cfg.map.rows - 1 - row) * lay.tile_h_px - z * lay.px_per_cm,
            lay.tile_w_px, lay.tile_h_px)


def cell_center(cfg: Config, row: float, col: float, z: float = 0.0) -> tuple[float, float]:
    x, y, w, h = cell_rect(cfg, row, col, z)
    return (x + w / 2, y + h / 2)


def feet(cfg: Config, role: Role, cell: tuple[float, float], z: float = 0.0) -> tuple[float, float]:
    """§4.1: feet on the surface at height z; the donkey's on its cell's centre, Shrek's on his bank cell's south
    edge (they never overlap)."""
    x, y = cell_center(cfg, *cell, z)
    if role is Role.SHREK:
        return (x, y + SHREK_FEET_SOUTH * cfg.render.layout.tile_h_px)
    return (x, y)



def water_line(cfg: Config, feet_y: float, depth_cm: float | None) -> float | None:
    """§9.1: the screen y of the water line over feet standing depth_cm under the water; None without water."""
    if depth_cm is None or depth_cm <= 0:
        return None
    return feet_y - depth_cm * cfg.render.layout.px_per_cm


def rows_back_to_front(cfg: Config) -> list[int]:
    """§2 drawing order: the north bank, the river from north to south, the south bank."""
    return list(range(cfg.map.rows, -BANK_ROWS, -1))


def _room_px(cfg: Config) -> float:
    lay = cfg.render.layout
    return lay.z_room_cm * lay.px_per_cm
