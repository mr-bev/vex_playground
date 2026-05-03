from __future__ import annotations

import pytest

from vex_sim.api import (
    DEGREES,
    FORWARD,
    INCHES,
    LEFT,
    MM,
    PERCENT,
    REVERSE,
    RIGHT,
    Ports,
)
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._drivetrain import DriveTrain, SmartDrive
from vex_sim.api._motor import Motor


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()


def _make_drivetrain() -> DriveTrain:
    lm = Motor(Ports.PORT6, False)
    rm = Motor(Ports.PORT10, True)
    return DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)


def test_drivetrain_construction_records():
    dt = _make_drivetrain()
    methods = [(e["obj"], e["method"]) for e in CALL_LOG.entries()]
    assert ("drivetrain", "DriveTrain") in methods
    assert dt._drive_velocity == 50


def test_smartdrive_construction_records_with_gyro():
    from vex_sim.api._brain import Brain

    brain = Brain()
    lm = Motor(Ports.PORT6, False)
    rm = Motor(Ports.PORT10, True)

    # Inertial isn't implemented yet — pass a dummy with _label.
    class DummyGyro:
        _label = "inertial_brain"

    SmartDrive(lm, rm, DummyGyro(), 259.34, 320, 40, MM, 1)
    methods = [(e["obj"], e["method"]) for e in CALL_LOG.entries()]
    assert ("drivetrain", "SmartDrive") in methods
    _ = brain  # silence unused


def test_drive_does_not_advance_clock():
    dt = _make_drivetrain()
    dt.drive(FORWARD)
    assert SIM_CLOCK.now() == 0.0


def test_drive_for_advances_clock_based_on_distance():
    dt = _make_drivetrain()
    # 200 mm at 100% (200 mm/s) = 1s
    dt.drive_for(FORWARD, 200, MM, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_drive_for_default_velocity_is_50_pct():
    dt = _make_drivetrain()
    # 200 mm at 50% (100 mm/s) = 2s
    dt.drive_for(FORWARD, 200, MM)
    assert SIM_CLOCK.now() == pytest.approx(2.0)


def test_drive_for_inches_converts():
    dt = _make_drivetrain()
    # 1 inch = 25.4 mm; at 100% = 25.4/200 s
    dt.drive_for(FORWARD, 1, INCHES, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(25.4 / 200.0)


def test_drive_for_wait_false_does_not_advance():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 200, MM, wait=False)
    assert SIM_CLOCK.now() == 0.0


def test_set_drive_velocity_changes_default():
    dt = _make_drivetrain()
    dt.set_drive_velocity(100, PERCENT)
    dt.drive_for(FORWARD, 200, MM)
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_turn_for_advances_based_on_angle():
    dt = _make_drivetrain()
    # 90 deg at 100% (90 deg/s) = 1s
    dt.turn_for(LEFT, 90, DEGREES, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_turn_for_records_direction():
    dt = _make_drivetrain()
    CALL_LOG.clear()
    dt.turn_for(RIGHT, 90, DEGREES)
    e = CALL_LOG.entries()[0]
    assert e["method"] == "turn_for"
    assert e["args"][0] == "right"


def test_turn_to_heading_fixed_advance():
    dt = _make_drivetrain()
    dt.turn_to_heading(90, DEGREES, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_drive_for_reverse_direction_recorded():
    dt = _make_drivetrain()
    CALL_LOG.clear()
    dt.drive_for(REVERSE, 100, MM, wait=False)
    e = CALL_LOG.entries()[0]
    assert e["args"][0] == "reverse"


def test_drivetrain_getters_return_defaults():
    dt = _make_drivetrain()
    assert dt.heading() == 0.0
    assert dt.rotation() == 0.0
    assert dt.is_done() is True
    assert dt.is_moving() is False


def test_stop_with_no_arg_records_no_args():
    dt = _make_drivetrain()
    CALL_LOG.clear()
    dt.stop()
    e = CALL_LOG.entries()[0]
    assert e["method"] == "stop"
    assert e["args"] == []
