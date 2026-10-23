"""M-05: attempt i uses the i-th consecutive block of rng_world; the first attempt meeting M-04 is the map."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.config import load_config
from engine.rng import make_rngs
from engine.world import MapGenerationError, build_world, draw_world_block, generate_world, meets_guarantee

from tests.support import config_with

# P(rock-free path) ≈ 0.085 at p = 0.45 (MODEL A.1): most seeds need several attempts.
STRICT = config_with({"map": {"stone_density": 0.45, "path_guarantee": "path"}}).map


def test_without_a_guarantee_the_first_attempt_is_the_map():
    cfg = config_with({"map": {"path_guarantee": "none"}}).map
    rngs = make_rngs(42)
    world, after = generate_world(cfg, 42, rngs)
    block, one_block = draw_world_block(rngs, cfg)
    assert world == build_world(block, cfg, seed=42, attempt=0)
    assert after == one_block


@pytest.mark.parametrize("seed", range(15))
def test_attempt_i_is_the_ith_block(seed):
    world, after = generate_world(STRICT, seed, make_rngs(seed))
    rngs = make_rngs(seed)
    for i in range(world.regen_attempt + 1):
        block, rngs = draw_world_block(rngs, STRICT)
        candidate = build_world(block, STRICT, seed=seed, attempt=i)
        # Every earlier attempt fails the guarantee, the chosen one meets it.
        assert meets_guarantee(STRICT, candidate.rocks_to_solve) == (i == world.regen_attempt)
    assert candidate == world
    assert after == rngs  # rng_world advanced by exactly regen_attempt + 1 blocks


def test_some_seeds_really_regenerate():
    # Guards the test above: with no regeneration at all it would prove nothing about M-05.
    assert max(generate_world(STRICT, s, make_rngs(s))[0].regen_attempt for s in range(15)) >= 3


def test_only_the_world_stream_moves():
    rngs = make_rngs(3)
    _, after = generate_world(STRICT, 3, rngs)
    assert (after.water, after.items, after.throw, after.slip) == (rngs.water, rngs.items, rngs.throw, rngs.slip)


def test_same_seed_same_world():
    assert generate_world(STRICT, 11, make_rngs(11)) == generate_world(STRICT, 11, make_rngs(11))


def test_impossible_guarantee_is_an_error():
    cfg = config_with({"map": {"stone_density": 0.0, "path_guarantee": "path", "max_regen_attempts": 5}}).map
    with pytest.raises(MapGenerationError, match="5 attempts"):
        generate_world(cfg, 42, make_rngs(42))


def test_error_is_a_value_error():
    # MODEL M-05: the config is invalid for this seed. Callers catching config errors catch this too.
    assert issubclass(MapGenerationError, ValueError)


def test_last_allowed_attempt_is_used():
    # Exactly max_regen_attempts tries: a seed whose map needs attempt k works with k + 1 allowed, not k.
    seed = next(s for s in range(100) if generate_world(STRICT, s, make_rngs(s))[0].regen_attempt >= 2)
    k = generate_world(STRICT, seed, make_rngs(seed))[0].regen_attempt
    enough = config_with({"map": {"stone_density": 0.45, "path_guarantee": "path", "max_regen_attempts": k + 1}}).map
    too_few = config_with({"map": {"stone_density": 0.45, "path_guarantee": "path", "max_regen_attempts": k}}).map
    assert generate_world(enough, seed, make_rngs(seed))[0].regen_attempt == k
    with pytest.raises(MapGenerationError):
        generate_world(too_few, seed, make_rngs(seed))


@given(seed=st.integers(min_value=0, max_value=2**64 - 1), profile=st.sampled_from(["warmup", "percolation_edge", "hard"]))
def test_every_profile_map_meets_its_guarantee(seed, profile):
    cfg = load_config(profile).map
    world, _ = generate_world(cfg, seed, make_rngs(seed))
    assert meets_guarantee(cfg, world.rocks_to_solve)
    assert 0 <= world.regen_attempt < cfg.max_regen_attempts
