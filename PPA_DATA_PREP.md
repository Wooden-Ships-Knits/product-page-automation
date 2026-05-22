# PPA — Data Preparation Checklist

What must exist (and be filled in) so [main.py](main.py) (single style) and [return_product.py](return_product.py) (bulk from Master Grid of Return) can run cleanly.

Companion to [PPA_FLOW.md](PPA_FLOW.md) — that doc covers the *logic*, this one covers the *inputs*.

---

## 0. Dependency map at a glance

```mermaid
flowchart LR
    PPA[PPA Sheet<br/>PP SY LIST + stock tabs + Color list] --> PIPE[Pipeline]
    UPC[SKU/UPC Sheet<br/>PRODUCTION + SAMPLE UPC LIST] --> PIPE
    MD[Master Data Sheet<br/>size chart, XL flag, prices] --> PIPE
    RET[Master Grid of Return<br/>daily worksheet] --> PIPE
    IMX[IM Master xlsx<br/>weights] --> PIPE
    SVC[Google service-account JSON] --> PIPE
    ENV[.env<br/>Shopify + sheet IDs + location IDs] --> PIPE
    PIPE --> SHOP[Shopify store<br/>collections + locations + templates]
```

If any one of these is missing, mis-tabbed, or has wrong headers, **the affected step will silently fall back to empty values / `qty=0` / `barcode=""`**. The pipeline doesn't fail loudly — it fails quietly with bad data, behind a `try / except: traceback.print_exc()`. Verify each input below before a run.

---

## 1. Credentials & environment

| File | Purpose | Required keys / contents |
|---|---|---|
| `Setup/.env` | All sheet IDs, Shopify credentials, location IDs | See table below |
| `credentials/dialy-report-automation-e20c53e67542.json` | Google service-account key used by `gspread` and `googleapiclient` | Standard service-account JSON. The account must be **shared as Editor** on every Google Sheet listed in §2. |
| `Copy of <season> IM MASTER.xlsx` | Per-size weights | Lives in the project root. The current season's file must be present locally. |

`.env`, `credentials/`, and `*.xlsx` are all gitignored.

### `.env` keys actually consumed by the code

| Key | Used by | Notes |
|---|---|---|
| `CLIENT_ID` | Shopify OAuth (via `set_sy`) | Custom-app credentials |
| `CLIENT_SECRET` | Shopify OAuth (via `set_sy`) | Custom-app credentials |
| `PPA_SHEET_ID` | `PUD.decide` (reads `PP SY LIST`), `main.py` write, `fetch_product_id_new.py` write | The "PPA sheet" with multiple tabs |
| `SKU_UPC_ID` | `ProductInfo.fetch_barcode`, `ProductInfo.get_sku_barcode`, `fetch_product_id_new.py` | The UPC sheet |
| `MASTER_DATA_ID` | `ProductInfo.get_metachart`, price lookups | Size chart + XL flag + prices |
| `RETURN_ID` | `return_product.py` (reads daily worksheet, writes link in column R) | Master Grid of Return |
| `NE_First_Choice_ID` | `set_inventory_metafield` for `fixed` / `sale_stock` | Shopify location ID |
| `Bali_Stock_ID` | `set_inventory_metafield` for `fixed` / `sale_stock` | Shopify location ID |
| `NE_Sample_ID` | `set_inventory_metafield` for `sample` | Shopify location ID |
| `Bali_To_Produce_ID` | `set_inventory_metafield` for `unfix` / `o4` | Shopify location ID |

Shopify OAuth scopes the access token must have: `read_products`, `write_products`, `read_inventory`, `write_inventory`, `read_publications`, `write_publications`, `read_metaobjects`, `write_metaobjects`.

---

## 2. Google Sheets

### 2.1 PPA Sheet (`PPA_SHEET_ID`)

The primary sheet. Multiple tabs, all read by the pipeline.

#### 2.1.1 `PP SY LIST` — create vs update lookup

- **Used by:** `PUD.decide` (read), `main.py` (write new rows after a successful create)
- **Header row:** row 1 (data starts row 2)
- **Required columns** (used as filter or write target):
  - `Style` — substring match against `STYLE` param (case-insensitive)
  - `Color` — substring match against `COLOR` param (case-insensitive)
  - `Product ID` — Shopify numeric ID; `main.py` writes this after a successful create
  - `Page Status` — must contain `"DRAFT"` for the pipeline to act; anything else is skipped
  - `FP/DC` — exact match (`"FP"` or `"DC"`)
- **`main.py` writes** new rows starting at column A of the first row where `Style` is empty: `[STYLE, COLOR, product_id, "DRAFT", FP_DC]`. Column order must match the sheet's column order.
- ⚠️ **`Page Status` is a stale snapshot.** It's only refreshed by running `fetch_product_id_new.py`. Between snapshots, a Shopify product can drift DRAFT → ACTIVE without the sheet knowing. If `PP SY LIST` says DRAFT but Shopify says ACTIVE, the update will overwrite a live product.
- ⚠️ `PUD.decide` uses `str.contains` (substring + regex). If two styles share a prefix (`"EMORY TIPPED"` vs `"EMORY TIPPED L/S"`), the lookup may grab the wrong row. Keep style names disambiguated, or change the matcher to exact equality.

#### 2.1.2 `NE STOCK` — NE warehouse stock + SKUs (per size)

- **Used by:** `ProductInfo.get_NE_qty` (returns `(qty, skus)` per size)
- **Required columns:**
  - `style` — substring filter against `self.style`
  - `color` — substring filter against `self.color`
  - `style_code` — used to build SKU stem: `<style_code>-<color>-<size>`
  - `X/S`, `S/M`, `M/L`, `X/L` — integer stock qty per size
- **Behavior:**
  - Returns `qty_ne = [X/S, S/M, M/L, X/L]` and `skus = ["<stem>-X/S", "<stem>-S/M", "<stem>-M/L", "<stem>-X/L"]`
  - If the filter yields **no rows**, returns `([0,0,0,0], ["","","",""])` (short-circuit; no crash).
- ⚠️ **The SKU returned is constructed from `style_code` + `color`, not read from a separate SKU column.** If `style_code` is mistyped or `color` is in a different format than the UPC list expects, `fetch_barcode` will fail to find a match → empty barcode.

#### 2.1.3 `BALI STOCK` — Bali warehouse stock + SKUs

- **Used by:** `ProductInfo.get_BALI_qty` (returns `(qty, skus)` per size)
- **Same columns as `NE STOCK`**, but:
  - **`X/L` is hardcoded to 0** in the return — Bali doesn't carry X/L sizes (by design)
  - Empty match → `([0,0,0,0], ["","","",""])`
- Used as a per-size fallback when `NE STOCK`'s SKU is blank for that size:
  ```python
  skus_chosen[i] = skus_ne[i] if str(skus_ne[i]).strip() else skus_ba[i]
  ```

#### 2.1.4 `NE SAMPLE STOCK` — sample inventory

- **Used by:** `ProductInfo.get_sample_qty` (returns a 1-element list)
- Callers must do `qty_sample[0]` before passing to `set_inventory_metafield`.

#### 2.1.5 `Color list` — brand color → generic color mapping

- **Used by:** `Setup/generic_color_generator.py`
- Brand color (e.g. `"Ventana Blue"`) → generic family (`"Blue"`, `"Pink"`, etc.) for SEO + tag generation.
- **Side-effect:** if a brand color is not present, the generator calls GPT to propose one and **writes the new entry back to the sheet** for next time. This is the only undocumented sheet write that happens during a `create_*` call.

### 2.2 SKU / UPC Sheet (`SKU_UPC_ID`)

- **Used by:** `ProductInfo.get_sku_barcode` (default SKU + barcode), `ProductInfo.fetch_barcode` (lookup by SKU)
- **Two tabs:**
  - `PRODUCTION UPC LIST` — primary lookup for both default barcodes and `fetch_barcode`
  - `SAMPLE UPC LIST` — used by `get_sku_barcode` when `sample=True`
- **Required columns:**
  - `Lineitem sku` — the SKU string (must exactly match the SKU constructed in NE/BALI STOCK for `fetch_barcode` to find it)
  - `UPC Barcode` — the barcode value posted to Shopify's variant `barcode` field
- `fetch_barcode` normalizes SKUs (`.strip().upper()`) before lookup, so case + whitespace are tolerated.
- ⚠️ If a SKU isn't in `PRODUCTION UPC LIST`, `fetch_barcode` returns `""` and the variant ships with no barcode. Shopify accepts this silently.

### 2.3 Master Data Sheet (`MASTER_DATA_ID`)

- **Used by:** `ProductInfo.get_metachart` (size chart HTML), price columns, XL flag
- **Required columns** (consulted, not exhaustive):
  - `DEV | XL | (Y/N)` — toggles whether the size chart includes X/L
  - Width / Length per size — populates the size chart cells
  - Various price columns — fallback chain for `P.get_price()`
- The size chart **always renders the master-data sizes**, not the filtered keep-sizes, by design (the chart is a reference, not a stock listing).

### 2.4 Master Grid of Return (`RETURN_ID`)

- **Used by:** `return_product.py` (read daily worksheet, write link to column R)
- **Worksheet name:** today's date formatted as `"%d %B, %Y"` (e.g. `"21 May, 2026"`). Generated from `date.today()`.
- **Header row:** row 6 (data starts row 7)
- **Required columns:**
  - `Style`, `Color` — passed to `PUD.decide`
  - `Added to full price`, `Added to sale` — values `"x"` (case-insensitive) decide FP vs DC:
    - FP marked, DC blank → `FP_DC="FP"`, `SALE=False` → `U.update_fixed()`
    - DC marked, FP blank → `FP_DC="DC"`, `SALE=True` → `U.update_sale_stock()`
    - Both `x` → log + skip
    - Neither → log + skip
  - Any column with `"ZZ"` in its header — used as an exclusion filter. Rows where any such column equals `"ZZ"` are dropped entirely from the iteration.
  - **Column R** — the destination cell where each row's Shopify admin link is written after a successful update.
- ⚠️ The Master Grid sheet can have **duplicate column headers**; `return_product.py` uses a `_first()` helper to handle that: `_first(x)` returns `x.iloc[0]` if `x` is a Series, else `x`. Don't remove it.
- ⚠️ Column `R` is hardcoded. Verify it's actually the link column in your Master Grid before a run.

---

## 3. Local Excel file — IM Master (`Copy of <season> IM MASTER.xlsx`)

- **Used by:** `ProductInfo.get_weight` (per-variant weight), some price fallbacks
- **Location:** project root (alongside `main.py`)
- **Header row:** see `config/varia.py` for the configured row index
- **Required columns:**
  - `DESCRIPTION` — substring filter against STYLE; also must contain the size code (`S/M`, `M/L`, …) for the per-size weight lookup
  - `WS TAG COLOR` — filter against COLOR
  - `PRE COMPONENT WT (PC WT)` — weight in **kg** (multiplied by 1000 → grams for Shopify)
  - Other columns may be used for full-price fallback
- ⚠️ The script reads the xlsx from `Path(__file__).parent`. If the file isn't synced locally to the user running the script, weight will be `0` / `None` silently.
- ⚠️ Per-season filename change. For `26 Spring` the file is `Copy of S26 IM MASTER.xlsx`. For `26 Fall` it would be `Copy of F26 IM MASTER.xlsx`. Confirm the file exists before a run.

---

## 4. Shopify-side prerequisites

These are configured **inside the Shopify store**, not in a file.

### 4.1 Inventory location IDs

All four must exist in the store and their numeric IDs must be set in `.env`:

| Env var | Used by |
|---|---|
| `NE_First_Choice_ID` | `fixed` + `sale_stock` (NE qty) |
| `Bali_Stock_ID` | `fixed` + `sale_stock` (Bali qty) |
| `NE_Sample_ID` | `sample` (qty 5000 placeholder) |
| `Bali_To_Produce_ID` | `unfix` + `o4` (qty 5000 placeholder) |

Verify each still resolves: `GET /admin/api/2026-01/locations.json`.

### 4.2 Theme templates

The active theme must publish both product templates:

- `default` — used when `template_suffix` resolves to `'default'` (full-price products)
- `sale-item` — used when `template_suffix` resolves to `'sale-item'` (sale products)

`tg.additional_tags` returns a suggested `template_suffix`; if it returns `None`, the fallback is `'sale-item' if SALE else 'default'`. If `sale-item` doesn't exist in the live theme, Shopify accepts the product but falls back to default rendering — meaning sale items won't render with sale styling.

### 4.3 Publication channels

`set_sy.publish_to_all_channels(product_id, sale=...)`:

- `sale=False` → publish to **every** sales channel returned by `publications(first: 20)`.
- `sale=True` → publish to every channel **except Pinterest**.

If you want different channel handling, edit the GraphQL filter in [Setup/set_sy.py](Setup/set_sy.py).

### 4.4 Tax code metafield

- Namespace: `avalara`, key: `taxcode`, value: `PC040100`
- Set at the product level (in the create payload) and per-variant level (after creation, in `set_inventory_metafield`).
- No prerequisite metafield definition needed — Shopify auto-creates on first write.
- ⚠️ Every update re-POSTs the per-variant metafield. Shopify usually dedupes by `(owner_id, namespace, key)`, but if you see duplicate `avalara.taxcode` metafields on a variant in the admin, the dedup isn't holding and the create-or-update should be switched to GraphQL `metafieldsSet`.

---

## 5. Per-row data quality rules

For one row in the Master Grid of Return (or one style targeted by main.py) to produce a clean update, **every dependent lookup must hit a matching row**.

| Lookup | Match keys | Sheet/file | Failure mode |
|---|---|---|---|
| Decide create vs update | `Style` substring, `Color` substring, `FP/DC` exact | `PPA_SHEET_ID` → `PP SY LIST` | No row → `create_new=True, status="DRAFT"` (forced) → create branch |
| NE qty + SKU | `style` substring, `color` substring | `PPA_SHEET_ID` → `NE STOCK` | Empty → `([0,0,0,0], ["","","",""])` |
| Bali qty + SKU | `style` substring, `color` substring | `PPA_SHEET_ID` → `BALI STOCK` | Empty → `([0,0,0,0], ["","","",""])`. Together with NE empty → `keep=[]` → "No stock" skip |
| Barcode by SKU | Exact normalized SKU | `SKU_UPC_ID` → `PRODUCTION UPC LIST` | Missing → barcode = `""` |
| Default SKU + barcode (unfix/sample/o4) | Positional | `SKU_UPC_ID` → `PRODUCTION UPC LIST` / `SAMPLE UPC LIST` | Missing → variant gets empty SKU/barcode |
| Size chart | `Style`, `Color` | `MASTER_DATA_ID` | Empty → blank cells / `-` placeholders rendered |
| Generic color | Brand color → generic | `PPA_SHEET_ID` → `Color list` | Missing → GPT proposes + writes back |
| Weight | STYLE + COLOR + size code | IM Master xlsx | Missing → weight = 0 silently |

**Pre-run rule of thumb:** for each row before pressing play, confirm the `(STYLE, COLOR)` pair appears in:

1. `NE STOCK` and/or `BALI STOCK` (at least one must have non-zero qty for fixed / sale_stock to proceed)
2. `PRODUCTION UPC LIST` with a non-empty `UPC Barcode` for every NE SKU you expect to ship
3. `MASTER_DATA_ID` (for the size chart)
4. `Color list` (or accept that GPT will write a new entry)
5. IM Master xlsx (for weights)
6. `PP SY LIST` if you want it to be an update; absent → create

---

## 6. Per-season tweaks (what changes when starting `S27`, `F26`, …)

| Where | What | Action |
|---|---|---|
| `main.py` | `SEASON = "26 Spring"` constant | Update to new season string |
| Project root | `Copy of S26 IM MASTER.xlsx` | Add the new season's file; remove or archive old one |
| `config/varia.py` | Default `SEASON`, IM header row | Confirm header row didn't shift |
| `MASTER_DATA_ID` data | New season rows | Make sure every style+color this season has rows in master data, with size chart cells populated |
| `PPA_SHEET_ID` → `NE STOCK` / `BALI STOCK` | New season rows + stock counts | Updated by stock team |
| `PPA_SHEET_ID` → `Color list` | New colors | Add manually or let GPT write them on first reference |
| `SKU_UPC_ID` → `PRODUCTION UPC LIST` | New SKUs + barcodes for the season | Critical — empty `UPC Barcode` cells = empty barcodes on Shopify |
| `RETURN_ID` | A daily worksheet matching `date.today().strftime("%d %B, %Y")` must exist before `return_product.py` runs | Ops creates the daily tab |

There's no single `SeasonConfig` object yet — these are scattered. A consolidation would be a useful refactor.

---

## 7. Naming-convention contracts (parser depends on these)

`ProductInfo` parses substrings from `STYLE` and `COLOR` to derive product type, tags, fabric category, etc.

### STYLE string (last-token-first analysis)

- Last token drives **product type**: `V`, `CREW`, `CARDI` / `CARDIGAN`, `HOODIE`, `TOP` (`POLO TOP` → Collar, else Crewneck)
- Substring tokens trigger fabric/style tags: `COTTON`, `MERCER`, `CHUNKY`, `LIGHTWEIGHT`, `CABLE`, `STRIPE`, `MARLED` / `MARL`, `HEATHERED`, `3/4`, `TEE`, `SLEEVELESS`, `HALF SLEEVE`, `ZIP`
- Composition text branches on last token: `COTTON` vs `MERCER` blends differ

### COLOR string

- Multi-color colors are slash-separated, up to 3 colors: `COLOR1/COLOR2/COLOR3`
- Modifier suffixes recognized: `HEATHER`, `STRIPE`, `MARL` — extracted and removed before generic-color lookup
- `Color list` lookup is exact-match (case-insensitive after cleanup) — extra spaces or typos = no generic color = weaker SEO

### FP_DC mapping (driven by production_type or sheet column)

| production_type | FP_DC | SALE |
|---|---|---|
| `unfix`, `fixed` | `FP` | `False` |
| `sale_stock`, `sample`, `o4` | `DC` | `True` |

---

## 8. Pre-flight checklist

Before running:

- [ ] `Setup/.env` has all 11 keys from §1
- [ ] `credentials/dialy-report-automation-e20c53e67542.json` is present and the service account is shared as Editor on the PPA Sheet, SKU/UPC Sheet, Master Data Sheet, and Master Grid of Return
- [ ] Project root has `Copy of <season> IM MASTER.xlsx`
- [ ] `(STYLE, COLOR)` appears in either `NE STOCK` or `BALI STOCK` (for fixed/sale_stock)
- [ ] Every NE SKU expected to ship has a row in `PRODUCTION UPC LIST` with non-empty `UPC Barcode`
- [ ] Brand color is in `Color list` (or you're OK letting GPT write it)
- [ ] Size chart cells in `MASTER_DATA_ID` are populated for the size set you expect
- [ ] IM Master xlsx has rows for `(STYLE, COLOR)` with `PRE COMPONENT WT` filled per size
- [ ] All 4 Shopify location IDs in `.env` still resolve (`GET /locations.json`)
- [ ] Active theme has both `default` and `sale-item` templates
- [ ] (For bulk run) Master Grid of Return has a daily worksheet named `date.today().strftime("%d %B, %Y")`
- [ ] (For bulk run) Column `R` on that worksheet is the link/result column

If all checks pass, the pipeline should run cleanly.
