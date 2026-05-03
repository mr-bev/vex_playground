from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from vex_sim import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vex_sim",
        description="Headless simulator for VEX EXP Python student programs.",
    )
    parser.add_argument("--version", action="version", version=f"vex_sim {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
