"""Scenario runner: evaluate a student program against success criteria.

A scenario is the union of:

* a :class:`vex_sim.world.Playground` (geometry + named zones)
* the :class:`vex_sim.world.SuccessCriteria` declared in that playground
* a wall-clock-style budget (``time_limit``, falls back to ``max_time``)

The runner wraps :func:`vex_sim.runner.run` (headless) or
:func:`vex_sim.render.run_live` (visual), then layers an evaluation pass
over the resulting world state to decide pass/fail and emit metrics
useful for marking:

* ``passed``: did every success rule hold?
* ``time_taken``: simulated seconds elapsed when the run ended
* ``distance_travelled_mm``: how far the robot's centre actually moved
* ``collisions``: number of integration substeps clamped by a wall
* ``sensor_reads``: how many calls the student made to a sensor
  (``object_distance``, ``pressing``, ``color``, ...) -- a cheap proxy
  for "did they actually use the sensor I asked them to use"
* ``visited_zones``: ordered list of named regions the centre passed
  through
* ``final_pose``: serialised :class:`vex_sim.world.Pose`

Phase 4 keeps success criteria in the playground file. If Phase 5 needs
to run a single playground under multiple rule sets, split out a
``Scenario`` dataclass that references the playground by name.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vex_sim.world import WORLD, Playground, Pose, SuccessCriteria

#: Sensor methods that count toward ``sensor_reads`` in the scenario
#: result. Constructors and "set_X" calls don't count -- the metric is
#: about reading the world, not configuring the sensor.
_SENSOR_READ_METHODS: frozenset[str] = frozenset(
    {
        "object_distance",
        "is_object_detected",
        "object_size",
        "object_velocity",
        "pressing",
        "color",
        "brightness",
        "hue",
        "is_near_object",
        "heading",
        "rotation",
    }
)


@dataclass
class ScenarioResult:
    playground: str
    passed: bool
    status: str
    reason: str
    time_taken: float
    distance_travelled_mm: float
    collisions: int
    sensor_reads: int
    visited_zones: list[str]
    final_pose: dict[str, float]
    success_criteria: dict[str, Any]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_human(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        lines = [
            f"{verdict}  scenario={self.playground}  status={self.status}",
            f"  reason: {self.reason}",
            f"  time_taken: {self.time_taken:.2f} s",
            f"  distance_travelled: {self.distance_travelled_mm:.1f} mm",
            f"  collisions: {self.collisions}",
            f"  sensor_reads: {self.sensor_reads}",
            f"  visited_zones: {', '.join(self.visited_zones) or '(none)'}",
            f"  final_pose: x={self.final_pose['x']:.1f}, "
            f"y={self.final_pose['y']:.1f}, "
            f"theta={self.final_pose['theta']:.3f} rad",
        ]
        return "\n".join(lines)


def evaluate(
    playground: Playground,
    raw_result: dict[str, Any],
    final_pose: Pose,
    *,
    distance_travelled_mm: float,
    collisions: int,
    visited_zones: list[str],
) -> ScenarioResult:
    """Combine the runner's raw result with world metrics and decide pass/fail.

    Pass conditions (all must hold):

    * The student program ran to completion (status == "completed"),
      OR the only failure was a timeout that the criteria explicitly
      allowed via ``time_limit``.
    * If ``reach_zone`` is set, the named zone appears in
      ``visited_zones``.
    * If ``visit_sequence`` is set, ``visited_zones`` contains those
      names in the same relative order.
    * If ``time_limit`` is set, ``time_taken`` <= ``time_limit``.
    * If ``forbid_collisions`` is True, ``collisions == 0``.
    """
    sc = playground.success_criteria or SuccessCriteria()

    sensor_reads = sum(
        1 for entry in raw_result.get("calls", []) if entry.get("method") in _SENSOR_READ_METHODS
    )
    time_taken = float(raw_result.get("elapsed_sim_time", 0.0))
    status = raw_result.get("status", "unknown")

    failures: list[str] = []

    if status == "error":
        err = raw_result.get("error") or {}
        failures.append(f"student program raised {err.get('type', 'error')}: {err.get('message')}")

    if sc.time_limit is not None and time_taken > sc.time_limit + 1e-6:
        failures.append(f"time_limit exceeded ({time_taken:.2f}s > {sc.time_limit:.2f}s)")
    elif sc.time_limit is None and status == "timed_out":
        failures.append("max_time exceeded with no time_limit set in scenario")

    if sc.reach_zone is not None and sc.reach_zone not in visited_zones:
        failures.append(f"never entered zone {sc.reach_zone!r}")

    if sc.visit_sequence and not _contains_subsequence(visited_zones, sc.visit_sequence):
        failures.append(
            f"did not visit zones in order; required {list(sc.visit_sequence)}, "
            f"actual {visited_zones}"
        )

    if sc.forbid_collisions and collisions > 0:
        failures.append(f"forbid_collisions=True but {collisions} collision substep(s) recorded")

    passed = not failures
    reason = "all criteria met" if passed else "; ".join(failures)

    return ScenarioResult(
        playground=playground.name,
        passed=passed,
        status=status,
        reason=reason,
        time_taken=time_taken,
        distance_travelled_mm=distance_travelled_mm,
        collisions=collisions,
        sensor_reads=sensor_reads,
        visited_zones=list(visited_zones),
        final_pose={"x": final_pose.x, "y": final_pose.y, "theta": final_pose.theta},
        success_criteria={
            "reach_zone": sc.reach_zone,
            "visit_sequence": list(sc.visit_sequence),
            "time_limit": sc.time_limit,
            "forbid_collisions": sc.forbid_collisions,
        },
        raw=raw_result,
    )


def _contains_subsequence(haystack: list[str], needle: tuple[str, ...]) -> bool:
    """True if every item of ``needle`` appears in ``haystack`` in order."""
    if not needle:
        return True
    it = iter(haystack)
    return all(any(h == n for h in it) for n in needle)


def run_scenario(
    student_path: str | Path,
    playground: Playground,
    *,
    render: bool = False,
    speed: float = 1.0,
    max_time: float | None = None,
) -> ScenarioResult:
    """Run a student program against a playground and return a result.

    ``max_time`` defaults to the scenario's ``time_limit`` (or 30 s if
    the scenario has none) so the student program is bounded even when
    no time criterion is declared. The evaluator still flags actual
    timeouts as failures unless ``time_limit`` permits them.
    """
    sc = playground.success_criteria or SuccessCriteria()
    if max_time is None:
        max_time = sc.time_limit if sc.time_limit is not None else 30.0

    if render:
        from vex_sim import render as render_mod  # noqa: PLC0415

        raw = render_mod.run_live(
            student_path,
            max_time=max_time,
            playground=playground,
            speed=speed,
            auto_close_on_complete=True,
        )
    else:
        from vex_sim import runner  # noqa: PLC0415

        raw = runner.run(student_path, max_time=max_time, playground=playground)

    # The runner module finalises the WORLD before returning, so these
    # snapshots reflect the run's terminal state.
    return evaluate(
        playground,
        raw,
        WORLD.pose.copy(),
        distance_travelled_mm=WORLD.distance_travelled_mm,
        collisions=WORLD.collision_count,
        visited_zones=list(WORLD.visited_zones),
    )


def write_result_files(result: ScenarioResult, json_path: Path) -> None:
    """Dump the result as JSON next to the student's working directory."""
    json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
