"""Water (MODEL.md §3, W-01 … W-07; TICK.md step 5).

Base level B (Ornstein–Uhlenbeck), Gaussian waves travelling west -> east, and Shrek's dam. Each W-rule is a
small pure function; water_stage chains them in the TICK.md step 5 sub-order and emits the events.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from engine.config import Config, WaterConfig
from engine.events import WaveExited, WaveOrigin, WaveSpawned
from engine.rng import Rngs, draw

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


def draw_noise(rngs: Rngs) -> tuple[float, Rngs]:
    """W-01, R-02: ε_t ~ N(0, 1) from rng_water, drawn every tick (also when σ = 0)."""
    return draw(rngs, "water", lambda g: float(g.standard_normal()))


def draw_arrivals(rngs: Rngs, water_cfg: WaterConfig) -> tuple[np.ndarray, Rngs]:
    """W-02, R-02: N_t ~ Poisson(λ), then N_t amplitudes ~ Exponential(ā), in one rng_water call every tick."""
    lam, a_bar = water_cfg.wave_rate_per_tick, water_cfg.wave_amp_mean_cm
    return draw(rngs, "water", lambda g: g.exponential(a_bar, g.poisson(lam)))


def spawn_waves(water: Water, amplitudes: np.ndarray, water_cfg: WaterConfig, t: int) -> tuple[Water, tuple[Wave, ...]]:
    """W-02: one UPSTREAM wave per amplitude at x = −k_spawn·s, numbered from next_wave_id."""
    x0 = -water_cfg.wave_spawn_offset_widths * water_cfg.wave_width_cols
    born = tuple(
        Wave(id=water.next_wave_id + i, amplitude=float(a), x=x0, origin=WaveOrigin.UPSTREAM, spawned_at=t)
        for i, a in enumerate(amplitudes)
    )
    return dataclasses.replace(water, waves=water.waves + born, next_wave_id=water.next_wave_id + len(born)), born


def advance_waves(waves: tuple[Wave, ...], water_cfg: WaterConfig) -> tuple[Wave, ...]:
    """W-03: x_k(t+1) = x_k(t) + v."""
    v = water_cfg.wave_speed_cols_per_tick
    return tuple(dataclasses.replace(w, x=w.x + v) for w in waves)


def cull_waves(waves: tuple[Wave, ...], cols: int, water_cfg: WaterConfig) -> tuple[tuple[Wave, ...], tuple[Wave, ...]]:
    """W-03: (kept, gone); a wave is gone once x > (C − 1) + k_cull·s."""
    edge = (cols - 1) + water_cfg.wave_cull_offset_widths * water_cfg.wave_width_cols
    return tuple(w for w in waves if w.x <= edge), tuple(w for w in waves if w.x > edge)


def wave_profile(waves: tuple[Wave, ...], cols: int, s: float) -> np.ndarray:
    """W-03: W(c) = Σ_k A_k·exp(−(c − x_k)²/2s²) at columns c = 0 … cols−1."""
    c = np.arange(cols, dtype=float)
    profile = np.zeros(cols)
    for w in waves:
        profile += w.amplitude * np.exp(-((c - w.x) ** 2) / (2 * s * s))
    return profile


def column_levels(base_level: float, waves: tuple[Wave, ...], dam: Dam, config: Config) -> np.ndarray:
    """W-07: L(c) = B + W_eff(c) − drop·1[dam active ∧ c > c_d].

    W-06 cut: with the dam active, columns c > c_d only see waves centred at x ≥ c_d; the west of the dam
    sees every wave (V0: no backwater rise).
    """
    cols, s = config.map.cols, config.water.wave_width_cols
    level = base_level + wave_profile(waves, cols, s)
    if dam.active:
        east = np.arange(cols) > dam.col
        east_only = tuple(w for w in waves if w.x >= dam.col)
        level = np.where(east, base_level + wave_profile(east_only, cols, s) - config.dam.downstream_drop_cm, level)
    return level


def water_stage(tick: Tick) -> Tick:
    """TICK.md step 5, sub-steps (a) … (h); the dam sub-steps (c) … (e) are W-04 … W-06."""
    state, cfg = tick.state, tick.state.config
    water, rngs = state.water, tick.rngs
    # (a) W-01
    eps, rngs = draw_noise(rngs)
    water = dataclasses.replace(water, base_level=ou_step(water.base_level, eps, cfg.water))
    # (b) W-03
    water = dataclasses.replace(water, waves=advance_waves(water.waves, cfg.water))
    # (f) W-02
    amplitudes, rngs = draw_arrivals(rngs, cfg.water)
    water, born = spawn_waves(water, amplitudes, cfg.water, tick.t)
    # (g) W-03
    kept, gone = cull_waves(water.waves, cfg.map.cols, cfg.water)
    water = dataclasses.replace(water, waves=kept)
    # (h) W-07
    water = dataclasses.replace(water, level=_read_only(column_levels(water.base_level, water.waves, state.dam, cfg)))

    tick = dataclasses.replace(tick, state=dataclasses.replace(state, water=water), rngs=rngs)
    for w in born:
        tick = tick.emit(WaveSpawned, wave_id=w.id, amplitude=w.amplitude, x=w.x, origin=w.origin)
    for w in gone:
        tick = tick.emit(WaveExited, wave_id=w.id)
    return tick


def _read_only(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array
