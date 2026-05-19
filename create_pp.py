from fetch_to_product_page import ProductInfo
import requests
from Setup import set_sy,setup
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / "Setup/.env", override=True)

headers = setup.HEADERS
product_url = set_sy.product_url

def create_unfix(STYLE,COLOR,SEASON):
    size_numbers = ["(2-4)","(6-8)","(10-12)","(14-16)"]
    try:

        P= ProductInfo(STYLE,COLOR,SEASON,sample=False, sale=False, sas=False)
        print(f"ProductInfo created: STYLE={STYLE}, COLOR={COLOR}, SEASON={SEASON}")

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
        print(f"size: {sizes}, \nweights: {weights}")

        barcodes, skus = P.get_sku_barcode()
        print(f"barcodes: {barcodes}")
        print(f"skus: {skus}")

        metachart = P.get_metachart()
        print(f"metachart: {metachart}")

        tags = P.get_tags()
        print(f"tags: {tags}")

        _type = P.get_type()
        print(f"type: {_type}")

        full_price,_ = P.get_price()
        print(f"full_price: {full_price}")
    except Exception as e:
        print(e)

    variants = []
    print("processing variant")
    for i, size in enumerate(sizes):
        variants.append({
        "option1": f"{sizes[i]} {size_numbers[i]}",
        "option2": COLOR.title(),
        "sku": skus[i],
        "price": full_price,
        "inventory_management": "shopify",
        "barcode": barcodes[i],
        "weight": weights[i],
        "weight_unit": "g",
    })

        options = [
            {
                "name": "Size",
                "values": [f"{size} {size_numbers[i]}" for i, size in enumerate(sizes)]
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

            #images
            # "images":images,

            #meta
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
    response = requests.post(product_url, headers=headers, json=product_data)
    product = response.json()["product"]
    product_id = product["id"]

    set_sy.publish_to_all_channels(product_id)
    # set_sy.collection_release(collection,product_id,headers)

    if response.status_code != 201:
        print("Product creation failed:", response.text)
        # continue

    data = response.json()
    for variant in data["product"]["variants"]:
        inventory_item_id = variant["inventory_item_id"]
        inventory_data = {
            "location_id": os.getenv("Bali_To_Produce_ID"),
            "inventory_item_id": inventory_item_id,
            "available": 5000
        }

        requests.post(
            "https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
            headers=headers,
            json=inventory_data
        )


    data = response.json()
    for variant in data["product"]["variants"]:
        variant_id = variant["id"]

        # print("Variant ID:", variant_id)

        metafield_data = {
        "metafield": {
            "namespace": "avalara",
            "key": "taxcode",
            "type": "single_line_text_field",
            "value": "PC040100",
            "owner_id": variant_id,
            "owner_resource": "variant"
        }
        }

        requests.post(
            "https://wooden-ships.myshopify.com/admin/api/2026-01/metafields.json",
            headers=headers,
            json=metafield_data
        )           