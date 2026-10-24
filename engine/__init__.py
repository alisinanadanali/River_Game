"""Pure game core (ADR-005): stdlib, numpy, pydantic and pyyaml only; never imports an outer layer."""

ENGINE_VERSION = "0.1.0"  # = pyproject.toml [project] version (tests/engine/test_version.py); log header, EVENTS.md
