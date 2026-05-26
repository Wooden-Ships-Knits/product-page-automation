# PPA — Product Page Automation: Flow & Branch Summary

What the current pipeline does, end-to-end. Companion to [PPA_DATA_PREP.md](PPA_DATA_PREP.md) (inputs) and [README.md](README.md) (setup + quick reference).

The big insight: there are **two entry points** and **two operations** (create / update), but the per-production-type logic is consolidated into one `product_post()` helper in each of [create_pp.py](create_pp.py) and [update_pp.py](update_pp.py). The five production types share the same skeleton — they differ only in `ProductInfo` flags, inventory location, and (for `fixed` / `sale_stock`) stock-based filtering.

---

## 1. Two entry points

### 1.1 Single-style manual run ([main.py](main.py))

Edit constants at top, run `python main.py`.

```mermaid
flowchart TD
    A[main.py constants:<br/>STYLE, COLOR, SEASON, production_type] --> B[Derive FP_DC + SALE]
    B --> C[PUD.decide STYLE COLOR FP_DC<br/>returns create_new, product_id, status, description]
    C --> D{status == DRAFT?}
    D -- no --> E[skip, print 'active or not found']
    D -- yes --> F{create_new?}
    F -- True --> G[CreatePP STYLE COLOR SEASON SALE description<br/>.create_type]
    F -- False --> H[UpdatePP STYLE COLOR SEASON product_id SALE description<br/>.update_type]
    G --> I{link != None?}
    I -- yes --> J[append to lists]
    H --> K[link captured but not appended]
    J --> L{styles non-empty?}
    K --> L
    L -- yes --> M[write new_rows to PP SY LIST<br/>at first empty Style row, column A]
    L -- no --> N[exit]
```

### 1.2 Bulk sheet-driven run ([return_product.py](return_product.py))

Reads today's worksheet from Master Grid of Return, iterates rows. Now handles **both** create and update.

```mermaid
flowchart TD
    A[worksheet_name = today date<br/>strftime '%B %d, %Y' e.g. 'May 25, 2026'] --> B[GET Master Grid tab]
    B --> C[Drop rows with ZZ in any ZZ-column<br/>then dedupe by Style, Color]
    C --> D{For each remaining row}
    D --> E[Read 'Added to full price' / 'Added to sale']
    E --> F{which x mark?}
    F -- both/neither --> D
    F -- FP --> G[FP_DC=FP, SALE=False]
    F -- DC --> H[FP_DC=DC, SALE=True]
    G --> I[PUD.decide]
    H --> I
    I --> J{create_new?}
    J -- True --> K[C.create_fixed FP or C.create_sale_stock DC]
    K --> K2[Write link to col R + accumulate for PP SY LIST writeback]
    J -- False --> L{status == DRAFT?}
    L -- no --> M[print 'active — skip']
    L -- yes --> N[U.update_fixed or U.update_sale_stock]
    N --> O[Write link back to col R of source row]
    O --> D
    K2 --> D
    M --> D
    D -.after loop.-> P{any creates?}
    P -- yes --> Q[append rows to PP SY LIST col A]
    P -- no --> R[done]
```

`return_product.py` now creates **and** updates. New products go via `create_fixed` / `create_sale_stock` only — the placeholder types (`unfix`, `sample`, `o4`) are still single-style-only via `main.py`.

> ⚠️ **`return_product.py` is currently broken** against the post-`description` signatures: it unpacks `create_new, PRODUCT_ID, status` from `PUD.decide` (now 4 returns) and constructs `CreatePP` / `UpdatePP` without the new `DESCRIPTION` arg. The outer `try/except` swallows the `ValueError`. See [README §8](README.md#8-running) for the fix.

---

## 2. The decision: create vs update ([post_update_decision.py](post_update_decision.py))

```python
def decide(STYLE, COLOR, FP_DC):
    # reads PP SY LIST tab of PPA sheet
    # 1) per-style description lookup (Color/FP_DC ignored — description is style-level)
    df_desc = df[df["Style"].str.contains(STYLE, case=False, na=False)]
    description = df_desc["Description"].iloc[0] if not df_desc.empty else ""

    # 2) create vs update lookup (all three keys must match)
    df = df[
        df["Style"].str.contains(STYLE, case=False, na=False) &
        df["Color"].str.contains(COLOR, case=False, na=False) &
        (df["FP/DC"] == FP_DC)
    ]
    if df.empty:
        return True, "", "DRAFT", description       # not in sheet → treat as new
    return False, df['Product ID'].iloc[0], df['Page Status'].iloc[0], description
```

| `df.empty` | returned `create_new` | returned `product_id` | returned `status` | Caller behavior |
|---|---|---|---|---|
| True | `True` | `""` | `"DRAFT"` (forced) | run CreatePP |
| False, sheet DRAFT | `False` | `<int>` | `"DRAFT"` | run UpdatePP |
| False, sheet ACTIVE | `False` | `<int>` | `"ACTIVE"` | **skip** (don't overwrite live product) |

`description` is returned in all three cases (`""` if no style-matching row exists). It's injected into the Shopify `body_html` as `<p>{description}</p>` between the sale-disclaimer block and the thread-composition paragraph, on both create and update.

The `"DRAFT"` forced-default means "no row in sheet" is treated identically to "row in sheet with DRAFT status" — both proceed to act on the product (create / update).

---

## 3. The five production types

| Type | `sample` | `sale` | `sas` | Sizes | Inventory location(s) | FP_DC | SALE |
|---|---|---|---|---|---|---|---|
| `unfix` | F | F | F | All 4 (template) | `Bali_To_Produce_ID` qty 5000 | FP | False |
| `fixed` | F | F | F | Only sizes with NE+Bali stock > 0 | `NE_First_Choice_ID` + `Bali_Stock_ID` real qty | FP | False |
| `sample` | T | T | F | S/M only | `NE_Sample_ID` qty from `get_sample_qty()` | DC | True |
| `sale_stock` | F | T | F | Only sizes with NE+Bali stock > 0 | `NE_First_Choice_ID` + `Bali_Stock_ID` real qty | DC | True |
| `o4` | F | T | T | All 4 (template) | `Bali_To_Produce_ID` qty 5000 | DC | True |

`fixed` and `sale_stock` are the only types that read live stock; the other three are placeholders.

---

## 4. The common pipeline

Every `create_*` / `update_*` method runs these conceptual steps in roughly the same order:

| # | Step | Where |
|---|------|-------|
| 1 | Construct `ProductInfo(STYLE, COLOR, SEASON, sample=, sale=, sas=)` | top of each method |
| 2 | *(fixed/sale_stock only)* `qty_ne, skus_ne = P.get_NE_qty()`; `qty_ba, skus_ba = P.get_BALI_qty()` | top of method |
| 3 | *(fixed/sale_stock only)* Build `keep` = indices where `qty_ne + qty_ba > 0`; skip product if `keep == []` | top of method |
| 4 | *(fixed/sale_stock only)* Build `skus_chosen` (NE primary, Bali fallback) and `barcodes_chosen = P.fetch_barcode(skus_chosen)` | top of method |
| 5 | *(update only)* `GET /products/{id}.json` → build `sku_to_id = {sku: id}` map | mid-method |
| 6 | `product_post(P, keep=, qty=, skus=, barcodes=)` builds the Shopify payload (variants, options, tags, template_suffix) | shared helper |
| 7 | *(update only)* Stamp `v["id"] = sku_to_id[v["sku"]]` on each new variant whose SKU exists | mid-method |
| 8 | `POST /products.json` (create) or `PUT /products/{id}.json` (update) | end of method |
| 9 | `_attach_variant_image(product/response)` — extra PUT assigning the first product image as `image_id` for all variants. ID reference only, no file uploads. | after POST/PUT |
| 10 | *(create only)* `set_sy.publish_to_all_channels(product_id, sale=...)` | after POST |
| 11 | `set_inventory_metafield(response, type, qty_ne=, qty_ba=, qty_sample=)` per-variant inventory + Avalara taxcode metafield | end of method |
| 12 | Return `(link, product_id)` (create) or `link` (update). Failures return `(None, None)` / `None`. | end of method |

---

## 5. Create flow ([create_pp.py](create_pp.py))

```
CreatePP(STYLE, COLOR, SEASON, SALE, DESCRIPTION).create_<type>()
   │
   ├── P = ProductInfo(STYLE, COLOR, SEASON, sample=, sale=, sas=)
   │
   ├── [fixed / sale_stock only]
   │     qty_ne, skus_ne = P.get_NE_qty()        ← reads NE STOCK
   │                                                empty → ([0,0,0,0], ["","","",""])
   │     qty_ba, skus_ba = P.get_BALI_qty()      ← reads BALI STOCK (X/L always 0)
   │     combined = qty_ne + qty_ba (per size, _to_int)
   │     keep = indices where combined > 0
   │     if not keep:  return (None, None)        ← skip product, no stock
   │     skus_chosen[i]  = skus_ne[i] if non-blank else skus_ba[i]
   │     barcodes_chosen = P.fetch_barcode(skus_chosen)    ← UPC LIST lookup
   │     filter qty_ne / qty_ba by keep
   │     total_qty = sum(filtered qty_ne + qty_ba)
   │
   ├── product_data = self.product_post(P, keep=, qty=, skus=skus_chosen?, barcodes=barcodes_chosen?)
   │     │
   │     ├── P.title_and_desc()         title, sale title, body HTML, thread composition
   │     ├── P.get_SEL()                SEO page title, meta description, handle
   │     ├── P.get_weight()             sizes + per-variant weight (IM Master xlsx)
   │     ├── P.get_sku_barcode()        default barcodes + default SKUs (UPC LIST)
   │     │                               — used as fallback only
   │     ├── P.get_metachart()          size chart HTML (MASTER_DATA sheet)
   │     ├── P.get_tags()               base tag string (per-type tags + color + dated tag)
   │     ├── tg.additional_tags(tags, sizes, qty) → (tags, template_suffix)
   │     ├── P.get_type()               product_type derived from STYLE name
   │     ├── P.get_price()              full_price + sale price (cascading fallback)
   │     ├── [if keep]                  filter sizes/weights/default_barcodes/default_skus by keep
   │     ├── skus     = skus_kwarg     if provided else default_skus
   │     ├── barcodes = barcodes_kwarg if provided else default_barcodes
   │     └── return assembled Shopify product payload
   │         body_html = sale_desc + f"<p>{self.description}</p>" + thread_comp
   │
   ├── POST /admin/api/2026-01/products.json
   │     └── non-201 → print, return (None, None)
   │
   ├── self._attach_variant_image(product)
   │     PUT /admin/api/2024-01/products/{id}.json with variants=[{id, image_id=first_image_id}, ...]
   │     — assigns the first product image to every variant (no src URL, so no new files in Content > Files)
   │     — silent no-op when product has no images or no variants
   │
   ├── set_sy.publish_to_all_channels(product_id, sale=...)
   │     ├── create_unfix / create_fixed → sale=False (Pinterest INCLUDED)
   │     └── create_sample / create_sale_stock / create_o4 → default sale=True (Pinterest EXCLUDED)
   │
   ├── set_inventory_metafield(response, type, qty_ne=, qty_ba=, qty_sample=)
   │     │
   │     ├── fixed / sale_stock → per-variant POST to NE_First_Choice_ID (qty_ne[i])
   │     │                        and Bali_Stock_ID (qty_ba[i])         ← only these two locations
   │     ├── sample              → per-variant POST to NE_Sample_ID (qty_sample) ← only this location
   │     ├── unfix / o4          → per-variant POST to Bali_To_Produce_ID (qty=5000) ← only this location
   │     └── per-variant POST to Avalara taxcode metafield
```

`create_*` is wrapped in `try / except Exception: traceback.print_exc(); return (None, None)`. All failure paths return `(None, None)`.

---

## 6. Update flow ([update_pp.py](update_pp.py))

Mirrors create, except the product already exists on Shopify and we PUT instead of POST.

```
UpdatePP(STYLE, COLOR, SEASON, PRODUCT_ID, SALE, DESCRIPTION).update_<type>()
   │
   ├── P = ProductInfo(...)
   │
   ├── [fixed / sale_stock only]
   │     same stock filter + skus_chosen + barcodes_chosen as create
   │     (empty match short-circuits to all-zero qty/blank SKUs → "No stock" skip → return None)
   │
   ├── GET /admin/api/2024-01/products/{PRODUCT_ID}.json
   │     └── sku_to_id = {v.sku: v.id for v in existing if v.get("sku")}
   │
   ├── variants, options, tags, template_suffix = self.product_post(self.COLOR, P, keep=, qty=, skus=, barcodes=)
   │
   ├── for v in variants:
   │       if v["sku"] in sku_to_id:
   │           v["id"] = sku_to_id[v["sku"]]      ← Shopify treats as in-place update
   │
   ├── PUT /admin/api/2024-01/products/{PRODUCT_ID}.json
   │     payload = {"product": {
   │         "id":              PRODUCT_ID,
   │         "body_html":       sale_desc + f"<p>{description}</p>" + thread_comp,
   │         "images":          P.get_image(),
   │         "variants":        variants,
   │         "options":         options,
   │         "tags":            tags,
   │         "template_suffix": template_suffix
   │     }}
   │
   ├── self._attach_variant_image(response)
   │     PUT /admin/api/2024-01/products/{id}.json with variants=[{id, image_id=first_image_id}, ...]
   │     — reads the first image from the just-PUT response and stamps it onto every variant
   │     — ID reference only, so no new files appear in Content > Files
   │     — backfills variant→image on products created before this step existed
   │
   ├── set_inventory_metafield(response, type, qty_ne=, qty_ba=, qty_sample=)
   │     — UNLIKE create: posts to ALL FOUR locations per variant, zeroing
   │       out the locations irrelevant to the type. This wipes any stale
   │       stock from a previous type assignment.
   │
   └── return link
```

### Shopify PUT semantics

- Variant **with** `id` → update in place.
- Variant **without** `id` → create.
- Existing variant **omitted** from the new array → deleted.

Fields not included in the PUT body (`status`, `title`, SEO metafields, etc.) are left untouched, so a DRAFT product stays DRAFT with its existing title. `body_html` and `images` **are** included, so the description (from `PP SY LIST.Description`) and the image list (from `Links storage`) are refreshed on every update.

### `set_inventory_metafield` divergence (create vs update)

Create-side posts inventory **only** to the relevant location(s) for the type. Update-side posts to **all four** locations and zeros out the irrelevant ones:

| Type | Create-side posts to | Update-side posts to |
|---|---|---|
| `fixed`, `sale_stock` | `NE_First_Choice_ID`, `Bali_Stock_ID` | All 4 — real qty to NE+Bali, `0` to NE_Sample + Bali_To_Produce |
| `sample` | `NE_Sample_ID` | All 4 — `qty_sample` to NE_Sample, `0` to the other 3 |
| `unfix` / `o4` (default branch) | `Bali_To_Produce_ID` | All 4 — `5000` to Bali_To_Produce, `0` to the other 3 |

Practical effect: changing a product's type via update (e.g. promoting `unfix` → `fixed`) cleanly resets stock at the now-irrelevant locations. Create doesn't need this because there's nothing to reset.

---

## 7. Inventory & SKU/barcode sourcing

Per production type, the variants get sourced from different sheets:

| Type | SKU source | Barcode source | Why |
|---|---|---|---|
| `unfix`, `sample`, `o4` | `PRODUCTION UPC LIST` / `SAMPLE UPC LIST` via `P.get_sku_barcode()` | Same (positional pairing) | Placeholder products — use the canonical UPC list |
| `fixed`, `sale_stock` | NE STOCK (primary), Bali STOCK (fallback) per size | `PRODUCTION UPC LIST` looked up **by SKU** via `P.fetch_barcode(skus_chosen)` | Real-stock products — SKU must reflect what's actually shippable; barcode joined by value, not position |

`fetch_barcode` returns `""` for unknown SKUs and Shopify accepts empty strings. If both `skus_ne[i]` and `skus_ba[i]` are blank for a size that has `qty > 0`, the variant ends up with `sku=""` and `barcode=""` — a data-entry symptom worth investigating.

---

## 8. Key derived fields

- **Sizes**: `X/S`, `S/M`, `M/L`, `X/L`. The `SIZE_RANGE` constant maps each to a body-size label (`S/M → (6-8)`) used for the Shopify variant `option1` text.
- **Size chart**: rendered HTML from `MASTER_DATA_ID`. Shows all sizes regardless of stock filtering — by design (reference, not a stock listing). `DEV | XL | (Y/N)` flag toggles whether X/L is included.
- **Description**: pulled in `PUD.decide()` from the `Description` column of `PP SY LIST` (first row where `Style` substring-matches — Color and FP/DC are ignored, so the description is style-level not variant-level). Injected into `body_html` as `<p>{description}</p>`. Editing the cell and re-running an update will refresh the description on Shopify.
- **Generic color**: looked up in the `Color list` tab of the PPA sheet. If absent, GPT proposes one and writes it back to the sheet (undocumented side-effect during create or update).
- **Price**: `P.get_price()` returns `(full_price, sale_price)` with a cascading fallback: `PB ADJUSTED ...` → `LATEST ...` → `IM PRICE`. For non-sale products, `full_price` returns as `""` and `price` becomes the `full_price` value.
- **Template suffix**: `tg.additional_tags` returns one based on qty bands (e.g. `nearly-gone` when qty ≤ 5); if `None`, fallback is `'sale-item'` when `self.sale=True` else `'default'`.
- **Tags**: base tags from `P.get_tags()` (per-type + color family + dated `Additional <Mon DD YYYY>`), plus appendage from `tg.additional_tags` (qty/size-driven `FILTERBY-*` and `NEARLY GONE` tags).
- **Status**: products are always created `draft` (Shopify status). Updates don't change status — the PUT body omits the `status` field.

---

## 9. Error handling & idempotency

- All `create_*` / `update_*` methods are wrapped in `try / except Exception: traceback.print_exc()`. They never raise; they return `(None, None)` / `None` on failure.
- `main.py` checks `if link is not None:` before appending to its accumulator lists, so a failed create doesn't pollute the PP SY LIST writeback. `return_product.py` does the same for its create branch.
- `return_product.py` writes the link unconditionally inside its update DRAFT branch — if `link is None` (e.g. no stock), it writes `None` to the cell. Guard with `if link:` before the sheet write if that matters.
- **No idempotency on create**: a failed mid-create (e.g. POST succeeded but inventory POST failed) leaves an orphaned Shopify draft. Re-running creates a duplicate. Mitigation: PP SY LIST writeback happens after all sub-calls, so a row not in PP SY LIST is a signal the create didn't complete cleanly.
- **`set_inventory_metafield` reads `data["product"]["variants"]` from the response.** If the POST/PUT failed (response is an error JSON like `{"errors": ...}`), this raises `KeyError`, caught by the outer except — the inventory step is skipped silently. (See the `update_pp.py:277` `KeyError: 'product'` trace people have hit.)

---

## 10. Files involved

| File | Role |
|---|---|
| [main.py](main.py) | Single-style manual entry point — supports all 5 production types |
| [return_product.py](return_product.py) | Bulk entry from Master Grid of Return — creates and updates `fixed` / `sale_stock` only |
| [post_update_decision.py](post_update_decision.py) | `decide()` — PP SY LIST lookup for create-vs-update routing + per-style description |
| [create_pp.py](create_pp.py) | `CreatePP` class — 5 `create_*` methods, `product_post`, `set_inventory_metafield` |
| [update_pp.py](update_pp.py) | `UpdatePP` class — 5 `update_*` methods, `product_post`, `set_inventory_metafield` |
| [fetch_to_product_page.py](fetch_to_product_page.py) | `ProductInfo` class — all data fetching/derivation (stock, SKU, barcode, weight, price, SEO, tags, size chart, images) |
| [Setup/fetch_product_id_new.py](Setup/fetch_product_id_new.py) | One-off: snapshot existing Shopify products into PPA sheet's `PP SY LIST` |
| [Setup/set_sy.py](Setup/set_sy.py) | Shopify auth headers, `publish_to_all_channels` GraphQL mutation, `product_url` constant |
| [Setup/setup.py](Setup/setup.py) | Google Sheets client + cached `_get_sheet_values`, Shopify `HEADERS`, `sheet` |
| [Setup/tags_generator.py](Setup/tags_generator.py) | `generate_tags(STYLE, COLOR)` (base tags) and `additional_tags(tags, sizes, qty)` — appends qty/size-based tags, returns `(tags, template_suffix)` |
| [Setup/generic_color_generator.py](Setup/generic_color_generator.py) | Brand color → generic color mapping (with GPT fallback that writes back to sheet) |
| [config/varia.py](config/varia.py) | Constants (`IM_header = 56`, default `season`) |

---

## 11. Known gaps / open items

1. **`return_product.py` is broken against current signatures.** It unpacks 3 values from `PUD.decide` (which returns 4 since the `description` field was added) and constructs `CreatePP` / `UpdatePP` without the new `DESCRIPTION` arg. The outer `try/except` masks the `ValueError`. Mirror the call sites in `main.py` to fix.
2. **`qty_sample` shape mismatch.** `ProductInfo.get_sample_qty()` returns a **scalar**, but `CreatePP.create_sample` / `UpdatePP.update_sample` still do `qty_sample[0]`. For string qtys this slices the first character; for the no-match `0` int it raises `TypeError`. Drop the `[0]` in the callers, or change `get_sample_qty` to return a list.
3. **`set_inventory_metafield` divergence between create and update.** Create posts only to relevant locations; update posts to all 4 (zeroing irrelevant ones). Intentional reset semantic, but the two helpers are no longer interchangeable.
4. **Inventory positional ordering trusted.** `set_inventory_metafield` iterates `response.json()["product"]["variants"]` and pairs positionally with `qty_ne[i]/qty_ba[i]`. If Shopify ever returns variants in an order different from the submission order, qtys land on the wrong size. Verify on first real run.
5. **Metafield POST may create duplicates.** `POST /metafields.json` is called on every update; Shopify usually dedupes by `(owner_id, namespace, key)` but it's not guaranteed for all metafield types.
6. **API version mismatch.** `update_pp.py` uses `2024-01` for product calls and `2026-01` for inventory + metafields. `create_pp.py` uses `2026-01` throughout.
7. **`keep` doesn't filter on blank SKU.** A size with `qty > 0` and both `skus_ne[i]` and `skus_ba[i]` blank creates a variant with empty SKU.
8. **`PP SY LIST` Page Status is a stale snapshot** — only refreshed by `fetch_product_id_new.py`. Between snapshots, a Shopify product can drift DRAFT → ACTIVE without `PUD.decide` knowing.
9. **`PUD.decide` uses substring regex matching** — `str.contains(STYLE, case=False, na=False)` is substring + regex by default. `EMORY TIPPED L/S TOP` matches `EMORY TIPPED L/S TOP V2`. Use exact-match if style prefixes collide.
10. **`return_product.py` only creates/updates `fixed` / `sale_stock`.** Placeholder types (`unfix`, `sample`, `o4`) are single-style-only via `main.py`.
11. **`return_product.py` column R hardcoded** for the master-grid link writeback, and column `A` hardcoded for the PP SY LIST writeback. Same in `main.py` (column `A`). Verify column positions before a run.
12. **Update path silently overwrites `body_html` and `images`.** If a content team edits the Shopify description by hand on a DRAFT, the next `update_*` will clobber it with `PP SY LIST.Description`. Update the sheet, not Shopify, for description changes.
13. **`KeyError: 'product'` on failed PUT/POST.** `set_inventory_metafield` does `data["product"]["variants"]` with no status check. If the upstream request failed (response is `{"errors": ...}`), this raises and the outer `try/except` swallows it — inventory is silently skipped. Look at the full traceback to find the actual upstream failure.

Items 1, 2, 4, 7, 9 are the most likely to bite; the rest are mostly informational.
