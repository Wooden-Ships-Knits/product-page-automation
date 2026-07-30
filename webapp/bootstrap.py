"""
Path/CWD shim — imported FIRST by every webapp entry (app.py + each page).

Additive: touches no existing file. It only makes the existing PPA code importable
and its relative paths resolve:
  - puts the PPA project root on sys.path  -> `import main`, `drive_sync`,
    `config.varia`, `Setup.setup` all work
  - chdir()s to the project root           -> relative paths used by the core
    (credentials/…json, Output/product_link.txt, cron_fetch.log) resolve no
    matter where `streamlit run` was launched from.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)
