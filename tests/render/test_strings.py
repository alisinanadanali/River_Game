"""VISUALS §7 / ADR-007: every string constant with a Turkish letter lives in render/strings_tr.py.

Static, like the import tests: each file is read with `ast`, nothing is imported. Docstrings do not count (they
are documentation, English by the coding rules); f-string pieces do. A Turkish text without a Turkish letter
("Oyun bitti") slips through: that is the test's documented limit.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VISUALS = ROOT / "docs" / "VISUALS.md"
SCANNED = ("engine", "render", "controllers", "game", "envs", "logs", "tools")  # packages; main.py as well
STRINGS = "render/strings_tr.py"
EXEMPT = ("tools/bench.py", "tools/design_calcs.py")  # developer reports, VISUALS §7
TURKISH = frozenset("çğıİöşüÇĞÖŞÜ")


def turkish_strings(source: str) -> list[tuple[int, str]]:
    """(line, text) of every string constant with a Turkish letter, docstrings left out."""
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and TURKISH & set(node.value)
    ]


def scanned_files() -> list[Path]:
    files = [path for package in SCANNED for path in (ROOT / package).rglob("*.py")]
    files += [ROOT / "main.py"] if (ROOT / "main.py").exists() else []
    skipped = {ROOT / STRINGS, *(ROOT / path for path in EXEMPT)}
    return sorted(path for path in files if path not in skipped)


def section_7() -> str:
    text = VISUALS.read_text(encoding="utf-8")
    return re.search(r"^## 7\..*?(?=^## )", text, re.M | re.S)[0]


# --- the scanner itself ----------------------------------------------------------------------------------------

def test_scanner_finds_plain_and_fstring_text_but_not_docstrings():
    source = '''
"""Modül: çalışır."""
X = "Eşek"
def f(n):
    """Fonksiyon: ğ."""
    return f"{n} tık", "plain", "ascii only"
class C:
    """Sınıf."""
    y = {"k": "sağ"}
'''
    assert sorted(text for _, text in turkish_strings(source)) == sorted(["Eşek", " tık", "sağ"])


def test_every_turkish_letter_is_caught():
    for letter in TURKISH:
        assert turkish_strings(f'X = "a{letter}b"') == [(1, f"a{letter}b")]


def test_scan_covers_the_packages_that_exist():
    scanned = {path.relative_to(ROOT).parts[0] for path in scanned_files()}
    assert {"engine", "render", "tools"} <= scanned
    assert ROOT / STRINGS not in scanned_files()


# --- the rule and its doc --------------------------------------------------------------------------------------

def test_doc_names_the_scanned_packages_the_strings_module_and_the_exemptions():
    doc = section_7()
    for name in (*SCANNED, "main.py", STRINGS, *EXEMPT):
        assert f"`{name}" in doc, name


def test_exempt_files_exist():
    for path in EXEMPT:
        assert (ROOT / path).is_file(), path


def test_the_strings_module_holds_turkish_text():
    assert turkish_strings((ROOT / STRINGS).read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", scanned_files(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_turkish_string_outside_the_strings_module(path):
    found = turkish_strings(path.read_text(encoding="utf-8"))
    assert not found, f"move to {STRINGS}: " + "; ".join(f"line {line}: {text!r}" for line, text in found)
