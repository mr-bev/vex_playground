"""Hardcoded playgrounds for the simulator.

A playground is a self-contained scenario: a bounded room, a fixed start
pose, and (optionally) a goal zone. Phase 2 ships a single empty room.
Future phases will add playgrounds that exercise sensors and obstacles.
"""

from __future__ import annotations

import math

from vex_sim.world import Goal, Playground, Pose, Wall

# 3 m square room. Robot starts in the centre, facing +y (theta = pi/2)
# so that "forward" on the screen looks like "up" in the rendered view.
_ROOM_SIZE_MM = 3000.0

EMPTY_ROOM = Playground(
    name="empty_room",
    width=_ROOM_SIZE_MM,
    height=_ROOM_SIZE_MM,
    walls=(
        Wall(0.0, 0.0, _ROOM_SIZE_MM, 0.0),
        Wall(_ROOM_SIZE_MM, 0.0, _ROOM_SIZE_MM, _ROOM_SIZE_MM),
        Wall(_ROOM_SIZE_MM, _ROOM_SIZE_MM, 0.0, _ROOM_SIZE_MM),
        Wall(0.0, _ROOM_SIZE_MM, 0.0, 0.0),
    ),
    goal=Goal(x=2400.0, y=2400.0, w=400.0, h=400.0),
    start_pose=Pose(x=_ROOM_SIZE_MM / 2.0, y=_ROOM_SIZE_MM / 2.0, theta=math.pi / 2.0),
)


PLAYGROUNDS: dict[str, Playground] = {
    EMPTY_ROOM.name: EMPTY_ROOM,
}


def get_playground(name: str) -> Playground:
    try:
        return PLAYGROUNDS[name]
    except KeyError as e:
        known = ", ".join(sorted(PLAYGROUNDS)) or "(none)"
        raise KeyError(f"unknown playground {name!r}; known: {known}") from e
