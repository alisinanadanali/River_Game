"""Water (MODEL.md §3, W-01 … W-07; TICK.md step 5).

Base level B (Ornstein–Uhlenbeck), Gaussian waves travelling west -> east, and Shrek's dam. Each W-rule is a
small pure function; water_stage chains them in the TICK.md step 5 sub-order and emits the events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from engine.config import Config, WaterConfig
from engine.events import WaveOrigin

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports this module
    from engine.tick import Tick


@dataclass(frozen=True, kw_only=True)
class Wave:
    """ENTITIES.md Wave: a Gaussian bump of height `amplitude` centred at column `x` (W-02, W-03)."""

    id: int
    amplitude: float    # cm, > 0
    x: float            # columns; continuous, may be west of 0 or east of C-1
    origin: WaveOrigin
    spawned_at: int     # tick


@dataclass(frozen=True, kw_only=True, eq=False)
class Water:
    """ENTITIES.md Water. `level` is L(c) per column (W-07), read-only."""

    base_level: float           # B(t), cm
    waves: tuple[Wave, ...]     # in id order
    level: np.ndarray           # float[C], cm
    next_wave_id: int

    def __eq__(self, other):
        if not isinstance(other, Water):
            return NotImplemented
        return (
            (self.base_level, self.waves, self.next_wave_id) == (other.base_level, other.waves, other.next_wave_id)
            and np.array_equal(self.level, other.level)
        )

    __hash__ = None  # equal by content, and numpy arrays are not hashable


@dataclass(frozen=True, kw_only=True)
class Dam:
    """ENTITIES.md Dam. The defaults are the idle dam of a new game."""

    active: bool = False
    col: int | None = None            # c_d
    volume: float = 0.0               # Q, cm·columns
    started_at: int | None = None     # tick
    absorbed_volume: float = 0.0      # this episode's Σ absorbed V_k (W-06)
    accumulated_volume: float = 0.0   # this episode's Σ q_in (W-04)
    held_ticks: int = 0               # ticks with accumulation this episode
    burst_lock: bool = False          # S-08


def initial_water(config: Config) -> Water:
    """W-01: B(0) = μ, no waves, so L(c) = μ in every column."""
    mu = config.water.ou_mu_cm
    return Water(base_level=mu, waves=(), level=_read_only(np.full(config.map.cols, mu)), next_wave_id=0)


def ou_step(base_level: float, eps: float, water_cfg: WaterConfig) -> float:
    """W-01: one Ornstein–Uhlenbeck (AR(1)) step, B + θ(μ − B) + σ·ε."""
    theta, mu, sigma = water_cfg.ou_theta_per_tick, water_cfg.ou_mu_cm, water_cfg.ou_sigma_cm
    return base_level + theta * (mu - base_level) + sigma * eps


def _read_only(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array
