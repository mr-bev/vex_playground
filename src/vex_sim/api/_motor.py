from __future__ import annotations

from typing import Any

from vex_sim.api._brain import _Recorder
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._enums import (
    BrakeType,
    CurrentUnits,
    GearSetting,
    PowerUnits,
    RotationUnits,
    TemperatureUnits,
    TimeUnits,
    TorqueUnits,
    VelocityUnits,
)


def _spin_seconds(amount: float, units: str, velocity_pct: float) -> float:
    """Stub time advancement for spin_for. 100% velocity = 1 rev/sec."""
    if units == TimeUnits.SEC:
        return float(amount)
    if units == TimeUnits.MSEC:
        return float(amount) / 1000.0
    revolutions = float(amount) if units == RotationUnits.REV else float(amount) / 360.0
    if velocity_pct <= 0:
        return 0.0
    return revolutions / (velocity_pct / 100.0)


class Motor(_Recorder):
    def __init__(
        self,
        port: int,
        gears: Any = GearSetting.RATIO_18_1,
        reverse: bool = False,
    ) -> None:
        # Real student code uses the 2-arg form Motor(port, False) where the
        # second positional is `reverse`. Type-dispatch on `gears`: a bool
        # there means the caller meant `reverse`.
        if isinstance(gears, bool):
            self._gears = GearSetting.RATIO_18_1
            self._reverse = gears
        else:
            self._gears = gears
            self._reverse = reverse
        self._port = port
        self._label = f"motor_port{port}"
        self._velocity = 50  # percent
        self._stopping = BrakeType.BRAKE
        self._record(
            "Motor",
            (port,),
            {"gears": self._gears, "reverse": self._reverse},
        )

    def spin(
        self,
        direction: str,
        velocity: float = 50,
        units: str = VelocityUnits.PERCENT,
    ) -> None:
        self._record("spin", (direction, velocity, units))

    def spin_for(
        self,
        direction: str,
        angle: float,
        units: str = RotationUnits.DEG,
        velocity: float | None = None,
        units_v: str = VelocityUnits.PERCENT,
        wait: bool = True,
    ) -> None:
        v = self._velocity if velocity is None else velocity
        self._record("spin_for", (direction, angle, units, v, units_v, wait))
        if wait:
            SIM_CLOCK.advance(_spin_seconds(angle, units, v))

    def spin_to_position(
        self,
        rotation: float,
        units: str = RotationUnits.DEG,
        velocity: float | None = None,
        units_v: str = VelocityUnits.PERCENT,
        wait: bool = True,
    ) -> None:
        v = self._velocity if velocity is None else velocity
        self._record("spin_to_position", (rotation, units, v, units_v, wait))
        if wait:
            SIM_CLOCK.advance(0.5)

    def stop(self, mode: str = BrakeType.BRAKE) -> None:
        self._record("stop", (mode,))

    def set_position(self, position: float, units: str = RotationUnits.DEG) -> None:
        self._record("set_position", (position, units))

    def set_velocity(self, velocity: float, units: str = VelocityUnits.PERCENT) -> None:
        self._record("set_velocity", (velocity, units))
        if units == VelocityUnits.PERCENT:
            self._velocity = velocity

    def set_stopping(self, mode: str) -> None:
        self._record("set_stopping", (mode,))
        self._stopping = mode

    def set_max_torque(self, value: float, units: str = TorqueUnits.NM) -> None:
        self._record("set_max_torque", (value, units))

    def set_timeout(self, value: float, units: str = TimeUnits.MSEC) -> None:
        self._record("set_timeout", (value, units))

    def set_reversed(self, value: bool) -> None:
        self._record("set_reversed", (value,))
        self._reverse = value

    def reset_position(self) -> None:
        self._record("reset_position")

    def is_done(self) -> bool:
        self._record("is_done")
        return True

    def is_spinning(self) -> bool:
        self._record("is_spinning")
        return False

    def position(self, units: str = RotationUnits.DEG) -> float:
        self._record("position", (units,))
        return 0.0

    def velocity(self, units: str = VelocityUnits.PERCENT) -> float:
        self._record("velocity", (units,))
        return 0.0

    def current(self, units: str = CurrentUnits.AMP) -> float:
        self._record("current", (units,))
        return 0.0

    def power(self, units: str = PowerUnits.WATT) -> float:
        self._record("power", (units,))
        return 0.0

    def torque(self, units: str = TorqueUnits.NM) -> float:
        self._record("torque", (units,))
        return 0.0

    def efficiency(self, units: str = VelocityUnits.PERCENT) -> float:
        self._record("efficiency", (units,))
        return 0.0

    def temperature(self, units: str = TemperatureUnits.CELSIUS) -> float:
        self._record("temperature", (units,))
        return 25.0

    def get_timeout(self) -> int:
        self._record("get_timeout")
        return 0


class MotorGroup(_Recorder):
    _next_id = 1

    def __init__(self, *motors: Motor) -> None:
        self._motors = list(motors)
        self._id = MotorGroup._next_id
        MotorGroup._next_id += 1
        self._label = f"motor_group_{self._id}"
        self._velocity = 50
        self._record(
            "MotorGroup",
            tuple(m._label for m in self._motors),
        )

    def count(self) -> int:
        self._record("count")
        return len(self._motors)

    def spin(
        self,
        direction: str,
        velocity: float = 50,
        units: str = VelocityUnits.PERCENT,
    ) -> None:
        self._record("spin", (direction, velocity, units))

    def spin_for(
        self,
        direction: str,
        angle: float,
        units: str = RotationUnits.DEG,
        velocity: float | None = None,
        units_v: str = VelocityUnits.PERCENT,
        wait: bool = True,
    ) -> None:
        v = self._velocity if velocity is None else velocity
        self._record("spin_for", (direction, angle, units, v, units_v, wait))
        if wait:
            SIM_CLOCK.advance(_spin_seconds(angle, units, v))

    def spin_to_position(
        self,
        rotation: float,
        units: str = RotationUnits.DEG,
        velocity: float | None = None,
        units_v: str = VelocityUnits.PERCENT,
        wait: bool = True,
    ) -> None:
        v = self._velocity if velocity is None else velocity
        self._record("spin_to_position", (rotation, units, v, units_v, wait))
        if wait:
            SIM_CLOCK.advance(0.5)

    def stop(self, mode: str = BrakeType.BRAKE) -> None:
        self._record("stop", (mode,))

    def set_position(self, position: float, units: str = RotationUnits.DEG) -> None:
        self._record("set_position", (position, units))

    def set_velocity(self, velocity: float, units: str = VelocityUnits.PERCENT) -> None:
        self._record("set_velocity", (velocity, units))
        if units == VelocityUnits.PERCENT:
            self._velocity = velocity

    def set_stopping(self, mode: str) -> None:
        self._record("set_stopping", (mode,))

    def set_max_torque(self, value: float, units: str = TorqueUnits.NM) -> None:
        self._record("set_max_torque", (value, units))

    def set_timeout(self, value: float, units: str = TimeUnits.MSEC) -> None:
        self._record("set_timeout", (value, units))

    def is_done(self) -> bool:
        self._record("is_done")
        return True

    def is_spinning(self) -> bool:
        self._record("is_spinning")
        return False

    def position(self, units: str = RotationUnits.DEG) -> float:
        self._record("position", (units,))
        return 0.0

    def velocity(self, units: str = VelocityUnits.PERCENT) -> float:
        self._record("velocity", (units,))
        return 0.0

    def current(self, units: str = CurrentUnits.AMP) -> float:
        self._record("current", (units,))
        return 0.0

    def power(self, units: str = PowerUnits.WATT) -> float:
        self._record("power", (units,))
        return 0.0

    def torque(self, units: str = TorqueUnits.NM) -> float:
        self._record("torque", (units,))
        return 0.0

    def efficiency(self, units: str = VelocityUnits.PERCENT) -> float:
        self._record("efficiency", (units,))
        return 0.0

    def temperature(self, units: str = TemperatureUnits.CELSIUS) -> float:
        self._record("temperature", (units,))
        return 25.0
