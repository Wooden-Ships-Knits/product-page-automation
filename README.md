# PPA — Product Page Automation

Creates and updates Wooden Ships product pages on Shopify from internal source-of-truth data (IM Master Excel, PPA Google Sheets, Master Data Sheet, UPC list). One style-color goes in, one fully-built (or fully-updated) product page comes out — title, SEO, variants, size chart, weights, SKUs, barcodes, tags, prices, and per-location inventory.

For deeper background on inputs and the original redesign sketch, see [PPA_FLOW.md](PPA_FLOW.md) and [PPA_DATA_PREP.md](PPA_DATA_PREP.md). This README documents the **current** active flow across [create_pp.py](create_pp.py), [update_pp.py](update_pp.py), [post_update_decision.py](post_update_decision.py), [return_product.py](return_product.py), and [fetch_to_product_page.py](fetch_to_product_page.py).

---

## 1. Setup

Python 3.9.6. Install deps:

```bash
pip install -r Lrequirements.txt
```

You also need:

- `Setup/.env` with at least: `CLIENT_ID`, `CLIENT_SECRET` (Shopify), `PPA_SHEET_ID`, `PPA_ID`, `MASTER_DATA_ID`, `RETURN_ID`, and the Shopify location IDs `NE_First_Choice_ID`, `NE_Sample_ID`, `Bali_Stock_ID`, `Bali_To_Produce_ID`.
- `credentials/dialy-report-automation-e20c53e67542.json` — Google service-account key (already gitignored).
- The current season's `Copy of <S26|F26> IM MASTER.xlsx` in the project root.

`.env`, `credentials/`, and `*.xlsx` are all gitignored.

---

## 2. Project layout

```
PPA/
├── main.py                       Manual single-style entry — picks create vs update via PUD.decide
├── return_product.py             Bulk entry — iterates the Master Grid of Return sheet and updates
├── create_pp.py                  CreatePP class — 5 create_* product-type methods + product_post + set_inventory_metafield
├── update_pp.py                  UpdatePP class — 5 update_* methods mirroring create_pp (PUT instead of POST)
├── post_update_decision.py       decide() — looks up PP SY LIST to choose create vs update + returns product_id/status
├── fetch_to_product_page.py      ProductInfo class — all data fetching/derivation lives here
├── pp_status.py                  Scratch / WIP (currently just imports)
├── deletion_products.py          One-off product cleanup
├── config/varia.py               Constants (IM header row, default season)
├── Setup/
│   ├── setup.py                  Google Sheets client + caching, Shopify headers
│   ├── set_sy.py                 Shopify auth, product POST helper, publish_to_all_channels, collections
│   ├── fetch_product_id_new.py   Snapshot existing Shopify products into the PPA sheet
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
| `sample`     | T        | T      | F     | S/M only (filtered in `get_weight()`)  | `NE_Sample_ID` (placeholder qty 5000)              |
| `sale_stock` | F        | T      | F     | **Only sizes with NE+Bali stock > 0**  | `NE_First_Choice_ID` + `Bali_Stock_ID` (real qty)  |
| `o4`         | F        | T      | T     | Full IM master template (4 sizes)      | `Bali_To_Produce_ID` (placeholder qty 5000)        |

The `sample` / `sale` / `sas` flags propagate into pricing, tags, SEO copy, body description, and SKU sheet choice via `ProductInfo`.

---

## 4. Create vs update — how the decision is made

Both [main.py](main.py) and [return_product.py](return_product.py) consult [post_update_decision.py](post_update_decision.py) `decide(STYLE, COLOR, FP_DC)` before doing anything:

- Reads the `PP SY LIST` tab of the PPA sheet.
- Filters rows whose `Style` and `Color` match (case-insensitive) and whose `FP/DC` column equals `"FP"` or `"DC"`.
- If **no match** → `create_new=True`; caller routes to `CreatePP`.
- If a match exists → `create_new=False`, returns the existing `Product ID` and `Page Status` (e.g. `DRAFT` / `ACTIVE`); caller routes to `UpdatePP`.

`FP_DC` mapping (set by the caller):

- `fixed`, `unfix` → `"FP"` (full price product line) → `SALE=False`
- `sale_stock`, `sample`, `o4` → `"DC"` (discounted / sale line) → `SALE=True`

The caller also sets a `SALE` boolean alongside `FP_DC` and passes it into both `CreatePP(STYLE, COLOR, SEASON, SALE)` and `UpdatePP(STYLE, COLOR, SEASON, PRODUCT_ID, SALE)`. This boolean drives:

- `template_suffix` selection in `product_post` — `'sale-item'` when `SALE=True`, `'default'` when `SALE=False` (only used as fallback when `tags_generator.additional_tags` doesn't return its own suffix).
- The `sale=` kwarg passed to `set_sy.publish_to_all_channels(product_id, sale=...)` — `sale=True` excludes Pinterest, `sale=False` includes all channels.

**The current rule is to only act on `DRAFT` products.** `ACTIVE` products are skipped so we never overwrite a live page. This is enforced in both `main.py` and `return_product.py`.

---

## 5. End-to-end flow

### 5a. Create flow

```
main.py / return_product.py
   │
   ▼
PUD.decide(STYLE, COLOR, FP_DC)  →  create_new=True  →  CreatePP.create_<type>()
   │
   ├── P = ProductInfo(STYLE, COLOR, SEASON, sample=..., sale=..., sas=...)
   │
   ├── [fixed / sale_stock only]
   │     qty_ne = P.get_NE_qty()                  ← reads NE STOCK sheet
   │     qty_ba = P.get_BALI_qty()                ← reads BALI STOCK sheet
   │     combined = qty_ne + qty_ba (per size)
   │     keep = indices where combined > 0
   │     if not keep:  skip product (no stock)
   │     filter qty_ne / qty_ba by keep
   │
   ├── product_data = self.product_post(P, keep=..., qty=...)
   │     │
   │     ├── P.title_and_desc()        title, sale title, body HTML, thread composition
   │     ├── P.get_SEL()               SEO page title, meta description, handle/url
   │     ├── P.get_weight()            sizes + per-variant weight (from IM Master xlsx)
   │     ├── P.get_sku_barcode()       SKUs + UPC barcodes (from PRODUCTION/SAMPLE UPC LIST)
   │     ├── P.get_metachart()         size chart HTML (from MASTER_DATA sheet)
   │     ├── P.get_tags()              base tag string (per-type tags + color + dated tag)
   │     ├── tg.additional_tags(...)   appends qty/size-based tags, returns (tags, template_suffix)
   │     ├── P.get_type()              product_type derived from STYLE name
   │     ├── P.get_price()             full_price + sale price (with fallback chain)
   │     ├── [if keep]                 filter sizes/weights/skus/barcodes by keep
   │     └── assemble variants + options + Shopify product payload
   │
   ├── POST /admin/api/2026-01/products.json     ← creates the draft product
   │     └── on non-201 / no-stock / exception:  return (None, None)
   │
   ├── set_sy.publish_to_all_channels(product_id, sale=self.sale) ← Pinterest is excluded when sale=True
   │
   ├── set_inventory_metafield(response, type, qty_ne=, qty_ba=)
   │     │
   │     ├── for each variant:
   │     │     ├── [fixed/sale_stock] POST inventory to NE_First_Choice_ID with qty_ne[i]
   │     │     │                       POST inventory to Bali_Stock_ID with qty_ba[i]
   │     │     ├── [unfix/o4]         POST inventory 5000 to Bali_To_Produce_ID
   │     │     ├── [sample]           POST inventory 5000 to NE_Sample_ID
   │     │     └── POST avalara taxcode metafield on the variant
   │     └── (no return — fire and forget)
   │
   └── return (link, product_id)   ← link is the Shopify admin URL; caller can append to PP SY LIST
```

### 5b. Update flow

Mirrors create, except the product already exists. `UpdatePP` is constructed with the existing `PRODUCT_ID` returned by `PUD.decide`.

```
PUD.decide(STYLE, COLOR, FP_DC)  →  create_new=False  →  UpdatePP.update_<type>()
   │
   ├── P = ProductInfo(STYLE, COLOR, SEASON, sample=..., sale=..., sas=...)
   │
   ├── [fixed / sale_stock only]   stock filtering, same as create
   │
   ├── GET /admin/api/2024-01/products/{id}.json
   │     └── build sku_to_id = {variant.sku: variant.id}
   │
   ├── variants, options, tags, template_suffix = self.product_post(self.COLOR, P, keep=..., qty=...)
   │
   ├── for each new variant:
   │       if v["sku"] in sku_to_id: v["id"] = sku_to_id[v["sku"]]   ← keeps Shopify treating it as an update
   │
   ├── PUT /admin/api/2024-01/products/{id}.json
   │     payload = {"product": {"id": ..., "variants": [...], "options": [...], "tags": ..., "template_suffix": ...}}
   │
   ├── set_inventory_metafield(response, type, qty_ne=, qty_ba=)
   │     (same per-variant inventory + tax metafield posting as create;
   │      for `sample`, qty_sample[0] is extracted before passing — qty_sample is a 1-element list)
   │
   └── return link   ← Shopify admin URL built from self.PRODUCT_ID; caller can log to a sheet
```

Shopify's PUT semantics handle the reconciliation:

- Variant **with** `id` (SKU matched an existing one) → update in place.
- Variant **without** `id` (new SKU) → create.
- Existing variant **omitted** from the array → deleted.

Status, title, description, images, tags, and any other field not included in the PUT body are left untouched, so a `DRAFT` product stays a `DRAFT`.

### Key derived fields

- **Sizes** are X/S, S/M, M/L, X/L. The `SIZE_RANGE` constant maps each to its body-size label (e.g. `S/M → (6-8)`), used for the Shopify variant option text.
- **Size chart**: comes from `MASTER_DATA_ID`. `DEV | XL | (Y/N)` flag toggles whether X/L is included. The chart currently always renders **all sizes from master data**, even when stock-based filtering drops variants — by design (the chart is a reference, not a stock listing).
- **Generic color**: looked up in the `Color list` tab of the PPA sheet. If absent, GPT proposes one and writes it back to the sheet for next time.
- **Prices** use a cascading fallback: `PB ADJUSTED ...` → `LATEST ...` → `IM PRICE`.

---

## 6. Data sources

| Source                                  | Used for                                              |
|-----------------------------------------|-------------------------------------------------------|
| `Copy of <season> IM MASTER.xlsx`       | Per-size weights, size labels, IM price               |
| Master Data sheet (`MASTER_DATA_ID`)    | Size chart, XL flag, printed flag, price columns      |
| PPA sheet (`PPA_SHEET_ID`)              | `Color list` (generic colors), `NE STOCK`, `BALI STOCK`, `NE SAMPLE STOCK`, `PP SY LIST` (the create-vs-update lookup) |
| UPC sheet (`PPA_ID`)                    | `PRODUCTION UPC LIST` / `SAMPLE UPC LIST` (SKUs + barcodes) |
| Master Grid of Return (`RETURN_ID`)     | Daily worksheet driving `return_product.py` (which styles to update today, FP vs sale flag) |
| Shopify Admin API (`2024-01` + `2026-01`) | Product create/update, inventory, metafields, publishing |

Sheet reads go through `Setup.setup._get_sheet_values` which caches by `(sheet_id, worksheet, range)` for the life of the process. Excel reads are similarly cached. So inside one run the same sheet is fetched once.

---

## 7. Inventory & location handling

Split into two cases:

**Real-inventory case (`fixed`, `sale_stock`)**

- Pulls actual qtys from `NE STOCK` and `BALI STOCK` tabs.
- Filters out sizes where combined qty = 0 — those variants are never created on Shopify (and on update, are omitted from the PUT so Shopify deletes them).
- Posts the **real** per-warehouse qty to each location: NE qty → `NE_First_Choice_ID`, Bali qty → `Bali_Stock_ID`.
- If every size is zero, the product is skipped entirely with a console message.

**Placeholder case (`unfix`, `sample`, `o4`)**

- All 4 sizes (or just S/M for `sample`) always created.
- Inventory set to a flat `5000` at a single location, signalling "to-be-produced" supply.

> **Order assumption**: `get_NE_qty`, `get_BALI_qty`, `get_weight`, `get_sku_barcode` all return arrays in **X/S → S/M → M/L → X/L** order. If a source sheet is sorted differently, fix it at the source — the code trusts this order and the filter uses positional indices.

---

## 8. Running

### Single style, manual (`main.py`)

Edit the constants at the top of `main.py`:

```python
STYLE  = "EMORY TIPPED L/S TOP COTTON".upper()
COLOR  = "Ventana Blue/Twilight Sky".upper()
SEASON = "26 Spring"
production_type = "fixed"   # one of: unfix, fixed, sample, sale_stock, o4
```

Then run:

```bash
python main.py
```

`main.py` will:

1. Map `production_type` → `FP_DC` and `SALE` (FP / `SALE=False` for unfix/fixed, DC / `SALE=True` otherwise).
2. Call `PUD.decide(STYLE, COLOR, FP_DC)`.
3. If `status == DRAFT`: route to `CreatePP(STYLE, COLOR, SEASON, SALE)` (new) or `UpdatePP(STYLE, COLOR, SEASON, product_id, SALE)` (existing).
4. On successful create (`link is not None`), append `[COLOR, STYLE, product_id, "DRAFT", FP_DC]` to the first empty `Style` row in the `PP SY LIST` tab via `sheet.values().update(...)`. The starting row is detected by reading the sheet, filtering rows where `Style` is empty after `fillna('').str.strip()`, and taking `df.index[0] + 2` (header offset). The write target is hardcoded to column `R`.
5. The sheet write only fires if at least one product was actually created. Updates (the `create_new == False` path) do **not** append to `PP SY LIST` — that row is presumed already present from the original create.
6. If `status != DRAFT`, print "not found or an active pp. skipping" and exit without writing.

### Bulk, sheet-driven (`return_product.py`)

Reads the Master Grid of Return sheet's daily worksheet (`"21 May, 2026"` style, generated from `date.today()`), filters out rows flagged `ZZ`, and iterates each Style/Color:

- Reads `Added to full price` and `Added to sale` columns. The one marked `x` decides FP vs DC and `SALE` (FP → `SALE=False`, DC → `SALE=True`). Both `x` or neither → log and `continue` to the next row.
- Calls `PUD.decide` to find the existing product page.
- If `create_new == True`: prints "no product page found, create new one." and moves on (no creation from this entry point — creates are done via `main.py`).
- If the product is `DRAFT`:
  - `FP_DC == "FP"` → `link = U.update_fixed()`
  - `FP_DC == "DC"` → `link = U.update_sale_stock()`
  - Then writes that `link` back to the Master Grid row's column `R` via `sheet.values().update(spreadsheetId=RETURN_ID, range="'<worksheet>'!R<sheet_row>", ...)`.
- Active products are logged with "this is an active product, retracting..." and skipped.

```bash
python return_product.py
```

Row→sheet mapping: `iterrows()` yields the DataFrame index `idx`; the actual sheet row is `idx + 7` because `values[5]` is the header (sheet row 6) and `values[6:]` starts at row 7. Filtering preserves the original index, so this offset stays correct even after the `ZZ` filter.

The whole loop is wrapped in `try/except: traceback.print_exc()` so one bad row doesn't kill the run — but it also means errors are swallowed; check console output.

---

## 9. Known caveats

- **Hardcoded write column `R`.** Both `main.py` (PP SY LIST writeback) and `return_product.py` (Master Grid writeback) write starting at column `R`. Verify `R` is actually the first column of the target field range in each sheet — if columns shift, change the constant.
- **`main.py` writes to PP SY LIST only on successful **create**.** The update path (`create_new == False`) doesn't append — there's no row to add because PP SY LIST is presumed to already contain that style. If you want updates logged elsewhere (e.g. a "last touched" column), add the writeback inside the update branch.
- **`CreatePP.create_*` returns `(None, None)` on any failure** (no stock, non-201, exception). Callers must check `if link is not None:` before using the values. `UpdatePP.update_*` returns `None` on no-stock skip but still returns a built `link` after an exception — inconsistent with create, so don't assume a non-None update return means success without also looking at console.
- **Error handling swallows failures.** Both `CreatePP.create_*` and `UpdatePP.update_*` wrap their full body in `try/except Exception: traceback.print_exc()`. A failure will print a stack trace but the loop in `return_product.py` (and `main.py` for a single run) keeps going. Check console output — silent success is not the same as actual success.
- **Update-side relies on stable SKUs.** The PUT reconciliation in [update_pp.py](update_pp.py) matches existing variants by SKU. If a SKU changes for a size+color that already exists, Shopify will see "delete old + create new with same option combo" and reject with "Option values are not unique" (422). Keep SKUs stable, or extend the matching to use `option1+option2`.
- **API version is mixed.** `update_pp.py` uses `2024-01` for product calls and `2026-01` for inventory/metafields. `create_pp.py` uses `2026-01`. Functional but inconsistent.
- **`set_inventory_metafield` has a silent catch-all.** Any `production_type` not in `('fixed', 'sale_stock', 'sample')` falls into the `Bali_To_Produce_ID` + 5000 branch. `unfix` and `o4` rely on this. A typoed production_type would also silently route there.
- **`qty_sample` is a 1-element list.** `P.get_sample_qty()` returns a list; callers must use `qty_sample[0]` both for the `tags_generator` call and when passing to `set_inventory_metafield` (otherwise the list itself ends up as the `available` value posted to Shopify).
- **Shopify variant order in the response is trusted** to match creation order (and update order) for the per-variant inventory loop. Normally true; if you ever see inventory landing on the wrong size, that's the first thing to check.
- **`get_BALI_qty` always returns 0 for X/L** (intentional — Bali doesn't carry X/L). A `fixed` product with NE-only X/L stock will correctly post 0 to Bali for that variant.
- **Header-duplication safety in `return_product.py`**: the loop uses a `_first()` helper because the Master Grid of Return sheet can have duplicate column headers — `_first(x)` returns `x.iloc[0]` if `x` is a Series, else `x`. Don't remove unless you've confirmed headers are unique.
