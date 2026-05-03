from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from vex_sim import __version__, runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vex_sim",
        description="Headless simulator for VEX EXP Python student programs.",
    )
    parser.add_argument("--version", action="version", version=f"vex_sim {__version__}")

    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser(
        "run",
        help="Execute a student program and dump the call log as JSON.",
    )
    run_p.add_argument("student_file", type=Path, help="Path to the student .py file.")
    run_p.add_argument(
        "--max-time",
        type=float,
        default=30.0,
        help="Maximum simulated time (seconds) before the run is terminated. Default: 30.",
    )
    run_p.add_argument(
        "--out",
        default="-",
        help="Output path for the JSON result. '-' (default) writes to stdout.",
    )

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    result = runner.run(args.student_file, max_time=args.max_time)
    out_text = json.dumps(result, indent=2)
    if args.out == "-":
        sys.stdout.write(out_text + "\n")
    else:
        Path(args.out).write_text(out_text, encoding="utf-8")
    return 1 if result["status"] == "error" else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
