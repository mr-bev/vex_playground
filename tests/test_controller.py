from __future__ import annotations

import pytest

from vex_sim.api import Controller
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()


def test_controller_has_all_buttons():
    c = Controller()
    for name in (
        "buttonA",
        "buttonB",
        "buttonUp",
        "buttonDown",
        "buttonL1",
        "buttonL2",
        "buttonL3",
        "buttonR1",
        "buttonR2",
        "buttonR3",
    ):
        assert hasattr(c, name), f"missing {name}"


def test_controller_has_all_axes():
    c = Controller()
    for name in ("axis1", "axis2", "axis3", "axis4"):
        assert hasattr(c, name)


def test_controller_button_pressing_default():
    c = Controller()
    assert c.buttonA.pressing() == 0
    assert c.buttonR2.pressing() == 0


def test_controller_axis_position_default():
    c = Controller()
    assert c.axis1.position() == 0
    assert c.axis3.position() == 0


def test_controller_button_pressed_records_callback_name():
    c = Controller()
    CALL_LOG.clear()

    def on_a():
        pass

    c.buttonA.pressed(on_a)
    e = CALL_LOG.entries()[0]
    assert e["obj"] == "controller.buttonA"
    assert e["method"] == "pressed"
    assert e["kwargs"]["callback"] == "on_a"


def test_controller_axis_changed_records():
    c = Controller()
    CALL_LOG.clear()

    def on_change():
        pass

    c.axis2.changed(on_change)
    e = CALL_LOG.entries()[0]
    assert e["obj"] == "controller.axis2"
    assert e["method"] == "changed"


def test_controller_remote_control_code_enabled_default_true():
    c = Controller()
    assert c.remote_control_code_enabled is True
