"""Locating a mounted CircuitPython board.

CircuitPython writes ``boot_out.txt`` to the root of the drive it exposes.
Looking for that file is more reliable than matching the ``CIRCUITPY`` volume
label, which users rename and which needs OS-specific APIs to read.
"""

from __future__ import annotations

import string
import sys
from pathlib import Path

MARKER = "boot_out.txt"


def _candidate_roots() -> list[Path]:
    if sys.platform == "win32":
        return [Path(f"{letter}:/") for letter in string.ascii_uppercase]
    if sys.platform == "darwin":
        return sorted(Path("/Volumes").glob("*"))
    roots: list[Path] = []
    for base in (Path("/media"), Path("/run/media"), Path("/mnt")):
        if base.is_dir():
            roots.extend(base.glob("*"))
            roots.extend(base.glob("*/*"))
    return sorted(roots)


def find_boards() -> list[Path]:
    """Return every mounted CircuitPython drive, most likely candidate first."""
    found: list[Path] = []
    for root in _candidate_roots():
        try:
            if (root / MARKER).is_file():
                found.append(root)
        except OSError:
            # Unreadable or disconnected drive letters raise here; skip them.
            continue
    # A drive actually named CIRCUITPY is the best guess when several match.
    found.sort(key=lambda p: p.name.upper() != "CIRCUITPY")
    return found


def describe(board: Path) -> str:
    """Read the board identity CircuitPython records in boot_out.txt."""
    try:
        first = (board / MARKER).read_text(errors="replace").splitlines()
        return first[0].strip() if first else "CircuitPython board"
    except OSError:
        return "CircuitPython board"
