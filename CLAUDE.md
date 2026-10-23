**Dependency rule (ADR-005): `engine/` never imports from `render/`, `controllers/`, `envs/`, `logs/` or `tools/`. Outer layers depend on the engine, never the reverse.**

# Nehir Geçidi (River Crossing)

Two-player local co-op game (Shrek on the bank, Donkey on the stones) that doubles as a learning sandbox for
stochastic processes (OU, Poisson, percolation, Markov chains) and decision/learning algorithms (value iteration,
A*, MCTS, Q-learning, PPO, MAPPO, behaviour cloning, SA/GA balancing). The same engine is played by humans
(pygame-ce) and by RL agents (Gymnasium / PettingZoo).

## Units
Height **cm**, mass **kg**, time **tick**. Config keys carry the unit as a suffix (`_cm`, `_kg`, `_ticks`,
`_per_tick`, `_cells`). Rows: −1 = south bank (Shrek), 0…R−1 river, R = north bank (delivery). Columns
0…C−1, water flows west → east.

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
| `docs/VISUALS.md` | Oblique projection, colour-blind-safe safety-margin scale, layout, HUD, debug overlay |
| `docs/ROADMAP.md` | Phases 0–5 with acceptance criteria; target directory layout |
| `docs/adr/` | ADR-001…ADR-011 |
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
HYPOTHESIS_PROFILE=full uv run pytest # ROADMAP acceptance (>= 200 seeds); before a push
uv run pytest tests/rules -k W05      # one rule
uv run python -m tools.tactical_cli --seed 42 --profile percolation_edge
uv run python -m tools.design_calcs   # re-check MODEL.md Appendix A
uv run python main.py                 # Phase 1: pygame-ce game
```

## Current phase
Phase 0 in progress (see `docs/ROADMAP.md`). Done: toolchain, ghosting test, INV-07, config, RNG, walking
skeleton (`engine/step.py` pipeline + INV-02), world generation (`engine/world.py`, M-01 … M-05).
Next: water (W-01 … W-07).
