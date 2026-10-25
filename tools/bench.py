"""Speed of the engine (ROADMAP Phase 0: >= 5 000 ticks/s on one core; ADR-011).

    uv run python -m tools.bench              # 3 000 ticks x 5 repeats per scenario, default config
    uv run python -m tools.bench --stages     # also µs per TICK.md step
    uv run python -m tools.bench --profile hard

Scenarios: every tick NOOP; random actions (fixed seed, every component; the kind of play the invariants use);
the RL loop (random actions, then observe for both roles). A finished game is replaced by the next seed's. Each
repeat replays the same games; the fastest repeat is reported, since interference only ever adds time. Exit
code 1 if random play is slower than the ROADMAP line.
"""

import argparse
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import Config, load_config
from engine.events import Role
from engine.observe import observe
from engine.rng import Rngs
from engine.state import GameState, new_game
from engine.step import PIPELINE, GameFinishedError, step
from engine.tick import Tick
from render.strings_tr import decimal, tr

ROADMAP_TICKS_PER_S = 5_000  # ROADMAP Phase 0 acceptance
ROLES = (Role.DONKEY, Role.SHREK)
Clock = Callable[[], float]


@dataclass(frozen=True)
class Result:
    us_per_tick: float  # the fastest repeat
    ticks: int
    games: int

    @property
    def ticks_per_s(self) -> float:
        return 1e6 / self.us_per_tick


def random_actions(n: int, seed: int) -> list[Actions]:
    """n ticks of uniformly random actions for both players, from a numpy generator seeded with `seed`."""
    g = np.random.default_rng(seed)
    donkey, move, aim, ability = (list(e) for e in (DonkeyAction, ShrekMove, Aim, Ability))
    picks = g.integers(0, [len(donkey), len(move), len(aim), len(ability)], size=(n, 4))
    return [Actions(donkey=donkey[d], shrek=ShrekAction(move=move[m], aim=aim[a], ability=ability[b])) for d, m, a, b in picks]


def measure(config: Config, actions: list[Actions], *, repeats: int, roles: int = 0, clock: Clock = time.perf_counter,
            clock_factory: Callable[[], Clock] | None = None) -> Result:
    """µs per tick of step (and of observe for the first `roles` roles), the fastest of `repeats` runs.

    Each call is timed on its own, so building new games between them is not counted.
    """
    best, games = float("inf"), 0
    for _ in range(repeats):
        now = clock_factory() if clock_factory is not None else clock
        seed, games, spent = 0, 1, 0.0
        state, rngs = new_game(config, seed)
        for tick_actions in actions:
            if state.game_over is not None:
                seed, games = seed + 1, games + 1
                state, rngs = new_game(config, seed)
            t0 = now()
            state, rngs, _ = step(state, tick_actions, rngs)
            spent += now() - t0
            for role in ROLES[:roles]:
                t0 = now()
                observe(state, role)
                spent += now() - t0
        best = min(best, spent / len(actions) * 1e6)
    return Result(us_per_tick=best, ticks=len(actions), games=games)


def timed_step(state: GameState, actions: Actions, rngs: Rngs, totals: list[float],
               clock: Clock = time.perf_counter) -> tuple[GameState, Rngs, tuple]:
    """step, stage by stage, adding each stage's seconds to totals[i] (tests check it equals step)."""
    if state.game_over is not None:
        raise GameFinishedError(f"game ended at t={state.t}")
    tick = Tick(state=state, actions=actions, rngs=rngs, t=state.t)
    for i, stage in enumerate(PIPELINE):
        t0 = clock()
        tick = stage(tick)
        totals[i] += clock() - t0
    return tick.state, tick.rngs, tick.events


def stage_labels() -> list[str]:
    """' 5: water' for each PIPELINE stage, from its docstring ("TICK.md step 5: water. Rules: …")."""
    labels = []
    for stage in PIPELINE:
        m = re.match(r"TICK\.md step (\d+): ([^.]+)\.", stage.__doc__ or "")
        labels.append(f"{int(m[1]):>2}: {m[2]}")
    return labels


def stage_times(config: Config, actions: list[Actions], clock: Clock = time.perf_counter) -> list[float]:
    """µs per tick spent in each PIPELINE stage over one pass of `actions`."""
    totals = [0.0] * len(PIPELINE)
    seed = 0
    state, rngs = new_game(config, seed)
    for tick_actions in actions:
        if state.game_over is not None:
            seed += 1
            state, rngs = new_game(config, seed)
        state, rngs, _ = timed_step(state, tick_actions, rngs, totals, clock)
    return [s / len(actions) * 1e6 for s in totals]


def _rate(x: float) -> str:
    return tr("{x:,.0f}", x=x).replace(",", " ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.bench", description="Motor hızı (ROADMAP: ≥ 5 000 tick/sn)")
    parser.add_argument("--ticks", type=int, default=3000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--stages", action="store_true", help="TICK.md adımı başına süre")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    config = load_config(args.profile)
    played = random_actions(args.ticks, seed=0)
    noop = measure(config, [Actions()] * args.ticks, repeats=args.repeats)
    rand = measure(config, played, repeats=args.repeats)
    rl = measure(config, played, repeats=args.repeats, roles=len(ROLES))
    ok = rand.ticks_per_s >= ROADMAP_TICKS_PER_S
    print(f"Hız (config: {args.profile or 'default'}, {args.ticks} tick × {args.repeats} tekrar, en hızlısı)")
    print(f"  boş eylem       {decimal(noop.us_per_tick, 1):>7} µs/tick  {_rate(noop.ticks_per_s):>7} tick/sn")
    print(f"  rastgele eylem  {decimal(rand.us_per_tick, 1):>7} µs/tick  {_rate(rand.ticks_per_s):>7} tick/sn"
          f"   ROADMAP ≥ {_rate(ROADMAP_TICKS_PER_S)} tick/sn {'✓' if ok else '✗'}")
    print(f"  RL döngüsü      {decimal(rl.us_per_tick, 1):>7} µs/tick  {_rate(rl.ticks_per_s):>7} tick/sn   (step + iki rol için observe)")
    print(f"  ({rand.games} oyun)")
    if args.stages:
        times = stage_times(config, played)
        total = sum(times)
        print("\nTICK.md adımı başına (rastgele eylem, tek geçiş):")
        for label, us in zip(stage_labels(), times, strict=True):
            print(f"  {label:<24} {decimal(us, 1):>6} µs  {'%' + decimal(100 * us / total, 1):>6}")
        print(f"  {'toplam':<24} {decimal(total, 1):>6} µs")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
