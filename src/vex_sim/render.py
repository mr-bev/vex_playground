"""Pygame live execution of a student program.

The pygame loop runs on the main thread. Between frames it advances the
scheduler-driven student greenlet by ``frame_dt * speed`` simulated
seconds, sub-stepping through the student's wait deadlines so that
animation is smooth and continuous-motion sleeps are integrated by the
world. The student greenlet, the world, and the controller-input cache
all live on this same thread; there are no locks.

Headless-first: this module imports pygame lazily so the package still
works on systems without it. Install the optional render extra:

    uv sync --extra render
"""

from __future__ import annotations

import io
import math
import random
import runpy
import sys
import traceback
from pathlib import Path
from typing import Any

from vex_sim import api
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK, SimulationTimeout
from vex_sim.scheduler import SCHEDULER
from vex_sim.sensors_world import SENSOR_CACHE
from vex_sim.stdout_capture import tee_stdout
from vex_sim.world import WORLD, Playground

_WINDOW_PX = 800
_BG_COLOR = (24, 24, 28)
_WALL_COLOR = (200, 200, 210)
_GOAL_COLOR = (80, 180, 110)
_ROBOT_COLOR = (240, 180, 70)
_HEADING_COLOR = (255, 255, 255)
_TEXT_COLOR = (200, 200, 210)
_ROBOT_RADIUS_MM = 160.0
_STDOUT_CAP = 64 * 1024


def _import_pygame():
    try:
        import pygame  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "pygame is required for --render mode. Install with: uv sync --extra render"
        ) from e
    return pygame


def _scale_factory(playground: Playground):
    """Return (to_screen, scale_px_per_mm). World y goes up; screen y goes down."""
    margin = 20
    avail = _WINDOW_PX - 2 * margin
    s = avail / max(playground.width, playground.height)

    def to_screen(x_mm: float, y_mm: float) -> tuple[int, int]:
        sx = margin + int(x_mm * s)
        sy = _WINDOW_PX - margin - int(y_mm * s)
        return sx, sy

    return to_screen, s


def _build_vex_module():
    from types import ModuleType  # noqa: PLC0415

    mod = ModuleType("vex")
    names = list(api.__all__)
    for name in names:
        setattr(mod, name, getattr(api, name))
    mod.__all__ = names  # type: ignore[attr-defined]
    return mod


def _install_shims() -> tuple[Any, Any]:
    prior_vex = sys.modules.get("vex")
    prior_urandom = sys.modules.get("urandom")
    sys.modules["vex"] = _build_vex_module()
    sys.modules["urandom"] = random
    return prior_vex, prior_urandom


def _restore_shims(prior: tuple[Any, Any]) -> None:
    prior_vex, prior_urandom = prior
    if prior_vex is None:
        sys.modules.pop("vex", None)
    else:
        sys.modules["vex"] = prior_vex
    if prior_urandom is None:
        sys.modules.pop("urandom", None)
    else:
        sys.modules["urandom"] = prior_urandom


def _student_entrypoint(student_path: str | Path, captured: io.StringIO) -> None:
    with tee_stdout(captured):
        runpy.run_path(str(student_path), run_name="__main__")


def _advance_until(target_t: float) -> None:
    """Drive the student greenlet up to simulated time ``target_t``.

    The student may yield several waits inside this window; each is
    processed by advancing the clock to its deadline (or to target_t,
    whichever comes first). When the deadline is hit the student is
    resumed; when target_t is hit we exit so the caller can render a
    frame and we resume on the next call.
    """
    while not SCHEDULER.done and SIM_CLOCK.now() < target_t:
        if SCHEDULER.pending_deadline == float("-inf") and not SCHEDULER.advance_to_next_wait():
            return
        deadline = SCHEDULER.pending_deadline
        advance_to = min(target_t, deadline)
        dt = advance_to - SIM_CLOCK.now()
        if dt > 0:
            SIM_CLOCK.advance(dt)
        # Wait satisfied: resume the student. It either finishes or issues
        # a new wait, which the next loop iteration picks up.
        if SIM_CLOCK.now() >= deadline and not SCHEDULER.advance_to_next_wait():
            return


def run_live(
    student_path: str | Path,
    max_time: float = 30.0,
    playground: Playground | None = None,
    *,
    speed: float = 1.0,
    fps: int = 60,
    auto_close_on_complete: bool = False,
) -> dict[str, Any]:
    """Run a student program live in a pygame window.

    Returns the same dict shape as :func:`vex_sim.runner.run`. Status
    becomes ``"interrupted"`` if the user closes the window before the
    program finishes.

    By default the window stays open after the student finishes so the
    user can inspect the final pose. Pass ``auto_close_on_complete=True``
    to exit the loop as soon as the program returns or fails — useful
    for automated tests under SDL's dummy video driver.
    """
    pygame = _import_pygame()

    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(max_time)
    CALL_LOG.clear()
    SENSOR_CACHE.reset()
    if playground is None:
        from vex_sim.playgrounds import EMPTY_ROOM  # noqa: PLC0415

        playground = EMPTY_ROOM
    WORLD.reset(playground)
    SENSOR_CACHE.refresh()

    prior_modules = _install_shims()
    captured = io.StringIO()
    status = "completed"
    error: dict[str, Any] | None = None

    pygame.init()
    SCHEDULER.install(lambda: _student_entrypoint(student_path, captured))

    try:
        screen = pygame.display.set_mode((_WINDOW_PX, _WINDOW_PX))
        pygame.display.set_caption(f"vex_sim — {playground.name}")
        clock = pygame.time.Clock()
        font = pygame.font.SysFont(None, 20)

        to_screen, scale = _scale_factory(playground)
        radius_px = max(4, int(_ROBOT_RADIUS_MM * scale))

        running = True
        while running:
            dt_ms = clock.tick(fps)
            dt_real = dt_ms / 1000.0
            target_t = SIM_CLOCK.now() + dt_real * speed

            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q)
                ):
                    running = False

            if not SCHEDULER.done:
                try:
                    _advance_until(target_t)
                except SimulationTimeout:
                    status = "timed_out"
                except SystemExit as e:
                    if e.code not in (None, 0):
                        status = "error"
                        error = {
                            "type": "SystemExit",
                            "message": str(e.code),
                            "traceback": traceback.format_exc(),
                        }
                except BaseException as e:  # noqa: BLE001
                    status = "error"
                    error = {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    }
            elif auto_close_on_complete:
                running = False

            screen.fill(_BG_COLOR)
            for w in playground.walls:
                pygame.draw.line(
                    screen, _WALL_COLOR, to_screen(w.x1, w.y1), to_screen(w.x2, w.y2), 3
                )
            if playground.goal is not None:
                g = playground.goal
                gx1, gy1 = to_screen(g.x, g.y + g.h)
                gx2, gy2 = to_screen(g.x + g.w, g.y)
                pygame.draw.rect(screen, _GOAL_COLOR, pygame.Rect(gx1, gy1, gx2 - gx1, gy2 - gy1))

            pose = WORLD.pose
            cx, cy = to_screen(pose.x, pose.y)
            pygame.draw.circle(screen, _ROBOT_COLOR, (cx, cy), radius_px)
            hx = pose.x + _ROBOT_RADIUS_MM * 1.4 * math.cos(pose.theta)
            hy = pose.y + _ROBOT_RADIUS_MM * 1.4 * math.sin(pose.theta)
            pygame.draw.line(screen, _HEADING_COLOR, (cx, cy), to_screen(hx, hy), 3)

            label_lines = [
                f"t = {SIM_CLOCK.now():6.2f} s   "
                f"({pose.x:7.1f}, {pose.y:7.1f}) mm   "
                f"{math.degrees(pose.theta):6.1f}°",
                f"status: {status}"
                + ("  (close window to exit)" if SCHEDULER.done or status != "completed" else ""),
            ]
            for i, line in enumerate(label_lines):
                screen.blit(font.render(line, True, _TEXT_COLOR), (10, 10 + i * 18))

            pygame.display.flip()

        if not SCHEDULER.done and running is False and status == "completed":
            status = "interrupted"
    finally:
        SCHEDULER.kill()
        _restore_shims(prior_modules)
        SIM_CLOCK.set_max_time(None)
        WORLD.finalize()
        pygame.quit()

    stdout_text = captured.getvalue()
    if len(stdout_text) > _STDOUT_CAP:
        stdout_text = stdout_text[:_STDOUT_CAP] + "\n[truncated]\n"

    return {
        "status": status,
        "max_time": max_time,
        "elapsed_sim_time": SIM_CLOCK.now(),
        "error": error,
        "stdout": stdout_text,
        "calls": CALL_LOG.entries(),
    }
