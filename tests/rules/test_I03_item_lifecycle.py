"""I-03: every item is in exactly one state each tick, moving only along the arrows of the ENTITIES.md state
machine; DELIVERED and LOST are absorbing. The diagram is read from the document itself, so code and document
cannot drift apart (the same idea as the TICK.md check in tests/engine/test_step.py).
"""

import re
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.items import ItemStatus

from tests.support import config_with, run

DOC = (Path(__file__).resolve().parents[2] / "docs" / "ENTITIES.md").read_text(encoding="utf-8")
CFG = config_with({"items": {"arrival_rate_per_tick": 0.5}})
TICKS = CFG.time.game_length_ticks


def documented_transitions() -> set[tuple[str, str]]:
    """Arrows 'A --> B' of the item life-cycle diagram; [*] is the start (before arrival) and the end."""
    block = DOC.split("### Yük yaşam döngüsü", 1)[1].split("```", 2)[1]
    return set(re.findall(r"^\s*(\[\*\]|\w+) --> (\[\*\]|\w+)", block, flags=re.MULTILINE))


def test_the_diagram_is_found_and_names_every_status():
    edges = documented_transitions()
    names = {name for edge in edges for name in edge} - {"[*]"}
    assert names == {s.value for s in ItemStatus}
    assert {("DELIVERED", "[*]"), ("LOST", "[*]")} <= edges
    assert not any(a in ("DELIVERED", "LOST") and b != "[*]" for a, b in edges)  # absorbing


actions = st.builds(
    Actions,
    donkey=st.sampled_from(DonkeyAction),
    shrek=st.builds(ShrekAction, move=st.sampled_from(ShrekMove), aim=st.sampled_from(Aim), ability=st.sampled_from(Ability)),
)


@given(seed=st.integers(0, 2**32 - 1), game=st.lists(actions, min_size=TICKS, max_size=TICKS))
def test_every_observed_change_is_a_documented_arrow(seed, game):
    edges = documented_transitions()
    previous: dict[int, str] = {}
    for state in run(CFG, seed, game).states:
        for item in state.items:
            before = previous.get(item.id, "[*]")
            if item.status.value != before:
                assert (before, item.status.value) in edges, f"item {item.id}: {before} -> {item.status.value}"
            previous[item.id] = item.status.value
