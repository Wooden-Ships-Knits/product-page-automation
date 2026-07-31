"""
Runs return_product.py (the bulk, sheet-driven create/update from the Master Grid
of Return) as a subprocess and streams its output live.

return_product.py runs its flow at module level (no function to import), so a
subprocess is the clean way to trigger it without executing it on import.
"""
import os
import subprocess
import sys


def run_return_streaming(season: str = "26 Fall"):
    """Run return_product.py for `season`, yielding output lines as they arrive.

    The season is passed through the PPA_SEASON env var, which return_product.py
    reads (defaulting to 26 Fall if unset).
    """
    env = {**os.environ, "PPA_SEASON": season}
    proc = subprocess.Popen(
        [sys.executable, "return_product.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    for line in proc.stdout:
        yield line
    proc.wait()
    yield f"\n[exit code {proc.returncode}]\n"
