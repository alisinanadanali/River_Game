"""VISUALS §3: the colour-blindness screenshots: four PNGs, each the normal frame through the simulation."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from engine.config import load_config  # noqa: E402
from engine.events import DepthState  # noqa: E402
from render.board import tier_of  # noqa: E402
from render.colour import Vision, rgb, simulate  # noqa: E402
from render.layout import cell_center  # noqa: E402
from tools.cvd_shots import LEVEL_CM, TIER_HEIGHTS_CM, TIER_ROW, demo_observation, main  # noqa: E402

CFG = load_config()


def test_the_demo_board_shows_every_tier_in_order():
    obs = demo_observation(CFG)
    levels = [LEVEL_CM] * CFG.map.cols
    tiers = [tier_of(obs, levels, TIER_ROW, 1 + i) for i in range(len(TIER_HEIGHTS_CM))]
    assert tiers == [DepthState.DRY, DepthState.ANKLE, DepthState.KNEE, DepthState.SWEPT]


def test_four_pictures_each_the_simulated_normal_one(tmp_path):
    assert main(["--out", str(tmp_path)]) == 0
    pygame.init()
    try:
        images = {v: pygame.surfarray.array3d(pygame.image.load(str(tmp_path / f"{v.value}.png"))) for v in Vision}
    finally:
        pygame.quit()
    x, y = (round(v) for v in cell_center(CFG, TIER_ROW, 1, TIER_HEIGHTS_CM[0]))   # the dry stone's top face
    dry = rgb(CFG.render.palette.dry)
    assert tuple(images[Vision.NORMAL][x, y]) == tuple(np.round(dry * 255))
    for vision in (Vision.PROTAN, Vision.DEUTAN, Vision.TRITAN):
        assert images[vision][x, y] == pytest.approx(simulate(dry, vision) * 255, abs=1)
        assert not np.array_equal(images[vision], images[Vision.NORMAL])
