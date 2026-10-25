"""Nehir Geçidi: the pygame window (CONTROLS.md §7.1). A thin shell: it reads the clock and the pygame events,
gives them to the session (game/session.py) and draws the frame (VISUALS §4.1). No rules here.

    uv run python main.py [--seed N] [--profile P]
"""

import argparse
import secrets
import sys
import time
from collections.abc import Callable

import pygame

from controllers.keyboard import FocusLost, KeyDown, KeyEvent, KeyUp
from engine.config import Config, load_config
from game.session import Session, frame, start
from game.view import follow, new_view, scene
from render.draw import draw_scene, load_assets
from render.scene import caption
from render.strings_tr import MAIN_DESCRIPTION, MAIN_FRAMES_HELP, MAIN_PROFILE_HELP, MAIN_SEED_HELP

SEED_BITS = 32  # a random seed when none is given: any non-negative integer works (R-01)


def translate(event: pygame.event.Event) -> KeyEvent | None:
    """§7.1: key and focus events for the session; everything else (QUIT included) is the shell's."""
    if event.type == pygame.KEYDOWN:
        return KeyDown(event.scancode)
    if event.type == pygame.KEYUP:
        return KeyUp(event.scancode)
    if event.type == pygame.WINDOWFOCUSLOST:
        return FocusLost()
    return None


def run(cfg: Config, seed: int, frames: int = 0, clock: Callable[[], float] = time.perf_counter,
        inject: Callable[[int], None] | None = None) -> Session:
    """The loop until the window is closed, or for `frames` frames (0: no limit). `inject(i)` runs before frame i
    reads the event queue (tests post events there). Returns the last session."""
    pygame.init()
    try:
        screen = pygame.display.set_mode(cfg.render.window_px)
        pygame.display.set_caption(caption(seed))
        assets, limiter = load_assets(cfg), pygame.time.Clock()
        session = start(cfg, seed, clock())
        view = new_view(session, session.last_frame_s)
        i = 0
        while frames == 0 or i < frames:
            if inject is not None:
                inject(i)
            events = pygame.event.get()
            if any(e.type == pygame.QUIT for e in events):
                break
            now = clock()
            session = frame(session, [k for e in events if (k := translate(e)) is not None], now)
            view = follow(view, session, now)
            draw_scene(screen, assets, scene(view, session, now))
            pygame.display.flip()
            limiter.tick(cfg.render.fps)
            i += 1
        return session
    finally:
        pygame.quit()


def choose_seed(seed: int | None) -> int:
    return secrets.randbits(SEED_BITS) if seed is None else seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="main.py", description=MAIN_DESCRIPTION)
    parser.add_argument("--seed", type=int, default=None, help=MAIN_SEED_HELP)
    parser.add_argument("--profile", default=None, help=MAIN_PROFILE_HELP)
    parser.add_argument("--frames", type=int, default=0, help=MAIN_FRAMES_HELP)
    args = parser.parse_args(argv)
    run(load_config(args.profile), choose_seed(args.seed), args.frames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
