"""Tests for vex_sim.render.

The pure helpers (`_scale_factory`, `_advance_until`) are exercised
directly. The full pygame loop is tested under SDL's dummy video driver
so it can run in CI without a display: a short student program runs to
completion in the live loop, and we verify the world ended up where the
headless runner would put it.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._drivetrain import _MAX_LINEAR_MMPS
from vex_sim.playgrounds import EMPTY_ROOM
from vex_sim.render import _advance_until, _scale_factory
from vex_sim.scheduler import SCHEDULER
from vex_sim.world import WORLD


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    WORLD.reset()
    SCHEDULER.kill()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    WORLD.reset()
    SCHEDULER.kill()


def test_scale_factory_maps_origin_corner():
    to_screen, _ = _scale_factory(EMPTY_ROOM)
    sx, sy = to_screen(0.0, 0.0)
    assert sx >= 0
    assert sy <= 800


def test_scale_factory_y_axis_is_flipped():
    to_screen, _ = _scale_factory(EMPTY_ROOM)
    _, sy_low = to_screen(0.0, 0.0)
    _, sy_high = to_screen(0.0, EMPTY_ROOM.height)
    assert sy_high < sy_low


def test_advance_until_drives_student_to_completion(tmp_path: Path):
    import io  # noqa: PLC0415

    from vex_sim import runner  # noqa: PLC0415

    p = tmp_path / "student.py"
    p.write_text(
        textwrap.dedent("""
            from vex import *
            brain = Brain()
            wait(0.5, SEC)
            wait(0.25, SEC)
            """),
        encoding="utf-8",
    )

    SIM_CLOCK.set_max_time(5.0)
    WORLD.reset(EMPTY_ROOM)
    captured = io.StringIO()
    prior = runner._install_shims()
    SCHEDULER.install(lambda: runner._student_entrypoint(p, captured))
    try:
        # Walk forward by 0.1 s of simulated time at a time. The student
        # suspends at 0.5 s, then 0.75 s, then finishes.
        for _ in range(20):
            _advance_until(SIM_CLOCK.now() + 0.1)
            if SCHEDULER.done:
                break
        assert SCHEDULER.done
        assert SIM_CLOCK.now() == pytest.approx(0.75)
    finally:
        SCHEDULER.kill()
        runner._restore_shims(prior)
        SIM_CLOCK.set_max_time(None)


@pytest.mark.skipif(
    os.environ.get("VEX_SIM_SKIP_PYGAME") == "1",
    reason="pygame loop test disabled by environment",
)
def test_run_live_completes_short_program(tmp_path: Path, monkeypatch):
    """End-to-end: a short program runs to completion in the live render loop.

    Uses SDL's dummy video driver so no real window is opened; safe for CI.
    Student program is short (~40 ms sim time at fast speed), so the test
    is fast.
    """
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")

    from vex_sim import render  # noqa: PLC0415

    p = tmp_path / "student.py"
    p.write_text(
        textwrap.dedent("""
            from vex import *
            brain = Brain()
            lm = Motor(Ports.PORT6, False)
            rm = Motor(Ports.PORT10, True)
            dt = DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)
            dt.drive_for(FORWARD, 100, MM, velocity=100)
            """),
        encoding="utf-8",
    )

    result = render.run_live(
        p,
        max_time=5.0,
        playground=EMPTY_ROOM,
        speed=100.0,
        fps=240,
        auto_close_on_complete=True,
    )
    assert result["status"] == "completed"
    # 100 mm at 100% velocity = 100 / (100% speed) seconds of sim time.
    assert result["elapsed_sim_time"] == pytest.approx(100 / _MAX_LINEAR_MMPS, abs=0.05)
