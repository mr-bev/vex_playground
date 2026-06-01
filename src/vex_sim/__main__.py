from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from vex_sim import __version__, runner
from vex_sim.playgrounds import EMPTY_ROOM, PLAYGROUNDS, get_playground
from vex_sim.scenario import run_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vex_sim",
        description="Headless simulator for VEX EXP Python student programs.",
    )
    parser.add_argument("--version", action="version", version=f"vex_sim {__version__}")

    sub = parser.add_subparsers(dest="command")

    # ---- run ----------------------------------------------------------
    run_p = sub.add_parser(
        "run",
        help=(
            "Execute a student program against a playground. If the playground "
            "declares success criteria, the run is evaluated and a scenario "
            "result is emitted; otherwise the raw call log is emitted (Phase 3 "
            "behaviour, kept for back-compat)."
        ),
    )
    run_p.add_argument(
        "student_file",
        type=Path,
        help="Path to the student program: a .py file or a VEXcode EXP .exppython project file.",
    )
    run_p.add_argument(
        "--max-time",
        type=float,
        default=None,
        help=(
            "Maximum simulated time (seconds). Defaults to the playground's "
            "time_limit, or 30 s if the playground does not set one."
        ),
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
        help="Run without a display (default).",
    )
    mode.add_argument(
        "--render",
        dest="render",
        action="store_true",
        help="Open a pygame window and run the program live.",
    )
    run_p.set_defaults(render=False)
    run_p.add_argument(
        "--playground",
        default=EMPTY_ROOM.name,
        help=(
            f"Playground name (one of: {', '.join(sorted(PLAYGROUNDS))}) "
            "or path to a JSON playground file. "
            f"Default: {EMPTY_ROOM.name}."
        ),
    )
    run_p.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier for --render. Default: 1.0 (real-time).",
    )

    # ---- list ---------------------------------------------------------
    list_p = sub.add_parser("list", help="List bundled playgrounds.")
    list_p.add_argument(
        "--verbose",
        action="store_true",
        help="Include each playground's description in the output.",
    )

    # ---- grade --------------------------------------------------------
    grade_p = sub.add_parser(
        "grade",
        help=(
            "Run many submissions against many scenarios in subprocesses, "
            "writing a CSV/JSON results table."
        ),
    )
    grade_p.add_argument(
        "--submissions",
        required=True,
        type=Path,
        help=("Directory of student programs (.py or .exppython), or a single " "such file."),
    )
    grade_p.add_argument(
        "--scenarios",
        required=True,
        type=Path,
        help=(
            "Directory of playground .json files (or a single .json file). "
            "Pointing at src/vex_sim/playground_files runs every bundled scenario."
        ),
    )
    grade_p.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path. Extension picks the format: .csv (default) or .json.",
    )
    grade_p.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Wall-clock seconds per (submission, scenario) before the child is killed.",
    )
    grade_p.add_argument(
        "--max-time",
        type=float,
        default=None,
        help=(
            "Simulated-time budget passed to each child. Defaults to the "
            "scenario's time_limit, or 30 s if none is set."
        ),
    )
    grade_p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Run up to N (submission, scenario) pairs concurrently. Default: 1.",
    )
    grade_p.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Also write a self-contained HTML matrix report at this path.",
    )

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    playground = get_playground(args.playground)

    # If the playground has success criteria, run the scenario evaluator
    # and emit its structured result. The JSON payload still lands at
    # ``--out`` (stdout by default, kept compatible with Phase 3
    # consumers); the human-readable summary goes to stderr so tools
    # piping JSON aren't disturbed.
    if playground.success_criteria is not None:
        result = run_scenario(
            args.student_file,
            playground=playground,
            render=args.render,
            speed=args.speed,
            max_time=args.max_time,
        )
        out_text = json.dumps(result.to_dict(), indent=2)
        if args.out == "-":
            sys.stdout.write(out_text + "\n")
        else:
            Path(args.out).write_text(out_text, encoding="utf-8")
        sys.stderr.write(result.to_human() + "\n")
        # Exit 0 keeps Phase 3 consumers (which assumed CLI exit 0 means
        # "the simulator ran") happy. Pass/fail is in the JSON. A
        # student-error or unhandled timeout still exits 1 below.
        if result.raw.get("status") == "error":
            return 1
        return 0

    # No success criteria -> behave like Phase 3 (raw call-log JSON).
    max_time = args.max_time if args.max_time is not None else 30.0
    if args.render:
        from vex_sim import render  # noqa: PLC0415

        raw = render.run_live(
            args.student_file,
            max_time=max_time,
            playground=playground,
            speed=args.speed,
        )
    else:
        raw = runner.run(args.student_file, max_time=max_time, playground=playground)

    out_text = json.dumps(raw, indent=2)
    if args.out == "-":
        sys.stdout.write(out_text + "\n")
    else:
        Path(args.out).write_text(out_text, encoding="utf-8")
    return 1 if raw["status"] == "error" else 0


def _cmd_list(args: argparse.Namespace) -> int:
    for name in sorted(PLAYGROUNDS):
        pg = PLAYGROUNDS[name]
        if args.verbose and pg.description:
            sys.stdout.write(f"{name}\n    {pg.description}\n")
        else:
            sys.stdout.write(f"{name}\n")
    return 0


def _cmd_grade(args: argparse.Namespace) -> int:
    from vex_sim import grader  # noqa: PLC0415

    submissions = grader.discover_submissions(args.submissions)
    scenarios = grader.discover_scenarios(args.scenarios)

    if not submissions:
        sys.stderr.write(f"no submissions found under {args.submissions}\n")
        return 2
    if not scenarios:
        sys.stderr.write(f"no scenarios found under {args.scenarios}\n")
        return 2

    sys.stderr.write(
        f"grading {len(submissions)} submission(s) x {len(scenarios)} scenario(s) "
        f"= {len(submissions) * len(scenarios)} run(s); "
        f"timeout={args.timeout:.0f}s workers={args.workers}\n"
    )

    done = 0
    total = len(submissions) * len(scenarios)

    def progress(r: grader.GradeResult) -> None:
        nonlocal done
        done += 1
        verdict = "PASS" if r.passed else r.status.upper()
        sys.stderr.write(f"  [{done}/{total}] {r.submission}  {r.scenario}  {verdict}\n")

    results = grader.grade(
        submissions,
        scenarios,
        timeout=args.timeout,
        max_time=args.max_time,
        workers=args.workers,
        progress=progress,
    )

    out_path: Path = args.output
    suffix = out_path.suffix.lower()
    if suffix == ".json":
        grader.write_json(results, out_path)
    else:
        grader.write_csv(results, out_path)

    if args.html is not None:
        grader.write_html(results, args.html)

    passed = sum(1 for r in results if r.passed)
    sys.stderr.write(f"done: {passed}/{len(results)} pass -> {out_path}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "list":
        return _cmd_list(args)
    if args.command == "grade":
        return _cmd_grade(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
