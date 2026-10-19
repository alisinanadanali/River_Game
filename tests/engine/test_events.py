"""EVENTS.md: events are immutable records with t, seq, type; one canonical JSON line per event (ADR-009, ADR-010)."""

import dataclasses
import json

import pytest

from engine.events import EVENT_SCHEMA_VERSION, GameOver, GameOverReason, event_to_json, events_to_jsonl


def test_schema_version_is_one():
    # EVENTS.md log header: event_schema_version 1 until the first release (v0.1.0) fixes it.
    assert EVENT_SCHEMA_VERSION == 1


def test_common_fields_and_type_name():
    event = GameOver(t=299, seq=0, reason=GameOverReason.TIME, score=12)
    assert (event.t, event.seq, event.type) == (299, 0, "GameOver")


def test_type_is_not_a_field():
    # `type` comes from the class, so it can never disagree with it.
    names = [f.name for f in dataclasses.fields(GameOver)]
    assert names == ["t", "seq", "reason", "score"]


def test_events_are_frozen():
    event = GameOver(t=0, seq=0, reason=GameOverReason.LIVES, score=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.score = 99


def test_fields_are_keyword_only():
    # Positional construction would silently swap fields when one is added (schema change).
    with pytest.raises(TypeError):
        GameOver(0, 0, GameOverReason.TIME, 0)


def test_equal_events_compare_equal():
    a = GameOver(t=5, seq=1, reason=GameOverReason.TIME, score=3)
    b = GameOver(t=5, seq=1, reason=GameOverReason.TIME, score=3)
    assert a == b and a is not b


def test_reason_values_match_events_doc():
    assert [r.value for r in GameOverReason] == ["time", "lives"]


# --- canonical JSON ------------------------------------------------------------------

def test_json_line_exact_bytes():
    event = GameOver(t=299, seq=2, reason=GameOverReason.TIME, score=12)
    assert event_to_json(event) == '{"reason":"time","score":12,"seq":2,"t":299,"type":"GameOver"}'


def test_json_line_round_trips():
    event = GameOver(t=7, seq=0, reason=GameOverReason.LIVES, score=4)
    assert json.loads(event_to_json(event)) == {"t": 7, "seq": 0, "type": "GameOver", "reason": "lives", "score": 4}


def test_json_line_has_no_newline():
    # One event per line (JSONL): a newline inside would split the event.
    assert "\n" not in event_to_json(GameOver(t=0, seq=0, reason=GameOverReason.TIME, score=0))


def test_jsonl_is_one_line_per_event_with_trailing_newline():
    events = (
        GameOver(t=1, seq=0, reason=GameOverReason.TIME, score=1),
        GameOver(t=1, seq=1, reason=GameOverReason.LIVES, score=1),
    )
    text = events_to_jsonl(events)
    assert text == event_to_json(events[0]) + "\n" + event_to_json(events[1]) + "\n"


def test_jsonl_of_nothing_is_empty():
    assert events_to_jsonl(()) == ""


def test_nan_is_rejected():
    # Canonical JSON forbids NaN (EVENTS.md); a NaN reaching an event is a bug upstream, not a value to log.
    with pytest.raises(ValueError):
        event_to_json(GameOver(t=0, seq=0, reason=GameOverReason.TIME, score=float("nan")))
