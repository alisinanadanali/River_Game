"""R-01: five independent PCG64 streams from SeedSequence(seed).spawn(5); ADR-011: stream state is a value."""

import dataclasses

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.rng import STREAMS, draw, make_rngs

# K2 golden values: seed 42, computed with plain numpy 2.5.4 from the R-01 recipe (not from engine/rng.py).
# If these change after a numpy upgrade, every stored replay is invalid: bump engine_version, do not just edit.
GOLDEN_42 = {
    "world": ("random", 2, [0.9167441575549085, 0.9109866676343232]),
    "water": ("standard_normal", 2, [1.2544943667397455, 0.6062894401319061]),
    "items": ("random", 2, [0.07123920291270869, 0.7101597228953526]),
    "throw": ("standard_normal", 2, [-0.10042534847214493, 1.460115100190716]),
    "slip": ("random", 4, [0.017567502091441867, 0.991840578805897, 0.8324282691699447, 0.6860463136407406]),
}

seeds = st.integers(min_value=0, max_value=2**64 - 1)


def test_stream_order_matches_model_doc():
    assert STREAMS == ("world", "water", "items", "throw", "slip")


@pytest.mark.parametrize("stream", list(GOLDEN_42))
def test_golden_values_seed_42(stream):
    method, n, expected = GOLDEN_42[stream]
    values, _ = draw(make_rngs(42), stream, lambda g: getattr(g, method)(n))
    assert values.tolist() == expected          # exact: bit-level reproducibility, no tolerance


@settings(max_examples=50)
@given(seed=seeds)
def test_follows_the_r01_recipe(seed):
    plain = [np.random.Generator(np.random.PCG64(s)) for s in np.random.SeedSequence(seed).spawn(5)]
    rngs = make_rngs(seed)
    for i, stream in enumerate(STREAMS):
        values, rngs = draw(rngs, stream, lambda g: g.random(3))
        assert values.tolist() == plain[i].random(3).tolist()


def test_same_seed_same_value():
    assert make_rngs(7) == make_rngs(7)
    assert make_rngs(7) != make_rngs(8)


def test_streams_differ():
    rngs = make_rngs(42)
    firsts = {stream: draw(rngs, stream, lambda g: g.random())[0] for stream in STREAMS}
    assert len(set(firsts.values())) == 5


@settings(max_examples=25)
@given(seed=seeds, n=st.integers(min_value=0, max_value=1000))
def test_streams_are_independent(seed, n):
    # ADR-006: drawing from throw, however much, does not shift water's future.
    rngs = make_rngs(seed)
    _, after_throw = draw(rngs, "throw", lambda g: g.standard_normal(n))
    assert draw(after_throw, "water", lambda g: g.random(5))[0].tolist() == draw(rngs, "water", lambda g: g.random(5))[0].tolist()
    assert after_throw.water == rngs.water


# --- ADR-011: drawing is pure ------------------------------------------------------------------

def test_draw_does_not_change_its_input():
    rngs = make_rngs(42)
    before = dataclasses.replace(rngs)
    draw(rngs, "water", lambda g: g.random(10))
    assert rngs == before


def test_same_input_same_output():
    rngs = make_rngs(42)
    a, rngs_a = draw(rngs, "slip", lambda g: g.random(4))
    b, rngs_b = draw(rngs, "slip", lambda g: g.random(4))
    assert a.tolist() == b.tolist() and rngs_a == rngs_b


def test_chained_draws_advance():
    first, rngs = draw(make_rngs(42), "slip", lambda g: g.random(4))
    second, _ = draw(rngs, "slip", lambda g: g.random(4))
    assert first.tolist() != second.tolist()


@settings(max_examples=25)
@given(seed=seeds, sizes=st.lists(st.integers(min_value=0, max_value=7), max_size=6))
def test_chained_draws_equal_one_continuous_generator(seed, sizes):
    # The whole PCG64 state is carried, including the buffered half of a 64-bit word that odd counts of
    # 32-bit draws leave behind (has_uint32 / uinteger).
    plain = np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed).spawn(5)[1]))
    rngs = make_rngs(seed)
    for n in sizes:
        got, rngs = draw(rngs, "water", lambda g: g.integers(0, 2**32, size=n, dtype=np.uint32))
        assert got.tolist() == plain.integers(0, 2**32, size=n, dtype=np.uint32).tolist()


def test_rngs_is_frozen():
    rngs = make_rngs(42)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rngs.water = rngs.slip


# --- invalid input ------------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [-1, 1.5, "42", True, None])
def test_invalid_seed_is_rejected(seed):
    with pytest.raises((TypeError, ValueError)):
        make_rngs(seed)


def test_numpy_integer_seed_is_accepted():
    assert make_rngs(np.int64(42)) == make_rngs(42)


def test_unknown_stream_is_rejected():
    with pytest.raises(ValueError, match="unknown stream"):
        draw(make_rngs(42), "weather", lambda g: g.random())
