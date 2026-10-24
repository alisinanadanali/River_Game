"""Positions between ticks (VISUALS §9.1, ADR-002): pure, no pygame, time passed in."""


def tick_progress(now_s: float, tick_started_s: float, tick_seconds: float) -> float:
    """u = (now − tick start) / tick_seconds, clamped to [0, 1]."""
    return min(1.0, max(0.0, (now_s - tick_started_s) / tick_seconds))


def lerp(a: tuple[float, float], b: tuple[float, float], u: float) -> tuple[float, float]:
    """a + u · (b − a), per component."""
    return (a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]))
