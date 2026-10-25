"""VISUALS §4.1: the skeleton's top-bar texts, from the scene alone (pure)."""

import dataclasses

from engine.events import GameOverReason, Role
from engine.observe import observe
from engine.state import new_game
from render.characters.animator import Look
from render.characters.pose import Clip, pose
from render.scene import Scene, banner, caption, top_bar
from render.strings_tr import GAME_OVER_REASONS, MODE_NAMES
from tests.support import config_with

CFG = config_with({})
SEED = 7


def a_scene(**changes) -> Scene:
    state = dataclasses.replace(new_game(CFG, SEED)[0], **changes)
    looks = {role: Look(Clip.IDLE, pose(Clip.IDLE, 0.0, CFG), True) for role in Role}
    return Scene(observe(state, Role.DONKEY), feet={role: (0.0, 0.0) for role in Role}, looks=looks,
                 mode="realtime", paused=False, seed=SEED)


def test_the_top_bar_has_the_time_left_the_score_the_lives_and_the_mode():
    t = 100
    text = top_bar(a_scene(t=t, score=12))
    left_s = (CFG.time.game_length_ticks - t) * CFG.time.tick_seconds
    assert f"{left_s:.0f} sn" in text
    assert "12" in text and str(CFG.time.lives) in text
    assert MODE_NAMES["realtime"] in text
    assert MODE_NAMES["tactical"] in top_bar(dataclasses.replace(a_scene(), mode="tactical"))


def test_the_time_left_counts_whole_seconds_up():
    """0.4 s left shows as 1 s, never 0 s while the game still runs."""
    ticks = CFG.time.game_length_ticks
    almost = next(t for t in range(ticks) if 0 < ((ticks - t) * CFG.time.tick_seconds) % 1 < 1)
    left_s = (ticks - almost) * CFG.time.tick_seconds
    assert f"{int(left_s) + 1} sn" in top_bar(a_scene(t=almost))

def test_float_noise_is_not_a_second_more():
    cfg = config_with({"time": {"tick_seconds": 1.1}})
    t = cfg.time.game_length_ticks - 50
    assert 50 * 1.1 > 55                                                                   # 55.00000000000001
    scene = a_scene(t=t)
    assert " 55 sn" in top_bar(dataclasses.replace(scene, obs=dataclasses.replace(scene.obs, config=cfg)))


def test_no_banner_while_playing():
    assert banner(a_scene()) is None


def test_the_banner_shows_the_pause():
    assert banner(dataclasses.replace(a_scene(), paused=True)) is not None


def test_the_banner_shows_the_end_the_reason_and_the_score():
    for reason in GameOverReason:
        text = banner(a_scene(game_over=reason, score=34))
        assert GAME_OVER_REASONS[reason.value] in text and "34" in text


def test_the_caption_shows_the_seed():
    assert "123456" in caption(123456)
