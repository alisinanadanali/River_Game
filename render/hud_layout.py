"""VISUALS §4, §5: where the HUD's pieces go, in px. Pure: no pygame.

Every piece is a rectangle (x, y, w, h); a text's rectangle is the box it is drawn in. A dial is (cx, cy, r).
The panels are laid out top to bottom: a section's label line, then its pieces, then a gap.
"""

import dataclasses
from dataclasses import dataclass

from engine.config import Config
from render.layout import Rect

# Structural sizes (px), not model numbers
PAD_PX = 12               # the panels' inner margin
FONT_PX = 15              # the HUD font's size
LINE_PX = 20              # one text line of the HUD font
GAP_PX = 10               # between sections
BAR_PX = 14               # the balance and stance bars' height
SQUARE_PX = 22            # a bag's volume square
SQUARE_GAP_PX = 3
MASS_BAR_PX = 10          # a bag's mass bar width
BAG_SPACING_PX = 100      # from the left bag's squares to the right bag's
BADGE_PX = 28             # the depth badge
ARROW_PX = 20             # the stance arrow
SLOT_PX = 34              # a bank slot
SLOT_GAP_PX = 4
DIAL_R_PX = 16            # a cooldown dial's radius
DIAL_SPACING_PX = 90
DAM_BAR_W_PX = 24
DAM_BAR_H_PX = 110
TIME_BAR_PX = 4           # the time bar along the top bar's bottom edge
HEART_PX = 20
HEART_GAP_PX = 6

Dial = tuple[float, float, float]
DIAL_LEN = 3              # (cx, cy, r): told apart from a rectangle by its length


@dataclass(frozen=True)
class TopRects:
    time_bar: Rect
    hearts: tuple[Rect, ...]


@dataclass(frozen=True)
class DonkeyRects:
    panel: Rect
    title: Rect
    balance_label: Rect
    balance_bar: Rect
    balance_text: Rect
    bags_label: Rect
    squares: tuple[tuple[Rect, ...], tuple[Rect, ...]]    # left, right; bottom to top
    mass_bars: tuple[Rect, Rect]
    mass_texts: tuple[Rect, Rect]
    depth_label: Rect
    badge: Rect
    depth_text: Rect
    stance_label: Rect
    arrow: Rect
    stance_bar: Rect
    stance_text: Rect


@dataclass(frozen=True)
class ShrekRects:
    panel: Rect
    title: Rect
    queue_label: Rect
    slots: tuple[Rect, ...]                               # the head first
    next_label: Rect
    next_lines: tuple[Rect, Rect]
    cooldown_label: Rect
    dials: tuple[Dial, Dial]                              # throw, rock
    dial_labels: tuple[Rect, Rect]
    rocks_text: Rect
    dam_label: Rect
    dam_bar: Rect
    dam_lines: tuple[Rect, Rect]


def top_rects(cfg: Config) -> TopRects:
    """The time bar along the top bar's bottom edge; the hearts at its right end, the first life leftmost."""
    w, top = cfg.render.window_px[0], cfg.render.layout.top_bar_px
    lives = cfg.time.lives
    y = (top - TIME_BAR_PX - HEART_PX) / 2
    right = w - PAD_PX
    hearts = tuple((right - (lives - i) * HEART_PX - (lives - 1 - i) * HEART_GAP_PX, y, HEART_PX, HEART_PX)
                   for i in range(lives))
    return TopRects((0, top - TIME_BAR_PX, w, TIME_BAR_PX), hearts)


class _Column:
    """A cursor down a panel's inner column."""

    def __init__(self, panel: Rect):
        self.left, self.y = panel[0] + PAD_PX, panel[1] + PAD_PX
        self.width = panel[2] - 2 * PAD_PX

    def line(self) -> Rect:
        rect = (self.left, self.y, self.width, LINE_PX)
        self.y += LINE_PX
        return rect

    def gap(self) -> None:
        self.y += GAP_PX


def _panel(cfg: Config, x: float) -> Rect:
    lay, h = cfg.render.layout, cfg.render.window_px[1]
    return (x, lay.top_bar_px, lay.side_panel_px, h - lay.top_bar_px - lay.bottom_bar_px)


def donkey_rects(cfg: Config) -> DonkeyRects:
    """The left panel: title, balance, bags, depth, stance."""
    panel = _panel(cfg, 0)
    col = _Column(panel)
    left, width = col.left, col.width
    title = col.line()
    col.gap()
    balance_label = col.line()
    balance_bar = (left, col.y, width, BAR_PX)
    col.y += BAR_PX
    balance_text = col.line()
    col.gap()
    bags_label = col.line()
    volume = cfg.donkey.bag_max_volume_per_side
    stack = volume * SQUARE_PX + (volume - 1) * SQUARE_GAP_PX
    squares, bars = [], []
    for side in range(2):
        x = left + side * BAG_SPACING_PX
        squares.append(tuple((x, col.y + stack - (k + 1) * SQUARE_PX - k * SQUARE_GAP_PX, SQUARE_PX, SQUARE_PX)
                             for k in range(volume)))
        bars.append((x + SQUARE_PX + SQUARE_GAP_PX, col.y, MASS_BAR_PX, stack))
    col.y += stack
    mass_texts = ((left, col.y, BAG_SPACING_PX - SQUARE_GAP_PX, LINE_PX),
                  (left + BAG_SPACING_PX, col.y, width - BAG_SPACING_PX, LINE_PX))
    col.y += LINE_PX
    col.gap()
    depth_label = col.line()
    badge = (left, col.y, BADGE_PX, BADGE_PX)
    beside = left + BADGE_PX + GAP_PX
    depth_text = (beside, col.y + (BADGE_PX - LINE_PX) / 2, left + width - beside, LINE_PX)
    col.y += BADGE_PX
    col.gap()
    stance_label = col.line()
    arrow = (left, col.y, ARROW_PX, ARROW_PX)
    bar_x = left + ARROW_PX + GAP_PX
    stance_bar = (bar_x, col.y + (ARROW_PX - BAR_PX) / 2, width / 2, BAR_PX)
    text_x = bar_x + width / 2 + GAP_PX
    stance_text = (text_x, col.y + (ARROW_PX - LINE_PX) / 2, left + width - text_x, LINE_PX)
    return DonkeyRects(panel, title, balance_label, balance_bar, balance_text, bags_label,
                       (squares[0], squares[1]), (bars[0], bars[1]), mass_texts, depth_label, badge, depth_text,
                       stance_label, arrow, stance_bar, stance_text)


def shrek_rects(cfg: Config) -> ShrekRects:
    """The right panel: title, bank queue, next item, cooldowns and rocks, dam."""
    panel = _panel(cfg, cfg.render.window_px[0] - cfg.render.layout.side_panel_px)
    col = _Column(panel)
    left, width = col.left, col.width
    title = col.line()
    col.gap()
    queue_label = col.line()
    capacity = cfg.items.bank_capacity
    size = min(SLOT_PX, (width - (capacity - 1) * SLOT_GAP_PX) / capacity)
    slots = tuple((left + i * (size + SLOT_GAP_PX), col.y, size, size) for i in range(capacity))
    col.y += size
    col.gap()
    next_label = col.line()
    next_lines = (col.line(), col.line())
    col.gap()
    cooldown_label = col.line()
    dials = tuple((left + DIAL_R_PX + i * DIAL_SPACING_PX, col.y + DIAL_R_PX, DIAL_R_PX) for i in range(2))
    col.y += 2 * DIAL_R_PX
    dial_labels = ((left, col.y, DIAL_SPACING_PX - GAP_PX, LINE_PX),
                   (left + DIAL_SPACING_PX, col.y, width - DIAL_SPACING_PX, LINE_PX))
    col.y += LINE_PX
    rocks_text = col.line()
    col.gap()
    dam_label = col.line()
    dam_bar = (left, col.y, DAM_BAR_W_PX, DAM_BAR_H_PX)
    beside = left + DAM_BAR_W_PX + GAP_PX
    dam_lines = tuple((beside, col.y + i * LINE_PX, left + width - beside, LINE_PX) for i in range(2))
    return ShrekRects(panel, title, queue_label, slots, next_label, next_lines, cooldown_label, dials, dial_labels,
                      rocks_text, dam_label, dam_bar, dam_lines)


def pieces(layout: DonkeyRects | ShrekRects) -> list[Rect]:
    """Every piece but the panel, as rectangles (a dial as its bounding box)."""
    found: list[Rect] = []

    def add(value):
        if isinstance(value[0], int | float):
            if len(value) == DIAL_LEN:
                cx, cy, r = value
                found.append((cx - r, cy - r, 2 * r, 2 * r))
            else:
                found.append(value)
        else:
            for v in value:
                add(v)

    for f in dataclasses.fields(layout):
        if f.name != "panel":
            add(getattr(layout, f.name))
    return found
