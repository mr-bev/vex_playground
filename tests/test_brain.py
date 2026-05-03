from __future__ import annotations

import pytest

from vex_sim.api import (
    MSEC,
    SECONDS,
    VOLT,
    Brain,
    Timer,
    Triport,
    sleep,
    wait,
)
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK, SimulationTimeout


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()


def test_brain_construction_records_call():
    Brain()
    entries = CALL_LOG.entries()
    methods = [(e["obj"], e["method"]) for e in entries]
    assert ("brain", "Brain") in methods


def test_brain_screen_print_records_text():
    brain = Brain()
    CALL_LOG.clear()
    brain.screen.print("Calibrating")
    entries = CALL_LOG.entries()
    assert entries[0]["obj"] == "brain.screen"
    assert entries[0]["method"] == "print"
    assert entries[0]["args"] == ["Calibrating"]


def test_brain_screen_print_concatenates_with_sep():
    brain = Brain()
    CALL_LOG.clear()
    brain.screen.print("a", "b", "c", sep="-")
    assert CALL_LOG.entries()[0]["args"] == ["a-b-c"]


def test_brain_screen_print_formats_floats_at_precision():
    brain = Brain()
    CALL_LOG.clear()
    brain.screen.print(3.14159, precision=2)
    assert CALL_LOG.entries()[0]["args"] == ["3.14"]


def test_brain_screen_set_cursor_then_next_row():
    brain = Brain()
    brain.screen.set_cursor(2, 5)
    assert brain.screen.row() == 2
    assert brain.screen.column() == 5
    brain.screen.next_row()
    assert brain.screen.row() == 3
    assert brain.screen.column() == 1


def test_brain_screen_clear_resets_cursor():
    brain = Brain()
    brain.screen.set_cursor(5, 10)
    brain.screen.clear_screen()
    assert brain.screen.row() == 1
    assert brain.screen.column() == 1


def test_brain_battery_defaults():
    brain = Brain()
    assert brain.battery.voltage() == 12000.0
    assert brain.battery.voltage(VOLT) == 12.0
    assert brain.battery.current() == 0.0
    assert brain.battery.capacity() == 100


def test_brain_button_defaults_unpressed():
    brain = Brain()
    assert brain.button.pressing() == 0


def test_brain_button_pressed_callback_recorded():
    brain = Brain()
    CALL_LOG.clear()

    def on_press():
        pass

    brain.button.pressed(on_press)
    e = CALL_LOG.entries()[0]
    assert e["obj"] == "brain.button"
    assert e["method"] == "pressed"
    assert e["kwargs"]["callback"] == "on_press"


def test_brain_timer_system_reads_sim_clock():
    brain = Brain()
    SIM_CLOCK.advance(0.5)
    assert brain.timer.system() == 500


def test_brain_timer_time_default_msec():
    brain = Brain()
    SIM_CLOCK.advance(0.25)
    assert brain.timer.time() == 250


def test_brain_timer_time_seconds():
    brain = Brain()
    SIM_CLOCK.advance(0.5)
    assert brain.timer.time(SECONDS) == pytest.approx(0.5)


def test_brain_timer_clear_zeroes_offset():
    brain = Brain()
    SIM_CLOCK.advance(1.0)
    brain.timer.clear()
    assert brain.timer.time() == 0
    SIM_CLOCK.advance(0.1)
    assert brain.timer.time() == 100


def test_brain_three_wire_port_has_a_through_h():
    brain = Brain()
    for letter in "abcdefgh":
        pin = getattr(brain.three_wire_port, letter)
        assert pin._label == f"brain.three_wire_port.{letter}"
        assert pin._letter == letter


def test_triport_construction_records_and_exposes_pins():
    from vex_sim.api import Ports

    tp = Triport(Ports.PORT10)
    assert tp.index() == 10
    for letter in "abcdefgh":
        assert hasattr(tp, letter)


def test_standalone_timer_independent_offset():
    SIM_CLOCK.advance(2.0)
    t = Timer()
    SIM_CLOCK.advance(0.5)
    assert t.time(SECONDS) == pytest.approx(0.5)


def test_wait_advances_clock_seconds():
    wait(0.5)
    assert SIM_CLOCK.now() == pytest.approx(0.5)


def test_wait_advances_clock_msec():
    wait(250, MSEC)
    assert SIM_CLOCK.now() == pytest.approx(0.25)


def test_sleep_is_alias_of_wait():
    sleep(100, MSEC)
    assert SIM_CLOCK.now() == pytest.approx(0.1)


def test_wait_records_to_call_log():
    wait(0.1)
    e = CALL_LOG.entries()[-1]
    assert e["method"] == "wait"
    assert e["args"] == [0.1, "sec"]


def test_wait_raises_simulation_timeout_when_budget_exceeded():
    SIM_CLOCK.set_max_time(1.0)
    wait(0.5)
    with pytest.raises(SimulationTimeout):
        wait(0.6)


def test_program_stop_records():
    brain = Brain()
    CALL_LOG.clear()
    brain.program_stop()
    assert CALL_LOG.entries()[0] == {
        "t": 0.0,
        "obj": "brain",
        "method": "program_stop",
        "args": [],
        "kwargs": {},
    }
