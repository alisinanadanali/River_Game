"""Text tactical mode core (CONTROLS.md §5.1): keys from the keymaps, line parsing, the ASCII map, the play loop.

Pure apart from the read/write callables play() is given; the terminal lives in tools/tactical_cli.py.
Everything shown comes from observe() (MODEL §1 O), never from the state itself.
"""

import dataclasses
import re
from collections.abc import Callable, Iterable
from enum import Enum

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import Config
from engine.donkey import balance, classify_depth, effective_height, load_kg, stance_ready, stone_under
from engine.events import DepthState, Event, ItemStatus, Role, Side
from engine.items import item_type, round_half_up
from engine.observe import Observation, observe
from engine.shrek import throw_sigma
from engine.state import GameState, new_game
from engine.step import step
from engine.stones import temp_at

HID_A, HID_Z, HID_SPACE = 4, 29, 44  # USB HID usage page 7 (= SDL scancodes): 4 … 29 are a … z, 44 the space bar
CELL = 4                             # characters per map cell: marker, two glyph characters, marker
SHREK_COMPONENTS = {                 # keymaps.shrek_alt action → (ShrekAction field, value)
    "MOVE_W": ("move", ShrekMove.W),
    "MOVE_E": ("move", ShrekMove.E),
    "AIM_UP": ("aim", Aim.UP),
    "AIM_DOWN": ("aim", Aim.DOWN),
    "THROW": ("ability", Ability.THROW),
    "ROCK": ("ability", Ability.ROCK),
    "DAM": ("ability", Ability.DAM),
}
TURKISH_I = str.maketrans({"ı": "i", "İ": "i", "I": "i"})  # Turkish Q: the I key types ı; "İ".lower() is "i̇"

# UI strings (Turkish, ADR-007). Move to the strings module once render/ exists.
DONKEY_PROMPT = "Eşek  > "
SHREK_PROMPT = "Shrek > "
GAME_OVER = "Oyun bitti"
QUIT = "Çıkıldı."
HELP = (
    "Eşek: w/a/s/d yürü, q/e duruş (sol/sağ), x ya da boş satır bekle.\n"
    "Shrek: j/l yürü, i/k nişan, u fırlat, o kaya, boşluk baraj; bileşen başına bir tuş (ör. 'li', 'iu'). "
    "m ya da boş satır bekle.\n"
    "Komutlar: ? yardım, :q çık, :N (eşek satırında) iki oyuncu N tick bekler."
)
BAD_KEY = "! '{key}' tanımlı bir tuş değil"
ONE_KEY = "! eşek tek tuşla oynar"
TWO_KEYS = "! aynı bileşene iki tuş: '{a}' ve '{b}'"
WAIT_ALONE = "! 'm' (bekle) tek başına yazılır"
TIERS = {DepthState.DRY: "K", DepthState.ANKLE: "B", DepthState.KNEE: "D", DepthState.SWEPT: "!"}
DEPTH_NAMES = {DepthState.DRY: "KURU", DepthState.ANKLE: "BİLEK", DepthState.KNEE: "DİZ", DepthState.SWEPT: "SÜRÜKLENDİ"}
SIDE_NAMES = {Side.LEFT: "sol", Side.RIGHT: "sağ", Side.NONE: "yok"}
ITEM_NAMES = {"apple_crate": "Elma kasası", "potato_sack": "Patates çuvalı", "watermelon": "Karpuz"}
REASONS = {"time": "süre doldu", "lives": "can kalmadı"}


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
        raise InputError(ONE_KEY)
    if text not in keys:
        raise InputError(BAD_KEY.format(key=text))
    return keys[text]


def parse_shrek(line: str, keys: dict[str, tuple[str, Enum] | None]) -> ShrekAction:
    """At most one key per component, in any order. Spaces are kept: the space bar is the dam key."""
    text = line.strip("\r\n").translate(TURKISH_I).lower()
    chosen: dict[str, tuple[str, Enum]] = {}
    for key in text:
        if key not in keys:
            raise InputError(BAD_KEY.format(key=key))
        if keys[key] is None:
            if len(text) > 1:
                raise InputError(WAIT_ALONE)
            continue
        component, value = keys[key]
        if component in chosen:
            raise InputError(TWO_KEYS.format(a=chosen[component][0], b=key))
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
    glyphs[(-1, obs.shrek.col)] = "Sh"
    glyphs[(obs.donkey.row, obs.donkey.col)] = "Eş"  # in front of Shrek when both stand in one bank cell
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
        stance += " (hazır)" if stance_ready(donkey, obs.t) else " (bir tick sonra hazır)"
    moving = "" if donkey.move_target is None else f"  ·  yavaş hareket → {donkey.move_target}, {donkey.move_remaining} tick"
    head = obs.bank.queue[0] if obs.bank.queue else None
    next_item = "kuyruk boş"
    if head is not None:
        mass = item_type(cfg.items, obs.items[head].kind).mass_kg
        next_item = f"sıradaki σ = {throw_sigma(shrek.aim_row, mass, cfg.shrek):.2f} hücre"
    if dam.active:
        dam_line = f"Baraj: sütun {dam.col}, Q = {dam.volume:.1f} / {cfg.dam.q_max_cm_cols:g} cm·sütun"
    else:
        dam_line = "Baraj: tutulmuyor" + ("  (patladı: DAM bırakılana kadar kilitli)" if dam.burst_lock else "")
    waves = ", ".join(f"x = {w.x:.1f} A = {w.amplitude:.1f} cm" for w in obs.water.waves) or "yok"
    flying = ", ".join(f"{_item_name(obs, p.item_id)} → {p.target}, {p.ticks_left} tick" for p in obs.projectiles)
    floating = ", ".join(
        f"{_item_name(obs, i.id)} ({i.pos[0]:.0f}, {i.pos[1]:.2f})" for i in obs.items if i.status is ItemStatus.FLOATING
    )
    return [
        "",
        f"t = {obs.t} / {cfg.time.game_length_ticks}   Skor: {obs.score}   Can: {donkey.lives}",
        f"Eşek: ({donkey.row}, {donkey.col})  {depth}  ·  duruş: {stance}{moving}",
        f"  sol heybe: {_bag(obs, donkey.bag_left)}   sağ heybe: {_bag(obs, donkey.bag_right)}"
        f"   denge δ = {balance(donkey, cfg):+.2f}",
        f"Shrek: sütun {shrek.col}, nişan satırı {shrek.aim_row}  ·  fırlat cd {shrek.throw_cooldown}"
        f"  ·  kaya cd {shrek.rock_cooldown}  ·  geçici taş {len(obs.stones.temp)}/{cfg.shrek.rock_max_active}",
        f"  kıyı kuyruğu {len(obs.bank.queue)}/{cfg.items.bank_capacity}: "
        f"{', '.join(_item_name(obs, i) for i in obs.bank.queue) or '—'}  ·  {next_item}",
        dam_line,
        f"Su: B = {obs.water.base_level:.1f} cm; dalgalar: {waves}",
        f"Uçan: {flying or '—'}   Yüzen: {floating or '—'}",
    ]


def _bag(obs: Observation, bag) -> str:
    names = ", ".join(_item_name(obs, i) for i in bag.items) or "boş"
    d = obs.config.donkey
    return f"{names} ({bag.mass:g}/{d.bag_max_kg_per_side:g} kg, {bag.volume}/{d.bag_max_volume_per_side} hacim)"


def _item_name(obs: Observation, item_id: int) -> str:
    kind = obs.items[item_id].kind
    return ITEM_NAMES.get(kind, kind)


def _event_lines(events: Iterable[Event]) -> list[str]:
    lines = [f"  {e.type} {_event_fields(e)}".rstrip() for e in events]
    return ["Olaylar:", *lines] if lines else []


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
                write(QUIT)
                return state
        state, rngs, events = step(state, actions, rngs)
        if waiting > 0:
            write("\n".join([f"t = {state.t}", *_event_lines(events)]))
    write(render(observe(state, Role.DONKEY), events))
    write(f"{GAME_OVER} ({REASONS[state.game_over.value]}). Skor: {state.score}")
    return state


def _ask(read, write, keys) -> tuple[Actions, int]:
    """(this tick's actions, extra ticks to wait). Bad lines are reported and asked again."""
    donkey_keys_, shrek_keys_ = keys
    while True:
        line = _read(read, DONKEY_PROMPT, write)
        if (m := re.fullmatch(r":(\d+)", line.strip())) and int(m[1]) > 0:
            return Actions(), int(m[1]) - 1
        try:
            donkey = parse_donkey(line, donkey_keys_)
            break
        except InputError as error:
            write(str(error))
    while True:
        line = _read(read, SHREK_PROMPT, write)
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
            write(HELP)
            continue
        return line
