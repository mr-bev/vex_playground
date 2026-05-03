from __future__ import annotations

import pytest

from vex_sim.api import (
    DEGREES,
    FORWARD,
    PERCENT,
    REVERSE,
    SECONDS,
    TURNS,
    GearSetting,
    Ports,
)
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._motor import Motor, MotorGroup


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()


def test_motor_constructor_two_arg_form_takes_reverse():
    m = Motor(Ports.PORT6, False)
    assert m._reverse is False
    assert m._gears == GearSetting.RATIO_18_1


def test_motor_constructor_two_arg_form_reverse_true():
    m = Motor(Ports.PORT10, True)
    assert m._reverse is True


def test_motor_constructor_three_arg_form():
    m = Motor(Ports.PORT3, GearSetting.RATIO_36_1, True)
    assert m._gears == GearSetting.RATIO_36_1
    assert m._reverse is True


def test_motor_construction_records_label():
    Motor(Ports.PORT1, False)
    e = CALL_LOG.entries()[0]
    assert e["obj"] == "motor_port1"
    assert e["method"] == "Motor"


def test_motor_spin_for_advances_clock_at_default_velocity():
    m = Motor(Ports.PORT1, False)
    CALL_LOG.clear()
    m.spin_for(FORWARD, 360, DEGREES)  # 1 rev at 50% = 2s
    assert SIM_CLOCK.now() == pytest.approx(2.0)


def test_motor_spin_for_at_explicit_velocity():
    m = Motor(Ports.PORT1, False)
    m.spin_for(FORWARD, 360, DEGREES, velocity=100)  # 1 rev at 100% = 1s
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_motor_spin_for_with_wait_false_does_not_advance():
    m = Motor(Ports.PORT1, False)
    m.spin_for(FORWARD, 360, DEGREES, wait=False)
    assert SIM_CLOCK.now() == 0.0


def test_motor_spin_for_units_revolutions():
    m = Motor(Ports.PORT1, False)
    m.spin_for(FORWARD, 2, TURNS, velocity=100)  # 2 rev at 100% = 2s
    assert SIM_CLOCK.now() == pytest.approx(2.0)


def test_motor_spin_for_units_seconds():
    m = Motor(Ports.PORT1, False)
    m.spin_for(FORWARD, 1.5, SECONDS, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(1.5)


def test_motor_spin_to_position_fixed_advance():
    m = Motor(Ports.PORT1, False)
    m.spin_to_position(180, DEGREES)
    assert SIM_CLOCK.now() == pytest.approx(0.5)


def test_motor_spin_does_not_advance_clock():
    m = Motor(Ports.PORT1, False)
    m.spin(FORWARD)
    assert SIM_CLOCK.now() == 0.0


def test_motor_set_velocity_persists():
    m = Motor(Ports.PORT1, False)
    m.set_velocity(100, PERCENT)
    m.spin_for(FORWARD, 360, DEGREES)  # at 100% should be 1s
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_motor_stop_records():
    m = Motor(Ports.PORT1, False)
    CALL_LOG.clear()
    m.stop()
    assert CALL_LOG.entries()[0]["method"] == "stop"


def test_motor_getters_return_defaults():
    m = Motor(Ports.PORT1, False)
    assert m.position() == 0.0
    assert m.velocity() == 0.0
    assert m.is_done() is True
    assert m.is_spinning() is False
    assert m.temperature() == 25.0


def test_motor_spin_for_reverse_direction_recorded():
    m = Motor(Ports.PORT1, False)
    CALL_LOG.clear()
    m.spin_for(REVERSE, 90, DEGREES)
    e = CALL_LOG.entries()[0]
    assert e["args"][0] == "reverse"


def test_motor_group_count():
    m1 = Motor(Ports.PORT1, False)
    m2 = Motor(Ports.PORT2, False)
    g = MotorGroup(m1, m2)
    assert g.count() == 2


def test_motor_group_spin_for_advances_clock():
    m1 = Motor(Ports.PORT1, False)
    m2 = Motor(Ports.PORT2, False)
    g = MotorGroup(m1, m2)
    g.spin_for(FORWARD, 360, DEGREES, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(1.0)
