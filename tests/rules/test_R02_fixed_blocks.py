"""R-02 (TICK.md step 0): every tick rng_throw draws 2 standard normals and rng_slip 4 uniforms, used or not."""

import numpy as np
import pytest

from engine.actions import Ability, Actions, DonkeyAction, ShrekAction
from engine.config import load_config
from engine.rng import SLIP_BLOCK, THROW_BLOCK, draw, draw_blocks, make_rngs
from engine.state import new_game
from engine.step import step

from tests.rules.test_R01_streams import GOLDEN_42


def test_block_sizes_match_model_doc():
    assert (THROW_BLOCK, SLIP_BLOCK) == (2, 4)


def test_shapes_and_ranges():
    u_throw, u_slip, _ = draw_blocks(make_rngs(42))
    assert u_throw.shape == (THROW_BLOCK,) and u_slip.shape == (SLIP_BLOCK,)
    assert u_throw.dtype == u_slip.dtype == np.float64
    assert np.all((0 <= u_slip) & (u_slip < 1))


def test_first_block_seed_42():
    u_throw, u_slip, _ = draw_blocks(make_rngs(42))
    assert u_throw.tolist() == GOLDEN_42["throw"][2]
    assert u_slip.tolist() == GOLDEN_42["slip"][2]


def test_blocks_are_read_only():
    u_throw, u_slip, _ = draw_blocks(make_rngs(42))
    for block in (u_throw, u_slip):
        with pytest.raises(ValueError):
            block[0] = 0.0


def test_only_throw_and_slip_advance():
    rngs = make_rngs(42)
    _, _, after = draw_blocks(rngs)
    assert (after.world, after.water, after.items) == (rngs.world, rngs.water, rngs.items)
    assert after.throw != rngs.throw and after.slip != rngs.slip


def test_equals_drawing_the_blocks_by_hand():
    rngs = make_rngs(9)
    u_throw, u_slip, after = draw_blocks(rngs)
    by_hand_throw, rngs = draw(rngs, "throw", lambda g: g.standard_normal(THROW_BLOCK))
    by_hand_slip, rngs = draw(rngs, "slip", lambda g: g.random(SLIP_BLOCK))
    assert u_throw.tolist() == by_hand_throw.tolist() and u_slip.tolist() == by_hand_slip.tolist()
    assert after == rngs


def test_consecutive_ticks_see_new_blocks():
    # ADR-011 risk: reusing the old rngs would repeat the same numbers every tick.
    rngs = make_rngs(42)
    seen = set()
    for _ in range(100):
        u_throw, u_slip, rngs = draw_blocks(rngs)
        seen.add((*u_throw.tolist(), *u_slip.tolist()))
    assert len(seen) == 100


def test_same_block_count_whatever_was_used():
    # Common random numbers: tick t's block depends only on t, not on what earlier ticks used.
    a = make_rngs(42)
    b = make_rngs(42)
    for _ in range(10):
        _, _, a = draw_blocks(a)      # tick where nothing was thrown
        _, _, b = draw_blocks(b)      # tick where everything was used: still one block
    assert a == b


@pytest.mark.parametrize("ability", list(Ability))
@pytest.mark.parametrize("donkey", [DonkeyAction.NOOP, DonkeyAction.MOVE_N, DonkeyAction.STANCE_LEFT])
def test_step_draws_exactly_one_block_whatever_the_actions(donkey, ability):
    # TICK.md step 0. Steps 2, 3 and 7 use the block; none of them may draw more from throw or slip.
    state, rngs = new_game(load_config(), 42)
    _, after, _ = step(state, Actions(donkey=donkey, shrek=ShrekAction(ability=ability)), rngs)
    _, _, one_block = draw_blocks(rngs)
    assert (after.throw, after.slip) == (one_block.throw, one_block.slip)
