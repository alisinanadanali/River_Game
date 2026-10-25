"""Text tactical mode (CONTROLS.md §5.1): keys, line parsing, the ASCII map and the play loop.

Expected keys are written out by hand from the CONTROLS.md §5.1 table, not read from config: the doc is the
oracle. The play loop is checked against the engine itself: typing a game must give the state run() gives.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import load_config
from engine.donkey import Bag
from engine.events import ProjectileKind, Role, Side
from engine.evolve import evolve
from engine.items import Item, ItemStatus, Projectile
from engine.observe import observe
from engine.stones import TempStone
from render.strings_tr import TACTICAL_GAME_OVER as GAME_OVER
from render.strings_tr import TACTICAL_HELP as HELP
from render.strings_tr import SIDE_NAMES, TACTICAL_DAM_IDLE, TACTICAL_DAM_LOCKED, TACTICAL_READY, TACTICAL_READY_NEXT_TICK
from tools.tactical import (
    InputError,
    donkey_keys,
    parse_donkey,
    parse_shrek,
    play,
    render,
    scancode_char,
    shrek_keys,
)

from tests.support import config_with, run, scripted_actions, set_up, still

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config()

D = DonkeyAction
DONKEY = {"w": D.MOVE_N, "a": D.MOVE_W, "s": D.MOVE_S, "d": D.MOVE_E, "q": D.STANCE_LEFT, "e": D.STANCE_RIGHT, "x": D.NOOP}
SHREK = {
    "j": ("move", ShrekMove.W), "l": ("move", ShrekMove.E),
    "i": ("aim", Aim.UP), "k": ("aim", Aim.DOWN),
    "u": ("ability", Ability.THROW), "o": ("ability", Ability.ROCK), " ": ("ability", Ability.DAM),
    "m": None,
}


# --- keys --------------------------------------------------------------------------------------------------

def test_scancodes_to_characters():
    assert [scancode_char(c) for c in (4, 7, 26, 29, 44)] == ["a", "d", "w", "z", " "]
    with pytest.raises(ValueError, match="80"):
        scancode_char(80)  # an arrow key cannot be typed into a line


def test_key_tables_match_controls():
    assert donkey_keys(CFG) == DONKEY
    assert shrek_keys(CFG) == SHREK


def test_keys_follow_the_config():
    swapped = config_with({"controls": {"keymaps": {"donkey": {"MOVE_N": 27, "NOOP": 26}}}})  # W ↔ X
    assert donkey_keys(swapped)["x"] is D.MOVE_N and donkey_keys(swapped)["w"] is D.NOOP


def test_an_untypable_donkey_key_is_an_error():
    arrows = config_with({"controls": {"keymaps": {"donkey": {"MOVE_N": 82}, "shrek_default": {"AIM_UP": 26}}}})
    with pytest.raises(ValueError, match="82"):
        donkey_keys(arrows)


# --- parsing lines -------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("line", "action"), [*DONKEY.items(), ("", D.NOOP), ("W", D.MOVE_N), (" d ", D.MOVE_E)])
def test_donkey_lines(line, action):
    assert parse_donkey(line, donkey_keys(CFG)) is action


@pytest.mark.parametrize("line", ["ww", "z", "wd", "1"])
def test_bad_donkey_lines(line):
    with pytest.raises(InputError):
        parse_donkey(line, donkey_keys(CFG))


@pytest.mark.parametrize(
    ("line", "action"),
    [
        ("", ShrekAction()),
        ("m", ShrekAction()),
        ("li", ShrekAction(move=ShrekMove.E, aim=Aim.UP)),
        ("iu", ShrekAction(aim=Aim.UP, ability=Ability.THROW)),
        ("ui", ShrekAction(aim=Aim.UP, ability=Ability.THROW)),  # order does not matter
        (" ", ShrekAction(ability=Ability.DAM)),
        ("jk ", ShrekAction(move=ShrekMove.W, aim=Aim.DOWN, ability=Ability.DAM)),
        ("O", ShrekAction(ability=Ability.ROCK)),
        ("ı", ShrekAction(aim=Aim.UP)),   # Turkish Q: the I key types dotless ı
        ("I", ShrekAction(aim=Aim.UP)),
        ("İ", ShrekAction(aim=Aim.UP)),   # "İ".lower() is "i̇", two code points
    ],
)
def test_shrek_lines(line, action):
    assert parse_shrek(line, shrek_keys(CFG)) == action


@pytest.mark.parametrize("line", ["jl", "uo", "u ", "ik", "z", "mu", "ll"])
def test_bad_shrek_lines(line):
    # Two keys for one component, an unknown letter, or "wait" mixed with a key.
    with pytest.raises(InputError):
        parse_shrek(line, shrek_keys(CFG))


# --- the map -------------------------------------------------------------------------------------------------

SMALL = still({"map": {"rows": 3, "cols": 5}})
# Still water, L = 0: d = load/k − h with load/k = 200/50 = 4 cm, so h = 10 → d = −6 (KURU), 2 → 2 (BİLEK),
# −6 → 10 (DİZ), −20 → 24 (swept). Mossy (1, 1): k = 25, d = 8 − 10 = −2 (KURU).
HEIGHTS = {(0, 0): 10.0, (0, 1): 2.0, (0, 2): -6.0, (0, 3): -20.0, (0, 4): 10.0, (1, 1): 10.0}
ROWS = ["#####", ".m...", "....."]


def small_state():
    items = (
        Item(id=0, kind="apple_crate", status=ItemStatus.IN_FLIGHT, pos=(1.0, 4.0)),
        Item(id=1, kind="watermelon", status=ItemStatus.FLOATING, pos=(1.0, 2.5)),
    )
    projectile = Projectile(item_id=0, kind=ProjectileKind.THROW, target=(1, 4), landing=(1.3, 3.8), sigma=0.5,
                            ticks_left=1, thrown_at=0)
    state, _ = set_up(
        SMALL, ROWS, HEIGHTS, items=items, projectiles=(projectile,), donkey={"row": 0, "col": 4},
        stones={"temp": (TempStone(id=0, row=2, col=3, h=20.0, spawned_at=0),), "next_temp_id": 1},
    )
    return state


def map_cells(text: str) -> dict[int, list[str]]:
    """{row label: [4-character cell, …]} from the map lines "  2 |~~  #K  …"."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"^ *(-?\d+) \|(.*)$", line)
        if m:
            out[int(m[1])] = [m[2][i : i + 4] for i in range(0, len(m[2].rstrip()) + 1, 4)][: SMALL.map.cols]
    return out


def test_rows_run_from_the_north_bank_down_to_the_south_bank():
    assert list(map_cells(render(observe(small_state(), Role.DONKEY), ()))) == [3, 2, 1, 0, -1]


def test_cells():
    cells = map_cells(render(observe(small_state(), Role.DONKEY), ()))
    glyph = {(r, c): cells[r][c][1:3] for r in cells for c in range(SMALL.map.cols)}
    assert [glyph[(0, c)] for c in range(4)] == ["#K", "#B", "#D", "#!"]   # depth tier for the current load
    assert glyph[(0, 4)] == "Eş"                                            # the donkey hides its stone
    assert (glyph[(1, 1)], glyph[(2, 3)], glyph[(2, 0)]) == ("mK", "oK", "~~")
    assert glyph[(1, 3)] == "**"                                            # x = 2.5 → column 3 (S-05 half up)
    assert (glyph[(-1, 2)], glyph[(-1, 0)], glyph[(3, 0)]) == ("Sh", "..", "..")
    assert cells[0][2] == "[#D]"                                            # Shrek aims at (0, 2)
    assert cells[1][4] == "(~~)"                                            # the projectile's target, not its landing


def test_the_load_changes_the_tiers():
    # VISUALS §3: the tier answers "if the donkey stepped here now". 50 kg more: the mossy stone (k = 25) sinks
    # 250/25 = 10 cm instead of 8, d = 10 − 10 = 0 → BİLEK (d₀ = 0 belongs to the deeper state, D-04).
    state = small_state()
    loaded = evolve(state, donkey=evolve(state.donkey, bag_left=Bag(items=(1,), mass=50.0, volume=3)))
    assert map_cells(render(observe(state, Role.DONKEY), ()))[1][1][1:3] == "mK"
    assert map_cells(render(observe(loaded, Role.DONKEY), ()))[1][1][1:3] == "mB"


def test_hidden_values_do_not_reach_the_screen():
    state = small_state()
    other = evolve(state, world=evolve(state.world, seed=99),
                   projectiles=(evolve(state.projectiles[0], landing=(0.0, 0.0)),))
    assert render(observe(other, Role.DONKEY), ()) == render(observe(state, Role.DONKEY), ())


@pytest.mark.parametrize("since, ready", [(0, False), (-1, True)])
def test_the_stance_says_whether_it_catches_yet(since, ready):
    # D-08: taken in tick 0 it catches from tick 1 on; at t = 0 it is ready only if taken earlier.
    state, _ = set_up(SMALL, ROWS, HEIGHTS, donkey={"stance": Side.LEFT, "stance_since": since})
    text = render(observe(state, Role.DONKEY), ())
    assert SIDE_NAMES[Side.LEFT] + (TACTICAL_READY if ready else TACTICAL_READY_NEXT_TICK) in text


@pytest.mark.parametrize("locked", [False, True])
def test_a_burst_dam_shows_its_lock(locked):
    state, _ = set_up(SMALL, ROWS, HEIGHTS, dam={"burst_lock": locked})
    text = render(observe(state, Role.DONKEY), ())
    assert TACTICAL_DAM_IDLE in text and (TACTICAL_DAM_LOCKED in text) is locked


def test_the_last_ticks_events_are_listed():
    state, rngs = set_up(SMALL, ROWS, HEIGHTS)
    trace = run(SMALL, 1, [Actions(donkey=D.MOVE_N)], start=(state, rngs))
    text = render(observe(trace.states[-1], Role.DONKEY), trace.events)
    assert all(e.type in text for e in trace.events) and len(trace.events) > 0


# --- the play loop ------------------------------------------------------------------------------------------

class Terminal:
    """Feeds typed lines to play() and keeps what it writes. Out of lines → EOF, like Ctrl+Z."""

    def __init__(self, lines):
        self.lines, self.out, self.prompts = list(lines), [], 0

    def read(self, prompt: str) -> str:
        self.prompts += 1
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)

    def write(self, text: str) -> None:
        self.out.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.out)


def typed(actions: list[Actions]) -> list[str]:
    """The two lines a player pair types for each tick, from the CONTROLS.md §5.1 table."""
    donkey = {a: k for k, a in DONKEY.items()}
    shrek = {v: k for k, v in SHREK.items() if v is not None}
    lines = []
    for a in actions:
        parts = [("move", a.shrek.move), ("aim", a.shrek.aim), ("ability", a.shrek.ability)]
        lines += [donkey[a.donkey], "".join(shrek[p] for p in parts if p[1].name != "NONE")]
    return lines


def test_a_whole_game_of_waiting_is_playable():
    # ROADMAP Phase 0: a full game (300 ticks) can be played in the text tactical mode.
    terminal = Terminal([""] * 1000)
    final = play(CFG, 42, terminal.read, terminal.write)
    assert final.game_over is not None and final.t == CFG.time.game_length_ticks
    assert final == run(CFG, 42, [Actions()] * CFG.time.game_length_ticks).states[-1]
    assert terminal.prompts == 2 * CFG.time.game_length_ticks
    assert GAME_OVER in terminal.text


def test_typing_a_game_gives_what_the_engine_gives():
    actions = scripted_actions(CFG.time.game_length_ticks)
    terminal = Terminal(typed(actions))
    expected = run(CFG, 7, actions).states[-1]
    assert play(CFG, 7, terminal.read, terminal.write) == expected


def test_a_bad_line_is_asked_again_and_the_tick_waits():
    # A stance, not a move: on this map (0, 2) is water, so a rejected MOVE_N would look just like a NOOP (found
    # by a mutation that turned bad donkey lines into NOOP instead of asking again).
    terminal = Terminal(["z", "q", "jl", "l"])
    final = play(SMALL, 1, terminal.read, terminal.write)
    assert final == run(SMALL, 1, [Actions(donkey=D.STANCE_LEFT, shrek=ShrekAction(move=ShrekMove.E))]).states[-1]
    assert final != run(SMALL, 1, [Actions(shrek=ShrekAction(move=ShrekMove.E))]).states[-1]
    assert terminal.text.count("!") >= 2  # one error line per bad line (InputError messages start with "!")


def test_wait_n_ticks():
    final = play(SMALL, 1, *_rw(Terminal([":3"])))
    assert final == run(SMALL, 1, [Actions()] * 3).states[-1]


def test_help_and_quit():
    terminal = Terminal(["?", "", ":q", "", ""])  # lines after :q: quitting is not just running out of input
    final = play(SMALL, 1, terminal.read, terminal.write)
    assert HELP in terminal.text
    assert final.t == 0  # :q on the Shrek line quits before the tick is played


def test_end_of_input_quits_cleanly():
    assert play(SMALL, 1, *_rw(Terminal([]))).t == 0


def _rw(terminal):
    return terminal.read, terminal.write


# --- the command line ---------------------------------------------------------------------------------------

def cli(*args, stdin=""):
    # A Turkish Windows console (code page 1254) has no δ or σ: the CLI must switch to UTF-8 itself. This machine
    # runs UTF-8 everywhere, which hid a mutation that removed the switch until the code page was forced here.
    env = {**os.environ, "PYTHONIOENCODING": "cp1254"}
    return subprocess.run([sys.executable, "-m", "tools.tactical_cli", *args], input=stdin.encode("utf-8"),
                          capture_output=True, cwd=ROOT, env=env, timeout=120)


def test_the_documented_command_plays_a_whole_game():
    done = cli("--seed", "42", "--profile", "percolation_edge", stdin="\n" * 1000)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert GAME_OVER in done.stdout.decode("utf-8")


def test_an_unknown_profile_is_a_clear_error():
    done = cli("--profile", "nope")
    assert done.returncode == 2
    assert "nope" in done.stderr.decode("utf-8")
