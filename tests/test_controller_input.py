"""Tests for controller input buffer + keyboard mapping."""

from __future__ import annotations

import pytest

from vex_sim.api import Controller
from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.controller_input import (
    CONTROLLER_INPUT,
    keyboard_to_axes_buttons,
)


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    CONTROLLER_INPUT.reset()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    CONTROLLER_INPUT.reset()


# -----------------------------------------------------------------------------
# Buffer state
# -----------------------------------------------------------------------------


def test_buffer_starts_zeroed():
    assert CONTROLLER_INPUT.axis_position("axis1") == 0
    assert CONTROLLER_INPUT.button_pressing("buttonA") is False


def test_axis_set_propagates_to_controller_api():
    CONTROLLER_INPUT.axes["axis2"] = 75
    c = Controller()
    assert c.axis2.position() == 75


def test_button_set_propagates_to_controller_api():
    CONTROLLER_INPUT.buttons["buttonA"] = True
    c = Controller()
    assert c.buttonA.pressing() == 1
    CONTROLLER_INPUT.buttons["buttonA"] = False
    assert c.buttonA.pressing() == 0


def test_reset_zeroes_everything():
    CONTROLLER_INPUT.axes["axis1"] = 100
    CONTROLLER_INPUT.buttons["buttonA"] = True
    CONTROLLER_INPUT.reset()
    assert CONTROLLER_INPUT.axes["axis1"] == 0
    assert CONTROLLER_INPUT.buttons["buttonA"] is False


def test_unknown_axis_returns_zero():
    assert CONTROLLER_INPUT.axis_position("nonexistent_axis") == 0


def test_unknown_button_returns_false():
    assert CONTROLLER_INPUT.button_pressing("nonexistent_button") is False


# -----------------------------------------------------------------------------
# Keyboard translation (uses a fake pygame stand-in so the test stays
# headless-friendly — no real pygame init, no display required).
# -----------------------------------------------------------------------------


class _FakePygameKey:
    """Stand-in for pygame.key whose get_pressed returns a held-key set."""

    K_w = "w"
    K_a = "a"
    K_s = "s"
    K_d = "d"
    K_q = "q"
    K_e = "e"
    K_z = "z"
    K_x = "x"
    K_j = "j"
    K_k = "k"
    K_u = "u"
    K_o = "o"
    K_i = "i"
    K_COMMA = ","
    K_UP = "UP"
    K_DOWN = "DOWN"
    K_LEFT = "LEFT"
    K_RIGHT = "RIGHT"

    class _Pressed:
        def __init__(self, held: set):
            self._held = held

        def __getitem__(self, key):
            return key in self._held

    def __init__(self, held: set):
        self._held = held

    @property
    def key(self):
        return self

    def get_pressed(self):
        return self._Pressed(self._held)


def _fake_pygame(*held: str):
    return _FakePygameKey(set(held))


def test_keyboard_w_drives_axis2_positive():
    axes, _ = keyboard_to_axes_buttons(_fake_pygame("w"))
    assert axes["axis2"] == 100


def test_keyboard_s_drives_axis2_negative():
    axes, _ = keyboard_to_axes_buttons(_fake_pygame("s"))
    assert axes["axis2"] == -100


def test_keyboard_a_d_combined_cancels():
    axes, _ = keyboard_to_axes_buttons(_fake_pygame("a", "d"))
    assert axes["axis1"] == 0


def test_keyboard_arrows_drive_left_stick():
    axes, _ = keyboard_to_axes_buttons(_fake_pygame("UP", "RIGHT"))
    assert axes["axis3"] == 100  # left-stick Y
    assert axes["axis4"] == 100  # left-stick X


def test_keyboard_button_keys():
    _, buttons = keyboard_to_axes_buttons(_fake_pygame("j", "u"))
    assert buttons["buttonA"] is True
    assert buttons["buttonR1"] is True
    assert buttons["buttonB"] is False


def test_no_keys_pressed_yields_neutral_state():
    axes, buttons = keyboard_to_axes_buttons(_fake_pygame())
    assert all(v == 0 for v in axes.values())
    assert all(v is False for v in buttons.values())


# -----------------------------------------------------------------------------
# Headless determinism: the runner does not populate the buffer, so a
# Controller-driven student program reads zeros throughout.
# -----------------------------------------------------------------------------


def test_runner_leaves_controller_buffer_zeroed(tmp_path):
    from vex_sim import runner  # noqa: PLC0415

    p = tmp_path / "student.py"
    p.write_text(
        "from vex import *\n"
        "c = Controller()\n"
        "axis = c.axis2.position()\n"
        "btn = c.buttonA.pressing()\n"
        "print(f'axis={axis} btn={btn}')\n",
        encoding="utf-8",
    )
    result = runner.run(p)
    assert result["status"] == "completed"
    assert "axis=0 btn=0" in result["stdout"]
