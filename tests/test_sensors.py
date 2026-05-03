from __future__ import annotations

import pytest

from vex_sim.api import (
    DEGREES,
    INCHES,
    MM,
    XAXIS,
    YAXIS,
    ZAXIS,
    Brain,
    Bumper,
    Color,
    Distance,
    Inertial,
    LEDStateType,
    ObjectSizeType,
    Optical,
    Ports,
    Triport,
)
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


def test_distance_construction_records():
    Distance(Ports.PORT1)
    e = CALL_LOG.entries()[0]
    assert e["obj"] == "distance_port1"
    assert e["method"] == "Distance"


def test_distance_object_distance_default_mm():
    d = Distance(Ports.PORT1)
    assert d.object_distance() == 1000.0
    assert d.object_distance(MM) == 1000.0


def test_distance_object_distance_inches_converts():
    d = Distance(Ports.PORT1)
    assert d.object_distance(INCHES) == pytest.approx(1000.0 / 25.4)


def test_distance_no_object_detected_default():
    d = Distance(Ports.PORT1)
    assert d.is_object_detected() is False
    assert d.object_velocity() == 0.0
    assert d.object_size() == ObjectSizeType.NEAR


def test_bumper_from_brain_three_wire_port_d():
    brain = Brain()
    CALL_LOG.clear()
    b = Bumper(brain.three_wire_port.d)
    assert b._label == "bumper_3wire_d"
    assert b.pressing() == 0


def test_bumper_from_brain_three_wire_port_f():
    brain = Brain()
    b = Bumper(brain.three_wire_port.f)
    assert b._label == "bumper_3wire_f"


def test_bumper_from_expander_pin():
    expander = Triport(Ports.PORT8)
    b = Bumper(expander.a)
    # Expander pins use a different label format; main thing is pressing() works.
    assert b.pressing() == 0


def test_inertial_no_port_is_brain_builtin():
    i = Inertial()
    assert i._label == "inertial_brain"


def test_inertial_with_port():
    i = Inertial(Ports.PORT5)
    assert i._label == "inertial_port5"


def test_inertial_defaults():
    i = Inertial()
    assert i.heading() == 0.0
    assert i.rotation() == 0.0
    assert i.is_calibrating() is False  # critical: must terminate calibration loop
    assert i.installed() is True


def test_inertial_acceleration_axes():
    i = Inertial()
    assert i.acceleration(XAXIS) == 0.0
    assert i.acceleration(YAXIS) == 0.0
    assert i.acceleration(ZAXIS) == 0.0


def test_inertial_calibrate_records_no_advance():
    i = Inertial()
    SIM_CLOCK.reset()
    i.calibrate()
    assert SIM_CLOCK.now() == 0.0


def test_inertial_orientation_records():
    i = Inertial()
    CALL_LOG.clear()
    i.orientation("pitch", DEGREES)
    e = CALL_LOG.entries()[0]
    assert e["method"] == "orientation"
    assert e["args"] == ["pitch", "deg"]


def test_optical_construction_records():
    Optical(Ports.PORT7)
    e = CALL_LOG.entries()[0]
    assert e["obj"] == "optical_port7"


def test_optical_color_default_is_black():
    o = Optical(Ports.PORT7)
    assert o.color() == Color.BLACK


def test_optical_color_compares_correctly_against_red():
    o = Optical(Ports.PORT7)
    # The student-code idiom: `if o.color() == Color.RED:`
    assert (o.color() == Color.RED) is False


def test_optical_brightness_hue_defaults():
    o = Optical(Ports.PORT7)
    assert o.brightness() == 0
    assert o.hue() == 0
    assert o.is_near_object() is False


def test_optical_set_light_records():
    o = Optical(Ports.PORT7)
    CALL_LOG.clear()
    o.set_light(LEDStateType.ON)
    assert CALL_LOG.entries()[0]["args"] == ["on"]
