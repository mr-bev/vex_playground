from __future__ import annotations

import math

import pytest

from vex_sim.api import (
    DEGREES,
    FORWARD,
    INCHES,
    LEFT,
    MM,
    PERCENT,
    REVERSE,
    RIGHT,
    Ports,
)
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._drivetrain import _MAX_LINEAR_MMPS, DriveTrain, SmartDrive
from vex_sim.api._motor import Motor
from vex_sim.world import WORLD


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    # WORLD is a process-global singleton; reset it so motion state (pose,
    # and a pending non-blocking auto-stop) can't leak between tests.
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


def test_drivetrain_construction_records():
    dt = _make_drivetrain()
    methods = [(e["obj"], e["method"]) for e in CALL_LOG.entries()]
    assert ("drivetrain", "DriveTrain") in methods
    assert dt._drive_velocity == 50


def test_smartdrive_construction_records_with_gyro():
    from vex_sim.api._brain import Brain

    brain = Brain()
    lm = Motor(Ports.PORT6, False)
    rm = Motor(Ports.PORT10, True)

    # Inertial isn't implemented yet — pass a dummy with _label.
    class DummyGyro:
        _label = "inertial_brain"

    SmartDrive(lm, rm, DummyGyro(), 259.34, 320, 40, MM, 1)
    methods = [(e["obj"], e["method"]) for e in CALL_LOG.entries()]
    assert ("drivetrain", "SmartDrive") in methods
    _ = brain  # silence unused


def test_drive_does_not_advance_clock():
    dt = _make_drivetrain()
    dt.drive(FORWARD)
    assert SIM_CLOCK.now() == 0.0


def test_drive_for_advances_clock_based_on_distance():
    dt = _make_drivetrain()
    # 200 mm at 100% takes 200 / (100% speed) seconds.
    dt.drive_for(FORWARD, 200, MM, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(200 / _MAX_LINEAR_MMPS)


def test_drive_for_default_velocity_is_50_pct():
    dt = _make_drivetrain()
    # Default velocity is 50%, i.e. half speed -> twice as long as 100%.
    dt.drive_for(FORWARD, 200, MM)
    assert SIM_CLOCK.now() == pytest.approx(200 / (_MAX_LINEAR_MMPS * 0.5))


def test_drive_for_inches_converts():
    dt = _make_drivetrain()
    # 1 inch = 25.4 mm; at 100% that distance takes 25.4 / (100% speed) s.
    dt.drive_for(FORWARD, 1, INCHES, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(25.4 / _MAX_LINEAR_MMPS)


def test_drive_for_wait_false_does_not_advance():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 200, MM, wait=False)
    assert SIM_CLOCK.now() == 0.0


def test_set_drive_velocity_changes_default():
    dt = _make_drivetrain()
    dt.set_drive_velocity(100, PERCENT)
    dt.drive_for(FORWARD, 200, MM)
    assert SIM_CLOCK.now() == pytest.approx(200 / _MAX_LINEAR_MMPS)


def test_turn_for_advances_based_on_angle():
    dt = _make_drivetrain()
    # 90 deg at 100% (90 deg/s) = 1s
    dt.turn_for(LEFT, 90, DEGREES, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_turn_for_records_direction():
    dt = _make_drivetrain()
    CALL_LOG.clear()
    dt.turn_for(RIGHT, 90, DEGREES)
    e = CALL_LOG.entries()[0]
    assert e["method"] == "turn_for"
    assert e["args"][0] == "right"


def test_turn_to_heading_fixed_advance():
    dt = _make_drivetrain()
    dt.turn_to_heading(90, DEGREES, velocity=100)
    assert SIM_CLOCK.now() == pytest.approx(1.0)


def test_drive_for_reverse_direction_recorded():
    dt = _make_drivetrain()
    CALL_LOG.clear()
    dt.drive_for(REVERSE, 100, MM, wait=False)
    e = CALL_LOG.entries()[0]
    assert e["args"][0] == "reverse"


def test_drivetrain_getters_return_defaults():
    dt = _make_drivetrain()
    assert dt.heading() == 0.0
    assert dt.rotation() == 0.0
    assert dt.is_done() is True
    assert dt.is_moving() is False


def test_stop_with_no_arg_records_no_args():
    dt = _make_drivetrain()
    CALL_LOG.clear()
    dt.stop()
    e = CALL_LOG.entries()[0]
    assert e["method"] == "stop"
    assert e["args"] == []


# --------------------------------------------------------------------------
# Non-blocking motion (wait=False)
#
# A wait=False drive_for/turn_for must return immediately *and* actually move
# the robot: it starts the motion and the world stops it once the commanded
# distance/angle is covered, however coarsely the clock is later advanced.
# (Regression: the wait=False branch used to be unimplemented, so the robot
# never moved at all.)
# --------------------------------------------------------------------------


def test_drive_for_nonblocking_returns_without_advancing_clock():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 200, MM, velocity=100, wait=False)
    assert SIM_CLOCK.now() == 0.0  # did not block
    assert WORLD.is_motion_pending() is True


def test_drive_for_nonblocking_moves_and_auto_stops_after_one_big_jump():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 200, MM, velocity=100, wait=False)
    # 200 mm at 600 mm/s finishes in 0.333 s; jump far past that in one go.
    SIM_CLOCK.advance(5.0)
    assert WORLD.pose.x == pytest.approx(200.0)
    assert WORLD.pose.y == pytest.approx(0.0)
    assert WORLD.is_motion_pending() is False


def test_drive_for_nonblocking_stops_at_exact_distance_over_many_steps():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 150, MM, velocity=50, wait=False)  # 150 / 300 = 0.5 s
    for _ in range(10):
        SIM_CLOCK.advance(0.1)  # 1.0 s total, well past the 0.5 s move
    assert WORLD.pose.x == pytest.approx(150.0)
    assert WORLD.is_motion_pending() is False


def test_is_moving_tracks_nonblocking_move_progress():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 600, MM, velocity=100, wait=False)  # 1.0 s
    SIM_CLOCK.advance(0.4)
    assert dt.is_moving() is True
    assert dt.is_done() is False
    SIM_CLOCK.advance(1.0)  # cross the 1.0 s deadline
    assert dt.is_moving() is False
    assert dt.is_done() is True
    assert WORLD.pose.x == pytest.approx(600.0)


def test_new_command_supersedes_pending_nonblocking_move():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 600, MM, velocity=100, wait=False)
    SIM_CLOCK.advance(0.1)  # 60 mm so far
    assert WORLD.pose.x == pytest.approx(60.0)
    dt.stop()  # cancels the pending auto-stop, keeps the distance travelled
    assert WORLD.is_motion_pending() is False
    SIM_CLOCK.advance(5.0)
    assert WORLD.pose.x == pytest.approx(60.0)


def test_turn_for_nonblocking_rotates_and_auto_stops():
    dt = _make_drivetrain()
    dt.turn_for(LEFT, 90, DEGREES, velocity=100, wait=False)  # 90 deg/s -> 1.0 s
    SIM_CLOCK.advance(5.0)
    assert WORLD.pose.theta == pytest.approx(math.radians(90))
    assert WORLD.is_motion_pending() is False


def test_nonblocking_drive_completes_end_to_end_via_runner(tmp_path):
    """The reported case: a program whose only motion is a wait=False
    drive_for. The runner must settle the pending move so the robot ends
    where it was sent rather than frozen at the start."""
    from vex_sim.runner import run

    prog = tmp_path / "robot.py"
    prog.write_text(
        "from vex import *\n"
        "brain = Brain()\n"
        "lm = Motor(Ports.PORT6, False)\n"
        "rm = Motor(Ports.PORT10, True)\n"
        "dt = DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)\n"
        "dt.drive_for(FORWARD, 200, MM, velocity=100, wait=False)\n"
    )
    result = run(prog, max_time=10.0)
    assert result["status"] == "completed"
    assert WORLD.pose.x == pytest.approx(200.0)


def test_is_moving_advances_clock_while_move_pending():
    dt = _make_drivetrain()
    dt.drive_for(FORWARD, 600, MM, velocity=100, wait=False)
    t0 = SIM_CLOCK.now()
    assert dt.is_moving() is True
    assert SIM_CLOCK.now() > t0  # the probe nudged sim time forward


def test_is_moving_does_not_advance_clock_when_idle():
    dt = _make_drivetrain()
    t0 = SIM_CLOCK.now()
    assert dt.is_moving() is False
    assert SIM_CLOCK.now() == t0  # no move pending -> no nudge


def test_bare_is_moving_poll_loop_does_not_hang(tmp_path):
    """The reported failure: a `while drivetrain.is_moving(): ...` loop with
    no wait() of its own. It must complete (the probe advances sim time)
    rather than spin forever freezing the simulator."""
    from vex_sim.runner import run

    prog = tmp_path / "robot.py"
    prog.write_text(
        "from vex import *\n"
        "brain = Brain()\n"
        "lm = Motor(Ports.PORT6, False); rm = Motor(Ports.PORT10, True)\n"
        "dt = DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)\n"
        "dt.drive_for(FORWARD, 300, MM, velocity=100, wait=False)\n"
        "ticks = 0\n"
        "while dt.is_moving():\n"  # no wait() inside -- used to hang
        "    ticks += 1\n"
        "brain.screen.print(ticks)\n"
    )
    result = run(prog, max_time=10.0)
    assert result["status"] == "completed"
    assert WORLD.pose.x == pytest.approx(300.0)


def test_nonblocking_drive_finishes_during_is_moving_poll_loop(tmp_path):
    """The intended use of wait=False: kick off a move, then poll is_moving
    while doing other work. The robot should travel the full distance."""
    from vex_sim.runner import run

    prog = tmp_path / "robot.py"
    prog.write_text(
        "from vex import *\n"
        "brain = Brain()\n"
        "lm = Motor(Ports.PORT6, False)\n"
        "rm = Motor(Ports.PORT10, True)\n"
        "dt = DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)\n"
        "dt.drive_for(FORWARD, 200, MM, velocity=100, wait=False)\n"
        "while dt.is_moving():\n"
        "    wait(20, MSEC)\n"
    )
    result = run(prog, max_time=10.0)
    assert result["status"] == "completed"
    assert WORLD.pose.x == pytest.approx(200.0)
