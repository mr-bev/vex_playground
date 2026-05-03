"""API surface contract test.

This test pins the public API for phases 2–6. Any signature change here is a
breaking change for student code: parameter names matter (kwarg calls), order
matters (positional calls), and method names must not change.

When a future phase legitimately needs to add a method, add an entry. When a
future phase needs to change a signature, change it knowing that every student
program written against the old signature will break — and update this test
deliberately.
"""

from __future__ import annotations

import inspect

import pytest

from vex_sim.api import (
    Brain,
    Bumper,
    Color,
    Controller,
    Distance,
    DriveTrain,
    Inertial,
    Motor,
    MotorGroup,
    Optical,
    Ports,
    SmartDrive,
    Timer,
    Triport,
    sleep,
    wait,
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


def _params_of(callable_obj) -> list[str]:
    sig = inspect.signature(callable_obj)
    return [name for name in sig.parameters if name not in ("self", "cls")]


# ---------------------------------------------------------------------------
# Class method signatures
# ---------------------------------------------------------------------------

CLASS_SIGNATURES: list[tuple[type, str, list[str]]] = [
    # Brain
    (Brain, "__init__", []),
    (Brain, "program_stop", []),
    # Timer (standalone)
    (Timer, "__init__", []),
    (Timer, "time", ["units"]),
    (Timer, "clear", []),
    (Timer, "event", ["callback", "delay", "arg"]),
    # Triport
    (Triport, "__init__", ["port"]),
    (Triport, "index", []),
    # Motor
    (Motor, "__init__", ["port", "gears", "reverse"]),
    (Motor, "spin", ["direction", "velocity", "units"]),
    (Motor, "spin_for", ["direction", "angle", "units", "velocity", "units_v", "wait"]),
    (Motor, "spin_to_position", ["rotation", "units", "velocity", "units_v", "wait"]),
    (Motor, "stop", ["mode"]),
    (Motor, "set_position", ["position", "units"]),
    (Motor, "set_velocity", ["velocity", "units"]),
    (Motor, "set_stopping", ["mode"]),
    (Motor, "set_max_torque", ["value", "units"]),
    (Motor, "set_timeout", ["value", "units"]),
    (Motor, "set_reversed", ["value"]),
    (Motor, "reset_position", []),
    (Motor, "is_done", []),
    (Motor, "is_spinning", []),
    (Motor, "position", ["units"]),
    (Motor, "velocity", ["units"]),
    (Motor, "current", ["units"]),
    (Motor, "power", ["units"]),
    (Motor, "torque", ["units"]),
    (Motor, "efficiency", ["units"]),
    (Motor, "temperature", ["units"]),
    (Motor, "get_timeout", []),
    # MotorGroup
    (MotorGroup, "__init__", ["motors"]),
    (MotorGroup, "count", []),
    (MotorGroup, "spin", ["direction", "velocity", "units"]),
    (MotorGroup, "spin_for", ["direction", "angle", "units", "velocity", "units_v", "wait"]),
    (MotorGroup, "spin_to_position", ["rotation", "units", "velocity", "units_v", "wait"]),
    (MotorGroup, "stop", ["mode"]),
    (MotorGroup, "set_position", ["position", "units"]),
    (MotorGroup, "set_velocity", ["velocity", "units"]),
    (MotorGroup, "set_stopping", ["mode"]),
    (MotorGroup, "set_max_torque", ["value", "units"]),
    (MotorGroup, "set_timeout", ["value", "units"]),
    (MotorGroup, "is_done", []),
    (MotorGroup, "is_spinning", []),
    (MotorGroup, "position", ["units"]),
    (MotorGroup, "velocity", ["units"]),
    (MotorGroup, "current", ["units"]),
    (MotorGroup, "power", ["units"]),
    (MotorGroup, "torque", ["units"]),
    (MotorGroup, "efficiency", ["units"]),
    (MotorGroup, "temperature", ["units"]),
    # DriveTrain
    (
        DriveTrain,
        "__init__",
        ["lm", "rm", "wheelTravel", "trackWidth", "wheelBase", "units", "externalGearRatio"],
    ),
    (DriveTrain, "drive", ["direction", "velocity", "units"]),
    (
        DriveTrain,
        "drive_for",
        ["direction", "distance", "units", "velocity", "units_v", "wait"],
    ),
    (DriveTrain, "turn", ["direction", "velocity", "units"]),
    (DriveTrain, "turn_for", ["direction", "angle", "units", "velocity", "units_v", "wait"]),
    (DriveTrain, "turn_to_heading", ["angle", "units", "velocity", "units_v", "wait"]),
    (DriveTrain, "turn_to_rotation", ["angle", "units", "velocity", "units_v", "wait"]),
    (DriveTrain, "stop", ["mode"]),
    (DriveTrain, "calibrate_drivetrain", []),
    (DriveTrain, "set_drive_velocity", ["velocity", "units"]),
    (DriveTrain, "set_turn_velocity", ["velocity", "units"]),
    (DriveTrain, "set_stopping", ["mode"]),
    (DriveTrain, "set_timeout", ["value", "units"]),
    (DriveTrain, "set_heading", ["heading", "units"]),
    (DriveTrain, "set_rotation", ["rotation", "units"]),
    (DriveTrain, "set_turn_threshold", ["value"]),
    (DriveTrain, "set_turn_constant", ["value"]),
    (DriveTrain, "set_turn_direction_reverse", ["value"]),
    (DriveTrain, "is_done", []),
    (DriveTrain, "is_moving", []),
    (DriveTrain, "heading", ["units"]),
    (DriveTrain, "rotation", ["units"]),
    (DriveTrain, "velocity", ["units"]),
    (DriveTrain, "current", ["units"]),
    (DriveTrain, "power", ["units"]),
    (DriveTrain, "torque", ["units"]),
    (DriveTrain, "efficiency", ["units"]),
    (DriveTrain, "temperature", ["units"]),
    (DriveTrain, "get_timeout", []),
    # SmartDrive (extends DriveTrain with a gyro positional arg)
    (
        SmartDrive,
        "__init__",
        ["lm", "rm", "g", "wheelTravel", "trackWidth", "wheelBase", "units", "externalGearRatio"],
    ),
    # Distance
    (Distance, "__init__", ["smartport", "mount_height"]),
    (Distance, "object_distance", ["units"]),
    (Distance, "object_velocity", []),
    (Distance, "object_size", []),
    (Distance, "is_object_detected", []),
    (Distance, "changed", ["callback", "arg"]),
    # Bumper
    (Bumper, "__init__", ["port"]),
    (Bumper, "pressing", []),
    (Bumper, "pressed", ["callback", "arg"]),
    (Bumper, "released", ["callback", "arg"]),
    # Inertial
    (Inertial, "__init__", ["smartport"]),
    (Inertial, "heading", ["units"]),
    (Inertial, "rotation", ["units"]),
    (Inertial, "gyro_rate", ["axis", "units"]),
    (Inertial, "orientation", ["type", "units"]),
    (Inertial, "acceleration", ["axis"]),
    (Inertial, "calibrate", []),
    (Inertial, "is_calibrating", []),
    (Inertial, "installed", []),
    (Inertial, "set_heading", ["value", "units"]),
    (Inertial, "set_rotation", ["value", "units"]),
    (Inertial, "reset_heading", []),
    (Inertial, "reset_rotation", []),
    (Inertial, "set_turn_type", ["turntype"]),
    (Inertial, "get_turn_type", []),
    (Inertial, "changed", ["callback", "arg"]),
    (Inertial, "collision", ["callback", "arg"]),
    # Optical
    (Optical, "__init__", ["smartport"]),
    (Optical, "set_light", ["state"]),
    (Optical, "set_light_power", ["percent", "units"]),
    (Optical, "is_near_object", []),
    (Optical, "color", []),
    (Optical, "brightness", []),
    (Optical, "hue", []),
    (Optical, "object_detected", ["callback", "arg"]),
    (Optical, "object_lost", ["callback", "arg"]),
    # Controller
    (Controller, "__init__", []),
]


@pytest.mark.parametrize("klass,method,expected", CLASS_SIGNATURES)
def test_class_method_signature(klass, method, expected):
    fn = getattr(klass, method)
    actual = _params_of(fn)
    assert actual == expected, f"{klass.__name__}.{method}: expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# Top-level functions
# ---------------------------------------------------------------------------

TOP_LEVEL_SIGNATURES: list[tuple[str, callable, list[str]]] = [
    ("wait", wait, ["time", "units"]),
    ("sleep", sleep, ["time", "units"]),
]


@pytest.mark.parametrize("name,fn,expected", TOP_LEVEL_SIGNATURES)
def test_top_level_signature(name, fn, expected):
    actual = _params_of(fn)
    assert actual == expected, f"{name}: expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# Brain sub-object methods (instance attribute paths)
# ---------------------------------------------------------------------------


def _build_brain_for_introspection() -> Brain:
    return Brain()


BRAIN_SUB_SIGNATURES: list[tuple[tuple[str, ...], list[str]]] = [
    # battery
    (("battery", "voltage"), ["units"]),
    (("battery", "current"), []),
    (("battery", "capacity"), []),
    # button
    (("button", "pressing"), []),
    (("button", "pressed"), ["callback", "arg"]),
    (("button", "released"), ["callback", "arg"]),
    # timer
    (("timer", "time"), ["units"]),
    (("timer", "clear"), []),
    (("timer", "event"), ["callback", "delay", "arg"]),
    (("timer", "system"), []),
    (("timer", "system_high_res"), []),
    # screen
    (("screen", "print"), ["args", "sep", "precision"]),
    (("screen", "print_at"), ["text", "x", "y", "sep", "precision", "opaque"]),
    (("screen", "next_row"), []),
    (("screen", "clear_screen"), ["color"]),
    (("screen", "clear_row"), ["row", "color"]),
    (("screen", "row"), []),
    (("screen", "column"), []),
    (("screen", "get_string_width"), ["string"]),
    (("screen", "get_string_height"), ["string"]),
    (("screen", "set_cursor"), ["row", "column"]),
    (("screen", "set_font"), ["fontname"]),
    (("screen", "set_pen_width"), ["width"]),
    (("screen", "set_pen_color"), ["color"]),
    (("screen", "set_fill_color"), ["color"]),
    (("screen", "draw_pixel"), ["x", "y"]),
    (("screen", "draw_line"), ["x1", "y1", "x2", "y2"]),
    (("screen", "draw_rectangle"), ["x", "y", "width", "height", "color"]),
    (("screen", "draw_circle"), ["x", "y", "radius", "color"]),
    (("screen", "draw_image_from_file"), ["filename", "x", "y"]),
    (("screen", "render"), []),
    (("screen", "set_origin"), ["x", "y"]),
    (("screen", "set_clip_region"), ["x", "y", "width", "height"]),
]


@pytest.mark.parametrize("path,expected", BRAIN_SUB_SIGNATURES)
def test_brain_sub_object_signature(path: tuple[str, ...], expected: list[str]):
    brain = _build_brain_for_introspection()
    obj = brain
    for attr in path[:-1]:
        obj = getattr(obj, attr)
    method = getattr(obj, path[-1])
    actual = _params_of(method)
    assert actual == expected, f"brain.{'.'.join(path)}: expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# Brain.three_wire_port pins
# ---------------------------------------------------------------------------


def test_brain_three_wire_port_has_pins_a_through_h():
    brain = Brain()
    for letter in "abcdefgh":
        assert hasattr(brain.three_wire_port, letter), f"missing pin {letter}"


def test_triport_has_pins_a_through_h():
    tp = Triport(Ports.PORT5)
    for letter in "abcdefgh":
        assert hasattr(tp, letter)


# ---------------------------------------------------------------------------
# Controller buttons and axes
# ---------------------------------------------------------------------------


CONTROLLER_BUTTONS = [
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
]
CONTROLLER_AXES = ["axis1", "axis2", "axis3", "axis4"]


@pytest.mark.parametrize("name", CONTROLLER_BUTTONS)
def test_controller_has_button(name):
    c = Controller()
    btn = getattr(c, name)
    assert _params_of(btn.pressing) == []
    assert _params_of(btn.pressed) == ["callback", "arg"]
    assert _params_of(btn.released) == ["callback", "arg"]


@pytest.mark.parametrize("name", CONTROLLER_AXES)
def test_controller_has_axis(name):
    c = Controller()
    ax = getattr(c, name)
    assert _params_of(ax.position) == []
    assert _params_of(ax.changed) == ["callback", "arg"]


# ---------------------------------------------------------------------------
# Enums and bare-name exports
# ---------------------------------------------------------------------------

PORTS_REQUIRED = [f"PORT{i}" for i in range(1, 22)]


@pytest.mark.parametrize("name", PORTS_REQUIRED)
def test_ports_member_exists(name):
    assert hasattr(Ports, name)


COLOR_REQUIRED = [
    "RED",
    "GREEN",
    "BLUE",
    "WHITE",
    "YELLOW",
    "ORANGE",
    "PURPLE",
    "CYAN",
    "BLACK",
    "TRANSPARENT",
]


@pytest.mark.parametrize("name", COLOR_REQUIRED)
def test_color_member_exists(name):
    assert hasattr(Color, name)


BARE_NAME_EXPORTS = [
    "FORWARD",
    "REVERSE",
    "LEFT",
    "RIGHT",
    "COAST",
    "BRAKE",
    "HOLD",
    "MM",
    "INCHES",
    "IN",
    "DEGREES",
    "TURNS",
    "RAW",
    "PERCENT",
    "RPM",
    "DPS",
    "SECONDS",
    "SEC",
    "MSEC",
    "MV",
    "VOLT",
    "XAXIS",
    "YAXIS",
    "ZAXIS",
    "PITCH",
    "ROLL",
    "YAW",
]


@pytest.mark.parametrize("name", BARE_NAME_EXPORTS)
def test_bare_name_export_exists(name):
    from vex_sim import api

    assert hasattr(api, name), f"vex_sim.api.{name} missing"
    # And it must be in __all__ so `from vex import *` picks it up.
    assert name in api.__all__, f"{name} not in api.__all__"


PUBLIC_CLASSES = [
    "Brain",
    "Bumper",
    "Controller",
    "Distance",
    "DriveTrain",
    "Inertial",
    "Motor",
    "MotorGroup",
    "Optical",
    "SmartDrive",
    "Timer",
    "Triport",
]


@pytest.mark.parametrize("name", PUBLIC_CLASSES)
def test_public_class_in_all(name):
    from vex_sim import api

    assert name in api.__all__
    assert hasattr(api, name)


def test_top_level_functions_exported():
    from vex_sim import api

    for name in ("wait", "sleep"):
        assert name in api.__all__
        assert callable(getattr(api, name))
