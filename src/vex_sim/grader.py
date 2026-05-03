"""Batch grader: run many submissions against many scenarios, collect results.

Each (submission, scenario) pair is run as a subprocess invocation of the
existing ``python -m vex_sim run`` CLI. The CLI already emits a JSON
scenario result to stdout when the playground declares success criteria;
the grader parses that, plus wraps the call in a wall-clock timeout so a
student's runaway loop can't hang the batch.

Threat model
------------

The subprocess boundary is for **crash isolation**, not security. A
student program that raises, segfaults, or hits an infinite loop will be
killed without taking down the grader. It will not stop a malicious
student from reading the marker's files, opening network connections,
or shelling out -- the subprocess inherits the marker's user
permissions. Run untrusted submissions in a real sandbox (container,
VM, restricted user) if that is a concern.
"""

from __future__ import annotations

import csv
import html
import json
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GradeResult:
    submission: str
    scenario: str
    passed: bool
    status: str
    reason: str
    time_taken: float = 0.0
    distance_travelled_mm: float = 0.0
    collisions: int = 0
    sensor_reads: int = 0
    visited_zones: list[str] = field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None
    runtime_wall_seconds: float = 0.0

    def to_csv_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["visited_zones"] = ",".join(self.visited_zones)
        d["passed"] = "true" if self.passed else "false"
        return d


CSV_FIELDS: tuple[str, ...] = (
    "submission",
    "scenario",
    "passed",
    "status",
    "reason",
    "time_taken",
    "distance_travelled_mm",
    "collisions",
    "sensor_reads",
    "visited_zones",
    "error_type",
    "error_message",
    "runtime_wall_seconds",
)


def discover_submissions(path: Path) -> list[Path]:
    """Return ``*.py`` files in ``path`` (or ``[path]`` if it's a file).

    Files starting with ``_`` are skipped so ``__init__.py`` and the
    like don't show up as submissions by accident.
    """
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"submissions path does not exist: {path}")
    return sorted(p for p in path.glob("*.py") if not p.name.startswith("_"))


def discover_scenarios(path: Path) -> list[Path]:
    """Return ``*.json`` files in ``path`` (or ``[path]`` if it's a file).

    The bundled ``playground.schema.json`` is excluded so the grader can
    be pointed straight at ``src/vex_sim/playground_files`` without a
    spurious "scenario".
    """
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"scenarios path does not exist: {path}")
    return sorted(p for p in path.glob("*.json") if p.name != "playground.schema.json")


def run_one(
    submission: Path,
    scenario: Path,
    *,
    timeout: float,
    max_time: float | None = None,
) -> GradeResult:
    """Run one (submission, scenario) pair as a child Python process.

    ``timeout`` is the wall-clock seconds before the child is killed.
    A wall timeout produces ``status="wall_timeout"``; a non-JSON or
    crashed child produces ``status="subprocess_crash"``. Otherwise the
    status comes straight from the simulator's scenario result.
    """
    cmd = [
        sys.executable,
        "-m",
        "vex_sim",
        "run",
        str(submission),
        "--playground",
        str(scenario),
        "--out",
        "-",
    ]
    if max_time is not None:
        cmd += ["--max-time", str(max_time)]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return GradeResult(
            submission=submission.name,
            scenario=scenario.stem,
            passed=False,
            status="wall_timeout",
            reason=f"subprocess exceeded wall-clock timeout of {timeout:.1f}s",
            runtime_wall_seconds=time.monotonic() - start,
        )

    elapsed = time.monotonic() - start

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
        return GradeResult(
            submission=submission.name,
            scenario=scenario.stem,
            passed=False,
            status="subprocess_crash",
            reason=f"unparseable child output (exit={proc.returncode}); last stderr: {tail[0]}",
            runtime_wall_seconds=elapsed,
        )

    err = (payload.get("raw") or {}).get("error") or None
    return GradeResult(
        submission=submission.name,
        scenario=str(payload.get("playground", scenario.stem)),
        passed=bool(payload.get("passed", False)),
        status=str(payload.get("status", "unknown")),
        reason=str(payload.get("reason", "")),
        time_taken=float(payload.get("time_taken", 0.0)),
        distance_travelled_mm=float(payload.get("distance_travelled_mm", 0.0)),
        collisions=int(payload.get("collisions", 0)),
        sensor_reads=int(payload.get("sensor_reads", 0)),
        visited_zones=list(payload.get("visited_zones", []) or []),
        error_type=(err or {}).get("type") if err else None,
        error_message=(err or {}).get("message") if err else None,
        runtime_wall_seconds=elapsed,
    )


def grade(
    submissions: list[Path],
    scenarios: list[Path],
    *,
    timeout: float,
    max_time: float | None = None,
    workers: int = 1,
    progress: Callable[[GradeResult], None] | None = None,
) -> list[GradeResult]:
    """Run every (submission, scenario) pair and return sorted results.

    ``workers`` parallelises by spawning multiple child processes
    concurrently via threads + ``subprocess.run``. The simulator itself
    is single-process per pair; the threads just block on the OS.
    """
    pairs = [(s, sc) for s in submissions for sc in scenarios]
    results: list[GradeResult] = []

    if workers <= 1:
        for sub, sc in pairs:
            r = run_one(sub, sc, timeout=timeout, max_time=max_time)
            results.append(r)
            if progress is not None:
                progress(r)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [
                ex.submit(run_one, sub, sc, timeout=timeout, max_time=max_time) for sub, sc in pairs
            ]
            for f in as_completed(futures):
                r = f.result()
                results.append(r)
                if progress is not None:
                    progress(r)

    results.sort(key=lambda r: (r.submission, r.scenario))
    return results


def write_csv(results: list[GradeResult], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in results:
            w.writerow(r.to_csv_row())


def write_json(results: list[GradeResult], path: Path) -> None:
    path.write_text(
        json.dumps([asdict(r) for r in results], indent=2),
        encoding="utf-8",
    )


def write_html(results: list[GradeResult], path: Path) -> None:
    """Render a self-contained matrix: rows = submissions, cols = scenarios.

    Cell colour: green=pass, red=fail, grey=crash/timeout. Hovering a
    cell surfaces the failure reason and key metrics so a marker can
    skim the matrix and drill into the failures without opening the
    raw CSV.
    """
    submissions = sorted({r.submission for r in results})
    scenarios = sorted({r.scenario for r in results})
    by_pair: dict[tuple[str, str], GradeResult] = {(r.submission, r.scenario): r for r in results}

    pass_count = sum(1 for r in results if r.passed)
    total = len(results)

    rows_html: list[str] = []
    for sub in submissions:
        cells = [f"<th class='row'>{html.escape(sub)}</th>"]
        for sc in scenarios:
            r = by_pair.get((sub, sc))
            if r is None:
                cells.append("<td class='missing'></td>")
                continue
            cls = (
                "pass"
                if r.passed
                else (
                    "crash" if r.status in {"wall_timeout", "subprocess_crash", "error"} else "fail"
                )
            )
            label = "PASS" if r.passed else r.status.upper()
            tip = (
                f"{r.reason}\n"
                f"time {r.time_taken:.2f}s  dist {r.distance_travelled_mm:.0f}mm  "
                f"collisions {r.collisions}  sensor_reads {r.sensor_reads}  "
                f"wall {r.runtime_wall_seconds:.2f}s"
            )
            cells.append(f"<td class='{cls}' title='{html.escape(tip)}'>{html.escape(label)}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    header_cells = "".join(f"<th>{html.escape(s)}</th>" for s in scenarios)
    body = (
        "<table>"
        f"<thead><tr><th></th>{header_cells}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )

    style = (
        "body{font-family:system-ui,sans-serif;margin:2em;color:#222}"
        "h1{margin-bottom:0.2em}p.summary{color:#555;margin-top:0}"
        "table{border-collapse:collapse;font-size:14px}"
        "th,td{border:1px solid #ccc;padding:6px 10px;text-align:center}"
        "th.row{text-align:left;font-weight:normal;background:#f6f6f6}"
        "td.pass{background:#d4edda;color:#155724}"
        "td.fail{background:#f8d7da;color:#721c24}"
        "td.crash{background:#e2e3e5;color:#383d41}"
        "td.missing{background:#fff}"
    )

    out = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>vex_sim grade report</title>"
        f"<style>{style}</style></head><body>"
        "<h1>vex_sim grade report</h1>"
        f"<p class='summary'>{pass_count} / {total} pass "
        f"&middot; {len(submissions)} submissions &times; {len(scenarios)} scenarios</p>"
        f"{body}"
        "</body></html>"
    )
    path.write_text(out, encoding="utf-8")
