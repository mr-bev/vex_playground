from __future__ import annotations

import math
from typing import Any

from vex_sim.api._brain import _Recorder
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._enums import (
    CurrentUnits,
    DirectionType,
    DistanceUnits,
    PowerUnits,
    RotationUnits,
    TemperatureUnits,
    TimeUnits,
    TorqueUnits,
    TurnType,
    VelocityUnits,
)
from vex_sim.api._motor import Motor
from vex_sim.scheduler import SCHEDULER as _SCHEDULER

# isort: split
# vex_sim.world imports vex_sim.api._clock, and api/__init__.py imports this
# module before world.py has finished defining WORLD. Held as a module
# reference; dereference _world.WORLD on each call to avoid binding now.
import vex_sim.world as _world

# 100% velocity baselines for the simulated chassis. These set the shape of
# the time domain (drive_for / turn_for durations) and the world kinematics.
_MAX_LINEAR_MMPS = 200.0
_MAX_ANGULAR_RADPS = math.radians(90.0)


def _to_mm(distance: float, units: str) -> float:
    if units == DistanceUnits.IN or units == DistanceUnits.INCHES:
        return float(distance) * 25.4
    return float(distance)


def _drive_seconds(distance: float, units: str, velocity_pct: float) -> float:
    """100% velocity = 200 mm/s, scaled by velocity_pct."""
    if velocity_pct <= 0:
        return 0.0
    mm = _to_mm(distance, units)
    mm_per_sec = _MAX_LINEAR_MMPS * (velocity_pct / 100.0)
    return mm / mm_per_sec


def _turn_seconds(angle: float, units: str, velocity_pct: float) -> float:
    """100% velocity = 90 deg/sec, scaled by velocity_pct."""
    if velocity_pct <= 0:
        return 0.0
    deg = float(angle) * 360.0 if units == RotationUnits.REV else float(angle)
    deg_per_sec = 90.0 * (velocity_pct / 100.0)
    return deg / deg_per_sec


def _drive_velocity_mmps(direction: str, velocity_pct: float) -> float:
    sign = -1.0 if direction == DirectionType.REVERSE else 1.0
    return sign * _MAX_LINEAR_MMPS * (max(velocity_pct, 0.0) / 100.0)


def _turn_velocity_radps(direction: str, velocity_pct: float) -> float:
    # LEFT in VEX is CCW in math coords (theta increases).
    sign = 1.0 if direction == TurnType.LEFT else -1.0
    return sign * _MAX_ANGULAR_RADPS * (max(velocity_pct, 0.0) / 100.0)


class DriveTrain(_Recorder):
    _label = "drivetrain"

    def __init__(
        self,
        lm: Motor,
        rm: Motor,
        wheelTravel: float = 300,
        trackWidth: float = 320,
        wheelBase: float = 320,
        units: str = DistanceUnits.MM,
        externalGearRatio: float = 1.0,
    ) -> None:
        self._lm = lm
        self._rm = rm
        self._wheel_travel = wheelTravel
        self._track_width = trackWidth
        self._wheel_base = wheelBase
        self._units = units
        self._gear_ratio = externalGearRatio
        self._drive_velocity = 50
        self._turn_velocity = 50
        self._record(
            "DriveTrain",
            (lm._label, rm._label, wheelTravel, trackWidth, wheelBase, units, externalGearRatio),
        )

    def drive(
        self, direction: str, velocity: float | None = None, units: str = VelocityUnits.PERCENT
    ) -> None:
        self._record("drive", (direction, velocity, units))
        v = self._drive_velocity if velocity is None else velocity
        _world.WORLD.set_velocity(_drive_velocity_mmps(direction, v), 0.0)

    def drive_for(
        self,
        direction: str,
        distance: float,
        units: str = DistanceUnits.MM,
        velocity: float | None = None,
        units_v: str = VelocityUnits.PERCENT,
        wait: bool = True,
    ) -> None:
        v = self._drive_velocity if velocity is None else velocity
        self._record("drive_for", (direction, distance, units, v, units_v, wait))
        if wait:
            duration = _drive_seconds(distance, units, v)
            _world.WORLD.set_velocity(_drive_velocity_mmps(direction, v), 0.0)
            _SCHEDULER.yield_for(SIM_CLOCK.now() + duration)
            _world.WORLD.stop()

    def turn(
        self, direction: str, velocity: float | None = None, units: str = VelocityUnits.PERCENT
    ) -> None:
        self._record("turn", (direction, velocity, units))
        v = self._turn_velocity if velocity is None else velocity
        _world.WORLD.set_velocity(0.0, _turn_velocity_radps(direction, v))

    def turn_for(
        self,
        direction: str,
        angle: float,
        units: str = RotationUnits.DEG,
        velocity: float | None = None,
        units_v: str = VelocityUnits.PERCENT,
        wait: bool = True,
    ) -> None:
        v = self._turn_velocity if velocity is None else velocity
        self._record("turn_for", (direction, angle, units, v, units_v, wait))
        if wait:
            duration = _turn_seconds(angle, units, v)
            _world.WORLD.set_velocity(0.0, _turn_velocity_radps(direction, v))
            _SCHEDULER.yield_for(SIM_CLOCK.now() + duration)
            _world.WORLD.stop()

    def turn_to_heading(
        self,
        angle: float,
        units: str = RotationUnits.DEG,
        velocity: float | None = None,
        units_v: str = VelocityUnits.PERCENT,
        wait: bool = True,
    ) -> None:
        v = self._turn_velocity if velocity is None else velocity
        self._record("turn_to_heading", (angle, units, v, units_v, wait))
        if wait:
            _SCHEDULER.yield_for(SIM_CLOCK.now() + 1.0)

    def turn_to_rotation(
        self,
        angle: float,
        units: str = RotationUnits.DEG,
        velocity: float | None = None,
        units_v: str = VelocityUnits.PERCENT,
        wait: bool = True,
    ) -> None:
        v = self._turn_velocity if velocity is None else velocity
        self._record("turn_to_rotation", (angle, units, v, units_v, wait))
        if wait:
            _SCHEDULER.yield_for(SIM_CLOCK.now() + 1.0)

    def stop(self, mode: Any = None) -> None:
        self._record("stop", () if mode is None else (mode,))
        _world.WORLD.stop()

    def calibrate_drivetrain(self) -> None:
        self._record("calibrate_drivetrain")

    def set_drive_velocity(self, velocity: float, units: str = VelocityUnits.PERCENT) -> None:
        self._record("set_drive_velocity", (velocity, units))
        if units == VelocityUnits.PERCENT:
            self._drive_velocity = velocity

    def set_turn_velocity(self, velocity: float, units: str = VelocityUnits.PERCENT) -> None:
        self._record("set_turn_velocity", (velocity, units))
        if units == VelocityUnits.PERCENT:
            self._turn_velocity = velocity

    def set_stopping(self, mode: str) -> None:
        self._record("set_stopping", (mode,))

    def set_timeout(self, value: float, units: str = TimeUnits.MSEC) -> None:
        self._record("set_timeout", (value, units))

    def set_heading(self, heading: float, units: str = RotationUnits.DEG) -> None:
        self._record("set_heading", (heading, units))

    def set_rotation(self, rotation: float, units: str = RotationUnits.DEG) -> None:
        self._record("set_rotation", (rotation, units))

    def set_turn_threshold(self, value: float) -> None:
        self._record("set_turn_threshold", (value,))

    def set_turn_constant(self, value: float) -> None:
        self._record("set_turn_constant", (value,))

    def set_turn_direction_reverse(self, value: bool) -> None:
        self._record("set_turn_direction_reverse", (value,))

    def is_done(self) -> bool:
        self._record("is_done")
        return True

    def is_moving(self) -> bool:
        self._record("is_moving")
        return False

    def heading(self, units: str = RotationUnits.DEG) -> float:
        self._record("heading", (units,))
        return 0.0

    def rotation(self, units: str = RotationUnits.DEG) -> float:
        self._record("rotation", (units,))
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


class SmartDrive(DriveTrain):
    def __init__(
        self,
        lm: Motor,
        rm: Motor,
        g: Any,
        wheelTravel: float = 300,
        trackWidth: float = 320,
        wheelBase: float = 320,
        units: str = DistanceUnits.MM,
        externalGearRatio: float = 1.0,
    ) -> None:
        self._lm = lm
        self._rm = rm
        self._gyro = g
        self._wheel_travel = wheelTravel
        self._track_width = trackWidth
        self._wheel_base = wheelBase
        self._units = units
        self._gear_ratio = externalGearRatio
        self._drive_velocity = 50
        self._turn_velocity = 50
        gyro_label = getattr(g, "_label", repr(g))
        self._record(
            "SmartDrive",
            (
                lm._label,
                rm._label,
                gyro_label,
                wheelTravel,
                trackWidth,
                wheelBase,
                units,
                externalGearRatio,
            ),
        )
