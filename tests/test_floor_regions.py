"""Tests for FloorRegion (rect + polygon), zone visit tracking, and
the optical-sensor lookup against named regions.

Floor regions never block motion or trip bumpers. They exist for two
purposes:

* Optical sensor reads a colour beneath the robot.
* Named regions count as "zones" for scenario success criteria
  (``reach_zone`` / ``visit_sequence``).
"""

from __future__ import annotations

import pytest

from vex_sim.api import Bumper, Color, Distance, Optical, Ports
from vex_sim.api._brain import Brain
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._drivetrain import DriveTrain
from vex_sim.api._motor import Motor
from vex_sim.sensors_world import SENSOR_CACHE
from vex_sim.world import WORLD, FloorRegion, Playground, Pose


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


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------


def test_floor_region_rect_contains():
    r = FloorRegion(color="green", bounds=(100.0, 100.0, 200.0, 200.0))
    assert r.contains(150.0, 150.0)
    assert r.contains(100.0, 100.0)
    assert not r.contains(50.0, 150.0)
    assert not r.contains(150.0, 350.0)


def test_floor_region_polygon_contains():
    # Triangle with vertices (0,0), (200,0), (100,200).
    r = FloorRegion(color="red", points=((0.0, 0.0), (200.0, 0.0), (100.0, 200.0)))
    assert r.contains(100.0, 50.0)  # well inside
    assert not r.contains(0.0, 100.0)  # outside the left edge
    assert not r.contains(300.0, 0.0)  # right of the polygon


def test_floor_region_requires_exactly_one_shape():
    with pytest.raises(ValueError):
        FloorRegion(color="green")  # neither set
    with pytest.raises(ValueError):
        FloorRegion(
            color="green",
            bounds=(0.0, 0.0, 1.0, 1.0),
            points=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        )


def test_floor_region_polygon_needs_three_points():
    with pytest.raises(ValueError):
        FloorRegion(color="red", points=((0.0, 0.0), (1.0, 1.0)))


# ---------------------------------------------------------------------------
# Optical sensor reads from named regions
# ---------------------------------------------------------------------------


def _make_playground(*regions: FloorRegion) -> Playground:
    return Playground(
        name="probe",
        width=2000.0,
        height=2000.0,
        walls=(),
        goal=None,
        start_pose=Pose(1000.0, 1000.0, 0.0),
        floor_regions=regions,
    )


def test_optical_reads_polygon_region():
    region = FloorRegion(
        color=Color.GREEN,
        name="start",
        points=((900.0, 900.0), (1100.0, 900.0), (1000.0, 1100.0)),
    )
    pg = _make_playground(region)
    WORLD.reset(pg)
    # Robot starts at (1000, 1000) which is inside the triangle.
    o = Optical(Ports.PORT7)
    SENSOR_CACHE.refresh()
    assert o.color() == Color.GREEN


def test_optical_returns_black_outside_any_region():
    region = FloorRegion(color=Color.RED, bounds=(0.0, 0.0, 100.0, 100.0))
    pg = _make_playground(region)
    WORLD.reset(pg)  # start_pose is (1000, 1000), well outside
    o = Optical(Ports.PORT7)
    SENSOR_CACHE.refresh()
    assert o.color() == Color.BLACK


def test_optical_first_region_wins_when_overlapping():
    """A small marker on top of a wide background: the marker wins
    because it appears earlier in the floor_regions tuple."""
    marker = FloorRegion(color=Color.RED, bounds=(950.0, 950.0, 100.0, 100.0))
    background = FloorRegion(color=Color.GREEN, bounds=(0.0, 0.0, 2000.0, 2000.0))
    pg = _make_playground(marker, background)
    WORLD.reset(pg)
    o = Optical(Ports.PORT7)
    SENSOR_CACHE.refresh()
    assert o.color() == Color.RED


# ---------------------------------------------------------------------------
# Zone visit tracking via World motion
# ---------------------------------------------------------------------------


def test_starting_inside_named_zone_records_first_visit():
    start_zone = FloorRegion(color=Color.GREEN, name="start", bounds=(900.0, 900.0, 200.0, 200.0))
    pg = _make_playground(start_zone)
    WORLD.reset(pg)
    assert WORLD.visited_zones == ["start"]


def test_visit_sequence_records_zones_in_entry_order():
    start = FloorRegion(color=Color.GREEN, name="start", bounds=(0.0, 900.0, 200.0, 200.0))
    middle = FloorRegion(color=Color.BLUE, name="middle", bounds=(800.0, 900.0, 200.0, 200.0))
    end = FloorRegion(color=Color.RED, name="end", bounds=(1600.0, 900.0, 200.0, 200.0))
    pg = Playground(
        name="path",
        width=2000.0,
        height=2000.0,
        walls=(),
        goal=None,
        start_pose=Pose(100.0, 1000.0, 0.0),
        floor_regions=(start, middle, end),
    )
    WORLD.reset(pg)
    # Drive forward through the zones using the real drivetrain.
    lm = Motor(Ports.PORT6, False)
    rm = Motor(Ports.PORT10, True)
    dt = DriveTrain(lm, rm, 259.34, 320, 40, "mm", 1)
    dt.drive_for("forward", 1700, "mm", velocity=100)
    assert WORLD.visited_zones == ["start", "middle", "end"]


def test_unnamed_regions_do_not_count_as_zones():
    """Anonymous floor regions are visual-only -- no zone tracking."""
    paint = FloorRegion(color=Color.GREEN, bounds=(900.0, 900.0, 200.0, 200.0))
    pg = _make_playground(paint)
    WORLD.reset(pg)
    assert WORLD.visited_zones == []


# ---------------------------------------------------------------------------
# Floor regions never block motion
# ---------------------------------------------------------------------------


def test_floor_region_does_not_block_motion():
    region = FloorRegion(color=Color.RED, bounds=(400.0, 0.0, 200.0, 2000.0))
    pg = Playground(
        name="probe",
        width=2000.0,
        height=2000.0,
        walls=(),
        goal=None,
        start_pose=Pose(100.0, 1000.0, 0.0),
        floor_regions=(region,),
    )
    WORLD.reset(pg)
    lm = Motor(Ports.PORT6, False)
    rm = Motor(Ports.PORT10, True)
    dt = DriveTrain(lm, rm, 259.34, 320, 40, "mm", 1)
    dt.drive_for("forward", 1000, "mm", velocity=100)
    # Robot drove all 1000 mm -- no floor-region collision.
    assert WORLD.pose.x == pytest.approx(1100.0)


def test_floor_region_does_not_trigger_bumper():
    # A 30 mm-tall wall would trip the bumper; a floor region must not.
    region = FloorRegion(color=Color.YELLOW, bounds=(150.0, -100.0, 50.0, 200.0))
    pg = Playground(
        name="probe",
        width=2000.0,
        height=2000.0,
        walls=(),
        goal=None,
        start_pose=Pose(0.0, 0.0, 0.0),
        floor_regions=(region,),
    )
    WORLD.reset(pg)
    brain = Brain()
    bumper = Bumper(brain.three_wire_port.a)
    SENSOR_CACHE.refresh()
    assert bumper.pressing() == 0


def test_floor_region_invisible_to_distance():
    region = FloorRegion(color=Color.PURPLE, bounds=(300.0, -1000.0, 50.0, 2000.0))
    pg = Playground(
        name="probe",
        width=2000.0,
        height=2000.0,
        walls=(),
        goal=None,
        start_pose=Pose(0.0, 0.0, 0.0),
        floor_regions=(region,),
    )
    WORLD.reset(pg)
    d = Distance(Ports.PORT1)
    SENSOR_CACHE.refresh()
    assert d.object_distance() == 1000.0  # nothing seen
