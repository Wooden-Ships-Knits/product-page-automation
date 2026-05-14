import create_product_underdev
from pp_status import  bulk_produce, update_sheet_hyperlink, update_sheet_value


season = "S26"

# main.py
worksheet, products, production_types, row_numbers = bulk_produce("S26 - TEST2")

if __name__ == "__main__":
    for product, ptype, row_number  in zip(products, production_types, row_numbers):
        single = [product]
        link = None
        processed = False
        try:
            if ptype == "sale sample":
                link = create_product_underdev.create_sale_sample(single, season)
                processed = True
            elif ptype == "unfixed inv":
                link = create_product_underdev.create_unfix(single, season)
                processed = True
            elif ptype == "sale O4":
                link= create_product_underdev.create_04(single, season)
                processed = True
            elif ptype == "sale stock":
                link= create_product_underdev.create_fixed(single, season, sale=True)
                processed = True
            elif ptype == "fixed stock" or ptype == "fixed inv":
                link = create_product_underdev.create_fixed(single, season, sale=False)
                processed = True
        except Exception as e:
            print(f"Failed {product['STYLE']} {product['COLOR']}: {e}")

        if link:
            update_sheet_hyperlink(
                worksheet=worksheet,
                row_number=row_number,
                column_name="CHECK", 
                url=link,
                label="link"
            )
        if processed:
            update_sheet_value(
                worksheet=worksheet,
                row_number=row_number,
                column_name="ACTION",
                value="PP CREATED"
            )
