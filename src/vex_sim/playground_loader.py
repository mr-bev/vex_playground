"""Load and validate playground JSON files.

A playground file declares a 2D world (walls, painted floor regions,
robot start pose) plus optional success criteria for the scenario
runner. The schema lives next to the loader at
``playground_files/playground.schema.json`` and is the canonical
documentation; this module hand-rolls a lightweight validator that
produces clear, line-of-sight error messages instead of pulling in the
``jsonschema`` runtime dependency.

Pedagogical context (the *why* of wall heights)
----------------------------------------------

The simulator is 2D, but real EXP robots live in 3D. Walls have heights
in millimetres. Distance sensors mounted high on a robot can see *over*
short walls without detecting them; bumpers at floor level catch
everything. This mirrors a real failure mode in physical builds where
students mount the distance sensor high on the chassis and then can't
detect short obstacles. Rather than abstracting this away, the loader
preserves wall heights end-to-end so a playground file can teach the
lesson: "distance sensor at 100 mm + low 30 mm wall = invisible
obstacle, but the bumper still hits it".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vex_sim.world import (
    DEFAULT_WALL_HEIGHT_MM,
    FloorRegion,
    Goal,
    Playground,
    Pose,
    SuccessCriteria,
    Wall,
    parse_wall_height,
)


class PlaygroundFileError(ValueError):
    """Raised when a playground JSON file is malformed.

    The message includes the file path (when known) and the JSON
    pointer-style location of the offending node, e.g.
    ``walls[2].height: expected number or one of 'low','mid','tall'``.
    """


PLAYGROUND_DIR: Path = Path(__file__).parent / "playground_files"


def discover_playground_files(directory: Path | None = None) -> list[Path]:
    """List every ``*.json`` playground file in ``directory``.

    The schema file is excluded. Sorted by name so the order in
    ``--list`` output is stable across runs.
    """
    target = directory or PLAYGROUND_DIR
    return sorted(p for p in target.glob("*.json") if p.name != "playground.schema.json")


def load_playground_file(path: str | Path) -> Playground:
    """Read ``path`` and return a validated :class:`Playground`.

    Raises :class:`PlaygroundFileError` on schema violations,
    :class:`FileNotFoundError` if the file does not exist, and the
    underlying :class:`json.JSONDecodeError` on malformed JSON.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise PlaygroundFileError(f"{p}: invalid JSON at line {e.lineno}: {e.msg}") from e
    try:
        return _build_playground(raw)
    except PlaygroundFileError as e:
        # Re-raise with the file path prepended so error messages point
        # at the offending file even when many are loaded at once.
        raise PlaygroundFileError(f"{p}: {e}") from None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require(condition: bool, location: str, message: str) -> None:
    if not condition:
        raise PlaygroundFileError(f"{location}: {message}")


def _require_keys(data: dict[str, Any], required: tuple[str, ...], location: str) -> None:
    missing = [k for k in required if k not in data]
    if missing:
        raise PlaygroundFileError(
            f"{location}: missing required key(s) {', '.join(repr(k) for k in missing)}"
        )


def _check_type(value: Any, expected: type | tuple[type, ...], location: str) -> None:
    if not isinstance(value, expected):
        names = (
            expected.__name__
            if isinstance(expected, type)
            else " or ".join(t.__name__ for t in expected)
        )
        raise PlaygroundFileError(f"{location}: expected {names}, got {type(value).__name__}")


def _check_xy(value: Any, location: str) -> tuple[float, float]:
    _check_type(value, list, location)
    _require(len(value) == 2, location, f"expected [x, y], got list of length {len(value)}")
    for i, n in enumerate(value):
        _check_type(n, (int, float), f"{location}[{i}]")
    return float(value[0]), float(value[1])


# ---------------------------------------------------------------------------
# Core builders
# ---------------------------------------------------------------------------


_ALLOWED_TOP_KEYS = {
    "name",
    "description",
    "size",
    "robot_start",
    "walls",
    "floor_regions",
    "goal",
}


def _build_playground(raw: Any) -> Playground:
    _check_type(raw, dict, "$")
    extra = set(raw) - _ALLOWED_TOP_KEYS
    _require(not extra, "$", f"unknown top-level key(s): {', '.join(sorted(extra))}")
    _require_keys(raw, ("name", "size", "robot_start", "walls"), "$")

    name = raw["name"]
    _check_type(name, str, "name")
    _require(bool(name), "name", "must be non-empty")

    description = raw.get("description", "")
    _check_type(description, str, "description")

    size = raw["size"]
    _check_type(size, list, "size")
    _require(len(size) == 2, "size", "expected [width, height]")
    width = float(size[0])
    height = float(size[1])
    _require(width > 0 and height > 0, "size", "width and height must be positive")

    robot_start = raw["robot_start"]
    _check_type(robot_start, list, "robot_start")
    _require(len(robot_start) == 3, "robot_start", "expected [x, y, theta]")
    for i, n in enumerate(robot_start):
        _check_type(n, (int, float), f"robot_start[{i}]")
    start_pose = Pose(float(robot_start[0]), float(robot_start[1]), float(robot_start[2]))

    walls = tuple(_build_wall(w, f"walls[{i}]") for i, w in enumerate(raw["walls"]))

    raw_regions = raw.get("floor_regions", [])
    _check_type(raw_regions, list, "floor_regions")
    floor_regions = tuple(
        _build_floor_region(r, f"floor_regions[{i}]") for i, r in enumerate(raw_regions)
    )

    goal_raw = raw.get("goal")
    success_criteria: SuccessCriteria | None = None
    if goal_raw is not None:
        success_criteria = _build_success_criteria(goal_raw, floor_regions, "goal")

    visual_goal = _derive_visual_goal(success_criteria, floor_regions)

    return Playground(
        name=name,
        width=width,
        height=height,
        walls=walls,
        goal=visual_goal,
        start_pose=start_pose,
        description=description,
        floor_regions=floor_regions,
        success_criteria=success_criteria,
    )


_ALLOWED_WALL_KEYS = {"start", "end", "height"}


def _build_wall(raw: Any, location: str) -> Wall:
    _check_type(raw, dict, location)
    extra = set(raw) - _ALLOWED_WALL_KEYS
    _require(not extra, location, f"unknown key(s): {', '.join(sorted(extra))}")
    _require_keys(raw, ("start", "end"), location)
    x1, y1 = _check_xy(raw["start"], f"{location}.start")
    x2, y2 = _check_xy(raw["end"], f"{location}.end")
    height_value = raw.get("height")
    try:
        height_mm = (
            DEFAULT_WALL_HEIGHT_MM if height_value is None else parse_wall_height(height_value)
        )
    except (TypeError, ValueError) as e:
        raise PlaygroundFileError(f"{location}.height: {e}") from None
    return Wall(x1=x1, y1=y1, x2=x2, y2=y2, height_mm=height_mm)


_ALLOWED_REGION_KEYS = {"name", "color", "shape", "bounds", "points"}


def _build_floor_region(raw: Any, location: str) -> FloorRegion:
    _check_type(raw, dict, location)
    extra = set(raw) - _ALLOWED_REGION_KEYS
    _require(not extra, location, f"unknown key(s): {', '.join(sorted(extra))}")
    _require_keys(raw, ("color",), location)

    color = raw["color"]
    _check_type(color, str, f"{location}.color")
    name = raw.get("name")
    if name is not None:
        _check_type(name, str, f"{location}.name")

    shape = raw.get("shape")
    bounds_raw = raw.get("bounds")
    points_raw = raw.get("points")

    if shape is None:
        if bounds_raw is not None and points_raw is None:
            shape = "rect"
        elif points_raw is not None and bounds_raw is None:
            shape = "polygon"
        else:
            raise PlaygroundFileError(
                f"{location}: provide exactly one of 'bounds' (rect) or 'points' (polygon)"
            )

    if shape == "rect":
        _require(
            bounds_raw is not None,
            location,
            "rect region requires 'bounds': [x, y, w, h]",
        )
        _check_type(bounds_raw, list, f"{location}.bounds")
        _require(len(bounds_raw) == 4, f"{location}.bounds", "expected [x, y, w, h]")
        for i, n in enumerate(bounds_raw):
            _check_type(n, (int, float), f"{location}.bounds[{i}]")
        return FloorRegion(
            color=color,
            name=name,
            bounds=(
                float(bounds_raw[0]),
                float(bounds_raw[1]),
                float(bounds_raw[2]),
                float(bounds_raw[3]),
            ),
        )
    if shape == "polygon":
        _require(
            points_raw is not None,
            location,
            "polygon region requires 'points': [[x,y], ...]",
        )
        _check_type(points_raw, list, f"{location}.points")
        _require(len(points_raw) >= 3, f"{location}.points", "polygon needs at least 3 vertices")
        pts: list[tuple[float, float]] = []
        for i, pt in enumerate(points_raw):
            x, y = _check_xy(pt, f"{location}.points[{i}]")
            pts.append((x, y))
        return FloorRegion(color=color, name=name, points=tuple(pts))
    raise PlaygroundFileError(f"{location}.shape: expected 'rect' or 'polygon', got {shape!r}")


_ALLOWED_GOAL_KEYS = {"type", "zone", "zones", "time_limit", "forbid_collisions"}


def _build_success_criteria(
    raw: Any, regions: tuple[FloorRegion, ...], location: str
) -> SuccessCriteria:
    _check_type(raw, dict, location)
    extra = set(raw) - _ALLOWED_GOAL_KEYS
    _require(not extra, location, f"unknown key(s): {', '.join(sorted(extra))}")

    goal_type = raw.get("type")
    reach_zone: str | None = None
    visit_sequence: tuple[str, ...] = ()

    known_zones = {r.name for r in regions if r.name}

    if goal_type == "reach_zone":
        _require_keys(raw, ("zone",), location)
        zone = raw["zone"]
        _check_type(zone, str, f"{location}.zone")
        _require(
            zone in known_zones,
            f"{location}.zone",
            f"references unknown floor region {zone!r}; known: {sorted(known_zones) or '(none)'}",
        )
        reach_zone = zone
    elif goal_type == "visit_sequence":
        _require_keys(raw, ("zones",), location)
        zones = raw["zones"]
        _check_type(zones, list, f"{location}.zones")
        _require(len(zones) >= 1, f"{location}.zones", "must contain at least one zone")
        for i, z in enumerate(zones):
            _check_type(z, str, f"{location}.zones[{i}]")
            _require(
                z in known_zones,
                f"{location}.zones[{i}]",
                f"references unknown floor region {z!r}; "
                f"known: {sorted(known_zones) or '(none)'}",
            )
        visit_sequence = tuple(zones)
    elif goal_type is not None:
        raise PlaygroundFileError(
            f"{location}.type: expected 'reach_zone' or 'visit_sequence', got {goal_type!r}"
        )

    time_limit = raw.get("time_limit")
    if time_limit is not None:
        _check_type(time_limit, (int, float), f"{location}.time_limit")
        _require(time_limit > 0, f"{location}.time_limit", "must be > 0")
        time_limit = float(time_limit)

    forbid_collisions = raw.get("forbid_collisions", False)
    _check_type(forbid_collisions, bool, f"{location}.forbid_collisions")

    return SuccessCriteria(
        reach_zone=reach_zone,
        visit_sequence=visit_sequence,
        time_limit=time_limit,
        forbid_collisions=forbid_collisions,
    )


def _derive_visual_goal(
    sc: SuccessCriteria | None, regions: tuple[FloorRegion, ...]
) -> Goal | None:
    """If the success criteria points at a single rect zone, expose its
    bounds as a :class:`Goal` so the renderer can outline it.

    Polygon zones and visit-sequence goals don't get a visual outline
    here -- they're already drawn as filled floor regions, which is
    expressive enough.
    """
    if sc is None or sc.reach_zone is None:
        return None
    for r in regions:
        if r.name == sc.reach_zone and r.bounds is not None:
            x, y, w, h = r.bounds
            return Goal(x=x, y=y, w=w, h=h)
    return None
