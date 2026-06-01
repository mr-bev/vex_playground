# vex_sim

A headless simulator for VEX EXP Python student programs.

## Intent

Let VEX EXP-style student code run, be tested, and be marked on a regular computer — without a physical robot, without a display, deterministically. The simulator's API surface mirrors the real VEX EXP Python API ([api.vex.com/exp/home/python](https://api.vex.com/exp/home/python)) so a program written here will run on the brain unchanged.

Design priorities, in order:

1. **API parity** with VEX EXP Python — same classes, methods, parameter names, units.
2. **Headless-first** — every feature must work without a display (CI, automated marking).
3. **Determinism** — same input + same playground = same result, every time.

## 2D world, with heights

The world is rendered top-down, but every wall has a **height in millimetres**. A distance sensor only sees walls whose height is at least its `mount_height`. Bumpers sit at floor level and trigger on every wall, regardless of height.

This is deliberate — and it preserves a real classroom failure mode:

> Mount the distance sensor 100 mm up the chassis, drive it at a 30 mm wall, and the sensor reports infinity. The bumper still hits. On a real robot, this is the moment the student realises *where* you mount a sensor decides what it can see. The simulator catches it without anyone needing to move a physical motor.

Three wall-height presets are built in — `"low"` = 30 mm, `"mid"` = 100 mm, `"tall"` = 200 mm — and the renderer colour-codes each (pale grey / medium blue / dark blue). Numeric heights work too. Default if omitted: `"tall"`.

## Quick start

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.10+.

```bash
uv sync
uv run pytest
uv run python -m vex_sim --help
uv run python -m vex_sim list --verbose      # show bundled playgrounds
```

## Running a student program

A student program is either a plain `.py` file or — more conveniently — the
`.exppython` project file that VEXcode EXP saves. Point the simulator straight
at the `.exppython`; there is no need to copy-paste code into a `.py` file.

> **`.exppython` files** are JSON. The runnable program lives in the
> `textContent` field: the VEXcode-generated robot-configuration block followed
> by the student's own code, exactly as it is flashed to the brain. The
> simulator unwraps this automatically, and an error traceback points at the
> right line of the embedded program. See `tests/empty.exppython` for the shape.

Headless (default — no display, JSON result to stdout or a file):

```bash
uv run python -m vex_sim run path/to/student.exppython --playground empty_room
uv run python -m vex_sim run path/to/student.py --playground low_wall_maze --out result.json
```

With the pygame window (requires the `render` extra):

```bash
uv sync --extra render
uv run python -m vex_sim run path/to/student.py --playground pickup_and_dropoff --render
uv run python -m vex_sim run path/to/student.py --playground empty_room --render --speed 2.0
```

When the chosen playground declares success criteria (every bundled one does), the CLI emits a structured **scenario result**: pass/fail, time taken, distance travelled, collisions, sensor reads, visited zones, and the final pose. The JSON goes to `--out` (stdout by default); a human-readable summary goes to stderr so you can pipe JSON downstream.

### Worked examples

- `examples/reach_goal.py` — drives diagonally across `empty_room` into the goal zone using dead reckoning.
- `examples/bumper_wall_follower.py` — bumper-only nav for `low_wall_maze`. Demonstrates that a default 100 mm distance sensor mount is blind to the 30 mm interior walls; the bumper picks them up on contact.
- `examples/colour_walker.py` — walks `pickup_and_dropoff` in the right order using `Optical(port).color()` to confirm arrival at each coloured zone.
- `examples/drive_square.py` — a 1 m square in the empty room (Phase 2 demo).
- `examples/drive_keyboard.py` — keyboard driver-control demo (render mode).

```bash
uv run python -m vex_sim run examples/colour_walker.py --playground pickup_and_dropoff --render
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
| `--playground NAME` | `empty_room` | A bundled playground name (see `list`) or a path to a custom JSON file. |
| `--max-time SEC` | scenario `time_limit`, else `30` | Simulated-time budget. Unbounded loops terminate when the clock crosses this. |
| `--out PATH` | `-` (stdout) | Where the JSON result goes. |
| `--headless` / `--render` | `--headless` | Render opens a pygame window and runs the program live. |
| `--speed N` | `1.0` | Playback speed multiplier for `--render` (1.0 = real-time). |

## Bundled playgrounds

Drop a `*.json` file into `src/vex_sim/playground_files/` and it is discovered automatically. The schema lives next to it at `playground.schema.json`; the loader hand-rolls a clear-error validator (`vex_sim.playground_loader`) so malformed files report exactly which key is wrong, e.g. `walls[2].height: unknown wall-height preset 'tiny'`.

| Name | What it teaches |
|---|---|
| `empty_room` | Sanity check: 3 m room, single goal zone, all-tall walls. |
| `low_wall_maze` | All interior walls are 30 mm low. Default-mounted distance sensor cannot see them — students must drop the mount or rely on bumpers. |
| `mixed_heights` | Mix of low, mid, tall walls. Rewards a thoughtful `mount_height` choice. |
| `pickup_and_dropoff` | Three coloured zones (green / red / blue). Read `Optical(port).color()` to confirm arrival at each. Visit-sequence success criteria. |

### Sensor & API additions in Phase 4

- `Distance(port, mount_height=100)` — millimetres above the floor. Distance reads filter walls by `height_mm >= mount_height`.
- `Optical(port).color()` — returns the colour of the floor region under the robot's centre, or `"black"` if there isn't one. Canonical colour names: `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `cyan`, `white`, `black`.
- Bumpers ignore wall heights (everything triggers them on contact, like in the real world).

## Batch grading

`python -m vex_sim grade` runs many submissions against many scenarios in
subprocesses, with a wall-clock timeout per pair, and writes a results
table.

```bash
uv run python -m vex_sim grade \
    --submissions ./submissions/ \
    --scenarios src/vex_sim/playground_files/ \
    --output results.csv \
    --timeout 60 \
    --workers 4 \
    --html results.html
```

| Flag | Default | Notes |
|---|---|---|
| `--submissions PATH` | required | Directory of student programs — `.py` and/or `.exppython` files (or a single file). Files starting with `_` are skipped. |
| `--scenarios PATH` | required | Directory of playground `.json` files (or a single file). The bundled `playground.schema.json` is excluded. |
| `--output PATH` | required | Output path. `.json` extension picks JSON; anything else (typically `.csv`) picks CSV. |
| `--timeout SEC` | `60` | Wall-clock budget per (submission, scenario). The child process is killed past this, and a `wall_timeout` row is written. |
| `--max-time SEC` | scenario `time_limit`, else `30` | Simulated-time budget passed to each child. |
| `--workers N` | `1` | Run up to N pairs concurrently (threaded subprocess fan-out). |
| `--html PATH` | — | Also writes a self-contained HTML matrix report. |

CSV columns: `submission, scenario, passed, status, reason, time_taken,
distance_travelled_mm, collisions, sensor_reads, visited_zones,
error_type, error_message, runtime_wall_seconds`. Status is one of
`completed`, `timed_out`, `error` (from the simulator), or
`wall_timeout` / `subprocess_crash` (from the harness when the child
exceeds the wall budget or fails to emit JSON).

Progress and the final summary go to stderr, so stdout stays empty for
piping into other tooling.

### Threat model — read this before grading untrusted code

The subprocess boundary exists for **crash isolation**, not security.
A submission that raises, hits a recursion limit, or runs an infinite
loop will be killed without taking down the harness. That is all.

The child process inherits the marker's user permissions, so a
malicious submission can read or modify any file the marker can, open
arbitrary network sockets, spawn shell commands, and fork further
processes that may outlive the wall timeout.

If you are grading code from people you do not trust, run the grader
inside a real sandbox (container, throwaway VM, restricted user
account). This project is not the right place to build that sandbox —
it is a deliberate non-goal.

## Status

**Phase 5 — batch grading.** `python -m vex_sim grade --submissions
DIR --scenarios DIR --output results.csv` runs every (submission,
scenario) pair as a subprocess with a wall-clock timeout, isolating
student crashes and infinite loops from the harness. Output is CSV
(default) or JSON, with an optional HTML matrix report. Phase 4's
playground / scenario / wall-height / floor-region machinery is
unchanged. All 537 prior tests still pass.

Out of scope until later phases: true security sandboxing, variable
floor surfaces, slip / drift, sensor noise, optical mount-position
offset, 3D rendering, Webots backend.

## Development

```bash
uv run ruff check .       # lint
uv run black .            # format
uv run pytest             # tests
```
