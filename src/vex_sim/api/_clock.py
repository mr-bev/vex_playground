from __future__ import annotations


class SimulationTimeout(Exception):
    """Raised when simulated time exceeds the runner's max_time budget.

    The runner catches this to mark a run as timed_out and dump the call log.
    Student code should never see or catch this; a `while True:` loop terminates
    when wait()/sleep() or a motion method advances the clock past max_time.
    """


class Clock:
    def __init__(self) -> None:
        self._t: float = 0.0
        self._max_time: float | None = None

    def now(self) -> float:
        return self._t

    def now_ms(self) -> int:
        return int(self._t * 1000)

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError(f"cannot advance clock backwards (seconds={seconds!r})")
        self._t += seconds
        self._check_timeout()

    def reset(self) -> None:
        self._t = 0.0

    def set_max_time(self, max_time: float | None) -> None:
        """Set the timeout budget. None disables it."""
        self._max_time = max_time

    def get_max_time(self) -> float | None:
        return self._max_time

    def _check_timeout(self) -> None:
        if self._max_time is not None and self._t > self._max_time:
            raise SimulationTimeout(
                f"simulated time {self._t:.3f}s exceeded max_time {self._max_time:.3f}s"
            )


SIM_CLOCK = Clock()
