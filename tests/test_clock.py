from __future__ import annotations

import pytest

from vex_sim.api._clock import SIM_CLOCK, Clock, SimulationTimeout


@pytest.fixture(autouse=True)
def _isolated_clock():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)


def test_clock_starts_at_zero():
    assert SIM_CLOCK.now() == 0.0
    assert SIM_CLOCK.now_ms() == 0


def test_advance_accumulates():
    SIM_CLOCK.advance(0.5)
    SIM_CLOCK.advance(0.25)
    assert SIM_CLOCK.now() == pytest.approx(0.75)
    assert SIM_CLOCK.now_ms() == 750


def test_reset_zeroes_clock():
    SIM_CLOCK.advance(1.0)
    SIM_CLOCK.reset()
    assert SIM_CLOCK.now() == 0.0


def test_negative_advance_rejected():
    with pytest.raises(ValueError):
        SIM_CLOCK.advance(-0.1)


def test_max_time_triggers_simulation_timeout():
    SIM_CLOCK.set_max_time(1.0)
    SIM_CLOCK.advance(0.5)
    with pytest.raises(SimulationTimeout):
        SIM_CLOCK.advance(0.6)


def test_max_time_none_disables_timeout():
    SIM_CLOCK.set_max_time(None)
    SIM_CLOCK.advance(1_000_000.0)


def test_independent_clock_instance():
    c = Clock()
    c.advance(1.5)
    assert c.now() == pytest.approx(1.5)
    assert SIM_CLOCK.now() == 0.0
