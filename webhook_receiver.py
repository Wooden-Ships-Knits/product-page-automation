"""
Shopify webhook receiver — keeps the `PP SY LIST` tab in sync per product, in near real time,
instead of waiting for the hourly full snapshot (cron_fetch.py / fetch_product_id_new.fetch).

Topics handled: products/create, products/update, products/delete
(register them with register_webhooks.py).

Flow:
  Shopify POST /shopify/webhook
    -> verify HMAC (X-Shopify-Hmac-Sha256, signed with the app's CLIENT_SECRET)
    -> drop duplicate deliveries (X-Shopify-Event-Id)
    -> queue the event, answer 200 immediately (Shopify times out after 5s)
  Worker thread, every WEBHOOK_FLUSH_SECONDS:
    -> coalesce queued events per product (newest wins)
    -> read PP SY LIST once
    -> update changed rows / write new rows below the last row / delete rows of deleted products
       (also removes extra rows with the same Product ID, e.g. left by the full fetch rewrite)
    -> on a Sheets error the batch is re-queued and retried

Row format is the same as fetch_product_id_new.fetch():
  A Style | B Color | C Product ID | D Page Status | E FP/DC | F Description

Env (Setup/.env / docker-compose):
  CLIENT_SECRET          Shopify app client secret (HMAC key) — already in Setup/.env
  PPA_SHEET_ID           PPA spreadsheet — already in Setup/.env
  WEBHOOK_PORT           default 8502
  WEBHOOK_PATH           default /shopify/webhook
  WEBHOOK_FLUSH_SECONDS  default 5
  WEBHOOK_DRY_RUN        "1" = read the sheet and print the planned changes, but never write

Run from the project root (credentials/ is a relative path):
  venv/bin/python webhook_receiver.py
"""
import base64
import hashlib
import hmac
import html
import json
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv(Path(__file__).parent / "Setup/.env", override=True)

CLIENT_SECRET = (os.getenv("CLIENT_SECRET") or "").strip()
SHEET_ID = (os.getenv("PPA_SHEET_ID") or "").strip()
TAB = "PP SY LIST"
PORT = int(os.getenv("WEBHOOK_PORT", "8502"))
PATH = os.getenv("WEBHOOK_PATH", "/shopify/webhook")
FLUSH_SECONDS = float(os.getenv("WEBHOOK_FLUSH_SECONDS", "5"))
DRY_RUN = os.getenv("WEBHOOK_DRY_RUN", "") == "1"
CREDS_FILE = "credentials/dialy-report-automation-e20c53e67542.json"   # same as Setup/setup.py

TOPICS = {"products/create", "products/update", "products/delete"}


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


# -------------------------
# ROW BUILDING (same rules as fetch_product_id_new.fetch preprocessing)
# -------------------------
SALE_PREFIXES = ["*SALE* - ", "*SALE* ", "*SALE*- ", "SALE* - ", "*SALES* - ", "*SALE * - "]

BOILERPLATE = [
    "Composition: 60% cotton, 40% acrylic",
    "Composition: 60% Cotton, 40% Acrylic",
    "Composition: 76% acrylic, 12% mohair and 12% wool",
    "Composition: 76% Acrylic, 12% Mohair and 12% Wool",
    "Sale items are FINAL SALE: No Returns, Refunds or Exchanges.",
    "Why is this on Sale? Sometimes a shopper changes their mind leaving us with perfectly fabulous sweaters, or we have extra yarn with which we knit new sweaters.",
    "Sale items are FINAL SALE: No Returns, Refunds, or Exchanges.",
    "Why is this on Sale? These pieces are knit as samples for our wholesale business. They have been handled during sales appointments, but they are carefully inspected before shipping.",
]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(body_html):
    """Approximates GraphQL `description` (body_html without tags)."""
    if not body_html:
        return ""
    p = _TextExtractor()
    p.feed(body_html)
    return html.unescape("".join(p.parts))


def first_variant_color(product):
    """Color of the first variant (by position), like variants(first: 1) in the fetch query."""
    position = None
    for opt in product.get("options") or []:
        if (opt.get("name") or "").lower() in ["color", "colour"]:
            position = opt.get("position")
            break
    variants = sorted(product.get("variants") or [], key=lambda v: v.get("position") or 0)
    if position is None or not variants:
        return ""
    return variants[0].get(f"option{position}") or ""


def build_row(product):
    title = product.get("title") or ""
    style = title
    for prefix in SALE_PREFIXES:
        style = style.replace(prefix, "")
    style = style.strip()
    fp_dc = "DC" if "SALE" in title else "FP"

    description = html_to_text(product.get("body_html"))
    for b in BOILERPLATE:
        description = description.replace(b, "")
    description = description.strip()

    return [
        style,
        first_variant_color(product),
        str(product["id"]),
        (product.get("status") or "").upper(),   # webhook sends "active", fetch writes "ACTIVE"
        fp_dc,
        description,
    ]


# -------------------------
# EVENT QUEUE
# -------------------------
_lock = threading.Lock()
_pending = {}                 # product_id -> (triggered_at, topic, payload)
_seen_events = OrderedDict()  # event id -> None, bounded
_SEEN_MAX = 5000


def enqueue(topic, payload, triggered_at, event_id):
    """Returns False when the event is a duplicate delivery (or has no product id)."""
    pid = str(payload.get("id") or "")
    if not pid:
        return False
    with _lock:
        if event_id:
            if event_id in _seen_events:
                return False
            _seen_events[event_id] = None
            while len(_seen_events) > _SEEN_MAX:
                _seen_events.popitem(last=False)
        current = _pending.get(pid)
        if current is None or triggered_at >= current[0]:
            _pending[pid] = (triggered_at, topic, payload)
    return True


def _requeue(batch):
    with _lock:
        for pid, item in batch.items():
            current = _pending.get(pid)
            if current is None or item[0] > current[0]:
                _pending[pid] = item


# -------------------------
# SHEETS SYNC
# -------------------------
def _sheets():
    creds = Credentials.from_service_account_file(
        CREDS_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()


def _tab_properties(sheets):
    meta = sheets.get(
        spreadsheetId=SHEET_ID,
        fields="sheets(properties(sheetId,title,gridProperties(rowCount)))",
    ).execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == TAB:
            return s["properties"]["sheetId"], s["properties"]["gridProperties"]["rowCount"]
    raise RuntimeError(f"Tab '{TAB}' not found in PPA sheet")


def apply_batch(sheets, batch):
    tab_id, row_count = _tab_properties(sheets)
    # Only column A..C for the whole tab (11k+ rows); full A:F just for the rows we touch.
    values = sheets.values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A2:C"
    ).execute().get("values", [])

    # Product ID (column C) -> sheet row numbers (row 1 is the header)
    index = {}
    for i, row in enumerate(values):
        pid = row[2].strip() if len(row) > 2 else ""
        if pid:
            index.setdefault(pid, []).append(i + 2)

    touched = sorted({index[pid][0] for pid in batch if pid in index})
    existing_rows = {}
    if touched:
        got = sheets.values().batchGet(
            spreadsheetId=SHEET_ID, ranges=[f"'{TAB}'!A{r}:F{r}" for r in touched]
        ).execute()
        for r, vr in zip(touched, got.get("valueRanges", [])):
            existing_rows[r] = ((vr.get("values") or [[]])[0] + [""] * 6)[:6]

    updates, new_rows, delete_rows = [], [], set()
    for pid, (_, topic, payload) in batch.items():
        rows = index.get(pid, [])
        if topic == "products/delete":
            delete_rows.update(rows)
            continue
        new = build_row(payload)
        if rows:
            first = rows[0]
            if existing_rows.get(first) != new:
                updates.append({"range": f"'{TAB}'!A{first}:F{first}", "values": [new]})
            delete_rows.update(rows[1:])   # duplicates of the same product
        else:
            new_rows.append(new)

    if not (updates or new_rows or delete_rows):
        log(f"{len(batch)} event(s): no sheet changes")
        return

    log(f"{len(batch)} event(s): update {len(updates)}, add {len(new_rows)}, delete {len(delete_rows)} row(s)")
    if DRY_RUN:
        for u in updates:
            log(f"  [dry-run] update {u['range']}: {u['values'][0][:5]}")
        for r in new_rows:
            log(f"  [dry-run] add: {r[:5]}")
        for r in sorted(delete_rows):
            log(f"  [dry-run] delete row {r}: {(values[r - 2] + [''] * 3)[:3]}")
        return

    if updates:
        sheets.values().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()

    if new_rows:
        start = len(values) + 2                 # first row after the last non-empty row
        needed = start + len(new_rows) - 1
        if needed > row_count:
            sheets.batchUpdate(spreadsheetId=SHEET_ID, body={"requests": [{
                "appendDimension": {"sheetId": tab_id, "dimension": "ROWS", "length": needed - row_count}
            }]}).execute()
        sheets.values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{TAB}'!A{start}",
            valueInputOption="RAW",
            body={"values": new_rows},
        ).execute()

    if delete_rows:
        # bottom-up so earlier deletions don't shift the later ones
        requests_ = [{
            "deleteDimension": {"range": {
                "sheetId": tab_id, "dimension": "ROWS", "startIndex": r - 1, "endIndex": r,
            }}
        } for r in sorted(delete_rows, reverse=True)]
        sheets.batchUpdate(spreadsheetId=SHEET_ID, body={"requests": requests_}).execute()


def worker():
    sheets = _sheets()
    backoff = FLUSH_SECONDS
    while True:
        time.sleep(backoff)
        with _lock:
            batch = dict(_pending)
            _pending.clear()
        if not batch:
            backoff = FLUSH_SECONDS
            continue
        try:
            apply_batch(sheets, batch)
            backoff = FLUSH_SECONDS
        except (HttpError, OSError, RuntimeError) as e:
            _requeue(batch)
            backoff = min(backoff * 2, 300)
            log(f"Sheets sync failed, retrying in {backoff:.0f}s: {e}")


# -------------------------
# HTTP SERVER
# -------------------------
def valid_hmac(body, header_value):
    digest = hmac.new(CLIENT_SECRET.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), header_value or "")


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, text=""):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode())

    def do_GET(self):
        if self.path == "/healthz":
            with _lock:
                queued = len(_pending)
            return self._reply(200, f"ok queued={queued}")
        self._reply(404)

    def do_POST(self):
        if self.path.split("?")[0] != PATH:
            return self._reply(404)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not valid_hmac(body, self.headers.get("X-Shopify-Hmac-Sha256")):
            log("rejected: bad HMAC")
            return self._reply(401)

        topic = self.headers.get("X-Shopify-Topic", "")
        if topic not in TOPICS:
            return self._reply(200)   # acknowledge so Shopify doesn't retry
        try:
            payload = json.loads(body)
        except ValueError:
            return self._reply(400)

        fresh = enqueue(
            topic,
            payload,
            self.headers.get("X-Shopify-Triggered-At") or payload.get("updated_at") or "",
            self.headers.get("X-Shopify-Event-Id") or self.headers.get("X-Shopify-Webhook-Id"),
        )
        if fresh:
            log(f"{topic} {payload.get('id')} {payload.get('title', '')}")
        self._reply(200)

    def log_message(self, *args):
        pass   # we log events ourselves


def main():
    if not CLIENT_SECRET or not SHEET_ID:
        raise SystemExit("CLIENT_SECRET and PPA_SHEET_ID must be set (Setup/.env)")
    threading.Thread(target=worker, daemon=True).start()
    log(f"webhook receiver on :{PORT}{PATH}{' (DRY RUN)' if DRY_RUN else ''}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
