"""VISUALS §9.2: every clip's transform, checked against the table and hand-computed values.

The clip list, each clip's image, kind (loop / one-shot) and roles are read from the VISUALS §9.2 table, so the
doc is the oracle. Formula checks use round config values so the expected numbers can be worked out by hand.
"""

import math
import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.events import Role
from render.characters.pose import CLIPS_OF, LOOPS, Clip, Transform, duration_s, is_done, pose
from tests.support import config_with

VISUALS = Path(__file__).resolve().parents[2] / "docs" / "VISUALS.md"

ANIM = {
    "breath_period_s": 2.0, "breath_scale": 0.1,
    "scared_shake_px": 2.0, "scared_shake_hz": 5.0,
    "wade_period_s": 0.5, "wade_bob_px": 4.0,
    "dam_shake_px": 3.0, "dam_shake_hz": 10.0,
    "hop_height_px": 20.0, "land_s": 0.2, "land_squash": 0.1,
    "throw_s": 1.0, "throw_windup_ratio": 0.4, "throw_squash": 0.2,
    "slip_s": 1.0, "slip_tilt_deg": 20.0, "slip_wobble_hz": 2.0,
    "happy_s": 1.0, "happy_bounce_px": 10.0, "happy_bounces": 2,
    "respawn_s": 0.5,
    "swept_s": 2.0, "swept_slide_px": 100.0, "swept_tilt_deg": 40.0,
}
TICK_S = 0.5
CFG = config_with({"time": {"tick_seconds": TICK_S}, "render": {"animation": ANIM}})


def numbers(tr: Transform) -> tuple[float, ...]:
    return (tr.dx_px, tr.dy_px, tr.scale_x, tr.scale_y, tr.angle_deg, tr.alpha)


def clip_table() -> dict[Clip, dict[str, str]]:
    """VISUALS §9.2 rows: clip → {role, image, kind}; a row may name two clips (`SLIP_LEFT`, `SLIP_RIGHT`)."""
    text = VISUALS.read_text(encoding="utf-8")
    section = text.split("### 9.2", 1)[1].split("### 9.3", 1)[0]
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("| `"):
            continue
        for name in re.findall(r"`(\w+)`", cells[0]):
            rows[Clip(name)] = {"role": cells[1], "image": cells[2], "kind": cells[3]}
    return rows


TABLE = clip_table()
ROLE_WORDS = {Role.SHREK: ("Shrek", "ikisi"), Role.DONKEY: ("Eşek", "ikisi")}


# --- the table in VISUALS §9.2 ---------------------------------------------------------------------------------

def test_clips_are_the_ones_in_visuals():
    assert set(TABLE) == set(Clip)


@pytest.mark.parametrize("clip", list(Clip))
def test_image_and_kind_match_visuals(clip):
    assert pose(clip, 0.3, CFG).image == TABLE[clip]["image"]
    assert (clip in LOOPS) == (TABLE[clip]["kind"] == "döngü")
    assert (duration_s(clip, CFG) is None) == (clip in LOOPS)


@pytest.mark.parametrize("role", list(Role))
def test_roles_match_visuals(role):
    expected = {c for c, row in TABLE.items() if row["role"].startswith(ROLE_WORDS[role])}
    assert CLIPS_OF[role] == expected


@pytest.mark.parametrize("role", list(Role))
def test_every_image_a_role_uses_is_a_configured_pose(role):
    poses = getattr(CFG.render.characters, role.value).poses
    assert {pose(c, 0.0, CFG).image for c in CLIPS_OF[role]} <= set(type(poses).model_fields)


# --- loops -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("clip", sorted(LOOPS or Clip))
def test_loops_start_neutral_and_never_end(clip):
    assert numbers(pose(clip, 0.0, CFG)) == pytest.approx(numbers(Transform()), abs=1e-9)
    if clip in LOOPS:
        assert not is_done(clip, 1e6, CFG)


def test_idle_breathes():
    # scale_y = 1 + 0.1·sin(2πt/2): a quarter period (0.5 s) in, it is at its top
    top = pose(Clip.IDLE, 0.5, CFG)
    assert top.scale_y == pytest.approx(1.1)
    assert top.scale_x == pytest.approx(1 / 1.1)
    assert pose(Clip.IDLE, 1.5, CFG).scale_y == pytest.approx(0.9)
    assert numbers(pose(Clip.IDLE, 0.7 + 2.0, CFG)) == pytest.approx(numbers(pose(Clip.IDLE, 0.7, CFG)))


def test_scared_trembles_while_breathing():
    # dx = 2·sin(2π·5·t): top at t = 1/20 s
    assert pose(Clip.SCARED, 0.05, CFG).dx_px == pytest.approx(2.0)
    assert pose(Clip.SCARED, 0.5, CFG).scale_y == pytest.approx(pose(Clip.IDLE, 0.5, CFG).scale_y)


def test_wade_bobs_up_only():
    assert pose(Clip.WADE, 0.25, CFG).dy_px == pytest.approx(-4.0)   # dy = −4·|sin(πt/0.5)|
    assert pose(Clip.WADE, 0.75, CFG).dy_px == pytest.approx(-4.0)
    assert all(pose(Clip.WADE, t / 100, CFG).dy_px <= 0 for t in range(200))


def test_dam_strains():
    assert pose(Clip.DAM, 0.025, CFG).dx_px == pytest.approx(3.0)    # dx = 3·sin(2π·10·t)
    assert pose(Clip.DAM, 0.075, CFG).dx_px == pytest.approx(-3.0)


# --- one-shots -------------------------------------------------------------------------------------------------

def test_durations():
    assert duration_s(Clip.HOP, CFG) == pytest.approx(TICK_S + 0.2)   # flight = one tick, then the landing
    assert duration_s(Clip.THROW, CFG) == 1.0
    assert duration_s(Clip.SLIP_LEFT, CFG) == duration_s(Clip.SLIP_RIGHT, CFG) == 1.0
    assert duration_s(Clip.HAPPY, CFG) == duration_s(Clip.CHEER, CFG) == 1.0
    assert duration_s(Clip.RESPAWN, CFG) == 0.5
    assert duration_s(Clip.SWEPT, CFG) == 2.0


@pytest.mark.parametrize("clip", [c for c in Clip if c not in LOOPS] or list(Clip))
def test_one_shots_end_on_time(clip):
    d = duration_s(clip, CFG)
    assert not is_done(clip, d - 1e-6, CFG)
    assert is_done(clip, d, CFG)


@pytest.mark.parametrize("clip", [c for c in Clip if c not in LOOPS and c is not Clip.SWEPT] or list(Clip))
def test_one_shots_end_neutral(clip):
    end = pose(clip, duration_s(clip, CFG), CFG)
    assert numbers(end) == pytest.approx(numbers(Transform()), abs=1e-9)
    assert pose(clip, 99.0, CFG) == end  # held after the end, never extrapolated


def test_hop_arc_then_landing_squash():
    assert pose(Clip.HOP, 0.0, CFG).dy_px == 0
    assert pose(Clip.HOP, TICK_S / 2, CFG).dy_px == pytest.approx(-20.0)      # −4h·v(1−v) at v = ½
    assert pose(Clip.HOP, TICK_S / 4, CFG).dy_px == pytest.approx(-15.0)      # −4·20·¼·¾
    land = pose(Clip.HOP, TICK_S + 0.1, CFG)                                   # half way through land_s
    assert land.dy_px == pytest.approx(0) and land.scale_y == pytest.approx(0.9)
    assert pose(Clip.HOP, TICK_S / 2, CFG).scale_y == 1                       # no squash in the air


def test_throw_winds_up_then_stretches():
    assert pose(Clip.THROW, 0.4, CFG).scale_y == pytest.approx(0.8)            # fully wound at r·T
    assert pose(Clip.THROW, 0.2, CFG).scale_y == pytest.approx(1 - 0.2 * math.sin(math.pi / 4))
    # release, w = 0.75 at t = 0.4 + 0.75·0.6: 1 − 0.2·cos(0.75π)·0.25
    assert pose(Clip.THROW, 0.85, CFG).scale_y == pytest.approx(1 + 0.2 * math.sqrt(0.5) * 0.25)
    assert max(pose(Clip.THROW, t / 100, CFG).scale_y for t in range(101)) > 1  # it does stretch


def test_slip_tilts_towards_the_side_and_wobbles_out():
    assert pose(Clip.SLIP_LEFT, 0.0, CFG).angle_deg == pytest.approx(20.0)     # left = counter-clockwise
    assert pose(Clip.SLIP_LEFT, 0.125, CFG).angle_deg == pytest.approx(0, abs=1e-9)  # cos(2π·2·⅛) = 0
    assert pose(Clip.SLIP_LEFT, 0.25, CFG).angle_deg == pytest.approx(-15.0)   # 20·¾·cos(π): swings across
    assert pose(Clip.SLIP_LEFT, 0.5, CFG).angle_deg == pytest.approx(10.0)     # 20·(1 − ½)·cos(2π)
    for t in (0.0, 0.13, 0.5, 0.77):
        assert pose(Clip.SLIP_RIGHT, t, CFG).angle_deg == pytest.approx(-pose(Clip.SLIP_LEFT, t, CFG).angle_deg)


def test_happy_bounces_and_cheer_moves_the_same():
    assert pose(Clip.HAPPY, 0.25, CFG).dy_px == pytest.approx(-10.0)           # −10·|sin(2π·¼)|
    assert pose(Clip.HAPPY, 0.5, CFG).dy_px == pytest.approx(0, abs=1e-9)     # between the two bounces
    for t in (0.1, 0.25, 0.6):
        assert pose(Clip.CHEER, t, CFG).dy_px == pose(Clip.HAPPY, t, CFG).dy_px


def test_respawn_fades_in():
    assert pose(Clip.RESPAWN, 0.0, CFG).alpha == 0
    assert pose(Clip.RESPAWN, 0.25, CFG).alpha == pytest.approx(0.5)


def test_swept_slides_downstream_tips_over_and_fades():
    half = pose(Clip.SWEPT, 1.0, CFG)
    assert (half.dx_px, half.angle_deg, half.alpha) == pytest.approx((50.0, -20.0, 0.5))
    end = pose(Clip.SWEPT, 2.0, CFG)
    assert (end.dx_px, end.angle_deg, end.alpha) == pytest.approx((100.0, -40.0, 0.0))


def test_negative_elapsed_is_the_start():
    assert pose(Clip.HOP, -0.1, CFG) == pose(Clip.HOP, 0.0, CFG)


# --- every clip, any time --------------------------------------------------------------------------------------

@given(st.sampled_from(list(Clip)), st.floats(0, 10))
def test_transform_is_always_drawable(clip, t):
    tr = pose(clip, t, CFG)
    assert all(math.isfinite(v) for v in numbers(tr))
    assert 0 <= tr.alpha <= 1
    assert tr.scale_x > 0 and tr.scale_y > 0
    assert tr.scale_x * tr.scale_y == pytest.approx(1)  # squash and stretch keep the area
