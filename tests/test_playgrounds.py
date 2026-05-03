"""Tests for vex_sim.playgrounds: shape and contents of the bundled scenarios."""

from __future__ import annotations

import math

import pytest

from vex_sim.playgrounds import EMPTY_ROOM, PLAYGROUNDS, get_playground


def test_empty_room_registered_by_name():
    assert "empty_room" in PLAYGROUNDS
    assert get_playground("empty_room") is EMPTY_ROOM


def test_unknown_playground_raises():
    with pytest.raises(KeyError):
        get_playground("does_not_exist")


def test_empty_room_is_3m_square():
    assert EMPTY_ROOM.width == pytest.approx(3000.0)
    assert EMPTY_ROOM.height == pytest.approx(3000.0)


def test_empty_room_has_four_walls():
    assert len(EMPTY_ROOM.walls) == 4
    # Walls form a closed loop along the room boundary.
    points = {(w.x1, w.y1) for w in EMPTY_ROOM.walls} | {(w.x2, w.y2) for w in EMPTY_ROOM.walls}
    expected_corners = {
        (0.0, 0.0),
        (3000.0, 0.0),
        (3000.0, 3000.0),
        (0.0, 3000.0),
    }
    assert points == expected_corners


def test_empty_room_has_goal_inside_bounds():
    g = EMPTY_ROOM.goal
    assert g is not None
    assert 0.0 <= g.x <= EMPTY_ROOM.width
    assert 0.0 <= g.y <= EMPTY_ROOM.height
    assert g.x + g.w <= EMPTY_ROOM.width
    assert g.y + g.h <= EMPTY_ROOM.height


def test_empty_room_starts_robot_at_centre_facing_up():
    p = EMPTY_ROOM.start_pose
    assert p.x == pytest.approx(EMPTY_ROOM.width / 2.0)
    assert p.y == pytest.approx(EMPTY_ROOM.height / 2.0)
    # Facing +y so "FORWARD" looks like "up" on screen.
    assert p.theta == pytest.approx(math.pi / 2.0)
