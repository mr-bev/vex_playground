from __future__ import annotations

from collections.abc import Callable

from vex_sim.api._brain import _callback_name, _Recorder


class _ControllerButton(_Recorder):
    def __init__(self, name: str) -> None:
        self._label = f"controller.{name}"

    def pressing(self) -> int:
        self._record("pressing")
        return 0

    def pressed(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("pressed", (), {"callback": _callback_name(callback), "arg": arg})

    def released(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("released", (), {"callback": _callback_name(callback), "arg": arg})


class _ControllerAxis(_Recorder):
    def __init__(self, name: str) -> None:
        self._label = f"controller.{name}"

    def position(self) -> int:
        self._record("position")
        return 0

    def changed(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("changed", (), {"callback": _callback_name(callback), "arg": arg})


class Controller(_Recorder):
    _label = "controller"

    def __init__(self) -> None:
        for name in (
            "buttonA",
            "buttonB",
            "buttonUp",
            "buttonDown",
            "buttonL1",
            "buttonL2",
            "buttonL3",
            "buttonR1",
            "buttonR2",
            "buttonR3",
        ):
            setattr(self, name, _ControllerButton(name))
        for name in ("axis1", "axis2", "axis3", "axis4"):
            setattr(self, name, _ControllerAxis(name))
        self.remote_control_code_enabled = True
        self._record("Controller")
