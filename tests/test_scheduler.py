"""Tests for vex_sim.scheduler: greenlet-based cooperative scheduling."""

from __future__ import annotations

import pytest

from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.scheduler import SCHEDULER


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    SCHEDULER.kill()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    SCHEDULER.kill()


def _drive_to_completion() -> None:
    while SCHEDULER.advance_to_next_wait():
        dt = max(0.0, SCHEDULER.pending_deadline - SIM_CLOCK.now())
        SIM_CLOCK.advance(dt)


# -----------------------------------------------------------------------------
# yield_for fallback (no student installed)
# -----------------------------------------------------------------------------


def test_yield_for_falls_back_to_clock_advance_outside_student():
    SCHEDULER.yield_for(SIM_CLOCK.now() + 0.5)
    assert SIM_CLOCK.now() == pytest.approx(0.5)


def test_yield_for_no_op_when_deadline_already_passed():
    SIM_CLOCK.advance(1.0)
    SCHEDULER.yield_for(0.5)  # deadline in the past
    assert SIM_CLOCK.now() == pytest.approx(1.0)


# -----------------------------------------------------------------------------
# install + drive
# -----------------------------------------------------------------------------


def test_student_runs_to_completion_with_no_waits():
    log = []

    def student():
        log.append("ran")

    SCHEDULER.install(student)
    _drive_to_completion()
    assert SCHEDULER.done
    assert log == ["ran"]


def test_student_yields_and_resumes():
    log = []

    def student():
        log.append("before")
        SCHEDULER.yield_for(SIM_CLOCK.now() + 1.0)
        log.append("after")

    SCHEDULER.install(student)
    # First step: student runs up to yield_for and suspends.
    assert SCHEDULER.advance_to_next_wait() is True
    assert log == ["before"]
    assert SCHEDULER.pending_deadline == pytest.approx(1.0)
    # Advance clock to the deadline; resume.
    SIM_CLOCK.advance(1.0)
    assert SCHEDULER.advance_to_next_wait() is False
    assert SCHEDULER.done
    assert log == ["before", "after"]


def test_student_multiple_waits_accumulate_clock():
    def student():
        SCHEDULER.yield_for(SIM_CLOCK.now() + 0.25)
        SCHEDULER.yield_for(SIM_CLOCK.now() + 0.5)
        SCHEDULER.yield_for(SIM_CLOCK.now() + 0.25)

    SCHEDULER.install(student)
    _drive_to_completion()
    assert SCHEDULER.done
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_student_exception_propagates_to_main():
    def student():
        SCHEDULER.yield_for(SIM_CLOCK.now() + 0.1)
        raise ValueError("boom")

    SCHEDULER.install(student)
    SCHEDULER.advance_to_next_wait()  # to first yield
    SIM_CLOCK.advance(0.1)
    with pytest.raises(ValueError, match="boom"):
        SCHEDULER.advance_to_next_wait()


def test_kill_terminates_suspended_student():
    log = []

    def student():
        try:
            SCHEDULER.yield_for(SIM_CLOCK.now() + 100.0)
        finally:
            log.append("cleanup")

    SCHEDULER.install(student)
    SCHEDULER.advance_to_next_wait()  # student suspends
    assert log == []
    SCHEDULER.kill()
    # The finally block ran inside the student greenlet during teardown.
    assert log == ["cleanup"]
    assert SCHEDULER.done


def test_install_replaces_previous_student():
    log = []

    def first():
        try:
            SCHEDULER.yield_for(SIM_CLOCK.now() + 100.0)
        finally:
            log.append("first cleanup")

    def second():
        log.append("second ran")

    SCHEDULER.install(first)
    SCHEDULER.advance_to_next_wait()
    SCHEDULER.install(second)  # should kill `first`
    assert log == ["first cleanup"]
    _drive_to_completion()
    assert log == ["first cleanup", "second ran"]


# -----------------------------------------------------------------------------
# in_student_context
# -----------------------------------------------------------------------------


def test_in_student_context_true_only_inside_student():
    seen = []

    def student():
        seen.append(SCHEDULER.in_student_context())
        SCHEDULER.yield_for(SIM_CLOCK.now() + 0.1)
        seen.append(SCHEDULER.in_student_context())

    SCHEDULER.install(student)
    assert SCHEDULER.in_student_context() is False
    _drive_to_completion()
    assert seen == [True, True]
    assert SCHEDULER.in_student_context() is False
