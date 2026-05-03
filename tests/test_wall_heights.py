"""Tests for wall heights and the ``parse_wall_height`` helper.

Walls in the simulator are 2D line segments with a height in mm. Three
named presets ("low" / "mid" / "tall") expand to numeric millimetres;
arbitrary numeric heights are also accepted. The default when nothing is
specified is the "tall" preset (200 mm), so legacy two-arg ``Wall``
construction stays a full-height wall.
"""

from __future__ import annotations

import pytest

import vex_sim.api  # noqa: F401  -- load the api package first (others do this)
from vex_sim.world import (
    DEFAULT_WALL_HEIGHT_MM,
    WALL_HEIGHT_PRESETS,
    Wall,
    parse_wall_height,
)


def test_default_height_is_tall_preset():
    assert WALL_HEIGHT_PRESETS["tall"] == DEFAULT_WALL_HEIGHT_MM
    assert WALL_HEIGHT_PRESETS == {"low": 30.0, "mid": 100.0, "tall": 200.0}


def test_wall_default_height_is_tall():
    """A two-arg-style Wall built with positional coordinates is tall."""
    w = Wall(0.0, 0.0, 100.0, 0.0)
    assert w.height_mm == DEFAULT_WALL_HEIGHT_MM


def test_wall_with_explicit_numeric_height():
    w = Wall(0.0, 0.0, 100.0, 0.0, height_mm=75.0)
    assert w.height_mm == 75.0


@pytest.mark.parametrize(
    "preset,expected",
    [("low", 30.0), ("mid", 100.0), ("tall", 200.0)],
)
def test_parse_wall_height_string_presets(preset, expected):
    assert parse_wall_height(preset) == expected


def test_parse_wall_height_is_case_insensitive():
    assert parse_wall_height("TALL") == 200.0
    assert parse_wall_height("Mid") == 100.0


def test_parse_wall_height_accepts_numeric():
    assert parse_wall_height(50) == 50.0
    assert parse_wall_height(123.4) == 123.4


def test_parse_wall_height_none_is_default():
    assert parse_wall_height(None) == DEFAULT_WALL_HEIGHT_MM


def test_parse_wall_height_rejects_unknown_preset():
    with pytest.raises(ValueError, match="unknown wall-height preset"):
        parse_wall_height("medium")  # student typo: "mid" is the canonical name


def test_parse_wall_height_rejects_zero_or_negative():
    with pytest.raises(ValueError):
        parse_wall_height(0)
    with pytest.raises(ValueError):
        parse_wall_height(-50)


def test_parse_wall_height_rejects_non_numeric_non_string():
    with pytest.raises(TypeError):
        parse_wall_height([100])  # type: ignore[arg-type]


# -------------------------------------------------------------------------
# Render category snapping (continuous heights -> nearest preset for colour)
# -------------------------------------------------------------------------


def test_render_wall_category_snaps_to_nearest_preset():
    pytest.importorskip("pygame")
    from vex_sim.render import _wall_category

    # Exact preset values land on themselves.
    assert _wall_category(30.0) == "low"
    assert _wall_category(100.0) == "mid"
    assert _wall_category(200.0) == "tall"

    # 70 mm is between low (30) and mid (100); closer to mid.
    assert _wall_category(70.0) == "mid"
    # 50 mm is closer to low (delta 20) than mid (delta 50).
    assert _wall_category(50.0) == "low"
    # 300 mm is well past tall but still snaps to tall.
    assert _wall_category(300.0) == "tall"
