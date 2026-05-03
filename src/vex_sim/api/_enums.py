"""VEX EXP enums and unit sentinels.

Mirrors the API style of the real VEX runtime: plain classes with class
attributes (not enum.Enum), so `if x == DirectionType.FORWARD:` works against
the string values used internally and in the call log.

Bare-name exports (FORWARD, MM, DEGREES, etc.) are flowed up to api/__init__.py
so `from vex import *` in student code resolves them unqualified.
"""

from __future__ import annotations


class Ports:
    pass


for _i in range(1, 22):
    setattr(Ports, f"PORT{_i}", _i)


class GearSetting:
    RATIO_18_1 = "18:1"
    RATIO_36_1 = "36:1"
    RATIO_6_1 = "6:1"


class DirectionType:
    FORWARD = "forward"
    REVERSE = "reverse"


class TurnType:
    LEFT = "left"
    RIGHT = "right"


class BrakeType:
    COAST = "coast"
    BRAKE = "brake"
    HOLD = "hold"


class DistanceUnits:
    MM = "mm"
    IN = "in"
    INCHES = "in"


class RotationUnits:
    DEG = "deg"
    REV = "rev"
    RAW = "raw"


class VelocityUnits:
    PERCENT = "percent"
    RPM = "rpm"
    DPS = "dps"


class TimeUnits:
    SEC = "sec"
    MSEC = "msec"


class VoltageUnits:
    MV = "mv"
    VOLT = "volt"


class CurrentUnits:
    AMP = "amp"


class PowerUnits:
    WATT = "watt"


class TorqueUnits:
    NM = "nm"
    INLB = "inlb"


class TemperatureUnits:
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"


class AxisType:
    XAXIS = "x"
    YAXIS = "y"
    ZAXIS = "z"


class OrientationType:
    PITCH = "pitch"
    ROLL = "roll"
    YAW = "yaw"


class LEDStateType:
    ON = "on"
    OFF = "off"


class ObjectSizeType:
    NEAR = "near"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class Color:
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    WHITE = "white"
    YELLOW = "yellow"
    ORANGE = "orange"
    PURPLE = "purple"
    CYAN = "cyan"
    BLACK = "black"
    TRANSPARENT = "transparent"


# Bare-name exports for `from vex import *`. Same string values as the enum
# attributes — a student writing `set_drive_velocity(20, PERCENT)` and one
# writing `set_drive_velocity(20, VelocityUnits.PERCENT)` produce identical
# call-log entries.
FORWARD = DirectionType.FORWARD
REVERSE = DirectionType.REVERSE

LEFT = TurnType.LEFT
RIGHT = TurnType.RIGHT

COAST = BrakeType.COAST
BRAKE = BrakeType.BRAKE
HOLD = BrakeType.HOLD

MM = DistanceUnits.MM
IN = DistanceUnits.IN
INCHES = DistanceUnits.INCHES

DEGREES = RotationUnits.DEG
TURNS = RotationUnits.REV
RAW = RotationUnits.RAW

PERCENT = VelocityUnits.PERCENT
RPM = VelocityUnits.RPM
DPS = VelocityUnits.DPS

SECONDS = TimeUnits.SEC
SEC = TimeUnits.SEC
MSEC = TimeUnits.MSEC

MV = VoltageUnits.MV
VOLT = VoltageUnits.VOLT

XAXIS = AxisType.XAXIS
YAXIS = AxisType.YAXIS
ZAXIS = AxisType.ZAXIS

PITCH = OrientationType.PITCH
ROLL = OrientationType.ROLL
YAW = OrientationType.YAW
