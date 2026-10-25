"""VISUALS §4, §5: where the HUD's pieces go. Pure, for every profile: each piece inside its panel, none overlapping.

Every piece is a rectangle (x, y, w, h) in px, texts too (the box the text is drawn in); a dial is (cx, cy, r).
"""

from itertools import combinations

import pytest

from engine.config import load_config
from render.hud_layout import donkey_rects, pieces, shrek_rects, top_rects

PROFILES = [None, "warmup", "percolation_edge", "hard"]


@pytest.fixture(params=PROFILES, ids=lambda p: p or "default")
def cfg(request):
    return load_config(request.param)


def inside(rect, area) -> bool:
    x, y, w, h = rect
    ax, ay, aw, ah = area
    return ax <= x and ay <= y and x + w <= ax + aw and y + h <= ay + ah


def overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def test_the_panels_are_the_side_strips(cfg):
    lay, (w, h) = cfg.render.layout, cfg.render.window_px
    middle = h - lay.top_bar_px - lay.bottom_bar_px
    assert donkey_rects(cfg).panel == (0, lay.top_bar_px, lay.side_panel_px, middle)          # the donkey on the left
    assert shrek_rects(cfg).panel == (w - lay.side_panel_px, lay.top_bar_px, lay.side_panel_px, middle)


@pytest.mark.parametrize("rects", [donkey_rects, shrek_rects], ids=["donkey", "shrek"])
def test_every_piece_is_inside_its_panel_and_none_overlap(cfg, rects):
    layout = rects(cfg)
    every = pieces(layout)
    assert len(every) > 10
    assert all(inside(r, layout.panel) for r in every)
    clashes = [(a, b) for a, b in combinations(every, 2) if overlap(a, b)]
    assert not clashes, clashes[:3]


def test_pieces_lists_every_rectangle_and_dial():
    """The check above sees every field: a rectangle, a tuple of them, or a dial as its bounding box."""
    cfg = load_config()
    d = donkey_rects(cfg)
    every = pieces(d)
    assert d.balance_bar in every and d.squares[1][-1] in every and d.stance_text in every
    s = shrek_rects(cfg)
    cx, cy, r = s.dials[1]
    assert (cx - r, cy - r, 2 * r, 2 * r) in pieces(s) and s.slots[-1] in pieces(s) and s.panel not in pieces(s)


def test_the_bag_squares_stack_upwards_one_per_volume_unit(cfg):
    d = donkey_rects(cfg)
    for squares, bar in zip(d.squares, d.mass_bars, strict=True):
        assert len(squares) == cfg.donkey.bag_max_volume_per_side
        assert [s[1] for s in squares] == sorted((s[1] for s in squares), reverse=True)      # bottom first
        assert bar[1] == squares[-1][1] and bar[1] + bar[3] == squares[0][1] + squares[0][3]  # as tall as the stack
    assert d.squares[0][0][0] < d.squares[1][0][0]                                          # left, then right


def test_one_slot_per_bank_place_and_two_dials(cfg):
    s = shrek_rects(cfg)
    assert len(s.slots) == cfg.items.bank_capacity
    assert [r[0] for r in s.slots] == sorted(r[0] for r in s.slots)                          # the head on the left
    assert len(s.dials) == 2


def test_the_top_bar_has_a_time_bar_across_and_a_heart_per_life(cfg):
    t = top_rects(cfg)
    w, lay = cfg.render.window_px[0], cfg.render.layout
    x, y, bw, bh = t.time_bar
    assert (x, bw) == (0, w) and y + bh == lay.top_bar_px
    assert len(t.hearts) == cfg.time.lives
    assert all(inside(h, (0, 0, w, y)) for h in t.hearts)
    apart = [(x - 1, y - 1, w + 2, h + 2) for x, y, w, h in t.hearts]               # not even touching: countable
    assert not any(overlap(a, b) for a, b in combinations(apart, 2))
