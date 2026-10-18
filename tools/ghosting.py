"""Ghosting test core (CONTROLS.md §6): key combinations and their evaluation.

Pure logic, no pygame. The window lives in tools/ghosting_test.py.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "default.yaml"

LAYOUTS = {"default": "shrek_default", "alt": "shrek_alt"}

HOLD_MS = 3000  # CONTROLS.md §6: hold each combination for at least 3 s


@dataclass(frozen=True)
class Combo:
    id: str
    reason: str
    donkey: tuple[str, ...]  # action names in keymaps.donkey
    shrek: tuple[str, ...]   # action names in keymaps.shrek_*


# CONTROLS.md §6, in table order.
COMBOS = (
    Combo("W+UP+THROW", "Eşek ilerlerken Shrek nişanlayıp atıyor", ("MOVE_N",), ("AIM_UP", "THROW")),
    Combo("D+RIGHT+DAM", "Eşek kaçarken Shrek yürümeye çalışıyor / baraj tutuyor", ("MOVE_E",), ("MOVE_E", "DAM")),
    Combo("Q+DOWN+ROCK", "Duruş + kaya", ("STANCE_LEFT",), ("AIM_DOWN", "ROCK")),
    Combo("W+D+LEFT+UP", "Dört yön birden", ("MOVE_N", "MOVE_E"), ("MOVE_W", "AIM_UP")),
    Combo("E+DAM+UP", "Baraj tutarken nişan + duruş", ("STANCE_RIGHT",), ("DAM", "AIM_UP")),
    Combo("A+S+THROW+ROCK", "En kötü durum", ("MOVE_W", "MOVE_S"), ("THROW", "ROCK")),
)


def load_keymaps(path: Path = DEFAULT_CONFIG) -> dict[str, dict[str, int]]:
    """Read controls.keymaps from the YAML config.

    Temporary: reads the raw YAML. Step 2 replaces this with the validated engine.config loader.
    """
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["controls"]["keymaps"]


def combo_scancodes(combo: Combo, keymaps: dict[str, dict[str, int]], layout: str) -> frozenset[int]:
    """Scancodes that must all be held for `combo` under the given Shrek layout ("default" | "alt")."""
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout {layout!r}; expected one of {sorted(LAYOUTS)}")
    shrek = keymaps[LAYOUTS[layout]]
    return frozenset(keymaps["donkey"][a] for a in combo.donkey) | frozenset(shrek[a] for a in combo.shrek)


def evaluate(pressed: Iterable[int], required: frozenset[int]) -> tuple[bool, frozenset[int]]:
    """Were all required keys detected?

    Returns (ok, missing): `missing` is the required scancodes not in `pressed`;
    `ok` is True when nothing is missing. Extra pressed keys do not matter.
    """
    missing = required - frozenset(pressed)
    return not missing, missing


class HoldTracker:
    """Has every required key been detected without a break for `hold_ms`?

    Time comes in as an argument, so tests need no clock. A single tick with a key
    missing restarts the timer.
    """

    def __init__(self, hold_ms: int = HOLD_MS):
        self.hold_ms = hold_ms
        self._since: int | None = None  # when the current unbroken hold began

    def update(self, ok: bool, now_ms: int) -> bool:
        if not ok:
            self._since = None
            return False
        if self._since is None:
            self._since = now_ms
        return now_ms - self._since >= self.hold_ms

    def progress(self, now_ms: int) -> float:
        """Fraction of `hold_ms` held so far, in [0, 1]."""
        if self._since is None:
            return 0.0
        return min(1.0, (now_ms - self._since) / self.hold_ms)


@dataclass(frozen=True)
class Result:
    combo_id: str
    ok: bool
    missing: frozenset[int]  # scancodes not detected when the combo was marked failed


def results_table(layout: str, results: Iterable[Result]) -> str:
    """Markdown table of one run, to paste into CONTROLS.md §6."""
    lines = [f"| Kombinasyon | {layout} | Eksik scancode |", "|---|---|---|"]
    for r in results:
        mark = "☑" if r.ok else "✗"
        missing = ", ".join(str(code) for code in sorted(r.missing))
        lines.append(f"| {r.combo_id} | {mark} | {missing} |")
    return "\n".join(lines)
