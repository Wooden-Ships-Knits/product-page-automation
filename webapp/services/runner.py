"""
Runs main.production(data) and streams its console output — WITHOUT modifying
the core. production() already print()s per style; we capture that stdout/stderr
into a queue a Streamlit page can drain live.

Also does a best-effort IM-file pre-sync (drive_sync) so the workbook is present
on a headless VM before get_weight() reads it. No-op on the Mac (Drive mounted).
"""
import io
import os
import queue
import re
import sys
import threading
import traceback

# Shopify admin product links printed by production(), for the results panel.
_LINK_RE = re.compile(r"https://admin\.shopify\.com/store/wooden-ships/products/\d+")


def extract_links(log_text: str):
    """Unique Shopify admin product links found in the captured log, in order."""
    seen, out = set(), []
    for m in _LINK_RE.findall(log_text or ""):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _presync_im(season: str, log) -> None:
    """On a VM (IM_COLLECTION_BASE set), download the season's IM workbook to the
    cache path get_im_path() will build. On the Mac (env unset) this is skipped —
    the Drive mount already provides the file."""
    base = os.getenv("IM_COLLECTION_BASE")
    if not base:
        return
    try:
        import drive_sync
        year, name = season.split()[0], season.split()[1].title()
        code = f"{name[0].upper()}{year}"                 # "26 Fall" -> "F26"
        path = f"{base}/{year} {name}/IM/{code} IM MASTER.xlsx"
        log(f"[presync] ensuring {code} IM MASTER.xlsx …\n")
        drive_sync.ensure_local(path)
    except Exception as e:
        log(f"[presync] skipped: {e}\n")


class _QueueWriter(io.TextIOBase):
    def __init__(self, q: "queue.Queue[str]"):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(s)
        return len(s)

    def flush(self):
        pass


class BuildRun:
    """Runs production(data) for a season in a background thread with live output."""

    def __init__(self, data, season: str):
        self.data = data
        self.season = season
        self.q: "queue.Queue[str]" = queue.Queue()
        self.thread = None
        self.error = None

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        writer = _QueueWriter(self.q)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = writer
        try:
            _presync_im(self.season, self.q.put)
            import main
            main.SEASON = self.season          # drive the season without touching the file
            main.production(self.data)
        except Exception:
            self.error = traceback.format_exc()
            self.q.put("\n[ERROR]\n" + self.error)
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def drain(self) -> str:
        chunks = []
        try:
            while True:
                chunks.append(self.q.get_nowait())
        except queue.Empty:
            pass
        return "".join(chunks)

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()
