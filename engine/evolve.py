"""evolve: dataclasses.replace for the engine's frozen dataclasses, about three times faster (ROADMAP Phase 0 speed).

dataclasses.replace runs __init__ again; a tick makes some thirty such copies. evolve copies the instance
dictionary instead. It only suits plain frozen dataclasses without __post_init__ or __slots__, which is what the
engine's state, tick and stream values are. Field names are checked, so a typo fails instead of adding an
attribute that __eq__ would never look at.
"""

from typing import TypeVar

T = TypeVar("T")


def evolve(obj: T, **changes) -> T:
    """A copy of the frozen dataclass `obj` with `changes` applied; `obj` itself is not changed."""
    fields = type(obj).__dataclass_fields__
    if not fields.keys() >= changes.keys():
        raise TypeError(f"{type(obj).__name__} has no field(s) {sorted(changes.keys() - fields.keys())}")
    new = object.__new__(type(obj))
    new.__dict__.update(obj.__dict__)
    new.__dict__.update(changes)
    return new
