from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from vex_sim import __version__, runner
from vex_sim.playgrounds import EMPTY_ROOM, get_playground


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
    mode = run_p.add_mutually_exclusive_group()
    mode.add_argument(
        "--headless",
        dest="render",
        action="store_false",
        help=(
            "Run without a display (default). The call log and JSON result "
            "are emitted exactly as before."
        ),
    )
    mode.add_argument(
        "--render",
        dest="render",
        action="store_true",
        help="After the run, open a pygame window and play back the recorded trajectory.",
    )
    run_p.set_defaults(render=False)
    run_p.add_argument(
        "--playground",
        default=EMPTY_ROOM.name,
        help=f"Playground name. Default: {EMPTY_ROOM.name}.",
    )
    run_p.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier for --render. Default: 1.0 (real-time).",
    )

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    playground = get_playground(args.playground)

    if args.render:
        # Lazy import so headless installations don't pull pygame.
        from vex_sim import render

        result = render.run_live(
            args.student_file,
            max_time=args.max_time,
            playground=playground,
            speed=args.speed,
        )
    else:
        result = runner.run(args.student_file, max_time=args.max_time, playground=playground)

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
