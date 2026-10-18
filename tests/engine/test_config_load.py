"""ADR-008: default.yaml + profiles/<name>.yaml -> merged, validated Config.

build_config is the pure part (dicts in, Config out); load_config only reads the files.
"""

import shutil

import pytest
import yaml
from pydantic import ValidationError

from engine.config import CONFIG_DIR, build_config, load_config

PROFILES = sorted(p.stem for p in (CONFIG_DIR / "profiles").glob("*.yaml"))


def test_profiles_dir_lists_the_documented_profiles():
    assert PROFILES == ["hard", "percolation_edge", "warmup"]   # CLAUDE.md doc map


# --- the real config files ------------------------------------------------------------------

def test_no_profile_is_default_yaml():
    cfg = load_config()
    assert cfg.meta.profile == "percolation_edge"
    assert cfg.map.stone_density == 0.58


@pytest.mark.parametrize("name", PROFILES)
def test_every_profile_loads_under_its_own_name(name):
    assert load_config(name).meta.profile == name


def test_warmup_overrides_and_inherits():
    cfg = load_config("warmup")
    assert cfg.map.stone_density == 0.72 and cfg.map.path_guarantee == "path"   # from warmup.yaml
    assert cfg.water.ou_sigma_cm == 2.0
    assert cfg.map.rows == 9 and cfg.donkey.mass_kg == 200                     # from default.yaml


def test_hard_raises_rocks_together():
    cfg = load_config("hard")
    assert cfg.map.max_rocks_to_solve == 3 and cfg.shrek.rock_max_active == 3


def test_percolation_edge_equals_default():
    # percolation_edge.yaml: "default.yaml bu profilin değerlerini taşır".
    assert load_config("percolation_edge") == load_config()


def test_loading_is_repeatable():
    assert load_config("warmup") == load_config("warmup")
    assert load_config() == load_config()       # an earlier profile load left default.yaml untouched


@pytest.mark.parametrize("name", ["dvorak", "../default", "profiles/warmup", ""])
def test_unknown_profile_is_rejected(name):
    with pytest.raises(ValueError, match="unknown profile"):
        load_config(name)


# --- build_config: rules on hand-made profiles -------------------------------------------------

@pytest.fixture(scope="module")
def default():
    with open(CONFIG_DIR / "default.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_profile_typo_is_rejected(default):
    profile = {"meta": {"profile": "x"}, "map": {"stone_densty": 0.7}}
    with pytest.raises(ValidationError, match="stone_densty"):
        build_config(default, profile, "x")


def test_profile_forgetting_a_paired_key_is_rejected(default):
    # hard.yaml without `shrek.rock_max_active: 3`: valid alone, invalid once merged (MODEL.md §9).
    profile = {"meta": {"profile": "x"}, "map": {"max_rocks_to_solve": 3}}
    with pytest.raises(ValidationError, match="max_rocks_to_solve"):
        build_config(default, profile, "x")


def test_profile_name_must_match_meta(default):
    # warmup.yaml copied to hard2.yaml without editing meta.profile.
    with pytest.raises(ValueError, match="meta.profile"):
        build_config(default, {"meta": {"profile": "warmup"}}, "hard2")


def test_profile_without_meta_is_rejected(default):
    with pytest.raises(ValueError, match="meta.profile"):
        build_config(default, {"map": {"rows": 11}}, "big")


@pytest.mark.parametrize("profile", [None, [], "warmup"])
def test_profile_must_be_a_mapping(default, profile):
    # An empty YAML file loads as None.
    with pytest.raises(ValueError, match="mapping"):
        build_config(default, profile, "x")


def test_load_config_reads_another_config_dir(tmp_path):
    shutil.copy(CONFIG_DIR / "default.yaml", tmp_path / "default.yaml")
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "big.yaml").write_text("meta:\n  profile: big\nmap:\n  rows: 11\n", encoding="utf-8")
    cfg = load_config("big", config_dir=tmp_path)
    assert cfg.map.rows == 11 and cfg.map.cols == 9
