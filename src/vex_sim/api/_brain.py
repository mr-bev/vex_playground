from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vex_sim.api._calllog import CALL_LOG
from vex_sim.api._clock import SIM_CLOCK
from vex_sim.api._enums import TimeUnits, VoltageUnits
from vex_sim.scheduler import SCHEDULER as _SCHEDULER


def _callback_name(cb: Callable) -> str:
    return getattr(cb, "__name__", repr(cb))


class _Recorder:
    _label: str = ""

    def _record(
        self, method: str, args: tuple[Any, ...] = (), kwargs: dict[str, Any] | None = None
    ) -> None:
        CALL_LOG.record(self._label, method, args, kwargs)


def _to_seconds(time: float, units: str) -> float:
    if units == TimeUnits.MSEC:
        return float(time) / 1000.0
    return float(time)


class _Battery(_Recorder):
    _label = "brain.battery"

    def voltage(self, units: str = VoltageUnits.MV) -> float:
        self._record("voltage", (units,))
        if units == VoltageUnits.VOLT:
            return 12.0
        return 12000.0

    def current(self) -> float:
        self._record("current")
        return 0.0

    def capacity(self) -> int:
        self._record("capacity")
        return 100


class _Button(_Recorder):
    _label = "brain.button"

    def pressing(self) -> int:
        self._record("pressing")
        return 0

    def pressed(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("pressed", (), {"callback": _callback_name(callback), "arg": arg})

    def released(self, callback: Callable, arg: tuple | None = None) -> None:
        self._record("released", (), {"callback": _callback_name(callback), "arg": arg})


class _Screen(_Recorder):
    _label = "brain.screen"

    def __init__(self) -> None:
        self._row = 1
        self._column = 1

    @staticmethod
    def _format_args(args: tuple[Any, ...], sep: str, precision: int) -> str:
        parts: list[str] = []
        for a in args:
            if isinstance(a, float):
                parts.append(f"{a:.{precision}f}")
            else:
                parts.append(str(a))
        return sep.join(parts)

    def print(self, *args: Any, sep: str = "", precision: int = 2) -> None:
        text = self._format_args(args, sep, precision)
        self._record("print", (text,), {"sep": sep, "precision": precision})

    def print_at(
        self,
        text: Any,
        x: int = 1,
        y: int = 1,
        sep: str = " ",
        precision: int = 2,
        opaque: bool = True,
    ) -> None:
        rendered = self._format_args((text,), sep, precision)
        self._record(
            "print_at",
            (rendered, x, y),
            {"sep": sep, "precision": precision, "opaque": opaque},
        )

    def next_row(self) -> None:
        self._record("next_row")
        self._row += 1
        self._column = 1

    def clear_screen(self, color: Any = None) -> None:
        self._record("clear_screen", (color,) if color is not None else ())
        self._row = 1
        self._column = 1

    def clear_row(self, row: int | None = None, color: Any = None) -> None:
        kwargs: dict[str, Any] = {}
        if row is not None:
            kwargs["row"] = row
        if color is not None:
            kwargs["color"] = color
        self._record("clear_row", (), kwargs)

    def row(self) -> int:
        self._record("row")
        return self._row

    def column(self) -> int:
        self._record("column")
        return self._column

    def get_string_width(self, string: str) -> int:
        self._record("get_string_width", (string,))
        return 6 * len(string)

    def get_string_height(self, string: str) -> int:
        self._record("get_string_height", (string,))
        return 16

    def set_cursor(self, row: int, column: int) -> None:
        self._record("set_cursor", (row, column))
        self._row = row
        self._column = column

    def set_font(self, fontname: str) -> None:
        self._record("set_font", (fontname,))

    def set_pen_width(self, width: int) -> None:
        self._record("set_pen_width", (width,))

    def set_pen_color(self, color: Any) -> None:
        self._record("set_pen_color", (color,))

    def set_fill_color(self, color: Any) -> None:
        self._record("set_fill_color", (color,))

    def draw_pixel(self, x: int, y: int) -> None:
        self._record("draw_pixel", (x, y))

    def draw_line(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self._record("draw_line", (x1, y1, x2, y2))

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: Any = None) -> None:
        args: tuple[Any, ...] = (x, y, width, height)
        if color is not None:
            args = (*args, color)
        self._record("draw_rectangle", args)

    def draw_circle(self, x: int, y: int, radius: int, color: Any = None) -> None:
        args: tuple[Any, ...] = (x, y, radius)
        if color is not None:
            args = (*args, color)
        self._record("draw_circle", args)

    def draw_image_from_file(self, filename: str, x: int, y: int) -> None:
        self._record("draw_image_from_file", (filename, x, y))

    def render(self) -> None:
        self._record("render")

    def set_origin(self, x: int, y: int) -> None:
        self._record("set_origin", (x, y))

    def set_clip_region(self, x: int, y: int, width: int, height: int) -> None:
        self._record("set_clip_region", (x, y, width, height))


class Timer(_Recorder):
    """Standalone timer that begins counting at construction."""

    def __init__(self) -> None:
        self._label = f"timer_{id(self):x}"
        self._offset = SIM_CLOCK.now()
        self._record("Timer")

    def time(self, units: str = TimeUnits.MSEC) -> int | float:
        self._record("time", (units,))
        elapsed = SIM_CLOCK.now() - self._offset
        if units == TimeUnits.MSEC:
            return int(elapsed * 1000)
        return float(elapsed)

    def clear(self) -> None:
        self._record("clear")
        self._offset = SIM_CLOCK.now()

    def event(self, callback: Callable, delay: int, arg: tuple | None = None) -> None:
        self._record("event", (delay,), {"callback": _callback_name(callback), "arg": arg})


class _BrainTimer(Timer):
    """Brain.timer — Timer plus system()/system_high_res() that read absolute sim time."""

    def __init__(self) -> None:
        self._label = "brain.timer"
        self._offset = SIM_CLOCK.now()

    def system(self) -> int:
        self._record("system")
        return SIM_CLOCK.now_ms()

    def system_high_res(self) -> int:
        self._record("system_high_res")
        return int(SIM_CLOCK.now() * 1_000_000)


class _TriPin:
    """A single 3-wire pin (a–h) on a port set. Passed to 3-wire device constructors."""

    def __init__(self, label: str, letter: str) -> None:
        self._label = label
        self._letter = letter


class _TriPort:
    """The 8-pin 3-wire port set. Built into the brain or returned via Triport(port)."""

    def __init__(self, base_label: str) -> None:
        for letter in "abcdefgh":
            setattr(self, letter, _TriPin(f"{base_label}.{letter}", letter))


class Triport(_Recorder):
    """3-Wire Expander connected to a smart port."""

    def __init__(self, port: int) -> None:
        self._port = port
        self._label = f"triport_port{port}"
        self._record("Triport", (port,))
        for letter in "abcdefgh":
            setattr(self, letter, _TriPin(f"{self._label}.{letter}", letter))

    def index(self) -> int:
        self._record("index")
        return self._port


class _SDCard(_Recorder):
    _label = "brain.sdcard"

    def is_inserted(self) -> bool:
        self._record("is_inserted")
        return False


class Brain(_Recorder):
    _label = "brain"

    def __init__(self) -> None:
        self.battery = _Battery()
        self.button = _Button()
        self.screen = _Screen()
        self.timer = _BrainTimer()
        self.three_wire_port = _TriPort("brain.three_wire_port")
        self.sdcard = _SDCard()
        self._record("Brain")

    def program_stop(self) -> None:
        self._record("program_stop")


def wait(time: float, units: str = TimeUnits.SEC) -> None:
    CALL_LOG.record("", "wait", (time, units))
    _SCHEDULER.yield_for(SIM_CLOCK.now() + _to_seconds(time, units))


def sleep(time: float, units: str = TimeUnits.SEC) -> None:
    CALL_LOG.record("", "sleep", (time, units))
    _SCHEDULER.yield_for(SIM_CLOCK.now() + _to_seconds(time, units))
