"""ADR-008: profiles hold only differences and are deep-merged onto default.yaml."""

import copy

from engine.config import deep_merge

# Shortened from config/default.yaml and config/profiles/warmup.yaml.
DEFAULT = {
    "meta": {"config_version": 1, "profile": "percolation_edge"},
    "map": {"rows": 9, "cols": 9, "stone_density": 0.58, "path_guarantee": "max_rocks", "mossy_prob": 0.15},
    "water": {"ou_sigma_cm": 2.5, "wave_rate_per_tick": 0.03},
}
WARMUP = {
    "meta": {"profile": "warmup"},
    "map": {"stone_density": 0.72, "path_guarantee": "path", "mossy_prob": 0.10},
    "water": {"ou_sigma_cm": 2.0},
}


def test_profile_overrides_leaves_and_keeps_the_rest():
    assert deep_merge(DEFAULT, WARMUP) == {
        "meta": {"config_version": 1, "profile": "warmup"},
        "map": {"rows": 9, "cols": 9, "stone_density": 0.72, "path_guarantee": "path", "mossy_prob": 0.10},
        "water": {"ou_sigma_cm": 2.0, "wave_rate_per_tick": 0.03},
    }


def test_not_a_shallow_merge():
    # {**DEFAULT, **WARMUP} would replace the whole "map" section and lose rows/cols.
    merged = deep_merge(DEFAULT, WARMUP)
    assert merged["map"]["rows"] == 9 and merged["map"]["cols"] == 9


def test_merges_at_any_depth():
    base = {"items": {"types": {"watermelon": {"mass_kg": 50, "prob": 0.2}, "apple_crate": {"prob": 0.5}}}}
    override = {"items": {"types": {"watermelon": {"prob": 0.3}}}}
    assert deep_merge(base, override) == {
        "items": {"types": {"watermelon": {"mass_kg": 50, "prob": 0.3}, "apple_crate": {"prob": 0.5}}}
    }


def test_list_is_replaced_whole():
    # [0, 20] is a range: a profile's [5, 25] replaces it, elements are not merged.
    assert deep_merge({"stone_base_h_cm": [0, 20]}, {"stone_base_h_cm": [5, 25]}) == {"stone_base_h_cm": [5, 25]}
    assert deep_merge({"stone_base_h_cm": [0, 20]}, {"stone_base_h_cm": [5]}) == {"stone_base_h_cm": [5]}


def test_new_key_is_added():
    # A typo such as `stone_densty` survives the merge; rejecting it is validation's job (2b).
    assert deep_merge({"map": {"rows": 9}}, {"map": {"stone_densty": 0.7}}) == {
        "map": {"rows": 9, "stone_densty": 0.7}
    }


def test_type_clash_override_wins():
    assert deep_merge({"water": {"ou_sigma_cm": 2.5}}, {"water": 3}) == {"water": 3}
    assert deep_merge({"rows": 9}, {"rows": {"n": 9}}) == {"rows": {"n": 9}}


def test_empty_override_is_identity():
    assert deep_merge(DEFAULT, {}) == DEFAULT


def test_inputs_are_not_mutated():
    base, override = copy.deepcopy(DEFAULT), copy.deepcopy(WARMUP)
    deep_merge(base, override)
    assert base == DEFAULT and override == WARMUP


def test_result_shares_no_dicts_with_inputs():
    # Mutating the result must not leak back into default (the next profile load would see it).
    merged = deep_merge(DEFAULT, {})
    merged["map"]["rows"] = 99
    assert DEFAULT["map"]["rows"] == 9


def test_result_shares_no_lists_with_override():
    override = {"stone_base_h_cm": [5, 25]}
    merged = deep_merge({}, override)
    merged["stone_base_h_cm"].append(30)
    assert override == {"stone_base_h_cm": [5, 25]}
