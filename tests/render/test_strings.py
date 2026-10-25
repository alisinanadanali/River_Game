"""VISUALS §7 / ADR-007: every string constant with a Turkish letter lives in render/strings_tr.py, and every
fractional number is written with a decimal comma.

Static, like the import tests: each file is read with `ast`, nothing is imported. Docstrings do not count (they
are documentation, English by the coding rules); f-string pieces do. A Turkish text without a Turkish letter
("Oyun bitti") slips through: that is the test's documented limit.
"""

import ast
import re
from pathlib import Path

import pytest

from render import strings_tr
from render.strings_tr import decimal, tr

ROOT = Path(__file__).resolve().parents[2]
VISUALS = ROOT / "docs" / "VISUALS.md"
SCANNED = ("engine", "render", "controllers", "game", "envs", "logs", "tools")  # packages; main.py as well
STRINGS = "render/strings_tr.py"
EXEMPT = ("tools/bench.py", "tools/design_calcs.py")  # developer reports, VISUALS §7
TURKISH = frozenset("çğıİöşüÇĞÖŞÜ")
DECIMAL_EXEMPT = ("tools/design_calcs.py",)  # matches MODEL.md's quotes, VISUALS §7
FRACTION_SPEC = re.compile(r"[fFgGeE%]$")      # a format spec that can print a decimal point
FIELD_SPEC = re.compile(r"\{[^{}:]*:([^{}]*)\}")


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


# --- the decimal comma (VISUALS §7) ----------------------------------------------------------------------------

@pytest.mark.parametrize(("template", "values", "expected"), [
    ("{x:.1f} sn", {"x": 0.6}, "0,6 sn"),
    ("{x:g}", {"x": 0.25}, "0,25"),
    ("{x:+.2f}", {"x": -0.125}, "-0,12"),
    ("%{x:.1f}", {"x": 1.5}, "%1,5"),
    ("{x:>6.1f}|", {"x": 7.25}, "   7,2|"),
    ("{n} / {m:g}", {"n": 3, "m": 150}, "3 / 150"),
    ("{s}. {x:.0f}.", {"s": "a.b", "x": 2.0}, "a.b. 2."),
])
def test_tr_writes_fractions_with_a_comma_and_leaves_the_rest(template, values, expected):
    assert tr(template, **values) == expected


@pytest.mark.parametrize(("x", "digits", "expected"), [(1.5, 1, "1,5"), (-3.14159, 2, "-3,14"), (2, 0, "2")])
def test_decimal_writes_one_number(x, digits, expected):
    assert decimal(x, digits) == expected


def fraction_templates() -> frozenset[str]:
    """Names of the strings module's templates with a fractional field."""
    return frozenset(
        name for name, value in vars(strings_tr).items()
        if isinstance(value, str) and any(FRACTION_SPEC.search(spec) for spec in FIELD_SPEC.findall(value))
    )


def dot_decimals(source: str, templates: frozenset[str]) -> list[tuple[int, str]]:
    """(line, what) of each f-string field with a fractional spec and each `.format(` on a fractional template."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FormattedValue) and isinstance(node.format_spec, ast.JoinedStr):
            spec = "".join(v.value for v in node.format_spec.values if isinstance(v, ast.Constant))
            if FRACTION_SPEC.search(spec):
                found.append((node.lineno, f"f-string :{spec}"))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"
                and isinstance(node.func.value, ast.Name) and node.func.value.id in templates):
            found.append((node.lineno, f"{node.func.value.id}.format"))
    return found


def test_the_decimal_scanner_finds_fstrings_and_template_formats():
    source = 'a = f"{x:.1f} {y:g} {z:5.1%} {n} {n:>3} {s!r}"\nb = T.format(x=1)\nc = U.format(x=1)\n'
    assert sorted(what for _, what in dot_decimals(source, frozenset({"T"}))) == sorted([
        "f-string :.1f", "f-string :g", "f-string :5.1%", "T.format"])


def test_the_strings_module_has_fractional_templates():
    assert {"TACTICAL_NEXT_SIGMA", "PREVIEW_BENCH"} <= fraction_templates()


def test_doc_names_the_decimal_exemption():
    doc = section_7()
    assert all(f"`{path}`" in doc for path in DECIMAL_EXEMPT) and "`strings_tr.tr(" in doc


@pytest.mark.parametrize("path", [p for p in scanned_files() if p.relative_to(ROOT).as_posix() not in DECIMAL_EXEMPT]
                         + [ROOT / path for path in EXEMPT if path not in DECIMAL_EXEMPT],
                         ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_dot_decimal_outside_tr(path):
    found = dot_decimals(path.read_text(encoding="utf-8"), fraction_templates())
    assert not found, "use strings_tr.tr / decimal: " + "; ".join(f"line {line}: {what}" for line, what in found)
