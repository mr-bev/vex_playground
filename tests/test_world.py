"""Tests for vex_sim.world: pose integration, drivetrain wiring, trajectory."""

from __future__ import annotations

import math

import pytest

from vex_sim.api import (
    DEGREES,
    FORWARD,
    LEFT,
    MM,
    REVERSE,
    RIGHT,
    Ports,
    sleep,
)
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._drivetrain import DriveTrain
from vex_sim.api._motor import Motor
from vex_sim.world import WORLD, Pose, integrate_pose


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


def _make_drivetrain() -> DriveTrain:
    lm = Motor(Ports.PORT6, False)
    rm = Motor(Ports.PORT10, True)
    return DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)


# -----------------------------------------------------------------------------
# integrate_pose: pure kinematics
# -----------------------------------------------------------------------------


def test_integrate_pose_pure_linear_along_x():
    p = Pose(0.0, 0.0, 0.0)
    out = integrate_pose(p, linear_v=200.0, angular_v=0.0, dt=1.0)
    assert out.x == pytest.approx(200.0)
    assert out.y == pytest.approx(0.0)
    assert out.theta == pytest.approx(0.0)


def test_integrate_pose_pure_linear_along_heading():
    p = Pose(0.0, 0.0, math.pi / 2)
    out = integrate_pose(p, linear_v=100.0, angular_v=0.0, dt=1.0)
    assert out.x == pytest.approx(0.0, abs=1e-9)
    assert out.y == pytest.approx(100.0)
    assert out.theta == pytest.approx(math.pi / 2)


def test_integrate_pose_pure_rotation_in_place():
    p = Pose(50.0, 50.0, 0.0)
    out = integrate_pose(p, linear_v=0.0, angular_v=math.pi / 2, dt=1.0)
    assert out.x == pytest.approx(50.0)
    assert out.y == pytest.approx(50.0)
    assert out.theta == pytest.approx(math.pi / 2)


def test_integrate_pose_zero_dt_returns_copy():
    p = Pose(1.0, 2.0, 0.5)
    out = integrate_pose(p, linear_v=10.0, angular_v=1.0, dt=0.0)
    assert out.x == p.x
    assert out.y == p.y
    assert out.theta == p.theta


def test_integrate_pose_arc_motion_returns_to_start_after_full_circle():
    # Drive at constant linear+angular velocity for a full revolution. The
    # robot traces a circle and returns to its starting position.
    p = Pose(0.0, 0.0, 0.0)
    angular = 2 * math.pi  # one full turn per second
    linear = 100.0
    out = integrate_pose(p, linear_v=linear, angular_v=angular, dt=1.0)
    assert out.x == pytest.approx(0.0, abs=1e-6)
    assert out.y == pytest.approx(0.0, abs=1e-6)
    assert out.theta == pytest.approx(2 * math.pi)


# -----------------------------------------------------------------------------
# Drivetrain motion drives the world pose
# -----------------------------------------------------------------------------


def test_drive_for_advances_pose_along_heading():
    dt = _make_drivetrain()
    # Start at origin facing +x. Drive 200 mm forward at 100% (200 mm/s) → 1s.
    dt.drive_for(FORWARD, 200, MM, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(1.0)
    assert WORLD.pose.x == pytest.approx(200.0)
    assert WORLD.pose.y == pytest.approx(0.0, abs=1e-9)
    assert WORLD.pose.theta == pytest.approx(0.0)


def test_drive_for_reverse_moves_backwards_along_heading():
    dt = _make_drivetrain()
    dt.drive_for(REVERSE, 100, MM, velocity=100)
    assert WORLD.pose.x == pytest.approx(-100.0)
    assert WORLD.pose.y == pytest.approx(0.0, abs=1e-9)


def test_turn_for_left_increases_theta():
    dt = _make_drivetrain()
    dt.turn_for(LEFT, 90, DEGREES, velocity=100)
    assert WORLD.pose.theta == pytest.approx(math.pi / 2)
    # And position is unchanged after a turn-in-place.
    assert WORLD.pose.x == pytest.approx(0.0)
    assert WORLD.pose.y == pytest.approx(0.0)


def test_turn_for_right_decreases_theta():
    dt = _make_drivetrain()
    dt.turn_for(RIGHT, 90, DEGREES, velocity=100)
    assert WORLD.pose.theta == pytest.approx(-math.pi / 2)


def test_turn_then_drive_chains_through_pose():
    dt = _make_drivetrain()
    dt.turn_for(LEFT, 90, DEGREES, velocity=100)  # facing +y now
    dt.drive_for(FORWARD, 200, MM, velocity=100)
    assert WORLD.pose.x == pytest.approx(0.0, abs=1e-6)
    assert WORLD.pose.y == pytest.approx(200.0)
    assert WORLD.pose.theta == pytest.approx(math.pi / 2)


def test_continuous_drive_then_wait_integrates_pose():
    dt = _make_drivetrain()
    # 50% of 200 mm/s = 100 mm/s along +x.
    dt.drive(FORWARD, 50)
    sleep(2.0)
    assert WORLD.pose.x == pytest.approx(200.0)
    assert SIM_CLOCK.now() == pytest.approx(2.0)


def test_stop_halts_continuous_motion():
    dt = _make_drivetrain()
    dt.drive(FORWARD, 50)  # 100 mm/s
    sleep(1.0)
    dt.stop()
    sleep(2.0)
    assert WORLD.pose.x == pytest.approx(100.0)


def test_drive_for_wait_false_does_not_move_pose():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 200, MM, wait=False)
    assert WORLD.pose.x == pytest.approx(0.0)
    assert SIM_CLOCK.now() == pytest.approx(0.0)


# -----------------------------------------------------------------------------
# Trajectory recording
# -----------------------------------------------------------------------------


def test_trajectory_records_segments():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 200, MM, velocity=100)  # 1s straight
    dt.turn_for(LEFT, 90, DEGREES, velocity=100)  # 1s rotate
    WORLD.finalize()
    # We expect at least the two motion segments. The drive_for/turn_for pairs
    # each emit one segment with the motion velocity, then close-on-stop adds
    # zero-duration entries that are skipped.
    motion_segments = [s for s in WORLD.trajectory if s.linear_v != 0 or s.angular_v != 0]
    assert len(motion_segments) >= 2
    drive_seg = motion_segments[0]
    assert drive_seg.t_start == pytest.approx(0.0)
    assert drive_seg.t_end == pytest.approx(1.0)
    assert drive_seg.start_pose.x == pytest.approx(0.0)
    assert drive_seg.end_pose.x == pytest.approx(200.0)
    turn_seg = motion_segments[1]
    assert turn_seg.t_start == pytest.approx(1.0)
    assert turn_seg.t_end == pytest.approx(2.0)


def test_trajectory_empty_when_no_motion():
    _ = _make_drivetrain()
    sleep(1.0)
    WORLD.finalize()
    # Idle segment — exists but has zero velocity.
    for seg in WORLD.trajectory:
        assert seg.linear_v == 0.0
        assert seg.angular_v == 0.0


# -----------------------------------------------------------------------------
# Reset
# -----------------------------------------------------------------------------


def test_reset_zeroes_state():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 200, MM, velocity=100)
    SIM_CLOCK.reset()
    WORLD.reset()
    assert WORLD.pose.x == 0.0
    assert WORLD.pose.y == 0.0
    assert WORLD.pose.theta == 0.0
    assert WORLD.linear_v == 0.0
    assert WORLD.angular_v == 0.0
    assert WORLD.trajectory == []


def test_reset_with_playground_uses_start_pose():
    from vex_sim.playgrounds import EMPTY_ROOM

    WORLD.reset(EMPTY_ROOM)
    assert WORLD.pose.x == pytest.approx(EMPTY_ROOM.start_pose.x)
    assert WORLD.pose.y == pytest.approx(EMPTY_ROOM.start_pose.y)
    assert WORLD.pose.theta == pytest.approx(EMPTY_ROOM.start_pose.theta)
    assert WORLD.playground is EMPTY_ROOM
