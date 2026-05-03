from __future__ import annotations

import json

import pytest

from vex_sim.api._calllog import CALL_LOG, CallLog
from vex_sim.api._clock import SIM_CLOCK


@pytest.fixture(autouse=True)
def _isolated_state():
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()
    yield
    SIM_CLOCK.reset()
    SIM_CLOCK.set_max_time(None)
    CALL_LOG.clear()


def test_record_appends_entry():
    CALL_LOG.record("motor_port1", "spin", args=("forward",), kwargs={"velocity": 50})
    entries = CALL_LOG.entries()
    assert len(entries) == 1
    e = entries[0]
    assert e["obj"] == "motor_port1"
    assert e["method"] == "spin"
    assert e["args"] == ["forward"]
    assert e["kwargs"] == {"velocity": 50}


def test_record_captures_clock_time():
    SIM_CLOCK.advance(0.25)
    CALL_LOG.record("brain", "screen.print", args=("hi",))
    assert CALL_LOG.entries()[0]["t"] == pytest.approx(0.25)


def test_clear_empties_log():
    CALL_LOG.record("brain", "Brain")
    CALL_LOG.record("brain", "screen.print", args=("a",))
    assert len(CALL_LOG) == 2
    CALL_LOG.clear()
    assert len(CALL_LOG) == 0
    assert CALL_LOG.entries() == []


def test_to_json_roundtrip():
    CALL_LOG.record("motor_port6", "spin_for", args=("forward", 90, "deg"), kwargs={"wait": True})
    out = CALL_LOG.to_json()
    parsed = json.loads(out)
    assert parsed == [
        {
            "t": 0.0,
            "obj": "motor_port6",
            "method": "spin_for",
            "args": ["forward", 90, "deg"],
            "kwargs": {"wait": True},
        }
    ]


def test_unserializable_args_fall_back_to_repr():
    class Opaque:
        def __repr__(self) -> str:
            return "<Opaque>"

    CALL_LOG.record("brain", "weird", args=(Opaque(),))
    assert CALL_LOG.entries()[0]["args"] == ["<Opaque>"]


def test_independent_log_instance():
    cl = CallLog()
    cl.record("x", "y")
    assert len(cl) == 1
    assert len(CALL_LOG) == 0
