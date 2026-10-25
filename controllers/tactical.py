"""CONTROLS.md §5.2: tactical mode in the window. Each tick waits until both roles confirm an action.

Pure, like the real-time buffer: key events carry scancodes; only presses count. The session steps the engine
when tactical_actions() returns the tick's actions, then starts the next tick from an empty Tactical().
"""

from dataclasses import dataclass, replace

from controllers.keyboard import SHREK_COMPONENTS, KeyDown, KeyEvent, shrek_keymap
from engine.actions import Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import ControlsConfig


@dataclass(frozen=True)
class Tactical:
    donkey: DonkeyAction | None = None   # confirmed this tick, or None
    shrek: ShrekAction | None = None     # confirmed this tick, or None
    move: ShrekMove = ShrekMove.NONE     # Shrek's selection until confirmed (shown on screen)
    aim: Aim = Aim.NONE


def tactical_feed(tactical: Tactical, event: KeyEvent, controls: ControlsConfig) -> Tactical:
    """§5.2: a press selects or confirms; a confirmed role's later presses are ignored."""
    if not isinstance(event, KeyDown):
        return tactical
    code = event.scancode
    donkey = {c: DonkeyAction(name) for name, c in controls.keymaps.donkey.model_dump().items()}
    if code in donkey:
        return tactical if tactical.donkey is not None else replace(tactical, donkey=donkey[code])
    shrek = {c: SHREK_COMPONENTS.get(name) for name, c in shrek_keymap(controls).items()}  # wait key → None
    if code not in shrek or tactical.shrek is not None:
        return tactical
    if shrek[code] is None:
        return replace(tactical, shrek=ShrekAction(move=tactical.move, aim=tactical.aim))
    component, value = shrek[code]
    if component == "ability":
        return replace(tactical, shrek=ShrekAction(move=tactical.move, aim=tactical.aim, ability=value))
    none = ShrekMove.NONE if component == "move" else Aim.NONE
    return replace(tactical, **{component: none if getattr(tactical, component) is value else value})


def tactical_actions(tactical: Tactical) -> Actions | None:
    """The tick's actions once both roles have confirmed, else None."""
    if tactical.donkey is None or tactical.shrek is None:
        return None
    return Actions(donkey=tactical.donkey, shrek=tactical.shrek)
