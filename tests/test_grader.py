"""Tests for the Phase 5 batch grader.

Covers:
  * subprocess crash isolation -- a syntax error or unhandled exception
    in one submission doesn't take down the run, just produces a result
    row with an error_type.
  * wall-clock timeout -- a submission that loops forever in pure Python
    (no ``wait`` call to hand control back to the scheduler) gets killed
    at the wall budget, and the rest of the batch carries on.
  * happy-path PASS -- a working submission against the empty_room
    scenario produces ``passed=True``.
  * CSV / JSON output shape and the HTML matrix.
  * The ``grade`` CLI subcommand end-to-end.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from vex_sim import grader

# Single bundled scenario gives us an end-to-end PASS without dragging
# the whole bundled set into every test.
EMPTY_ROOM_FILE = (
    Path(__file__).parents[1] / "src" / "vex_sim" / "playground_files" / "empty_room.json"
)


def _write(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _passing_submission(tmp_path: Path) -> Path:
    # empty_room: start (1500, 1500, theta=pi/2 facing +y); goal box
    # at (2400..2800, 2400..2800). Drive forward then right.
    return _write(
        tmp_path / "passes.py",
        """
        from vex import *
        brain = Brain()
        lm = Motor(Ports.PORT6, False)
        rm = Motor(Ports.PORT10, True)
        dt = DriveTrain(lm, rm, 259.34, 320, 40, MM, 1)
        dt.drive_for(FORWARD, 1100, MM)
        dt.turn_for(RIGHT, 90, DEGREES)
        dt.drive_for(FORWARD, 1100, MM)
        dt.stop()
        """,
    )


def _crashing_submission(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "crashes.py",
        """
        from vex import *
        brain = Brain()
        raise RuntimeError("boom from student code")
        """,
    )


def _infinite_loop_submission(tmp_path: Path) -> Path:
    # Pure Python loop with no wait() call: never yields back to the
    # scheduler, so only the wall-clock subprocess timeout can stop it.
    return _write(
        tmp_path / "loops.py",
        """
        from vex import *
        brain = Brain()
        while True:
            pass
        """,
    )


# ---------------------------------------------------------------------------
# unit: discover_*
# ---------------------------------------------------------------------------


def test_discover_submissions_skips_dunder_files(tmp_path: Path):
    (tmp_path / "good.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "_helpers.py").write_text("# skip me\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not python\n", encoding="utf-8")
    found = grader.discover_submissions(tmp_path)
    assert [p.name for p in found] == ["good.py"]


def test_discover_submissions_accepts_single_file(tmp_path: Path):
    f = tmp_path / "one.py"
    f.write_text("print('hi')\n", encoding="utf-8")
    assert grader.discover_submissions(f) == [f]


def test_discover_scenarios_skips_schema(tmp_path: Path):
    (tmp_path / "playground.schema.json").write_text("{}", encoding="utf-8")
    (tmp_path / "real.json").write_text("{}", encoding="utf-8")
    found = grader.discover_scenarios(tmp_path)
    assert [p.name for p in found] == ["real.json"]


def test_discover_submissions_missing_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        grader.discover_submissions(tmp_path / "nope")


# ---------------------------------------------------------------------------
# integration: run_one
# ---------------------------------------------------------------------------


def test_run_one_passes_for_working_submission(tmp_path: Path):
    sub = _passing_submission(tmp_path)
    r = grader.run_one(sub, EMPTY_ROOM_FILE, timeout=60.0)
    assert r.submission == "passes.py"
    assert r.scenario == "empty_room"
    assert r.passed is True
    assert r.status == "completed"
    assert r.distance_travelled_mm > 0
    assert r.error_type is None


def test_run_one_records_student_exception(tmp_path: Path):
    sub = _crashing_submission(tmp_path)
    r = grader.run_one(sub, EMPTY_ROOM_FILE, timeout=60.0)
    assert r.passed is False
    assert r.status == "error"
    assert r.error_type == "RuntimeError"
    assert "boom from student code" in (r.error_message or "")


def test_run_one_wall_timeout_kills_infinite_loop(tmp_path: Path):
    sub = _infinite_loop_submission(tmp_path)
    r = grader.run_one(sub, EMPTY_ROOM_FILE, timeout=2.0)
    assert r.passed is False
    assert r.status == "wall_timeout"
    # The wall_timeout reason carries the configured budget so a marker
    # can see at a glance which submissions were killed by the harness
    # rather than by a real failure.
    assert "2.0s" in r.reason
    # Wall time should be close to the timeout, not vastly above it
    # (we don't assert a tight bound: subprocess teardown on Windows
    # can add a second or so).
    assert r.runtime_wall_seconds < 10.0


# ---------------------------------------------------------------------------
# integration: grade() composes pairs and isolates failures
# ---------------------------------------------------------------------------


def test_grade_isolates_failures(tmp_path: Path):
    subs = [_passing_submission(tmp_path), _crashing_submission(tmp_path)]
    results = grader.grade(
        subs,
        [EMPTY_ROOM_FILE],
        timeout=30.0,
    )
    assert len(results) == 2
    by_name = {r.submission: r for r in results}
    assert by_name["passes.py"].passed is True
    assert by_name["crashes.py"].passed is False
    assert by_name["crashes.py"].error_type == "RuntimeError"


def test_grade_workers_parallel_matches_serial(tmp_path: Path):
    subs = [
        _passing_submission(tmp_path),
        _crashing_submission(tmp_path),
    ]
    serial = grader.grade(subs, [EMPTY_ROOM_FILE], timeout=30.0, workers=1)
    parallel = grader.grade(subs, [EMPTY_ROOM_FILE], timeout=30.0, workers=2)
    # Pass/fail and error-types must match regardless of worker count;
    # numeric metrics from subprocess timing are allowed to drift.
    assert [(r.submission, r.passed, r.error_type) for r in serial] == [
        (r.submission, r.passed, r.error_type) for r in parallel
    ]


# ---------------------------------------------------------------------------
# output formats
# ---------------------------------------------------------------------------


def test_write_csv_round_trip(tmp_path: Path):
    sub = _passing_submission(tmp_path)
    results = grader.grade([sub], [EMPTY_ROOM_FILE], timeout=30.0)
    out = tmp_path / "results.csv"
    grader.write_csv(results, out)
    rows = list(csv.DictReader(out.open(encoding="utf-8", newline="")))
    assert len(rows) == 1
    row = rows[0]
    assert set(grader.CSV_FIELDS).issubset(row.keys())
    assert row["submission"] == "passes.py"
    assert row["scenario"] == "empty_room"
    assert row["passed"] == "true"


def test_write_json_round_trip(tmp_path: Path):
    sub = _passing_submission(tmp_path)
    results = grader.grade([sub], [EMPTY_ROOM_FILE], timeout=30.0)
    out = tmp_path / "results.json"
    grader.write_json(results, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["submission"] == "passes.py"
    assert data[0]["passed"] is True


def test_write_html_renders_matrix_with_pass_class(tmp_path: Path):
    sub = _passing_submission(tmp_path)
    results = grader.grade([sub], [EMPTY_ROOM_FILE], timeout=30.0)
    out = tmp_path / "report.html"
    grader.write_html(results, out)
    text = out.read_text(encoding="utf-8")
    assert "<table>" in text
    assert "passes.py" in text
    assert "empty_room" in text
    assert "td class='pass'" in text
    assert "1 / 1 pass" in text


# ---------------------------------------------------------------------------
# end-to-end: the grade CLI subcommand
# ---------------------------------------------------------------------------


def test_grade_cli_writes_csv(tmp_path: Path):
    subs_dir = tmp_path / "subs"
    subs_dir.mkdir()
    _passing_submission(subs_dir)
    _crashing_submission(subs_dir)

    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "empty_room.json").write_text(
        EMPTY_ROOM_FILE.read_text(encoding="utf-8"), encoding="utf-8"
    )

    out = tmp_path / "results.csv"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vex_sim",
            "grade",
            "--submissions",
            str(subs_dir),
            "--scenarios",
            str(scenarios_dir),
            "--output",
            str(out),
            "--timeout",
            "30",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    rows = list(csv.DictReader(out.open(encoding="utf-8", newline="")))
    assert len(rows) == 2
    by_name = {r["submission"]: r for r in rows}
    assert by_name["passes.py"]["passed"] == "true"
    assert by_name["crashes.py"]["passed"] == "false"
    assert by_name["crashes.py"]["error_type"] == "RuntimeError"
    # Progress + summary appear on stderr; stdout stays empty so the CLI
    # is well-behaved when chained into other tooling.
    assert "PASS" in proc.stderr
    assert proc.stdout == ""


def test_grade_cli_emits_json_when_output_has_json_extension(tmp_path: Path):
    subs_dir = tmp_path / "subs"
    subs_dir.mkdir()
    _passing_submission(subs_dir)

    out = tmp_path / "results.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vex_sim",
            "grade",
            "--submissions",
            str(subs_dir),
            "--scenarios",
            str(EMPTY_ROOM_FILE),
            "--output",
            str(out),
            "--timeout",
            "30",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0]["submission"] == "passes.py"
    assert data[0]["passed"] is True


def test_grade_cli_html_flag_writes_report(tmp_path: Path):
    subs_dir = tmp_path / "subs"
    subs_dir.mkdir()
    _passing_submission(subs_dir)

    out = tmp_path / "results.csv"
    html_path = tmp_path / "results.html"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vex_sim",
            "grade",
            "--submissions",
            str(subs_dir),
            "--scenarios",
            str(EMPTY_ROOM_FILE),
            "--output",
            str(out),
            "--html",
            str(html_path),
            "--timeout",
            "30",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    text = html_path.read_text(encoding="utf-8")
    assert "<table>" in text
    assert "passes.py" in text


def test_grade_cli_errors_when_no_submissions_found(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    out = tmp_path / "results.csv"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vex_sim",
            "grade",
            "--submissions",
            str(empty),
            "--scenarios",
            str(EMPTY_ROOM_FILE),
            "--output",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "no submissions" in proc.stderr
