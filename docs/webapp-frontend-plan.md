# PPA Web App — Frontend Plan (Streamlit)

Status: **planning / not yet built**
Goal: host a small web app on the VM, running 24/7, that lets the team trigger
product-page builds, watch them run live, see the resulting Shopify links, and
monitor the hourly fetch jobs — **without changing the existing PPA code.**

---

## 0. Guiding principle — additive only

> **The current PPA code is treated as frozen and robust. The web app is a new
> layer on top of it. No existing file is modified.**

The app *imports and calls* existing functions and *reads* existing outputs.
Every file in §4 is **new**. Existing-file changes, if ever worthwhile, are
listed only under §12 as **optional and non-blocking**.

---

## 1. What this app is actually for

The input is trivial — four fields (season, style, colors, production type). The
app does **not** exist to make that easier. It earns its keep on three things:

1. **Remote trigger** — run a build from anywhere (phone, office) without SSHing
   into the VM or running Python locally.
2. **Feedback on a slow, error-swallowing process** — `create_*` / `update_*`
   swallow failures into `traceback.print_exc()`. Streaming progress + a
   per-style result table (success / skip / error + Shopify link) makes runs
   legible.
3. **Cron visibility** — see the hourly fetch's last run + log without SSHing.

A secondary win: sourcing the input from **live data dropdowns** (not free text)
kills the exact-match failure class we hit (`No master data row for style=…`,
the `4-Feb` size mess).

---

## 2. Features (agreed scope)

- **Trigger product builds** — pick season / style / colors / production type, run.
- **Live run logs / progress** — stream the build's console output to the browser.
- **View results & product links** — per-style status table + Shopify admin links.
- **Monitor the hourly fetch** — last-run time/status, `cron_fetch.log` tail, "run now".

---

## 3. Architecture (additive layer)

```
        ┌─────────────────────────────────────────────┐
        │  NEW: Streamlit web app (webapp/)            │
        │   • Build page (form → live log → results)   │
        │   • Fetch monitor page                       │
        │   • theming, auth                            │
        └───────────────┬─────────────────────────────┘
                        │ imports / calls / reads (never edits)
        ┌───────────────▼─────────────────────────────┐
        │  EXISTING PPA code (unchanged)               │
        │   main.production(data)                      │
        │   config.varia / launcher_params.json        │
        │   Setup.setup._get_sheet_values, ProductInfo │
        │   Output/product_link.txt                    │
        │   cron_fetch.py + cron_fetch.log             │
        └──────────────────────────────────────────────┘
```

Two long-lived processes on the VM:
- **The Streamlit app** (always-on service).
- **The hourly fetch** (`cron_fetch.py`) on a system cron / systemd timer — same
  job that runs locally today, just moved to the VM.

---

## 4. Files — ALL NEW (nothing existing touched)

Proposed new package `webapp/` at the project root:

```
webapp/
├── app.py                 Streamlit entry (page routing, theming, auth gate)
├── pages/
│   ├── 1_Build.py         form + live log + results table
│   └── 2_Fetch_Monitor.py cron_fetch.log tail + "run now"
├── services/
│   ├── runner.py          wraps main.production(); captures stdout → stream
│   ├── run_lock.py        single-run guard (file lock)
│   ├── options.py         reads master data / Color list for dropdowns
│   └── fetch.py           reads cron_fetch.log; shells out to cron_fetch.py
├── auth.py                simple login gate (see §10)
└── .streamlit/
    └── config.toml        theme (background/colors/font) — see §9
```

Plus deployment files (also new): `deploy/ppa-webapp.service`,
`deploy/ppa-fetch.service` + `.timer` (or a crontab line), `deploy/nginx.conf`.

> `webapp/` importing top-level modules (`main`, `Setup`, `config`) requires the
> **project root on `sys.path`** and the process **cwd = project root** (because
> `Setup/setup.py` loads credentials by a relative path). Handled by running the
> service with `WorkingDirectory=<project root>` and a one-line `sys.path` shim in
> `app.py` — no existing file changes.

---

## 5. Screens

### 5a. Build page (`pages/1_Build.py`)
1. **Form** (smart dropdowns, §6): Season (derived/display-only), Style, Colors
   (multi-select), Production type (the 5 enums). "Run build" button — disabled
   while a run is in progress (§8).
2. **Live log** — an `st.status()` / `st.empty()` container streaming stdout as
   `production()` runs (§7).
3. **Results table** — after the run: one row per style →
   `created / updated / skipped / error` + Shopify admin link (from
   `Output/product_link.txt` and captured log). `st.link_button` per link.

### 5b. Fetch monitor (`pages/2_Fetch_Monitor.py`)
- Last run time + inferred status from `cron_fetch.log`.
- Scrollable log tail (`st.code`), manual refresh / auto-refresh.
- "Run fetch now" button → runs `cron_fetch.py` (guarded like builds).

---

## 6. Smart input (removes the exact-match error class)

Instead of free-text, populate dropdowns from live data (read-only reuse of
existing helpers):

- **Style** → distinct `FROM IM | DESCRIPTION` values from the season's Master
  Data tab (guarantees `PUD.decide` / `get_metachart` matches).
- **Colors** → from `Color list` tab, multi-select.
- **Production type** → static list: `unfix, fixed, sample, sale_stock, o4`.
- **Season** → derived; shown read-only.

The chosen values become the `data` list (same shape `config.varia` builds) and
are handed to `production()` — or written to `launcher_params.json` first, to
match the existing mechanism exactly.

---

## 7. Live logs without touching `production()`

`production()` already `print()`s per style. The app captures that:

- `services/runner.py` runs `production(data)` in a background thread, redirecting
  `sys.stdout`/`sys.stderr` into a thread-safe queue (`contextlib.redirect_stdout`
  to a custom writer).
- The Streamlit page drains the queue into a live container each rerun until the
  thread finishes, then renders the results table.

No change to `production()` — we only *observe* its output.

> Optional (later, non-blocking): if we ever want structured results instead of
> parsing stdout, `production()` could `return` a per-style summary. Listed in §12.

---

## 8. Run safety (important — shared state)

A build writes to shared **Google Sheets** + `Output/product_link.txt`, so two
concurrent runs would clobber each other.

- `services/run_lock.py` — a file lock (e.g. `webapp/.run.lock`). Acquire before a
  build/fetch; release after. If held, the UI shows "a run is in progress" and
  disables the button.
- One global lock covers both builds and manual fetches.

---

## 9. Theming / colors (what you asked about)

**Level 1 — `webapp/.streamlit/config.toml`** (supported, upgrade-safe):

```toml
[theme]
base = "dark"
primaryColor = "#e07a5f"
backgroundColor = "#1d1d2b"
secondaryBackgroundColor = "#2a2a3d"
textColor = "#f5f5f5"
font = "sans serif"
```

**Level 2 — custom CSS** via `st.markdown("<style>…</style>",
unsafe_allow_html=True)` for gradients, button shapes, hiding the menu/footer,
per-element colors. Caveat: CSS targets Streamlit's generated class names, which
can shift on version upgrades and may need occasional tweaks. Fine for an internal
tool; pixel-perfect/arbitrary layouts are the one thing Streamlit can't do (would
need React — not worth it here).

---

## 10. Auth (required — it's public and writes to live Shopify)

Minimum viable: a login gate in `auth.py` — a shared password / small user list
checked in `st.session_state`, or `streamlit-authenticator`. Nginx basic-auth can
sit in front as a second layer. Never expose the app unauthenticated.

---

## 11. Deployment on the VM

- **Streamlit service** — `systemd` unit `ppa-webapp.service`:
  `WorkingDirectory=<project root>`, `ExecStart=streamlit run webapp/app.py
  --server.port 8501 --server.address 127.0.0.1`, `Restart=always`.
- **Hourly fetch** — move today's local schedule to the VM: either a crontab line
  (`0 * * * * cd <root> && venv/bin/python cron_fetch.py >> cron_fetch.log 2>&1`)
  or a `ppa-fetch.service` + `ppa-fetch.timer` (systemd, `OnCalendar=hourly`).
- **Reverse proxy** — Nginx terminates HTTPS (Let's Encrypt) and proxies to
  `127.0.0.1:8501`; add basic-auth here too.
- **Env/secrets** — `Setup/.env` + `credentials/…json` present on the VM (as files
  or mounted secrets). cwd must be project root for the relative credential path.

---

## 12. Dependencies & assumptions (flag before building)

1. **IM Master file access on the VM — SOLVED (built + verified).** Handled by
   [drive_sync.py](../drive_sync.py) + the `IM_COLLECTION_BASE` env var:
   - On the VM, `export IM_COLLECTION_BASE=/var/ppa/im_cache/Collection`; `get_im_path()`
     then returns a local cache path (Mac default unchanged).
   - Before a build, call `drive_sync.ensure_local(P.get_im_path())` — it walks the
     Shared Drive `Collection/<season>/IM/` folder and downloads the correct workbook
     to that exact path, so `get_weight()` reads it unchanged.
   - Prereq done: the service account is a member of the `PTIF SERVER` Shared Drive.
   - **Still open: staleness policy** — `ensure_local()` only fetches when the local
     file is missing; add a modifiedTime check / `--force` if builds must always use
     the latest workbook.
2. **Credentials & `.env`** present on the VM; process cwd = project root.
3. **`FROM IM | CODE`** stays in the `K##`/`PK##` format `get_im_path()` expects.
4. **F24 (K53) workbook** currently fails to open (invalid XML) — builds for that
   season would error until the file is re-saved.

### Optional existing-file improvements (NOT required, never blocking)
- `production()` → `return` a structured per-style summary (cleaner than parsing
  stdout in §7).
- Centralize the IM-file read behind a Drive-API helper (§12.1) for cloud portability.

---

## 13. Build phases

1. **Skeleton** — `app.py`, theming, auth gate, two empty pages. (proves deploy)
2. **Build page, no live log** — dropdowns → `production()` → results from
   `Output/product_link.txt`. Add the run-lock.
3. **Live logs** — stdout capture + streaming container.
4. **Fetch monitor** — log tail + "run now".
5. **Deploy** — systemd service + timer + Nginx/HTTPS + auth.
6. **VM data access** — resolve §12.1 (Drive API for the IM file).

---

## 14. Open questions

- Single shared login, or per-user accounts?
- Keep the `launcher_params.json` hand-off, or call `production(data)` directly
  from the app? (Both are additive; direct call is simpler, JSON keeps parity with
  the current interface.)
- Does the existing separate Streamlit interface get folded into this app, or does
  this replace it?
