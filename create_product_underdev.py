Bali_Stock_ID = "35472048176"
Bali_To_Produce_ID = "37977930"
Jillamy_WBPA_ID = "14627995696"
NE_First_Choice_ID = "65178107952"
NE_Sample_ID = "65218150448"
Yarn_Warehouse_ID = "36831821872"
from all_function_list_underdev import Product
import Setup.set_sy
import time
vendor = "Wooden Ships"
TAX_code = "PC040100"
color1, color2, color3 = None,None,None


import requests

def create_sale_sample(products,season):
    print("Processing sale sample product")
    for p in products:
        time.sleep(1)
        product_name = p["STYLE"]
        color_raw = p["COLOR"]
        collection = p["COLLECTION"]    
        print(product_name, "->", color_raw)
        try:
            SKUs=[]
            product = Product(product_name, color_raw, season,collection)
            _, title_seo, desc_seo,_, handle_seo = product.get_seo()
            _, title_page, desc_sale, thread_comp = product.title_and_desc(sample=True)
            size, SKU, stocks = product.ne_sample()
            SKUs.append(SKU)
            
            SKUs[0] += "-S"
            weight_g = product.get_weight()
            tags = product.get_tags(sale=True,sample=True,sas=False,sizes=size)
            # price, compare_at_price = product.get_price()
            price, compare_at_price = 0,0 
            metafield = product.get_meta_chart()
            print(SKUs)
            barcodes = product.get_barcodes(SKUs,sample=True)
            tipe = product.get_type()

        except Exception as e:
            print(f"Skipping {product_name} {color_raw} because of error: {e}")
            continue
        
       
        color_name_sens = color_raw.lower().title()
        url = "https://wooden-ships.myshopify.com/admin/api/2026-01/products.json"
        headers = {
            "X-Shopify-Access-Token": set_sy.get_token(),
            "Content-Type": "application/json"
        }

        # images = []
        # for i in range(13):
        #     image ={
        #     "src": f"https://cdn.shopify.com/s/files/1/1436/4400/files/wooden-ships-knits__{product_name.lower().replace(' ','-')}__{color_raw.lower().replace('/','-')}-{1+i}.webp",
        #     "alt": color_raw.lower().replace("/", "-")
        #     }
        #     images.append(image)
        try:
            product_data = {
                "product": {
                    #SEO
                    "handle":handle_seo,
                    "metafields_global_title_tag": title_seo,
                    "metafields_global_description_tag":desc_seo,
                    #header
                    "title": title_page,
                    "body_html": desc_sale + thread_comp,
                    #right side
                    "vendor": vendor,
                    "product_type": tipe,
                    "tags": tags,
                    "status": "draft",
                    "template_suffix": "sale-item",
                    "published_scope": "web",

                    # main images
                    # "images": product.images(),

                    #meta
                    "metafields": [
                        {
                            "namespace": "avalara",
                            "key": "taxcode",
                            "type": "single_line_text_field",
                            "value": TAX_code
                        },
                            {
                            "namespace": "custom",
                            "key": "size_chart_metafield",  # adjust if needed
                            "value": metafield
                        }
                    ],
                    "variants": [
                        {
                            "option1": "S/M (6-8)",
                            "option2": color_name_sens,
                            "sku": SKUs[0],
                            "price": price,
                            "compare_at_price": compare_at_price,
                            # "inventory_quantity": stocks,
                            "inventory_management": "shopify",
                            "barcode": barcodes[0],
                            "weight": weight_g,
                            "weight_unit": "g"            }
                    ],
                    "options": [
                        {
                            "name": "Size",
                            "values": ["S/M (6-8)"]
                        },
                        {
                            "name": "Color",
                            "values": [color_name_sens]
                        }
                    ]
                }
            }
            
            response = requests.post(url, headers=headers, json=product_data)
            # print("status:", response.status_code)
            # print("body:", response.text)
            # print("json:", response.json())
            # print("x-request-id:", response.headers.get("x-request-id"))
            product = response.json()["product"]
            product_id = product["id"]
        except Exception as e:
            print(e,"try again without image")
            product_data = {
                "product": {
                    #SEO
                    "handle":handle_seo,
                    "metafields_global_title_tag": title_seo,
                    "metafields_global_description_tag":desc_seo,
                    #header
                    "title": title_page,
                    "body_html": desc_sale + thread_comp,
                    #right side
                    "vendor": vendor,
                    "product_type": tipe,
                    "tags": tags,
                    "status": "draft",
                    "template_suffix": "sale-item",
                    "published_scope": "web",

                    # main images
                    # "images": product.images(),

                    #meta
                    "metafields": [
                        {
                            "namespace": "avalara",
                            "key": "taxcode",
                            "type": "single_line_text_field",
                            "value": TAX_code
                        },
                            {
                            "namespace": "custom",
                            "key": "size_chart_metafield",  # adjust if needed
                            "value": metafield
                        }
                    ],
                    "variants": [
                        {
                            "option1": "S/M (6-8)",
                            "option2": color_name_sens,
                            "sku": SKUs[0],
                            "price": price,
                            "compare_at_price": compare_at_price,
                            # "inventory_quantity": stocks,
                            "inventory_management": "shopify",
                            "barcode": barcodes[0],
                            "weight": weight_g,
                            "weight_unit": "g"            }
                    ],
                    "options": [
                        {
                            "name": "Size",
                            "values": ["S/M (6-8)"]
                        },
                        {
                            "name": "Color",
                            "values": [color_name_sens]
                        }
                    ]
                }
            }
            
            response = requests.post(url, headers=headers, json=product_data)
            # print("status:", response.status_code)
            # print("body:", response.text)
            # print("json:", response.json())
            # print("x-request-id:", response.headers.get("x-request-id"))

            product = response.json()["product"]
            product_id = product["id"]
        set_sy.publish_to_all_channels(product_id)

        set_sy.collection_release(collection, product_id, headers)

        if response.status_code != 201:
            print("Product creation failed:", response.text)
            continue

        data = response.json()
        import json

        # print(json.dumps(data, indent=2, ensure_ascii=False))

        inventory_item_id = data["product"]["variants"][0]["inventory_item_id"]
        # print("Inventory Item ID:", inventory_item_id)
        inventory_data = {
        "location_id": NE_Sample_ID,
        "inventory_item_id": inventory_item_id,
        "available": stocks
        }

        requests.post(
            f"https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
            headers=headers,
            json=inventory_data
        )
        # inventory_response = requests.post(
        #     f"https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
        #     headers=headers,
        #     json=inventory_data
        # )

        # print(inventory_response.status_code)
        # print(inventory_response.text)

        data = response.json()

        variant_id = data["product"]["variants"][0]["id"]

        # print("Variant ID:", variant_id)

        metafield_data = {
        "metafield": {
            "namespace": "avalara",
            "key": "taxcode",
            "type": "single_line_text_field",
            "value": TAX_code,
            "owner_id": variant_id,
            "owner_resource": "variant"
        }
        }

        metafield_response = requests.post(
            "https://wooden-ships.myshopify.com/admin/api/2026-01/metafields.json",
            headers=headers,
            json=metafield_data
        )

        # print("Metafield status:", metafield_response.status_code)
        # print(metafield_response.text)
        
        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
    return link

def create_fixed(products,season,sale):
    link = None
    if sale== True:
        print("Processing sale stock product")
    else: print("Processing fixed inventory product")
    for collection,product_name, color_raw in products:
        size_numbers = ["(2-4)","(6-8)","(10-12)","(14-16)"]
        size_label_map = {
        "X/S": "(2-4)",
        "S/M": "(6-8)",
        "M/L": "(10-12)",
        "X/L": "(14-16)",
}
        for p in products:
            time.sleep(1)
            product_name = p["STYLE"]
            color_raw = p["COLOR"]
            color_raw.replace(" ","")
            print(color_raw)
            collection = p["COLLECTION"]    
            print(product_name, "->", color_raw)
            color_name_sens = color_raw.lower().title()
            url = "https://wooden-ships.myshopify.com/admin/api/2026-01/products.json"
            headers = {
                "X-Shopify-Access-Token": set_sy.get_token(),
                "Content-Type": "application/json"
            }
            compare_at_price = 0
            try: 
                product = Product(product_name,color_raw,season,collection)
                if sale == True:
                    _,title_seo,desc_seo,_,handle_seo = product.get_seo()
                    _,title_page,sale_desc,thread_comp = product.title_and_desc(sample=False)
                    price, compare_at_price = product.get_price()
                else:
                    title_seo,_, desc_seo, handle_seo,_ = product.get_seo()
                    title_page,_,_,thread_comp = product.title_and_desc(sample=False)
                    price = product.get_fullprice()
                ne_data = product.ne_first_choice()
                bali_data = product.bali_stocks()
                sizes_b= []
                sizes_n = []
                SKUs_n = []
                SKUs_b = []
                sku_by_size = {}
                stocks_b = None
                stocks_n = None
                if ne_data != None:
                    sizes_n, SKUs_n, stocks_n = ne_data
                    print(ne_data)
                if bali_data != None:
                    sizes_b, SKUs_b, stocks_b = bali_data
                    print(bali_data)
                order = ["X/S", "S/M", "M/L", "X/L"]
                sizes = [s for s in order if s in (sizes_b + sizes_n)]
                all_skus = SKUs_b + SKUs_n
                for sku in all_skus:
                    size = sku.split("-")[-1]   # gets {size} from {code}-{color}-{size}
                    if size not in sku_by_size: # keep first one found
                        sku_by_size[size] = sku
                
                
                SKUs = [sku_by_size[s] for s in order if s in sku_by_size]
                print(SKUs)
                ###still need barcode code if the product is only on bali stocks
                old = False
                weight_gs, old = product.get_weight_multiple(sizes)
                barcodes = product.get_barcodes(SKUs,sample=False)
                tags = product.get_tags(sale,sample=False,sas=False,sizes=sizes)
                metafield = product.get_meta_chart()
                tipe = product.get_type()
            except Exception as e:
                print(f"{product_name} - {color_raw} is skipped due to", e)
                continue
            default_size = ["X/S","S/M", "M/L", "X/L"]
            rebarcodes = []
            for i, size in enumerate(sizes):
                for j, k in enumerate(default_size):
                    if sizes[i] == k:
                        rebarcodes.append(barcodes[i]) 
            print("rearrange",SKUs)
            print("rearrange:" ,rebarcodes)
            print("rearrange",weight_gs)
            variants = [] 
            if old == True:
                for i, size in enumerate(sizes):
                    variants.append({
                    "option1": f"{size} {size_label_map.get(size, '')}".strip(),
                    "option2": color_name_sens,
                    "sku": SKUs[i],
                    "price": price,
                    "compare_at_price": compare_at_price,
                    "inventory_management": "shopify",
                    "barcode": barcodes[i],

                    "weight_unit": "g",
                })
            else:

                print(sizes, size_numbers, SKUs, barcodes,weight_gs)
                for i, size in enumerate(sizes):
                    print(sizes[i],size_numbers[i], SKUs[i], barcodes[i],weight_gs[i])
                    variants.append({
                    "option1": f"{size} {size_label_map.get(size, '')}".strip(),
                    "option2": color_name_sens,
                    "sku": SKUs[i],
                    "price": price,
                    "compare_at_price": compare_at_price,
                    "inventory_management": "shopify",
                    "barcode": barcodes[i],
                    "weight": weight_gs[i],
                    "weight_unit": "g",
                })
            options = [
                {
                    "name": "Size",
                    "values": [f"{size} {size_label_map.get(size, '')}".strip() for size in sizes]
                },
                {
                    "name": "Color",
                    "values": [color_name_sens]
                }
            ]
            if sale == True:
                template_suffix = "sale-item"
            else:
                template_suffix = "default"



            if sale == True:
                product_data = {
                "product": {
                    #SEO
                    "handle":handle_seo,
                    "metafields_global_title_tag": title_seo,
                    "metafields_global_description_tag":desc_seo,
                    #header
                    "title": title_page,
                    "body_html": sale_desc+thread_comp,
                    #right side
                    "vendor": vendor,
                    "product_type": tipe,
                    "tags": tags,
                    "status": "draft",
                    "template_suffix": template_suffix,
                    "published_scope": "web",

                    #images
                    # "images":product.images(),

                    #meta
                    "metafields": [
                        {
                            "namespace": "avalara",
                            "key": "taxcode",
                            "type": "single_line_text_field",
                            "value": TAX_code
                        },
                            {
                            "namespace": "custom",
                            "key": "size_chart_metafield",  
                            "value": metafield
                        }
                    ],
                    "variants": variants,
                    "options": options
                }
            }
            else:
                product_data = {
                "product": {
                    #SEO
                    "handle":handle_seo,
                    "metafields_global_title_tag": title_seo,
                    "metafields_global_description_tag":desc_seo,
                    #header
                    "title": title_page,
                    "body_html": thread_comp,
                    #right side
                    "vendor": vendor,
                    "product_type": tipe,
                    "tags": tags,
                    "status": "draft",
                    "template_suffix": template_suffix,
                    "published_scope": "web",

                    #images
                    # "images":images,

                    #meta
                    "metafields": [
                        {
                            "namespace": "avalara",
                            "key": "taxcode",
                            "type": "single_line_text_field",
                            "value": TAX_code
                        },
                            {
                            "namespace": "custom",
                            "key": "size_chart_metafield",  
                            "value": metafield
                        }
                    ],
                    "variants": variants,
                    "options": options
                }
            }
            print("finish set up product")
            response = requests.post(url, headers=headers, json=product_data)
            product = response.json()["product"]
            product_id = product["id"]
            data = response.json()
            
            set_sy.publish_to_all_channels(product_id)

            set_sy.collection_release(collection, product_id, headers)

            if response.status_code != 201:
                print("Product creation failed:", response.text)
                continue


            print("CP 1!")
            if ne_data != None:
                for i, variant in enumerate(data["product"]["variants"]):
                    inventory_item_id = variant["inventory_item_id"]
                    size = variant["option1"].split(" ")[0] # or normalize if option1 includes extra text
                    qty = stocks_n[i]

                    inventory_data = {
                        "location_id": NE_First_Choice_ID,
                        "inventory_item_id": inventory_item_id,
                        "available": qty
                    }
                    requests.post(
                    f"https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
                    headers=headers,
                    json=inventory_data
                )
            if bali_data != None:
                for variant in data["product"]["variants"]:
                    inventory_item_id = variant["inventory_item_id"]
                    size = variant["option1"].split(" ")[0]  # or normalize if option1 includes extra text
                    qty = stocks_b[i]

                    inventory_data = {
                        "location_id": Bali_Stock_ID,
                        "inventory_item_id": inventory_item_id,
                        "available": qty
                    }
                    requests.post(
                    f"https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
                    headers=headers,
                    json=inventory_data
                )

            # requests.post(
            #     f"https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
            #     headers=headers,
            #     json=inventory_data
            # )

            data = response.json()

            for variant in data["product"]["variants"]:
                variant_id = variant["id"]


            # print("Variant ID:", variant_id)

                metafield_data = {
                "metafield": {
                    "namespace": "avalara",
                    "key": "taxcode",
                    "type": "single_line_text_field",
                    "value": TAX_code,
                    "owner_id": variant_id,
                    "owner_resource": "variant"
                }
                }

                requests.post(
                    "https://wooden-ships.myshopify.com/admin/api/2026-01/metafields.json",
                    headers=headers,
                    json=metafield_data
                )
                link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"

    return link

def create_unfix(products, season):
    print("Processing unfixed product")
    for p in products:
        size_numbers = ["(2-4)","(6-8)","(10-12)","(14-16)"]
        time.sleep(1)
        product_name = p["STYLE"]
        color_raw = p["COLOR"]
        collection = p["COLLECTION"]    
        print(product_name, "->", color_raw)
        color_name_sens = color_raw.lower().title()
        url = "https://wooden-ships.myshopify.com/admin/api/2026-01/products.json"
        headers = {
            "X-Shopify-Access-Token": set_sy.get_token(),
            "Content-Type": "application/json"
        }
        try:
            product = Product(product_name, color_raw, season,collection)
            title_seo,_, desc_seo, handle_seo,_ = product.get_seo()
            title_page,_,_,thread_comp = product.title_and_desc(sample=False)
            barcodes, sizes, SKUs = product.unfix()
            print(sizes)
            weight_gs, _ = product.get_weight_multiple(sizes)
            tags = product.get_tags(sale=False, sample=False, sas=False, sizes=sizes)
            price = product.get_fullprice()
            metafield = product.get_meta_chart()
            tipe = product.get_type()
            
        except Exception as e:
            print(f"{product_name} - {color_raw} is skipped due to ",e)
            continue

        variants = []
        print("processing variant")
        for i, size in enumerate(sizes):
            variants.append({
            "option1": f"{sizes[i]} {size_numbers[i]}",
            "option2": color_name_sens,
            "sku": SKUs[i],
            "price": price,
            "inventory_management": "shopify",
            "barcode": barcodes[i],
            "weight": weight_gs[i],
            "weight_unit": "g",
        })
        print("processing options")
        options = [
            {
                "name": "Size",
                "values": [f"{size} {size_numbers[i]}" for i, size in enumerate(sizes)]
            },
            {
                "name": "Color",
                "values": [color_name_sens]
            }
        ]

        # images = []
        # for i in range(13):
        #     image ={
        #     "src": f"https://cdn.shopify.com/s/files/1/1436/4400/files/wooden-ships-knits__{product_name.lower().replace(' ','-')}__{color_raw.lower().replace('/','-')}-{1+i}.webp",
        #     "alt": color_raw.lower().replace("/", "-")
        #     }
        #     images.append(image)
        
        print("processing product")
        product_data = {
            "product": {
                #SEO
                "handle":handle_seo,
                "metafields_global_title_tag": title_seo,
                "metafields_global_description_tag":desc_seo,
                #header
                "title": title_page,
                "body_html": thread_comp,
                #right side
                "vendor": vendor,
                "product_type": tipe,
                "tags": tags,
                "status": "draft",
                "published_scope": "web",
                
                #images
                # "images":product.images(),
                
                #meta
                "metafields": [
                    {
                        "namespace": "avalara",
                        "key": "taxcode",
                        "type": "single_line_text_field",
                        "value": TAX_code
                    },
                        {
                        "namespace": "custom",
                        "key": "size_chart_metafield",  
                        "value": metafield
                    }
                ],
                "variants": variants,
                "options": options
            }
        }
        response = requests.post(url, headers=headers, json=product_data)
        product = response.json()["product"]
        product_id = product["id"]

        set_sy.publish_to_all_channels(product_id)
        set_sy.collection_release(collection,product_id,headers)

        if response.status_code != 201:
            print("Product creation failed:", response.text)
            continue

        data = response.json()
        for variant in data["product"]["variants"]:
            inventory_item_id = variant["inventory_item_id"]
            inventory_data = {
                "location_id": Bali_To_Produce_ID,
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
                "value": TAX_code,
                "owner_id": variant_id,
                "owner_resource": "variant"
            }
            }

            requests.post(
                "https://wooden-ships.myshopify.com/admin/api/2026-01/metafields.json",
                headers=headers,
                json=metafield_data
            )           
            link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
    return link

def create_04(products, season):
    print("Processing sale O4 product")
    for p in products:
        size_numbers = ["(2-4)","(6-8)","(10-12)","(14-16)"]
        time.sleep(1)
        product_name = p["STYLE"]
        color_raw = p["COLOR"]
        collection = p["COLLECTION"]    
        print(product_name, "->", color_raw)
        color_name_sens = color_raw.lower().title()
        url = "https://wooden-ships.myshopify.com/admin/api/2026-01/products.json"
        headers = {
            "X-Shopify-Access-Token": set_sy.get_token(),
            "Content-Type": "application/json"
        }
        try:
            product = Product(product_name, color_raw, season,collection)
            # title_seo,_, desc_seo, handle_seo,_ = product.get_seo()
            _,title_seo, desc_seo, _,handle_seo = product.get_seo()
            # title_page,_,thread_comp = product.title_and_desc()
            _,title_page,sale_desc,thread_comp = product.title_and_desc(sample=False)
            barcodes, sizes, SKUs = product.unfix()
            weight_gs, _ = product.get_weight_multiple(sizes)
            tags = product.get_tags(sale=True,sample=False,sas=False,sizes=sizes)
            price, compare_at_price = product.get_price()
            metafield = product.get_meta_chart()
            tipe = product.get_type()
        except Exception as e:
            print(f"{product_name} - {color_raw} is skipped due to ",e)
            continue
        variants = []
        for i, size in enumerate(sizes):
            variants.append({
            "option1": f"{sizes[i]} {size_numbers[i]}",
            "option2": color_name_sens,
            "sku": SKUs[i],
            "price": price,
            "compare_at_price": compare_at_price,
            "inventory_management": "shopify",
            "barcode": barcodes[i],
            "weight": weight_gs[i],
            "weight_unit": "g",
        })
        options = []
        for i, size in enumerate(sizes):
            options.append=(
                {
                "name": "Size",
                "values": [f"{sizes[i]} {size_numbers[i]}"]
            },
            {
                "name": "Color",
                "values": [color_name_sens]
            }
            )

        images = []
        for i in range(13):
            image ={
            "src": f"https://cdn.shopify.com/s/files/1/1436/4400/files/wooden-ships-knits__{product_name.lower().replace(' ','-')}__{color_raw.lower().replace('/','-')}-{1+i}.webp",
            "alt": color_raw.lower().replace("/", "-")
            }
            images.append(image)
        

        product_data = {
            "product": {
                #SEO
                "handle":handle_seo,
                "metafields_global_title_tag": title_seo,
                "metafields_global_description_tag":desc_seo,
                #header
                "title": title_page,
                "body_html": sale_desc + thread_comp,
                #right side
                "vendor": vendor,
                "product_type": tipe,
                "tags": tags,
                "status": "draft",
                "template_suffix": "sale-item",
                "published_scope": "web",

                #images
                # "images":images,

                #meta
                "metafields": [
                    {
                        "namespace": "avalara",
                        "key": "taxcode",
                        "type": "single_line_text_field",
                        "value": TAX_code
                    },
                        {
                        "namespace": "custom",
                        "key": "size_chart_metafield",  
                        "value": metafield
                    }
                ],
                "variants": variants,
                "options": [
            
                ]
            }
        }
        response = requests.post(url, headers=headers, json=product_data)
        product = response.json()["product"]
        product_id = product["id"]

        set_sy.publish_to_all_channels(product_id)

        set_sy.collection_release(collection,product_id,headers)
        
        if response.status_code != 201:
            print("Product creation failed:", response.text)
            continue

        data = response.json()
        inventory_item_id = data["product"]["variants"][0]["inventory_item_id"]
        # print("Inventory Item ID:", inventory_item_id)
        inventory_data = {
        "location_id": NE_Sample_ID,
        "inventory_item_id": inventory_item_id,
        "available": 5000
        }

        requests.post(
            f"https://wooden-ships.myshopify.com/admin/api/2026-01/inventory_levels/set.json",
            headers=headers,
            json=inventory_data
        )

        data = response.json()

        variant_id = data["product"]["variants"][0]["id"]

        # print("Variant ID:", variant_id)

        metafield_data = {
        "metafield": {
            "namespace": "avalara",
            "key": "taxcode",
            "type": "single_line_text_field",
            "value": TAX_code,
            "owner_id": variant_id,
            "owner_resource": "variant"
        }
        }

        requests.post(
            "https://wooden-ships.myshopify.com/admin/api/2026-01/metafields.json",
            headers=headers,
            json=metafield_data
        ) 


        link = f"https://admin.shopify.com/store/wooden-ships/products/{product_id}"
    return link
