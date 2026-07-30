from fetch_to_product_page import ProductInfo
import requests
from Setup import set_sy,setup,tags_generator as tg
import os
import traceback
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / "Setup/.env", override=True)

headers = setup.HEADERS
product_url = set_sy.product_url

SIZE_RANGE = {
    "X/S": "(2-4)",
    "S/M": "(6-8)",
    "M/L": "(10-12)",
    "X/L": "(14-16)",
}

class CreatePP:
    def __init__(self,STYLE,COLORS,SEASON,SALE, DESCRIPTION):
        self.STYLE= STYLE
        self.COLOR = COLORS[0]
        self.COLORS = COLORS
        self.SEASON = SEASON
        self.sale = SALE
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
        """Create the product via the GraphQL productSet mutation.

        productSet (not REST) lets us attach images by their existing
        Files/Content GID, so Shopify references the existing file instead of
        re-downloading it and creating a duplicate in Content.

        Returns (numeric_product_id, variants), where `variants` is aligned with
        `ordered_skus`; each entry is {"id", "inventory_item_id"} (numeric) or
        None if that sku wasn't returned. Returns (None, None) on failure.
        """
        mutation = """
        mutation CreateProductSet($input: ProductSetInput!) {
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

    def create_unfix(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=False, sale=False, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            product_data, ordered_skus = self.product_post(P)

            product_id, variants = self._run_product_set(product_data, ordered_skus)
            if product_id is None:
                return None, None

            set_sy.publish_to_all_channels(product_id, sale=False)

            self.set_inventory_metafield(variants, 'unfix')
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def create_fixed(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=False, sale=False, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            qty_ne, skus_ne = P.get_NE_qty()
            qty_ba, skus_ba = P.get_BALI_qty()
            combined = [self._to_int(a) + self._to_int(b) for a, b in zip(qty_ne, qty_ba)]
            keep = [i for i, q in enumerate(combined) if q > 0]
            if not keep:
                print(f"No stock for {self.STYLE} {self.COLOR} — skipping fixed product.")
                return None, None
            skus_chosen = [skus_ne[i] if str(skus_ne[i]).strip() else skus_ba[i] for i in keep]
            barcodes_chosen = P.fetch_barcode(skus_chosen)
            qty_ne = [qty_ne[i] for i in keep]
            qty_ba = [qty_ba[i] for i in keep]
            total_qty = sum(
                self._to_int(a) + self._to_int(b)
                for a, b in zip(qty_ne, qty_ba)
            )

            product_data, ordered_skus = self.product_post(P, keep=keep, qty=total_qty, skus=skus_chosen, barcodes=barcodes_chosen)

            product_id, variants = self._run_product_set(product_data, ordered_skus)
            if product_id is None:
                return None, None

            set_sy.publish_to_all_channels(product_id, sale=False)

            self.set_inventory_metafield(variants, 'fixed', qty_ne=qty_ne, qty_ba=qty_ba)
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def create_sample(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=True, sale=True, sas=False)
            qty_sample = P.get_sample_qty()
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            _, sizes = P.get_metachart()
            if 'S/M' not in sizes:
                print(f"S/M not found in sizes for {self.STYLE} {self.COLOR} — skipping sample.")
                return None, None
            keep = [sizes.index('S/M')]
            product_data, ordered_skus = self.product_post(P, keep=keep, qty=qty_sample)

            product_id, variants = self._run_product_set(product_data, ordered_skus)
            if product_id is None:
                return None, None

            set_sy.publish_to_all_channels(product_id)

            self.set_inventory_metafield(variants, 'sample', qty_sample=qty_sample)
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def create_sale_stock(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=False, sale=True, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            qty_ne, skus_ne = P.get_NE_qty()
            qty_ba, skus_ba = P.get_BALI_qty()
            combined = [self._to_int(a) + self._to_int(b) for a, b in zip(qty_ne, qty_ba)]
            keep = [i for i, q in enumerate(combined) if q > 0]
            if not keep:
                print(f"No stock for {self.STYLE} {self.COLOR} — skipping sale_stock product.")
                return None, None
            skus_chosen = [skus_ne[i] if str(skus_ne[i]).strip() else skus_ba[i] for i in keep]
            barcodes_chosen = P.fetch_barcode(skus_chosen)
            qty_ne = [qty_ne[i] for i in keep]
            qty_ba = [qty_ba[i] for i in keep]
            total_qty = sum(
                self._to_int(a) + self._to_int(b)
                for a, b in zip(qty_ne, qty_ba)
            )
            product_data, ordered_skus = self.product_post(P, keep=keep, qty=total_qty, skus=skus_chosen, barcodes=barcodes_chosen)

            product_id, variants = self._run_product_set(product_data, ordered_skus)
            if product_id is None:
                return None, None

            set_sy.publish_to_all_channels(product_id)

            self.set_inventory_metafield(variants, 'sale_stock', qty_ne=qty_ne, qty_ba=qty_ba)
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def create_o4(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLORS,self.SEASON,sample=False, sale=True, sas=True)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            product_data, ordered_skus = self.product_post(P)

            product_id, variants = self._run_product_set(product_data, ordered_skus)
            if product_id is None:
                return None, None

            set_sy.publish_to_all_channels(product_id)

            self.set_inventory_metafield(variants, 'o4')
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def product_post(self,P,keep=None,qty=None,skus=None,barcodes=None):
        title_page, sale_title_page, sale_desc, thread_comp = P.title_and_desc()
        print(f"title_page: {title_page}")
        print(f"sale_title_page: {sale_title_page}")
        print(f"sale_desc: {sale_desc}")
        print(f"thread_comp: {thread_comp}")

        page_title, meta_desc, url = P.get_SEL()
        print(f"page_title: {page_title}")
        print(f"meta_desc: {meta_desc}")
        print(f"url: {url}")

        # sizes = list(P.get_sizes())
        metachart,sizes = P.get_metachart()
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


        print(f"metachart: {metachart}")

        tags = P.get_tags()
        tags,template_suffix= tg.additional_tags(tags,sizes,qty)
        if template_suffix ==None:
            if self.sale == False:
                template_suffix ='default'
            elif self.sale == True:
                template_suffix = 'sale-item'
        print(f"tags: {tags}")

        _type = P.get_type()
        print(f"type: {_type}")

        full_price,price = P.get_price()
        print(f"compare at price: {full_price}")
        print(f"price: {price}")
        
        # Existing Files/Content media (each {"id": <gid>, "alt": <color-slug>}).
        # Reference them by id so Shopify attaches the existing file with no copy.
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

        money_price = self._money(price)
        compare_at = self._money(full_price)

        variants = []
        ordered_skus = []
        print("processing variant")
        for j, c in enumerate(self.COLORS):
            j = j* len(sizes)
            alt_key = c.replace("/", " ").lower().replace(" ", "-")
            media_id = color_media.get(alt_key)   # this color's first image
            for i, size in enumerate(sizes):
                variant = {
                    "optionValues": [
                        {"optionName": "Size",  "name": f"{size} {SIZE_RANGE[size]}"},
                        {"optionName": "Color", "name": c.title()},
                    ],
                    "sku": skus[i+j],
                    "barcode": barcodes[i+j],
                    "inventoryItem": {
                        "tracked": True,
                        "measurement": {
                            "weight": {"value": float(weights[i]), "unit": "GRAMS"}
                        },
                    },
                }
                if money_price:
                    variant["price"] = money_price
                if compare_at:
                    variant["compareAtPrice"] = compare_at
                if media_id:
                    variant["file"] = {"id": media_id}
                variants.append(variant)
                ordered_skus.append(skus[i+j])

        product_options = [
            {"name": "Size",  "values": [{"name": f"{size} {SIZE_RANGE[size]}"} for size in sizes]},
            {"name": "Color", "values": [{"name": c.title()} for c in self.COLORS]},
        ]

        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        product_set_input = {
            #SEO
            "handle": url,
            "seo": {
                "title": page_title.replace("/", " "),
                "description": meta_desc,
            },
            #header
            "title": title_page,
            "descriptionHtml": sale_desc + f"<p>{self.description}</p>" + thread_comp,
            #right side
            "vendor": "Wooden Ships",
            "productType": _type,
            "tags": tag_list,
            "status": "DRAFT",
            "templateSuffix": template_suffix,
            "files": files_unique,
            "metafields": [
                {
                    "namespace": "avalara",
                    "key": "taxcode",
                    "type": "single_line_text_field",
                    "value": "PC040100"
                },
                {
                    "namespace": "custom",
                    "key": "size_chart_metafield",
                    "value": metachart
                }
            ],
            "productOptions": product_options,
            "variants": variants,
        }

        return product_set_input, ordered_skus

    def set_inventory_metafield(self, variants, production_type, qty_ne=None, qty_ba=None, qty_sample = None):
        # `variants` is the ordered list from _run_product_set: each entry is
        # {"id", "inventory_item_id"} (numeric) or None if its sku wasn't returned.
        def _to_int(v):
            try:
                return int(str(v).strip() or 0)
            except (TypeError, ValueError):
                return 0

        if production_type in ('fixed', 'sale_stock'):
            ne_loc = os.getenv("NE_First_Choice_ID")
            bali_loc = os.getenv("Bali_Stock_ID")
            per_variant_locations = [
                [(ne_loc, _to_int(qty_ne[i])), (bali_loc, _to_int(qty_ba[i]))]
                for i in range(len(variants))
            ]
        else:
            if production_type == 'sample':
                loc = os.getenv("NE_Sample_ID")
                per_variant_locations = [[(loc, qty_sample)] for _ in variants]
            else:
                loc = os.getenv("Bali_To_Produce_ID")
                per_variant_locations = [[(loc, 5000)] for _ in variants]

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
                    # Safe: keep/combined>0 guarantees it's stocked at another location.
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
