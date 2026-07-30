"""Single-run guard.

A build (or a manual fetch) writes to shared Google Sheets + Output/, so only one
may run at a time. This is a simple exclusive-file lock at the project root.
"""
import json
import os
import time
from pathlib import Path

LOCK_PATH = Path(__file__).resolve().parent.parent / ".run.lock"


class RunBusy(Exception):
    """Raised when a run is already in progress."""


def acquire(label: str) -> None:
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RunBusy(current())
    try:
        os.write(fd, json.dumps({"label": label, "started": time.time()}).encode())
    finally:
        os.close(fd)


def release() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def current():
    """Return {'label', 'started'} of the active run, or None."""
    try:
        return json.loads(LOCK_PATH.read_text())
    except Exception:
        return None


def is_locked() -> bool:
    return LOCK_PATH.exists()
