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

Phase 2 stays simple: instantaneous velocity changes, no acceleration,
no slip, no collision response. Walls are stored for rendering only.
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


@dataclass(frozen=True)
class Wall:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Goal:
    """Axis-aligned rectangle, anchored at its bottom-left corner."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Playground:
    name: str
    width: float
    height: float
    walls: tuple[Wall, ...]
    goal: Goal | None
    start_pose: Pose


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
    _segment_start_time: float = 0.0
    _segment_start_pose: Pose = field(default_factory=Pose)

    def reset(self, playground: Playground | None = None) -> None:
        self.playground = playground
        self.pose = playground.start_pose.copy() if playground else Pose()
        self.linear_v = 0.0
        self.angular_v = 0.0
        self.trajectory = []
        self._segment_start_time = SIM_CLOCK.now()
        self._segment_start_pose = self.pose.copy()

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
        if not walls:
            self.pose = integrate_pose(self.pose, self.linear_v, self.angular_v, dt)
            return

        # Substep so we can never advance the centre by more than 10 mm
        # per step. The robot stops at most one substep short of the
        # wall, which is below the visual resolution of the simulator
        # (10 mm is roughly two pixels at typical zoom). Cheaper and
        # simpler than a swept-circle collision check.
        max_step_mm = 10.0
        speed = abs(self.linear_v)
        n = max(1, math.ceil(speed * dt / max_step_mm)) if speed > 1e-9 else 1
        dt_sub = dt / n

        for _ in range(n):
            candidate = integrate_pose(self.pose, self.linear_v, self.angular_v, dt_sub)
            if not _circle_hits_walls(candidate.x, candidate.y, walls, ROBOT_RADIUS_MM):
                self.pose = candidate
                continue
            rot_only = integrate_pose(self.pose, 0.0, self.angular_v, dt_sub)
            if _circle_hits_walls(rot_only.x, rot_only.y, walls, ROBOT_RADIUS_MM):
                self.pose = Pose(self.pose.x, self.pose.y, rot_only.theta)
            else:
                self.pose = rot_only

    def finalize(self) -> None:
        """Close the current segment. Called once at run termination so the
        trajectory ends exactly at the final clock time, even if no further
        velocity change occurs after the last motion."""
        self._close_segment()

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
