"""Tests for wall-collision clamping in vex_sim.world.integrate."""

from __future__ import annotations

import math

import pytest

from vex_sim.api import (
    DEGREES,
    FORWARD,
    LEFT,
    MM,
    Ports,
    sleep,
)
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._drivetrain import DriveTrain
from vex_sim.api._motor import Motor
from vex_sim.world import ROBOT_RADIUS_MM, WORLD, Playground, Pose, Wall


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    WORLD.reset()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    WORLD.reset()


def _corridor(robot_x: float = 500.0, wall_x: float = 1000.0) -> Playground:
    return Playground(
        name="corridor",
        width=2000.0,
        height=2000.0,
        walls=(Wall(wall_x, 0.0, wall_x, 2000.0),),
        goal=None,
        start_pose=Pose(robot_x, 1000.0, 0.0),
    )


def _make_drivetrain() -> DriveTrain:
    lm = Motor(Ports.PORT6, False)
    rm = Motor(Ports.PORT10, True)
    return DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)


def test_drive_into_wall_stops_at_radius():
    """Driving toward a wall halts when the chassis reaches it."""
    WORLD.reset(_corridor(robot_x=500.0, wall_x=1000.0))
    dt = _make_drivetrain()
    # Try to drive 1000 mm forward; wall is at x=1000, robot starts at
    # x=500, so the wall is 500 mm away and the robot's centre can only
    # travel until it sits ROBOT_RADIUS_MM short of the wall.
    dt.drive_for(FORWARD, 1000, MM, velocity=100)
    expected_max_x = 1000.0 - ROBOT_RADIUS_MM
    assert WORLD.pose.x <= expected_max_x + 1e-6
    # And the robot should have *gotten close* -- not stuck miles away.
    assert WORLD.pose.x > expected_max_x - 5.0


def test_drive_along_wall_does_not_clip():
    # Robot starts ROBOT_RADIUS_MM from a wall on its left, drives
    # parallel. It should advance exactly the requested distance.
    walls = (Wall(0.0, 0.0, 0.0, 2000.0),)
    WORLD.reset(
        Playground(
            name="along",
            width=2000.0,
            height=2000.0,
            walls=walls,
            goal=None,
            start_pose=Pose(ROBOT_RADIUS_MM + 10.0, 500.0, 0.0),
        )
    )
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 200, MM, velocity=100)
    assert WORLD.pose.x == pytest.approx(ROBOT_RADIUS_MM + 10.0 + 200.0)


def test_rotation_still_works_when_wedged_against_wall():
    """A wedged robot can still rotate to escape, even if it can't translate."""
    WORLD.reset(_corridor(robot_x=1000.0 - ROBOT_RADIUS_MM, wall_x=1000.0))
    dt = _make_drivetrain()
    # Push into the wall; clamp leaves x at the limit, theta unchanged.
    dt.drive(FORWARD, 100)
    sleep(1.0)
    pinned_x = WORLD.pose.x
    assert pinned_x <= 1000.0 - ROBOT_RADIUS_MM + 1e-6
    # Now turn in place. Position must stay clamped, heading must update.
    dt.stop()
    dt.turn_for(LEFT, 90, DEGREES, velocity=100)
    assert WORLD.pose.theta == pytest.approx(math.pi / 2)
    assert WORLD.pose.x == pytest.approx(pinned_x)


def test_no_collision_when_no_walls():
    """Without a playground (or with empty walls), motion is unrestricted."""
    WORLD.reset()
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 5000, MM, velocity=100)
    assert WORLD.pose.x == pytest.approx(5000.0)


def test_bumper_triggers_after_driving_into_wall():
    """End-to-end: drive forward into a wall, both bumpers should fire."""
    from vex_sim.api import Brain, Bumper
    from vex_sim.sensors_world import SENSOR_CACHE

    SENSOR_CACHE.reset()
    WORLD.reset(_corridor(robot_x=500.0, wall_x=1000.0))
    brain = Brain()
    bumper_d = Bumper(brain.three_wire_port.d)
    bumper_f = Bumper(brain.three_wire_port.f)
    SENSOR_CACHE.refresh()
    assert bumper_d.pressing() == 0
    assert bumper_f.pressing() == 0

    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 2000, MM, velocity=100)
    assert bumper_d.pressing() == 1
    assert bumper_f.pressing() == 1


def test_distance_sensor_reports_close_wall_after_clamp():
    """Sensor cache reflects the post-clamp pose, not the would-have-been pose."""
    from vex_sim.api import Distance
    from vex_sim.sensors_world import SENSOR_CACHE

    SENSOR_CACHE.reset()
    WORLD.reset(_corridor(robot_x=500.0, wall_x=1000.0))
    SENSOR_CACHE.refresh()
    distance = Distance(Ports.PORT1)
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 2000, MM, velocity=100)
    # The sensor sits on the front face of the chassis, so when the
    # robot is wedged against the wall it reads ~0 mm. (Substep
    # granularity leaves a few mm of slack between the front face and
    # the wall; tolerate up to one substep.)
    assert distance.object_distance() == pytest.approx(0.0, abs=12.0)
