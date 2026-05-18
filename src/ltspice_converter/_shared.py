"""Shared paths and helpers for ltspice_converter.

The training datasets (textbook DB, LTspice bundled examples, third-party
GitHub repos) are intentionally NOT shipped with this package -- only the
trained converter itself and a handful of author-authored test fixtures.
See README.md for the copyright rationale.
"""
from __future__ import annotations

import os
from pathlib import Path

_PACKAGE_DIR = Path(__file__).parent              # src/ltspice_converter/
_PARSER_DIR = _PACKAGE_DIR / "parser"


def _find_ltspice() -> str | None:
    """Auto-detect LTspice executable (Windows). Returns None on non-Windows
    or if LTspice is not installed.
    """
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "ADI" / "LTspice" / "LTspice.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ADI" / "LTspice" / "LTspice.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "LTC" / "LTspiceXVII" / "XVIIx64.exe",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None
