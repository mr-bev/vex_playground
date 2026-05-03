from __future__ import annotations

import json
from typing import Any

from vex_sim.api._clock import SIM_CLOCK


def _serialize(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    return repr(value)


class CallLog:
    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def record(
        self,
        obj_label: str,
        method: str,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._entries.append(
            {
                "t": SIM_CLOCK.now(),
                "obj": obj_label,
                "method": method,
                "args": [_serialize(a) for a in args],
                "kwargs": {k: _serialize(v) for k, v in (kwargs or {}).items()},
            }
        )

    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self._entries, indent=indent)


CALL_LOG = CallLog()
