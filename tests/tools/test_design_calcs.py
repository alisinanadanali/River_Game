"""tools/design_calcs.py (ROADMAP Phase 0): MODEL.md Appendix A re-checked with the engine.

The checks run once at a tenth of the appendix's sample sizes (the CLI's --quick); every one must agree within
its tolerance. Each check's number must also be printed on the MODEL.md line it names, inside its own section,
so the tool and the document cannot drift apart.
"""

import re
from pathlib import Path

import numpy as np
import pytest

from tools import design_calcs
from tools.design_calcs import (
    SECTIONS,
    Check,
    a1,
    a3,
    binomial_tol,
    main,
    rock_lifetime,
    rounding,
    run_checks,
    stone_path_steps,
    with_appendix_error,
)

from tests.support import config_with

ROOT = Path(__file__).resolve().parents[2]
MODEL = (ROOT / "docs" / "MODEL.md").read_text(encoding="utf-8")
QUICK = 0.1


def appendix_section(section: str) -> str:
    body = MODEL.split("## Ek A", 1)[1]
    return body.split(f"### {section} ", 1)[1].split("\n### ", 1)[0]


@pytest.fixture(scope="module")
def checks():
    return run_checks(QUICK)


# --- the appendix agrees with the engine ---------------------------------------------------------------------

def test_every_check_agrees(checks):
    bad = [f"{c.section} {c.label}: {c.measured:.4f} vs {c.text} ± {c.tolerance:.4f}" for c in checks if not c.ok]
    assert bad == []


def test_every_section_is_checked(checks):
    sections = re.findall(r"^### (A\.\d) ", MODEL, flags=re.MULTILINE)
    assert sections == list(SECTIONS) == sorted({c.section for c in checks})


def test_every_number_is_printed_where_the_check_says(checks):
    missing = []
    for c in checks:
        lines = [line for line in appendix_section(c.section).splitlines() if c.line in line]
        if len(lines) != 1 or c.text not in lines[0]:
            missing.append(f"{c.section} {c.label}: {c.text!r} on the line with {c.line!r} ({len(lines)} lines)")
    assert missing == []


def test_table_rows_are_checked_cell_by_cell(checks):
    # Guards the test above against a check list that quietly lost rows: A.1 has 6 + 4·5 + 6, A.3 15 + 5 cells.
    count = {s: sum(c.section == s for c in checks) for s in SECTIONS}
    assert count["A.1"] == 32 and count["A.3"] == 20 and count["A.4"] == 14


# --- tolerances --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("text", "half"), [("0,193", 0.0005), ("0,18", 0.005), ("%21", 0.005), ("9", 0.5),
                                            ("12,5", 0.05), ("%14", 0.005)])
def test_rounding_is_half_the_last_printed_digit(text, half):
    assert rounding(text) == pytest.approx(half)


def test_a_printed_zero_is_not_a_certain_zero():
    # 0,00 stands for anything below 0,005: the variance is taken there, not at 0 (which would allow no error).
    assert binomial_tol(0.0, 2000, 20_000, "0,00") > rounding("0,00") + 0.005
    assert binomial_tol(0.6, 2000, 20_000, "0,60") == pytest.approx(binomial_tol(0.4, 2000, 20_000, "0,40"))


def test_a_changed_engine_is_caught():
    # A smaller catch radius moves every A.3 cell: the tool must report it, not round it away.
    shrunk = a3(config_with({"shrek": {"catch_radius_cells": 0.7}}), 1.0)
    assert sum(not c.ok for c in shrunk) >= 15


def test_a_changed_engine_is_caught_by_the_monte_carlo_checks():
    # One more river row: every crossing is a step longer and paths are rarer. Found by a mutation that made the
    # tolerance ten times wider (SIGMAS = 40) and passed every test: a tolerance that wide would hide this.
    taller = a1(config_with({"map": {"rows": 10}}), QUICK)
    assert sum(not c.ok for c in taller) >= 6


def test_the_appendix_own_error_is_added():
    # Two equal samples: the difference of their means has √2 times the standard error of one.
    assert with_appendix_error(1.0, 120_000, 120_000) == pytest.approx(2**0.5)
    assert with_appendix_error(1.0, 12_000, 120_000) == pytest.approx(1.1**0.5)


# --- the pieces the tool adds to the engine ------------------------------------------------------------------

def test_stone_path_steps():
    s = np.array([[True, False], [True, False], [True, True]])
    assert stone_path_steps(s) == 4  # bank → 3 river rows → bank
    s = np.array([[True, False, False], [True, True, True], [False, False, True]])
    assert stone_path_steps(s) == 6  # (0,0) (1,0) (1,1) (1,2) (2,2), plus the two bank moves
    assert stone_path_steps(np.array([[True], [False], [True]])) is None


def test_rock_lifetime_matches_the_engine_tests():
    # tests/rules/test_S07_matches_appendix_A6.py measures the same through step: 25 ticks, 14 of them DRY.
    assert rock_lifetime(config_with({})) == (25, 14)


# --- the command line ----------------------------------------------------------------------------------------

def test_main_prints_the_report_and_exits_0(checks, monkeypatch, capsys):
    monkeypatch.setattr(design_calcs, "run_checks", lambda scale: checks)
    assert main(["--quick"]) == 0
    out = capsys.readouterr().out
    assert all(f"{s} {title}" in out for s, (title, _) in SECTIONS.items())
    assert f"{len(checks)}/{len(checks)} uyumlu" in out


def test_main_exits_1_on_a_disagreement(checks, monkeypatch, capsys):
    wrong = Check("A.5", "yük başına kg", 24.0, "24 kg", "Yük başına", 30.0, 0.5)
    monkeypatch.setattr(design_calcs, "run_checks", lambda scale: [*checks, wrong])
    assert main([]) == 1
    assert "✗" in capsys.readouterr().out
