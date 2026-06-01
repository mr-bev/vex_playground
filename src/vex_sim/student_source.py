"""Load and execute a student program from a ``.py`` or ``.exppython`` file.

Students author their robot code in VEXcode EXP, which saves the project
as a single ``*.exppython`` file. Rather than have them copy-paste the
code out into a plain ``.py`` file (error-prone, and easy to forget the
generated configuration block), the simulator reads the ``.exppython``
file directly.

An ``.exppython`` file is JSON. The runnable program lives in its
``textContent`` field: the VEXcode-generated robot-configuration region
followed by the student's own code, concatenated exactly as it is flashed
to the brain. ``tests/empty.exppython`` is a minimal example.

A plain ``.py`` file is run unchanged via :func:`runpy.run_path`; only the
``.exppython`` case needs unwrapping.
"""

from __future__ import annotations

import json
import linecache
import runpy
from pathlib import Path

#: Extension of a VEXcode EXP project file.
EXP_PYTHON_SUFFIX = ".exppython"


def is_exppython(path: str | Path) -> bool:
    """True if ``path`` looks like a VEXcode EXP project file."""
    return Path(path).suffix == EXP_PYTHON_SUFFIX


def extract_exppython_source(path: str | Path) -> str:
    """Return the runnable Python program embedded in an ``.exppython`` file.

    Raises :class:`ValueError` with a student-friendly message if the
    file is not JSON or does not carry a ``textContent`` string -- i.e.
    if someone points the simulator at the wrong file.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"{path}: not valid JSON. A .exppython file is the JSON project "
            f"VEXcode EXP saves; this file could not be parsed ({e})."
        ) from e

    if not isinstance(data, dict) or "textContent" not in data:
        raise ValueError(
            f"{path}: no 'textContent' field. Is this really a VEXcode EXP "
            f"project (.exppython) file?"
        )

    source = data["textContent"]
    if not isinstance(source, str):
        raise ValueError(f"{path}: 'textContent' is not text; the project file looks corrupt.")
    return source


def run_student_program(student_path: str | Path, run_name: str = "__main__") -> None:
    """Execute a student program from a ``.py`` or ``.exppython`` file.

    Plain ``.py`` files go through :func:`runpy.run_path` unchanged. For
    ``.exppython`` files the embedded program is compiled and executed in
    a fresh ``__main__`` namespace; the source is registered with
    :mod:`linecache` so a traceback points at the student's actual lines
    (with line numbers relative to the full embedded program -- config
    region first, then their code -- exactly as it runs on the brain).
    """
    path = Path(student_path)
    if not is_exppython(path):
        runpy.run_path(str(path), run_name=run_name)
        return

    source = extract_exppython_source(path)
    filename = str(path)
    # Make the extracted source visible to traceback / linecache so error
    # frames show "File '.../student.exppython', line N" with real lines.
    linecache.cache[filename] = (
        len(source),
        None,
        source.splitlines(keepends=True),
        filename,
    )
    code = compile(source, filename, "exec")
    exec(code, {"__name__": run_name, "__file__": filename})  # noqa: S102
