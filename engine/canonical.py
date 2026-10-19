"""Canonical JSON (EVENTS.md): one byte string per value, shared by config_hash and the event log.

Keys sorted, separators "," and ":" without spaces, UTF-8 text kept as is, NaN and infinities refused.
"""

import json


def canonical_json(value) -> str:
    """EVENTS.md canonical JSON of `value` (dicts, lists, str, int, float, bool, None)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
