"""Character preview (VISUALS §9.5): both characters, every clip, and the values to tune scale and feet.

    uv run python -m tools.character_preview            # window
    uv run python -m tools.character_preview --bench    # drawing time per frame

The pure core (PreviewState, apply, auto_clip, shown_clip, yaml_snippet) is tested without a window; main() is
the pygame shell. Tuned values live only in the preview: P prints them for config/default.yaml.
"""

import argparse
import dataclasses
import time
from dataclasses import dataclass
from enum import Enum, auto

import yaml

from engine.config import Config, deep_merge, load_config, validate_config
from engine.events import Role
from render.characters.pose import CLIPS_OF, LOOPS, Clip, duration_s

LOOP_SHOW_S = 2.0      # auto mode: how long a loop clip is shown
REST_S = 0.5           # pause after each clip before the next one (or the repeat)
HEIGHT_STEP_PX = 2     # VISUALS §9.5 key table
ANCHOR_STEP = 0.01
SCALE_STEP = 0.02
WATER_STEP_CM = 2
DECIMALS = 4           # tuned values are rounded so repeated steps do not drift (0.52 + 0.01 − 0.01)


class Action(Enum):
    NEXT_ROLE = auto()
    PREV_CLIP = auto()
    NEXT_CLIP = auto()
    AUTO = auto()
    PREV_POSE = auto()
    NEXT_POSE = auto()
    TALLER = auto()
    SHORTER = auto()
    ANCHOR_LEFT = auto()
    ANCHOR_RIGHT = auto()
    SCALE_UP = auto()
    SCALE_DOWN = auto()
    WATER_UP = auto()
    WATER_DOWN = auto()
    FLIP = auto()
    TOGGLE_DEBUG = auto()


@dataclass(frozen=True)
class PreviewState:
    cfg: Config                      # the config with the tuned values in it
    role: Role = Role.SHREK          # the character the keys tune
    pose: str = "idle"               # the pose image the anchor and scale keys change
    clip: Clip | None = None         # the selected character's chosen clip; None: every clip in turn (auto)
    clip_since_s: float = 0.0        # when the chosen clip was picked
    depth_cm: float = 0.0            # water over the stone top, for the crop
    facing_right: bool = True        # both characters; M flips them to check the mirrored anchor
    debug: bool = False


def clips_of(role: Role) -> list[Clip]:
    """The role's clips in VISUALS §9.2 table order."""
    return [c for c in Clip if c in CLIPS_OF[role]]


def apply(state: PreviewState, action: Action, now_s: float) -> PreviewState:
    """One key press."""
    look = getattr(state.cfg.render.characters, state.role.value)
    pose_names = list(type(look.poses).model_fields)
    pose = getattr(look.poses, state.pose)
    match action:
        case Action.NEXT_ROLE:
            roles = list(Role)
            role = roles[(roles.index(state.role) + 1) % len(roles)]
            return dataclasses.replace(state, role=role, pose="idle", clip=None)
        case Action.PREV_CLIP | Action.NEXT_CLIP:
            clips, step = clips_of(state.role), 1 if action is Action.NEXT_CLIP else -1
            if state.clip is None:
                clip = clips[0] if step > 0 else clips[-1]
            else:
                clip = clips[(clips.index(state.clip) + step) % len(clips)]
            return dataclasses.replace(state, clip=clip, clip_since_s=now_s)
        case Action.AUTO:
            return dataclasses.replace(state, clip=None)
        case Action.PREV_POSE | Action.NEXT_POSE:
            step = 1 if action is Action.NEXT_POSE else -1
            return dataclasses.replace(state, pose=pose_names[(pose_names.index(state.pose) + step) % len(pose_names)])
        case Action.TALLER | Action.SHORTER:
            step = HEIGHT_STEP_PX if action is Action.TALLER else -HEIGHT_STEP_PX
            return _tuned(state, {"height_px": max(HEIGHT_STEP_PX, look.height_px + step)})
        case Action.ANCHOR_LEFT | Action.ANCHOR_RIGHT:
            step = ANCHOR_STEP if action is Action.ANCHOR_RIGHT else -ANCHOR_STEP
            x = min(1.0, max(0.0, round(pose.anchor[0] + step, DECIMALS)))
            return _tuned(state, {"poses": {state.pose: {"anchor": [x, pose.anchor[1]]}}})
        case Action.SCALE_UP | Action.SCALE_DOWN:
            step = SCALE_STEP if action is Action.SCALE_UP else -SCALE_STEP
            return _tuned(state, {"poses": {state.pose: {"scale": max(SCALE_STEP, round(pose.scale + step, DECIMALS))}}})
        case Action.WATER_UP | Action.WATER_DOWN:
            step = WATER_STEP_CM if action is Action.WATER_UP else -WATER_STEP_CM
            return dataclasses.replace(state, depth_cm=state.depth_cm + step)
        case Action.FLIP:
            return dataclasses.replace(state, facing_right=not state.facing_right)
        case Action.TOGGLE_DEBUG:
            return dataclasses.replace(state, debug=not state.debug)
    raise ValueError(f"unknown action {action!r}")


def _tuned(state: PreviewState, changes: dict) -> PreviewState:
    """The selected character's render.characters values changed, validated like any config (ADR-008)."""
    data = state.cfg.model_dump(mode="json", by_alias=True)
    data = deep_merge(data, {"render": {"characters": {state.role.value: changes}}})
    return dataclasses.replace(state, cfg=validate_config(data))


def auto_clip(role: Role, t_s: float, cfg: Config) -> tuple[Clip, float]:
    """Every clip of the role in turn: a loop for LOOP_SHOW_S, a one-shot for its duration, each then REST_S."""
    slots = [(c, (LOOP_SHOW_S if c in LOOPS else duration_s(c, cfg)) + REST_S) for c in clips_of(role)]
    t = t_s % sum(length for _, length in slots)
    for clip, length in slots:
        if t < length:
            return clip, t
        t -= length
    return slots[-1][0], t  # float rounding at the very end of the cycle


def shown_clip(state: PreviewState, role: Role, now_s: float) -> tuple[Clip, float]:
    """(clip, elapsed) for `role`: the chosen clip, repeated after REST_S, or the auto cycle."""
    if role is not state.role or state.clip is None:
        return auto_clip(role, now_s, state.cfg)
    since = now_s - state.clip_since_s
    if state.clip in LOOPS:
        return state.clip, since
    return state.clip, since % (duration_s(state.clip, state.cfg) + REST_S)


def yaml_snippet(cfg: Config, role: Role) -> str:
    """The role's render.characters entry, indented to paste under `characters:` in config/default.yaml."""
    look = getattr(cfg.render.characters, role.value).model_dump(mode="json")
    text = yaml.safe_dump({role.value: look}, sort_keys=False, allow_unicode=True, default_flow_style=None)
    return "".join("    " + line + "\n" for line in text.splitlines())


# --- the window ------------------------------------------------------------------------------------------------

BACKGROUND, TEXT, DIM, CROSS = (25, 25, 32), (235, 235, 235), (150, 150, 160), (255, 255, 255)
FONT_PX = 20
LINE_PX = 26
FRONT_TILES = 1.0     # front face height, × tile_h
CROSS_PX = 10


def _keys(pygame) -> dict[int, Action]:
    k = pygame
    return {
        k.K_TAB: Action.NEXT_ROLE, k.K_LEFT: Action.PREV_CLIP, k.K_RIGHT: Action.NEXT_CLIP, k.K_SPACE: Action.AUTO,
        k.K_PAGEUP: Action.PREV_POSE, k.K_PAGEDOWN: Action.NEXT_POSE,
        k.K_PLUS: Action.TALLER, k.K_EQUALS: Action.TALLER, k.K_KP_PLUS: Action.TALLER,
        k.K_MINUS: Action.SHORTER, k.K_KP_MINUS: Action.SHORTER,
        k.K_a: Action.ANCHOR_LEFT, k.K_d: Action.ANCHOR_RIGHT, k.K_x: Action.SCALE_UP, k.K_z: Action.SCALE_DOWN,
        k.K_w: Action.WATER_UP, k.K_s: Action.WATER_DOWN, k.K_m: Action.FLIP, k.K_F1: Action.TOGGLE_DEBUG,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", default=None)
    parser.add_argument("--frames", type=int, default=0, help="stop after this many frames (0: run until Esc)")
    parser.add_argument("--bench", action="store_true", help="time the drawing instead of opening a window")
    args = parser.parse_args(argv)

    import pygame  # the shell only: the core above is tested without it

    cfg = load_config(args.profile)
    pygame.init()
    try:
        if args.bench:
            return _bench(pygame, cfg, args.frames or 600)
        return _window(pygame, PreviewState(cfg), args.frames)
    finally:
        pygame.quit()


def _load(cfg: Config) -> dict:
    from render.characters.sprites import load_character

    return {role: load_character(role, cfg) for role in Role}


def _feet(cfg: Config, role: Role) -> tuple[float, float]:
    """The middle of a stone's top face, one per half of the window."""
    w, h = cfg.render.window_px
    half = w / 2
    return (half / 2 if role is Role.SHREK else half + half / 2), h * 0.6


def _draw_frame(pygame, screen, state: PreviewState, sprites: dict, font, now_s: float) -> None:
    from render.characters.animator import Look
    from render.characters.pose import pose
    from render.characters.sprites import draw
    from render.strings_tr import (
        CLIP_NAMES,
        PREVIEW_AUTO,
        PREVIEW_FALLBACK,
        PREVIEW_HINT,
        PREVIEW_MANUAL,
        PREVIEW_SELECTED,
        PREVIEW_VALUES,
        PREVIEW_WATER,
        ROLE_NAMES,
    )

    cfg = state.cfg
    layout, palette = cfg.render.layout, cfg.render.palette
    screen.fill(BACKGROUND)
    for role in Role:
        fx, fy = _feet(cfg, role)
        top = pygame.Rect(0, 0, layout.tile_w_px, layout.tile_h_px)
        top.center = (round(fx), round(fy))
        stone = pygame.Color(palette.dry)
        front = pygame.Rect(top.left, top.bottom, top.width, round(layout.tile_h_px * FRONT_TILES))
        pygame.draw.rect(screen, [round(c * layout.front_shade) for c in stone[:3]], front)  # VISUALS §2 prism
        pygame.draw.rect(screen, stone, top)
        clip, elapsed = shown_clip(state, role, now_s)
        look = Look(clip, pose(clip, elapsed, cfg), state.facing_right)
        water_y = fy - state.depth_cm * layout.px_per_cm
        area = draw(screen, sprites[role], look, (fx, fy), water_y if state.depth_cm > 0 else None)
        water = pygame.Surface((cfg.render.window_px[0] // 2, max(0, cfg.render.window_px[1] - round(water_y))),
                               pygame.SRCALPHA)
        water.fill((*pygame.Color(palette.water)[:3], round(255 * layout.water_alpha)))
        screen.blit(water, (round(fx - water.get_width() / 2), round(water_y)))
        if state.debug:
            pygame.draw.rect(screen, CROSS, area, 1)
            pygame.draw.line(screen, CROSS, (fx - CROSS_PX, fy), (fx + CROSS_PX, fy))
            pygame.draw.line(screen, CROSS, (fx, fy - CROSS_PX), (fx, fy + CROSS_PX))

        look_cfg = getattr(cfg.render.characters, role.value)
        pose_name = state.pose if role is state.role else "idle"
        p = getattr(look_cfg.poses, pose_name)
        mode = PREVIEW_MANUAL if role is state.role and state.clip is not None else PREVIEW_AUTO
        lines = [
            ROLE_NAMES[role] + (PREVIEW_SELECTED if role is state.role else ""),
            f"{CLIP_NAMES[clip]} ({clip.value}, {mode})",
            PREVIEW_VALUES.format(height=look_cfg.height_px, pose=pose_name, ax=p.anchor[0], ay=p.anchor[1],
                                  scale=p.scale),
            PREVIEW_WATER.format(depth=state.depth_cm),
        ]
        if sprites[role].is_fallback:
            lines.append(PREVIEW_FALLBACK.format(files=", ".join(sprites[role].missing)))
        x = round(fx - cfg.render.window_px[0] / 4) + LINE_PX
        for i, line in enumerate(lines):
            screen.blit(font.render(line, True, TEXT if i < 2 else DIM), (x, LINE_PX + i * LINE_PX))
    for i, line in enumerate(PREVIEW_HINT):
        y = cfg.render.window_px[1] - (len(PREVIEW_HINT) + 1 - i) * LINE_PX
        screen.blit(font.render(line, True, DIM), (LINE_PX, y))


def _window(pygame, state: PreviewState, frames: int) -> int:
    from render.fonts import load_font
    from render.strings_tr import PREVIEW_PRINTED, PREVIEW_TITLE

    cfg = state.cfg
    screen = pygame.display.set_mode(cfg.render.window_px)
    pygame.display.set_caption(PREVIEW_TITLE)
    font, clock, keys = load_font(cfg, FONT_PX), pygame.time.Clock(), _keys(pygame)
    sprites = _load(cfg)
    count = 0
    while frames == 0 or count < frames:
        now = pygame.time.get_ticks() / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                return 0
            if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                print(yaml_snippet(state.cfg, state.role), end="")
                print(f"# {PREVIEW_PRINTED}")
            elif event.type == pygame.KEYDOWN and event.key in keys:
                before = state.cfg.render.characters
                state = apply(state, keys[event.key], now)
                if state.cfg.render.characters != before:
                    sprites = _load(state.cfg)
        _draw_frame(pygame, screen, state, sprites, font, now)
        pygame.display.flip()
        clock.tick(cfg.render.fps)
        count += 1
    return 0


def _bench(pygame, cfg: Config, frames: int) -> int:
    """VISUALS §9.6: both characters and the ghost per frame, every clip in turn; best of 5 runs."""
    from render.characters.animator import Look
    from render.characters.pose import pose
    from render.characters.sprites import draw
    from render.strings_tr import PREVIEW_BENCH, PREVIEW_KIND_IMAGE, PREVIEW_KIND_SHAPE, ROLE_NAMES

    screen = pygame.Surface(cfg.render.window_px)
    sprites = _load(cfg)
    fps = cfg.render.fps
    feet = {role: _feet(cfg, role) for role in Role}
    water_y = feet[Role.DONKEY][1] - WATER_STEP_CM * cfg.render.layout.px_per_cm
    runs = []
    for _ in range(5):
        start = time.perf_counter()
        for i in range(frames):
            t = i / fps
            for role in Role:
                clip, elapsed = auto_clip(role, t, cfg)
                draw(screen, sprites[role], Look(clip, pose(clip, elapsed, cfg), True), feet[role],
                     water_y if role is Role.DONKEY else None)
            ghost = pose(Clip.SWEPT, t % duration_s(Clip.SWEPT, cfg), cfg)
            draw(screen, sprites[Role.DONKEY], Look(Clip.SWEPT, ghost, True), feet[Role.DONKEY], water_y)
        runs.append((time.perf_counter() - start) / frames)
    kinds = ", ".join(
        f"{ROLE_NAMES[r]}: {PREVIEW_KIND_SHAPE if sprites[r].is_fallback else PREVIEW_KIND_IMAGE}" for r in Role
    )
    print(PREVIEW_BENCH.format(us=min(runs) * 1e6, kinds=kinds, fps=fps, share=100 * min(runs) * fps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
