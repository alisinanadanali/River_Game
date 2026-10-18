"""EVENTS.md log header: config_hash is the SHA-256 of the validated config's canonical JSON."""

import copy
import hashlib
import json
import re
import shutil

import pytest
import yaml

from engine.config import CONFIG_DIR, build_config, config_hash, load_config


@pytest.fixture(scope="module")
def default():
    with open(CONFIG_DIR / "default.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_format():
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", config_hash(load_config()))


def test_follows_the_documented_recipe():
    # EVENTS.md, written out independently: if this fails, every stored replay header is invalidated.
    cfg = load_config()
    canonical = json.dumps(
        cfg.model_dump(mode="json", by_alias=True), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert config_hash(cfg) == "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_same_config_same_hash():
    assert config_hash(load_config("warmup")) == config_hash(load_config("warmup"))


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("map", "stone_density", 0.581),
        ("water", "ou_sigma_cm", 2.6),
        ("donkey", "mass_kg", 201),
        ("render", "fps", 30),          # whole config is hashed, not only the engine's part
        ("meta", "profile", "other"),
    ],
)
def test_any_value_change_changes_the_hash(default, section, key, value):
    changed = copy.deepcopy(default)
    changed[section][key] = value
    assert config_hash(build_config(changed)) != config_hash(build_config(default))


def test_nested_value_change_changes_the_hash(default):
    changed = copy.deepcopy(default)
    changed["controls"]["keymaps"]["global"]["RESTART"] = 63     # F6 instead of F5
    assert config_hash(build_config(changed)) != config_hash(build_config(default))


def test_yaml_formatting_does_not_matter(tmp_path, default):
    # Same values, no comments, keys sorted, flow style: a different file, the same config.
    (tmp_path / "profiles").mkdir()
    (tmp_path / "default.yaml").write_text(yaml.safe_dump(default, sort_keys=True, default_flow_style=True))
    assert config_hash(load_config(config_dir=tmp_path)) == config_hash(load_config())


def test_item_type_order_does_not_matter(default):
    # items.types is a free-named dict: its order comes from the YAML, unlike the schema's fixed fields.
    reordered = copy.deepcopy(default)
    reordered["items"]["types"] = dict(reversed(default["items"]["types"].items()))
    assert list(reordered["items"]["types"]) == ["watermelon", "potato_sack", "apple_crate"]
    assert config_hash(build_config(reordered)) == config_hash(build_config(default))


def test_int_and_float_spelling_do_not_matter(default):
    as_float = copy.deepcopy(default)
    as_float["map"]["stiffness_kg_per_cm"] = 50.0                # default.yaml writes 50
    assert config_hash(build_config(as_float)) == config_hash(build_config(default))


def test_profiles_hash_differently():
    hashes = {name: config_hash(load_config(name)) for name in ("warmup", "percolation_edge", "hard")}
    assert len(set(hashes.values())) == 3
    assert hashes["percolation_edge"] == config_hash(load_config())  # same config, same hash


def test_profile_and_hand_merged_default_agree(tmp_path):
    # Loading warmup as a profile, or a default.yaml that already holds warmup's values, is the same config.
    merged = load_config("warmup").model_dump(mode="json", by_alias=True)
    (tmp_path / "profiles").mkdir()
    (tmp_path / "default.yaml").write_text(yaml.safe_dump(merged), encoding="utf-8")
    shutil.copy(CONFIG_DIR / "profiles" / "warmup.yaml", tmp_path / "profiles" / "warmup.yaml")
    assert config_hash(load_config(config_dir=tmp_path)) == config_hash(load_config("warmup"))
