"""
Re-prefix variant SKUs on existing Shopify products: K53CPE3W615 -> K57CPE3W615.
Only the leading season prefix (K## / PK##) changes; the rest of the SKU is untouched.

    from sku_prefix import update_sku_prefix

    update_sku_prefix([7568916611120, 7732973371440])                    # DRY RUN, prints what would change
    update_sku_prefix([7568916611120], dry_run=False)                    # actually writes
    update_sku_prefix(ids, target="K57", dry_run=False, include_pk=True) # also re-prefix PK## skus

From the project root:
    venv/bin/python sku_prefix.py 7568916611120 7732973371440            # dry run
    venv/bin/python sku_prefix.py --apply 7568916611120

Notes
- Barcodes are NOT touched, only SKUs.
- PK## skus are skipped by default: rewriting them to K57 would drop the "P"
  (a different category). Pass include_pk=True if that's what you want.
- Each product triggers a products/update webhook -> PP SY LIST resyncs by itself.
"""
import argparse
import re

import requests

from Setup import set_sy

GRAPHQL_URL = "https://wooden-ships.myshopify.com/admin/api/2026-01/graphql.json"
PREFIX_RE = re.compile(r"^(PK\d{2}|K\d{2})", re.IGNORECASE)

VARIANTS_QUERY = """
query ($id: ID!) {
  product(id: $id) {
    id
    title
    variants(first: 100) {
      nodes { id sku }
    }
  }
}
"""

BULK_UPDATE = """
mutation ($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id sku }
    userErrors { field message }
  }
}
"""


def _gql(query, variables):
    r = requests.post(
        GRAPHQL_URL,
        headers=set_sy.headers_,
        json={"query": query, "variables": variables},
        timeout=30,
    )
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def new_sku(sku, target="K57", include_pk=False):
    """'K53CPE3W615' -> 'K57CPE3W615'. Returns None when nothing should change."""
    sku = (sku or "").strip()
    m = PREFIX_RE.match(sku)
    if not m:
        return None                      # no K##/PK## prefix — leave alone
    old_prefix = m.group(1)
    if old_prefix.upper().startswith("PK") and not include_pk:
        return None                      # would drop the "P" — skip unless asked
    if old_prefix.upper() == target.upper():
        return None                      # already correct
    return target + sku[len(old_prefix):]


def update_sku_prefix(product_id_list, target="K57", dry_run=True, include_pk=False):
    """Re-prefix every variant SKU of each product to `target`.
    dry_run=True (default) only prints the planned changes. Returns {product_id: summary}."""
    results = {}
    for pid in product_id_list:
        pid = str(pid).strip()
        if not pid:
            continue
        gid = pid if pid.startswith("gid://") else f"gid://shopify/Product/{pid}"
        try:
            product = _gql(VARIANTS_QUERY, {"id": gid})["product"]
            if product is None:
                results[pid] = "product not found"
                print(f"❌ {pid}: product not found")
                continue

            changes = []
            for v in product["variants"]["nodes"]:
                nsku = new_sku(v["sku"], target=target, include_pk=include_pk)
                if nsku:
                    changes.append((v["id"], v["sku"], nsku))

            if not changes:
                results[pid] = "no change"
                print(f"–  {pid} {product['title']}: no SKU needs changing")
                continue

            print(f"{'[dry-run] ' if dry_run else ''}{pid} {product['title']}:")
            for _, old, new in changes:
                print(f"     {old}  ->  {new}")

            if dry_run:
                results[pid] = f"would change {len(changes)}"
                continue

            data = _gql(BULK_UPDATE, {
                "productId": gid,
                "variants": [{"id": vid, "inventoryItem": {"sku": new}} for vid, _, new in changes],
            })["productVariantsBulkUpdate"]
            if data["userErrors"]:
                results[pid] = f"userErrors: {data['userErrors']}"
                print(f"❌ {pid}: {data['userErrors']}")
            else:
                results[pid] = f"updated {len(changes)}"
                print(f"✅ {pid}: updated {len(changes)} sku(s)")
        except Exception as e:
            results[pid] = f"{type(e).__name__}: {e}"
            print(f"❌ {pid}: {results[pid]}")

    changed = sum(1 for v in results.values() if v.startswith(("updated", "would change")))
    print(f"\n{'Would change' if dry_run else 'Changed'} SKUs on {changed}/{len(results)} product(s) -> prefix {target}")
    return results


