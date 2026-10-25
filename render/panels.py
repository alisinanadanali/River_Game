"""VISUALS §5: the HUD drawn (pygame): the time bar and hearts, the donkey's and Shrek's panels.

Where each piece goes is render/hud_layout.py, what it shows is render/hud.py; this module only paints. Bars get a
thin `palette.bank` outline and fill over it, so a fill's length in px is its share of the bar.
"""

import math

import pygame

from engine.config import Config
from engine.events import Role, Side
from render.colour import tier_colour
from render.hud import BagView, Cooldown, DonkeyPanel, Hud, ShrekPanel, TopBar
from render.hud_layout import DonkeyRects, ShrekRects, donkey_rects, shrek_rects, top_rects
from render.layout import Rect
from render.patterns import draw_pattern
from render.strings_tr import (
    DEPTH_NAMES,
    HUD_BAG_MASS,
    HUD_BAGS,
    HUD_BALANCE,
    HUD_COOLDOWNS,
    HUD_DAM,
    HUD_DAM_IDLE,
    HUD_DAM_VOLUME,
    HUD_DAM_WAVE,
    HUD_DEPTH,
    HUD_DEPTH_CM,
    HUD_MOSSY,
    HUD_NEXT,
    HUD_NEXT_HANDOFF,
    HUD_NEXT_ITEM,
    HUD_NEXT_THROW,
    HUD_NO_STANCE,
    HUD_QUEUE,
    HUD_QUEUE_EMPTY,
    HUD_ROCK,
    HUD_ROCKS,
    HUD_SLIP,
    HUD_STANCE,
    HUD_STANCE_LEFT,
    HUD_STANCE_NONE,
    HUD_THROW,
    ITEM_NAMES,
    ROLE_NAMES,
    tr,
)

OUTLINE_PX = 1
FRAME_PX = 2              # the top item's frame
HEART_LINE_PX = 2         # a lost life's heart outline
HEART_LOBE = 0.25         # a heart's two lobes: circles of this share of its width, on its top
DIAL_STEPS = 32           # a dial's arc as a polygon of this many segments per full turn
PERCENT = 100


def draw_hud(screen: pygame.Surface, font: pygame.font.Font, model: Hud, cfg: Config) -> None:
    _top(screen, model.top, cfg)
    _donkey(screen, font, model.donkey, donkey_rects(cfg), cfg)
    _shrek(screen, font, model.shrek, shrek_rects(cfg), cfg)


# --- pieces ------------------------------------------------------------------------------------------------------

def _rect(rect: Rect) -> pygame.Rect:
    x, y, w, h = rect
    return pygame.Rect(round(x), round(y), round(w), round(h))


def _text(screen, font, text: str, rect: Rect, colour) -> None:
    """The text at the rectangle's top left, cut at its width."""
    r = _rect(rect)
    image = font.render(text, True, colour)
    screen.blit(image, r.topleft, pygame.Rect(0, 0, r.width, r.height))


def _centred(screen, font, text: str, rect: Rect, colour) -> None:
    image = font.render(text, True, colour)
    screen.blit(image, image.get_rect(center=_rect(rect).center))


def _bar(screen, rect: Rect, share: float, colour, outline, *, vertical: bool = False) -> None:
    """An outlined bar filled share ∈ [0, 1] of its length: from the left, or from the bottom."""
    r = _rect(rect)
    pygame.draw.rect(screen, outline, r, OUTLINE_PX)
    share = min(1.0, max(0.0, share))
    if vertical:
        h = round(share * r.height)
        screen.fill(colour, (r.left, r.bottom - h, r.width, h))
    else:
        screen.fill(colour, (r.left, r.top, round(share * r.width), r.height))


def _heart(screen, rect: Rect, colour, filled: bool) -> None:
    x, y, w, h = rect
    r = w * HEART_LOBE
    width = 0 if filled else HEART_LINE_PX
    for cx in (x + r, x + w - r):
        pygame.draw.circle(screen, colour, (cx, y + r), r, width)
    pygame.draw.polygon(screen, colour, [(x, y + r), (x + w, y + r), (x + w / 2, y + h)], width)


def _letter(kind: str) -> str:
    return ITEM_NAMES[kind][0]


# --- the top bar -------------------------------------------------------------------------------------------------

def _top(screen, top: TopBar, cfg: Config) -> None:
    palette, rects = cfg.render.palette, top_rects(cfg)
    x, y, w, h = _rect(rects.time_bar)
    screen.fill(palette.text, (x, y, round(top.time_share * w), h))
    for i, heart in enumerate(rects.hearts):
        alive = i < top.lives
        _heart(screen, heart, palette.danger if alive else palette.text, alive)


# --- the donkey --------------------------------------------------------------------------------------------------

def _donkey(screen, font, panel: DonkeyPanel, rects: DonkeyRects, cfg: Config) -> None:
    palette = cfg.render.palette
    _text(screen, font, ROLE_NAMES[Role.DONKEY], rects.title, palette.text)

    _text(screen, font, HUD_BALANCE, rects.balance_label, palette.text)
    bal = panel.balance
    bar = _rect(rects.balance_bar)
    pygame.draw.rect(screen, palette.bank, bar, OUTLINE_PX)
    reach = round(abs(bal.delta) / bal.limit * bar.width / 2)
    left = bar.centerx - reach if bal.delta < 0 else bar.centerx
    screen.fill(tier_colour(palette, bal.tier), (left, bar.top, reach, bar.height))
    pygame.draw.line(screen, palette.text, (bar.centerx, bar.top), (bar.centerx, bar.bottom - 1), OUTLINE_PX)
    slip = tr(HUD_SLIP, p=PERCENT * bal.p_slip) + (tr(HUD_MOSSY, multiplier=bal.multiplier) if bal.mossy else "")
    _text(screen, font, slip, rects.balance_text, palette.text)

    _text(screen, font, HUD_BAGS, rects.bags_label, palette.text)
    for bag, squares, mass_bar, mass_text in zip(panel.bags, rects.squares, rects.mass_bars, rects.mass_texts,
                                                 strict=True):
        _bag(screen, font, bag, squares, cfg)
        _bar(screen, mass_bar, bag.mass / bag.mass_max, palette.text, palette.bank, vertical=True)
        _text(screen, font, tr(HUD_BAG_MASS, mass=bag.mass, mass_max=bag.mass_max), mass_text, palette.text)

    _text(screen, font, HUD_DEPTH, rects.depth_label, palette.text)
    badge, base = _rect(rects.badge), tier_colour(palette, panel.depth_state)
    screen.fill(base, badge)
    draw_pattern(screen, badge, panel.depth_state, base, palette.background)
    name = DEPTH_NAMES[panel.depth_state]
    depth = name if panel.depth_cm is None else tr(HUD_DEPTH_CM, name=name, depth=panel.depth_cm)
    _text(screen, font, depth, rects.depth_text, palette.text)

    stance = panel.stance
    if stance is None:                                        # on the label's line: the arrow's row stays empty
        _text(screen, font, HUD_STANCE_NONE.format(stance=HUD_STANCE, none=HUD_NO_STANCE), rects.stance_label,
              palette.text)
        return
    _text(screen, font, HUD_STANCE, rects.stance_label, palette.text)
    x, y, w, h = rects.arrow
    tip, base_x = (x, x + w) if stance.side is Side.LEFT else (x + w, x)
    pygame.draw.polygon(screen, palette.text, [(tip, y + h / 2), (base_x, y), (base_x, y + h)])
    _bar(screen, rects.stance_bar, stance.ticks_left / stance.ticks_max, palette.text, palette.bank)
    _text(screen, font, tr(HUD_STANCE_LEFT, seconds=stance.seconds_left), rects.stance_text, palette.text)


def _bag(screen, font, bag: BagView, squares: tuple[Rect, ...], cfg: Config) -> None:
    """D-09's stack: each item fills its volume of squares from the bottom, its letter on its top square; the top
    item is framed."""
    palette = cfg.render.palette
    for square in squares:
        pygame.draw.rect(screen, palette.bank, _rect(square), OUTLINE_PX)
    start = 0
    for i, (kind, volume) in enumerate(zip(bag.kinds, bag.volumes, strict=True)):
        own = [_rect(s) for s in squares[start:start + volume]]
        for square in own:
            screen.fill(palette.bank, square)
        _centred(screen, font, _letter(kind), own[-1], palette.text)
        if i == len(bag.kinds) - 1:
            pygame.draw.rect(screen, palette.text, own[0].unionall(own), FRAME_PX)
        start += volume


# --- Shrek -------------------------------------------------------------------------------------------------------

def _shrek(screen, font, panel: ShrekPanel, rects: ShrekRects, cfg: Config) -> None:
    palette = cfg.render.palette
    _text(screen, font, ROLE_NAMES[Role.SHREK], rects.title, palette.text)

    _text(screen, font, HUD_QUEUE.format(queued=len(panel.queue), capacity=panel.capacity), rects.queue_label,
          palette.text)
    fill = palette.danger if panel.queue_warn else palette.bank
    for i, slot in enumerate(rects.slots):
        if i < len(panel.queue):
            screen.fill(fill, _rect(slot))
            _centred(screen, font, _letter(panel.queue[i]), slot, palette.text)
        else:
            pygame.draw.rect(screen, palette.bank, _rect(slot), OUTLINE_PX)

    _text(screen, font, HUD_NEXT, rects.next_label, palette.text)
    item = panel.next_item
    if item is None:
        lines = (HUD_QUEUE_EMPTY, "")
    else:
        what = tr(HUD_NEXT_ITEM, name=ITEM_NAMES[item.kind], mass=item.mass, volume=item.volume)
        how = HUD_NEXT_HANDOFF if item.handoff else tr(HUD_NEXT_THROW, sigma=item.sigma, p=PERCENT * item.p_catch)
        lines = (what, how)
    for line, rect in zip(lines, rects.next_lines, strict=True):
        _text(screen, font, line, rect, palette.text)

    _text(screen, font, HUD_COOLDOWNS, rects.cooldown_label, palette.text)
    for cooldown, dial, label, name in zip((panel.throw, panel.rock), rects.dials, rects.dial_labels,
                                           (HUD_THROW, HUD_ROCK), strict=True):
        _dial(screen, cooldown, dial, cfg)
        _text(screen, font, name, label, palette.text)
    _text(screen, font, HUD_ROCKS.format(active=panel.rocks_active, max=panel.rocks_max), rects.rocks_text,
          palette.text)

    _text(screen, font, HUD_DAM, rects.dam_label, palette.text)
    dam = panel.dam
    colour = palette.danger if dam.flash_on else palette.water
    _bar(screen, rects.dam_bar, dam.volume / dam.q_max, colour, palette.bank, vertical=True)
    if dam.active:
        lines = (tr(HUD_DAM_VOLUME, volume=dam.volume, q_max=dam.q_max), tr(HUD_DAM_WAVE, amplitude=dam.amplitude_cm))
    else:
        lines = (HUD_DAM_IDLE, "")
    for line, rect in zip(lines, rects.dam_lines, strict=True):
        _text(screen, font, line, rect, palette.text)


def _dial(screen, cooldown: Cooldown, dial, cfg: Config) -> None:
    """The ready part (1 − share) as a pie from the top, clockwise; a full disc is ready."""
    palette = cfg.render.palette
    cx, cy, r = dial
    ready = 1 - cooldown.share
    if ready >= 1:
        pygame.draw.circle(screen, palette.dry, (cx, cy), r)
    elif ready > 0:
        steps = max(1, math.ceil(DIAL_STEPS * ready))
        arc = [(cx + r * math.sin(math.tau * ready * k / steps), cy - r * math.cos(math.tau * ready * k / steps))
               for k in range(steps + 1)]
        pygame.draw.polygon(screen, palette.dry, [(cx, cy), *arc])
    pygame.draw.circle(screen, palette.bank, (cx, cy), r, OUTLINE_PX)
