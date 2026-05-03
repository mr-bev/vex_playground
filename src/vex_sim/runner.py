"""Run a VEX EXP-style student program in the simulator and capture its calls.

The runner installs two synthetic modules into sys.modules:

  - `vex`     -- a module populated from vex_sim.api so that the student's
                 `from vex import *` works unchanged.
  - `urandom` -- aliased to Python's stdlib `random`, so MicroPython-style
                 `import urandom; urandom.seed(...)` works on CPython.

Time advances only via SIM_CLOCK; there are no real-time sleeps. A `while True:`
loop terminates because wait()/motion methods raise SimulationTimeout when the
clock crosses max_time.
"""

from __future__ import annotations

import io
import random
import runpy
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Any

from vex_sim import api
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK, SimulationTimeout

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


def run(student_path: str | Path, max_time: float = 30.0) -> dict[str, Any]:
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

    prior_modules = _install_shims()
    captured = io.StringIO()
    status = "completed"
    error: dict[str, Any] | None = None

    try:
        with redirect_stdout(captured):
            runpy.run_path(str(student_path), run_name="__main__")
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
        _restore_shims(prior_modules)
        SIM_CLOCK.set_max_time(None)

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
