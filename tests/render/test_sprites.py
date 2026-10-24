"""VISUALS §9.1 and §9.4: loading pose images, the fallback shape, and drawing a Look at the feet.

No window: SDL's dummy video driver. The real images live in assets/private/ and are not in git, so every test
makes its own small PNGs under tmp_path and points `root` there.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from engine.events import Role  # noqa: E402
from render.characters.animator import Look  # noqa: E402
from render.characters.pose import Clip, Transform  # noqa: E402
from render.characters.sprites import draw, fallback_surface, load_character, rotated_anchor  # noqa: E402
from tests.support import DEFAULT, config_with  # noqa: E402

BLACK, RED, BLUE = (0, 0, 0), (255, 0, 0), (0, 0, 255)
FEET = (200, 300)
POSE = {"anchor": [0.5, 1.0], "faces": "right", "scale": 1.0}
CFG = config_with({"render": {"characters": {
    "shrek": {"height_px": 120, "fallback_size_px": [64, 64], "fallback_color": "#7DB04B",
              "poses": {name: POSE for name in ("idle", "throw", "dam")}},
    "donkey": {"height_px": 120, "fallback_size_px": [44, 52], "fallback_color": "#8E8E8E",
               "poses": {"idle": POSE, "happy": {**POSE, "scale": 0.5}}},
}}})
SHREK_GREEN, DONKEY_GREY = (0x7D, 0xB0, 0x4B), (0x8E, 0x8E, 0x8E)


def png(root, rel: str, size=(50, 100), split=False):
    """A solid red PNG (left half red, right half blue when `split`) at root/rel."""
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(RED)
    if split:
        surface.fill(BLUE, pygame.Rect(size[0] // 2, 0, size[0] - size[0] // 2, size[1]))
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(path))


def files(role: Role) -> dict[str, str]:
    return {name: p["file"] for name, p in DEFAULT["render"]["characters"][role.value]["poses"].items()}


@pytest.fixture
def shrek_images(tmp_path):
    for rel in files(Role.SHREK).values():
        png(tmp_path, rel)
    return tmp_path


def canvas() -> pygame.Surface:
    target = pygame.Surface((400, 400))
    target.fill(BLACK)
    return target


def colour(target, xy) -> tuple[int, int, int]:
    return tuple(target.get_at((round(xy[0]), round(xy[1]))))[:3]


def drawn(sprites, transform=Transform(), facing_right=True, water_y=None) -> pygame.Surface:
    target = canvas()
    draw(target, sprites, Look(Clip.IDLE, transform, facing_right), FEET, water_y)
    return target


# --- loading and the fallback (VISUALS §9.4) ------------------------------------------------------------------

def test_no_files_means_the_fallback_shape(tmp_path):
    sprites = load_character(Role.SHREK, CFG, root=tmp_path)
    assert sprites.is_fallback
    assert sorted(sprites.missing) == sorted(files(Role.SHREK).values())
    assert set(sprites.poses) == {"idle", "throw", "dam"}
    assert all(p.surface.get_size() == (64, 64) and p.anchor == (32, 64) for p in sprites.poses.values())


def test_one_missing_file_falls_the_whole_character_back(tmp_path):
    for name, rel in files(Role.SHREK).items():
        if name != "dam":
            png(tmp_path, rel)
    sprites = load_character(Role.SHREK, CFG, root=tmp_path)
    assert sprites.missing == (files(Role.SHREK)["dam"],)
    assert all(p.surface.get_size() == (64, 64) for p in sprites.poses.values())  # no half image, half shape


def test_an_unreadable_file_counts_as_missing(tmp_path):
    for rel in files(Role.DONKEY).values():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"not a png")
    assert load_character(Role.DONKEY, CFG, root=tmp_path).is_fallback


def test_images_are_scaled_to_their_height_and_anchored(tmp_path):
    for rel in files(Role.DONKEY).values():
        png(tmp_path, rel, size=(50, 100))
    sprites = load_character(Role.DONKEY, CFG, root=tmp_path)
    assert not sprites.is_fallback
    idle, happy = sprites.poses["idle"], sprites.poses["happy"]
    assert idle.surface.get_size() == (60, 120) and idle.anchor == (30, 120)   # height_px 120, width kept in ratio
    assert happy.surface.get_size() == (30, 60) and happy.anchor == (15, 60)   # scale 0.5
    assert idle.faces_right


@pytest.mark.parametrize(("role", "size"), [(Role.SHREK, (64, 64)), (Role.DONKEY, (44, 52))])
def test_fallback_surface_has_its_size(role, size):
    assert fallback_surface(role, CFG).get_size() == size


def test_fallback_shrek_is_a_green_square():
    shape = fallback_surface(Role.SHREK, CFG)
    assert tuple(shape.get_at((32, 32)))[:3] == SHREK_GREEN
    assert shape.get_at((0, 0)).a == 0                       # rounded corner: transparent


def test_fallback_donkey_is_a_grey_circle_with_ears():
    shape = fallback_surface(Role.DONKEY, CFG)
    w, h = shape.get_size()
    assert tuple(shape.get_at((w // 2, h - w // 2)))[:3] == DONKEY_GREY   # the circle's centre
    assert shape.get_at((0, h - 1)).a == 0                                 # a circle, not a square
    above_circle = [shape.get_at((x, y)).a for x in range(w) for y in range(h - w)]
    assert max(above_circle) == 255                                         # the ears stick out above it


def test_fallback_is_drawn_like_an_image(tmp_path):
    sprites = load_character(Role.SHREK, CFG, root=tmp_path)
    target = drawn(sprites)
    assert colour(target, (200, 300 - 32)) == SHREK_GREEN
    assert colour(target, (200, 300 + 5)) == BLACK


# --- drawing ---------------------------------------------------------------------------------------------------

def test_the_feet_stand_on_the_given_point(shrek_images):
    target = drawn(load_character(Role.SHREK, CFG, root=shrek_images))   # 60 × 120, anchor bottom centre
    assert colour(target, (200, 250)) == RED
    assert colour(target, (200, 182)) == RED and colour(target, (200, 178)) == BLACK   # top at 300 − 120
    assert colour(target, (200, 305)) == BLACK
    assert colour(target, (200 - 28, 250)) == RED and colour(target, (200 - 32, 250)) == BLACK


def test_offsets_move_the_drawing(shrek_images):
    target = drawn(load_character(Role.SHREK, CFG, root=shrek_images), Transform(dx_px=100, dy_px=-50))
    assert colour(target, (300, 220)) == RED
    assert colour(target, (200, 250)) == BLACK


def test_the_image_is_mirrored_when_facing_against_it(tmp_path):
    for rel in files(Role.SHREK).values():
        png(tmp_path, rel, split=True)                         # red left half, blue right half, faces right
    sprites = load_character(Role.SHREK, CFG, root=tmp_path)
    assert colour(drawn(sprites, facing_right=True), (185, 250)) == RED
    assert colour(drawn(sprites, facing_right=False), (185, 250)) == BLUE


def test_nothing_is_drawn_below_the_water_line(shrek_images):
    target = drawn(load_character(Role.SHREK, CFG, root=shrek_images), water_y=290)
    assert colour(target, (200, 295)) == BLACK
    assert colour(target, (200, 285)) == RED
    assert target.get_clip() == target.get_rect()              # the clip is put back


def test_the_water_line_stays_when_the_character_hops(shrek_images):
    # lifted 20 px the image spans y 160…280; the water at 270 cuts it there, not 20 px higher
    target = drawn(load_character(Role.SHREK, CFG, root=shrek_images), Transform(dy_px=-20), water_y=270)
    assert colour(target, (200, 265)) == RED and colour(target, (200, 275)) == BLACK


def test_alpha_fades_without_changing_the_loaded_image(shrek_images):
    sprites = load_character(Role.SHREK, CFG, root=shrek_images)
    assert colour(drawn(sprites, Transform(alpha=0.0)), (200, 250)) == BLACK
    assert colour(drawn(sprites, Transform(alpha=0.5)), (200, 250))[0] == pytest.approx(128, abs=2)
    assert colour(drawn(sprites), (200, 250)) == RED           # the cached surface is still opaque


def test_squash_keeps_the_feet(shrek_images):
    target = drawn(load_character(Role.SHREK, CFG, root=shrek_images), Transform(scale_x=2.0, scale_y=0.5))
    assert colour(target, (200 - 55, 280)) == RED              # 120 wide
    assert colour(target, (200, 235)) == BLACK                 # 60 high
    assert colour(target, (200, 298)) == RED


def test_rotation_turns_about_the_feet(shrek_images):
    target = drawn(load_character(Role.SHREK, CFG, root=shrek_images), Transform(angle_deg=90))
    assert colour(target, (140, 300)) == RED                   # counter-clockwise: the body now lies west
    assert colour(target, (200, 250)) == BLACK


@pytest.mark.parametrize(
    ("anchor", "angle", "rotated_size", "expected"),
    [
        ((5, 20), 0, (10, 20), (5, 20)),
        ((5, 20), 90, (20, 10), (20, 5)),     # bottom centre → right middle (counter-clockwise)
        ((5, 20), 180, (10, 20), (5, 0)),
        ((5, 20), -90, (20, 10), (0, 5)),
        ((0, 20), 90, (20, 10), (20, 10)),    # bottom-left corner → bottom-right
        ((0, 20), -90, (20, 10), (0, 0)),     # bottom-left corner → top-left
    ],
)
def test_rotated_anchor(anchor, angle, rotated_size, expected):
    assert rotated_anchor(anchor, (10, 20), angle, rotated_size) == pytest.approx(expected, abs=1e-9)


def test_mirroring_keeps_an_off_centre_anchor_on_the_feet(tmp_path):
    for rel in files(Role.SHREK).values():
        png(tmp_path, rel)
    cfg = config_with({"render": {"characters": {"shrek": {"height_px": 120, "poses": {
        name: {**POSE, "anchor": [0.25, 1.0]} for name in ("idle", "throw", "dam")}}}}})
    sprites = load_character(Role.SHREK, cfg, root=tmp_path)      # 60 wide, feet 15 px from the left edge
    as_is, mirrored = drawn(sprites, facing_right=True), drawn(sprites, facing_right=False)
    assert colour(as_is, (200 + 40, 250)) == RED and colour(as_is, (200 - 20, 250)) == BLACK
    assert colour(mirrored, (200 - 40, 250)) == RED and colour(mirrored, (200 + 20, 250)) == BLACK
