"""VISUALS §2, §4.1: the oblique board geometry, pure, for every profile."""

import pytest

from engine.config import load_config
from engine.events import Role
from render.layout import board_rect, cell_center, cell_rect, feet, map_area, rows_back_to_front, water_line

PROFILES = [None, "warmup", "percolation_edge", "hard"]


@pytest.fixture(params=PROFILES, ids=lambda p: p or "default")
def cfg(request):
    return load_config(request.param)


def room_px(cfg):
    return cfg.render.layout.z_room_cm * cfg.render.layout.px_per_cm


def test_the_map_area_is_the_window_minus_the_bars_and_the_panels(cfg):
    lay, (w, h) = cfg.render.layout, cfg.render.window_px
    assert map_area(cfg) == (lay.side_panel_px, lay.top_bar_px, w - 2 * lay.side_panel_px,
                             h - lay.top_bar_px - lay.bottom_bar_px)


def test_the_board_and_its_room_fit_in_the_middle_of_the_map_area(cfg):
    lay = cfg.render.layout
    x, y, w, h = board_rect(cfg)
    assert (w, h) == (cfg.map.cols * lay.tile_w_px, (cfg.map.rows + 2) * lay.tile_h_px + room_px(cfg))
    ax, ay, aw, ah = map_area(cfg)
    assert x - ax == pytest.approx(ax + aw - (x + w)) and x >= ax          # centred and inside
    assert y - ay == pytest.approx(ay + ah - (y + h)) and y >= ay


def test_north_is_up_the_banks_are_the_outer_rows_and_the_room_is_on_top(cfg):
    lay, rows = cfg.render.layout, cfg.map.rows
    x, y, w, h = board_rect(cfg)
    assert cell_rect(cfg, rows, 0)[:2] == (x, y + room_px(cfg))           # the north bank at z = 0, under the room
    assert cell_rect(cfg, -1, cfg.map.cols - 1) == (x + w - lay.tile_w_px, y + h - lay.tile_h_px, lay.tile_w_px,
                                                    lay.tile_h_px)          # the south bank at the bottom
    for r in range(-1, rows):
        assert cell_center(cfg, r, 0)[1] - cell_center(cfg, r + 1, 0)[1] == lay.tile_h_px
    for c in range(cfg.map.cols - 1):
        assert cell_center(cfg, 0, c + 1)[0] - cell_center(cfg, 0, c)[0] == lay.tile_w_px


@pytest.mark.parametrize("z", [-12.5, 0.0, 7.0, 40.0])
def test_height_lifts_a_cell_by_px_per_cm(cfg, z):
    """§2: y = y0 + (R − 1 − r) · tile_h − z · px_per_cm; x does not change."""
    x, y, w, h = cell_rect(cfg, 3, 2)
    assert cell_rect(cfg, 3, 2, z) == pytest.approx((x, y - z * cfg.render.layout.px_per_cm, w, h))
    assert cell_center(cfg, 3, 2, z)[1] == pytest.approx(cell_center(cfg, 3, 2)[1] - z * cfg.render.layout.px_per_cm)


def test_the_formula_of_section_2(cfg):
    lay, rows = cfg.render.layout, cfg.map.rows
    x0, y0, _, _ = cell_rect(cfg, rows - 1, 0)                             # (x0, y0): row R − 1 at z = 0
    for r, c, z in [(0, 0, 0.0), (4, 7, 10.0), (-1, 3, -5.0), (rows, 8, 25.0)]:
        assert cell_rect(cfg, r, c, z)[:2] == pytest.approx(
            (x0 + c * lay.tile_w_px, y0 + (rows - 1 - r) * lay.tile_h_px - z * lay.px_per_cm))


def test_the_centre_is_the_middle_of_the_cell(cfg):
    x, y, w, h = cell_rect(cfg, 3, 2, 5.0)
    assert cell_center(cfg, 3, 2, 5.0) == (x + w / 2, y + h / 2)


def test_the_donkey_stands_in_the_middle_and_shrek_on_the_south_edge(cfg):
    cx, cy = cell_center(cfg, -1, 4, 25.0)
    assert feet(cfg, Role.DONKEY, (-1, 4), 25.0) == (cx, cy)
    assert feet(cfg, Role.SHREK, (-1, 4), 25.0) == (cx, cy + cfg.render.layout.tile_h_px / 2)
    assert feet(cfg, Role.DONKEY, (2.5, 4), 3.0) == cell_center(cfg, 2.5, 4, 3.0)  # between cells: interpolation


def test_rows_are_drawn_from_the_north_bank_to_the_south_bank(cfg):
    assert rows_back_to_front(cfg) == list(range(cfg.map.rows, -2, -1))


@pytest.mark.parametrize("depth", [None, 0.0, -3.0])
def test_no_water_line_without_water_over_the_feet(cfg, depth):
    assert water_line(cfg, 300.0, depth) is None


def test_the_water_line_is_the_depth_above_the_feet(cfg):
    """VISUALS §9.1: d · px_per_cm px above the feet, on §2's scale."""
    assert water_line(cfg, 300.0, 5.0) == pytest.approx(300.0 - 5.0 * cfg.render.layout.px_per_cm)
