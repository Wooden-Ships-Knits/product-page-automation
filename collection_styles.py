"""
List the unique ACTIVE styles in a Shopify collection.

    from collection_styles import get_active_styles, get_active_products

    styles = get_active_styles("BEACH + LAKE")      # ['ALESSA MARLED CABLE CREW CHUNKY', ...]
    rows   = get_active_products("BEACH + LAKE")    # per product page: style, title, color, id

From the project root:
    venv/bin/python collection_styles.py "BEACH + LAKE"
    venv/bin/python collection_styles.py "BEACH + LAKE" --products   # the full per-page list
    venv/bin/python collection_styles.py --list                      # show all collection names

A collection holds one product page per style+color (and separate FP/DC pages), so the
same style appears several times — the style list is de-duplicated and sorted.
Style = product title minus the '*SALE* - ' prefixes, the same rule as
Setup/fetch_product_id_new.fetch() and webhook_receiver.build_row(); keep the three in sync.
"""
import argparse
import csv
import sys
from pathlib import Path

import requests

from Setup import set_sy

GRAPHQL_URL = "https://wooden-ships.myshopify.com/admin/api/2026-01/graphql.json"
SALE_PREFIXES = ["*SALE* - ", "*SALE* ", "*SALE*- ", "SALE* - ", "*SALES* - ", "*SALE * - "]

COLLECTIONS_QUERY = """
query ($cursor: String) {
  collections(first: 250, after: $cursor) {
    edges { node { id title productsCount { count } } }
    pageInfo { hasNextPage endCursor }
  }
}
"""

COLLECTION_PRODUCTS_QUERY = """
query ($id: ID!, $cursor: String) {
  collection(id: $id) {
    title
    products(first: 250, after: $cursor) {
      edges {
        node {
          id
          title
          status
          variants(first: 1) {
            edges { node { selectedOptions { name value } } }
          }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def _gql(query, variables=None):
    r = requests.post(
        GRAPHQL_URL,
        headers=set_sy.headers_,
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def list_collections():
    """[(title, product count)] for every collection in the store, sorted by title."""
    out, cursor = [], None
    while True:
        data = _gql(COLLECTIONS_QUERY, {"cursor": cursor})["collections"]
        for e in data["edges"]:
            n = e["node"]
            out.append((n["title"], (n.get("productsCount") or {}).get("count")))
        if not data["pageInfo"]["hasNextPage"]:
            return sorted(out, key=lambda t: t[0].casefold())
        cursor = data["pageInfo"]["endCursor"]


def _collection_id(name):
    """Resolve a collection by title (exact first, then 'contains'); raises if ambiguous."""
    name = name.strip()
    found, cursor = [], None
    while True:
        data = _gql(COLLECTIONS_QUERY, {"cursor": cursor})["collections"]
        for e in data["edges"]:
            found.append((e["node"]["title"], e["node"]["id"]))
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]

    exact = [c for c in found if c[0].casefold() == name.casefold()]
    if exact:
        return exact[0][1], exact[0][0]
    partial = [c for c in found if name.casefold() in c[0].casefold()]
    if len(partial) == 1:
        return partial[0][1], partial[0][0]
    if not partial:
        raise ValueError(
            f"No collection named {name!r}. Run with --list to see the available names."
        )
    raise ValueError(f"{name!r} matches several collections: {[c[0] for c in partial]}")


def _style_of(title):
    style = title
    for prefix in SALE_PREFIXES:
        style = style.replace(prefix, "")
    return style.strip()


def _write_csv(path, header, rows, collection_name):
    """Write `rows` (list of lists) to `path`; a blank/True path auto-names the file in Output/."""
    if path in (None, True, ""):
        safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in collection_name).strip()
        path = Path("Output") / f"{safe} {header[0].lower()}s.csv"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig = opens cleanly in Excel
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"Saved {len(rows)} row(s) -> {path}")
    return str(path)


def get_active_products(collection_name, csv_path=None):
    """Per ACTIVE product page in the collection: {style, title, color, product_id, sale}.
    csv_path: a filename, or True to auto-name it in Output/."""
    cid, resolved = _collection_id(collection_name)
    print(f"Collection: {resolved}")
    rows, cursor = [], None
    total = 0
    while True:
        data = _gql(COLLECTION_PRODUCTS_QUERY, {"id": cid, "cursor": cursor})["collection"]["products"]
        for e in data["edges"]:
            n = e["node"]
            total += 1
            if n["status"] != "ACTIVE":
                continue
            color = ""
            variants = n["variants"]["edges"]
            if variants:
                for opt in variants[0]["node"]["selectedOptions"]:
                    if opt["name"].lower() in ("color", "colour"):
                        color = opt["value"]
                        break
            rows.append({
                "style": _style_of(n["title"]),
                "title": n["title"],
                "color": color,
                "product_id": n["id"].split("/")[-1],
                "sale": "SALE" in n["title"],
            })
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]

    print(f"{len(rows)} active product page(s) out of {total} in the collection")
    if csv_path:
        _write_csv(
            csv_path,
            ["Style", "Title", "Color", "Product ID", "FP/DC"],
            [[r["style"], r["title"], r["color"], r["product_id"], "DC" if r["sale"] else "FP"] for r in rows],
            resolved,
        )
    return rows


def get_active_styles(collection_name, csv_path=None):
    """Unique, sorted style names of the ACTIVE products in the collection.
    csv_path: a filename, or True to auto-name it in Output/."""
    styles = sorted({r["style"] for r in get_active_products(collection_name) if r["style"]})
    print(f"{len(styles)} unique style(s)")
    if csv_path:
        _write_csv(csv_path, ["Style"], [[s] for s in styles], collection_name)
    return styles


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Active styles in a Shopify collection.")
    ap.add_argument("collection", nargs="?", help="collection name, e.g. 'BEACH + LAKE'")
    ap.add_argument("--list", action="store_true", help="list all collection names + product counts")
    ap.add_argument("--products", action="store_true", help="print every active page, not just styles")
    ap.add_argument("--csv", nargs="?", const=True, metavar="FILE",
                    help="also save to CSV (no FILE given -> auto-named in Output/)")
    a = ap.parse_args()

    if a.list:
        for title, count in list_collections():
            print(f"{count if count is not None else '?':>5}  {title}")
        sys.exit(0)
    if not a.collection:
        ap.error("give a collection name, or --list")

    if a.products:
        for r in get_active_products(a.collection, csv_path=a.csv):
            print(f"{r['product_id']:>15}  {'DC' if r['sale'] else 'FP'}  {r['style']}  |  {r['color']}")
    else:
        for s in get_active_styles(a.collection, csv_path=a.csv):
            print(s)
