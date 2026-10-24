"""Text tactical mode (CONTROLS.md §5.1). Thin terminal shell around tools/tactical.py.

    uv run python -m tools.tactical_cli --seed 42 --profile percolation_edge

Each tick the donkey and then Shrek type one line; ? shows the keys, :q quits.
"""

import argparse
import sys

from engine.config import load_config
from engine.world import MapGenerationError
from tools.tactical import play


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.tactical_cli", description="Nehir Geçidi, metin taktik modu")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--profile", default=None, help="config/profiles/<ad>.yaml; verilmezse default.yaml")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # Turkish letters and map glyphs on any console code page
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        config = load_config(args.profile)
        play(config, args.seed, input, print)
    except (ValueError, MapGenerationError) as error:
        parser.exit(2, f"hata: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
