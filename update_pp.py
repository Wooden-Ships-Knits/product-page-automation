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
    def __init__(self,STYLE,COLOR,SEASON,PRODUCT_ID,SALE, DESCRIPTION):
        self.STYLE = STYLE
        self.COLOR = COLOR
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

    def _attach_variant_image(self, response):
        data = response.json().get("product", {})
        images = data.get("images", [])
        variants = data.get("variants", [])
        if not images or not variants:
            return
        image_id = images[0]["id"]
        payload = {
            "product": {
                "id": self.PRODUCT_ID,
                "variants": [{"id": v["id"], "image_id": image_id} for v in variants],
            }
        }
        requests.put(self.url, headers=headers, json=payload)

    def update_unfix(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=False, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}
            title_page, sale_title_page, sale_desc, thread_comp = P.title_and_desc()
            page_title, meta_desc, url = P.get_SEL()    
            variants, options,tags, template_suffix = self.product_post(self.COLOR, P)
            metachart , _ = P.get_metachart()

            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "handle":url,
                    "metafields_global_title_tag": page_title.replace("/"," "),
                    "metafields_global_description_tag":meta_desc,
                    "body_html": sale_desc + f"<p>{self.description}</p>" + thread_comp,
                    "images": P.get_image(),
                    "variants": variants,
                    "options": options,
                    "tags":tags,
                    "template_suffix":template_suffix,
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
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self._attach_variant_image(response)
            self.set_inventory_metafield(response, 'unfix')
        except Exception as e:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link
    
    def update_fixed(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=False, sas=False)
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
            _, metachart = P.get_metachart()
            title_page, sale_title_page, sale_desc, thread_comp = P.title_and_desc()
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}
            page_title, meta_desc, url = P.get_SEL()
            variants, options,tags, template_suffix = self.product_post(self.COLOR, P, keep=keep, qty=total_qty, skus=skus_chosen, barcodes=barcodes_chosen)
            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "handle":url,
                    "metafields_global_title_tag": page_title.replace("/"," "),
                    "metafields_global_description_tag":meta_desc,
                    "body_html": sale_desc + f"<p>{self.description}</p>" + thread_comp,
                    "images": P.get_image(),
                    "variants": variants,
                    "options": options,
                    "tags":tags,
                    "template_suffix":template_suffix,
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
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self._attach_variant_image(response)
            self.set_inventory_metafield(response, 'fixed', qty_ne=qty_ne, qty_ba=qty_ba)

        except Exception:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link
    
    def update_sample(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=True, sale=True, sas=False)
            qty_sample = P.get_sample_qty()
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}
            title_page, sale_title_page, sale_desc, thread_comp = P.title_and_desc()
            page_title, meta_desc, url = P.get_SEL()
            _, sizes = P.get_metachart()
            if 'S/M' not in sizes:
                print(f"S/M not found in sizes for {self.STYLE} {self.COLOR} — skipping sample update.")
                return f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
            keep = [sizes.index('S/M')]
            variants, options,tags, template_suffix = self.product_post(self.COLOR, P,keep=keep,qty=qty_sample)
            metachart , _ = P.get_metachart()
            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "handle":url,
                    "metafields_global_title_tag": page_title.replace("/"," "),
                    "metafields_global_description_tag":meta_desc,
                    "body_html": sale_desc + f"<p>{self.description}</p>" + thread_comp,
                    "images": P.get_image(),
                    "variants": variants,
                    "options": options,
                    "tags":tags,
                    "template_suffix":template_suffix,
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
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            if response.status_code not in (200, 201):
                print("Sample update failed:", response.text)
            self._attach_variant_image(response)
            self.set_inventory_metafield(response, 'sample', qty_sample=qty_sample)
        except Exception as e:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link 

    def update_sale_stock(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=True, sas=False)
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
            title_page, sale_title_page, sale_desc, thread_comp = P.title_and_desc()
            page_title, meta_desc, url = P.get_SEL()
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}
            total_qty = sum(
                self._to_int(a) + self._to_int(b)
                for a, b in zip(qty_ne, qty_ba)
            )
            metachart , _ = P.get_metachart()
            variants, options,tags,template_suffix = self.product_post(self.COLOR, P, keep=keep, qty=total_qty, skus=skus_chosen, barcodes=barcodes_chosen)
            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "handle":url,
                    "metafields_global_title_tag": page_title.replace("/"," "),
                    "metafields_global_description_tag":meta_desc,
                    "body_html": sale_desc + f"<p>{self.description}</p>" + thread_comp,
                    "images": P.get_image(),
                    "variants": variants,
                    "options": options,
                    "tags":tags,
                    "template_suffix":template_suffix,
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
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self._attach_variant_image(response)
            self.set_inventory_metafield(response, 'sale_stock', qty_ne=qty_ne, qty_ba=qty_ba)

        except Exception:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link

    def update_o4(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=True, sas=True)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}
            title_page, sale_title_page, sale_desc, thread_comp = P.title_and_desc()
            variants, options,tags,template_suffix = self.product_post(self.COLOR, P)
            page_title, meta_desc, url = P.get_SEL()
            metachart , _ = P.get_metachart()

            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "handle":url,
                    "metafields_global_title_tag": page_title.replace("/"," "),
                    "metafields_global_description_tag":meta_desc,
                    "body_html": sale_desc + f"<p>{self.description}</p>" + thread_comp,
                    "images": P.get_image(),
                    "variants": variants,
                    "options": options,
                    "tags":tags,
                    "template_suffix":template_suffix,
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
                        "value": metachart,
                    }
                ],
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self._attach_variant_image(response)
            self.set_inventory_metafield(response, 'o4')
        except Exception as e:
            traceback.print_exc()
        link = f"https://admin.shopify.com/store/wooden-ships/products/{self.PRODUCT_ID}"
        return link
    
    def product_post(self,COLOR,P,keep=None,qty=None,skus=None,barcodes=None):
        # sizes = list(P.get_sizes())
        _, sizes = P.get_metachart()
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

        full_price,price = P.get_price()
        print(f"full_price: {full_price}")
        print(f"discounted_price: {full_price}")
        tags = P.get_tags()
        tags,template_suffix = tg.additional_tags(tags,sizes,qty)
        if template_suffix == None:
            if self.sale == False:
                template_suffix ="default"
            elif self.sale == True:
                template_suffix ="sale-item"
        variants = []
        print("processing variant")

        for i, size in enumerate(sizes):
            variants.append({
            "option1": f"{size} {SIZE_RANGE[size]}",
            "option2": COLOR.title(),
            "sku": skus[i],
            "price": price,
            "compare_at_price": full_price,
            "inventory_management": "shopify",
            "barcode": barcodes[i],
            "weight": weights[i],
            "weight_unit": "g",
        })
        
        options = [
        {
            "name": "Size",
            "values": [f"{size} {SIZE_RANGE[size]}" for size in sizes]
        },
        {
            "name": "Color",
            "values": [COLOR.title()]
        }
        ]
        return variants, options, tags, template_suffix
            
    def set_inventory_metafield(self,response, production_type, qty_ne=None, qty_ba=None, qty_sample = None):
        data = response.json()
        if "product" in data and "variants" in data["product"]:
            variants = data["product"]["variants"]
        else:
            print("PUT response missing 'product' — falling back to GET for inventory update.")
            variants = requests.get(self.url, headers=headers).json()["product"]["variants"]

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
            inventory_item_id = variant["inventory_item_id"]
            variant_id = variant["id"]

            for location_id, qty in locations:
                requests.post(
                    "https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
                    headers=headers,
                    json={
                        "location_id": location_id,
                        "inventory_item_id": inventory_item_id,
                        "available": qty,
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