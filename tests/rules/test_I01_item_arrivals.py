"""I-01: every tick N_t ~ Poisson(λ_items) items arrive; each kind is drawn by inverse CDF over the item types in
sorted name order (one rng_items call per tick: N_t, then N_t uniforms). Item ids are the arrival order.
"""

import copy
import math

import numpy as np
import pytest

from engine.actions import Actions
from engine.config import build_config, config_hash
from engine.events import ItemArrived
from engine.items import ItemStatus, draw_arrivals, kind_of
from engine.rng import make_rngs

from tests.support import DEFAULT, config_with, run

CFG = config_with({})
ITEMS = CFG.items


@pytest.mark.parametrize(
    ("u", "kind"),
    [(0.0, "apple_crate"), (0.4999, "apple_crate"), (0.5, "potato_sack"), (0.7999, "potato_sack"),
     (0.8, "watermelon"), (0.999999, "watermelon")],
)
def test_inverse_cdf_in_sorted_name_order(u, kind):
    # Sorted: apple_crate 0.5 | potato_sack 0.3 | watermelon 0.2 → cumulative 0.5, 0.8, 1.0.
    assert kind_of(u, ITEMS) == kind


def test_yaml_order_does_not_matter():
    # config_hash sorts keys, so two configs with the same hash must draw the same kinds.
    raw = copy.deepcopy(DEFAULT)
    raw["items"]["types"] = dict(reversed(list(raw["items"]["types"].items())))
    reordered = build_config(raw)
    assert list(reordered.items.types) != list(ITEMS.types)  # the YAML order really differs
    assert config_hash(reordered) == config_hash(CFG)
    us = np.linspace(0, 1, 101, endpoint=False)
    assert [kind_of(u, reordered.items) for u in us] == [kind_of(u, ITEMS) for u in us]


def test_rate_and_mix_match_the_config():
    # 40 000 ticks: N_t is Poisson(λ) and kinds follow the probabilities, each within 4 standard errors.
    rngs, counts, kinds = make_rngs(5), [], []
    for _ in range(40_000):
        us, rngs = draw_arrivals(rngs, ITEMS)
        counts.append(len(us))
        kinds += [kind_of(u, ITEMS) for u in us]
    lam, n = ITEMS.arrival_rate_per_tick, len(counts)
    assert abs(np.mean(counts) - lam) < 4 * math.sqrt(lam / n)
    for name, item_type in ITEMS.types.items():
        p = item_type.prob
        assert abs(kinds.count(name) / len(kinds) - p) < 4 * math.sqrt(p * (1 - p) / len(kinds))


def test_rate_zero_brings_nothing():
    # (How much rng_items draws must not depend on the actions: that is INV-03, tests/invariants.)
    trace = run(config_with({"items": {"arrival_rate_per_tick": 0.0}}), 3, [Actions()] * 100)
    assert trace.states[-1].items == () and not any(isinstance(e, ItemArrived) for e in trace.events)


def test_arrivals_in_a_game():
    trace = run(CFG, 3, [Actions()] * 60)
    arrived = [e for e in trace.events if isinstance(e, ItemArrived)]
    assert len(arrived) > 0
    assert [e.item_id for e in arrived] == list(range(len(arrived)))
    items = trace.states[-1].items
    assert [i.id for i in items] == list(range(len(items))) and len(items) == len(arrived)
    assert all(i.kind == e.kind for i, e in zip(items, arrived, strict=True))
    assert {i.status for i in items} <= {ItemStatus.ON_BANK, ItemStatus.LOST}


def test_appendix_a5_item_economy():
    # MODEL A.5: per item 24 kg, 1.7 volume, 2.6 points on average; ≈ 30 items per 300-tick game.
    types = ITEMS.types.values()
    assert sum(t.prob * t.mass_kg for t in types) == pytest.approx(24.0)
    assert sum(t.prob * t.volume for t in types) == pytest.approx(1.7)
    assert sum(t.prob * t.points for t in types) == pytest.approx(2.6)
    assert ITEMS.arrival_rate_per_tick * CFG.time.game_length_ticks == pytest.approx(30.0)
