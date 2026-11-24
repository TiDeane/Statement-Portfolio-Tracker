"""Putting a newly written file in place of the old one, on every system."""

from __future__ import annotations

import os
import time
from pathlib import Path

HELD_SECONDS = 1.0
"""How long a file another program holds is waited for before giving up."""


def replace(source: Path, target: Path) -> None:
    """Put ``source`` in place of ``target`` in one step, as ``os.replace`` does.

    On Windows another program can hold a file for a moment, an antivirus checking a file just written
    or a search indexer, and the replacement is refused meanwhile. It is tried again for up to
    ``HELD_SECONDS``; a file held for longer (a spreadsheet open in Excel) raises the PermissionError.
    """
    deadline = time.monotonic() + HELD_SECONDS
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)
