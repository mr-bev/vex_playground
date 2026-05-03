"""Bundled playgrounds for the simulator.

Phase 4 onward: playgrounds are JSON files in
``src/vex_sim/playground_files/``, validated against
``playground.schema.json`` by :mod:`vex_sim.playground_loader`. The
files are discovered and loaded once at import time so the rest of the
codebase can keep treating :data:`PLAYGROUNDS` as a static dict keyed
by playground name -- exactly as it did in Phases 2 and 3.

To add a new playground, drop a ``my_scenario.json`` file in the
``playground_files/`` directory. It will be discovered automatically.
There is no Python code to edit, no module to register the file in.

Pedagogical context
-------------------

A playground bundles three things:

1. **Geometry** -- walls (with heights in mm) and a robot start pose.
2. **Floor regions** -- coloured patches the optical sensor can read,
   and / or named "zones" the scenario runner uses for success rules.
3. **Success criteria** -- pass/fail rules (reach a zone, visit zones
   in order, time limit, optionally forbid wall collisions).

Wall heights are central to the simulator's teaching value: the world
is rendered top-down but a 30 mm "low" wall is invisible to a distance
sensor mounted at 100 mm. Run a low-mount sensor to see the same wall.
This is exactly the failure mode that bites real EXP builds.
"""

from __future__ import annotations

from vex_sim.playground_loader import (
    PLAYGROUND_DIR,
    discover_playground_files,
    load_playground_file,
)
from vex_sim.world import Playground


def _load_bundled() -> dict[str, Playground]:
    out: dict[str, Playground] = {}
    for path in discover_playground_files(PLAYGROUND_DIR):
        pg = load_playground_file(path)
        if pg.name in out:
            raise RuntimeError(
                f"playground name collision: {pg.name!r} declared in both "
                f"{out[pg.name].name} and {path.name}"
            )
        out[pg.name] = pg
    return out


PLAYGROUNDS: dict[str, Playground] = _load_bundled()

#: The default playground -- a 3 m square room with a single goal zone.
#: Matches the Phase 2/3 EMPTY_ROOM constant so existing imports don't
#: break.
EMPTY_ROOM: Playground = PLAYGROUNDS["empty_room"]


def get_playground(name: str) -> Playground:
    """Return a bundled playground by name.

    Accepts either a bundled name (``"empty_room"``,
    ``"low_wall_maze"``, ...) or a path to a custom JSON file. Path
    detection is intentionally lax: anything containing ``/``, ``\\``,
    or ending in ``.json`` is treated as a file path.
    """
    if name.endswith(".json") or "/" in name or "\\" in name:
        return load_playground_file(name)
    try:
        return PLAYGROUNDS[name]
    except KeyError as e:
        known = ", ".join(sorted(PLAYGROUNDS)) or "(none)"
        raise KeyError(f"unknown playground {name!r}; known: {known}") from e
