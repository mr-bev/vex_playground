"""Tests for the scenario runner: success criteria evaluation, metrics,
pass/fail, and end-to-end execution against a real student program."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

import vex_sim.api  # noqa: F401  -- load api package first
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.playground_loader import PLAYGROUND_DIR, load_playground_file
from vex_sim.scenario import (
    ScenarioResult,
    _contains_subsequence,
    evaluate,
    run_scenario,
)
from vex_sim.world import (
    WORLD,
    FloorRegion,
    Playground,
    Pose,
    SuccessCriteria,
    Wall,
)


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    WORLD.reset()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    WORLD.reset()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_contains_subsequence_basics():
    assert _contains_subsequence(["a", "b", "c"], ("a", "c"))
    assert _contains_subsequence(["a", "b", "c"], ("a", "b", "c"))
    assert not _contains_subsequence(["a", "c", "b"], ("a", "b", "c"))
    assert _contains_subsequence([], ())
    assert not _contains_subsequence([], ("a",))


# ---------------------------------------------------------------------------
# Evaluator: combine raw runner result + world metrics into a ScenarioResult
# ---------------------------------------------------------------------------


def _empty_pg(criteria: SuccessCriteria | None) -> Playground:
    return Playground(
        name="test",
        width=1000.0,
        height=1000.0,
        walls=(Wall(0, 0, 1000, 0),),
        goal=None,
        start_pose=Pose(500, 500, 0),
        floor_regions=(),
        success_criteria=criteria,
    )


def _completed_raw(elapsed: float = 1.0, calls: list | None = None) -> dict:
    return {
        "status": "completed",
        "max_time": 30.0,
        "elapsed_sim_time": elapsed,
        "error": None,
        "stdout": "",
        "calls": calls or [],
    }


def test_evaluate_pass_when_no_criteria_and_program_completes():
    pg = _empty_pg(None)
    result = evaluate(
        pg,
        _completed_raw(elapsed=1.0),
        Pose(100, 100, 0),
        distance_travelled_mm=200.0,
        collisions=0,
        visited_zones=[],
    )
    assert result.passed is True
    assert "all criteria met" in result.reason


def test_evaluate_fails_when_zone_not_reached():
    pg = _empty_pg(SuccessCriteria(reach_zone="goal"))
    result = evaluate(
        pg,
        _completed_raw(),
        Pose(0, 0, 0),
        distance_travelled_mm=0.0,
        collisions=0,
        visited_zones=["other"],
    )
    assert result.passed is False
    assert "never entered zone 'goal'" in result.reason


def test_evaluate_passes_when_zone_reached():
    pg = _empty_pg(SuccessCriteria(reach_zone="goal"))
    result = evaluate(
        pg,
        _completed_raw(),
        Pose(0, 0, 0),
        distance_travelled_mm=500.0,
        collisions=0,
        visited_zones=["start", "goal"],
    )
    assert result.passed is True


def test_evaluate_visit_sequence_in_order():
    pg = _empty_pg(SuccessCriteria(visit_sequence=("a", "b", "c")))
    result = evaluate(
        pg,
        _completed_raw(),
        Pose(0, 0, 0),
        distance_travelled_mm=0.0,
        collisions=0,
        visited_zones=["a", "x", "b", "c"],
    )
    assert result.passed is True


def test_evaluate_visit_sequence_out_of_order_fails():
    pg = _empty_pg(SuccessCriteria(visit_sequence=("a", "b", "c")))
    result = evaluate(
        pg,
        _completed_raw(),
        Pose(0, 0, 0),
        distance_travelled_mm=0.0,
        collisions=0,
        visited_zones=["b", "a", "c"],
    )
    assert result.passed is False
    assert "did not visit zones in order" in result.reason


def test_evaluate_time_limit_exceeded_fails():
    pg = _empty_pg(SuccessCriteria(reach_zone="goal", time_limit=10.0))
    result = evaluate(
        pg,
        {**_completed_raw(elapsed=12.0), "status": "timed_out"},
        Pose(0, 0, 0),
        distance_travelled_mm=0.0,
        collisions=0,
        visited_zones=["goal"],
    )
    assert result.passed is False
    assert "time_limit exceeded" in result.reason


def test_evaluate_forbid_collisions_fails_with_any_collision():
    pg = _empty_pg(SuccessCriteria(reach_zone="goal", forbid_collisions=True))
    result = evaluate(
        pg,
        _completed_raw(),
        Pose(0, 0, 0),
        distance_travelled_mm=100.0,
        collisions=3,
        visited_zones=["goal"],
    )
    assert result.passed is False
    assert "forbid_collisions=True" in result.reason


def test_evaluate_student_error_fails():
    pg = _empty_pg(SuccessCriteria(reach_zone="goal"))
    raw = {
        **_completed_raw(),
        "status": "error",
        "error": {"type": "ZeroDivisionError", "message": "div by zero", "traceback": "..."},
    }
    result = evaluate(
        pg,
        raw,
        Pose(0, 0, 0),
        distance_travelled_mm=0.0,
        collisions=0,
        visited_zones=["goal"],
    )
    assert result.passed is False
    assert "ZeroDivisionError" in result.reason


def test_evaluate_counts_sensor_reads():
    pg = _empty_pg(None)
    calls = [
        {"t": 0.1, "obj": "distance_port1", "method": "object_distance", "args": [], "kwargs": {}},
        {"t": 0.2, "obj": "distance_port1", "method": "object_distance", "args": [], "kwargs": {}},
        {"t": 0.3, "obj": "bumper_3wire_a", "method": "pressing", "args": [], "kwargs": {}},
        # Constructor doesn't count
        {"t": 0.0, "obj": "distance_port1", "method": "Distance", "args": [1], "kwargs": {}},
        # set_X is configuration, not a read
        {"t": 0.4, "obj": "optical_port7", "method": "set_light", "args": ["on"], "kwargs": {}},
    ]
    result = evaluate(
        pg,
        _completed_raw(calls=calls),
        Pose(0, 0, 0),
        distance_travelled_mm=0.0,
        collisions=0,
        visited_zones=[],
    )
    assert result.sensor_reads == 3


# ---------------------------------------------------------------------------
# End-to-end against a real student program + bundled playground
# ---------------------------------------------------------------------------


def test_run_scenario_end_to_end_passes_when_zone_reached(tmp_path: Path):
    pg = load_playground_file(PLAYGROUND_DIR / "empty_room.json")
    student = tmp_path / "student.py"
    student.write_text(
        textwrap.dedent("""
            from vex import *
            brain = Brain()
            lm = Motor(Ports.PORT6, False)
            rm = Motor(Ports.PORT10, True)
            dt = DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)
            # Goal zone is at (2400,2400, 400x400) -> centre ~(2600, 2600).
            # Start: (1500, 1500, theta=pi/2 facing +y).
            # Drive +y by 1100 mm, turn right, drive +x by 1100 mm.
            dt.drive_for(FORWARD, 1100, MM, velocity=200)
            dt.turn_for(RIGHT, 90, DEGREES, velocity=100)
            dt.drive_for(FORWARD, 1100, MM, velocity=200)
        """),
        encoding="utf-8",
    )
    result = run_scenario(student, pg, render=False)
    assert result.passed, result.reason
    assert "goal" in result.visited_zones
    assert result.collisions == 0
    assert result.distance_travelled_mm > 1000.0
    assert result.final_pose["x"] > 2400.0


def test_run_scenario_end_to_end_fails_when_program_stays_still(tmp_path: Path):
    pg = load_playground_file(PLAYGROUND_DIR / "empty_room.json")
    student = tmp_path / "student.py"
    student.write_text(
        textwrap.dedent("""
            from vex import *
            brain = Brain()
            wait(1, SEC)
        """),
        encoding="utf-8",
    )
    result = run_scenario(student, pg, render=False)
    assert result.passed is False
    assert "never entered zone 'goal'" in result.reason


def test_run_scenario_returns_serialisable_result(tmp_path: Path):
    pg = load_playground_file(PLAYGROUND_DIR / "empty_room.json")
    student = tmp_path / "student.py"
    student.write_text("from vex import *\nbrain = Brain()\nwait(0.1, SEC)\n", encoding="utf-8")
    result = run_scenario(student, pg, render=False)
    payload = json.dumps(result.to_dict())
    assert "playground" in payload and "passed" in payload


def test_visit_sequence_passes_for_zone_walk(tmp_path: Path):
    """Walk through a three-zone playground in the right order."""
    region_a = FloorRegion(color="green", name="a", bounds=(0, 0, 200, 1000))
    region_b = FloorRegion(color="blue", name="b", bounds=(900, 0, 200, 1000))
    region_c = FloorRegion(color="red", name="c", bounds=(1800, 0, 200, 1000))
    pg = Playground(
        name="three_zones",
        width=2000,
        height=1000,
        walls=(),
        goal=None,
        start_pose=Pose(100, 500, 0),  # facing +x, in zone a
        floor_regions=(region_a, region_b, region_c),
        success_criteria=SuccessCriteria(visit_sequence=("a", "b", "c"), time_limit=30.0),
    )
    student = tmp_path / "student.py"
    student.write_text(
        textwrap.dedent("""
            from vex import *
            brain = Brain()
            lm = Motor(Ports.PORT6, False)
            rm = Motor(Ports.PORT10, True)
            dt = DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)
            dt.drive_for(FORWARD, 1850, MM, velocity=200)
        """),
        encoding="utf-8",
    )
    result = run_scenario(student, pg, render=False)
    assert result.passed, f"reason={result.reason} visited={result.visited_zones}"
    assert result.visited_zones == ["a", "b", "c"]


def test_human_output_includes_metrics():
    result = ScenarioResult(
        playground="demo",
        passed=True,
        status="completed",
        reason="all criteria met",
        time_taken=2.5,
        distance_travelled_mm=400.0,
        collisions=0,
        sensor_reads=5,
        visited_zones=["start", "goal"],
        final_pose={"x": 100.0, "y": 200.0, "theta": 0.0},
        success_criteria={
            "reach_zone": "goal",
            "visit_sequence": [],
            "time_limit": 30.0,
            "forbid_collisions": False,
        },
    )
    out = result.to_human()
    assert "PASS" in out
    assert "demo" in out
    assert "sensor_reads: 5" in out
    assert "visited_zones: start, goal" in out
