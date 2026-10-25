"""CONTROLS.md §4: the real-time input buffer. Pure: key events arrive as SDL scancodes, no pygame (ADR-005).

A tick window collects presses; at the tick boundary each role's action is built from the window's presses and
the keys still held, and the next window starts with the held keys only.
"""

from dataclasses import dataclass

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import ControlsConfig

SHREK_COMPONENTS = {                 # keymaps.shrek_* action → (ShrekAction field, value); NONE has none
    "MOVE_W": ("move", ShrekMove.W),
    "MOVE_E": ("move", ShrekMove.E),
    "AIM_UP": ("aim", Aim.UP),
    "AIM_DOWN": ("aim", Aim.DOWN),
    "THROW": ("ability", Ability.THROW),
    "ROCK": ("ability", Ability.ROCK),
    "DAM": ("ability", Ability.DAM),
}
DONKEY_REPEATS = frozenset({DonkeyAction.MOVE_N, DonkeyAction.MOVE_S, DonkeyAction.MOVE_E, DonkeyAction.MOVE_W})
SHREK_REPEATS = frozenset({"move", "aim"})  # §4.1: walking and sweeping the aim by holding


@dataclass(frozen=True)
class KeyDown:
    scancode: int


@dataclass(frozen=True)
class KeyUp:
    scancode: int


@dataclass(frozen=True)
class FocusLost:
    pass


KeyEvent = KeyDown | KeyUp | FocusLost


@dataclass(frozen=True)
class KeyBuffer:
    held: tuple[int, ...] = ()       # keys down now, in the order they were pressed
    pressed: tuple[int, ...] = ()    # presses in this tick window, in order (§4.1: a press is up → down)


def feed(buffer: KeyBuffer, event: KeyEvent) -> KeyBuffer:
    """§4.1: one key event into the window. A down of a held key is no press; focus lost forgets the held keys."""
    if isinstance(event, FocusLost):
        return KeyBuffer(held=(), pressed=buffer.pressed)
    if isinstance(event, KeyUp):
        return KeyBuffer(held=tuple(c for c in buffer.held if c != event.scancode), pressed=buffer.pressed)
    if event.scancode in buffer.held:
        return buffer
    return KeyBuffer(held=(*buffer.held, event.scancode), pressed=(*buffer.pressed, event.scancode))


def donkey_action(buffer: KeyBuffer, keys: dict[str, int]) -> DonkeyAction:
    """§4: the window's last donkey press, else the last held move key (hold repeat), else NOOP."""
    actions = {code: DonkeyAction(name) for name, code in keys.items()}
    repeats = {code: action for code, action in actions.items() if action in DONKEY_REPEATS}
    return _last(buffer.pressed, actions) or _last(buffer.held, repeats) or DonkeyAction.NOOP


def shrek_action(buffer: KeyBuffer, keys: dict[str, int]) -> ShrekAction:
    """§4: per component the last press, else for move/aim the last held key; DAM held or pressed wins."""
    chosen = {}
    for component in ("move", "aim", "ability"):
        values = {keys[name]: value for name, (field, value) in SHREK_COMPONENTS.items() if field == component}
        held = buffer.held if component in SHREK_REPEATS else ()
        if (value := _last(buffer.pressed, values) or _last(held, values)) is not None:
            chosen[component] = value
    if keys["DAM"] in buffer.held or keys["DAM"] in buffer.pressed:
        chosen["ability"] = Ability.DAM
    return ShrekAction(**chosen)


def tick_actions(buffer: KeyBuffer, controls: ControlsConfig) -> tuple[Actions, KeyBuffer]:
    """The tick boundary: both roles' actions, and the next window (the held keys, no presses)."""
    keymaps = controls.keymaps
    shrek_keys = keymaps.shrek_alt if controls.shrek_keymap == "alt" else keymaps.shrek_default
    actions = Actions(
        donkey=donkey_action(buffer, keymaps.donkey.model_dump()),
        shrek=shrek_action(buffer, shrek_keys.model_dump()),
    )
    return actions, KeyBuffer(held=buffer.held)


def _last(codes: tuple[int, ...], values: dict):
    """The value of the latest code in `codes` that has one, else None."""
    return next((values[code] for code in reversed(codes) if code in values), None)
