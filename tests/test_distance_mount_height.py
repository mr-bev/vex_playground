"""Tests for the Distance sensor's ``mount_height`` filter.

A distance sensor only sees walls whose ``height_mm`` is at least its
``mount_height``. A short wall in front of a high-mounted sensor is
invisible -- the ray-cast skips it -- but the bumper still triggers on
contact, mirroring the real classroom failure mode.
"""

from __future__ import annotations

import pytest

from vex_sim.api import Brain, Bumper, Distance, Ports
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.sensors_world import SENSOR_CACHE
from vex_sim.world import WORLD, Playground, Pose, Wall


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    SENSOR_CACHE.reset()
    WORLD.reset()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    SENSOR_CACHE.reset()
    WORLD.reset()


def _wall_in_front_world(wall_height_mm: float) -> None:
    """A single perpendicular wall 500 mm in front of the robot."""
    walls = (Wall(500.0, -1000.0, 500.0, 1000.0, height_mm=wall_height_mm),)
    WORLD.reset(
        Playground(
            name="probe",
            width=2000.0,
            height=2000.0,
            walls=walls,
            goal=None,
            start_pose=Pose(0.0, 0.0, 0.0),
        )
    )


def test_default_mount_height_sees_tall_walls():
    _wall_in_front_world(wall_height_mm=200.0)  # tall
    d = Distance(Ports.PORT1)
    SENSOR_CACHE.refresh()
    # Default mount = 100 mm; tall wall (200) >= 100, so visible.
    # Range = wall - centre - chassis radius = 500 - 0 - 160 = 340.
    assert d.object_distance() == pytest.approx(340.0)
    assert d.is_object_detected() is True


def test_default_mount_height_misses_low_walls():
    _wall_in_front_world(wall_height_mm=30.0)  # low
    d = Distance(Ports.PORT1)
    SENSOR_CACHE.refresh()
    # Default mount = 100 mm; low wall (30) < 100, filtered out.
    # No object in range -> sentinel value.
    assert d.object_distance() == 1000.0
    assert d.is_object_detected() is False


def test_low_mount_can_see_low_walls():
    _wall_in_front_world(wall_height_mm=30.0)  # low
    d = Distance(Ports.PORT1, mount_height=20.0)
    SENSOR_CACHE.refresh()
    # 20 mm mount sees the 30 mm wall.
    assert d.object_distance() == pytest.approx(340.0)
    assert d.is_object_detected() is True


def test_high_mount_misses_mid_walls():
    _wall_in_front_world(wall_height_mm=100.0)  # mid
    d = Distance(Ports.PORT1, mount_height=150.0)
    SENSOR_CACHE.refresh()
    assert d.object_distance() == 1000.0


def test_two_sensors_same_world_different_views():
    """A high and a low sensor on the same robot disagree about a low wall."""
    _wall_in_front_world(wall_height_mm=30.0)
    high = Distance(Ports.PORT1, mount_height=100.0)
    low = Distance(Ports.PORT2, mount_height=10.0)
    SENSOR_CACHE.refresh()
    assert high.object_distance() == 1000.0  # blind to low wall
    assert low.object_distance() == pytest.approx(340.0)


def test_bumper_still_fires_against_low_wall_invisible_to_distance():
    """The 'sensor at chassis height misses low obstacles' lesson:
    distance reads infinity, but the bumper still triggers on contact.
    """
    # Place a low wall right at the chassis edge so the bumper pad sits
    # against it.
    walls = (Wall(160.0 + 5.0, -1000.0, 160.0 + 5.0, 1000.0, height_mm=30.0),)
    WORLD.reset(
        Playground(
            name="bumper_low_wall",
            width=2000.0,
            height=2000.0,
            walls=walls,
            goal=None,
            start_pose=Pose(0.0, 0.0, 0.0),
        )
    )
    d = Distance(Ports.PORT1)  # default 100 mm mount
    brain = Brain()
    bumper = Bumper(brain.three_wire_port.a)
    SENSOR_CACHE.refresh()
    assert d.object_distance() == 1000.0  # invisible
    assert bumper.pressing() == 1  # but bumper definitely felt it


def test_distance_records_mount_height_in_call_log():
    """The constructor's mount_height becomes part of the call log so
    auto-marking can tell which mount the student chose."""
    _wall_in_front_world(wall_height_mm=200.0)
    Distance(Ports.PORT1, mount_height=85.0)
    entries = [e for e in CALL_LOG.entries() if e["method"] == "Distance"]
    assert entries, "no Distance constructor entry recorded"
    assert entries[-1]["kwargs"] == {"mount_height": 85.0}
