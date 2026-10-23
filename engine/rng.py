"""Random streams as values (R-01, R-02, ADR-006, ADR-011).

Each stream's PCG64 state is a frozen StreamState. A draw rebuilds a Generator from that state, lets the caller
draw from it, and returns the result with a new Rngs; the Generator never outlives the call and the input
Rngs is never changed, so equal inputs always give equal outputs.
"""

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import numpy as np

from engine.evolve import evolve

THROW_BLOCK = 2  # R-02: standard normals drawn from rng_throw every tick
SLIP_BLOCK = 4   # R-02: uniforms drawn from rng_slip every tick (slip, slip side, knee drop, drop side)

T = TypeVar("T")


@dataclass(frozen=True)
class StreamState:
    """Complete PCG64 state: 128-bit state and increment, plus the buffered half of a 64-bit word."""

    state: int
    inc: int
    has_uint32: int
    uinteger: int


@dataclass(frozen=True)
class Rngs:
    world: StreamState  # M-02, M-03, M-05
    water: StreamState  # W-01, W-02
    items: StreamState  # I-01
    throw: StreamState  # S-04
    slip: StreamState   # D-02, D-03, D-06


STREAMS = tuple(f.name for f in dataclasses.fields(Rngs))  # R-01 spawn order = Rngs field order, one source


def make_rngs(seed: int) -> Rngs:
    """R-01: the five streams for a master seed (a non-negative integer)."""
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise TypeError(f"seed must be a non-negative integer, got {type(seed).__name__}")
    if seed < 0:
        raise ValueError(f"seed must be non-negative, got {seed}")
    children = np.random.SeedSequence(int(seed)).spawn(len(STREAMS))
    return Rngs(**{name: _state_of(np.random.PCG64(child)) for name, child in zip(STREAMS, children, strict=True)})


def draw(rngs: Rngs, stream: str, f: Callable[[np.random.Generator], T]) -> tuple[T, Rngs]:
    """ADR-011: `f(generator)` on one stream; returns its result and the Rngs with only that stream advanced.

    `f` must not keep the generator: drawing from it later would not be seen by any Rngs.
    """
    if stream not in STREAMS:
        raise ValueError(f"unknown stream {stream!r}; expected one of {STREAMS}")
    bit_generator = _pcg64(getattr(rngs, stream))
    result = f(np.random.Generator(bit_generator))
    return result, evolve(rngs, **{stream: _state_of(bit_generator)})


def draw_blocks(rngs: Rngs) -> tuple[np.ndarray, np.ndarray, Rngs]:
    """R-02 (TICK.md step 0): the fixed per-tick blocks, drawn whether or not they are used.

    Returns (u_throw[THROW_BLOCK] standard normals, u_slip[SLIP_BLOCK] uniforms in [0, 1), new Rngs).
    The blocks are read-only.
    """
    u_throw, rngs = draw(rngs, "throw", lambda g: g.standard_normal(THROW_BLOCK))
    u_slip, rngs = draw(rngs, "slip", lambda g: g.random(SLIP_BLOCK))
    u_throw.flags.writeable = False
    u_slip.flags.writeable = False
    return u_throw, u_slip, rngs


def _state_of(bit_generator: np.random.PCG64) -> StreamState:
    s = bit_generator.state
    return StreamState(s["state"]["state"], s["state"]["inc"], s["has_uint32"], s["uinteger"])


def _pcg64(stream: StreamState) -> np.random.PCG64:
    bit_generator = np.random.PCG64(0)  # placeholder seed, overwritten at once by the stored state
    bit_generator.state = {
        "bit_generator": "PCG64",
        "state": {"state": stream.state, "inc": stream.inc},
        "has_uint32": stream.has_uint32,
        "uinteger": stream.uinteger,
    }
    return bit_generator
