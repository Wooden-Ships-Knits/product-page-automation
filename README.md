# PPA — Product Page Automation

Creates Wooden Ships product pages on Shopify from internal source-of-truth data (IM Master Excel, PPA Google Sheets, Master Data Sheet, UPC list). One style-color goes in, one fully-built product page comes out — title, SEO, variants, size chart, weights, SKUs, barcodes, tags, prices, and per-location inventory.

For deeper background on inputs and an older redesign sketch, see [PPA_FLOW.md](PPA_FLOW.md) and [PPA_DATA_PREP.md](PPA_DATA_PREP.md). This README documents the **current** active flow in [create_pp.py](create_pp.py) + [fetch_to_product_page.py](fetch_to_product_page.py).

---

## 1. Setup

Python 3.9.6. Install deps:

```bash
pip install -r Lrequirements.txt
```

You also need:

- `Setup/.env` with at least: `CLIENT_ID`, `CLIENT_SECRET` (Shopify), `PPA_SHEET_ID`, `PPA_ID`, `MASTER_DATA_ID`, and the Shopify location IDs `NE_First_Choice_ID`, `NE_Sample_ID`, `Bali_Stock_ID`, `Bali_To_Produce_ID`.
- `credentials/dialy-report-automation-e20c53e67542.json` — Google service-account key (already gitignored).
- The current season's `Copy of <S26|F26> IM MASTER.xlsx` in the project root.

`.env`, `credentials/`, and `*.xlsx` are all gitignored.

---

## 2. Project layout

```
PPA/
├── main.py                       Entry point — picks a STYLE/COLOR/SEASON and calls a create_* function
├── create_pp.py                  The 5 create_* product-type entry points + product_post + set_inventory_metafield
├── fetch_to_product_page.py      ProductInfo class — all data fetching/derivation lives here
├── post_update_decision.py       Looks up whether a product already exists (create vs update)
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

All five live in [create_pp.py](create_pp.py). They share the same skeleton — only the `ProductInfo` flags, inventory location, and (now) size filtering differ.

| Type         | `sample` | `sale` | `sas` | Sizes                                  | Inventory location(s)                              |
|--------------|----------|--------|-------|----------------------------------------|----------------------------------------------------|
| `unfix`      | F        | F      | F     | Full IM master template (4 sizes)      | `Bali_To_Produce_ID` (placeholder qty 5000)        |
| `fixed`      | F        | F      | F     | **Only sizes with NE+Bali stock > 0**  | `NE_First_Choice_ID` + `Bali_Stock_ID` (real qty)  |
| `sample`     | T        | T      | F     | S/M only (filtered in `get_weight()`)  | `NE_Sample_ID` (placeholder qty 5000)              |
| `sale_stock` | F        | T      | F     | **Only sizes with NE+Bali stock > 0**  | `NE_First_Choice_ID` + `Bali_Stock_ID` (real qty)  |
| `o4`         | F        | T      | T     | Full IM master template (4 sizes)      | `Bali_To_Produce_ID` (placeholder qty 5000)        |

The `sample` / `sale` / `sas` flags propagate into pricing, tags, SEO copy, body description, and SKU sheet choice via `ProductInfo`.

---

## 4. End-to-end flow

Triggered from [main.py](main.py) — it sets `STYLE`, `COLOR`, `SEASON` and calls one of `create_unfix` / `create_fixed` / `create_sample` / `create_sale_stock` / `create_o4`.

```
main.py
   │
   ▼
create_<type>(STYLE, COLOR, SEASON)              ← create_pp.py
   │
   ├── P = ProductInfo(STYLE, COLOR, SEASON, ...) ← fetch_to_product_page.py
   │
   ├── [fixed / sale_stock only]
   │     qty_ne = P.get_NE_qty()                  ← reads NE STOCK sheet
   │     qty_ba = P.get_BALI_qty()                ← reads BALI STOCK sheet
   │     combined = qty_ne + qty_ba (per size)
   │     keep = indices where combined > 0
   │     if not keep:  skip product (no stock)
   │     filter qty_ne / qty_ba by keep
   │
   ├── product_data = product_post(STYLE, COLOR, SEASON, P, keep=...)
   │     │
   │     ├── P.title_and_desc()        title, sale title, body HTML, thread composition
   │     ├── P.get_SEL()               SEO page title, meta description, handle/url
   │     ├── P.get_weight()            sizes + per-variant weight (from IM Master xlsx)
   │     ├── P.get_sku_barcode()       SKUs + UPC barcodes (from PRODUCTION/SAMPLE UPC LIST)
   │     ├── P.get_metachart()         size chart HTML (from MASTER_DATA sheet)
   │     ├── P.get_tags()              tag string (per-type tags + color + dated tag)
   │     ├── P.get_type()              product_type derived from STYLE name
   │     ├── P.get_price()             full_price + sale price (with fallback chain)
   │     ├── [if keep]                 filter sizes/weights/skus/barcodes by keep
   │     └── assemble variants + options + Shopify product payload
   │
   ├── POST /admin/api/2026-01/products.json     ← creates the draft product
   │
   ├── set_sy.publish_to_all_channels(product_id) ← assigns to every sales channel (GraphQL)
   │
   └── set_inventory_metafield(response, type, qty_ne=, qty_ba=)
         │
         ├── for each variant:
         │     ├── [fixed/sale_stock] POST inventory to NE_First_Choice_ID with qty_ne[i]
         │     │                       POST inventory to Bali_Stock_ID with qty_ba[i]
         │     ├── [unfix/o4]         POST inventory 5000 to Bali_To_Produce_ID
         │     ├── [sample]           POST inventory 5000 to NE_Sample_ID
         │     └── POST avalara taxcode metafield on the variant
         └── (no return — fire and forget)
```

### Key derived fields

- **Sizes** are X/S, S/M, M/L, X/L. The `SIZE_RANGE` constant maps each to its body-size label (e.g. `S/M → (6-8)`), used for the Shopify variant option text.
- **Size chart**: comes from `MASTER_DATA_ID`. `DEV | XL | (Y/N)` flag toggles whether X/L is included. The chart currently always renders **all sizes from master data**, even when stock-based filtering drops variants — by design (the chart is a reference, not a stock listing).
- **Generic color**: looked up in the `Color list` tab of the PPA sheet. If absent, GPT proposes one and writes it back to the sheet for next time.
- **Prices** use a cascading fallback: `PB ADJUSTED ...` → `LATEST ...` → `IM PRICE`.

---

## 5. Data sources

| Source                                  | Used for                                              |
|-----------------------------------------|-------------------------------------------------------|
| `Copy of <season> IM MASTER.xlsx`       | Per-size weights, size labels, IM price               |
| Master Data sheet (`MASTER_DATA_ID`)    | Size chart, XL flag, printed flag, price columns      |
| PPA sheet (`PPA_SHEET_ID`)              | Color list (generic colors), NE STOCK, BALI STOCK, NE SAMPLE STOCK, PP SY LIST |
| UPC sheet (`PPA_ID`)                    | `PRODUCTION UPC LIST` / `SAMPLE UPC LIST` (SKUs + barcodes) |
| Shopify Admin API (`2026-01`)           | Product creation, inventory, metafields, publishing   |

Sheet reads go through `Setup.setup._get_sheet_values` which caches by `(sheet_id, worksheet, range)` for the life of the process. Excel reads are similarly cached. So inside one run the same sheet is fetched once.

---

## 6. Inventory & location handling

The recent change (May 2026) split this into two cases:

**Real-inventory case (`fixed`, `sale_stock`)**

- Pulls actual qtys from `NE STOCK` and `BALI STOCK` tabs.
- Filters out sizes where combined qty = 0 — those variants are never created on Shopify.
- Posts the **real** per-warehouse qty to each location: NE qty → `NE_First_Choice_ID`, Bali qty → `Bali_Stock_ID`.
- If every size is zero, the product is skipped entirely with a console message.

**Placeholder case (`unfix`, `sample`, `o4`)**

- All 4 sizes (or just S/M for `sample`) always created.
- Inventory set to a flat `5000` at a single location, signalling "to-be-produced" supply.

> **Order assumption**: `get_NE_qty`, `get_BALI_qty`, `get_weight`, `get_sku_barcode` all return arrays in **X/S → S/M → M/L → X/L** order. If a source sheet is sorted differently, fix it at the source — the code trusts this order and the filter uses positional indices.

---

## 7. Running

```bash
python main.py
```

Edit the constants at the top of `main.py`:

```python
STYLE  = "Maura Marled Chunky Top Cotton".upper()
COLOR  = "Ventana Blue/Almond Butter Marl".upper()
SEASON = "26 Spring"
```

Then change the line at the bottom to whichever `create_*` you want to run. Right now `main.py` is wired for single-product manual runs; bulk runs over a season tab are the next step.

---

## 8. Known caveats

- **Error handling is permissive.** `create_*` functions wrap `ProductInfo` construction in `try/except` that only `print`s — if it fails, the function still tries to POST `product_data`, which will `NameError`. Don't catch this unless you're ready to rethink the error model end-to-end.
- **Shopify variant order in the response is trusted** to match creation order for the per-variant inventory loop. Normally true; if you ever see inventory landing on the wrong size, that's the first thing to check.
- **`get_BALI_qty` always returns 0 for X/L** (intentional — Bali doesn't carry X/L). A `fixed` product with NE-only X/L stock will correctly post 0 to Bali for that variant.
- **`post_update_decision.py` is wired but not yet integrated** into the create flow. The intended behaviour is: if the style-color already exists with `FP/DC = DC`, update instead of recreate.
