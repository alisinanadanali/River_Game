"""ROADMAP Phase 0 acceptance: every rule id in MODEL.md has a tests/rules/test_<ID>_*.py file, and every such
file names a rule that exists. The rule list is read from MODEL.md itself ("**W-05 …**" headings).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = (ROOT / "docs" / "MODEL.md").read_text(encoding="utf-8")
RULE_FILES = sorted(p.name for p in (ROOT / "tests" / "rules").glob("test_*.py"))


def model_rule_ids() -> list[str]:
    return re.findall(r"^\*\*([MWDSIR]-\d\d) ", MODEL, flags=re.MULTILINE)


def test_model_lists_the_known_rule_families():
    ids = model_rule_ids()
    assert len(ids) == len(set(ids)) == 37  # M 5 + W 7 + D 10 + S 8 + I 5 + R 2; a new rule updates this count
    assert {i[0] for i in ids} == set("MWDSIR")


def test_every_rule_has_a_test_file():
    missing = [i for i in model_rule_ids() if not any(n.startswith(f"test_{i.replace('-', '')}_") for n in RULE_FILES)]
    assert missing == []


def test_every_rule_test_file_names_a_rule():
    ids = {i.replace("-", "") for i in model_rule_ids()}
    strays = [n for n in RULE_FILES if re.match(r"test_([A-Z]\d\d)_", n) is None or re.match(r"test_([A-Z]\d\d)_", n)[1] not in ids]
    assert strays == []
