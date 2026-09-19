"""
Near-real-time sync of Shopify Files -> the `Links storage` tab.

Shopify has no webhook for Files (Content -> Files), so instead of a webhook this polls:
every FILES_POLL_SECONDS it asks Shopify only for files whose `updated_at` is newer than the
last check (normally 0-10 files, not the whole list) and upserts them by file ID:
  - existing ID  -> row rewritten if URL / Filename / Alt changed
  - new ID       -> row written below the last row
Deleted files are NOT removed here — the nightly full list_shop_files() rewrite handles that.

Same rules as Setup/fetch_images_name_link.list_shop_files():
  filename:wooden-ships-knits*  ·  MediaImage only  ·  .webp only
  columns: A ID | B URL | C Filename | D Alt
If you change those rules there, change them here too.

Started as a background thread by webhook_receiver.py. One-off test (no writes):
  venv/bin/python files_poller.py --since-hours 24 --dry-run

Env:
  CLIENT_ID / CLIENT_SECRET  Shopify app (client-credentials token) — already in Setup/.env
  PPA_SHEET_ID               PPA spreadsheet — already in Setup/.env
  FILES_POLL_SECONDS         default 180; 0 disables the poller
  WEBHOOK_DRY_RUN            "1" = log planned changes, never write (shared with the receiver)
"""
import argparse
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv(Path(__file__).parent / "Setup/.env", override=True)

SHOP = "https://wooden-ships.myshopify.com"
GRAPHQL_URL = f"{SHOP}/admin/api/2026-01/graphql.json"
SHEET_ID = (os.getenv("PPA_SHEET_ID") or "").strip()
TAB = "Links storage"
FILENAME_QUERY = "filename:wooden-ships-knits*"          # same as list_shop_files()
POLL_SECONDS = float(os.getenv("FILES_POLL_SECONDS", "180"))
OVERLAP = timedelta(minutes=15)   # re-check a window before the last poll (clock skew, slow processing)
FIRST_LOOKBACK = timedelta(hours=24)   # on start, catch up on changes made while the service was down
DRY_RUN = os.getenv("WEBHOOK_DRY_RUN", "") == "1"
CREDS_FILE = "credentials/dialy-report-automation-e20c53e67542.json"   # same as Setup/setup.py

QUERY = """
query ($cursor: String, $q: String) {
  files(first: 250, after: $cursor, query: $q, sortKey: UPDATED_AT) {
    edges {
      node {
        ... on MediaImage {
          id
          alt
          image { url }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [files] {msg}", flush=True)


# -------------------------
# SHOPIFY (client-credentials token, refreshed before it expires — the service runs for days)
# -------------------------
_token = {"value": None, "expires": 0.0}


def _access_token(force=False):
    if force or not _token["value"] or time.time() > _token["expires"]:
        r = requests.post(
            f"{SHOP}/admin/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": (os.getenv("CLIENT_ID") or "").strip(),
                "client_secret": (os.getenv("CLIENT_SECRET") or "").strip(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        _token["value"] = body["access_token"]
        # refresh 10 min early; default to 12h if Shopify doesn't say
        _token["expires"] = time.time() + float(body.get("expires_in") or 43200) - 600
    return _token["value"]


def _gql(variables):
    for attempt in range(2):
        r = requests.post(
            GRAPHQL_URL,
            headers={"X-Shopify-Access-Token": _access_token(force=attempt > 0),
                     "Content-Type": "application/json"},
            json={"query": QUERY, "variables": variables},
            timeout=60,
        )
        if r.status_code == 401 and attempt == 0:
            continue   # token expired early — get a new one and retry once
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            raise RuntimeError(data["errors"])
        return data["data"]


def changed_files(since):
    """MediaImage .webp files matching FILENAME_QUERY updated at/after `since` (UTC datetime)."""
    q = f"{FILENAME_QUERY} updated_at:>='{since.strftime('%Y-%m-%dT%H:%M:%SZ')}'"
    files, cursor = [], None
    while True:
        data = _gql({"cursor": cursor, "q": q})["files"]
        for edge in data["edges"]:
            node = edge["node"]
            img = node.get("image")
            if not node.get("id") or not img:   # not an image, or still processing (picked up next poll)
                continue
            filename = img["url"].split("/")[-1].split("?")[0]
            if filename.endswith(".webp"):
                files.append([node["id"], img["url"], filename, node.get("alt") or ""])
        if not data["pageInfo"]["hasNextPage"]:
            return files
        cursor = data["pageInfo"]["endCursor"]


# -------------------------
# SHEET UPSERT
# -------------------------
def _sheets():
    creds = Credentials.from_service_account_file(
        CREDS_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()


def upsert(sheets, rows, dry_run=DRY_RUN):
    ids = sheets.values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A:A"
    ).execute().get("values", [])
    index = {r[0].strip(): i + 1 for i, r in enumerate(ids) if r and r[0].strip()}   # id -> sheet row

    known = sorted({index[r[0]] for r in rows if r[0] in index})
    existing = {}
    if known:
        got = sheets.values().batchGet(
            spreadsheetId=SHEET_ID, ranges=[f"'{TAB}'!A{n}:D{n}" for n in known]
        ).execute()
        for n, vr in zip(known, got.get("valueRanges", [])):
            existing[n] = ((vr.get("values") or [[]])[0] + [""] * 4)[:4]

    updates, new_rows = [], []
    for row in rows:
        n = index.get(row[0])
        if n is None:
            new_rows.append(row)
        elif existing.get(n) != row:
            updates.append({"range": f"'{TAB}'!A{n}:D{n}", "values": [row]})

    if not (updates or new_rows):
        log(f"{len(rows)} changed file(s): no sheet changes")
        return
    log(f"{len(rows)} changed file(s): update {len(updates)}, add {len(new_rows)} row(s)")
    if dry_run:
        for u in updates:
            log(f"  [dry-run] update {u['range']}: {u['values'][0][2]} | alt={u['values'][0][3]!r}")
        for r in new_rows:
            log(f"  [dry-run] add: {r[2]} | alt={r[3]!r}")
        return

    if updates:
        sheets.values().batchUpdate(
            spreadsheetId=SHEET_ID, body={"valueInputOption": "RAW", "data": updates}
        ).execute()
    if new_rows:
        # below the last filled row; INSERT_ROWS grows the grid when needed
        sheets.values().append(
            spreadsheetId=SHEET_ID,
            range=f"'{TAB}'!A{len(ids) + 1}",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": new_rows},
        ).execute()


# -------------------------
# LOOP
# -------------------------
def run():
    if POLL_SECONDS <= 0:
        log("disabled (FILES_POLL_SECONDS=0)")
        return
    sheets = _sheets()
    since = datetime.now(timezone.utc) - FIRST_LOOKBACK
    log(f"polling every {POLL_SECONDS:.0f}s{' (DRY RUN)' if DRY_RUN else ''}")
    while True:
        started = datetime.now(timezone.utc)
        try:
            rows = changed_files(since)
            if rows:
                upsert(sheets, rows)
            since = started - OVERLAP   # only advance after a successful sync
        except (requests.RequestException, HttpError, RuntimeError, KeyError, ValueError) as e:
            log(f"poll failed, will retry: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="One-off Files -> Links storage sync")
    ap.add_argument("--since-hours", type=float, default=24)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    found = changed_files(datetime.now(timezone.utc) - timedelta(hours=args.since_hours))
    log(f"{len(found)} file(s) changed in the last {args.since_hours:g}h")
    if found:
        upsert(_sheets(), found, dry_run=args.dry_run or DRY_RUN)
