"""Tests for the JSON playground file format and its loader.

The schema (``playground_files/playground.schema.json``) is the canonical
description; this test suite checks (a) the bundled starter playgrounds
load cleanly, (b) malformed files produce *clear* error messages
pointing at the offending node, and (c) ``load_playground_file`` builds
the right ``Playground`` shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import vex_sim.api  # noqa: F401  -- load api package first to avoid circular import
from vex_sim.playground_loader import (
    PLAYGROUND_DIR,
    PlaygroundFileError,
    discover_playground_files,
    load_playground_file,
)
from vex_sim.world import FloorRegion, SuccessCriteria

# ---------------------------------------------------------------------------
# Bundled playgrounds load and validate
# ---------------------------------------------------------------------------


BUNDLED_NAMES = {
    "empty_room",
    "low_wall_maze",
    "mixed_heights",
    "pickup_and_dropoff",
}


def test_bundled_playground_files_present():
    found = {p.stem for p in discover_playground_files(PLAYGROUND_DIR)}
    assert BUNDLED_NAMES.issubset(found), f"missing playground files: {BUNDLED_NAMES - found}"


@pytest.mark.parametrize("name", sorted(BUNDLED_NAMES))
def test_bundled_playground_loads(name):
    p = PLAYGROUND_DIR / f"{name}.json"
    pg = load_playground_file(p)
    assert pg.name == name
    assert pg.width > 0 and pg.height > 0
    assert pg.walls, "every bundled playground has at least one wall"


def test_pickup_and_dropoff_has_named_zones_and_visit_sequence():
    pg = load_playground_file(PLAYGROUND_DIR / "pickup_and_dropoff.json")
    names = [r.name for r in pg.floor_regions]
    assert names == ["start", "pickup", "dropoff"]
    assert pg.success_criteria is not None
    assert pg.success_criteria.visit_sequence == ("start", "pickup", "dropoff")


def test_low_wall_maze_has_low_walls():
    pg = load_playground_file(PLAYGROUND_DIR / "low_wall_maze.json")
    low_walls = [w for w in pg.walls if w.height_mm == 30.0]
    assert len(low_walls) >= 3, "low_wall_maze should have several low walls"


def test_mixed_heights_has_each_preset():
    pg = load_playground_file(PLAYGROUND_DIR / "mixed_heights.json")
    heights = {w.height_mm for w in pg.walls}
    assert {30.0, 100.0, 200.0}.issubset(heights)


def test_empty_room_visual_goal_derived_from_named_zone():
    """The legacy ``Playground.goal`` rectangle is auto-built from the
    rect-shaped zone the success criteria points at."""
    pg = load_playground_file(PLAYGROUND_DIR / "empty_room.json")
    assert pg.goal is not None
    assert pg.goal.x == 2400.0
    assert pg.goal.y == 2400.0
    assert pg.goal.w == 400.0
    assert pg.goal.h == 400.0


# ---------------------------------------------------------------------------
# Schema violations -> clear errors
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, payload: dict) -> Path:
    f = tmp_path / "scenario.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    return f


def _minimal_payload() -> dict:
    return {
        "name": "demo",
        "size": [1000, 1000],
        "robot_start": [500, 500, 0],
        "walls": [{"start": [0, 0], "end": [1000, 0]}],
    }


def test_missing_required_top_key_reports_clearly(tmp_path):
    payload = _minimal_payload()
    del payload["walls"]
    p = _write(tmp_path, payload)
    with pytest.raises(PlaygroundFileError, match="missing required key.*'walls'"):
        load_playground_file(p)


def test_unknown_top_key_rejected(tmp_path):
    payload = _minimal_payload()
    payload["color_palette"] = {}
    p = _write(tmp_path, payload)
    with pytest.raises(PlaygroundFileError, match="unknown top-level key"):
        load_playground_file(p)


def test_unknown_wall_height_preset_pinpoints_line(tmp_path):
    payload = _minimal_payload()
    payload["walls"] = [
        {"start": [0, 0], "end": [100, 0], "height": "tiny"},
    ]
    p = _write(tmp_path, payload)
    with pytest.raises(PlaygroundFileError, match=r"walls\[0\].height.*unknown wall-height preset"):
        load_playground_file(p)


def test_negative_wall_height_rejected(tmp_path):
    payload = _minimal_payload()
    payload["walls"] = [{"start": [0, 0], "end": [100, 0], "height": -10}]
    p = _write(tmp_path, payload)
    with pytest.raises(PlaygroundFileError, match=r"walls\[0\].height"):
        load_playground_file(p)


def test_floor_region_without_shape_rejected(tmp_path):
    payload = _minimal_payload()
    payload["floor_regions"] = [{"color": "green"}]
    p = _write(tmp_path, payload)
    with pytest.raises(PlaygroundFileError, match=r"floor_regions\[0\]"):
        load_playground_file(p)


def test_polygon_needs_at_least_three_points(tmp_path):
    payload = _minimal_payload()
    payload["floor_regions"] = [{"color": "red", "shape": "polygon", "points": [[0, 0], [100, 0]]}]
    p = _write(tmp_path, payload)
    with pytest.raises(PlaygroundFileError, match=r"polygon needs at least 3"):
        load_playground_file(p)


def test_goal_zone_must_reference_known_region(tmp_path):
    payload = _minimal_payload()
    payload["floor_regions"] = [{"name": "one", "color": "green", "bounds": [0, 0, 100, 100]}]
    payload["goal"] = {"type": "reach_zone", "zone": "two"}
    p = _write(tmp_path, payload)
    with pytest.raises(PlaygroundFileError, match=r"unknown floor region 'two'"):
        load_playground_file(p)


def test_visit_sequence_zone_must_exist(tmp_path):
    payload = _minimal_payload()
    payload["floor_regions"] = [{"name": "a", "color": "green", "bounds": [0, 0, 100, 100]}]
    payload["goal"] = {"type": "visit_sequence", "zones": ["a", "b"]}
    p = _write(tmp_path, payload)
    with pytest.raises(PlaygroundFileError, match=r"unknown floor region 'b'"):
        load_playground_file(p)


def test_invalid_json_reports_line_number(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(PlaygroundFileError, match="invalid JSON at line"):
        load_playground_file(f)


# ---------------------------------------------------------------------------
# Builder shape sanity
# ---------------------------------------------------------------------------


def test_loader_round_trip_polygon_region(tmp_path):
    payload = _minimal_payload()
    payload["floor_regions"] = [
        {
            "name": "triangle",
            "color": "yellow",
            "points": [[0, 0], [200, 0], [100, 200]],
        }
    ]
    payload["goal"] = {"type": "reach_zone", "zone": "triangle"}
    p = _write(tmp_path, payload)
    pg = load_playground_file(p)
    assert isinstance(pg.floor_regions[0], FloorRegion)
    assert pg.floor_regions[0].points == ((0.0, 0.0), (200.0, 0.0), (100.0, 200.0))
    # No visual Goal for polygon zones -- they are drawn as filled regions.
    assert pg.goal is None
    assert isinstance(pg.success_criteria, SuccessCriteria)
    assert pg.success_criteria.reach_zone == "triangle"


def test_get_playground_accepts_file_path(tmp_path):
    """``get_playground`` should treat anything containing a path
    separator or .json extension as a file path, not a bundled name."""
    from vex_sim.playgrounds import get_playground  # noqa: PLC0415

    payload = _minimal_payload()
    p = _write(tmp_path, payload)
    pg = get_playground(str(p))
    assert pg.name == "demo"
