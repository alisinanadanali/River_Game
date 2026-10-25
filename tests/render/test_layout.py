"""VISUALS §4.1: the walking skeleton's flat board geometry (§2 with z = 0), pure, for every profile."""

import pytest

from engine.config import load_config
from engine.events import Role
from render.layout import board_rect, cell_center, cell_rect, feet, map_area

PROFILES = [None, "warmup", "percolation_edge", "hard"]


@pytest.fixture(params=PROFILES, ids=lambda p: p or "default")
def cfg(request):
    return load_config(request.param)


def test_the_map_area_is_the_window_minus_the_bars_and_the_panels(cfg):
    lay, (w, h) = cfg.render.layout, cfg.render.window_px
    assert map_area(cfg) == (lay.side_panel_px, lay.top_bar_px, w - 2 * lay.side_panel_px,
                             h - lay.top_bar_px - lay.bottom_bar_px)


def test_the_board_is_the_river_and_both_banks_in_the_middle_of_the_map_area(cfg):
    lay = cfg.render.layout
    x, y, w, h = board_rect(cfg)
    assert (w, h) == (cfg.map.cols * lay.tile_w_px, (cfg.map.rows + 2) * lay.tile_h_px)
    ax, ay, aw, ah = map_area(cfg)
    assert x - ax == pytest.approx(ax + aw - (x + w)) and x >= ax          # centred and inside
    assert y - ay == pytest.approx(ay + ah - (y + h)) and y >= ay


def test_north_is_up_and_the_banks_are_the_outer_rows(cfg):
    lay, rows = cfg.render.layout, cfg.map.rows
    x, y, w, h = board_rect(cfg)
    assert cell_rect(cfg, rows, 0)[:2] == (x, y)                            # the north bank on top
    assert cell_rect(cfg, -1, cfg.map.cols - 1) == (x + w - lay.tile_w_px, y + h - lay.tile_h_px, lay.tile_w_px,
                                                    lay.tile_h_px)          # the south bank at the bottom
    for r in range(-1, rows):
        assert cell_center(cfg, r, 0)[1] - cell_center(cfg, r + 1, 0)[1] == lay.tile_h_px
    for c in range(cfg.map.cols - 1):
        assert cell_center(cfg, 0, c + 1)[0] - cell_center(cfg, 0, c)[0] == lay.tile_w_px


def test_the_centre_is_the_middle_of_the_cell(cfg):
    x, y, w, h = cell_rect(cfg, 3, 2)
    assert cell_center(cfg, 3, 2) == (x + w / 2, y + h / 2)


def test_the_donkey_stands_in_the_middle_and_shrek_on_the_south_edge(cfg):
    cx, cy = cell_center(cfg, -1, 4)
    assert feet(cfg, Role.DONKEY, (-1, 4)) == (cx, cy)
    assert feet(cfg, Role.SHREK, (-1, 4)) == (cx, cy + cfg.render.layout.tile_h_px / 2)
    assert feet(cfg, Role.DONKEY, (2.5, 4)) == cell_center(cfg, 2.5, 4)    # between cells: interpolation
