"""Reading and running VEXcode EXP ``.exppython`` project files directly.

Students save their work as ``.exppython`` (a JSON project file). The
simulator unwraps the program from the ``textContent`` field instead of
making them copy-paste code into a plain ``.py`` file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from vex_sim import grader, runner
from vex_sim.student_source import extract_exppython_source, is_exppython

EMPTY_EXPPYTHON = Path(__file__).parent / "empty.exppython"


def _write_exppython(tmp_path: Path, source: str, name: str = "student.exppython") -> Path:
    """Write a minimal .exppython file wrapping ``source`` in textContent."""
    p = tmp_path / name
    p.write_text(
        json.dumps({"mode": "Text", "hardwareTarget": "brain", "textContent": source}),
        encoding="utf-8",
    )
    return p


# --- source extraction ---------------------------------------------------


def test_is_exppython_by_suffix():
    assert is_exppython("foo.exppython")
    assert is_exppython(Path("a/b/foo.exppython"))
    assert not is_exppython("foo.py")


def test_extract_source_from_bundled_empty_fixture():
    source = extract_exppython_source(EMPTY_EXPPYTHON)
    assert "from vex import *" in source
    assert "VEXcode Generated Robot Configuration" in source


def test_extract_source_roundtrips_textcontent(tmp_path: Path):
    body = "from vex import *\nbrain = Brain()\n"
    p = _write_exppython(tmp_path, body)
    assert extract_exppython_source(p) == body


def test_extract_source_rejects_non_json(tmp_path: Path):
    p = tmp_path / "broken.exppython"
    p.write_text("from vex import *\nbrain = Brain()\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        extract_exppython_source(p)


def test_extract_source_rejects_missing_textcontent(tmp_path: Path):
    p = tmp_path / "nope.exppython"
    p.write_text(json.dumps({"mode": "Text", "robotConfig": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="textContent"):
        extract_exppython_source(p)


def test_extract_source_rejects_non_string_textcontent(tmp_path: Path):
    p = tmp_path / "weird.exppython"
    p.write_text(json.dumps({"textContent": 42}), encoding="utf-8")
    with pytest.raises(ValueError, match="not text"):
        extract_exppython_source(p)


# --- running through the runner ------------------------------------------


def test_runner_runs_bundled_empty_exppython():
    """The VEXcode-generated config block runs to completion (calibration ends)."""
    result = runner.run(EMPTY_EXPPYTHON, max_time=10.0)
    assert result["status"] == "completed"
    assert result["error"] is None
    methods = {(c["obj"], c["method"]) for c in result["calls"]}
    assert ("drivetrain", "SmartDrive") in methods
    assert any(method == "calibrate" for _, method in methods)


def test_runner_runs_student_code_in_exppython(tmp_path: Path):
    p = _write_exppython(
        tmp_path,
        "from vex import *\nbrain = Brain()\nbrain.screen.print('hi')\nprint('hello')\n",
    )
    result = runner.run(p)
    assert result["status"] == "completed"
    assert "hello" in result["stdout"]
    methods = [(c["obj"], c["method"]) for c in result["calls"]]
    assert ("brain.screen", "print") in methods


def test_runner_error_traceback_points_at_exppython(tmp_path: Path):
    p = _write_exppython(
        tmp_path,
        "from vex import *\nbrain = Brain()\nraise ValueError('boom')\n",
    )
    result = runner.run(p)
    assert result["status"] == "error"
    assert result["error"]["type"] == "ValueError"
    tb = result["error"]["traceback"]
    # The traceback frame shows the student's file and the real source line.
    assert "student.exppython" in tb
    assert "raise ValueError('boom')" in tb


def test_runner_times_out_on_unbounded_loop_in_exppython(tmp_path: Path):
    p = _write_exppython(
        tmp_path,
        "from vex import *\nwhile True:\n    wait(50, MSEC)\n",
    )
    result = runner.run(p, max_time=2.0)
    assert result["status"] == "timed_out"


# --- discovery / grading -------------------------------------------------


def test_grader_discovers_exppython_submissions(tmp_path: Path):
    _write_exppython(tmp_path, "from vex import *\n", name="alice.exppython")
    (tmp_path / "bob.py").write_text("from vex import *\n", encoding="utf-8")
    (tmp_path / "_helper.exppython").write_text(json.dumps({"textContent": ""}), encoding="utf-8")
    found = {p.name for p in grader.discover_submissions(tmp_path)}
    assert found == {"alice.exppython", "bob.py"}


# --- CLI end-to-end ------------------------------------------------------


def test_cli_run_accepts_exppython(tmp_path: Path):
    p = _write_exppython(
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
    # empty_room declares success criteria, so a scenario result is emitted.
    assert payload["status"] in {"completed", "timed_out"}
