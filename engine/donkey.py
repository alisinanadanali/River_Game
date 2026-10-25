"""The donkey (MODEL.md §4, D-01 … D-10; TICK.md steps 3, 7 and 11).

The donkey walks the stone graph (M-01) carrying two LIFO bags. Each rule is a small pure function; the stages
(donkey_stage, depth_stage, expire_stance) chain them in TICK.md order and emit the events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.actions import DonkeyAction
from engine.config import Config, DonkeyConfig
from engine.events import (
    ActionRejected, Component, DepthState, DonkeyDepthChanged, DonkeyMoved, DonkeyMoveStarted, DonkeyRespawned,
    DonkeySlipped, DonkeyStance, DonkeySwept, DropCause, GameOver, GameOverReason, ItemDelivered, ItemDropped, ItemStatus, LifeLost,
    RejectReason, Role, Side, StanceReason, SweptCause,
)
from engine.evolve import evolve
from engine.items import drop_into_water, item_type, set_item
from engine.stones import temp_at
from engine.world import walkable

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports this module
    from engine.state import GameState
    from engine.tick import Tick

__all__ = ["Bag", "DepthState", "Donkey", "Side"]  # DepthState and Side live in engine.events (event fields)

MOVES = {  # D-05: (row, col) step; north is towards row R, the delivery bank
    DonkeyAction.MOVE_N: (1, 0),
    DonkeyAction.MOVE_S: (-1, 0),
    DonkeyAction.MOVE_E: (0, 1),
    DonkeyAction.MOVE_W: (0, -1),
}
STANCES = {DonkeyAction.STANCE_LEFT: Side.LEFT, DonkeyAction.STANCE_RIGHT: Side.RIGHT}  # D-08


@dataclass(frozen=True, kw_only=True)
class Bag:
    """ENTITIES.md Bag: item ids, the last one on top (LIFO). Mass and volume are kept in step with the items."""

    items: tuple[int, ...] = ()
    mass: float = 0.0     # kg
    volume: int = 0


@dataclass(frozen=True, kw_only=True)
class Donkey:
    """ENTITIES.md Donkey. Rows −1 and R are the banks. The defaults are a freshly (re)spawned donkey."""

    row: int
    col: int
    lives: int
    depth_state: DepthState = DepthState.DRY
    depth: float | None = None                    # cm, d = L − e (D-04); None on a bank
    move_target: tuple[int, int] | None = None    # D-05 slow move
    move_remaining: int = 0                       # ticks
    stance: Side = Side.NONE                      # D-08
    stance_since: int | None = None               # tick
    bag_left: Bag = Bag()
    bag_right: Bag = Bag()


def initial_donkey(config: Config) -> Donkey:
    """D-05: the donkey starts on the south bank in column ⌊C/2⌋, next to Shrek, with all its lives (D-07)."""
    return Donkey(row=-1, col=config.map.cols // 2, lives=config.time.lives)


# --- pure rules ------------------------------------------------------------------------

def in_river(donkey: Donkey, rows: int) -> bool:
    """M-01: rows 0 … R−1 are river, −1 and R are banks."""
    return 0 <= donkey.row < rows


def on_graph(state: GameState, row: int, col: int) -> bool:
    """M-01, D-05: banks, permanent stones and temporary stones (S-07)."""
    return walkable(state.world, row, col) or (0 <= row < state.world.rows and temp_at(state.stones, row, col) is not None)


def stone_under(state: GameState, row: int, col: int) -> tuple[float, float] | None:
    """D-01: (height before the load, stiffness) of the stone at a river cell, or None if there is none.

    Permanent stone: h_i + r_i(t) and k_i. Temporary stone: its height h(t) and rock_stiffness_kg_per_cm.
    """
    world = state.world
    if world.is_stone[row, col]:
        return float(world.base_h[row, col] + state.stones.raise_h[row, col]), float(world.stiffness[row, col])
    stone = temp_at(state.stones, row, col)
    if stone is not None:
        return stone.h, state.config.shrek.rock_stiffness_kg_per_cm
    return None


def load_kg(donkey: Donkey, config: Config) -> float:
    """D-01: m_D + M_bag."""
    return config.donkey.mass_kg + donkey.bag_left.mass + donkey.bag_right.mass


def effective_height(h: float, load: float, stiffness: float) -> float:
    """D-01: e = h − load / k, where h already includes r_i (permanent stone) or is the temporary stone's height."""
    return h - load / stiffness


def classify_depth(d: float, donkey_cfg: DonkeyConfig) -> DepthState:
    """D-04: each threshold belongs to the deeper state."""
    if d >= donkey_cfg.depth_swept_cm:
        return DepthState.SWEPT
    if d >= donkey_cfg.depth_knee_cm:
        return DepthState.KNEE
    if d >= donkey_cfg.depth_ankle_cm:
        return DepthState.ANKLE
    return DepthState.DRY


def fits(bag: Bag, mass: float, volume: int, donkey_cfg: DonkeyConfig) -> bool:
    """D-09: room for an item of this mass and volume on this side."""
    return bag.mass + mass <= donkey_cfg.bag_max_kg_per_side and bag.volume + volume <= donkey_cfg.bag_max_volume_per_side


def push(bag: Bag, item_id: int, mass: float, volume: int) -> Bag:
    """D-09: the item goes on top. The caller has checked fits()."""
    return Bag(items=bag.items + (item_id,), mass=bag.mass + mass, volume=bag.volume + volume)


def pop(bag: Bag, mass: float, volume: int) -> tuple[int, Bag]:
    """D-09: (top item, bag without it); mass and volume are the top item's."""
    if not bag.items:
        raise ValueError("pop from an empty bag")
    return bag.items[-1], Bag(items=bag.items[:-1], mass=bag.mass - mass, volume=bag.volume - volume)


def bag_of(donkey: Donkey, side: Side) -> Bag:
    return donkey.bag_left if side is Side.LEFT else donkey.bag_right


def with_bag(donkey: Donkey, side: Side, bag: Bag) -> Donkey:
    return evolve(donkey, bag_left=bag) if side is Side.LEFT else evolve(donkey, bag_right=bag)


def balance(donkey: Donkey, config: Config) -> float:
    """D-02: δ = (m_R − m_L) / (m_R + m_L + m_D), in (−1, 1)."""
    left, right = donkey.bag_left.mass, donkey.bag_right.mass
    return (right - left) / (right + left + config.donkey.mass_kg)


def heavy_side(delta: float, u: float) -> Side:
    """D-02: RIGHT for δ > 0, LEFT for δ < 0; δ = 0 is a coin, u < 0.5 → LEFT."""
    if delta > 0:
        return Side.RIGHT
    if delta < 0:
        return Side.LEFT
    return Side.LEFT if u < 0.5 else Side.RIGHT


def slip_probability(delta: float, mu: float, donkey_cfg: DonkeyConfig) -> float:
    """D-03: p_slip = min(1, p₀ + κ·δ²·μ)."""
    return min(1.0, donkey_cfg.slip_base_prob + donkey_cfg.slip_kappa * delta * delta * mu)


def slip_risk(world, donkey: Donkey, config: Config) -> tuple[float, bool]:
    """D-03: the next move's (p_slip, mossy) without drawing; 0 off a stone or with empty bags.

    `world` is the World or an observation's WorldView (both have rows, is_stone and mossy).
    """
    if not in_river(donkey, world.rows) or not (donkey.bag_left.items or donkey.bag_right.items):
        return 0.0, False
    mossy = bool(world.is_stone[donkey.row, donkey.col] and world.mossy[donkey.row, donkey.col])
    p = slip_probability(balance(donkey, config), config.map.mossy_slip_multiplier if mossy else 1.0, config.donkey)
    return p, mossy


def stance_ready(donkey: Donkey, t: int) -> bool:
    """D-08: a stance catches only in ticks after the one it was taken in."""
    return donkey.stance is not Side.NONE and t > donkey.stance_since


# --- TICK.md step 3 ------------------------------------------------------------------------

def donkey_stage(tick: Tick) -> Tick:
    """TICK.md step 3: a slow move goes on (D-05), or the validated action starts a move or sets a stance (D-08)."""
    donkey, action = tick.state.donkey, tick.actions.donkey
    if donkey.move_remaining > 0:
        return _continue_move(tick)
    if action in MOVES:
        return _start_move(tick, action)
    if action in STANCES:
        side = STANCES[action]
        tick = _set_donkey(tick, evolve(donkey, stance=side, stance_since=tick.t))
        return tick.emit(DonkeyStance, side=side, reason=StanceReason.SET)
    return tick


def _start_move(tick: Tick, action: DonkeyAction) -> Tick:
    """D-05: off the graph → ActionRejected(no_stone); else the stance ends, D-03 may slip, and the move is done
    or begun."""
    donkey, cfg = tick.state.donkey, tick.state.config
    dr, dc = MOVES[action]
    target = (donkey.row + dr, donkey.col + dc)
    if not on_graph(tick.state, *target):
        return tick.emit(ActionRejected, role=Role.DONKEY, component=Component.ACTION, reason=RejectReason.NO_STONE)
    if donkey.stance is not Side.NONE:
        donkey = evolve(donkey, stance=Side.NONE, stance_since=None)
        tick = _set_donkey(tick, donkey).emit(DonkeyStance, side=Side.NONE, reason=StanceReason.MOVED)
    tick = _maybe_slip(tick)
    donkey = tick.state.donkey  # a slip lightens a bag
    slow = cfg.donkey.slow_move_ticks
    if donkey.depth_state is DepthState.DRY or slow == 1:
        return _arrive(tick, donkey, target)
    tick = _set_donkey(tick, evolve(donkey, move_target=target, move_remaining=slow - 1))
    return tick.emit(DonkeyMoveStarted, from_cell=(donkey.row, donkey.col), to_cell=target, ticks=slow)


def _maybe_slip(tick: Tick) -> Tick:
    """D-03 (u_slip[0], side u_slip[1]): only leaving a stone, only with something in the bags."""
    state = tick.state
    donkey, cfg = state.donkey, state.config
    p, mossy = slip_risk(state.world, donkey, cfg)
    if not tick.u_slip[0] < p:                     # p = 0 off a stone or with empty bags, and u ∈ [0, 1)
        return tick
    delta = balance(donkey, cfg)
    side = heavy_side(delta, float(tick.u_slip[1]))
    tick = tick.emit(DonkeySlipped, side=side, p_slip=p, delta=delta, mossy=mossy)
    return drop_top(tick, side, DropCause.SLIP)


def drop_top(tick: Tick, side: Side, cause: DropCause) -> Tick:
    """D-03, D-06: the top item of `side` falls into the water of the donkey's cell (I-04)."""
    state = tick.state
    donkey = state.donkey
    bag = bag_of(donkey, side)
    t = item_type(state.config.items, state.items[bag.items[-1]].kind)
    item_id, rest = pop(bag, t.mass_kg, t.volume)
    tick = _set_donkey(tick, with_bag(donkey, side, rest))
    tick = tick.emit(ItemDropped, item_id=item_id, side=side, cause=cause)
    return drop_into_water(tick, item_id, donkey.row, float(donkey.col))


def _knee_drop(tick: Tick) -> Tick:
    """D-06 (u_slip[2], side u_slip[3]): in KNEE the heavy side may lose its top item."""
    donkey, cfg = tick.state.donkey, tick.state.config
    if not (donkey.bag_left.items or donkey.bag_right.items) or not tick.u_slip[2] < cfg.donkey.knee_drop_prob:
        return tick
    return drop_top(tick, heavy_side(balance(donkey, cfg), float(tick.u_slip[3])), DropCause.KNEE)


def _continue_move(tick: Tick) -> Tick:
    """D-05: one tick less; on the last one the donkey arrives. The target is not checked again (a vanished
    temporary stone means the donkey lands in the water and is swept in step 7)."""
    donkey = tick.state.donkey
    remaining = donkey.move_remaining - 1
    if remaining > 0:
        return _set_donkey(tick, evolve(donkey, move_remaining=remaining))
    return _arrive(tick, evolve(donkey, move_target=None, move_remaining=0), donkey.move_target)


def _arrive(tick: Tick, donkey: Donkey, target: tuple[int, int]) -> Tick:
    origin = (donkey.row, donkey.col)
    tick = _set_donkey(tick, evolve(donkey, row=target[0], col=target[1]))
    return tick.emit(DonkeyMoved, from_cell=origin, to_cell=target)


# --- TICK.md step 7 ------------------------------------------------------------------------

def depth_stage(tick: Tick) -> Tick:
    """TICK.md step 7: D-01 e, D-04 d and state; KNEE → D-06; SWEPT → D-07."""
    state = tick.state
    donkey, cfg = state.donkey, state.config
    if not in_river(donkey, cfg.map.rows):
        return _set_depth(tick, DepthState.DRY, None)
    stone = stone_under(state, donkey.row, donkey.col)
    if stone is None:
        return sweep(tick, SweptCause.STONE_VANISHED, None)
    h, k = stone
    d = float(state.water.level[donkey.col]) - effective_height(h, load_kg(donkey, cfg), k)
    new = classify_depth(d, cfg.donkey)
    if new is DepthState.SWEPT:
        return sweep(tick, SweptCause.DEPTH, d)
    tick = _set_depth(tick, new, d)
    return _knee_drop(tick) if new is DepthState.KNEE else tick


def _set_depth(tick: Tick, new: DepthState, d: float | None) -> Tick:
    donkey = tick.state.donkey
    if new is donkey.depth_state and d == donkey.depth:
        return tick  # e.g. every tick on a bank
    tick = _set_donkey(tick, evolve(donkey, depth_state=new, depth=d))
    if new is not donkey.depth_state:
        tick = tick.emit(DonkeyDepthChanged, old=donkey.depth_state, new=new, depth_cm=d, row=donkey.row, col=donkey.col)
    return tick


def sweep(tick: Tick, cause: SweptCause, depth: float | None) -> Tick:
    """D-07: bags emptied, one life lost, instant respawn on the south bank in the same column (stance and move
    cancelled). With no life left the game ends; the donkey is still put on the bank but not 'respawned'."""
    state = tick.state
    donkey = state.donkey
    sides = {i: Side.LEFT for i in donkey.bag_left.items} | {i: Side.RIGHT for i in donkey.bag_right.items}
    tick = tick.emit(
        DonkeySwept, row=donkey.row, col=donkey.col, depth_cm=depth, cause=cause, items_dropped=len(sides)
    )
    for item_id in sorted(sides):  # MODEL D-07: in id order, each into the water of the donkey's cell (I-04)
        tick = tick.emit(ItemDropped, item_id=item_id, side=sides[item_id], cause=DropCause.SWEPT)
        tick = drop_into_water(tick, item_id, donkey.row, float(donkey.col))
    lives = donkey.lives - 1
    tick = tick.emit(LifeLost, lives_left=lives)
    tick = _set_donkey(tick, Donkey(row=-1, col=donkey.col, lives=lives))
    if donkey.stance is not Side.NONE:
        tick = tick.emit(DonkeyStance, side=Side.NONE, reason=StanceReason.SWEPT)
    if lives > 0:
        return tick.emit(DonkeyRespawned, col=donkey.col)
    tick = evolve(tick, state=evolve(tick.state, game_over=GameOverReason.LIVES))
    return tick.emit(GameOver, reason=GameOverReason.LIVES, score=tick.state.score)


# --- TICK.md step 10 -----------------------------------------------------------------------

def delivery_stage(tick: Tick) -> Tick:
    """D-10: on the north bank every bagged item is delivered, in id order, and scores its points."""
    state = tick.state
    donkey = state.donkey
    if donkey.row != state.config.map.rows or not (donkey.bag_left.items or donkey.bag_right.items):
        return tick
    tick = _set_donkey(tick, evolve(donkey, bag_left=Bag(), bag_right=Bag()))
    for item_id in sorted(donkey.bag_left.items + donkey.bag_right.items):
        item = tick.state.items[item_id]
        points = item_type(state.config.items, item.kind).points
        tick = set_item(tick, evolve(item, status=ItemStatus.DELIVERED))
        tick = evolve(tick, state=evolve(tick.state, score=tick.state.score + points))
        tick = tick.emit(ItemDelivered, item_id=item_id, kind=item.kind, points=points)
    return tick


# --- TICK.md step 11 -----------------------------------------------------------------------

def expire_stance(tick: Tick) -> Tick:
    """D-08: the stance ends once t − stance_since ≥ stance_max_ticks (t before the clock advances)."""
    donkey = tick.state.donkey
    if donkey.stance is Side.NONE or tick.t - donkey.stance_since < tick.state.config.donkey.stance_max_ticks:
        return tick
    tick = _set_donkey(tick, evolve(donkey, stance=Side.NONE, stance_since=None))
    return tick.emit(DonkeyStance, side=Side.NONE, reason=StanceReason.EXPIRED)


def _set_donkey(tick: Tick, donkey: Donkey) -> Tick:
    return evolve(tick, state=evolve(tick.state, donkey=donkey))
