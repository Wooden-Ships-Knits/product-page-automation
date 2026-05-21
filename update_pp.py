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
    def __init__(self,STYLE,COLOR,SEASON,PRODUCT_ID):
        self.STYLE = STYLE
        self.COLOR = COLOR
        self.SEASON = SEASON
        self.PRODUCT_ID = PRODUCT_ID
        self.url = f"https://wooden-ships.myshopify.com/admin/api/2024-01/products/{self.PRODUCT_ID}.json"

    def _to_int(self,v):
        try:
            return int(str(v).strip() or 0)
        except (TypeError, ValueError):
            return 0
            
    def update_unfix(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=False, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}

            variants, options,tags, template_suffix = self.product_post(self.COLOR, P)
            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "variants": variants,
                    "options": options,
                    "tags": tags,
                    "template_suffix": template_suffix,
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self.set_inventory_metafield(response, 'unfix')
        except Exception as e:
            traceback.print_exc()

    def update_fixed(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=False, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            qty_ne = P.get_NE_qty()
            qty_ba = P.get_BALI_qty()
            combined = [self._to_int(a) + self._to_int(b) for a, b in zip(qty_ne, qty_ba)]
            keep = [i for i, q in enumerate(combined) if q > 0]
            if not keep:
                print(f"No stock for {self.STYLE} {self.COLOR} — skipping fixed product.")
                return
            qty_ne = [qty_ne[i] for i in keep]
            qty_ba = [qty_ba[i] for i in keep]
            total_qty = sum(
                self._to_int(a) + self._to_int(b)
                for a, b in zip(qty_ne, qty_ba)
            )
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}

            variants, options,tags, template_suffix = self.product_post(self.COLOR, P, keep=keep, qty= total_qty)
            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "variants": variants,
                    "options": options,
                    "tags": tags,
                    "template_suffix": template_suffix,
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self.set_inventory_metafield(response, 'fixed', qty_ne=qty_ne, qty_ba=qty_ba)

        except Exception:
            traceback.print_exc()

    def update_sample(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=True, sale=True, sas=False)
            qty_sample = P.get_sample_qty()
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}

            variants, options,tags, template_suffix = self.product_post(self.COLOR, P,keep=None,qty=qty_sample[0])
            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "variants": variants,
                    "options": options,
                    "tags" : tags,
                    "template_suffix": template_suffix
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self.set_inventory_metafield(response, 'sample', qty_sample=qty_sample)
        except Exception as e:
            traceback.print_exc()

    def update_sale_stock(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=True, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            qty_ne = P.get_NE_qty()
            qty_ba = P.get_BALI_qty()
            combined = [self._to_int(a) + self._to_int(b) for a, b in zip(qty_ne, qty_ba)]
            keep = [i for i, q in enumerate(combined) if q > 0]
            if not keep:
                print(f"No stock for {self.STYLE} {self.COLOR} — skipping sale_stock product.")
                return
            qty_ne = [qty_ne[i] for i in keep]
            qty_ba = [qty_ba[i] for i in keep]

            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}
            total_qty = sum(
                self._to_int(a) + self._to_int(b)
                for a, b in zip(qty_ne, qty_ba)
            )
            variants, options,tags,template_suffix = self.product_post(self.COLOR, P, keep=keep, qty=total_qty)
            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "variants": variants,
                    "options": options,
                    "tags":tags,
                    "template_suffix":template_suffix,
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self.set_inventory_metafield(response, 'sale_stock', qty_ne=qty_ne, qty_ba=qty_ba)

        except Exception:
            traceback.print_exc()

    def update_o4(self):
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=True, sas=True)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            existing = requests.get(self.url, headers=headers).json()["product"]["variants"]
            sku_to_id = {v["sku"]: v["id"] for v in existing if v.get("sku")}

            variants, options,tags,template_suffix = self.product_post(self.COLOR, P)
            for v in variants:
                if v["sku"] in sku_to_id:
                    v["id"] = sku_to_id[v["sku"]]

            payload = {
                "product": {
                    "id": self.PRODUCT_ID,
                    "variants": variants,
                    "options": options,
                    "tags":tags,
                    "template_suffix":template_suffix
                }
            }
            response = requests.put(self.url, json=payload, headers=headers)
            self.set_inventory_metafield(response, 'o4')
        except Exception as e:
            traceback.print_exc()
    
    def product_post(self,COLOR,P,keep=None,qty= None):
        sizes,weights = P.get_weight()
        barcodes, skus = P.get_sku_barcode()

        if keep is not None:
            sizes    = [sizes[i]    for i in keep]
            weights  = [weights[i]  for i in keep]
            skus     = [skus[i]     for i in keep]
            barcodes = [barcodes[i] for i in keep]

        print(f"size: {sizes}, \nweights: {weights}")
        print(f"barcodes: {barcodes}")
        print(f"skus: {skus}")

        full_price,price = P.get_price()
        print(f"full_price: {full_price}")
        print(f"discounted_price: {full_price}")
        tags = P.get_tags()
        tags,template_suffix = tg.additional_tags(tags,sizes,qty)
        if template_suffix == None:
            template_suffix ="default"
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
        variants = data["product"]["variants"]

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
