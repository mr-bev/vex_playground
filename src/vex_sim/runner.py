"""Run a VEX EXP-style student program in the simulator and capture its calls.

The runner installs two synthetic modules into sys.modules:

  - `vex`     -- a module populated from vex_sim.api so that the student's
                 `from vex import *` works unchanged.
  - `urandom` -- aliased to Python's stdlib `random`, so MicroPython-style
                 `import urandom; urandom.seed(...)` works on CPython.

Execution model
---------------

The student program runs inside a greenlet managed by
:mod:`vex_sim.scheduler`. Time-taking API calls (``wait``, ``drive_for``,
``spin_for`` …) suspend the student greenlet on a deadline; the runner's
main loop advances :data:`SIM_CLOCK` to that deadline and resumes the
student. There is one OS thread, one Python frame stack active at a time.

The headless runner here fast-forwards every wait — sim time skips
straight to each deadline — so the observable behaviour is identical to
a synchronous run. The render module shares the same scheduler but paces
sim time against wall time so a human can watch the robot move.

A ``while True:`` loop terminates because every iteration's wait crosses
``max_time``, and :data:`SIM_CLOCK.advance` raises
:class:`SimulationTimeout` when that happens.
"""

from __future__ import annotations

import io
import random
import runpy
import sys
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any

from vex_sim import api
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK, SimulationTimeout
from vex_sim.scheduler import SCHEDULER
from vex_sim.stdout_capture import tee_stdout
from vex_sim.world import WORLD, Playground

_STDOUT_CAP = 64 * 1024


def _build_vex_module() -> ModuleType:
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
    """Body of the student greenlet.

    Run the student's source with stdout teed into ``captured`` while
    the user-visible terminal still receives every print as it happens.
    Any exception (including :class:`SimulationTimeout`, raised when a
    wait crosses ``max_time``) propagates out of the greenlet and is
    re-raised in the main greenlet by
    :meth:`SCHEDULER.advance_to_next_wait`.
    """
    with tee_stdout(captured):
        runpy.run_path(str(student_path), run_name="__main__")


def _drive_headless() -> None:
    """Pump the scheduler in headless mode: fast-forward through every wait.

    Each iteration resumes the student until its next wait, then advances
    the clock straight to that deadline. SIM_CLOCK.advance raises
    SimulationTimeout if the deadline is past ``max_time``; that
    exception propagates out, the runner's outer try/except catches it.
    """
    while SCHEDULER.advance_to_next_wait():
        dt = max(0.0, SCHEDULER.pending_deadline - SIM_CLOCK.now())
        SIM_CLOCK.advance(dt)


def run(
    student_path: str | Path,
    max_time: float = 30.0,
    playground: Playground | None = None,
) -> dict[str, Any]:
    """Execute the student program and return a structured result.

    Result keys:
      status: "completed" | "timed_out" | "error"
      max_time: the budget that was applied
      elapsed_sim_time: SIM_CLOCK.now() at termination
      error: None or {"type", "message", "traceback"}
      stdout: captured stdout from the student program (capped)
      calls: the call log entries
    """
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(max_time)
    CALL_LOG.clear()
    WORLD.reset(playground)

    prior_modules = _install_shims()
    captured = io.StringIO()
    status = "completed"
    error: dict[str, Any] | None = None

    SCHEDULER.install(lambda: _student_entrypoint(student_path, captured))
    try:
        _drive_headless()
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
    except BaseException as e:
        status = "error"
        error = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        SCHEDULER.kill()
        _restore_shims(prior_modules)
        SIM_CLOCK.set_max_time(None)
        WORLD.finalize()

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
