"""Tests for the render-mode HUD pieces.

Pure helpers (brain screen mirror, sensor cache state pickup) are
exercised without invoking the pygame loop. The full loop is covered
by the existing render integration test under SDL's dummy driver.
"""

from __future__ import annotations

import pytest

from vex_sim.api import Brain
from vex_sim.api._brain import (
    latest_brain_screen,
    reset_latest_brain_screen,
)
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    reset_latest_brain_screen()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    reset_latest_brain_screen()


def test_latest_brain_screen_none_before_brain_constructed():
    assert latest_brain_screen() is None


def test_latest_brain_screen_returns_screen_after_brain_construction():
    brain = Brain()
    screen = latest_brain_screen()
    assert screen is brain.screen


def test_text_lines_empty_initially():
    Brain()
    assert latest_brain_screen().text_lines() == []


def test_print_appears_in_text_lines():
    brain = Brain()
    brain.screen.print("hello")
    assert latest_brain_screen().text_lines() == ["hello"]


def test_print_two_rows_with_next_row():
    brain = Brain()
    brain.screen.print("first")
    brain.screen.next_row()
    brain.screen.print("second")
    assert latest_brain_screen().text_lines() == ["first", "second"]


def test_clear_screen_drops_text():
    brain = Brain()
    brain.screen.print("hello")
    brain.screen.clear_screen()
    assert latest_brain_screen().text_lines() == []


def test_clear_row_drops_only_that_row():
    brain = Brain()
    brain.screen.print("first")
    brain.screen.next_row()
    brain.screen.print("second")
    brain.screen.clear_row(1)
    # Row 1 cleared; row 2 remains.
    assert latest_brain_screen().text_lines() == ["second"]


def test_set_cursor_then_print_writes_at_that_row():
    brain = Brain()
    brain.screen.set_cursor(3, 1)
    brain.screen.print("third row")
    # Rows 1 and 2 are empty (not in dict), row 3 carries the text.
    assert latest_brain_screen().text_lines() == ["third row"]


def test_text_lines_clipped_to_max_rows():
    brain = Brain()
    for i in range(20):
        brain.screen.set_cursor(i + 1, 1)
        brain.screen.print(f"row{i}")
    lines = latest_brain_screen().text_lines()
    # 12-row cap means we get rows 1..12, not 1..20.
    assert len(lines) == 12


def test_reset_clears_registry():
    Brain()
    assert latest_brain_screen() is not None
    reset_latest_brain_screen()
    assert latest_brain_screen() is None


# -----------------------------------------------------------------------------
# Render hud helpers (sensor cache + brain screen pickup); skipped when
# pygame is unavailable since _draw_hud lives in the render module.
# -----------------------------------------------------------------------------


pygame = pytest.importorskip("pygame")


def test_brain_screen_lines_helper_proxies_latest_screen():
    from vex_sim.render import _brain_screen_lines  # noqa: PLC0415

    assert _brain_screen_lines() == []
    brain = Brain()
    brain.screen.print("hud check")
    assert _brain_screen_lines() == ["hud check"]
