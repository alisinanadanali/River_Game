"""VISUALS §3: screenshots of a demo board as seen with normal vision and the three simulated dichromacies.

    uv run python -m tools.cvd_shots              # PNGs into runs/cvd/ (git-ignored)
    uv run python -m tools.cvd_shots --out DIR

The demo board shows every tier above and under the water, a mossy stone and a temporary stone. The pictures
are for the eye; tests/render/test_colour.py checks the numbers.
"""

import argparse
import dataclasses
import os
from pathlib import Path

import numpy as np

from engine.config import Config, load_config
from engine.events import Role
from engine.observe import Observation, observe
from engine.state import new_game
from engine.stones import TempStone
from render.colour import Vision, simulate
from render.strings_tr import CVD_SHOTS_DESCRIPTION, CVD_SHOTS_OUT_HELP, CVD_SHOTS_WRITTEN

DEFAULT_OUT = Path("runs") / "cvd"
SEED = 0
LEVEL_CM = 0.0
TIER_HEIGHTS_CM = (15.0, 2.0, -6.0, -20.0)   # base heights: KURU, BİLEK, DİZ, TEHLİKE at LEVEL_CM (VISUALS §3)
TIER_ROW, MOSSY_ROW = 6, 3                    # rows of the demo board; the tiers stand in columns 1…4
TEMP_CELL = (3, 6)
CHANNEL_MAX = 255


def demo_stones() -> dict[tuple[int, int], float]:
    stones = {(TIER_ROW, 1 + i): h for i, h in enumerate(TIER_HEIGHTS_CM)}
    stones.update({(MOSSY_ROW, 1 + i): h for i, h in enumerate(TIER_HEIGHTS_CM)})
    return stones


def demo_observation(cfg: Config) -> Observation:
    """Water at LEVEL_CM everywhere; the demo stones (row MOSSY_ROW mossy), one fresh temporary stone."""
    state = new_game(cfg, SEED)[0]
    rows, cols = cfg.map.rows, cfg.map.cols
    is_stone, base_h, mossy = np.zeros((rows, cols), bool), np.zeros((rows, cols)), np.zeros((rows, cols), bool)
    for (r, c), h in demo_stones().items():
        is_stone[r, c], base_h[r, c], mossy[r, c] = True, h, r == MOSSY_ROW
    world = dataclasses.replace(state.world, is_stone=is_stone, base_h=base_h, mossy=mossy,
                                stiffness=np.full((rows, cols), cfg.map.stiffness_kg_per_cm))
    rock = TempStone(id=0, row=TEMP_CELL[0], col=TEMP_CELL[1], h=cfg.shrek.rock_initial_h_cm, spawned_at=0)
    stones = dataclasses.replace(state.stones, raise_h=np.zeros((rows, cols)), temp=(rock,), next_temp_id=1)
    water = dataclasses.replace(state.water, level=np.full(cols, LEVEL_CM))
    return observe(dataclasses.replace(state, world=world, stones=stones, water=water), Role.DONKEY)


def shots(pygame, cfg: Config) -> dict[Vision, np.ndarray]:
    """The demo frame as an (H, W, 3) uint8 image per vision."""
    from render.board import stand_z
    from render.characters.animator import Look
    from render.characters.pose import Clip, pose
    from render.draw import draw_scene, load_assets
    from render.layout import feet
    from render.scene import Scene

    obs = demo_observation(cfg)
    cells = {Role.SHREK: (-1, obs.shrek.col), Role.DONKEY: (obs.donkey.row, obs.donkey.col)}
    scene = Scene(obs, before=obs, u=1.0, levels=tuple(obs.water.level),
                  feet={role: feet(cfg, role, cell, stand_z(obs, *cell)) for role, cell in cells.items()},
                  rows={role: cell[0] for role, cell in cells.items()},
                  looks={role: Look(Clip.IDLE, pose(Clip.IDLE, 0.0, cfg), True) for role in Role},
                  mode="realtime", paused=False, seed=SEED)
    screen = pygame.Surface(cfg.render.window_px)
    draw_scene(screen, load_assets(cfg), scene)
    image = pygame.surfarray.array3d(screen).transpose(1, 0, 2) / CHANNEL_MAX     # (H, W, 3) in [0, 1]
    return {v: np.round(simulate(image, v) * CHANNEL_MAX).astype(np.uint8) for v in Vision}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.cvd_shots", description=CVD_SHOTS_DESCRIPTION)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=CVD_SHOTS_OUT_HELP)
    parser.add_argument("--profile", default=None)
    args = parser.parse_args(argv)
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame  # the window library only here: the board above is plain data

    cfg = load_config(args.profile)
    pygame.init()
    try:
        args.out.mkdir(parents=True, exist_ok=True)
        for vision, image in shots(pygame, cfg).items():
            pygame.image.save(pygame.surfarray.make_surface(image.transpose(1, 0, 2)), args.out / f"{vision.value}.png")
    finally:
        pygame.quit()
    print(CVD_SHOTS_WRITTEN.format(n=len(Vision), out=args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
