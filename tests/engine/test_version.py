"""ROADMAP Phase 0 close: one version, kept in pyproject.toml; the engine carries it for log headers (EVENTS.md).

The engine cannot read pyproject.toml itself (no I/O in engine/, ADR-005), so it holds a constant and this test
keeps the two equal: bumping one without the other fails here.
"""

import dataclasses
import gc
import hashlib
import re
import tomllib
from pathlib import Path

from engine import ENGINE_VERSION
from engine.events import EVENT_SCHEMA_VERSION, Event

ROOT = Path(__file__).resolve().parents[2]


def test_engine_version_is_the_project_version():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert ENGINE_VERSION == project


def test_version_is_major_minor_patch():
    assert re.fullmatch(r"\d+\.\d+\.\d+", ENGINE_VERSION)


# EVENTS.md: schema 1 was frozen by v0.1.0. Every released schema's catalogue fingerprint is pinned here; changing
# an event (name, field, field type) without bumping EVENT_SCHEMA_VERSION and adding its fingerprint fails.
SCHEMA_FINGERPRINTS = {
    1: "224e5f91a484b5c096a1c2061a8e39f40f693a0d070a2b385ed286effbee658b",
}


def catalogue_fingerprint() -> str:
    """SHA-256 over every event class's name and its (field, type) list, in name order."""
    classes, todo = {}, [Event]
    while todo:
        for sub in todo.pop().__subclasses__():
            classes[sub.__name__] = [(f.name, str(f.type)) for f in dataclasses.fields(sub)]
            todo.append(sub)
    return hashlib.sha256(repr(sorted(classes.items())).encode("utf-8")).hexdigest()


def test_the_event_catalogue_matches_its_schema_version():
    assert catalogue_fingerprint() == SCHEMA_FINGERPRINTS[EVENT_SCHEMA_VERSION]


def test_the_fingerprint_sees_a_changed_field():
    # Guards the test above: a fingerprint blind to fields would pin nothing.
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Probe(Event):
        extra: int

    try:
        assert catalogue_fingerprint() != SCHEMA_FINGERPRINTS[EVENT_SCHEMA_VERSION]
    finally:
        del Probe
        gc.collect()  # __subclasses__ holds weak references: the probe is gone once collected
    assert catalogue_fingerprint() == SCHEMA_FINGERPRINTS[EVENT_SCHEMA_VERSION]
