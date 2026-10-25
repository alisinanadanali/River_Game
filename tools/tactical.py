"""Text tactical mode core (CONTROLS.md §5.1): keys from the keymaps, line parsing, the ASCII map, the play loop.

Pure apart from the read/write callables play() is given; the terminal lives in tools/tactical_cli.py.
Everything shown comes from observe() (MODEL §1 O), never from the state itself.
"""

import dataclasses
import re
from collections.abc import Callable, Iterable
from enum import Enum

from controllers.keyboard import SHREK_COMPONENTS  # keymaps.shrek_alt action → (field, value)
from engine.actions import Actions, DonkeyAction, ShrekAction
from engine.config import Config
from engine.donkey import balance, classify_depth, effective_height, load_kg, stance_ready, stone_under
from engine.events import DepthState, Event, ItemStatus, Role, Side
from engine.items import item_type, round_half_up
from engine.observe import Observation, observe
from engine.shrek import throw_sigma
from engine.state import GameState, new_game
from engine.step import step
from engine.stones import temp_at
from render.strings_tr import (
    DEPTH_NAMES,
    GAME_OVER_REASONS,
    ITEM_NAMES,
    SIDE_NAMES,
    TACTICAL_AIRBORNE,
    TACTICAL_BAD_KEY,
    TACTICAL_BAG,
    TACTICAL_BAG_EMPTY,
    TACTICAL_BAGS,
    TACTICAL_BANK,
    TACTICAL_DAM_HELD,
    TACTICAL_DAM_IDLE,
    TACTICAL_DAM_LOCKED,
    TACTICAL_DONKEY,
    TACTICAL_DONKEY_GLYPH,
    TACTICAL_DONKEY_PROMPT,
    TACTICAL_EVENTS,
    TACTICAL_FLYING,
    TACTICAL_HEADER,
    TACTICAL_HELP,
    TACTICAL_MOVING,
    TACTICAL_NEXT_SIGMA,
    TACTICAL_NO_WAVES,
    TACTICAL_ONE_KEY,
    TACTICAL_QUEUE_EMPTY,
    TACTICAL_QUIT,
    TACTICAL_READY,
    TACTICAL_READY_NEXT_TICK,
    TACTICAL_RESULT,
    TACTICAL_SHREK,
    TACTICAL_SHREK_GLYPH,
    TACTICAL_SHREK_PROMPT,
    TACTICAL_TWO_KEYS,
    TACTICAL_WAIT_ALONE,
    TACTICAL_WATER,
    TURKISH_I,
)

HID_A, HID_Z, HID_SPACE = 4, 29, 44  # USB HID usage page 7 (= SDL scancodes): 4 … 29 are a … z, 44 the space bar
CELL = 4                             # characters per map cell: marker, two glyph characters, marker
EMPTY = "—"                          # an empty list in the panels
TIERS = {DepthState.DRY: "K", DepthState.ANKLE: "B", DepthState.KNEE: "D", DepthState.SWEPT: "!"}


class InputError(ValueError):
    """A typed line that is not a valid action; the message is shown and the line asked again."""


class Quit(Exception):
    """:q or end of input."""


# --- keys ------------------------------------------------------------------------------------------------------

def scancode_char(code: int) -> str:
    """The character a key types on a US layout: letters and the space bar only (others cannot go into a line)."""
    if HID_A <= code <= HID_Z:
        return chr(ord("a") + code - HID_A)
    if code == HID_SPACE:
        return " "
    raise ValueError(f"scancode {code} is not a letter or the space bar and cannot be typed into a line")


def donkey_keys(config: Config) -> dict[str, DonkeyAction]:
    """CONTROLS.md §5.1: keymaps.donkey as typed characters."""
    keymap = config.controls.keymaps.donkey.model_dump()
    return {scancode_char(code): DonkeyAction[name] for name, code in keymap.items()}


def shrek_keys(config: Config) -> dict[str, tuple[str, Enum] | None]:
    """CONTROLS.md §5.1: keymaps.shrek_alt as typed characters → (component, value); None is the wait key."""
    keymap = config.controls.keymaps.shrek_alt.model_dump()
    return {scancode_char(code): SHREK_COMPONENTS.get(name) for name, code in keymap.items()}


# --- parsing lines ---------------------------------------------------------------------------------------------

def parse_donkey(line: str, keys: dict[str, DonkeyAction]) -> DonkeyAction:
    """One key, or an empty line for NOOP."""
    text = line.strip().translate(TURKISH_I).lower()
    if text == "":
        return DonkeyAction.NOOP
    if len(text) > 1:
        raise InputError(TACTICAL_ONE_KEY)
    if text not in keys:
        raise InputError(TACTICAL_BAD_KEY.format(key=text))
    return keys[text]


def parse_shrek(line: str, keys: dict[str, tuple[str, Enum] | None]) -> ShrekAction:
    """At most one key per component, in any order. Spaces are kept: the space bar is the dam key."""
    text = line.strip("\r\n").translate(TURKISH_I).lower()
    chosen: dict[str, tuple[str, Enum]] = {}
    for key in text:
        if key not in keys:
            raise InputError(TACTICAL_BAD_KEY.format(key=key))
        if keys[key] is None:
            if len(text) > 1:
                raise InputError(TACTICAL_WAIT_ALONE)
            continue
        component, value = keys[key]
        if component in chosen:
            raise InputError(TACTICAL_TWO_KEYS.format(a=chosen[component][0], b=key))
        chosen[component] = (key, value)
    return ShrekAction(**{component: value for component, (_, value) in chosen.items()})


# --- the map and the panels ------------------------------------------------------------------------------------

def render(obs: Observation, events: Iterable[Event]) -> str:
    """CONTROLS.md §5.1: the map (north on top), the water level per column, the panels and the last tick's events."""
    return "\n".join([*_map_lines(obs), *_panel_lines(obs), *_event_lines(events)])


def _map_lines(obs: Observation) -> list[str]:
    rows, cols = obs.world.rows, obs.world.cols
    glyphs = {(r, c): _terrain(obs, r, c) for r in range(-1, rows + 1) for c in range(cols)}
    for item in obs.items:
        if item.status is ItemStatus.FLOATING:
            cell = (round(item.pos[0]), round_half_up(item.pos[1]))
            if cell in glyphs:
                glyphs[cell] = "**"
    glyphs[(-1, obs.shrek.col)] = TACTICAL_SHREK_GLYPH
    glyphs[(obs.donkey.row, obs.donkey.col)] = TACTICAL_DONKEY_GLYPH  # in front of Shrek when both stand in one bank cell
    markers = {(obs.shrek.aim_row, obs.shrek.col): "[]"}
    markers.update({p.target: "()" for p in obs.projectiles})  # the shadow sits on the target (VISUALS §5)

    lines = ["    |" + "".join(f" {c:<{CELL - 1}}" for c in range(cols))]
    for r in range(rows, -2, -1):
        cells = []
        for c in range(cols):
            left, right = markers.get((r, c), "  ")
            cells.append(left + glyphs[(r, c)] + right)
        lines.append(f"{r:>3} |" + "".join(cells))
    lines.append("  L |" + "".join(f"{level:>{CELL - 1}.0f} " for level in obs.water.level))
    return lines


def _terrain(obs: Observation, r: int, c: int) -> str:
    """Two characters: bank, water, or the stone's kind and its depth tier for the donkey's current load."""
    if r in (-1, obs.world.rows):
        return ".."
    stone = stone_under(obs, r, c)  # reads world, stones and config, which an Observation has like a GameState
    if stone is None:
        return "~~"
    if obs.world.is_stone[r, c]:
        kind = "m" if obs.world.mossy[r, c] else "#"
    else:
        kind = "o"
    h, k = stone
    d = float(obs.water.level[c]) - effective_height(h, load_kg(obs.donkey, obs.config), k)
    return kind + TIERS[classify_depth(d, obs.config.donkey)]


def _panel_lines(obs: Observation) -> list[str]:
    cfg, donkey, shrek, dam = obs.config, obs.donkey, obs.shrek, obs.dam
    depth = DEPTH_NAMES[donkey.depth_state] + ("" if donkey.depth is None else f" d = {donkey.depth:.1f} cm")
    stance = SIDE_NAMES[donkey.stance]
    if donkey.stance is not Side.NONE:
        stance += TACTICAL_READY if stance_ready(donkey, obs.t) else TACTICAL_READY_NEXT_TICK
    moving = "" if donkey.move_target is None else TACTICAL_MOVING.format(
        target=donkey.move_target, remaining=donkey.move_remaining
    )
    head = obs.bank.queue[0] if obs.bank.queue else None
    next_item = TACTICAL_QUEUE_EMPTY
    if head is not None:
        mass = item_type(cfg.items, obs.items[head].kind).mass_kg
        next_item = TACTICAL_NEXT_SIGMA.format(sigma=throw_sigma(shrek.aim_row, mass, cfg.shrek))
    if dam.active:
        dam_line = TACTICAL_DAM_HELD.format(col=dam.col, volume=dam.volume, q_max=cfg.dam.q_max_cm_cols)
    else:
        dam_line = TACTICAL_DAM_IDLE + (TACTICAL_DAM_LOCKED if dam.burst_lock else "")
    waves = ", ".join(f"x = {w.x:.1f} A = {w.amplitude:.1f} cm" for w in obs.water.waves) or TACTICAL_NO_WAVES
    flying = ", ".join(
        TACTICAL_FLYING.format(name=_item_name(obs, p.item_id), target=p.target, ticks=p.ticks_left)
        for p in obs.projectiles
    )
    floating = ", ".join(
        f"{_item_name(obs, i.id)} ({i.pos[0]:.0f}, {i.pos[1]:.2f})" for i in obs.items if i.status is ItemStatus.FLOATING
    )
    return [
        "",
        TACTICAL_HEADER.format(t=obs.t, length=cfg.time.game_length_ticks, score=obs.score, lives=donkey.lives),
        TACTICAL_DONKEY.format(row=donkey.row, col=donkey.col, depth=depth, stance=stance, moving=moving),
        TACTICAL_BAGS.format(
            left=_bag(obs, donkey.bag_left), right=_bag(obs, donkey.bag_right), balance=balance(donkey, cfg)
        ),
        TACTICAL_SHREK.format(
            col=shrek.col, aim_row=shrek.aim_row, throw_cd=shrek.throw_cooldown, rock_cd=shrek.rock_cooldown,
            temp=len(obs.stones.temp), temp_max=cfg.shrek.rock_max_active,
        ),
        TACTICAL_BANK.format(
            queued=len(obs.bank.queue), capacity=cfg.items.bank_capacity,
            names=", ".join(_item_name(obs, i) for i in obs.bank.queue) or EMPTY, next_item=next_item,
        ),
        dam_line,
        TACTICAL_WATER.format(base=obs.water.base_level, waves=waves),
        TACTICAL_AIRBORNE.format(flying=flying or EMPTY, floating=floating or EMPTY),
    ]


def _bag(obs: Observation, bag) -> str:
    d = obs.config.donkey
    return TACTICAL_BAG.format(
        names=", ".join(_item_name(obs, i) for i in bag.items) or TACTICAL_BAG_EMPTY,
        mass=bag.mass, max_kg=d.bag_max_kg_per_side, volume=bag.volume, max_volume=d.bag_max_volume_per_side,
    )


def _item_name(obs: Observation, item_id: int) -> str:
    kind = obs.items[item_id].kind
    return ITEM_NAMES.get(kind, kind)


def _event_lines(events: Iterable[Event]) -> list[str]:
    lines = [f"  {e.type} {_event_fields(e)}".rstrip() for e in events]
    return [TACTICAL_EVENTS, *lines] if lines else []


def _event_fields(event: Event) -> str:
    fields = [f for f in dataclasses.fields(event) if f.name not in ("t", "seq")]
    return " ".join(f"{f.name}={_plain(getattr(event, f.name))}" for f in fields)


def _plain(value) -> str:
    return value.value if isinstance(value, Enum) else str(value)


# --- the play loop ---------------------------------------------------------------------------------------------

def play(config: Config, seed: int, read: Callable[[str], str], write: Callable[[str], None]) -> GameState:
    """CONTROLS.md §5.1: one line per role per tick until game over, :q or end of input. Returns the last state."""
    state, rngs = new_game(config, seed)
    keys = donkey_keys(config), shrek_keys(config)
    events: tuple[Event, ...] = ()
    waiting = 0
    while state.game_over is None:
        if waiting > 0:
            waiting -= 1
            actions = Actions()
        else:
            write(render(observe(state, Role.DONKEY), events))  # V0: both roles see the same, one screen
            try:
                actions, waiting = _ask(read, write, keys)
            except Quit:
                write(TACTICAL_QUIT)
                return state
        state, rngs, events = step(state, actions, rngs)
        if waiting > 0:
            write("\n".join([f"t = {state.t}", *_event_lines(events)]))
    write(render(observe(state, Role.DONKEY), events))
    write(TACTICAL_RESULT.format(reason=GAME_OVER_REASONS[state.game_over.value], score=state.score))
    return state


def _ask(read, write, keys) -> tuple[Actions, int]:
    """(this tick's actions, extra ticks to wait). Bad lines are reported and asked again."""
    donkey_keys_, shrek_keys_ = keys
    while True:
        line = _read(read, TACTICAL_DONKEY_PROMPT, write)
        if (m := re.fullmatch(r":(\d+)", line.strip())) and int(m[1]) > 0:
            return Actions(), int(m[1]) - 1
        try:
            donkey = parse_donkey(line, donkey_keys_)
            break
        except InputError as error:
            write(str(error))
    while True:
        line = _read(read, TACTICAL_SHREK_PROMPT, write)
        try:
            return Actions(donkey=donkey, shrek=parse_shrek(line, shrek_keys_)), 0
        except InputError as error:
            write(str(error))


def _read(read, prompt: str, write) -> str:
    """A line that is not a command: ? prints the help and asks again, :q and end of input quit."""
    while True:
        try:
            line = read(prompt)
        except EOFError:
            raise Quit from None
        if line.strip() == ":q":
            raise Quit
        if line.strip() == "?":
            write(TACTICAL_HELP)
            continue
        return line
