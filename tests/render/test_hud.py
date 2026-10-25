"""VISUALS §5: the HUD model, pure. Every number is checked against the engine's rule functions, and the catch chance
against MODEL.md Appendix A.3's table."""

import dataclasses
import math
import re
from pathlib import Path

import pytest

from engine.donkey import Bag, balance, slip_risk
from engine.events import DepthState, Role, Side
from engine.items import Bank, Item, ItemStatus
from engine.observe import observe
from engine.shrek import throw_sigma
from engine.stones import TempStone
from engine.water import Dam, wave_volume
from render.hud import Cooldown, catch_chance, hud, slip_tier
from render.scene import seconds_left
from tests.support import config_with, set_up, still

MODEL = Path(__file__).resolve().parents[2] / "docs" / "MODEL.md"
CFG = still({"map": {"rows": 3, "cols": 5}})
LINE = ["..#m.", "..#..", "..#.."]  # (0, 3) is mossy
ITEMS = (
    Item(id=0, kind="watermelon", status=ItemStatus.IN_BAG),
    Item(id=1, kind="apple_crate", status=ItemStatus.IN_BAG),
    Item(id=2, kind="potato_sack", status=ItemStatus.IN_BAG),
    Item(id=3, kind="apple_crate", status=ItemStatus.ON_BANK),
    Item(id=4, kind="watermelon", status=ItemStatus.ON_BANK),
)
LOADED = {"bag_left": Bag(items=(0, 1), mass=60.0, volume=4), "bag_right": Bag(items=(2,), mass=30.0, volume=2)}


def an_obs(cfg=CFG, **fields):
    state, _ = set_up(cfg, LINE, items=ITEMS, **fields)
    return observe(state, Role.DONKEY)


def a_hud(obs=None, mode="realtime", now_s=0.0):
    return hud(an_obs() if obs is None else obs, mode, now_s)


# --- the top bar -------------------------------------------------------------------------------------------------

def test_the_top_bar_has_the_time_left_the_score_the_lives_and_the_mode():
    obs = dataclasses.replace(an_obs(donkey={"lives": 2}), t=75, score=9)
    top = a_hud(obs, mode="tactical").top
    length = CFG.time.game_length_ticks
    assert (top.seconds, top.score, top.lives, top.lives_max, top.mode) == (
        seconds_left(obs), 9, 2, CFG.time.lives, "tactical")
    assert top.time_share == pytest.approx((length - 75) / length)


# --- the donkey's panel ------------------------------------------------------------------------------------------

def test_the_balance_is_d02_within_the_largest_possible_imbalance():
    obs = an_obs(donkey={"row": 0, "col": 2, **LOADED})
    bal = a_hud(obs).donkey.balance
    d = CFG.donkey
    assert bal.delta == pytest.approx(balance(obs.donkey, CFG)) and bal.delta < 0     # the left is heavier
    assert bal.limit == pytest.approx(d.bag_max_kg_per_side / (d.bag_max_kg_per_side + d.mass_kg))
    full = an_obs(donkey={"bag_left": Bag(items=(0,), mass=d.bag_max_kg_per_side, volume=3)})
    assert abs(a_hud(full).donkey.balance.delta) == pytest.approx(bal.limit)          # one bag full, one empty


@pytest.mark.parametrize(("cell", "mossy"), [((0, 2), False), ((0, 3), True), ((-1, 2), False)])
def test_the_balance_colour_is_the_next_moves_p_slip(cell, mossy):
    obs = an_obs(donkey={"row": cell[0], "col": cell[1], **LOADED})
    bal = a_hud(obs).donkey.balance
    p, on_moss = slip_risk(obs.world, obs.donkey, CFG)
    assert (bal.p_slip, bal.mossy, bal.tier) == (p, mossy, slip_tier(p, CFG)) and on_moss is mossy
    assert bal.multiplier == CFG.map.mossy_slip_multiplier


@pytest.mark.parametrize(("share", "tier"), [
    (0.0, DepthState.DRY), (0.999, DepthState.DRY), (1.0, DepthState.ANKLE), (2.0, DepthState.KNEE),
    (3.0, DepthState.SWEPT), (3.5, DepthState.SWEPT),
])
def test_slip_tiers_split_at_the_configured_probabilities(share, tier):
    """share k.x: between tier k−1 and k of slip_prob_tiers (0 below the first)."""
    bounds = (0.0, *CFG.render.hud.slip_prob_tiers, 1.0)
    k, frac = int(share), share - int(share)
    p = bounds[k] + frac * (bounds[k + 1] - bounds[k])
    assert slip_tier(p, CFG) is tier


def test_the_bags_stack_bottom_to_top_with_their_volumes_and_mass():
    left, right = a_hud(an_obs(donkey=LOADED)).donkey.bags
    d = CFG.donkey
    assert (left.kinds, left.volumes, left.mass) == (("watermelon", "apple_crate"), (3, 1), 60.0)
    assert (right.kinds, right.volumes, right.mass) == (("potato_sack",), (2,), 30.0)
    assert (left.mass_max, left.volume_max) == (d.bag_max_kg_per_side, d.bag_max_volume_per_side)


def test_the_depth_is_the_donkeys():
    obs = an_obs(donkey={"row": 0, "col": 2, "depth_state": DepthState.KNEE, "depth": 9.5})
    panel = a_hud(obs).donkey
    assert (panel.depth_state, panel.depth_cm) == (DepthState.KNEE, 9.5)
    assert a_hud().donkey.depth_cm is None                                             # on the bank


@pytest.mark.parametrize(("t", "left"), [(11, 4), (12, 3), (14, 1)])
def test_the_stance_shows_the_ticks_it_still_catches_in(t, left):
    """D-08: taken at 10 with stance_max_ticks 4, it catches in ticks 11 … 14; the observation's t is the next."""
    cfg = still({"map": {"rows": 3, "cols": 5}, "donkey": {"stance_max_ticks": 4}})
    obs = dataclasses.replace(an_obs(cfg, donkey={"stance": Side.LEFT, "stance_since": 10}), t=t)
    stance = a_hud(obs).donkey.stance
    assert (stance.side, stance.ticks_left, stance.ticks_max) == (Side.LEFT, left, 4)
    assert stance.seconds_left == pytest.approx(left * cfg.time.tick_seconds)
    assert a_hud().donkey.stance is None


# --- Shrek's panel -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("queued", "warn"), [(4, False), (5, True)])
def test_the_bank_queue_warns_above_the_share(queued, warn):
    """capacity 5, warn_share 0.8: 4/5 is not above it, 5/5 is."""
    cfg = still({"map": {"rows": 3, "cols": 5}, "items": {"bank_capacity": 5}, "render": {"hud": {"warn_share": 0.8}}})
    items = ITEMS + tuple(Item(id=i, kind="apple_crate", status=ItemStatus.ON_BANK) for i in range(5, 8))
    state, _ = set_up(cfg, LINE, items=items, bank=Bank(queue=tuple(range(3, 3 + queued))))
    shrek = a_hud(observe(state, Role.DONKEY)).shrek
    assert (len(shrek.queue), shrek.capacity, shrek.queue_warn) == (queued, 5, warn)
    assert shrek.queue[:2] == ("apple_crate", "watermelon")


def test_the_next_item_has_its_sigma_and_catch_chance():
    obs = an_obs(bank=Bank(queue=(4, 3)), shrek={"aim_row": 2})
    item = a_hud(obs).shrek.next_item
    mass = CFG.items.types["watermelon"].mass_kg
    sigma = throw_sigma(2, mass, CFG.shrek)
    r = CFG.shrek.catch_radius_cells
    assert (item.kind, item.mass, item.volume, item.handoff) == ("watermelon", mass, 3, False)
    assert (item.sigma, item.p_catch) == (pytest.approx(sigma), pytest.approx(1 - math.exp(-r * r / (2 * sigma * sigma))))
    assert a_hud().shrek.next_item is None                                             # an empty queue


def test_a_handoff_has_no_noise():
    """S-06: the donkey on the south bank in Shrek's column, in a stance."""
    obs = an_obs(bank=Bank(queue=(3,)), donkey={"col": 2, "stance": Side.RIGHT, "stance_since": 0}, shrek={"col": 2})
    item = a_hud(obs).shrek.next_item
    assert (item.handoff, item.sigma, item.p_catch) == (True, 0.0, 1.0)
    moved = an_obs(bank=Bank(queue=(3,)), donkey={"col": 1, "stance": Side.RIGHT, "stance_since": 0}, shrek={"col": 2})
    assert a_hud(moved).shrek.next_item.handoff is False


def appendix_a3() -> list[tuple[int, list[float]]]:
    text = MODEL.read_text(encoding="utf-8")
    section = re.search(r"^### A\.3.*?(?=^### )", text, re.M | re.S)[0]
    rows = re.findall(r"^\| (\d+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \|$", section, re.M)
    return [(int(r[0]), [float(v.replace(",", ".")) for v in r[1:]]) for r in rows]


def test_the_catch_chance_matches_appendix_a3():
    table = appendix_a3()
    assert len(table) == 5
    cfg = config_with({})
    masses = [cfg.items.types[k].mass_kg for k in ("apple_crate", "potato_sack", "watermelon")]
    for distance, chances in table:
        for mass, expected in zip(masses, chances, strict=True):
            sigma = throw_sigma(distance - 1, mass, cfg.shrek)                         # aim_row + 1 = distance
            assert round(catch_chance(sigma, cfg.shrek.catch_radius_cells), 2) == expected, (distance, mass)
    assert catch_chance(0.0, 0.75) == 1.0


def test_the_cooldowns_and_the_rocks():
    rock = TempStone(id=0, row=1, col=3, h=20.0, spawned_at=0)
    obs = an_obs(shrek={"throw_cooldown": 2, "rock_cooldown": 0}, stones={"temp": (rock,), "next_temp_id": 1})
    shrek = a_hud(obs).shrek
    assert shrek.throw == Cooldown(2, CFG.shrek.throw_cooldown_ticks) and shrek.rock == Cooldown(0, CFG.shrek.rock_cooldown_ticks)
    assert shrek.throw.share == pytest.approx(2 / CFG.shrek.throw_cooldown_ticks) and shrek.rock.share == 0
    assert (shrek.rocks_active, shrek.rocks_max) == (1, CFG.shrek.rock_max_active)
    assert Cooldown(0, 0).share == 0                                                   # no cooldown: always ready


def dam_obs(volume):
    return an_obs(dam=Dam(active=True, col=2, volume=volume, started_at=0))


def test_the_dam_shows_its_volume_and_the_wave_it_would_release():
    q_max = CFG.dam.q_max_cm_cols
    dam = a_hud(dam_obs(0.5 * q_max)).shrek.dam
    assert (dam.active, dam.volume, dam.q_max, dam.warn) == (True, 0.5 * q_max, q_max, False)
    assert dam.amplitude_cm == pytest.approx(0.5 * q_max / wave_volume(1.0, CFG.water))
    idle = a_hud().shrek.dam
    assert (idle.active, idle.amplitude_cm, idle.warn, idle.flash_on) == (False, None, False, False)


def test_the_dam_warning_blinks_from_the_share_on():
    share, hz = CFG.render.hud.warn_share, CFG.render.hud.blink_hz
    q = share * CFG.dam.q_max_cm_cols
    period = 1 / hz
    assert a_hud(dam_obs(q), now_s=0.1 * period).shrek.dam.flash_on is True            # the first half: on
    assert a_hud(dam_obs(q), now_s=0.6 * period).shrek.dam.flash_on is False           # the second half: off
    assert a_hud(dam_obs(q), now_s=3.1 * period).shrek.dam.flash_on is True
    below = a_hud(dam_obs(0.99 * q), now_s=0.1 * period).shrek.dam
    assert (below.warn, below.flash_on) == (False, False)
    assert a_hud(dam_obs(q), now_s=0.6 * period).shrek.dam.warn is True
