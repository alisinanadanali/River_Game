"""MODEL.md Appendix A re-checked with the engine's own functions (ROADMAP Phase 0).

    uv run python -m tools.design_calcs            # the appendix's sample sizes (≈ 2 min)
    uv run python -m tools.design_calcs --quick    # a tenth of them, wider tolerances

Each Check is one number the appendix prints (`appendix`, written as `text` on the MODEL.md line containing
`line`) next to the engine's value. Tolerances: config values and formulas to the appendix's rounding; Monte
Carlo values within 4 combined standard errors (ours and the appendix's own simulation) plus the rounding. The
exit code is 1 if any check is out of tolerance. tests/tools/test_design_calcs.py ties every `text` to MODEL.md.
"""

import argparse
import math
import sys
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from engine.actions import Actions
from engine.config import Config, build_config, deep_merge, load_config
from engine.donkey import Bag, Donkey, balance, classify_depth, effective_height, slip_probability
from engine.events import DepthState, WaveOrigin, WaveSpawned
from engine.evolve import evolve
from engine.rng import make_rngs
from engine.shrek import throw_sigma
from engine.state import new_game
from engine.step import step
from engine.stones import TempStone, initial_stones, sink_and_decay
from engine.world import build_world, draw_world_block

SIGMAS = 4                  # Monte Carlo tolerance in combined standard errors
APPENDIX_MAPS = 20_000      # A: "20 000 harita"
APPENDIX_TICKS = 120_000    # A: "120 000 tick'lik tek yörünge"
WARM_UP_TICKS = 500         # B(0) = μ: let the OU level and the waves reach their stationary mix first
BATCHES = 40                # batch means for the autocorrelated water level (OU 1/θ ≈ 12.5 ticks)
LOADED_EXTRA_KG = 60.0      # A: "eşek yüklü (200 + 60 kg)"
STEPS_A4 = 12               # A.4: "12 adımda ≥ 1 kayma" (one crossing)
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))  # M-01: 4-neighbourhood

A1_P = (0.45, 0.50, 0.55, 0.58, 0.62, 0.70)
A1_PATH = {0.45: 0.085, 0.50: 0.193, 0.55: 0.353, 0.58: 0.482, 0.62: 0.641, 0.70: 0.894}
A1_ROCKS = {
    0.50: (0.18, 0.43, 0.30, 0.07, 0.00),
    0.58: (0.48, 0.41, 0.10, 0.01, 0.00),
    0.62: (0.64, 0.32, 0.04, 0.00, 0.00),
    0.70: (0.90, 0.10, 0.00, 0.00, 0.00),
}
A1_STEPS = {0.45: 12.5, 0.50: 12.5, 0.55: 12.3, 0.58: 12.1, 0.62: 11.8, 0.70: 11.1}
A2_SETS = {  # set name → (config overrides, MODEL.md row marker, under water, KURU, BİLEK, DİZ, swept, mossy swept)
    "Prompt": (
        {"water": {"ou_sigma_cm": 1.5, "wave_rate_per_tick": 0.02}, "map": {"stone_base_h_cm": [5, 25]}},
        "| Prompt", (0.05, "%5"), (0.86, 0.11, 0.02, 0.009), 0.015,
    ),
    "Seçilen": ({}, "| **Seçilen", (0.21, "%21"), (0.61, 0.24, 0.115, 0.032), 0.058),
}
A3 = {1: (0.96, 0.87, 0.75), 3: (0.84, 0.72, 0.61), 5: (0.69, 0.58, 0.49), 7: (0.55, 0.47, 0.39), 9: (0.45, 0.38, 0.32)}
A3_MASSES = (10.0, 30.0, 50.0)
A4 = ((10, 0.048, 0.015, 0.024, 0.16), (50, 0.200, 0.090, 0.250, 0.68), (60, 0.231, 0.117, 0.330, 0.77))


@dataclass(frozen=True)
class Check:
    section: str        # "A.1" … "A.6"
    label: str          # what is compared, in Turkish (report text)
    appendix: float     # the appendix's number
    text: str           # how MODEL.md prints it
    line: str           # a substring of the MODEL.md line that prints it
    measured: float     # the engine's value
    tolerance: float

    @property
    def ok(self) -> bool:
        return abs(self.measured - self.appendix) <= self.tolerance


def tr(x: float, decimals: int) -> str:
    """A number as MODEL.md prints it: decimal comma."""
    return f"{x:.{decimals}f}".replace(".", ",")


def printed(x: float) -> str:
    """A table value written with as many decimals as the appendix gives it: 0.115 → '0,115', 0.24 → '0,24'."""
    return tr(x, len(repr(x).split(".")[1]))


def rounding(text: str) -> float:
    """Half a unit of the last printed digit: '0,193' → 0.0005, '%21' → 0.005, '9' → 0.5."""
    digits = text.lstrip("%≈ ").split(",")
    half = 0.5 * 10.0 ** -(len(digits[1]) if len(digits) == 2 else 0)
    return half / 100 if text.startswith("%") else half


def with_appendix_error(se: float, n: int, appendix_n: int) -> float:
    """Our standard error combined with the appendix's own, which came from appendix_n samples of the same kind:
    se² + se²·n/appendix_n."""
    return se * math.sqrt(1 + n / appendix_n)


def binomial_tol(p: float, n: int, appendix_n: int, text: str) -> float:
    """4 combined standard errors plus the rounding. A printed p stands for any value within its rounding, so the
    variance is taken at the end of that interval nearer 0.5 (a printed 0,00 is not a certain zero)."""
    h = rounding(text)
    q = min(p + h, 0.5) if p < 0.5 else max(p - h, 0.5)
    return SIGMAS * math.sqrt(q * (1 - q) * (1 / n + 1 / appendix_n)) + h


# --- A.1 percolation --------------------------------------------------------------------------------------------

def stone_path_steps(is_stone: np.ndarray) -> int | None:
    """Moves on the shortest stones-only crossing (bank → row 0 … row R−1 → bank), or None if there is none.

    The banks are walkable in every column (M-01), so the crossing may start and end in any column.
    """
    rows, cols = is_stone.shape
    dist = np.full(is_stone.shape, -1)
    queue = deque()
    for c in range(cols):
        if is_stone[0, c]:
            dist[0, c] = 1  # the move from the bank onto row 0
            queue.append((0, c))
    while queue:
        r, c = queue.popleft()
        if r == rows - 1:
            return int(dist[r, c]) + 1  # and the move onto the north bank
        for dr, dc in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and is_stone[nr, nc] and dist[nr, nc] < 0:
                dist[nr, nc] = dist[r, c] + 1
                queue.append((nr, nc))
    return None


def a1(base: Config, scale: float) -> list[Check]:
    n = max(100, int(APPENDIX_MAPS * scale))
    checks = []
    for p in A1_P:
        cfg = load_like(base, {"map": {"stone_density": p, "path_guarantee": "none"}}).map
        rngs = make_rngs(20261017)
        rocks, steps = [], []
        for _ in range(n):
            block, rngs = draw_world_block(rngs, cfg)
            world = build_world(block, cfg, seed=0, attempt=0)
            rocks.append(world.rocks_to_solve)
            if world.rocks_to_solve == 0:
                steps.append(stone_path_steps(world.is_stone))
        rocks = np.array(rocks)
        row = f"| {tr(p, 2)} |"
        text = tr(A1_PATH[p], 3)
        checks.append(Check("A.1", f"p = {tr(p, 2)}  P(kayasız yol)", A1_PATH[p], text, row, float(np.mean(rocks == 0)),
                            binomial_tol(A1_PATH[p], n, APPENDIX_MAPS, text)))
        for k, expected in enumerate(A1_ROCKS.get(p, ())):
            measured = float(np.mean(rocks >= 4) if k == 4 else np.mean(rocks == k))
            label = f"p = {tr(p, 2)}  P(kaya = {'≥4' if k == 4 else k})"
            text = tr(expected, 2)
            checks.append(Check("A.1", label, expected, text, row, measured, binomial_tol(expected, n, APPENDIX_MAPS, text)))
        s = np.array(steps, dtype=float)
        se = s.std(ddof=1) * math.sqrt(1 / len(s) + 1 / (APPENDIX_MAPS * A1_PATH[p]))
        text = tr(A1_STEPS[p], 1)
        checks.append(Check("A.1", f"p = {tr(p, 2)}  ort. en kısa yol (adım)", A1_STEPS[p], text, row, float(s.mean()),
                            SIGMAS * se + rounding(text)))
    return checks


# --- A.2 water and depth ----------------------------------------------------------------------------------------

def a2(base: Config, scale: float) -> list[Check]:
    ticks = max(BATCHES * 50, int(APPENDIX_TICKS * scale) // BATCHES * BATCHES)
    checks = []
    for name, (overrides, row, (under, under_text), tiers, mossy) in A2_SETS.items():
        cfg = load_like(base, {"time": {"game_length_ticks": ticks + WARM_UP_TICKS + 1}, **overrides})
        samples, waves = water_samples(cfg, ticks)
        means = samples.mean(axis=0)
        batch = samples.reshape(BATCHES, -1, samples.shape[1]).mean(axis=1)
        se = with_appendix_error(batch.std(axis=0, ddof=1) / math.sqrt(BATCHES), ticks, APPENDIX_TICKS)
        expected = (under, *tiers, mossy)
        texts = (under_text, *(printed(x) for x in (*tiers, mossy)))
        labels = ("boş taş su altında", "yüklü: KURU", "yüklü: BİLEK", "yüklü: DİZ", "yüklü: SÜRÜKLENME",
                  "yosunlu yüklü: SÜRÜKLENME")
        for label, e, text, m, s in zip(labels, expected, texts, means, se, strict=True):
            checks.append(Check("A.2", f"{name}: {label}", e, text, row, float(m), SIGMAS * float(s) + rounding(text)))
        if name == "Seçilen":
            per_game = base.time.game_length_ticks
            count = len(waves)
            rate = count / ticks * per_game
            checks.append(Check("A.2", "oyun başına dalga", 9.0, "9", "oyun başına ≈ 9 dalga", rate,
                                SIGMAS * math.sqrt(max(count, 1)) / ticks * per_game + rounding("9")))
            big = float(np.mean(np.array(waves) > 20.0))
            checks.append(Check("A.2", "P(A > 20 cm)", 0.19, "0,19", "P(A > 20 cm) ≈ 0,19", big,
                                binomial_tol(0.19, count, count, "0,19")))
    return checks


def water_samples(cfg: Config, ticks: int) -> tuple[np.ndarray, list[float]]:
    """Per tick after the warm-up: P(empty stone under water) and the loaded tier probabilities on a random stone
    (h ~ U[lo, hi], all columns), plus the upstream wave amplitudes born meanwhile.

    For h ~ U[lo, hi], P(d ≥ x) = P(h ≤ L + load/k − x) = clip((L + load/k − x − lo)/(hi − lo), 0, 1): no stone
    has to be drawn. Thresholds belong to the deeper state (D-04).
    """
    lo, hi = cfg.map.stone_base_h_cm
    d = cfg.donkey
    load = d.mass_kg + LOADED_EXTRA_KG
    sink, sink_mossy = load / cfg.map.stiffness_kg_per_cm, load / cfg.map.mossy_stiffness_kg_per_cm

    def deeper(level, sunk, x):
        return np.clip((level + sunk - x - lo) / (hi - lo), 0, 1).mean()

    state, rngs = new_game(cfg, 7)
    out = np.empty((ticks, 6))
    amplitudes = []
    for i in range(ticks + WARM_UP_TICKS):
        state, rngs, events = step(state, Actions(), rngs)
        if i < WARM_UP_TICKS:
            continue
        amplitudes += [e.amplitude for e in events if isinstance(e, WaveSpawned) and e.origin is WaveOrigin.UPSTREAM]
        level = state.water.level
        ankle, knee, swept = (deeper(level, sink, x) for x in (d.depth_ankle_cm, d.depth_knee_cm, d.depth_swept_cm))
        under = np.clip((level - lo) / (hi - lo), 0, 1).mean()
        out[i - WARM_UP_TICKS] = (under, 1 - ankle, ankle - knee, knee - swept, swept, deeper(level, sink_mossy, d.depth_swept_cm))
    return out, amplitudes


# --- A.3 throw, A.4 slip, A.5 items, A.6 rocks: formulas and config ------------------------------------------

def a3(base: Config, scale: float) -> list[Check]:
    sh = base.shrek
    checks = [
        exact("A.3", "σ₀", 0.2, "σ₀ = 0,2", sh.throw_sigma0_cells),
        exact("A.3", "σ₁ (hücre/satır)", 0.05, "σ₁ = 0,05", sh.throw_sigma_per_row_cells),
        exact("A.3", "σ₂ (hücre/kg)", 0.004, "σ₂ = 0,004", sh.throw_sigma_per_kg_cells),
        exact("A.3", "r (hücre)", 0.75, "r = 0,75", sh.catch_radius_cells),
    ]
    for distance, ps in A3.items():
        for mass, p in zip(A3_MASSES, ps, strict=True):
            sigma = throw_sigma(distance - 1, mass, sh)
            text = tr(p, 2)
            checks.append(Check("A.3", f"uzaklık {distance}, {mass:g} kg", p, text, f"| {distance} |",
                                p_catch(sigma, sh.catch_radius_cells), rounding(text)))
    prompt = sh.model_copy(update={"throw_sigma_per_row_cells": 0.1, "catch_radius_cells": 0.5})
    checks.append(Check("A.3", "prompt değerleriyle satır 5, karpuz", 0.14, "%14", "karpuz için %14",
                        p_catch(throw_sigma(4, 50.0, prompt), 0.5), rounding("%14")))
    return checks


def p_catch(sigma: float, r: float) -> float:
    """A.3: P(‖landing − target‖ ≤ r) for an isotropic 2-D Gaussian of standard deviation σ."""
    return 1 - math.exp(-r * r / (2 * sigma * sigma))


def a4(base: Config, scale: float) -> list[Check]:
    d = base.donkey
    checks = [exact("A.4", "κ", 2.0, "κ = 2", d.slip_kappa), exact("A.4", "p₀", 0.01, "p₀ = 0,01", d.slip_base_prob)]
    for kg, delta, p, p_moss, p12 in A4:
        donkey = Donkey(row=0, col=0, lives=1, bag_right=Bag(mass=float(kg)))  # all of it on one side
        got = balance(donkey, base)
        row = f"| {kg} kg |"
        p_got = slip_probability(got, 1.0, d)
        checks += [
            Check("A.4", f"{kg} kg: δ", delta, tr(delta, 3), row, got, rounding(tr(delta, 3))),
            Check("A.4", f"{kg} kg: p_slip", p, tr(p, 3), row, p_got, rounding(tr(p, 3))),
            Check("A.4", f"{kg} kg: yosunlu p_slip", p_moss, tr(p_moss, 3), row,
                  slip_probability(got, base.map.mossy_slip_multiplier, d), rounding(tr(p_moss, 3))),
            Check("A.4", f"{kg} kg: {STEPS_A4} adımda ≥ 1 kayma", p12, tr(p12, 2), row, 1 - (1 - p_got) ** STEPS_A4,
                  rounding(tr(p12, 2))),
        ]
    return checks


def a5(base: Config, scale: float) -> list[Check]:
    types = base.items.types.values()
    mean = lambda f: sum(t.prob * f(t) for t in types)  # noqa: E731
    per_game = base.items.arrival_rate_per_tick * base.time.game_length_ticks
    d = base.donkey
    return [
        Check("A.5", "yük başına kg", 24.0, "24 kg", "Yük başına", mean(lambda t: t.mass_kg), rounding("24")),
        Check("A.5", "yük başına hacim", 1.7, "1,7 hacim", "Yük başına", mean(lambda t: t.volume), rounding("1,7")),
        Check("A.5", "yük başına puan", 2.6, "2,6 puan", "Yük başına", mean(lambda t: t.points), rounding("2,6")),
        Check("A.5", "oyun başına yük", 30.0, "≈ 30 yük", "Yük başına", per_game, rounding("30")),
        Check("A.5", "puan potansiyeli", 78.0, "≈ 78 puan", "Yük başına", per_game * mean(lambda t: t.points),
              rounding("78")),
        exact("A.5", "heybe kg (taraf başına)", 60.0, "2 × 60 kg", d.bag_max_kg_per_side),
        exact("A.5", "heybe hacmi (taraf başına)", 4.0, "2 × 4 hacim", d.bag_max_volume_per_side),
    ]


def a6(base: Config, scale: float) -> list[Check]:
    sh = base.shrek
    life, dry = rock_lifetime(base)
    hard = load_config("hard").shrek
    return [
        exact("A.6", "doğuş yüksekliği (cm)", 20.0, "20 cm'de doğar", sh.rock_initial_h_cm),
        exact("A.6", "batma (cm/tick)", 1.0, "1 cm/tick batar", sh.rock_sink_cm_per_tick),
        exact("A.6", "ömür (tick)", 25.0, "ömür 25 tick", life),
        exact("A.6", "yüklü eşek KURU (motor, tick)", 14.0, "motor 14 verir", dry),
        exact("A.6", "cooldown (tick)", 15.0, "**15** tick", sh.rock_cooldown_ticks),
        exact("A.6", "iki taşın örtüşmesi (tick)", 10.0, "(10 tick örtüşme)", life - sh.rock_cooldown_ticks),
        exact("A.6", "prompt cooldown 20 ile örtüşme", 5.0, "yalnızca 5 tick", life - 20),
        exact("A.6", "hard: rock_max_active", 3.0, "`rock_max_active = 3`", hard.rock_max_active),
        exact("A.6", "hard: cooldown", 12.0, "cooldown 12", hard.rock_cooldown_ticks),
    ]


def rock_lifetime(cfg: Config) -> tuple[int, int]:
    """(ticks a fresh temporary stone exists, ticks a loaded donkey on it stays DRY in still water L = 0).

    S-07: the stone is born in step 2(d) and already sinks in that tick's step 6; depth is read in step 7.
    """
    sh, load = cfg.shrek, cfg.donkey.mass_kg + LOADED_EXTRA_KG
    stones = evolve(initial_stones(cfg), temp=(TempStone(id=0, row=0, col=0, h=sh.rock_initial_h_cm, spawned_at=0),))
    life = dry = 0
    still_dry = True
    while stones.temp:
        stones, _ = sink_and_decay(stones, sh)
        if not stones.temp:
            break
        life += 1
        depth = 0.0 - effective_height(stones.temp[0].h, load, sh.rock_stiffness_kg_per_cm)
        still_dry = still_dry and classify_depth(depth, cfg.donkey) is DepthState.DRY
        dry += still_dry
    return life, dry


# --- running and reporting --------------------------------------------------------------------------------------

def exact(section: str, label: str, appendix: float, text: str, measured: float) -> Check:
    """A config value or a count the appendix states; `text` is also the MODEL.md line marker."""
    return Check(section, label, appendix, text, text, float(measured), 1e-9)


def load_like(base: Config, overrides: dict) -> Config:
    """`base` with `overrides` deep-merged and validated again (the same path a profile takes)."""
    return build_config(deep_merge(base.model_dump(by_alias=True), overrides))


SECTIONS: dict[str, tuple[str, Callable[[Config, float], list[Check]]]] = {
    "A.1": ("Perkolasyon (9×9)", a1),
    "A.2": ("Su ve derinlik", a2),
    "A.3": ("Atış yakalama olasılığı", a3),
    "A.4": ("Kayma", a4),
    "A.5": ("Yük ekonomisi", a5),
    "A.6": ("Kaya ömrü", a6),
}


def run_checks(scale: float = 1.0, base: Config | None = None) -> list[Check]:
    base = base if base is not None else load_config()
    return [check for _, compute in SECTIONS.values() for check in compute(base, scale)]


def report(checks: list[Check]) -> str:
    lines = []
    for section, (title, _) in SECTIONS.items():
        lines.append(f"\n{section} {title}")
        lines.append(f"  {'':44} {'Ek A':>8} {'motor':>9} {'tolerans':>9}")
        for c in (c for c in checks if c.section == section):
            mark = "✓" if c.ok else "✗"
            lines.append(f"  {c.label:44} {c.text:>8} {_num(c.measured):>9} {'±' + _num(c.tolerance):>9}  {mark}")
    failed = sum(not c.ok for c in checks)
    lines.append(f"\n{len(checks) - failed}/{len(checks)} uyumlu" + (f", {failed} uyumsuz" if failed else ""))
    lines.append("Yeniden hesaplanmayanlar (bot gerektirir, Faz 3): dalgaları yok sayan eşeğin can kaybı (A.2), "
                 "tur süresi ve tur başına yük (A.5).")
    return "\n".join(lines)


def _num(x: float) -> str:
    return tr(x, 4).rstrip("0").rstrip(",") if abs(x) < 1000 else tr(x, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.design_calcs", description="MODEL.md Ek A, motorla yeniden")
    parser.add_argument("--quick", action="store_true", help="örneklemlerin onda biri; toleranslar daha geniş")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    checks = run_checks(0.1 if args.quick else 1.0)
    print(report(checks))
    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
