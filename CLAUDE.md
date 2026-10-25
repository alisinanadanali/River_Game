**Dependency rule (ADR-005): `engine/` never imports from `render/`, `controllers/`, `envs/`, `logs/`, `tools/` or `game/`. Outer layers depend on the engine, never the reverse; nothing but `main.py` imports `game/`.**

# Nehir Geçidi (River Crossing)

Two-player local co-op game (Shrek on the bank, Donkey on the stones) that doubles as a learning sandbox for
stochastic processes (OU, Poisson, percolation, Markov chains) and decision/learning algorithms (value iteration,
A*, MCTS, Q-learning, PPO, MAPPO, behaviour cloning, SA/GA balancing). The same engine is played by humans
(pygame-ce) and by RL agents (Gymnasium / PettingZoo).

## Units
Height **cm**, mass **kg**, time **tick**. Config keys carry the unit as a suffix (`_cm`, `_kg`, `_ticks`,
`_per_tick`, `_cells`; render keys, on the wall clock and the screen: `_s`, `_px`, `_deg`, `_hz`). Rows: −1 = south
bank (Shrek), 0…R−1 river, R = north bank (delivery). Columns 0…C−1, water flows west → east.

## Workflow
1. **Document** – the rule lives in `docs/MODEL.md` with a rule ID (`M-`, `W-`, `D-`, `S-`, `I-`, `R-`), its
   order in `docs/TICK.md`, its events in `docs/EVENTS.md`.
2. **Test** – write `tests/rules/test_<RULEID>_<what>.py` (e.g. `test_W05_dam_release_volume.py`) and, where it
   applies, an invariant in `tests/invariants/` (hypothesis). See MODEL.md §8 (INV-01…INV-08).
3. **Code** – implement until the test passes. A rule change without a doc change is a bug.

Changing the tick order or any ADR decision requires a new/updated ADR in `docs/adr/`.

## Doc map
| File | What it answers |
|---|---|
| `docs/GLOSSARY.md` | Turkish UI term ↔ English identifier ↔ definition ↔ unit. Add new terms here first. |
| `docs/ENTITIES.md` | State objects, fields, units, ranges; item and donkey state machines |
| `docs/MODEL.md` | Formal Markov game, all rules with IDs, invariants, design calculations (Appendix A) |
| `docs/TICK.md` | The 12-step pipeline, RNG usage per step, ordering rationale |
| `docs/EVENTS.md` | Event catalogue, fields, emitting step, consumers; log header |
| `docs/CONTROLS.md` | Scancode keymaps, input buffer, tactical mode, ghosting test |
| `docs/METRICS.md` | Team score, Harmony report (Uyum raporu), critical moments, RL reward templates |
| `docs/VISUALS.md` | Oblique projection, colour-blind-safe safety-margin scale, layout, HUD, debug overlay, characters (§9) |
| `docs/ROADMAP.md` | Phases 0–5 with acceptance criteria; target directory layout |
| `docs/adr/` | ADR-001…ADR-012 |
| `config/default.yaml` | Every model parameter, with unit and valid range |
| `config/profiles/` | `warmup`, `percolation_edge` (default), `hard`: diffs only, deep-merged |

## Coding rules
- **No magic numbers.** Every model number comes from validated config (pydantic v2, unknown keys rejected,
  ADR-008). Derived quantities (e.g. `q_in = downstream_drop_cm * wave_speed_cols_per_tick`) are computed in
  code, not stored. Structural constants (RNG block sizes, R-02) are named module constants documented in MODEL.md.
- **Pure step.** `step(state, actions, rngs) -> (new_state, new_rngs, events)` (ADR-011); immutable state (frozen dataclasses,
  copied numpy arrays); no I/O, no globals, no wall-clock time inside `engine/`. Single exception:
  `engine/config.py:load_config` reads the YAML files once at start-up; `step` and state code never do I/O.
- **RNG streams.** Only the five streams from `SeedSequence(seed).spawn(5)`: `rng_world`, `rng_water`,
  `rng_items`, `rng_throw`, `rng_slip` (ADR-006). Action-dependent streams draw fixed-size blocks every tick.
  Never create an RNG elsewhere; never use `random` or `np.random.*` global functions.
- **Events are the only output channel.** Render, logs, rewards and metrics consume events (+ read-only state).
  Never compute a reward inside the engine (ADR-009). New/changed event ⇒ bump `event_schema_version`.
- **Rule IDs in code.** Each function implementing a rule cites it in its docstring (`"""W-04: dam accumulation."""`).
- **Language.** Code, identifiers, comments, commit messages: English. UI strings: Turkish, kept in one strings
  module. Design docs are Turkish (ADR-007).
- **Controllers** implement `act(observation) -> action`; the keyboard is just one controller.
- Python 3.12, numpy, pygame-ce (render only), pyyaml + pydantic v2, pytest + hypothesis; managed with uv.

## Commands (from Phase 0 on)
```
uv sync                               # install
uv run pytest                         # all tests, hypothesis profile `dev` (fast)
uv run pytest --hypothesis-profile=full  # ROADMAP acceptance (>= 200 seeds); before a push, with -m perf below
                                      # (any shell; the env var HYPOTHESIS_PROFILE=full does the same)
uv run pytest tests/rules -k W05      # one rule
uv run python -m tools.tactical_cli --seed 42 --profile percolation_edge
uv run python -m tools.design_calcs   # re-check MODEL.md Appendix A
uv run python -m tools.bench --stages # speed: µs/tick and ticks/s, per TICK.md step (ROADMAP >= 5 000 ticks/s)
uv run python -m tools.cvd_shots      # VISUALS §3: colour-blindness screenshots into runs/cvd/
uv run pytest -m perf                 # the speed guard; not in the default run, run it before a push
uv run python main.py                 # Phase 1: pygame-ce game
```

## Current phase
Phase 0 closed: `v0.1.0` (2026-10-24; acceptance table in `docs/ROADMAP.md`). The engine: `engine/step.py`
pipeline (13 stages, TICK.md), rules in `world.py`, `water.py`, `validation.py`, `shrek.py`, `donkey.py`,
`stones.py`, `items.py`, `catching.py` (imports one-way: items ← donkey ← catching), state copies with
`evolve.py`, controllers see `observe.py` (whole state minus `world.seed` and projectile landings). Tools:
`tactical_cli` (text tactical mode, CONTROLS.md §5.1), `design_calcs` (MODEL Appendix A, 96 checks), `bench`
(≈ 7 600 ticks/s; ADR-011). The version lives in `pyproject.toml` and `engine.ENGINE_VERSION` (tested equal);
event schema 1 is frozen and fingerprinted (`tests/engine/test_version.py`): an event change bumps
`EVENT_SCHEMA_VERSION`. Phase 1 started with the characters (VISUALS §9, ADR-012): `render/characters/` —
`pose.py` (pure clips), `animator.py` (pure clip state machine: loops from the state, one-shots from events),
`sprites.py` (pygame: local images from `assets/private/`, never in git, or the fallback shape) — plus
`render/interpolation.py`, `render/strings_tr.py` (all UI strings, the tools' too; an AST test keeps every
string with a Turkish letter there, VISUALS §7), `render/fonts.py` (committed Noto fonts in `assets/fonts/`,
hashes in VISUALS §7) and `tools/character_preview.py` (`--bench`
≈ 240 µs/frame). `tests/render/test_render_imports.py` guards render/'s imports (ADR-005 update). Next: the
Phase 1 micro-steps (ROADMAP); 1.0 (fonts + strings) done; 1.1 done: `controllers/keyboard.py` (pure input
buffer, CONTROLS §4.1: scancode events in, `tick_actions` at the boundary; no pygame, guarded by
`tests/controllers/test_controllers_imports.py`); 1.2 done: `controllers/tactical.py` (pure tactical
confirm, CONTROLS §5.2: Shrek selects move/aim, an ability or the wait key confirms; a confirmation is
final); 1.3 done: `game/session.py` (pure loop state, CONTROLS §7: `frame(session, key_events, now_s)`, fixed-step
clock with at most one real-time tick a frame and the backlog dropped, F1/Esc/F2/F5, game over; `ticks` records
actions + events; nothing imports `game/`, `tests/game/test_game_imports.py`); 1.4 done: walking skeleton — `main.py` (pygame
shell, CONTROLS §7.1: events → `KeyDown`/`KeyUp`/`FocusLost`, `--seed`/`--profile`/`--frames`, tested on the dummy
driver with a fake clock), `game/view.py` (pure: animators follow the ticks, `scene()`), `render/layout.py` (pure flat
board, VISUALS §4.1), `render/scene.py` (pure texts), `render/draw.py`; 1.5 done: oblique board (VISUALS §2: z on the engine's scale, `layout.z_room_cm`/`bank_z_cm`/
`front_shade`; `render/board.py` pure heights, water polygons, prisms; rows drawn back to front with the characters;
≈ 1 450 µs/frame); 1.6 done: safety-margin colours + patterns (VISUALS §3: `render/colour.py` pure, Machado 2009
CVD simulation + CIE76 ΔE ≥ 10 in `tests/render/test_colour.py`; under water the patterns carry the tiers; mossy and
temporary-stone marks; `uv run python -m tools.cvd_shots` → `runs/cvd/`; ≈ 1 780 µs/frame); 1.7 done: characters in the
water (VISUALS §4.1: `layout.water_line`, the donkey cut `d · px_per_cm` above its feet with `d` interpolated, a dry
stone's `d < 0` kept; a swept donkey (a life less) does not slide back; `scene.Ghost` on the swept cell, drawn with
its row). Next 1.8 (HUD).
