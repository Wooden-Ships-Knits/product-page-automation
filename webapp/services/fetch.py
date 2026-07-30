"""
Fetch-monitor helpers: read the hourly job's log and (optionally) run it now.

The hourly job is cron_fetch.py (fetch_id.fetch + fetch_image.list_shop_files),
run on a timer. Here we only READ its log and can trigger a one-off run — the
schedule itself lives in cron/systemd, not the app.
"""
import os
import subprocess
import sys
from pathlib import Path

# Default: project-root cron_fetch.log (Mac). In Docker set PPA_FETCH_LOG to a
# shared-volume path so the `web` container reads what the `fetch` container writes.
LOG_PATH = Path(os.getenv("PPA_FETCH_LOG", "cron_fetch.log"))


def read_log(max_chars: int = 12000) -> str:
    if not LOG_PATH.exists():
        return "(no cron_fetch.log yet)"
    text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def last_run_hint() -> str:
    """Best-effort last-run marker from the log tail."""
    if not LOG_PATH.exists():
        return "never (no log)"
    for line in reversed(LOG_PATH.read_text(errors="replace").splitlines()):
        if "cron_fetch run" in line or "=====" in line:
            return line.strip("= ").strip() or "see log"
    return "see log"


def run_fetch_streaming():
    """Run cron_fetch.py as a subprocess, yielding output lines live."""
    proc = subprocess.Popen(
        [sys.executable, "cron_fetch.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in proc.stdout:
        yield line
    proc.wait()
    yield f"\n[exit code {proc.returncode}]\n"
