"""MODEL.md Appendix A.2: with the chosen set, an empty stone (h ~ U[lo, hi]) is under water 21 % of the time.

P(L(c,t) > h) for h ~ U[lo, hi] equals E[clip((L − lo)/(hi − lo), 0, 1)], so no stones need to be drawn. The
level is strongly autocorrelated (OU time ≈ 12.5 ticks, waves ≈ 18 ticks to cross), so the standard error comes
from batch means: the run is cut into blocks much longer than those times and the block averages are treated as
independent. Deterministic seed; tolerance 4 standard errors plus the appendix's rounding (0.005).
"""

import numpy as np

from engine.actions import Actions
from engine.state import new_game
from engine.step import step

from tests.support import config_with

TICKS = 20_000
WARM_UP = 500
BATCHES = 40
APPENDIX = 0.21


def test_empty_stone_under_water_fraction():
    cfg = config_with({"time": {"game_length_ticks": TICKS + WARM_UP + 1}})
    lo, hi = cfg.map.stone_base_h_cm
    state, rngs = new_game(cfg, 7)
    covered = np.empty(TICKS)
    for i in range(TICKS + WARM_UP):
        state, rngs, _ = step(state, Actions(), rngs)
        if i >= WARM_UP:
            covered[i - WARM_UP] = np.clip((state.water.level - lo) / (hi - lo), 0, 1).mean()
    batch_means = covered.reshape(BATCHES, -1).mean(axis=1)
    se = batch_means.std(ddof=1) / np.sqrt(BATCHES)
    assert abs(covered.mean() - APPENDIX) < 4 * se + 0.005, f"{covered.mean():.3f} ± {se:.3f} vs A.2 {APPENDIX}"
