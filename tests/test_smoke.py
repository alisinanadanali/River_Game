"""Toolchain smoke test (Phase 0, step 0).

Checks the environment, not the game: uv picked the pinned interpreter
(.python-version) and the locked libraries are importable.
"""

import sys


def test_python_is_pinned_312():
    assert sys.version_info[:2] == (3, 12)


def test_core_libraries_import():
    import hypothesis  # noqa: F401
    import numpy as np
    import pydantic
    import yaml  # noqa: F401

    assert pydantic.VERSION.startswith("2.")  # ADR-008: pydantic v2
    assert hasattr(np.random, "SeedSequence")  # ADR-006: RNG streams
