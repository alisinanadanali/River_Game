"""Hypothesis profiles: `dev` (default, fast) and `full` (ROADMAP Phase 0 acceptance: >= 200 seeds x 300 ticks).

    uv run pytest                              # dev
    uv run pytest --hypothesis-profile=full    # full: before a push and when closing a phase (any shell)

The option comes from hypothesis's pytest plugin and wins over the HYPOTHESIS_PROFILE environment variable,
which also works (bash: `HYPOTHESIS_PROFILE=full uv run pytest`; PowerShell: `$env:HYPOTHESIS_PROFILE = "full"`).

Property tests take their example count from the profile, so the same test is quick while working and
complete when it matters. A test that pins its own max_examples keeps it in both profiles.
"""

import os

from hypothesis import HealthCheck, settings

FULL_EXAMPLES = 200  # ROADMAP Phase 0: invariants over >= 200 seeds
DEV_EXAMPLES = 25

_COMMON = {"deadline": None, "suppress_health_check": [HealthCheck.too_slow, HealthCheck.data_too_large]}
settings.register_profile("full", max_examples=FULL_EXAMPLES, **_COMMON)
settings.register_profile("dev", max_examples=DEV_EXAMPLES, **_COMMON)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


def pytest_report_header(config):
    return f"hypothesis profile: {settings._current_profile} ({settings.default.max_examples} examples)"
