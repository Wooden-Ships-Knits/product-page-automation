"""
Fields the Build page lets you choose when UPDATING an existing product page.

Used by webapp/pages/1_Build.py (the checkboxes) and update_pp.py (what gets sent).
No imports on purpose — the web page can load this without pulling in the Shopify/Sheets setup.

Only applies to UPDATES. A new product page is always created with every field, and a
size/color variant that doesn't exist yet on the product is always created complete.
"""

# key -> (label, help)
FIELDS = {
    "handle":      ("URL / handle", "Product URL (handle)."),
    "seo":         ("SEO", "Page title + meta description."),
    "description": ("Description", "Product description (sale text, description, composition)."),
    "tags":        ("Tags & template", "Tags + template. Includes the stock badges (NEARLY GONE / "
                                       "LAST ONE LEFT), so tick it together with Quantity to keep those in sync."),
    "size_chart":  ("Size chart", "Size chart metafield (+ tax code)."),
    "images":      ("Images", "Product images and per-color variant images."),
    "price":       ("Price", "Price + compare-at price of every variant."),
    "sku_barcode": ("SKU & barcode", "SKU and barcode of existing variants."),
    "weight":      ("Weight", "Variant weight."),
    "quantity":    ("Quantity", "Inventory per location."),
}

ALL = set(FIELDS)
