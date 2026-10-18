"""Validated, immutable game configuration (ADR-008).

default.yaml + optional profile (differences only) -> deep merge -> pydantic validation -> frozen Config.
"""

import copy


def deep_merge(base: dict, override: dict) -> dict:
    """ADR-008: merge `override` onto `base` recursively; the inputs are not modified.

    Where both sides hold a dict, merge inside it; anything else (scalar, list, type clash) is replaced
    by the override's value. Unknown keys are kept: rejecting them is validation's job.
    The result shares no dicts or lists with either input.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result
