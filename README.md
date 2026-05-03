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

`examples/drive_keyboard.py` is a driver-control demo. WASD steers the robot in render mode; in headless mode it sits still and quietly times out (controller axes are deterministic zero):

```bash
uv run python -m vex_sim run examples/drive_keyboard.py --render
```

### Render-mode controls

| Key | Action |
|---|---|
| `space` | Toggle pause |
| `→` | Single-step one frame (works while paused) |
| `1` / `2` / `3` | Set sim speed to 0.5× / 1× / 2× |
| `esc` | Quit |
| `W` `A` `S` `D` / `↑↓←→` | Controller axes (right-stick / left-stick) |
| `J K I , Q E U O Z X` | Controller buttons (A B Up Down L1 L2 R1 R2 L3 R3) |

### Flags

| Flag | Default | Notes |
|---|---|---|
| `--max-time SEC` | `30` | Simulated-time budget. Unbounded loops terminate when the clock crosses this. |
| `--out PATH` | `-` (stdout) | Where the JSON result goes. |
| `--headless` / `--render` | `--headless` | Render opens a pygame window after the run and animates the recorded trajectory. |
| `--playground NAME` | `empty_room` | Selects a playground from `vex_sim.playgrounds`. |
| `--speed N` | `1.0` | Playback speed multiplier for `--render` (1.0 = real-time). |

## Status

**Phase 3 — live execution, sensors, collisions, controller input.** Distance, Bumper, and Optical now read the world via a per-tick sensor cache (`vex_sim/sensors_world.py`); driving into a wall halts the robot at its chassis radius (rotation still allowed); the Controller API maps to pygame keyboard input in render mode and stays deterministically zeroed in headless mode. Render mode adds a HUD overlay (pose, sensors, brain.screen mirror) and playback controls (pause / single-step / speed). The greenlet-based scheduler from Phase 2 is unchanged — student programs from prior phases keep working without edits.

Out of scope until later phases: multiple playgrounds, scenario success criteria, batch grading, 3D rendering, motor dynamics, sensor noise.

## Development

```bash
uv run ruff check .       # lint
uv run black .            # format
uv run pytest             # tests
```
