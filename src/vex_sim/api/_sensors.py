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
from vex_sim.sensors_world import (
    SENSOR_CACHE,
    default_bumper_offset,
)


def _mm_to_units(distance_mm: float, units: str) -> float:
    if units in (DistanceUnits.IN, DistanceUnits.INCHES):
        return distance_mm / 25.4
    return distance_mm


class Distance(_Recorder):
    """Forward-facing distance sensor mounted on the robot's front face.

    Parameters
    ----------
    smartport:
        Smart-port index, like the real VEX EXP API.
    mount_height:
        Sensor mount height above the floor, in mm. Walls shorter than
        this height are *invisible* to this sensor -- the ray-cast
        filters them out before measuring. Defaults to 100 mm, which is
        a typical chassis-mid mounting that sees mid- and tall-height
        walls but skips the 30 mm "low" markers.

    Mount-height interaction with wall heights
    -----------------------------------------

    The simulator is 2D but tracks wall heights so the classroom lesson
    "your sensor can only see what its mount can reach" still applies::

        # 30 mm wall, 100 mm sensor: the wall is below the beam line.
        d = Distance(Ports.PORT1, mount_height=100)  # default
        # Driving forward at this wall, d.object_distance() stays at the
        # 1000 mm "no object" sentinel -- the bumper still triggers on
        # contact, but the distance sensor never sees it coming.

        # Same 30 mm wall, low-mounted sensor:
        d_low = Distance(Ports.PORT1, mount_height=20)
        # Now d_low.object_distance() decreases as the robot approaches.

    Bumpers ignore height entirely -- they sit at floor level and fire
    on every wall regardless of how short.
    """

    def __init__(self, smartport: int, mount_height: float = 100.0) -> None:
        self._port = smartport
        self._mount_height_mm = float(mount_height)
        self._label = f"distance_port{smartport}"
        SENSOR_CACHE.register_distance(self._label, self._mount_height_mm)
        self._record("Distance", (smartport,), {"mount_height": self._mount_height_mm})

    def object_distance(self, units: str = DistanceUnits.MM) -> float:
        self._record("object_distance", (units,))
        return _mm_to_units(SENSOR_CACHE.distance_mm.get(self._label, 1000.0), units)

    def object_velocity(self) -> float:
        self._record("object_velocity")
        return 0.0

    def object_size(self) -> str:
        self._record("object_size")
        return ObjectSizeType.NEAR

    def is_object_detected(self) -> bool:
        self._record("is_object_detected")
        # Anything closer than the no-object sentinel counts as a detection.
        return SENSOR_CACHE.distance_mm.get(self._label, 1000.0) < 1000.0

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
        forward, left = default_bumper_offset(self._label)
        SENSOR_CACHE.register_bumper(self._label, forward, left)
        self._record("Bumper", (source,))

    def pressing(self) -> int:
        self._record("pressing")
        return 1 if SENSOR_CACHE.bumper_pressed.get(self._label, False) else 0

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
        SENSOR_CACHE.register_optical(self._label)
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
        return SENSOR_CACHE.optical_color.get(self._label, Color.BLACK)

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
