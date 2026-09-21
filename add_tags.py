"""
Add tags to existing Shopify products, keeping their current tags (GraphQL tagsAdd).

    from add_tags import add_full_priced_tag
    add_full_priced_tag([7568916611120, "7732973371440"])

or from the project root:
    venv/bin/python add_tags.py 7568916611120 7732973371440
"""
import sys

import requests

from Setup import set_sy

GRAPHQL_URL = "https://wooden-ships.myshopify.com/admin/api/2026-01/graphql.json"

TAGS_ADD = """
mutation ($id: ID!, $tags: [String!]!) {
  tagsAdd(id: $id, tags: $tags) {
    node { id }
    userErrors { field message }
  }
}
"""


def add_tags(product_id_list, tags):
    """Add `tags` to every product in `product_id_list` (numeric ids or gid://shopify/Product/… ).
    Existing tags are kept; a tag the product already has is not duplicated.
    Returns {product_id: "ok" | error message}."""
    results = {}
    for pid in product_id_list:
        pid = str(pid).strip()
        if not pid:
            continue
        gid = pid if pid.startswith("gid://") else f"gid://shopify/Product/{pid}"
        try:
            r = requests.post(
                GRAPHQL_URL,
                headers=set_sy.headers_,
                json={"query": TAGS_ADD, "variables": {"id": gid, "tags": list(tags)}},
                timeout=30,
            )
            data = r.json()
            if data.get("errors"):
                results[pid] = f"GraphQL error: {data['errors']}"
            elif data["data"]["tagsAdd"]["userErrors"]:
                results[pid] = f"userErrors: {data['data']['tagsAdd']['userErrors']}"
            else:
                results[pid] = "ok"
        except Exception as e:
            results[pid] = f"{type(e).__name__}: {e}"
        print(f"{'✅' if results[pid] == 'ok' else '❌'} {pid}: {results[pid]}")

    ok = sum(1 for v in results.values() if v == "ok")
    print(f"Tagged {ok}/{len(results)} product(s) with {list(tags)}")
    return results


def add_full_priced_tag(product_id_list):
    """Add the 'full priced' tag to every product id in the list."""
    return add_tags(product_id_list, ["full priced"])


if __name__ == "__main__":
    add_full_priced_tag(sys.argv[1:])
