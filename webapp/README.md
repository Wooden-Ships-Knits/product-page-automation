# PPA Console — Streamlit web app

An **additive** UI layer over the existing PPA code. It imports and calls
`main.production()`, reads `Output/` and `cron_fetch.log`, and **modifies no core
file**.

## Run (from the project root)

```bash
./venv/bin/streamlit run webapp/app.py
```

Then open the URL Streamlit prints (default http://localhost:8501).

> `bootstrap.py` chdir's to the project root, so credentials/`.env`/logs resolve
> even though the app lives in `webapp/`.

## Pages

- **Build** — season · style · colors · production type → runs `production(data)`,
  streams the live log, then lists the resulting Shopify product links. Guarded by
  a confirmation box (it creates/updates **live** products) and a single-run lock.
- **Fetch Monitor** — shows `cron_fetch.log` and can run `cron_fetch.py` on demand.

## Structure

```
webapp/
├── app.py                  home + environment status
├── bootstrap.py            sys.path + chdir shim (imported first everywhere)
├── ui.py                   theme (colors/background via CSS) + page config
├── .streamlit/config.toml  base theme (used when launched from webapp/)
├── requirements.txt        streamlit
├── pages/
│   ├── 1_Build.py
│   └── 2_Fetch_Monitor.py
└── services/
    ├── run_lock.py         single-run file lock (.run.lock)
    ├── runner.py           wraps production(); stdout capture; IM pre-sync
    └── fetch.py            read log / run cron_fetch.py
```

## Theming

Edit the color constants at the top of [ui.py](ui.py) (`BG`, `ACCENT`, `TEXT`, …)
and/or [.streamlit/config.toml](.streamlit/config.toml).

## Notes / TODO

- **Auth**: none yet — add a login gate (and/or Nginx basic-auth) before exposing it.
- **Smart dropdowns**: Style/Color are free-text for now; a follow-up can populate
  them from the master-data sheet to prevent exact-match typos.
- **VM**: set `IM_COLLECTION_BASE=/var/ppa/im_cache/Collection`; the Build run then
  pre-syncs the IM workbook via `drive_sync` before `get_weight()` reads it.
- **Staleness**: `drive_sync.ensure_local()` fetches only when the local file is
  missing (see README §11a).
