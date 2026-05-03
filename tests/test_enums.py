from __future__ import annotations

from vex_sim.api import _enums


def test_ports_full_range():
    assert _enums.Ports.PORT1 == 1
    assert _enums.Ports.PORT21 == 21


def test_direction_type_values():
    assert _enums.DirectionType.FORWARD == "forward"
    assert _enums.DirectionType.REVERSE == "reverse"


def test_turn_type_values():
    assert _enums.TurnType.LEFT == "left"
    assert _enums.TurnType.RIGHT == "right"


def test_distance_units_inches_alias():
    assert _enums.DistanceUnits.IN == _enums.DistanceUnits.INCHES == "in"


def test_rotation_units_bare_export_uses_friendly_names():
    assert _enums.DEGREES == _enums.RotationUnits.DEG
    assert _enums.TURNS == _enums.RotationUnits.REV


def test_time_units_seconds_alias():
    assert _enums.SECONDS == _enums.SEC == _enums.TimeUnits.SEC == "sec"
    assert _enums.MSEC == _enums.TimeUnits.MSEC == "msec"


def test_axis_type_bare_exports():
    assert _enums.XAXIS == _enums.AxisType.XAXIS == "x"
    assert _enums.YAXIS == "y"
    assert _enums.ZAXIS == "z"


def test_color_members():
    expected = {
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
    }
    actual = {name for name in dir(_enums.Color) if not name.startswith("_")}
    assert expected.issubset(actual)
    assert _enums.Color.RED == "red"
    assert _enums.Color.BLACK == "black"


def test_color_red_distinct_from_green():
    assert _enums.Color.RED != _enums.Color.GREEN


def test_brake_type_bare_exports():
    assert _enums.COAST == _enums.BrakeType.COAST
    assert _enums.BRAKE == _enums.BrakeType.BRAKE
    assert _enums.HOLD == _enums.BrakeType.HOLD


def test_velocity_units_bare_exports():
    assert _enums.PERCENT == _enums.VelocityUnits.PERCENT
    assert _enums.RPM == _enums.VelocityUnits.RPM
    assert _enums.DPS == _enums.VelocityUnits.DPS


def test_voltage_units_bare_exports():
    assert _enums.MV == _enums.VoltageUnits.MV
    assert _enums.VOLT == _enums.VoltageUnits.VOLT


def test_gear_setting_values():
    assert _enums.GearSetting.RATIO_18_1 == "18:1"
    assert _enums.GearSetting.RATIO_36_1 == "36:1"
    assert _enums.GearSetting.RATIO_6_1 == "6:1"


def test_object_size_type_values():
    assert _enums.ObjectSizeType.NEAR == "near"
    assert _enums.ObjectSizeType.LARGE == "large"


def test_led_state_type_values():
    assert _enums.LEDStateType.ON == "on"
    assert _enums.LEDStateType.OFF == "off"


def test_temperature_units_values():
    assert _enums.TemperatureUnits.CELSIUS == "celsius"
    assert _enums.TemperatureUnits.FAHRENHEIT == "fahrenheit"
