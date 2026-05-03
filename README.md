# vex_sim

A headless simulator for VEX EXP Python student programs.

## Intent

Let VEX EXP-style student code run, be tested, and be marked on a regular computer — without a physical robot, without a display, deterministically. The simulator's API surface mirrors the real VEX EXP Python API ([api.vex.com/exp/home/python](https://api.vex.com/exp/home/python)) so a program written here will run on the brain unchanged.

Design priorities, in order:

1. **API parity** with VEX EXP Python — same classes, methods, parameter names, units.
2. **Headless-first** — every feature must work without a display (CI, automated marking).
3. **Determinism** — same input + same playground = same result, every time.

## Quick start

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.10+.

```bash
uv sync
uv run pytest
uv run python -m vex_sim --help
```

## Running a student program

Headless (default — no display, JSON call log to stdout or a file):

```bash
uv run python -m vex_sim run path/to/student.py
uv run python -m vex_sim run path/to/student.py --max-time 30 --out result.json
```

With the pygame window (requires the `render` extra):

```bash
uv sync --extra render
uv run python -m vex_sim run path/to/student.py --render
uv run python -m vex_sim run path/to/student.py --render --speed 2.0
```

A worked example lives in `examples/drive_square.py` — drives a 1 m square in the default playground:

```bash
uv run python -m vex_sim run examples/drive_square.py --render
```

### Flags

| Flag | Default | Notes |
|---|---|---|
| `--max-time SEC` | `30` | Simulated-time budget. Unbounded loops terminate when the clock crosses this. |
| `--out PATH` | `-` (stdout) | Where the JSON result goes. |
| `--headless` / `--render` | `--headless` | Render opens a pygame window after the run and animates the recorded trajectory. |
| `--playground NAME` | `empty_room` | Selects a playground from `vex_sim.playgrounds`. |
| `--speed N` | `1.0` | Playback speed multiplier for `--render` (1.0 = real-time). |

## Status

**Phase 2 — minimal pygame runtime, live execution.** Differential-drive kinematics move the robot through a 2D world; `--render` opens a pygame window and animates the run as it happens. Student code runs on a greenlet driven by the simulator's main loop — single-threaded cooperative scheduling, no locks, debugger-friendly (see `vex_sim/scheduler.py` for the rationale). Sensors still return defaults; collision response and controller input land in later phases. Determinism and headless-first remain the load-bearing constraints.

## Development

```bash
uv run ruff check .       # lint
uv run black .            # format
uv run pytest             # tests
```
