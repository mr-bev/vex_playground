"""Tests for vex_sim.stdout_capture: live tee of student prints."""

from __future__ import annotations

import io
import sys

from vex_sim.stdout_capture import tee_stdout


def test_tee_writes_to_both_destinations(capsys):
    captured = io.StringIO()
    with tee_stdout(captured):
        print("hello")
    assert "hello" in captured.getvalue()
    out = capsys.readouterr().out
    assert "hello" in out


def test_tee_restores_sys_stdout():
    original = sys.stdout
    captured = io.StringIO()
    with tee_stdout(captured):
        pass
    assert sys.stdout is original


def test_tee_flushes_eagerly(capsys):
    """A write without a trailing newline still reaches the live stream.

    The live render loop relies on this: a student that prints inside a
    long-running loop must show output between waits, not held back by
    line buffering.
    """
    captured = io.StringIO()
    with tee_stdout(captured):
        sys.stdout.write("partial")
        # Read live output mid-context — the write must already be visible.
        intermediate = capsys.readouterr().out
    assert "partial" in intermediate
    assert captured.getvalue() == "partial"


def test_tee_propagates_exceptions():
    captured = io.StringIO()
    try:
        with tee_stdout(captured):
            print("before")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    # Even on exception, the print before the raise was captured.
    assert "before" in captured.getvalue()
