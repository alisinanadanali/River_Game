"""VISUALS §9.5: the character preview's pure core, and its window on SDL's dummy driver."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402
import yaml  # noqa: E402

from engine.config import load_config  # noqa: E402
from engine.events import Role  # noqa: E402
from render.characters.pose import CLIPS_OF, LOOPS, Clip, duration_s  # noqa: E402
from render.strings_tr import CLIP_NAMES  # noqa: E402
from tools.character_preview import (  # noqa: E402
    LOOP_SHOW_S,
    REST_S,
    Action,
    PreviewState,
    apply,
    auto_clip,
    main,
    shown_clip,
    yaml_snippet,
)

CFG = load_config()


def chars(state: PreviewState):
    return state.cfg.render.characters


def run(*actions: Action, state: PreviewState | None = None, now_s: float = 0.0) -> PreviewState:
    state = state or PreviewState(CFG)
    for action in actions:
        state = apply(state, action, now_s)
    return state


# --- tuning ----------------------------------------------------------------------------------------------------

def test_height_changes_only_the_selected_character():
    state = run(Action.TALLER, Action.TALLER)
    assert chars(state).shrek.height_px == CFG.render.characters.shrek.height_px + 4   # ±2 px a press
    assert chars(state).donkey == CFG.render.characters.donkey
    assert chars(run(Action.SHORTER)).shrek.height_px == CFG.render.characters.shrek.height_px - 2


def test_anchor_and_scale_change_only_the_selected_pose():
    state = run(Action.NEXT_POSE, Action.ANCHOR_RIGHT, Action.SCALE_DOWN)            # Shrek's second pose
    assert state.pose == "throw"
    old, new = CFG.render.characters.shrek.poses, chars(state).shrek.poses
    assert new.throw.anchor[0] == pytest.approx(old.throw.anchor[0] + 0.01)
    assert new.throw.scale == pytest.approx(old.throw.scale - 0.02)
    assert new.idle == old.idle and new.dam == old.dam


def test_anchor_stays_inside_the_image():
    state = run(*[Action.ANCHOR_RIGHT] * 100)
    assert chars(state).shrek.poses.idle.anchor[0] == 1.0
    assert chars(run(*[Action.ANCHOR_LEFT] * 100)).shrek.poses.idle.anchor[0] == 0.0


def test_scale_stays_positive():
    assert chars(run(*[Action.SCALE_DOWN] * 100)).shrek.poses.idle.scale > 0


def test_poses_cycle_and_the_role_switch_starts_at_idle():
    assert run(Action.PREV_POSE).pose == "dam"                                   # wraps around
    state = run(Action.NEXT_POSE, Action.NEXT_ROLE)
    assert (state.role, state.pose) == (Role.DONKEY, "idle")
    assert run(Action.NEXT_POSE, state=state).pose == "happy"
    assert run(Action.NEXT_ROLE, Action.NEXT_ROLE).role is Role.SHREK


def test_water_moves_two_cm_a_press():
    assert run(Action.WATER_UP, Action.WATER_UP, Action.WATER_DOWN).depth_cm == 2


def test_m_flips_both_characters():
    assert run(Action.FLIP).facing_right is False and run(Action.FLIP, Action.FLIP).facing_right is True


def test_debug_toggles():
    assert run(Action.TOGGLE_DEBUG).debug and not run(Action.TOGGLE_DEBUG, Action.TOGGLE_DEBUG).debug


# --- clips -----------------------------------------------------------------------------------------------------

def test_auto_plays_every_clip_of_the_role_in_turn():
    for role in Role:
        seen, t = [], 0.0
        while len(seen) < len(CLIPS_OF[role]):
            clip, elapsed = auto_clip(role, t + 1e-6, CFG)       # just inside the slot: the sum of t drifts
            assert elapsed == pytest.approx(1e-6, abs=1e-9)
            seen.append(clip)
            t += (LOOP_SHOW_S if clip in LOOPS else duration_s(clip, CFG)) + REST_S
        assert set(seen) == CLIPS_OF[role] and len(set(seen)) == len(seen)
        assert auto_clip(role, t + 1e-6, CFG)[0] == seen[0]                      # and starts over


def test_choosing_a_clip_stops_auto_for_that_character():
    state = run(Action.NEXT_CLIP, now_s=5.0)
    clip, elapsed = shown_clip(state, Role.SHREK, 5.25)
    assert clip == state.clip and clip in CLIPS_OF[Role.SHREK] and elapsed == pytest.approx(0.25)
    assert shown_clip(state, Role.DONKEY, 5.25) == auto_clip(Role.DONKEY, 5.25, state.cfg)
    assert run(Action.AUTO, state=state).clip is None


def test_clip_keys_cycle_through_the_roles_clips():
    order = []
    state = PreviewState(CFG, role=Role.DONKEY)
    for _ in range(len(CLIPS_OF[Role.DONKEY])):
        state = apply(state, Action.NEXT_CLIP, 0.0)
        order.append(state.clip)
    assert set(order) == CLIPS_OF[Role.DONKEY]
    assert apply(state, Action.NEXT_CLIP, 0.0).clip == order[0]
    assert apply(apply(state, Action.NEXT_CLIP, 0.0), Action.PREV_CLIP, 0.0).clip == order[-1]


def test_a_chosen_one_shot_repeats_after_a_rest():
    state = PreviewState(CFG, clip=Clip.THROW, clip_since_s=1.0)
    period = duration_s(Clip.THROW, CFG) + REST_S
    assert shown_clip(state, Role.SHREK, 1.0 + period + 0.1)[1] == pytest.approx(0.1)


def test_every_clip_has_a_turkish_name():
    assert set(CLIP_NAMES) == set(Clip)


# --- the config snippet ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", list(Role))
def test_snippet_pastes_back_into_the_config(role):
    state = run(Action.TALLER, Action.ANCHOR_LEFT, state=PreviewState(CFG, role=role))
    text = yaml_snippet(state.cfg, role)
    assert text.startswith(f"    {role.value}:\n")                        # indented to sit under render.characters
    pasted = yaml.safe_load(text)[role.value]
    assert pasted == getattr(state.cfg.render.characters, role.value).model_dump(mode="json")


# --- the window ------------------------------------------------------------------------------------------------

def test_window_runs_a_few_frames(capsys):
    assert main(["--frames", "3"]) == 0


def test_bench_prints_the_time_per_frame(capsys):
    assert main(["--bench", "--frames", "20"]) == 0
    assert "µs" in capsys.readouterr().out
