from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from vex_sim import runner

FIXTURES = Path(__file__).parent / "fixtures"
BALL_COLLECTOR = FIXTURES / "student_ball_collector.py"


def _write_fixture(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "student.py"
    p.write_text(body, encoding="utf-8")
    return p


def test_runner_completes_minimal_program(tmp_path: Path):
    p = _write_fixture(
        tmp_path,
        "from vex import *\nbrain = Brain()\nbrain.screen.print('hi')\n",
    )
    result = runner.run(p)
    assert result["status"] == "completed"
    assert result["error"] is None
    methods = [(c["obj"], c["method"]) for c in result["calls"]]
    assert ("brain", "Brain") in methods
    assert ("brain.screen", "print") in methods


def test_runner_times_out_on_unbounded_loop(tmp_path: Path):
    p = _write_fixture(
        tmp_path,
        "from vex import *\nwhile True:\n    wait(50, MSEC)\n",
    )
    result = runner.run(p, max_time=2.0)
    assert result["status"] == "timed_out"
    assert result["elapsed_sim_time"] > 2.0
    assert result["elapsed_sim_time"] < 2.5


def test_runner_reports_error(tmp_path: Path):
    p = _write_fixture(
        tmp_path,
        "from vex import *\nraise ValueError('boom')\n",
    )
    result = runner.run(p)
    assert result["status"] == "error"
    assert result["error"]["type"] == "ValueError"
    assert "boom" in result["error"]["message"]


def test_runner_captures_stdout(tmp_path: Path):
    p = _write_fixture(
        tmp_path,
        "from vex import *\nprint('hello world')\n",
    )
    result = runner.run(p)
    assert "hello world" in result["stdout"]


def test_runner_urandom_shim_works(tmp_path: Path):
    p = _write_fixture(
        tmp_path,
        "import urandom\nurandom.seed(42)\nx = urandom.random()\n",
    )
    result = runner.run(p)
    assert result["status"] == "completed"


def test_runner_sysmodules_cleanup(tmp_path: Path):
    p = _write_fixture(tmp_path, "from vex import *\n")
    runner.run(p)
    # Synthetic modules should be removed after the run.
    assert "vex" not in sys.modules
    assert "urandom" not in sys.modules


def test_runner_ball_collector_fixture_runs():
    """The user's real student program runs to timeout and produces a sensible log."""
    result = runner.run(BALL_COLLECTOR, max_time=5.0)
    assert result["status"] == "timed_out"
    assert 5.0 < result["elapsed_sim_time"] < 5.2
    methods = {(c["obj"], c["method"]) for c in result["calls"]}
    # Setup phase
    assert ("brain", "Brain") in methods
    assert ("inertial_brain", "Inertial") in methods
    assert ("motor_port6", "Motor") in methods
    assert ("motor_port10", "Motor") in methods
    assert ("drivetrain", "SmartDrive") in methods
    assert ("bumper_3wire_d", "Bumper") in methods
    assert ("bumper_3wire_f", "Bumper") in methods
    assert ("distance_port1", "Distance") in methods
    assert ("optical_port7", "Optical") in methods
    # Calibration phase
    assert ("brain.screen", "print") in methods
    assert ("inertial_brain", "calibrate") in methods
    # Main loop fires the else branch repeatedly
    assert ("drivetrain", "drive") in methods


def test_runner_ball_collector_else_branch_dominates():
    """With default sensor values, every loop iteration runs `drivetrain.drive(FORWARD)`."""
    result = runner.run(BALL_COLLECTOR, max_time=3.0)
    drives = [c for c in result["calls"] if c["obj"] == "drivetrain" and c["method"] == "drive"]
    waits_50ms = [
        c
        for c in result["calls"]
        if c["obj"] == "" and c["method"] == "wait" and c["args"] == [50, "msec"]
    ]
    assert len(drives) > 30  # ~50 iterations in 3s
    assert len(waits_50ms) > 30


def test_cli_run_subcommand_writes_json(tmp_path: Path):
    out = tmp_path / "result.json"
    rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vex_sim",
            "run",
            str(BALL_COLLECTOR),
            "--max-time",
            "1.5",
            "--out",
            str(out),
        ],
        check=True,
    )
    assert rc.returncode == 0
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    # Phase 4: empty_room declares success criteria so the CLI emits a
    # scenario result. The Phase 3 raw call-log is nested under "raw".
    assert payload["status"] == "timed_out"
    assert payload["passed"] is False  # 1.5 s isn't enough to reach the goal
    assert "calls" in payload["raw"]


def test_cli_run_to_stdout_json(tmp_path: Path):
    p = _write_fixture(
        tmp_path,
        "from vex import *\nbrain = Brain()\n",
    )
    completed = subprocess.run(
        [sys.executable, "-m", "vex_sim", "run", str(p), "--max-time", "1.0"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["status"] == "completed"


def test_cli_no_command_returns_zero():
    completed = subprocess.run(
        [sys.executable, "-m", "vex_sim"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


@pytest.mark.parametrize(
    "fixture_body",
    [
        "from vex import *\nimport math\nx = math.sqrt(4)\n",
        "from vex import *\nfor _ in range(10):\n    wait(10, MSEC)\n",
    ],
)
def test_runner_various_completed_programs(tmp_path: Path, fixture_body: str):
    p = _write_fixture(tmp_path, fixture_body)
    result = runner.run(p)
    assert result["status"] == "completed"
