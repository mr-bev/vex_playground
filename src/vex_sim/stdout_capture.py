"""Live stdout capture for student programs.

The runner needs two things from the student's stdout: capture it for the
JSON result, AND show it to the user as it happens. ``redirect_stdout``
gives us only the first; a tee gives us both.

``tee_stdout`` swaps :data:`sys.stdout` for a stream that writes to both
the real stdout (so the user sees prints live) and a capture buffer (so
the runner can return the full text in its result). It auto-flushes
after every write so output isn't held back by line buffering.
"""

from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Iterator
from typing import IO


class _TeeStream(io.TextIOBase):
    """Write-through stream that mirrors writes to two destinations.

    The first destination (``live``) is the user-visible terminal; the
    second (``capture``) is the in-memory buffer the runner returns. Both
    receive every write; we flush ``live`` after each write so prints
    appear without waiting for newlines or program exit.
    """

    def __init__(self, live: IO[str], capture: io.StringIO) -> None:
        self._live = live
        self._capture = capture

    def write(self, s: str) -> int:  # type: ignore[override]
        self._capture.write(s)
        n = self._live.write(s)
        # Flush eagerly so live output keeps pace with simulated time.
        self._live.flush()
        return n

    def flush(self) -> None:  # type: ignore[override]
        self._live.flush()

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return getattr(self._live, "isatty", lambda: False)()


@contextlib.contextmanager
def tee_stdout(capture: io.StringIO) -> Iterator[None]:
    """Replace :data:`sys.stdout` with a tee that mirrors to ``capture``.

    Used by both the headless runner and the live render loop so a
    student's ``print`` calls (and ``brain.screen.print`` mirrors)
    appear in the terminal as they execute, while still being available
    in the JSON result via ``capture``.
    """
    live = sys.stdout
    tee = _TeeStream(live, capture)
    sys.stdout = tee
    try:
        yield
    finally:
        sys.stdout = live
