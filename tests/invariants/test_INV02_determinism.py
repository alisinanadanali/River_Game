"""INV-02: same seed + same actions -> bit-identical states, streams and event stream (example tests).

The walking skeleton emits few events, so today these tests mostly watch the clock and the streams. They need no
change as rules are added: every new event and state field is automatically inside what they compare.
The property-based version (random seeds and actions) is test_INV02_determinism_property.py.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from engine.config import load_config

from tests.support import run, scripted_actions

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config()
GAME = scripted_actions(CFG.time.game_length_ticks)  # one full game


def test_two_runs_give_identical_bytes():
    a = run(CFG, 42, GAME)
    b = run(CFG, 42, GAME)
    assert a.jsonl == b.jsonl
    assert a.states == b.states and a.rngs == b.rngs


def test_the_log_is_not_empty():
    # Guards the test above: two empty logs are trivially identical.
    log = run(CFG, 42, GAME).jsonl
    assert b'"type":"WaveSpawned"' in log and log.endswith(b'"type":"GameOver"}\n')


@pytest.mark.parametrize("profile", ["warmup", "percolation_edge", "hard"])
def test_every_profile_is_deterministic(profile):
    cfg = load_config(profile)
    assert run(cfg, 7, GAME).digest() == run(cfg, 7, GAME).digest()


def test_continuing_from_a_saved_tick_gives_the_same_rest():
    # ADR-011: (state, rngs) after tick k is all the future depends on. Branching (MCTS, critical moments)
    # is just stepping again from that pair.
    k = 100
    full = run(CFG, 42, GAME)
    rest = run(CFG, 42, GAME[k:], start=(full.states[k - 1], full.rngs[k - 1]))
    assert rest.states == full.states[k:] and rest.rngs == full.rngs[k:]
    assert rest.events == tuple(e for e in full.events if e.t >= k)


def test_other_seed_other_streams():
    # Guards against an engine that ignores its seed (which would be deterministic too).
    assert run(CFG, 1, GAME[:5]).rngs != run(CFG, 2, GAME[:5]).rngs


DIGEST_SCRIPT = """
from engine.config import load_config
from tests.support import run, scripted_actions
cfg = load_config()
print(run(cfg, 42, scripted_actions(cfg.time.game_length_ticks)).digest())
"""


def test_same_digest_in_fresh_processes_with_different_hash_seeds():
    # A fresh interpreter catches state hidden in the process (module globals, caches); a different
    # PYTHONHASHSEED catches anything that depends on set/dict-of-str iteration order.
    digests = set()
    for hash_seed in ("0", "1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        out = subprocess.run(
            [sys.executable, "-c", DIGEST_SCRIPT], cwd=ROOT, env=env, capture_output=True, text=True, check=True
        )
        digests.add(out.stdout.strip())
    digests.add(run(CFG, 42, GAME).digest())
    assert len(digests) == 1, digests
