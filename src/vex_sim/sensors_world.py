"""World-aware sensor cache.

Sensors in :mod:`vex_sim.api._sensors` are student-facing recorders;
their numeric return values come from this module. The cache holds the
most recent reading for every active sensor and is refreshed on every
:data:`SIM_CLOCK` advance via the listener registered in
:func:`install_listener`. Sensor reads then become O(1) cache lookups
with no clock movement -- crucial because the student calls them inside
tight ``while`` loops.

Geometry
--------

Distance: ray from the robot's centre, along its heading, against every
wall segment. Returns the minimum positive intersection in millimetres,
clamped to a nominal max range.

Bumper: a ring of contact points around the robot's circular footprint.
A bumper presses when its mounting offset (in robot-local coordinates)
brings its world-space contact point within ``_BUMPER_PROXIMITY_MM`` of
any wall segment.

Optical: floor-colour lookup. The playground may declare painted
regions; if the robot centre falls inside one, that colour is reported.
Otherwise the sensor reports :data:`Color.BLACK` -- the same default the
non-world sensor returned in Phase 2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._enums import Color
from vex_sim.world import ROBOT_RADIUS_MM, WORLD, Wall, point_segment_distance

# Distance sensor returns this when no wall is hit within the cone -- the
# Phase 2 default. 1 m matches the VEX EXP distance sensor's "no object"
# convention closely enough for student programs that compare against a
# threshold.
_DISTANCE_MAX_MM = 1000.0

# A bumper triggers when its mount point is within this radius of a
# wall. A real VEX bumper protrudes ~10 mm from the chassis; we treat
# any wall within 10 mm of the bumper's pad as pressing.
_BUMPER_PROXIMITY_MM = 10.0


@dataclass
class _DistanceProbe:
    label: str
    # In Phase 3 every distance sensor sits at the robot centre and points
    # along the robot's heading. Future phases may add per-sensor offset
    # and bearing; the cache structure leaves room for that.


@dataclass
class _BumperProbe:
    label: str
    # Mounting offset in robot-local coords (mm). +x is forward (along
    # heading), +y is left. Phase 3 ships front/rear/left/right defaults
    # selectable by the bumper's source label; see
    # :func:`_default_bumper_offset`.
    forward_mm: float
    left_mm: float


@dataclass
class _OpticalProbe:
    label: str


@dataclass
class SensorCache:
    distance_mm: dict[str, float] = field(default_factory=dict)
    bumper_pressed: dict[str, bool] = field(default_factory=dict)
    optical_color: dict[str, str] = field(default_factory=dict)

    distances: list[_DistanceProbe] = field(default_factory=list)
    bumpers: list[_BumperProbe] = field(default_factory=list)
    opticals: list[_OpticalProbe] = field(default_factory=list)

    def reset(self) -> None:
        self.distance_mm.clear()
        self.bumper_pressed.clear()
        self.optical_color.clear()
        self.distances.clear()
        self.bumpers.clear()
        self.opticals.clear()

    # ---- Registration ------------------------------------------------

    def register_distance(self, label: str) -> None:
        self.distances.append(_DistanceProbe(label=label))
        self.distance_mm[label] = _DISTANCE_MAX_MM

    def register_bumper(self, label: str, forward_mm: float, left_mm: float) -> None:
        self.bumpers.append(_BumperProbe(label=label, forward_mm=forward_mm, left_mm=left_mm))
        self.bumper_pressed[label] = False

    def register_optical(self, label: str) -> None:
        self.opticals.append(_OpticalProbe(label=label))
        self.optical_color[label] = Color.BLACK

    # ---- Refresh ------------------------------------------------------

    def refresh(self) -> None:
        """Recompute every cached reading from the current WORLD state.

        Cheap (O(probes * walls)); called on each SIM_CLOCK advance.
        """
        playground = WORLD.playground
        walls: tuple[Wall, ...] = playground.walls if playground is not None else ()
        pose = WORLD.pose

        for d in self.distances:
            self.distance_mm[d.label] = _ray_min_distance_mm(pose.x, pose.y, pose.theta, walls)

        cos_t = math.cos(pose.theta)
        sin_t = math.sin(pose.theta)
        for b in self.bumpers:
            wx = pose.x + b.forward_mm * cos_t - b.left_mm * sin_t
            wy = pose.y + b.forward_mm * sin_t + b.left_mm * cos_t
            self.bumper_pressed[b.label] = _point_near_any_wall(wx, wy, walls, _BUMPER_PROXIMITY_MM)

        regions = getattr(playground, "floor_regions", ()) if playground is not None else ()
        for o in self.opticals:
            self.optical_color[o.label] = _floor_color_at(pose.x, pose.y, regions)


SENSOR_CACHE = SensorCache()


# -----------------------------------------------------------------------------
# Geometry helpers
# -----------------------------------------------------------------------------


def _ray_segment_intersection_t(
    ox: float, oy: float, dx: float, dy: float, x1: float, y1: float, x2: float, y2: float
) -> float | None:
    """Distance ``t`` from ray origin to its hit point on a segment, or None.

    Ray is (ox + t*dx, oy + t*dy) for t >= 0; segment is (x1,y1)-(x2,y2).
    Solves the 2x2 linear system; returns the positive t if the
    intersection lies inside the segment, otherwise None.
    """
    sx = x2 - x1
    sy = y2 - y1
    denom = dx * (-sy) - dy * (-sx)
    if abs(denom) < 1e-12:
        return None
    rx = x1 - ox
    ry = y1 - oy
    t = (rx * (-sy) - ry * (-sx)) / denom
    u = (dx * ry - dy * rx) / denom
    if t < 0:
        return None
    if u < 0.0 or u > 1.0:
        return None
    return t


def _ray_min_distance_mm(ox: float, oy: float, theta: float, walls: tuple[Wall, ...]) -> float:
    """Return the minimum hit distance along ``theta`` against ``walls``.

    Clamped to :data:`_DISTANCE_MAX_MM` -- the "no object" sentinel
    students compare against. Distances are reported in millimetres,
    matching the world's coordinate units.
    """
    dx = math.cos(theta)
    dy = math.sin(theta)
    best = _DISTANCE_MAX_MM
    for w in walls:
        t = _ray_segment_intersection_t(ox, oy, dx, dy, w.x1, w.y1, w.x2, w.y2)
        if t is not None and t < best:
            best = t
    return best


def _point_near_any_wall(
    px: float, py: float, walls: tuple[Wall, ...], proximity_mm: float
) -> bool:
    for w in walls:
        if point_segment_distance(px, py, w.x1, w.y1, w.x2, w.y2) <= proximity_mm:
            return True
    return False


def _floor_color_at(x: float, y: float, regions) -> str:
    """Return the colour of the painted floor region at (x, y), or BLACK.

    A region is any object with ``x``, ``y``, ``w``, ``h`` (axis-aligned
    rectangle, anchored at the bottom-left corner) and a ``color`` string
    that matches one of the :class:`Color` constants. Phase 3 uses this
    for optional optical-sensor playgrounds; the default empty room has
    no painted regions and the sensor reports BLACK.
    """
    for r in regions:
        rx = getattr(r, "x", None)
        ry = getattr(r, "y", None)
        rw = getattr(r, "w", None)
        rh = getattr(r, "h", None)
        rc = getattr(r, "color", None)
        if rx is None or ry is None or rw is None or rh is None or rc is None:
            continue
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            return rc
    return Color.BLACK


# -----------------------------------------------------------------------------
# Bumper layout defaults
# -----------------------------------------------------------------------------


def default_bumper_offset(label: str) -> tuple[float, float]:
    """Map a bumper's port label to a sensible mounting offset.

    Phase 3 supports the four ``brain.three_wire_port.<a-h>`` letters
    students typically use:

      * ``a``/``b`` -> front bumpers (forward = +ROBOT_RADIUS, left = 0)
      * ``c``/``d`` -> left bumpers (forward = 0, left = +ROBOT_RADIUS)
      * ``e``/``f`` -> right bumpers (forward = 0, left = -ROBOT_RADIUS)
      * ``g``/``h`` -> rear bumpers (forward = -ROBOT_RADIUS, left = 0)

    Anything else falls through to "front", which keeps the sample
    student program working without forcing them to declare a layout.
    """
    if label.endswith(("_a", "_b")):
        return (ROBOT_RADIUS_MM, 0.0)
    if label.endswith(("_c", "_d")):
        return (0.0, ROBOT_RADIUS_MM)
    if label.endswith(("_e", "_f")):
        return (0.0, -ROBOT_RADIUS_MM)
    if label.endswith(("_g", "_h")):
        return (-ROBOT_RADIUS_MM, 0.0)
    return (ROBOT_RADIUS_MM, 0.0)


# -----------------------------------------------------------------------------
# Lifecycle: SIM_CLOCK listener registration
# -----------------------------------------------------------------------------


def _on_clock_advance(_dt: float) -> None:
    SENSOR_CACHE.refresh()


def install_listener() -> None:
    """Register the cache refresh on SIM_CLOCK. Called once at import time.

    The listener is idempotent: SIM_CLOCK.add_advance_listener appends
    the same callable each time it is called, so we guard with a flag.
    """
    if not _state.installed:
        SIM_CLOCK.add_advance_listener(_on_clock_advance)
        _state.installed = True


@dataclass
class _State:
    installed: bool = False


_state = _State()


install_listener()
