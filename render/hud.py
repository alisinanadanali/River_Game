"""VISUALS §5: the HUD's numbers. Pure: no pygame; built from the observation, the mode and the wall clock.

Each rule is computed by the engine's own function (D-02 balance, D-03 slip_risk, S-04 throw_sigma, W-05
wave_volume); only the display quantities (shares, the catch chance of MODEL Appendix A.3, the blinking) are here.
"""

import math
from dataclasses import dataclass

from engine.config import Config
from engine.donkey import Bag, balance, slip_risk
from engine.events import DepthState, Side
from engine.items import item_type
from engine.observe import Observation
from engine.shrek import is_handoff, throw_sigma
from engine.water import wave_volume
from render.colour import TIERS
from render.scene import seconds_left

BLINK_LIT_SHARE = 0.5   # VISUALS §5: a blink period is half lit, half dark


@dataclass(frozen=True)
class TopBar:
    seconds: int                     # time left, counted up (render.scene.seconds_left)
    time_share: float                # (game_length − t) / game_length
    score: int
    lives: int
    lives_max: int
    mode: str


@dataclass(frozen=True)
class BalanceView:
    delta: float                     # D-02
    limit: float                     # δ_max: one bag full, the other empty
    p_slip: float                    # D-03, the next move's
    tier: DepthState                 # the bar's colour (render.hud.slip_prob_tiers)
    mossy: bool
    multiplier: float                # map.mossy_slip_multiplier


@dataclass(frozen=True)
class BagView:
    kinds: tuple[str, ...]           # bottom to top (D-09: the top falls first)
    volumes: tuple[int, ...]
    mass: float                      # kg
    mass_max: float
    volume_max: int


@dataclass(frozen=True)
class StanceView:
    side: Side
    ticks_left: int                  # D-08: the ticks it still catches in, the next one included
    ticks_max: int
    seconds_left: float


@dataclass(frozen=True)
class DonkeyPanel:
    balance: BalanceView
    bags: tuple[BagView, BagView]    # left, right
    depth_state: DepthState
    depth_cm: float | None           # None on a bank
    stance: StanceView | None


@dataclass(frozen=True)
class NextItem:
    kind: str
    mass: float                      # kg
    volume: int
    sigma: float                     # cells, S-04 with the current aim (0 for a handoff)
    p_catch: float                   # MODEL Appendix A.3
    handoff: bool                    # S-06


@dataclass(frozen=True)
class Cooldown:
    left: int                        # ticks
    total: int

    @property
    def share(self) -> float:
        """The part still to wait, [0, 1]; 0 without a cooldown."""
        return self.left / self.total if self.total else 0.0


@dataclass(frozen=True)
class DamView:
    active: bool
    volume: float                    # Q, cm·columns
    q_max: float
    warn: bool                       # held and Q / q_max ≥ warn_share
    flash_on: bool                   # warn, in the lit half of the blink
    amplitude_cm: float | None       # W-05: the wave a release would start; None when not held


@dataclass(frozen=True)
class ShrekPanel:
    queue: tuple[str, ...]           # the kinds, head first
    capacity: int
    queue_warn: bool                 # len / capacity > warn_share
    next_item: NextItem | None
    throw: Cooldown
    rock: Cooldown
    rocks_active: int
    rocks_max: int
    dam: DamView


@dataclass(frozen=True)
class Hud:
    top: TopBar
    donkey: DonkeyPanel
    shrek: ShrekPanel


def hud(obs: Observation, mode: str, now_s: float) -> Hud:
    return Hud(_top(obs, mode), _donkey(obs), _shrek(obs, now_s))


def slip_tier(p: float, cfg: Config) -> DepthState:
    """VISUALS §5: the balance bar's colour for a slip probability."""
    return TIERS[sum(p >= bound for bound in cfg.render.hud.slip_prob_tiers)]


def catch_chance(sigma: float, radius: float) -> float:
    """MODEL Appendix A.3: P = 1 − exp(−r²/2σ²) for an isotropic 2-D Gaussian landing; 1 without noise."""
    if sigma == 0:
        return 1.0
    return 1 - math.exp(-radius * radius / (2 * sigma * sigma))


def _top(obs: Observation, mode: str) -> TopBar:
    time = obs.config.time
    return TopBar(seconds_left(obs), (time.game_length_ticks - obs.t) / time.game_length_ticks, obs.score,
                  obs.donkey.lives, time.lives, mode)


def _donkey(obs: Observation) -> DonkeyPanel:
    cfg, donkey = obs.config, obs.donkey
    d = cfg.donkey
    p, mossy = slip_risk(obs.world, donkey, cfg)
    bal = BalanceView(balance(donkey, cfg), d.bag_max_kg_per_side / (d.bag_max_kg_per_side + d.mass_kg), p,
                      slip_tier(p, cfg), mossy, cfg.map.mossy_slip_multiplier)
    stance = None
    if donkey.stance is not Side.NONE:
        left = donkey.stance_since + d.stance_max_ticks + 1 - obs.t
        stance = StanceView(donkey.stance, left, d.stance_max_ticks, left * cfg.time.tick_seconds)
    return DonkeyPanel(bal, (_bag(obs, donkey.bag_left), _bag(obs, donkey.bag_right)), donkey.depth_state,
                       donkey.depth, stance)


def _bag(obs: Observation, bag: Bag) -> BagView:
    d = obs.config.donkey
    kinds = tuple(obs.items[i].kind for i in bag.items)
    volumes = tuple(item_type(obs.config.items, k).volume for k in kinds)
    return BagView(kinds, volumes, bag.mass, d.bag_max_kg_per_side, d.bag_max_volume_per_side)


def _shrek(obs: Observation, now_s: float) -> ShrekPanel:
    cfg, shrek = obs.config, obs.shrek
    queue = tuple(obs.items[i].kind for i in obs.bank.queue)
    capacity = cfg.items.bank_capacity
    return ShrekPanel(
        queue=queue,
        capacity=capacity,
        queue_warn=len(queue) / capacity > cfg.render.hud.warn_share,
        next_item=_next_item(obs, queue[0]) if queue else None,
        throw=Cooldown(shrek.throw_cooldown, cfg.shrek.throw_cooldown_ticks),
        rock=Cooldown(shrek.rock_cooldown, cfg.shrek.rock_cooldown_ticks),
        rocks_active=len(obs.stones.temp),
        rocks_max=cfg.shrek.rock_max_active,
        dam=_dam(obs, now_s),
    )


def _next_item(obs: Observation, kind: str) -> NextItem:
    cfg, donkey, shrek = obs.config, obs.donkey, obs.shrek
    item = item_type(cfg.items, kind)
    handoff = is_handoff(donkey, shrek)
    sigma = 0.0 if handoff else throw_sigma(shrek.aim_row, item.mass_kg, cfg.shrek)
    return NextItem(kind, item.mass_kg, item.volume, sigma, catch_chance(sigma, cfg.shrek.catch_radius_cells),
                    handoff)


def _dam(obs: Observation, now_s: float) -> DamView:
    cfg, dam = obs.config, obs.dam
    hud_cfg, q_max = cfg.render.hud, cfg.dam.q_max_cm_cols
    warn = dam.active and dam.volume / q_max >= hud_cfg.warn_share
    lit = (now_s * hud_cfg.blink_hz) % 1 < BLINK_LIT_SHARE
    amplitude = dam.volume / wave_volume(1.0, cfg.water) if dam.active else None
    return DamView(dam.active, dam.volume, q_max, warn, warn and lit, amplitude)
