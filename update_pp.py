from fetch_to_product_page import ProductInfo
import requests
from Setup import set_sy,setup, tags_generator as tg
import os
from pathlib import Path
from dotenv import load_dotenv
import traceback
load_dotenv(Path(__file__).parent / "Setup/.env", override=True)

headers = setup.HEADERS
product_url = set_sy.product_url

SIZE_RANGE = {
    "X/S": "(2-4)",
    "S/M": "(6-8)",
    "M/L": "(10-12)",
    "X/L": "(14-16)",
}

class UpdatePP:
    def __init__(self,STYLE,COLORS,SEASON,PRODUCT_ID,SALE, DESCRIPTION):
        self.STYLE = STYLE
        self.COLOR = COLORS[0]
        self.COLORS = COLORS
        self.SEASON = SEASON
        self.PRODUCT_ID = PRODUCT_ID
        self.sale = SALE
        self.url = f"https://wooden-ships.myshopify.com/admin/api/2024-01/products/{self.PRODUCT_ID}.json"
        self.description = DESCRIPTION

    def _to_int(self,v):
        try:
            return int(str(v).strip() or 0)
        except (TypeError, ValueError):
            return 0

    GRAPHQL_URL = "https://wooden-ships.myshopify.com/admin/api/2026-01/graphql.json"

    @staticmethod
    def _money(v):
        """Coerce a price-ish value to a bare decimal string, or None if empty."""
        s = str(v).replace("$", "").replace(",", "").strip()
        return s or None

    def _run_product_set(self, product_set_input, ordered_skus):
        """Update the product via the GraphQL productSet mutation.

        productSet lets us attach images by their existing Files/Content GID, so
        Shopify references the existing file instead of re-downloading it and
        creating a duplicate in Content.

        Returns (numeric_product_id, variants) aligned with `ordered_skus` (the
        in-stock variants only); each entry is {"id", "inventory_item_id"}
        (numeric) or None if that sku wasn't returned. (None, None) on failure.
        """
        mutation = """
        mutation UpdateProductSet($input: ProductSetInput!) {
          productSet(synchronous: true, input: $input) {
            product {
              id
              variants(first: 100) {
                nodes { id sku inventoryItem { id } }
              }
            }
            userErrors { field message }
          }
        }
        """
        response = requests.post(
            self.GRAPHQL_URL,
            headers=headers,
            json={"query": mutation, "variables": {"input": product_set_input}},
        )
        result = response.json()
        if "errors" in result:
            print("productSet GraphQL errors:", result["errors"])
            return None, None
        ps = result.get("data", {}).get("productSet")
        if ps is None:
            print("Unexpected productSet response:", result)
            return None, None
        if ps["userErrors"]:
            print("productSet userErrors:", ps["userErrors"])
            return None, None

        product = ps["product"]
        product_id = product["id"].split("/")[-1]

        by_sku = {}
        for node in product["variants"]["nodes"]:
            by_sku[str(node.get("sku") or "")] = {
                "id": node["id"].split("/")[-1],
                "inventory_item_id": node["inventoryItem"]["id"].split("/")[-1],
            }
        variants = [by_sku.get(str(s)) for s in ordered_skus]
        return product_id, variants

    def update_unfix(self):
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=False, sale=False, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            product_set_input, ordered_skus = self.product_post(self.COLORS, P, existing)
            product_id, variants = self._run_product_set(product_set_input, ordered_skus)
            if product_id is not None:
                self.set_inventory_metafield(variants, 'unfix')
        except Exception as e:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link
    
    def update_fixed(self):
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=False, sale=False, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            qty_ne, skus_ne = P.get_NE_qty()
            qty_ba, skus_ba = P.get_BALI_qty()
            combined = [self._to_int(a) + self._to_int(b) for a, b in zip(qty_ne, qty_ba)]
            keep = [i for i, q in enumerate(combined) if q > 0]
            if not keep:
                print(f"No stock for {self.STYLE} {self.COLOR} — skipping fixed product.")
                return
            skus_chosen = [skus_ne[i] if str(skus_ne[i]).strip() else skus_ba[i] for i in keep]
            barcodes_chosen = P.fetch_barcode(skus_chosen)
            qty_ne = [qty_ne[i] for i in keep]
            qty_ba = [qty_ba[i] for i in keep]
            total_qty = sum(
                self._to_int(a) + self._to_int(b)
                for a, b in zip(qty_ne, qty_ba)
            )
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            product_set_input, ordered_skus = self.product_post(self.COLORS, P, existing, keep=keep, qty=total_qty, skus=skus_chosen, barcodes=barcodes_chosen)
            product_id, variants = self._run_product_set(product_set_input, ordered_skus)
            if product_id is not None:
                self.set_inventory_metafield(variants, 'fixed', qty_ne=qty_ne, qty_ba=qty_ba)

        except Exception:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link
    
    def update_sample(self):
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=True, sale=True, sas=False)
            qty_sample = P.get_sample_qty()
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            _, sizes = P.get_metachart()
            if 'S/M' not in sizes:
                print(f"S/M not found in sizes for {self.STYLE} {self.COLOR} — skipping sample update.")
                return f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
            keep = [sizes.index('S/M')]
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            product_set_input, ordered_skus = self.product_post(self.COLORS, P, existing, keep=keep, qty=qty_sample)
            product_id, variants = self._run_product_set(product_set_input, ordered_skus)
            if product_id is not None:
                self.set_inventory_metafield(variants, 'sample', qty_sample=qty_sample)
        except Exception as e:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link 

    def update_sale_stock(self):
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=False, sale=True, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            qty_ne, skus_ne = P.get_NE_qty()
            qty_ba, skus_ba = P.get_BALI_qty()
            combined = [self._to_int(a) + self._to_int(b) for a, b in zip(qty_ne, qty_ba)]
            keep = [i for i, q in enumerate(combined) if q > 0]
            if not keep:
                print(f"No stock for {self.STYLE} {self.COLOR} — skipping sale_stock product.")
                return
            skus_chosen = [skus_ne[i] if str(skus_ne[i]).strip() else skus_ba[i] for i in keep]
            barcodes_chosen = P.fetch_barcode(skus_chosen)
            qty_ne = [qty_ne[i] for i in keep]
            qty_ba = [qty_ba[i] for i in keep]
            total_qty = sum(
                self._to_int(a) + self._to_int(b)
                for a, b in zip(qty_ne, qty_ba)
            )
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            product_set_input, ordered_skus = self.product_post(self.COLORS, P, existing, keep=keep, qty=total_qty, skus=skus_chosen, barcodes=barcodes_chosen)
            product_id, variants = self._run_product_set(product_set_input, ordered_skus)
            if product_id is not None:
                self.set_inventory_metafield(variants, 'sale_stock', qty_ne=qty_ne, qty_ba=qty_ba)

        except Exception:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link

    def update_o4(self):
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=False, sale=True, sas=True)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            product_set_input, ordered_skus = self.product_post(self.COLORS, P, existing)
            product_id, variants = self._run_product_set(product_set_input, ordered_skus)
            if product_id is not None:
                self.set_inventory_metafield(variants, 'o4')
        except Exception as e:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link
    
    def product_post(self, COLORS, P, existing_variants, keep=None, qty=None, skus=None, barcodes=None):
        """Build the ProductSetInput for updating this product.

        `existing_variants` is the REST GET variants list. We match desired
        in-stock variants to their existing ids, and re-include every other
        existing variant so productSet (which deletes list entries it doesn't
        see) doesn't drop out-of-stock sizes.

        Returns (product_set_input, ordered_skus) where ordered_skus are the
        in-stock skus in build order (for inventory mapping after the mutation).
        """
        title_page, sale_title_page, sale_desc, thread_comp = P.title_and_desc()
        page_title, meta_desc, url = P.get_SEL()
        metachart, sizes = P.get_metachart()
        sizes_im, weights_im = P.get_weight()
        weight_by_size = dict(zip(sizes_im, weights_im))
        weights = [weight_by_size.get(s, 0) for s in sizes]

        need_defaults = skus is None or barcodes is None
        default_barcodes, default_skus = P.get_sku_barcode() if need_defaults else ([], [])

        if keep is not None:
            sizes   = [sizes[i]   for i in keep]
            weights = [weights[i] for i in keep]
            if default_skus:
                default_skus = [default_skus[i] for i in keep]
            if default_barcodes:
                default_barcodes = [default_barcodes[i] for i in keep]

        skus = skus if skus is not None else default_skus
        barcodes = barcodes if barcodes is not None else default_barcodes

        print(f"size: {sizes}, \nweights: {weights}")
        print(f"barcodes: {barcodes}")
        print(f"skus: {skus}")

        full_price, price = P.get_price()
        print(f"compared_at_price: {full_price}")
        print(f"price: {price}")
        money_price = self._money(price)
        compare_at = self._money(full_price)

        tags = P.get_tags()
        tags, template_suffix = tg.additional_tags(tags, sizes, qty)
        if template_suffix == None:
            template_suffix = "default" if self.sale == False else "sale-item"

        # existing variant ids, keyed by sku and by (size, color) option values
        sku_to_gid = {}
        options_to_gid = {}
        for v in existing_variants:
            gid = f"gid://shopify/ProductVariant/{v['id']}"
            if v.get("sku"):
                sku_to_gid[v["sku"]] = gid
            options_to_gid[(v.get("option1"), v.get("option2"))] = gid

        # existing Files/Content media referenced by id (no re-download), per color
        files = P.get_image_from_files()
        color_media = {}
        for f in files:
            color_media.setdefault(f["alt"], f["id"])
        seen_ids = set()
        files_unique = []
        for f in files:
            if f["id"] not in seen_ids:
                seen_ids.add(f["id"])
                files_unique.append({"id": f["id"], "alt": f["alt"]})

        desired = []
        ordered_skus = []
        desired_keys = set()
        print("processing variant")
        for j, c in enumerate(COLORS):
            j = j * len(sizes)
            alt_key = c.replace("/", " ").lower().replace(" ", "-")
            media_id = color_media.get(alt_key)
            for i, size in enumerate(sizes):
                size_val = f"{size} {SIZE_RANGE[size]}"
                color_val = c.title()
                variant = {
                    "optionValues": [
                        {"optionName": "Size",  "name": size_val},
                        {"optionName": "Color", "name": color_val},
                    ],
                    "sku": skus[i+j],
                    "barcode": barcodes[i+j],
                    "inventoryItem": {
                        "tracked": True,
                        "measurement": {"weight": {"value": float(weights[i]), "unit": "GRAMS"}},
                    },
                }
                if money_price:
                    variant["price"] = money_price
                if compare_at:
                    variant["compareAtPrice"] = compare_at
                if media_id:
                    variant["file"] = {"id": media_id}
                vid = sku_to_gid.get(skus[i+j]) or options_to_gid.get((size_val, color_val))
                if vid:
                    variant["id"] = vid
                desired.append(variant)
                ordered_skus.append(skus[i+j])
                desired_keys.add((size_val, color_val))

        # re-include existing variants not in the desired set so productSet
        # (full-sync on list fields) doesn't delete out-of-stock sizes
        preserved = []
        for v in existing_variants:
            key = (v.get("option1"), v.get("option2"))
            if key in desired_keys or v.get("option1") is None:
                continue
            preserved.append({
                "id": f"gid://shopify/ProductVariant/{v['id']}",
                "optionValues": [
                    {"optionName": "Size",  "name": v.get("option1")},
                    {"optionName": "Color", "name": v.get("option2")},
                ],
            })

        all_variants = desired + preserved

        # product options must list every value used by desired + preserved variants
        size_values, color_values = [], []
        for vv in all_variants:
            for ov in vv["optionValues"]:
                if ov["optionName"] == "Size" and ov["name"] not in size_values:
                    size_values.append(ov["name"])
                if ov["optionName"] == "Color" and ov["name"] not in color_values:
                    color_values.append(ov["name"])

        product_options = [
            {"name": "Size",  "values": [{"name": s} for s in size_values]},
            {"name": "Color", "values": [{"name": c} for c in color_values]},
        ]

        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        product_set_input = {
            "id": f"gid://shopify/Product/{self.PRODUCT_ID}",
            "handle": url,
            "seo": {"title": page_title.replace("/", " "), "description": meta_desc},
            "descriptionHtml": sale_desc + f"<p>{self.description}</p>" + thread_comp,
            "tags": tag_list,
            "templateSuffix": template_suffix,
            "metafields": [
                {"namespace": "avalara", "key": "taxcode", "type": "single_line_text_field", "value": "PC040100"},
                {"namespace": "custom", "key": "size_chart_metafield", "value": metachart},
            ],
            "productOptions": product_options,
            "variants": all_variants,
        }
        # Only send files when we actually matched some — an empty list would make
        # productSet delete ALL existing media from the product.
        if files_unique:
            product_set_input["files"] = files_unique

        return product_set_input, ordered_skus

    def set_inventory_metafield(self, variants, production_type, qty_ne=None, qty_ba=None, qty_sample = None):
        # `variants` is the in-stock list from _run_product_set, aligned with
        # ordered_skus: each entry is {"id", "inventory_item_id"} (numeric) or None.
        def _to_int(v):
            try:
                return int(str(v).strip() or 0)
            except (TypeError, ValueError):
                return 0

        ne_first_choice = os.getenv("NE_First_Choice_ID")
        bali_stock = os.getenv("Bali_Stock_ID")
        ne_sample = os.getenv("NE_Sample_ID")
        bali_to_produce = os.getenv("Bali_To_Produce_ID")

        if production_type in ('fixed', 'sale_stock'):
            per_variant_locations = [
                [
                    (ne_first_choice, _to_int(qty_ne[i])),
                    (bali_stock, _to_int(qty_ba[i])),
                    (ne_sample, 0),
                    (bali_to_produce, 0),
                ]
                for i in range(len(variants))
            ]
        elif production_type == 'sample':
            per_variant_locations = [
                [
                    (ne_sample, qty_sample),
                    (ne_first_choice, 0),
                    (bali_stock, 0),
                    (bali_to_produce, 0),
                ]
                for _ in variants
            ]
        else:
            per_variant_locations = [
                [
                    (bali_to_produce, 5000),
                    (ne_first_choice, 0),
                    (bali_stock, 0),
                    (ne_sample, 0),
                ]
                for _ in variants
            ]

        for variant, locations in zip(variants, per_variant_locations):
            if not variant:
                print("Skipping inventory/metafield: a variant sku was not returned by productSet.")
                continue
            inventory_item_id = variant["inventory_item_id"]
            variant_id = variant["id"]

            for location_id, qty in locations:
                if _to_int(qty) > 0:
                    requests.post(
                        "https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
                        headers=headers,
                        json={
                            "location_id": location_id,
                            "inventory_item_id": inventory_item_id,
                            "available": qty,
                        },
                    )
                else:
                    # qty == 0 -> deactivate this location (delete the inventory level)
                    # so the variant reads "not stocked here" instead of "0 available".
                    # Safe: the variant stays stocked at its other location(s).
                    requests.delete(
                        "https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels.json",
                        headers=headers,
                        params={
                            "inventory_item_id": inventory_item_id,
                            "location_id": location_id,
                        },
                    )

            requests.post(
                "https://wooden-ships.myshopify.com/admin/api/2026-01/metafields.json",
                headers=headers,
                json={
                    "metafield": {
                        "namespace": "avalara",
                        "key": "taxcode",
                        "type": "single_line_text_field",
                        "value": "PC040100",
                        "owner_id": variant_id,
                        "owner_resource": "variant",
                    }
                },
            )

"""
https://admin.shopify.com/store/wooden-ships/products/7976332853296
"""