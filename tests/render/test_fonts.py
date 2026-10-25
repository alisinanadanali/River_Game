"""VISUALS §7: the committed Noto fonts, their documented hashes, the Turkish glyphs and every window string.

Glyph presence is asked from pygame.freetype (None for a missing glyph): pygame.font draws a box instead and
does not say so. SDL's dummy driver: no window opens.
"""

import hashlib
import os
import re
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pygame.freetype  # noqa: E402
import pytest  # noqa: E402

from engine.config import load_config  # noqa: E402
from render import strings_tr  # noqa: E402
from render.fonts import font_path, load_font  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "assets" / "fonts"
CFG = load_config()
SIZE_PX = 24
TURKISH_PAIRS = ("ğg", "ĞG", "şs", "ŞS", "ıi", "İI", "çc", "ÇC", "öo", "ÖO", "üu", "ÜU")  # letter, its look-alike
TERMINAL_PREFIX = "TACTICAL_"  # printed to the terminal, never drawn with the font (VISUALS §7)


@pytest.fixture(scope="module", autouse=True)
def fonts_ready():
    pygame.font.init()
    pygame.freetype.init()
    yield
    pygame.freetype.quit()
    pygame.font.quit()


def font_table() -> dict[str, tuple[str, str]]:
    """VISUALS §7: file → (role, SHA-256)."""
    text = (ROOT / "docs" / "VISUALS.md").read_text(encoding="utf-8")
    return {m[1]: (m[2], m[3]) for m in re.finditer(r"^\s*\| `([^`]+)` \| (\w+) \| `([0-9a-f]{64})` \|", text, re.M)}


def missing_glyphs(text: str, mono: bool = False) -> set[str]:
    font = pygame.freetype.Font(font_path(CFG, mono), SIZE_PX)
    return {c for c, metrics in zip(text, font.get_metrics(text)) if metrics is None and not c.isspace()}


def window_strings() -> dict[str, str]:
    """name → text of every string the windows draw: strings_tr's constants, dicts and tuples of strings."""
    found = {}

    def collect(name, value):
        if isinstance(value, str):
            found[name] = value
        elif isinstance(value, dict):
            for key, item in value.items():
                collect(f"{name}[{key!r}]", item)
        elif isinstance(value, tuple | list):
            for i, item in enumerate(value):
                collect(f"{name}[{i}]", item)

    for name, value in vars(strings_tr).items():
        if name.isupper() and not name.startswith(TERMINAL_PREFIX):
            collect(name, value)
    return found


# --- the files -------------------------------------------------------------------------------------------------

def test_doc_lists_the_two_fonts_and_the_licence():
    assert {role for role, _ in font_table().values()} == {"arayüz", "sayısal", "lisans"}


@pytest.mark.parametrize("name", sorted(font_table()))
def test_committed_file_has_the_documented_hash(name):
    data = (FONT_DIR / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == font_table()[name][1]


def test_licence_is_the_sil_ofl_1_1():
    assert "SIL Open Font License, Version 1.1" in (FONT_DIR / "OFL.txt").read_text(encoding="utf-8")


def test_config_points_at_the_documented_fonts():
    role_of = {name: role for name, (role, _) in font_table().items()}
    assert role_of[font_path(CFG).name] == "arayüz" and role_of[font_path(CFG, mono=True).name] == "sayısal"
    assert font_path(CFG).parent == FONT_DIR and font_path(CFG, mono=True).parent == FONT_DIR


# --- the glyphs ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("mono", [False, True], ids=["sans", "mono"])
def test_every_turkish_letter_has_a_glyph(mono):
    assert missing_glyphs("".join(TURKISH_PAIRS), mono) == set()


def test_the_check_sees_a_missing_glyph():
    assert missing_glyphs("a→b") == {"→"}  # Noto Sans has no arrows (VISUALS §7)


@pytest.mark.parametrize("mono", [False, True], ids=["sans", "mono"])
@pytest.mark.parametrize("pair", TURKISH_PAIRS)
def test_turkish_letter_draws_unlike_its_look_alike(pair, mono):
    font = load_font(CFG, SIZE_PX, mono)
    letter, look_alike = (pygame.image.tobytes(font.render(c, True, (255, 255, 255)), "RGBA") for c in pair)
    assert letter != look_alike


def test_every_window_string_has_its_glyphs_in_noto_sans():
    strings = window_strings()
    for prefix in ("PREVIEW_HINT[", "ROLE_NAMES[", "GHOSTING_"):                 # the collector finds them
        assert any(name.startswith(prefix) for name in strings), prefix
    missing = {name: chars for name, text in strings.items() if (chars := missing_glyphs(text))}
    assert missing == {}


# --- loading ---------------------------------------------------------------------------------------------------

def test_size_is_the_one_asked_for():
    assert load_font(CFG, 2 * SIZE_PX).get_height() > load_font(CFG, SIZE_PX).get_height()


def test_mono_is_monospaced_and_sans_is_not():
    mono, sans = load_font(CFG, SIZE_PX, mono=True), load_font(CFG, SIZE_PX)
    assert mono.size("i")[0] == mono.size("W")[0]
    assert sans.size("i")[0] < sans.size("W")[0]


def test_a_missing_font_is_an_error_naming_the_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="NotoSans-Regular.ttf"):
        load_font(CFG, SIZE_PX, root=tmp_path)
