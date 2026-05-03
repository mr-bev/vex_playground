from __future__ import annotations

import vex_sim
from vex_sim.__main__ import build_parser, main


def test_package_has_version() -> None:
    assert vex_sim.__version__ == "0.1.0"


def test_cli_help_runs() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "vex_sim" in help_text
    assert "Headless simulator" in help_text


def test_cli_main_returns_zero() -> None:
    assert main([]) == 0
