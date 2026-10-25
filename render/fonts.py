"""VISUALS §7: the committed Noto fonts (assets/fonts/), at the size the caller asks for."""

from pathlib import Path

import pygame

from engine.config import Config
from render import PROJECT_ROOT


def font_path(cfg: Config, mono: bool = False, root: Path = PROJECT_ROOT) -> Path:
    """Noto Sans for text, Noto Sans Mono for the numeric layer (render.font, render.font_mono)."""
    return root / (cfg.render.font_mono if mono else cfg.render.font)


def load_font(cfg: Config, size_px: int, mono: bool = False, root: Path = PROJECT_ROOT) -> pygame.font.Font:
    """The font at size_px. The fonts are committed, so there is no fallback: a missing file is pygame's
    FileNotFoundError, which names it."""
    return pygame.font.Font(font_path(cfg, mono, root), size_px)
