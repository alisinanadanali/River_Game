"""Render layer (pygame-ce): reads state, observations and events, never writes to the engine (ADR-005)."""

from engine.config import CONFIG_DIR

PROJECT_ROOT = CONFIG_DIR.parent  # file paths in the render config (pose images, fonts) are relative to it
