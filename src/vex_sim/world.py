"""2D world model for the VEX simulator.

The World is a singleton that tracks the robot's pose (position and
heading) over simulated time. Motion is driven by the DriveTrain API:
when student code calls drive_for / turn_for / drive / turn / stop, the
DriveTrain translates the VEX-style call into linear and angular
velocities on the world. SIM_CLOCK.advance(dt) integrates the pose
forward by dt.

Coordinate convention:
  - x is right, y is up, units in millimetres.
  - theta is in radians, with 0 along +x, increasing counter-clockwise.
  - VEX FORWARD moves along +heading; LEFT turns CCW (+theta).

2D-with-heights: the world is rendered top-down, but every wall has a
``height_mm`` and every distance-sensor probe a ``mount_height_mm``.
Walls below the sensor's mount height are filtered before the ray-cast
runs, so a sensor mounted at 100 mm never "sees" a 30 mm low wall --
even though the bumper at floor level still triggers on contact. This
mirrors the real EXP failure mode where a high-mounted sensor lets the
robot drive into low obstacles. The simulator preserves the lesson
rather than abstracting it away.

Phase 4 also tracks per-run metrics on the singleton World instance --
``distance_travelled_mm``, ``collision_count``, ``visited_zones`` --
which the scenario runner reads to evaluate success criteria.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from vex_sim.api._clock import SIM_CLOCK


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0

    def copy(self) -> Pose:
        return Pose(self.x, self.y, self.theta)


#: Named height presets for walls. Real EXP builds use chassis-height
#: walls all over the place; these three buckets are enough to teach the
#: lesson that "the distance sensor doesn't see what its mount can't see".
WALL_HEIGHT_PRESETS: dict[str, float] = {
    "low": 30.0,
    "mid": 100.0,
    "tall": 200.0,
}

#: Default wall height when none is specified -- a full-height wall that
#: every reasonable distance-sensor mount will detect.
DEFAULT_WALL_HEIGHT_MM: float = WALL_HEIGHT_PRESETS["tall"]


def parse_wall_height(value: str | float | int | None) -> float:
    """Resolve a wall height to millimetres.

    ``None`` -> :data:`DEFAULT_WALL_HEIGHT_MM`.
    A string -> looked up in :data:`WALL_HEIGHT_PRESETS` (case-insensitive).
    A number -> taken as millimetres directly. Must be > 0.
    """
    if value is None:
        return DEFAULT_WALL_HEIGHT_MM
    if isinstance(value, str):
        key = value.strip().lower()
        if key not in WALL_HEIGHT_PRESETS:
            known = ", ".join(sorted(WALL_HEIGHT_PRESETS))
            raise ValueError(f"unknown wall-height preset {value!r}; known: {known}")
        return WALL_HEIGHT_PRESETS[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"wall height must be a number or preset name, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"wall height must be positive, got {value}")
    return float(value)


@dataclass(frozen=True)
class Wall:
    x1: float
    y1: float
    x2: float
    y2: float
    #: Height in mm. Distance sensors only see walls where
    #: ``height_mm >= sensor.mount_height``. Defaults to a full-height
    #: wall so legacy two-arg construction keeps working.
    height_mm: float = DEFAULT_WALL_HEIGHT_MM


@dataclass(frozen=True)
class Goal:
    """Axis-aligned rectangle, anchored at its bottom-left corner."""

    x: float
    y: float
    w: float
    h: float


def _point_in_polygon(x: float, y: float, points: tuple[tuple[float, float], ...]) -> bool:
    """Even-odd ray-cast point-in-polygon test."""
    n = len(points)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = points[i]
        xj, yj = points[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi):
            inside = not inside
        j = i
    return inside


def _region_contains(region: object, x: float, y: float) -> bool:
    """Inside-region test that tolerates the canonical FloorRegion *and*
    the legacy duck-typed (x, y, w, h) record used by Phase 3 tests."""
    contains = getattr(region, "contains", None)
    if callable(contains):
        return bool(contains(x, y))
    rx = getattr(region, "x", None)
    ry = getattr(region, "y", None)
    rw = getattr(region, "w", None)
    rh = getattr(region, "h", None)
    if rx is None or ry is None or rw is None or rh is None:
        return False
    return rx <= x <= rx + rw and ry <= y <= ry + rh


@dataclass(frozen=True)
class FloorRegion:
    """A coloured patch of floor.

    Floor regions do not block motion, do not trigger bumpers, and are
    invisible to the distance sensor. They exist for two reasons:

    * Visual reference -- mark a start zone, drop zone, etc. in the
      rendered view so students see what their program is meant to do.
    * Optical sensor reads -- :class:`vex_sim.api._sensors.Optical` looks
      down at the floor under the robot's centre and reports the colour
      of the region it's standing on.

    A region has either a rectangular ``bounds`` (x, y, w, h, anchored
    at the bottom-left corner) or a polygon ``points`` (sequence of
    (x, y) tuples in world coordinates). Exactly one must be set.
    """

    color: str
    name: str | None = None
    bounds: tuple[float, float, float, float] | None = None
    points: tuple[tuple[float, float], ...] | None = None

    def __post_init__(self) -> None:
        if (self.bounds is None) == (self.points is None):
            raise ValueError("FloorRegion needs exactly one of bounds= or points=")
        if self.points is not None and len(self.points) < 3:
            raise ValueError("polygon FloorRegion needs at least 3 points")

    def contains(self, x: float, y: float) -> bool:
        if self.bounds is not None:
            bx, by, bw, bh = self.bounds
            return bx <= x <= bx + bw and by <= y <= by + bh
        return _point_in_polygon(x, y, self.points or ())


@dataclass(frozen=True)
class SuccessCriteria:
    """Pass/fail rules evaluated by the scenario runner.

    A criterion bundle is satisfied when every active rule passes:

    * ``reach_zone`` -- robot's centre must enter the named region at
      some point during the run.
    * ``visit_sequence`` -- robot must enter each named region in the
      listed order. Visiting an out-of-order zone in between is fine.
    * ``time_limit`` -- max simulated seconds. Failure if exceeded.
    * ``forbid_collisions`` -- if True, any wall collision fails the
      run.
    """

    reach_zone: str | None = None
    visit_sequence: tuple[str, ...] = ()
    time_limit: float | None = None
    forbid_collisions: bool = False


@dataclass(frozen=True)
class Playground:
    name: str
    width: float
    height: float
    walls: tuple[Wall, ...]
    goal: Goal | None
    start_pose: Pose
    description: str = ""
    floor_regions: tuple[FloorRegion, ...] = ()
    success_criteria: SuccessCriteria | None = None


@dataclass
class TrajectorySegment:
    """A constant-velocity slice of the robot's path through time.

    Renderers interpolate between start_pose and end_pose by
    (t - t_start) / (t_end - t_start). Segments concatenate at every
    velocity change (drive/turn/stop call) and at the end of the run.
    """

    t_start: float
    t_end: float
    start_pose: Pose
    end_pose: Pose
    linear_v: float
    angular_v: float


def integrate_pose(pose: Pose, linear_v: float, angular_v: float, dt: float) -> Pose:
    """Move a pose forward by dt at constant linear and angular velocity.

    Pure linear motion: straight line along heading.
    Pure rotation: theta changes, position unchanged.
    Mixed: exact arc integration around the instantaneous centre of rotation.
    """
    if dt <= 0:
        return pose.copy()
    if abs(angular_v) < 1e-12:
        return Pose(
            x=pose.x + linear_v * math.cos(pose.theta) * dt,
            y=pose.y + linear_v * math.sin(pose.theta) * dt,
            theta=pose.theta,
        )
    new_theta = pose.theta + angular_v * dt
    if abs(linear_v) < 1e-12:
        return Pose(pose.x, pose.y, new_theta)
    r = linear_v / angular_v
    cx = pose.x - r * math.sin(pose.theta)
    cy = pose.y + r * math.cos(pose.theta)
    return Pose(
        x=cx + r * math.sin(new_theta),
        y=cy - r * math.cos(new_theta),
        theta=new_theta,
    )


def point_segment_distance(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Shortest distance from point (px,py) to segment (x1,y1)-(x2,y2)."""
    sx = x2 - x1
    sy = y2 - y1
    seg_len_sq = sx * sx + sy * sy
    if seg_len_sq < 1e-12:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * sx + (py - y1) * sy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    cx = x1 + t * sx
    cy = y1 + t * sy
    return math.hypot(px - cx, py - cy)


# Robot footprint (mm). Used for both collision and bumper geometry; kept
# next to the pose-integration helpers so the world model owns the shape.
ROBOT_RADIUS_MM = 160.0


def _circle_hits_walls(x: float, y: float, walls: tuple[Wall, ...], radius: float) -> bool:
    return any(point_segment_distance(x, y, w.x1, w.y1, w.x2, w.y2) < radius for w in walls)


@dataclass
class World:
    """Singleton 2D world. The runner resets it before every run."""

    playground: Playground | None = None
    pose: Pose = field(default_factory=Pose)
    linear_v: float = 0.0
    angular_v: float = 0.0
    trajectory: list[TrajectorySegment] = field(default_factory=list)
    #: Total Euclidean distance the robot's centre has moved since reset
    #: (mm). Wall clamps don't add to this -- only actual motion. Read by
    #: the scenario runner for metrics.
    distance_travelled_mm: float = 0.0
    #: Number of substeps in which the linear motion was clamped because
    #: the candidate position would have intersected a wall. A single
    #: ``drive_for`` into a wall typically registers many ticks; a clean
    #: run reports zero.
    collision_count: int = 0
    #: Names of floor regions whose interior the robot's centre has
    #: passed through, in entry order. Each name appears at most once.
    visited_zones: list[str] = field(default_factory=list)
    _segment_start_time: float = 0.0
    _segment_start_pose: Pose = field(default_factory=Pose)
    _last_zone: str | None = None

    def reset(self, playground: Playground | None = None) -> None:
        self.playground = playground
        self.pose = playground.start_pose.copy() if playground else Pose()
        self.linear_v = 0.0
        self.angular_v = 0.0
        self.trajectory = []
        self.distance_travelled_mm = 0.0
        self.collision_count = 0
        self.visited_zones = []
        self._segment_start_time = SIM_CLOCK.now()
        self._segment_start_pose = self.pose.copy()
        self._last_zone = None
        # Robot may already be standing inside a zone at start_pose; pick
        # that up immediately so visit_sequence checks see the start zone.
        self._record_zone_at(self.pose.x, self.pose.y)

    def set_velocity(self, linear_mmps: float, angular_radps: float) -> None:
        """Change the robot's velocity vector, closing the previous segment."""
        self._close_segment()
        self.linear_v = float(linear_mmps)
        self.angular_v = float(angular_radps)

    def stop(self) -> None:
        self.set_velocity(0.0, 0.0)

    def integrate(self, dt: float) -> None:
        """SIM_CLOCK advance listener: integrate pose using current velocities.

        Wall collision policy (Phase 3, intentionally simple):

        * Substep through ``dt`` so the robot can never translate more
          than half its radius per integration step. This stops fast
          motion (e.g. a 5 s drive_for resolved in one tick) from
          tunnelling through a wall in a single jump.
        * On each substep, tentatively integrate. If the resulting
          centre lands within :data:`ROBOT_RADIUS_MM` of any wall, drop
          the linear component for that substep. Angular motion is
          always preserved -- the student can still rotate to escape.
        * If even rotation-only still intersects (e.g. the robot
          spawned partially clipping a wall), keep the new heading and
          freeze position. No bounce, no slide -- those would surprise
          students more than a hard stop does.
        """
        if dt <= 0:
            return
        walls: tuple[Wall, ...] = self.playground.walls if self.playground is not None else ()

        # Substep so we never advance the centre by more than 10 mm per
        # step. Two reasons: (a) wall collision needs fine-grained
        # checks so fast motion can't tunnel through a wall; (b) zone
        # visit tracking needs to see intermediate positions, otherwise
        # a long drive_for through a small zone would skip it entirely.
        # 10 mm is below the visual resolution of the simulator (~ two
        # pixels at typical zoom).
        max_step_mm = 10.0
        speed = abs(self.linear_v)
        n = max(1, math.ceil(speed * dt / max_step_mm)) if speed > 1e-9 else 1
        dt_sub = dt / n

        for _ in range(n):
            prev_x, prev_y = self.pose.x, self.pose.y
            candidate = integrate_pose(self.pose, self.linear_v, self.angular_v, dt_sub)
            blocked = walls and _circle_hits_walls(candidate.x, candidate.y, walls, ROBOT_RADIUS_MM)
            if not blocked:
                self.pose = candidate
            else:
                self.collision_count += 1
                rot_only = integrate_pose(self.pose, 0.0, self.angular_v, dt_sub)
                if _circle_hits_walls(rot_only.x, rot_only.y, walls, ROBOT_RADIUS_MM):
                    self.pose = Pose(self.pose.x, self.pose.y, rot_only.theta)
                else:
                    self.pose = rot_only
            self.distance_travelled_mm += math.hypot(self.pose.x - prev_x, self.pose.y - prev_y)
            self._record_zone_at(self.pose.x, self.pose.y)

    def finalize(self) -> None:
        """Close the current segment. Called once at run termination so the
        trajectory ends exactly at the final clock time, even if no further
        velocity change occurs after the last motion."""
        self._close_segment()

    def _record_zone_at(self, x: float, y: float) -> None:
        """Note transitions into named floor regions for visit tracking.

        Re-entering the same zone after leaving it is allowed but only
        the first entry is recorded -- ``visit_sequence`` checks treat
        each zone as visit-once. Anonymous regions (no ``name``) are
        ignored; they exist for visual or optical-sensor purposes only.
        """
        playground = self.playground
        if playground is None:
            return
        current: str | None = None
        for region in playground.floor_regions:
            name = getattr(region, "name", None)
            if not name:
                continue
            if _region_contains(region, x, y):
                current = name
                break
        if current is None:
            self._last_zone = None
            return
        if current != self._last_zone:
            self._last_zone = current
            if current not in self.visited_zones:
                self.visited_zones.append(current)

    def _close_segment(self) -> None:
        now = SIM_CLOCK.now()
        if now > self._segment_start_time:
            self.trajectory.append(
                TrajectorySegment(
                    t_start=self._segment_start_time,
                    t_end=now,
                    start_pose=self._segment_start_pose,
                    end_pose=self.pose.copy(),
                    linear_v=self.linear_v,
                    angular_v=self.angular_v,
                )
            )
        self._segment_start_time = now
        self._segment_start_pose = self.pose.copy()


WORLD = World()
SIM_CLOCK.add_advance_listener(WORLD.integrate)
