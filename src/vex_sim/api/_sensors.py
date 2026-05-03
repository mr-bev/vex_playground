from __future__ import annotations

from collections.abc import Callable

from vex_sim.api._brain import _callback_name, _Recorder, _TriPin
from vex_sim.api._enums import (
    AxisType,
    Color,
    DistanceUnits,
    LEDStateType,
    ObjectSizeType,
    OrientationType,
    RotationUnits,
    TurnType,
    VelocityUnits,
)


def _distance_default(units: str) -> float:
    """Default object distance is 1000 mm; convert if inches requested."""
    if units in (DistanceUnits.IN, DistanceUnits.INCHES):
        return 1000.0 / 25.4
    return 1000.0


class Distance(_Recorder):
    def __init__(self, smartport: int) -> None:
        self._port = smartport
        self._label = f"distance_port{smartport}"
        self._record("Distance", (smartport,))

    def object_distance(self, units: str = DistanceUnits.MM) -> float:
        self._record("object_distance", (units,))
        return _distance_default(units)

    def object_velocity(self) -> float:
        self._record("object_velocity")
        return 0.0

    def object_size(self) -> str:
        self._record("object_size")
        return ObjectSizeType.NEAR

    def is_object_detected(self) -> bool:
        self._record("is_object_detected")
        return False

    def changed(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("changed", (), {"callback": _callback_name(callback), "arg": arg})


class Bumper(_Recorder):
    def __init__(self, port: _TriPin) -> None:
        # `port` is expected to be a _TriPin from brain.three_wire_port.<a-h>
        # or Triport(...).<a-h>. We label by the pin's source label suffix.
        source = getattr(port, "_label", None)
        letter = getattr(port, "_letter", None)
        if source and source.startswith("brain.three_wire_port.") and letter:
            self._label = f"bumper_3wire_{letter}"
        elif source and letter:
            # Expander-style label: bumper_<source-without-trailing-letter>_<letter>
            self._label = f"bumper_{source.replace('.', '_')}"
        else:
            self._label = f"bumper_{source or 'unknown'}"
        self._record("Bumper", (source,))

    def pressing(self) -> int:
        self._record("pressing")
        return 0

    def pressed(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("pressed", (), {"callback": _callback_name(callback), "arg": arg})

    def released(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("released", (), {"callback": _callback_name(callback), "arg": arg})


class Inertial(_Recorder):
    def __init__(self, smartport: int | None = None) -> None:
        self._port = smartport
        if smartport is None:
            self._label = "inertial_brain"
        else:
            self._label = f"inertial_port{smartport}"
        self._record("Inertial", () if smartport is None else (smartport,))

    def heading(self, units: str = RotationUnits.DEG) -> float:
        self._record("heading", (units,))
        return 0.0

    def rotation(self, units: str = RotationUnits.DEG) -> float:
        self._record("rotation", (units,))
        return 0.0

    def gyro_rate(self, axis: str, units: str = VelocityUnits.DPS) -> float:
        self._record("gyro_rate", (axis, units))
        return 0.0

    def orientation(self, type: str, units: str = RotationUnits.DEG) -> float:
        self._record("orientation", (type, units))
        return 0.0

    def acceleration(self, axis: str) -> float:
        self._record("acceleration", (axis,))
        return 0.0

    def calibrate(self) -> None:
        self._record("calibrate")

    def is_calibrating(self) -> bool:
        self._record("is_calibrating")
        return False

    def installed(self) -> bool:
        self._record("installed")
        return True

    def set_heading(self, value: float, units: str = RotationUnits.DEG) -> None:
        self._record("set_heading", (value, units))

    def set_rotation(self, value: float, units: str = RotationUnits.DEG) -> None:
        self._record("set_rotation", (value, units))

    def reset_heading(self) -> None:
        self._record("reset_heading")

    def reset_rotation(self) -> None:
        self._record("reset_rotation")

    def set_turn_type(self, turntype: str) -> None:
        self._record("set_turn_type", (turntype,))

    def get_turn_type(self) -> str:
        self._record("get_turn_type")
        return TurnType.RIGHT

    def changed(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("changed", (), {"callback": _callback_name(callback), "arg": arg})

    def collision(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("collision", (), {"callback": _callback_name(callback), "arg": arg})

    # Suppress unused-variable warning for the parameter named `type`
    # (matches the official VEX API parameter name).
    _ = AxisType, OrientationType  # keep imports referenced


class Optical(_Recorder):
    def __init__(self, smartport: int) -> None:
        self._port = smartport
        self._label = f"optical_port{smartport}"
        self._record("Optical", (smartport,))

    def set_light(self, state: str) -> None:
        self._record("set_light", (state,))

    def set_light_power(self, percent: float, units: str = VelocityUnits.PERCENT) -> None:
        self._record("set_light_power", (percent, units))

    def is_near_object(self) -> bool:
        self._record("is_near_object")
        return False

    def color(self) -> str:
        self._record("color")
        return Color.BLACK

    def brightness(self) -> int:
        self._record("brightness")
        return 0

    def hue(self) -> int:
        self._record("hue")
        return 0

    def object_detected(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("object_detected", (), {"callback": _callback_name(callback), "arg": arg})

    def object_lost(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("object_lost", (), {"callback": _callback_name(callback), "arg": arg})

    _ = LEDStateType  # imported for documentation, used by callers
