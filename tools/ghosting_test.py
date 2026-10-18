"""Ghosting test window (CONTROLS.md §6). Thin pygame-ce shell around tools/ghosting.py.

    uv run python -m tools.ghosting_test --layout default   # then --layout alt

Hold each combination until the bar fills (pass). F2 marks it failed, Esc quits.
The result table is printed to the terminal on exit.
"""

import argparse

import pygame

from tools.ghosting import COMBOS, LAYOUTS, HoldTracker, Result, combo_scancodes, evaluate, load_keymaps, results_table

WINDOW_PX = (960, 540)
FPS = 60
GREEN, RED, GREY, WHITE, BG = (60, 170, 90), (200, 70, 60), (90, 90, 100), (235, 235, 235), (25, 25, 32)

# UI strings (Turkish, ADR-007). Move to the strings module once render/ exists.
TITLE = "Ghosting testi"
HINT = "Tuşları çubuk dolana kadar basılı tut  ·  F2: başarısız  ·  Esc: çık"
RELEASE = "Tüm tuşları bırak…"
DONE = "Bitti. Sonuç tablosu terminalde."
HELD = "Basılı scancode'lar:"


def key_labels(combo, keymaps, layout):
    """(label, scancode) per required key, for display."""
    shrek = keymaps[LAYOUTS[layout]]
    return [(f"Eşek {a}", keymaps["donkey"][a]) for a in combo.donkey] + [
        (f"Shrek {a}", shrek[a]) for a in combo.shrek
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--layout", choices=sorted(LAYOUTS), default="default")
    layout = parser.parse_args().layout

    keymaps = load_keymaps()
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_PX)
    pygame.display.set_caption(f"{TITLE} ({layout})")
    font, big = pygame.font.Font(None, 30), pygame.font.Font(None, 44)
    clock = pygame.time.Clock()

    held: set[int] = set()
    names: dict[int, str] = {}       # scancode -> key name, learned from KEYDOWN events
    results: list[Result] = []
    index, armed = 0, True           # armed: previous combo's keys have all been released
    tracker = HoldTracker()
    fewest_missing = None            # best attempt so far, recorded if F2 marks a failure

    def finish(ok: bool, missing: frozenset[int]) -> None:
        nonlocal index, armed, tracker, fewest_missing
        results.append(Result(COMBOS[index].id, ok, missing))
        index, armed, tracker, fewest_missing = index + 1, False, HoldTracker(), None

    running = True
    while running:
        now = pygame.time.get_ticks()
        done = index >= len(COMBOS)
        required = frozenset() if done else combo_scancodes(COMBOS[index], keymaps, layout)

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN:
                held.add(event.scancode)
                names[event.scancode] = pygame.key.name(event.key)
                if event.key == pygame.K_F2 and armed and not done:
                    finish(False, required if fewest_missing is None else fewest_missing)
            elif event.type == pygame.KEYUP:
                held.discard(event.scancode)
            elif event.type == pygame.WINDOWFOCUSLOST:
                held.clear()         # KEYUPs are lost while unfocused; avoid stuck keys

        if not armed and not held:
            armed = True
        if armed and not done:
            ok, missing = evaluate(held, required)
            if held & required and (fewest_missing is None or len(missing) < len(fewest_missing)):
                fewest_missing = missing
            if tracker.update(ok, now):
                finish(True, frozenset())

        screen.fill(BG)
        if index >= len(COMBOS):
            screen.blit(big.render(DONE, True, WHITE), (40, 40))
        else:
            combo = COMBOS[index]
            screen.blit(big.render(f"{index + 1}/{len(COMBOS)}  {combo.id}", True, WHITE), (40, 30))
            screen.blit(font.render(combo.reason, True, WHITE), (40, 80))
            for i, (label, code) in enumerate(key_labels(combo, keymaps, layout)):
                rect = pygame.Rect(40 + i * 220, 130, 200, 90)
                pygame.draw.rect(screen, GREEN if code in held else RED, rect, border_radius=8)
                screen.blit(font.render(label, True, WHITE), (rect.x + 10, rect.y + 15))
                screen.blit(font.render(f"{code}  {names.get(code, '')}", True, WHITE), (rect.x + 10, rect.y + 50))
            bar = pygame.Rect(40, 250, 880, 30)
            pygame.draw.rect(screen, GREY, bar, border_radius=6)
            filled = bar.copy()
            filled.width = int(bar.width * tracker.progress(now))
            pygame.draw.rect(screen, GREEN, filled, border_radius=6)
            if not armed:
                screen.blit(font.render(RELEASE, True, WHITE), (40, 295))
        held_text = ", ".join(f"{c} {names.get(c, '')}" for c in sorted(held))
        screen.blit(font.render(f"{HELD} {held_text}", True, WHITE), (40, 440))
        screen.blit(font.render(HINT, True, GREY), (40, 490))
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    print(results_table(layout, results))


if __name__ == "__main__":
    main()
