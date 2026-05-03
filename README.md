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

## Status

**Phase 0 — scaffolding only.** The package installs and the CLI runs, but no simulation logic exists yet. See the project plan for what's next.

## Development

```bash
uv run ruff check .       # lint
uv run black .            # format
uv run pytest             # tests
```
