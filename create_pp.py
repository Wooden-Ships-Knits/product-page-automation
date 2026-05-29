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
    def __init__(self,STYLE,COLOR,SEASON,SALE, DESCRIPTION):
        self.STYLE= STYLE
        self.COLOR = COLOR
        self.SEASON = SEASON
        self.sale = SALE
        self.description = DESCRIPTION

    def _to_int(self,v):
        try:
            return int(str(v).strip() or 0)
        except (TypeError, ValueError):
            return 0

    def _attach_variant_image(self, product):
        images = product.get("images", [])
        variants = product.get("variants", [])
        if not images or not variants:
            return
        image_id = images[0]["id"]
        payload = {
            "product": {
                "id": product["id"],
                "variants": [{"id": v["id"], "image_id": image_id} for v in variants],
            }
        }
        requests.put(
            f"https://wooden-ships.myshopify.com/admin/api/2024-01/products/{product['id']}.json",
            headers=headers, json=payload,
        )

    def create_unfix(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=False, sas=False)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            product_data = self.product_post(P)

            response = requests.post(product_url, headers=headers, json=product_data)
            if response.status_code != 201:
                print("Product creation failed:", response.text)
                return None, None
            product = response.json()["product"]
            product_id = product["id"]
            self._attach_variant_image(product)

            set_sy.publish_to_all_channels(product_id, sale=False)

            self.set_inventory_metafield(response, 'unfix')
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def create_fixed(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=False, sas=False)
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

            product_data = self.product_post(P, keep=keep, qty=total_qty, skus=skus_chosen, barcodes=barcodes_chosen)

            response = requests.post(product_url, headers=headers, json=product_data)
            if response.status_code != 201:
                print("Product creation failed:", response.text)
                return None, None
            product = response.json()["product"]
            product_id = product["id"]
            self._attach_variant_image(product)

            set_sy.publish_to_all_channels(product_id, sale=False)

            self.set_inventory_metafield(response, 'fixed', qty_ne=qty_ne, qty_ba=qty_ba)
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def create_sample(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=True, sale=True, sas=False)
            qty_sample = P.get_sample_qty()
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            _, sizes = P.get_metachart()
            if 'S/M' not in sizes:
                print(f"S/M not found in sizes for {self.STYLE} {self.COLOR} — skipping sample.")
                return None, None
            keep = [sizes.index('S/M')]
            product_data = self.product_post(P, keep=keep, qty=qty_sample)

            response = requests.post(product_url, headers=headers, json=product_data)
            if response.status_code != 201:
                print("Product creation failed:", response.text)
                return None, None
            product = response.json()["product"]
            product_id = product["id"]
            self._attach_variant_image(product)

            set_sy.publish_to_all_channels(product_id)

            self.set_inventory_metafield(response, 'sample', qty_sample=qty_sample)
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def create_sale_stock(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=True, sas=False)
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
            product_data = self.product_post(P, keep=keep, qty=total_qty, skus=skus_chosen, barcodes=barcodes_chosen)

            response = requests.post(product_url, headers=headers, json=product_data)
            if response.status_code != 201:
                print("Product creation failed:", response.text)
                return None, None
            product = response.json()["product"]
            product_id = product["id"]
            self._attach_variant_image(product)

            set_sy.publish_to_all_channels(product_id)

            self.set_inventory_metafield(response, 'sale_stock', qty_ne=qty_ne, qty_ba=qty_ba)
        except Exception:
            traceback.print_exc()
            return None, None
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
        return link, product_id
    
    def create_o4(self):
        product_id = None
        try:
            P= ProductInfo(self.STYLE,self.COLOR,self.SEASON,sample=False, sale=True, sas=True)
            print(f"ProductInfo created: STYLE={self.STYLE}, COLOR={self.COLOR}, SEASON={self.SEASON}")
            product_data = self.product_post(P)

            response = requests.post(product_url, headers=headers, json=product_data)
            if response.status_code != 201:
                print("Product creation failed:", response.text)
                return None, None
            product = response.json()["product"]
            product_id = product["id"]
            self._attach_variant_image(product)

            set_sy.publish_to_all_channels(product_id)

            self.set_inventory_metafield(response, 'o4')
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
        print(f"full_price: {full_price}")
        print(f"discounted_price: {full_price}")
        
        variants = []
        print("processing variant")

        for i, size in enumerate(sizes):
            variants.append({
            "option1": f"{size} {SIZE_RANGE[size]}",
            "option2": self.COLOR.title(),
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
            "values": [self.COLOR.title()]
        }
        ]

        product_data = {
            "product": {
                #SEO
                "handle":url,
                "metafields_global_title_tag": page_title.replace("/"," "),
                "metafields_global_description_tag":meta_desc,
                #header
                "title": title_page,
                "body_html": sale_desc + f"<p>{self.description}</p>" + thread_comp,
                #right side
                "vendor": "Wooden Ships",
                "product_type": _type,
                "tags": tags,
                "status": "draft",
                "template_suffix":template_suffix,
                "published_scope": "web",
                "images": P.get_image(),
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
                "variants": variants,
                "options": options
            }
        }

        return product_data

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
