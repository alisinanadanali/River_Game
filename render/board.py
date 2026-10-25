"""VISUALS §2: the board's heights and shapes, from an observation. Pure: no pygame.

Heights are cm on the engine's scale (relative to μ); render/layout.py turns them into px. `levels` is L(c) per
column as drawn this frame (interpolated between ticks), so the water is not read from the observation here.
"""

from collections.abc import Sequence

from engine.config import Config
from engine.donkey import effective_height, load_kg, stone_under
from engine.observe import Observation
from render.layout import Rect, cell_rect


def is_bank(obs: Observation, row: int) -> bool:
    return row in (-1, obs.world.rows)


def stone_top_z(obs: Observation, row: int, col: int) -> float | None:
    """§2: the top face of the stone at a river cell; e_i under the donkey's load on its own stone (D-01),
    h_i + r_i on an empty permanent stone, h(t) on an empty temporary one. None on water and on the banks."""
    if is_bank(obs, row):
        return None
    stone = stone_under(obs, row, col)    # reads world, stones and config, which an Observation has like a GameState
    if stone is None:
        return None
    h, k = stone
    if (obs.donkey.row, obs.donkey.col) == (row, col):
        return effective_height(h, load_kg(obs.donkey, obs.config), k)
    return h


def surface_z(obs: Observation, levels: Sequence[float], row: int, col: int) -> float:
    """The height of what is seen on top of a cell: the bank top, or the higher of the stone top and the water."""
    if is_bank(obs, row):
        return obs.config.render.layout.bank_z_cm
    top = stone_top_z(obs, row, col)
    return levels[col] if top is None else max(top, levels[col])


def stand_z(obs: Observation, row: int, col: int) -> float:
    """§4.1: where a character's feet are: the bank top, or the top of its stone (the water where there is none)."""
    if is_bank(obs, row):
        return obs.config.render.layout.bank_z_cm
    top = stone_top_z(obs, row, col)
    return float(obs.water.level[col]) if top is None else top


def water_profile(levels: Sequence[float], col: int) -> tuple[float, float, float]:
    """§2: the water's height at the cell's west edge, centre and east edge: linear between column centres, so an
    edge is the mean of its two columns; flat at the board's two ends."""
    mid = levels[col]
    west = mid if col == 0 else (levels[col - 1] + mid) / 2
    east = mid if col == len(levels) - 1 else (mid + levels[col + 1]) / 2
    return (west, mid, east)


def water_polygon(cfg: Config, levels: Sequence[float], row: int, col: int) -> list[tuple[float, float]]:
    """§2: the cell's water, one tile deep, its top and bottom edges following the profile (clockwise from NW)."""
    x, y, w, h = cell_rect(cfg, row, col)
    px = cfg.render.layout.px_per_cm
    lifts = [z * px for z in water_profile(levels, col)]
    xs = (x, x + w / 2, x + w)
    return [(xi, y - lift) for xi, lift in zip(xs, lifts)] + \
           [(xi, y + h - lift) for xi, lift in reversed(list(zip(xs, lifts)))]


def front_face(cfg: Config, row: int, col: int, top_z: float, level: float) -> Rect | None:
    """§2: the prism's front, from the top face's south edge down to `level`; None when the top is not above it."""
    if top_z <= level:
        return None
    x, y, w, h = cell_rect(cfg, row, col, top_z)
    return (x, y + h, w, (top_z - level) * cfg.render.layout.px_per_cm)
