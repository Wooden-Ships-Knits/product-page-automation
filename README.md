# PPA — Product Page Automation

Creates and updates Wooden Ships product pages on Shopify from internal source-of-truth data (IM Master Excel, PPA Google Sheets, Master Data Sheet, UPC list). One or more style-colors go in, fully-built (or fully-updated) product pages come out — title, SEO, variants, size chart, weights, SKUs, barcodes, tags, prices, per-location inventory, images, and a per-style description.

For deeper background on inputs and the original redesign sketch, see [PPA_FLOW.md](PPA_FLOW.md) and [PPA_DATA_PREP.md](PPA_DATA_PREP.md). This README documents the **current** active flow across [create_pp.py](create_pp.py), [update_pp.py](update_pp.py), [post_update_decision.py](post_update_decision.py), [return_product.py](return_product.py), and [fetch_to_product_page.py](fetch_to_product_page.py).

> **Architecture note (current):** product create/update both run through the Shopify **GraphQL `productSet` mutation** (`_run_product_set`), not REST `POST`/`PUT`. `productSet` lets us attach images by their existing **Files/Content GID**, so Shopify references the existing file instead of re-downloading it and creating a duplicate in Content. Inventory and the per-variant Avalara taxcode metafield are still posted via REST (`2026-01`).

---

## 1. Setup

Python 3.9.6. Install deps:

```bash
pip install -r Lrequirements.txt
```

> **numpy/pandas pin:** pandas is built against numpy 1.x on this interpreter. If you hit `ValueError: numpy.dtype size changed`, install `numpy<2` (`pip install "numpy<2"`). numpy 2.x will break the pandas import.

You also need:

- `Setup/.env` with at least: `CLIENT_ID`, `CLIENT_SECRET` (Shopify), `PPA_SHEET_ID`, `SKU_UPC_ID`, `MASTER_DATA_ID`, `RETURN_ID`, and the Shopify location IDs `NE_First_Choice_ID`, `NE_Sample_ID`, `Bali_Stock_ID`, `Bali_To_Produce_ID`.
- **Optional:** `IM_COLLECTION_BASE` — base directory for the IM Master workbooks. Defaults to the Mac's Google Drive mount (`…/PTIF SERVER/Collection`), so **leave it unset on the Mac**. On a headless host (Debian VM / Docker) where Drive isn't mounted, set it to a local cache dir (e.g. `/var/ppa/im_cache/Collection`) and use [drive_sync.py](drive_sync.py) to download the workbook there. See §11a and [docs/webapp-frontend-plan.md](docs/webapp-frontend-plan.md).
- `credentials/dialy-report-automation-e20c53e67542.json` — Google service-account key (already gitignored). Scripts load this via a **relative path** (`credentials/...`), so they must be run from the project root.
- The current season's IM Master workbook at `<IM_COLLECTION_BASE>/<season>/IM/<season_code> IM MASTER.xlsx` (e.g. `…/Collection/26 Fall/IM/F26 IM MASTER.xlsx`). The path is built by `ProductInfo.get_im_path()` (derived from the `FROM IM | CODE` value), with the base dir from `IM_COLLECTION_BASE` (default = the Mac Drive mount).

`.env`, `credentials/`, and `*.xlsx` are all gitignored.

---

## 2. Project layout

```
PPA/
├── main.py                       Manual entry — a `data` list of {Styles, Colors, Production} dicts, looped by production()
├── cron_fetch.py                 Standalone runner for the two fetch jobs (fetch_id.fetch + list_shop_files); for scheduling
├── run_fetch.sh                  Wrapper that cd's to project root + uses the venv, then runs cron_fetch.py (logs to cron_fetch.log / launchd_fetch.log)
├── return_product.py             Bulk entry — iterates a daily Master Grid of Return tab and creates/updates
├── create_pp.py                  CreatePP class — 5 create_* methods + product_post + _run_product_set + set_inventory_metafield
├── update_pp.py                  UpdatePP class — 5 update_* methods mirroring create_pp (productSet update + variant preservation)
├── post_update_decision.py       decide() — looks up PP SY LIST to choose create vs update + returns product_id/status/description
├── fetch_to_product_page.py      ProductInfo class — all data fetching/derivation lives here
├── pp_status.py                  Scratch / WIP
├── deletion_products.py          One-off product cleanup
├── config/varia.py               Constants (IM header row, default season)
├── Setup/
│   ├── setup.py                  Google Sheets client + caching, Shopify headers
│   ├── set_sy.py                 Shopify auth, publish_to_all_channels, product_url
│   ├── fetch_product_id_new.py   Snapshot existing Shopify products into the PPA sheet (run daily)
│   ├── fetch_images_name_link.py List Shopify Files into the `Links storage` tab (run hourly-ish)
│   ├── tags_generator.py         Tag construction
│   └── generic_color_generator.py  Maps brand color → generic color (GPT-assisted, cached in sheet)
└── notes/                        Older / scratch work (gitignored)
```

---

## 3. The five production types

All five exist in **both** [create_pp.py](create_pp.py) (`CreatePP`) and [update_pp.py](update_pp.py) (`UpdatePP`). They share the same skeleton — only the `ProductInfo` flags, inventory location, and size filtering differ.

| Type         | `sample` | `sale` | `sas` | Sizes                                  | Inventory location(s)                              |
|--------------|----------|--------|-------|----------------------------------------|----------------------------------------------------|
| `unfix`      | F        | F      | F     | Full IM master template (4 sizes)      | `Bali_To_Produce_ID` (placeholder qty 5000)        |
| `fixed`      | F        | F      | F     | **Only sizes with NE+Bali stock > 0**  | `NE_First_Choice_ID` + `Bali_Stock_ID` (real qty)  |
| `sample`     | T        | T      | F     | S/M only (via `keep = [sizes.index('S/M')]`) | `NE_Sample_ID` (qty from `NE SAMPLE STOCK`)  |
| `sale_stock` | F        | T      | F     | **Only sizes with NE+Bali stock > 0**  | `NE_First_Choice_ID` + `Bali_Stock_ID` (real qty)  |
| `o4`         | F        | T      | T     | Full IM master template (4 sizes)      | `Bali_To_Produce_ID` (placeholder qty 5000)        |

The `sample` / `sale` / `sas` flags propagate into pricing, tags, SEO copy, body description, and SKU sheet choice via `ProductInfo`.

**Inventory-posting divergence between create and update:**
- `CreatePP.set_inventory_metafield` posts inventory **only to the relevant location(s)** for the type (so e.g. `unfix` touches only `Bali_To_Produce_ID`).
- `UpdatePP.set_inventory_metafield` posts to **all four locations** for every variant, zeroing out the irrelevant ones. This effectively clears stock from any location not in the type's "relevant" list. It's an intentional reset on update, but the two helpers are no longer symmetric — keep this in mind if you ever consolidate them.

---

## 4. Multi-color support

Both constructors now take a **list of colors**:

```python
CreatePP(STYLE, COLORS, SEASON, SALE, DESCRIPTION)        # COLORS is a list, e.g. ["NAVY", "CREAM"]
UpdatePP(STYLE, COLORS, SEASON, PRODUCT_ID, SALE, DESCRIPTION)
ProductInfo(STYLE, COLORS, SEASON, sample=, sale=, sas=)  # self.color = colors[0], self.colors = colors
```

`product_post` builds one variant per **(color × size)** and a single Shopify `Color` product option listing every colorway. Per-color images are matched from `Links storage` by an `alt` slug (`color.replace("/"," ").lower().replace(" ","-")`) and attached to that color's variants via `"file": {"id": <Files GID>}`. SKUs/barcodes are indexed `[i + j]` where `j = color_index * len(sizes)`, so the SKU/barcode arrays must be laid out color-major.

> Stock-based filtering (`get_NE_qty` / `get_BALI_qty`) and `get_sample_qty` still match on `self.color` = **the first color only**. Multi-color is currently exercised mainly for placeholder/full-template types and same-stock colorways. For `fixed` / `sale_stock`, treat one color per call as the safe path until stock lookups become per-color.

---

## 5. Create vs update — how the decision is made

Both [main.py](main.py) and [return_product.py](return_product.py) consult [post_update_decision.py](post_update_decision.py) `decide(STYLE, COLOR, FP_DC)` before doing anything. It returns **four** values:

```python
create_new, product_id, status, description = PUD.decide(STYLE, COLOR, FP_DC)
```

- Reads the `PP SY LIST` tab of the PPA sheet.
- Looks up `description` from the **last** row where `Style` contains `STYLE` (`df_desc["Description"].iloc[-1]`; no Color or FP/DC filter — the description column is per-style, shared across colorways). Empty string if no style row exists.
- Filters rows whose `Style` and `Color` match (case-insensitive substring) **and** whose `FP/DC` column equals `"FP"` or `"DC"`.
- If **no match** → `create_new=True`, `product_id=""`, `status="DRAFT"` (forced); caller routes to `CreatePP`.
- If a match exists → `create_new=False`, returns the existing `Product ID` and `Page Status` (e.g. `DRAFT` / `ACTIVE`); caller routes to `UpdatePP`.

`FP_DC` mapping (set by the caller):

- `fixed`, `unfix` → `"FP"` (full price product line) → `SALE=False`
- `sale_stock`, `sample`, `o4` → `"DC"` (discounted / sale line) → `SALE=True`

The boolean drives:

- `templateSuffix` selection in `product_post` — `'sale-item'` when `SALE=True`, `'default'` when `SALE=False` (only used as fallback when `tags_generator.additional_tags` doesn't return its own suffix).
- The `sale=` kwarg passed to `set_sy.publish_to_all_channels(product_id, sale=...)` on **create** — `create_unfix`/`create_fixed` pass `sale=False` (all channels incl. Pinterest); the other three use the default `sale=True` (excludes Pinterest).

The `description` is injected into `descriptionHtml` between the sale-disclaimer block (if any) and the thread-composition paragraph: `sale_desc + f"<p>{description}</p>" + thread_comp`. Used on both create and update.

**The current rule is to only act on `DRAFT` products.** `ACTIVE` products are skipped so we never overwrite a live page. Enforced in both `main.py` and `return_product.py`.

---

## 6. End-to-end flow

### 6a. Create flow

```
main.py / return_product.py
   │
   ▼
PUD.decide(STYLE, COLOR, FP_DC)  →  create_new=True  →  CreatePP.create_<type>()
   │
   ├── P = ProductInfo(STYLE, COLORS, SEASON, sample=, sale=, sas=)
   │
   ├── [fixed / sale_stock only]
   │     qty_ne, skus_ne = P.get_NE_qty()          ← reads NE STOCK (qty + built SKU per size)
   │                                                  empty match → ([0,0,0,0], ["","","",""])
   │     qty_ba, skus_ba = P.get_BALI_qty()        ← reads BALI STOCK (X/L always 0)
   │                                                  empty match → ([0,0,0,0], ["","","",""])
   │     combined = qty_ne + qty_ba (per size, via _to_int)
   │     keep = indices where combined > 0
   │     if not keep:  return (None, None)         ← skip product, no stock
   │     skus_chosen[i]  = skus_ne[i] if non-blank else skus_ba[i]   ← NE primary, Bali fallback
   │     barcodes_chosen = P.fetch_barcode(skus_chosen)              ← lookup in PRODUCTION UPC LIST
   │     filter qty_ne / qty_ba by keep;  total_qty = sum(qty_ne + qty_ba)   ← scalar, drives tag bands
   │
   ├── product_data, ordered_skus = self.product_post(P, keep=, qty=total_qty?, skus=skus_chosen?, barcodes=barcodes_chosen?)
   │     │
   │     ├── P.title_and_desc()        title, sale title, sale-disclaimer HTML, thread composition
   │     ├── P.get_SEL()               SEO page title, meta description, handle/url
   │     ├── P.get_metachart()         → (size-chart HTML, sizes list)  [from MASTER_DATA sheet]
   │     ├── P.get_weight()            sizes + per-size weight (grams) from IM Master xlsx
   │     ├── P.get_sku_barcode()       default barcodes + default SKUs (PRODUCTION/SAMPLE UPC LIST)
   │     │                              — used only when caller didn't pass skus= / barcodes=
   │     ├── [if keep]                 filter sizes/weights/default_skus/default_barcodes by keep
   │     ├── P.get_tags()              base tag string (per-type tags + color + dated tag)
   │     ├── tg.additional_tags(...)   appends qty/size-based tags, returns (tags, templateSuffix)
   │     ├── P.get_type()              productType derived from STYLE name
   │     ├── P.get_price()             (full_price, price) with fallback chain
   │     ├── P.get_image_from_files()  per-color list of {id: <Files GID>, alt: <color-slug>}
   │     └── assemble ProductSetInput:
   │           descriptionHtml = sale_desc + f"<p>{self.description}</p>" + thread_comp
   │           metafields = [avalara.taxcode, custom.size_chart_metafield]   ← size chart is a METAFIELD now
   │           files = unique Files GIDs;  variants carry "file": {"id": gid}
   │           status = "DRAFT"
   │
   ├── product_id, variants = self._run_product_set(product_data, ordered_skus)
   │     POST 2026-01/graphql.json  productSet(synchronous: true)
   │     └── on GraphQL errors / userErrors / null:  return (None, None)
   │     variants aligned to ordered_skus BY SKU: each {id, inventory_item_id} or None
   │
   ├── set_sy.publish_to_all_channels(product_id, sale=...)
   │
   ├── set_inventory_metafield(variants, type, qty_ne=, qty_ba=, qty_sample=)
   │     │  per variant (skipping any None whose sku productSet didn't return):
   │     ├── [fixed/sale_stock] inventory_levels/set NE_First_Choice_ID=qty_ne[i], Bali_Stock_ID=qty_ba[i]
   │     ├── [unfix/o4]         inventory_levels/set Bali_To_Produce_ID=5000
   │     ├── [sample]           inventory_levels/set NE_Sample_ID=qty_sample
   │     └── POST per-variant avalara.taxcode metafield
   │
   └── return (link, product_id)   ← Shopify admin URL; caller can append to PP SY LIST
```

### 6b. Update flow

Mirrors create, except the product already exists. `UpdatePP` is constructed with the existing `PRODUCT_ID` returned by `PUD.decide`.

```
PUD.decide(...)  →  create_new=False  →  UpdatePP.update_<type>()
   │
   ├── P = ProductInfo(STYLE, COLORS, SEASON, sample=, sale=, sas=)
   │
   ├── [fixed / sale_stock only]   stock filtering + NE/Bali SKU fallback + barcode lookup, same as create
   │
   ├── existing = GET 2024-01/products/{id}.json → ["product"]["variants"]   ← REST GET, still 2024-01
   │
   ├── product_set_input, ordered_skus = self.product_post(self.COLORS, P, existing, keep=, qty=, skus=, barcodes=)
   │     │   builds desired (in-stock) variants, stamping each with its existing id
   │     │   matched by SKU first, else by (size, color) option values
   │     │   PRESERVES every existing variant not in the desired set, re-including it so
   │     │     productSet's full-sync does NOT delete out-of-stock sizes
   │     │   productOptions list every Size/Color value across desired + preserved
   │     │   files only attached when non-empty (empty list would delete ALL media)
   │     └   includes: id, handle, seo, descriptionHtml, tags, templateSuffix, metafields, options, variants
   │         NOT included: title, status  → a DRAFT stays DRAFT with its existing title
   │
   ├── product_id, variants = self._run_product_set(product_set_input, ordered_skus)
   │     POST 2026-01/graphql.json  productSet(synchronous: true)
   │
   └── set_inventory_metafield(variants, type, ...)
         — posts to ALL FOUR locations per variant, zeroing the irrelevant ones
   │
   └── return link   ← Shopify admin URL built from self.PRODUCT_ID
```

`productSet` reconciliation semantics:

- Variant **with** `id` (matched an existing one) → update in place.
- Variant **without** `id` (new SKU/option combo) → create.
- Existing variant **omitted** from the list → deleted. **This is why update re-includes (`preserved`) the out-of-stock variants** — so they survive.

`handle`, `seo`, `descriptionHtml`, `tags`, `templateSuffix`, and the metafields **are** in the update payload, so URL/SEO, description, tags, template, size chart, and images all refresh on every update. `title` and `status` are **not**, so a `DRAFT` stays a `DRAFT` with its existing title.

### Key derived fields

- **Sizes** are X/S, S/M, M/L, X/L. `SIZE_RANGE` maps each to its body-size label (e.g. `S/M → (6-8)`), used in the Shopify `Size` option text (`"S/M (6-8)"`).
- **Size chart**: comes from `MASTER_DATA_ID` via `get_metachart()` and is written as the **`custom.size_chart_metafield`** product metafield (no longer embedded in `body_html`). `DEV | XL | (Y/N)` toggles whether X/L is included. The chart renders all master-data sizes even when stock filtering drops variants — by design.
- **Description**: pulled in `PUD.decide()` from the `Description` column of `PP SY LIST` (last row where `Style` matches) and injected into `descriptionHtml` as `<p>{description}</p>`. Editing the cell and re-running an update refreshes it on Shopify.
- **Generic color**: looked up in the `Color list` tab. If absent, GPT proposes one and writes it back for next time.
- **Prices** use a cascading fallback: `PB ADJUSTED …` → `LATEST …` → `IM PRICE`.
- **Images**: `get_image_from_files()` reads the `ID` column (a Shopify Files/Content GID) from `Links storage`, sorted by `Filename`, grouped per color. Attached by GID reference, so no new entries appear in Content > Files and no re-download happens on update.
- **SKU source depends on production type**:
  - `fixed` / `sale_stock` → SKU from **NE STOCK** if non-blank, else **BALI STOCK** per size:
    ```python
    skus_chosen = [skus_ne[i] if str(skus_ne[i]).strip() else skus_ba[i] for i in keep]
    ```
  - `unfix` / `sample` / `o4` → default SKU from `P.get_sku_barcode()` (`PRODUCTION UPC LIST` or `SAMPLE UPC LIST`).
- **Barcode source mirrors SKU source**:
  - `fixed` / `sale_stock` → `P.fetch_barcode(skus_chosen)` looks each SKU up in `PRODUCTION UPC LIST` (joined by value, `""` if missing).
  - `unfix` / `sample` / `o4` → default barcodes from `P.get_sku_barcode()` (positional pairing).
- **Missing-stock handling**: `get_NE_qty()` / `get_BALI_qty()` short-circuit to `([0,0,0,0], ["","","",""])` when style+color isn't present. With `keep = [i for i,q in enumerate(combined) if q > 0]`, a product missing from *both* sheets is cleanly skipped with "No stock … — skipping".

---

## 7. Data sources

| Source                                  | Used for                                              |
|-----------------------------------------|-------------------------------------------------------|
| IM Master xlsx (`…/Collection/<season>/IM/<season_code> IM MASTER.xlsx`) | Per-size weights (header row from `config/varia.py` `IM_header`) |
| Master Data sheet (`MASTER_DATA_ID`)    | Size chart, XL flag, printed flag, price columns      |
| PPA sheet (`PPA_SHEET_ID`)              | `Color list` (generic colors), `NE STOCK`, `BALI STOCK`, `NE SAMPLE STOCK`, `Links storage` (image Files GIDs + URLs), `PP SY LIST` (create-vs-update lookup + per-style `Description`) |
| UPC sheet (`SKU_UPC_ID`)                | `PRODUCTION UPC LIST` / `SAMPLE UPC LIST` (SKUs + barcodes) |
| Master Grid of Return (`RETURN_ID`)     | Daily worksheet driving `return_product.py` (which styles to update today, FP vs sale flag) |
| Shopify Admin API (`2026-01` GraphQL + REST; `2024-01` REST GET on update) | Product create/update, inventory, metafields, publishing |

Sheet reads go through `Setup.setup._get_sheet_values` which caches by `(sheet_id, worksheet, range_name, use_all_values)` for the life of the process. Excel reads are similarly cached. So inside one run the same sheet is fetched once.

---

## 8. Inventory & location handling

**Real-inventory case (`fixed`, `sale_stock`)**

- Pulls actual qtys from `NE STOCK` and `BALI STOCK`.
- Filters out sizes where combined qty = 0 — those variants are never created (and on update, are not in the desired set, though existing ones are preserved rather than deleted).
- Posts the **real** per-warehouse qty: NE qty → `NE_First_Choice_ID`, Bali qty → `Bali_Stock_ID` (and, on update, 0 to the two sample/produce locations).
- If every size is zero, the product is skipped with a console message.

**Placeholder case (`unfix`, `sample`, `o4`)**

- All 4 sizes (or just S/M for `sample`) always created.
- `unfix` / `o4`: inventory set to flat `5000` at `Bali_To_Produce_ID`.
- `sample`: inventory set to `get_sample_qty()` (the `S/M` cell, scalar) at `NE_Sample_ID`.

> **Inventory is mapped by SKU, not position.** `_run_product_set` returns variants aligned to `ordered_skus` by matching the `sku` field in the productSet response, so a variant whose SKU wasn't returned comes back as `None` and is skipped (with a console note) rather than landing qty on the wrong size.
>
> **Order assumption still holds for the source arrays**: `get_NE_qty` / `get_BALI_qty` / `get_weight` / `get_sku_barcode` return arrays in **X/S → S/M → M/L → X/L** order. The `keep` filter uses positional indices, so if a source sheet is sorted differently, fix it at the source.

---

## 9. Running

### Manual run (`main.py`)

Edit the `data` list at the top of `main.py` — a list of dicts, one per style:

```python
SEASON = "26 Spring"

data = [
    {
        "Styles": "KATE STRIPED V COTTON".upper(),
        "Colors": ["White/Black/Khaki"],   # a LIST — one or more colorways
        "Production": "fixed",             # one of: unfix, fixed, sample, sale_stock, o4
    },
]
```

Then run:

```bash
python main.py
```

`production(data)` will, for each entry:

1. Map `Production` → `FP_DC` and `SALE` (FP / `SALE=False` for `fixed`/`unfix`, DC / `SALE=True` otherwise).
2. Call `PUD.decide(STYLE, COLOR, FP_DC)` (using `Colors[0]`) and unpack `create_new, product_id, status, description`.
3. If `status.upper() == "DRAFT"`: route to `CreatePP(STYLE, COLORS, SEASON, SALE, description)` (new) or `UpdatePP(STYLE, COLORS, SEASON, product_id, SALE, description)` (existing), then call the matching `create_<type>()` / `update_<type>()`. **All five types are supported on both paths.**
4. On successful create (`link is not None`), accumulate `[STYLE, COLOR, product_id, "DRAFT", FP_DC]`.
5. If `status != "DRAFT"`, print "not found or an active pp. skipping" and continue.

After the loop, if any product was created, append the accumulated rows to the first empty `Style` row of `PP SY LIST` (column **A**). Updates do **not** append (the row is presumed already present).

> The `fetch_id.fetch()` / `fetch_image.list_shop_files()` calls in `main.py`'s `__main__` are commented out on purpose — those two snapshots now run on their own hourly schedule (see "Scheduled fetch refresh" below), so `main.py` only does `production(data)`. Uncomment them only if you want a one-off manual refresh inside a `main.py` run.

### Scheduled fetch refresh (`cron_fetch.py` + LaunchAgent)

The two snapshot jobs that keep the lookup sheets fresh —

- `fetch_id.fetch()` → refreshes the `PP SY LIST` Product-ID/status snapshot
- `fetch_image.list_shop_files()` → refreshes the `Links storage` image Files-GID list

— run **automatically every hour** via a macOS **LaunchAgent**, independent of the Streamlit app (which only runs `production(data)`).

Pieces:

- [cron_fetch.py](cron_fetch.py) — imports both modules and calls the two functions, with a timestamped log header.
- [run_fetch.sh](run_fetch.sh) — wrapper that `cd`s to the project root (required — credentials load via a relative path) and invokes `venv/bin/python cron_fetch.py`, appending stdout/stderr to a log.
- `~/Library/LaunchAgents/com.ppa.fetch.plist` — the schedule (`StartCalendarInterval` `Minute 0` = top of every hour). Installed in the user's own LaunchAgents, so **no admin / Full Disk Access** is needed (unlike system `cron`, which can't reach the Google Drive CloudStorage path without it).

Logs: `launchd_fetch.log` (LaunchAgent runs) and `cron_fetch.log` (manual `run_fetch.sh` runs), both in the project folder.

Manage it:

```bash
launchctl start com.ppa.fetch                                   # run once now (test)
launchctl list | grep ppa                                       # confirm it's loaded
launchctl unload ~/Library/LaunchAgents/com.ppa.fetch.plist     # stop / disable
launchctl load -w ~/Library/LaunchAgents/com.ppa.fetch.plist    # re-enable
```

> A LaunchAgent only fires while you're logged in and the Mac is awake. A run missed during sleep/shutdown is executed once shortly after the next login.
>
> An inert hourly `cron` entry also exists (`crontab -l`) from an earlier attempt; it fails silently without Full Disk Access and can be ignored or removed with `crontab -r`.

### Bulk, sheet-driven (`return_product.py`)

Reads the Master Grid of Return's daily worksheet, drops rows where any `ZZ`-named column equals `"ZZ"`, dedupes by `(Style, Color)`, and iterates each remaining row:

- Reads `Added to full price` / `Added to sale`. The one marked `x` decides FP vs DC and `SALE`. Both `x` or neither → log and `continue`.
- Calls `PUD.decide` (unpacks 4: `create_new, PRODUCT_ID, status, DESCRIPTION`).
- If `create_new == True`: instantiates `CreatePP` and calls `create_fixed()` (FP) or `create_sale_stock()` (DC). On success, writes the returned link to column **R** of the source row and accumulates a `PP SY LIST` writeback.
- If `create_new == False` and the product is `DRAFT`: `update_fixed()` (FP) or `update_sale_stock()` (DC), then writes the link back to column **R**.
- Active products are logged ("this is an active product, retracting…") and skipped.
- After the loop, appends accumulated new rows to `PP SY LIST` (column **A**).

```bash
python return_product.py
```

Row→sheet mapping: `iterrows()` yields the DataFrame index `idx`; the sheet row is `idx + 7` (header is `values[5]` = sheet row 6, data starts row 7). Filtering preserves the original index, so the offset stays correct after the `ZZ` filter.

The whole loop is wrapped in `try/except: traceback.print_exc()` so one bad row doesn't kill the run — but errors are swallowed; check console output.

> ⚠️ **`return_product.py`'s create branch is broken.** It calls `create_pp.CreatePP(STYLE, COLORS, SEASON, SALE)` — missing the required `DESCRIPTION` positional arg the constructor now expects. The first create will raise `TypeError: __init__() missing 1 required positional argument: 'DESCRIPTION'`, swallowed by the outer try/except. The **update** branch is correct (it passes `DESCRIPTION`). Fix: pass `DESCRIPTION` into the `CreatePP(...)` call, mirroring `main.py`.
>
> ⚠️ `worksheet_name` is currently **hardcoded** (`'Jun 5, 2026'`) with the `date.today()` line commented out. Re-enable the dynamic date for scheduled runs.

---

## 10. Known caveats

- **`return_product.py` create branch is broken** (missing `DESCRIPTION` — see §9). Update branch is fine.
- **Hardcoded write columns.** `main.py` / `return_product.py` write `PP SY LIST` rows starting at column **A**; `return_product.py` writes the Shopify link to column **R** of the source row. If columns shift, change the literal. The PPA sheet ID is also hardcoded as a literal in both writeback blocks (not read from `.env`).
- **Multi-color stock lookups are first-color-only.** `get_NE_qty` / `get_BALI_qty` / `get_sample_qty` filter on `self.color = colors[0]`. Variants for additional colors reuse the first color's keep/qty. Safe for placeholder types; for `fixed`/`sale_stock`, prefer one color per call.
- **`CreatePP.create_*` returns `(None, None)` on any failure** (no stock, GraphQL error, exception). Callers must check `if link is not None:`. `UpdatePP.update_*` returns a built `link` even after a swallowed exception or no-stock skip — a non-None update return does **not** guarantee success; check console.
- **Error handling swallows failures.** All `create_*` / `update_*` wrap their body in `try/except Exception: traceback.print_exc()`. Check console — silent success ≠ actual success.
- **Update preserves out-of-stock variants by re-including existing ones.** It matches existing variants by SKU, falling back to `(size, color)` option values. If a SKU changes for an existing size+color, productSet sees the old one as "to preserve" and the new one as "to create" with the same option combo → potential "Option values are not unique". Keep SKUs stable.
- **`set_inventory_metafield` diverges between create and update.** Create posts only to the relevant location(s); update posts to **all four**, zeroing the irrelevant ones (so updating `unfix` → `fixed` wipes `Bali_To_Produce_ID` to 0). Intentional, but easy to miss.
- **API version is mixed on update.** `update_pp.py` uses `2024-01` for the product GET and `2026-01` for productSet, inventory, and metafields. `create_pp.py` is `2026-01` throughout.
- **`set_inventory_metafield` has a silent catch-all.** Any `production_type` not in `('fixed', 'sale_stock', 'sample')` falls into the `Bali_To_Produce_ID` + 5000 branch. `unfix` / `o4` rely on this; a typoed type would also route there.
- **Update touches `handle` and `seo`.** An update re-sends the SEO handle/title, so a manually-changed product URL would be overwritten with the generated one. Same for `descriptionHtml`, `tags`, `templateSuffix`, size-chart metafield, and images — hand edits in the Shopify admin get clobbered. Edit the source sheets, not Shopify.
- **`files=[]` would delete all media on update** — guarded by only attaching `files` when non-empty. If a product's images vanish after an update, the `Links storage` match probably returned empty.
- **Blank-SKU variants.** `keep` filters on qty only. A size with `qty > 0` but both `skus_ne[i]` and `skus_ba[i]` blank creates a variant with empty SKU and (via `fetch_barcode`) empty barcode. Worth a glance after a run on a new product.
- **`get_BALI_qty` always returns 0 for X/L** (intentional — Bali doesn't carry X/L).
- **`PP SY LIST` Page Status is a stale snapshot** — only refreshed by `fetch_product_id_new.py`. Between snapshots a product can drift DRAFT → ACTIVE without `PUD.decide` knowing.
- **`PUD.decide` uses substring + regex matching** (`str.contains`). Prefix-colliding styles (`EMORY TIPPED L/S TOP` vs `… V2`) can match the wrong row.
- **Header-duplication safety in `return_product.py`**: the loop uses `_first()` because the Master Grid can have duplicate column headers. Don't remove it.

---

## 11. Off-machine / cloud deployment

The project currently assumes it runs **on a Mac with Google Drive for Desktop mounted**. Two host-specific assumptions must be removed before it can run on any cloud VM/container (Azure, GCP, AWS — all the same here):

### 11a. The IM Master workbook is read from a local filesystem path — SOLVED

On the Mac, `ProductInfo.get_im_path()` returns a path under the **Google Drive for Desktop mount**. No headless host (Debian VM / Docker) has that mount, so the path would `FileNotFoundError` off-machine.

**Implemented solution: download-to-disk via the Drive API, keeping the read code path-based.** Two pieces:

1. **`IM_COLLECTION_BASE` env var** ([fetch_to_product_page.py](fetch_to_product_page.py) `get_im_path()`) — the base dir for the workbooks. Defaults to the Mac Drive mount (so the Mac is unchanged); on the VM set it to a local cache dir (e.g. `/var/ppa/im_cache/Collection`). The path *shape* stays identical, so `header_finder()` / `get_weight()` are untouched.
2. **[drive_sync.py](drive_sync.py)** — a standalone helper that, using the existing service account, walks the Shared Drive folder chain `PTIF SERVER / Collection / <season> / IM /` and downloads the correct workbook to the exact local path `get_im_path()` expects:

   ```bash
   python drive_sync.py --check                          # verify access + list IM files
   python drive_sync.py --ensure "<get_im_path() value>" # download that workbook to disk
   ```

   In code: `drive_sync.ensure_local(P.get_im_path())` right before the build reads the IM file.

Why folder-walk, not file-ID or bare name: the Shared Drive holds **hundreds** of similarly-named IM Master copies (old seasons, `Copy of …`, `@Syno…` junk). The consistent anchor is the **season's `IM/` folder**, so `drive_sync` navigates the folder tree and takes the workbook inside it — exact name first, else the single workbook present, else a clear error (never a silent wrong guess).

Two Shared-Drive gotchas (handled by `drive_sync`):
- The service-account email (`dialy-report-bot@dialy-report-automation.iam.gserviceaccount.com`) must be a **member of the `PTIF SERVER` Shared Drive** (Viewer). Done.
- Every Drive call needs **`supportsAllDrives=True`** / **`includeItemsFromAllDrives=True`** or Shared-Drive files come back empty.

> Not solved by this: **staleness** — `ensure_local()` only downloads when the local file is missing, so a changed workbook in Drive won't refresh until forced. A modifiedTime check / `--force` policy is a TODO. And `rclone mount` was rejected as too fragile for an unattended server.

### 11b. Credentials load from a relative file path

`credentials/dialy-report-automation-e20c53e67542.json` is read by a **relative path**, so it must be present in the working directory. On a cloud host, ship it as a **mounted secret / env var**, not a checked-in file.

- **GCP advantage:** you can drop the key file entirely. Attach the service account to the resource (Compute Engine / Cloud Run / Cloud Function) and let the client libraries pick it up via **Application Default Credentials** — `google.auth.default(scopes=[...])` replaces `Credentials.from_service_account_file(...)`. Same code path works locally (falls back to `gcloud auth` or `GOOGLE_APPLICATION_CREDENTIALS`). Still requires Shared-Drive membership and the Drive/Sheets APIs enabled in the project; the `cloud-platform` scope does **not** include Drive.
- **Azure/AWS:** no keyless equivalent for Google APIs — mount the JSON key as a secret.

### 11c. Scheduling moves off the local LaunchAgent

The hourly fetch jobs (§9, "Scheduled fetch refresh") currently run from a macOS LaunchAgent that only fires while this Mac is awake. In the cloud, replace it with a native always-on scheduler:

| Local piece | GCP | Azure |
|---|---|---|
| LaunchAgent / cron timer | Cloud Scheduler | Logic Apps / Container Apps Jobs timer |
| `run_fetch.sh` + venv | Cloud Run Job (container) | Container Apps Job |
| `launchd_fetch.log` | Cloud Logging | Azure Monitor |
| service-account key file | attached SA (keyless) | mounted secret |

So `cron_fetch.py` → containerize → run as a scheduled job, no Mac required and no Full Disk Access dance.

> **Summary:** the only real code change is §11a (swap the hardcoded `.xlsx` path for a Drive-API download by file ID). Everything else — Sheets, Shopify, inventory — is already pure HTTPS API and portable as-is.
