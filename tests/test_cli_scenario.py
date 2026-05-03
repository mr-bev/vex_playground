"""End-to-end CLI tests for the Phase 4 scenario runner.

These exercise the JSON layout and exit-code conventions advertised by
``python -m vex_sim run`` when the chosen playground declares success
criteria.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path


def _student(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "student.py"
    p.write_text(body, encoding="utf-8")
    return p


def test_cli_scenario_json_payload_shape(tmp_path: Path):
    student = _student(
        tmp_path,
        textwrap.dedent("""
            from vex import *
            brain = Brain()
            wait(0.1, SEC)
        """),
    )
    out = tmp_path / "result.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vex_sim",
            "run",
            str(student),
            "--playground",
            "empty_room",
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    # Exit 0 even on scenario fail (per CLI contract: pass/fail is in JSON).
    assert proc.returncode == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    expected = {
        "playground",
        "passed",
        "status",
        "reason",
        "time_taken",
        "distance_travelled_mm",
        "collisions",
        "sensor_reads",
        "visited_zones",
        "final_pose",
        "success_criteria",
        "raw",
    }
    assert expected.issubset(payload.keys())
    assert payload["playground"] == "empty_room"


def test_cli_scenario_human_summary_on_stderr(tmp_path: Path):
    student = _student(tmp_path, "from vex import *\nbrain = Brain()\n")
    proc = subprocess.run(
        [sys.executable, "-m", "vex_sim", "run", str(student), "--playground", "empty_room"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "FAIL" in proc.stderr or "PASS" in proc.stderr
    assert "scenario=empty_room" in proc.stderr


def test_cli_list_outputs_each_bundled_playground():
    proc = subprocess.run(
        [sys.executable, "-m", "vex_sim", "list"],
        check=True,
        capture_output=True,
        text=True,
    )
    out = proc.stdout.splitlines()
    assert "empty_room" in out
    assert "low_wall_maze" in out
    assert "mixed_heights" in out
    assert "pickup_and_dropoff" in out


def test_cli_run_with_external_json_playground(tmp_path: Path):
    pg_file = tmp_path / "custom.json"
    pg_file.write_text(
        json.dumps(
            {
                "name": "custom",
                "size": [1000, 1000],
                "robot_start": [500, 500, 0],
                "walls": [{"start": [0, 0], "end": [1000, 0]}],
                "floor_regions": [
                    {"name": "goal", "color": "green", "bounds": [600, 400, 200, 200]}
                ],
                "goal": {"type": "reach_zone", "zone": "goal", "time_limit": 10},
            }
        ),
        encoding="utf-8",
    )
    student = _student(
        tmp_path,
        textwrap.dedent("""
            from vex import *
            brain = Brain()
            lm = Motor(Ports.PORT6, False)
            rm = Motor(Ports.PORT10, True)
            dt = DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)
            dt.drive_for(FORWARD, 250, MM, velocity=200)
        """),
    )
    out = tmp_path / "result.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vex_sim",
            "run",
            str(student),
            "--playground",
            str(pg_file),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["playground"] == "custom"
    assert payload["passed"] is True
