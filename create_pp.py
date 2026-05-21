from fetch_to_product_page import ProductInfo
import requests
from Setup import set_sy,setup
import os
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


def _to_int(v):
    try:
        return int(str(v).strip() or 0)
    except (TypeError, ValueError):
        return 0


def create_unfix(STYLE,COLOR,SEASON):
    try:
        P= ProductInfo(STYLE,COLOR,SEASON,sample=False, sale=False, sas=False)
        print(f"ProductInfo created: STYLE={STYLE}, COLOR={COLOR}, SEASON={SEASON}")
        product_data = product_post(STYLE,COLOR,SEASON,P)
    except Exception as e:
        print(e)

    response = requests.post(product_url, headers=headers, json=product_data)
    product = response.json()["product"]
    product_id = product["id"]

    set_sy.publish_to_all_channels(product_id)

    if response.status_code != 201:
        print("Product creation failed:", response.text)
        # continue

    set_inventory_metafield(response,'unfix')

def create_fixed(STYLE,COLOR,SEASON):
    try:
        P= ProductInfo(STYLE,COLOR,SEASON,sample=False, sale=False, sas=False)
        print(f"ProductInfo created: STYLE={STYLE}, COLOR={COLOR}, SEASON={SEASON}")
        qty_ne = P.get_NE_qty()
        qty_ba = P.get_BALI_qty()
        combined = [_to_int(a) + _to_int(b) for a, b in zip(qty_ne, qty_ba)]
        keep = [i for i, q in enumerate(combined) if q > 0]
        if not keep:
            print(f"No stock for {STYLE} {COLOR} — skipping fixed product.")
            return
        qty_ne = [qty_ne[i] for i in keep]
        qty_ba = [qty_ba[i] for i in keep]
        product_data = product_post(STYLE,COLOR,SEASON,P,keep=keep)
    except Exception as e:
        print(e)

    response = requests.post(product_url, headers=headers, json=product_data)
    product = response.json()["product"]
    product_id = product["id"]

    set_sy.publish_to_all_channels(product_id)

    if response.status_code != 201:
        print("Product creation failed:", response.text)
        # continue

    set_inventory_metafield(response, 'fixed', qty_ne=qty_ne, qty_ba=qty_ba)

def create_sample(STYLE,COLOR,SEASON):
    try:
        P= ProductInfo(STYLE,COLOR,SEASON,sample=True, sale=True, sas=False)
        print(f"ProductInfo created: STYLE={STYLE}, COLOR={COLOR}, SEASON={SEASON}")
        product_data = product_post(STYLE,COLOR,SEASON,P)
    except Exception as e:
        raise print(e)

    response = requests.post(product_url, headers=headers, json=product_data)
    product = response.json()["product"]
    product_id = product["id"]

    set_sy.publish_to_all_channels(product_id)

    if response.status_code != 201:
        print("Product creation failed:", response.text)
        # continue

    set_inventory_metafield(response,'sample')

def create_sale_stock(STYLE,COLOR,SEASON):
    try:
        P= ProductInfo(STYLE,COLOR,SEASON,sample=False, sale=True, sas=False)
        print(f"ProductInfo created: STYLE={STYLE}, COLOR={COLOR}, SEASON={SEASON}")
        qty_ne = P.get_NE_qty()
        qty_ba = P.get_BALI_qty()
        combined = [_to_int(a) + _to_int(b) for a, b in zip(qty_ne, qty_ba)]
        keep = [i for i, q in enumerate(combined) if q > 0]
        if not keep:
            print(f"No stock for {STYLE} {COLOR} — skipping sale_stock product.")
            return
        qty_ne = [qty_ne[i] for i in keep]
        qty_ba = [qty_ba[i] for i in keep]
        product_data = product_post(STYLE,COLOR,SEASON,P,keep=keep)
    except Exception as e:
        raise print(e)

    response = requests.post(product_url, headers=headers, json=product_data)
    product = response.json()["product"]
    product_id = product["id"]

    set_sy.publish_to_all_channels(product_id)

    if response.status_code != 201:
        print("Product creation failed:", response.text)
        # continue

    set_inventory_metafield(response, 'sale_stock', qty_ne=qty_ne, qty_ba=qty_ba)

def create_o4(STYLE,COLOR,SEASON):
    try:
        P= ProductInfo(STYLE,COLOR,SEASON,sample=False, sale=True, sas=True)
        print(f"ProductInfo created: STYLE={STYLE}, COLOR={COLOR}, SEASON={SEASON}")
        product_data = product_post(STYLE,COLOR,SEASON,P)
    except Exception as e:
        raise print(e)

    response = requests.post(product_url, headers=headers, json=product_data)
    product = response.json()["product"]
    product_id = product["id"]

    set_sy.publish_to_all_channels(product_id)

    if response.status_code != 201:
        print("Product creation failed:", response.text)
        # continue

    set_inventory_metafield(response,'O4')

def product_post(STYLE,COLOR,SEASON,P,keep=None):
    title_page, sale_title_page, sale_desc, thread_comp = P.title_and_desc()
    print(f"title_page: {title_page}")
    print(f"sale_title_page: {sale_title_page}")
    print(f"sale_desc: {sale_desc}")
    print(f"thread_comp: {thread_comp}")

    page_title, meta_desc, url = P.get_SEL()
    print(f"page_title: {page_title}")
    print(f"meta_desc: {meta_desc}")
    print(f"url: {url}")

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

    metachart = P.get_metachart()
    print(f"metachart: {metachart}")

    tags = P.get_tags()
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

    product_data = {
        "product": {
            #SEO
            "handle":url,
            "metafields_global_title_tag": page_title.replace("/"," "),
            "metafields_global_description_tag":meta_desc,
            #header
            "title": title_page,
            "body_html":thread_comp,
            #right side
            "vendor": "Wooden Ships",
            "product_type": _type,
            "tags": tags,
            "status": "draft",
            "published_scope": "web",

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

def set_inventory_metafield(response, production_type, qty_ne=None, qty_ba=None):
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
