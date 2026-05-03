"""Tests for vex_sim.sensors_world: distance/bumper/optical read the world."""

from __future__ import annotations

import math

import pytest

from vex_sim.api import (
    Brain,
    Bumper,
    Color,
    Distance,
    Optical,
    Ports,
)
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.playgrounds import EMPTY_ROOM
from vex_sim.sensors_world import (
    ROBOT_RADIUS_MM,
    SENSOR_CACHE,
    _point_segment_distance,
    _ray_segment_intersection_t,
    default_bumper_offset,
)
from vex_sim.world import WORLD, Pose, Wall


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


# -----------------------------------------------------------------------------
# Geometry primitives
# -----------------------------------------------------------------------------


def test_ray_hits_perpendicular_wall_at_expected_distance():
    # Ray from origin along +x; wall at x=300 spanning y in [-100, 100].
    t = _ray_segment_intersection_t(0.0, 0.0, 1.0, 0.0, 300.0, -100.0, 300.0, 100.0)
    assert t == pytest.approx(300.0)


def test_ray_misses_when_segment_is_outside_cone():
    # Wall above the ray's path at y=50 spanning x in [10, 20].
    t = _ray_segment_intersection_t(0.0, 0.0, 1.0, 0.0, 10.0, 50.0, 20.0, 50.0)
    assert t is None


def test_ray_ignores_segments_behind_origin():
    # Ray from (0,0) along +x; wall is at x=-100 (behind us).
    t = _ray_segment_intersection_t(0.0, 0.0, 1.0, 0.0, -100.0, -10.0, -100.0, 10.0)
    assert t is None


def test_ray_parallel_to_segment_returns_none():
    # Both ray and segment along +x.
    t = _ray_segment_intersection_t(0.0, 0.0, 1.0, 0.0, 100.0, 0.0, 200.0, 0.0)
    assert t is None


def test_point_segment_distance_perpendicular_drop():
    d = _point_segment_distance(50.0, 30.0, 0.0, 0.0, 100.0, 0.0)
    assert d == pytest.approx(30.0)


def test_point_segment_distance_clamps_to_endpoint():
    # Foot of perpendicular falls past the end of the segment; distance
    # is to the nearest endpoint, not the infinite line.
    d = _point_segment_distance(200.0, 0.0, 0.0, 0.0, 100.0, 0.0)
    assert d == pytest.approx(100.0)


# -----------------------------------------------------------------------------
# Bumper offset defaults
# -----------------------------------------------------------------------------


def test_bumper_offset_front_letters():
    fwd, left = default_bumper_offset("bumper_3wire_a")
    assert fwd == ROBOT_RADIUS_MM
    assert left == 0.0


def test_bumper_offset_left_letters():
    fwd, left = default_bumper_offset("bumper_3wire_d")
    assert fwd == 0.0
    assert left == ROBOT_RADIUS_MM


def test_bumper_offset_right_letters():
    fwd, left = default_bumper_offset("bumper_3wire_f")
    assert fwd == 0.0
    assert left == -ROBOT_RADIUS_MM


def test_bumper_offset_rear_letters():
    fwd, left = default_bumper_offset("bumper_3wire_g")
    assert fwd == -ROBOT_RADIUS_MM
    assert left == 0.0


# -----------------------------------------------------------------------------
# Distance: full integration with a playground
# -----------------------------------------------------------------------------


def test_distance_in_empty_room_caps_at_max():
    # In the 3 m empty room, the robot starts 1500 mm from the nearest
    # wall along its heading -- past the 1000 mm sensor cap.
    WORLD.reset(EMPTY_ROOM)
    SENSOR_CACHE.refresh()
    d = Distance(Ports.PORT1)
    assert d.object_distance() == 1000.0
    assert d.is_object_detected() is False


def test_distance_reads_close_wall():
    # A narrow corridor: robot at (50, 50) facing +x; wall at x=250.
    walls = (Wall(250.0, -1000.0, 250.0, 1000.0),)
    WORLD.playground = type(EMPTY_ROOM)(
        name="probe",
        width=500.0,
        height=500.0,
        walls=walls,
        goal=None,
        start_pose=Pose(50.0, 50.0, 0.0),
    )
    WORLD.pose = Pose(50.0, 50.0, 0.0)
    SENSOR_CACHE.refresh()
    d = Distance(Ports.PORT1)
    SENSOR_CACHE.refresh()
    assert d.object_distance() == pytest.approx(200.0)
    assert d.is_object_detected() is True


def test_distance_refreshes_after_motion():
    """Sensor cache reflects the latest pose without the student yielding."""
    walls = (Wall(500.0, -1000.0, 500.0, 1000.0),)
    WORLD.playground = type(EMPTY_ROOM)(
        name="probe",
        width=1000.0,
        height=1000.0,
        walls=walls,
        goal=None,
        start_pose=Pose(0.0, 0.0, 0.0),
    )
    WORLD.pose = Pose(0.0, 0.0, 0.0)
    d = Distance(Ports.PORT1)
    SENSOR_CACHE.refresh()
    initial = d.object_distance()
    WORLD.pose = Pose(100.0, 0.0, 0.0)
    # Simulate a clock tick: the listener fires on advance(0) too.
    SIM_CLOCK.advance(0.001)
    assert d.object_distance() == pytest.approx(initial - 100.0, abs=1.0)


# -----------------------------------------------------------------------------
# Bumper: triggers when robot edge meets a wall
# -----------------------------------------------------------------------------


def test_bumper_front_triggers_when_pressed_against_wall():
    # Robot at (1000, 1000) facing +x; wall just past the bumper pad.
    front_x = 1000.0 + ROBOT_RADIUS_MM
    walls = (Wall(front_x + 5.0, 0.0, front_x + 5.0, 2000.0),)
    WORLD.playground = type(EMPTY_ROOM)(
        name="probe",
        width=2000.0,
        height=2000.0,
        walls=walls,
        goal=None,
        start_pose=Pose(1000.0, 1000.0, 0.0),
    )
    WORLD.pose = Pose(1000.0, 1000.0, 0.0)
    brain = Brain()
    front = Bumper(brain.three_wire_port.a)
    SENSOR_CACHE.refresh()
    assert front.pressing() == 1


def test_bumper_does_not_trigger_when_clear_of_walls():
    WORLD.reset(EMPTY_ROOM)
    SENSOR_CACHE.refresh()
    brain = Brain()
    b = Bumper(brain.three_wire_port.a)
    assert b.pressing() == 0


# -----------------------------------------------------------------------------
# Optical: floor colour lookup
# -----------------------------------------------------------------------------


def test_optical_returns_black_in_empty_room():
    WORLD.reset(EMPTY_ROOM)
    SENSOR_CACHE.refresh()
    o = Optical(Ports.PORT7)
    assert o.color() == Color.BLACK


def test_optical_returns_region_color_when_robot_inside():
    # Custom playground with a single red square at (1000,1000)..(1100,1100).
    class _Region:
        def __init__(self, x, y, w, h, color):
            self.x = x
            self.y = y
            self.w = w
            self.h = h
            self.color = color

    class _Playground:
        name = "probe"
        width = 2000.0
        height = 2000.0
        walls = ()
        goal = None
        floor_regions = (_Region(1000.0, 1000.0, 100.0, 100.0, Color.RED),)
        start_pose = Pose(1050.0, 1050.0, 0.0)

    WORLD.playground = _Playground()
    WORLD.pose = Pose(1050.0, 1050.0, 0.0)
    o = Optical(Ports.PORT7)
    SENSOR_CACHE.refresh()
    assert o.color() == Color.RED

    # Move outside the region; cache should reflect black again.
    WORLD.pose = Pose(500.0, 500.0, 0.0)
    SIM_CLOCK.advance(0.001)
    assert o.color() == Color.BLACK


# -----------------------------------------------------------------------------
# Cache lifecycle
# -----------------------------------------------------------------------------


def test_cache_reset_drops_registered_probes():
    Distance(Ports.PORT1)
    Distance(Ports.PORT2)
    assert len(SENSOR_CACHE.distances) == 2
    SENSOR_CACHE.reset()
    assert SENSOR_CACHE.distances == []


def test_listener_refreshes_cache_on_clock_advance():
    """SIM_CLOCK.advance() must trigger the cache refresh listener."""
    walls = (Wall(500.0, -1000.0, 500.0, 1000.0),)
    WORLD.playground = type(EMPTY_ROOM)(
        name="probe",
        width=1000.0,
        height=1000.0,
        walls=walls,
        goal=None,
        start_pose=Pose(0.0, 0.0, 0.0),
    )
    WORLD.pose = Pose(0.0, 0.0, 0.0)
    Distance(Ports.PORT1)
    SIM_CLOCK.advance(0.0)
    initial = SENSOR_CACHE.distance_mm["distance_port1"]
    WORLD.pose = Pose(0.0, 0.0, math.pi)  # face away from the wall
    SIM_CLOCK.advance(0.0)
    assert SENSOR_CACHE.distance_mm["distance_port1"] != initial
