import Setup.fetch_product_id_new as fetch_id
import Setup.fetch_images_name_link as fetch_image
import fetch_to_product_page as ftp
import pandas as pd
import create_pp
import update_pp
import post_update_decision as PUD
from Setup import setup
from config.varia import data, season
from pathlib import Path
sheet = setup.sheet
SEASON = season   # driven by config/varia.py (and the interface's launcher_params.json override)



def production(data):
    out_file = Path("Output/product_link.txt")
    out_file.parent.mkdir(exist_ok=True)
    if out_file.exists():
        out_file.unlink()          # clear stale link from a previous run

    for d in data:
        STYLE = d['Styles'].upper()
        COLORS = d['Colors']
        COLOR = d['Colors'][0]
        production_type = d['Production']

        if production_type == 'fixed' or production_type == "unfix":
            FP_DC = "FP"
            SALE = False
        else:
            FP_DC = "DC"
            SALE = True

        create_new, product_id, status, description = PUD.decide(STYLE, COLOR, FP_DC)

        print("=" * 50)
        print(create_new, product_id, status)
        print(description)

        link = None

        if status.upper() == "DRAFT":
            if create_new == True:
                print(f"{STYLE} - {COLOR} - {SALE}")
                C = create_pp.CreatePP(STYLE, COLORS, SEASON, SALE, description)
                if production_type == 'unfix':
                    link, product_id = C.create_unfix()
                elif production_type == 'fixed':
                    link, product_id = C.create_fixed()
                elif production_type == 'sale_stock':
                    link, product_id = C.create_sale_stock()
                elif production_type == 'o4':
                    link, product_id = C.create_o4()
                elif production_type == 'sample':
                    link, product_id = C.create_sample()
                # PP SY LIST row for the new product is added by webhook_receiver.py

            elif create_new == False:
                U = update_pp.UpdatePP(STYLE, COLORS, SEASON, product_id, SALE, description)
                if production_type == 'unfix':
                    link = U.update_unfix()
                elif production_type == 'fixed':
                    link = U.update_fixed()
                elif production_type == 'sale_stock':
                    link = U.update_sale_stock()
                elif production_type == 'o4':
                    link = U.update_o4()
                elif production_type == 'sample':
                    link = U.update_sample()

        else:
            print(f'{STYLE} - {COLOR} not found or an active pp. skipping')

        print(link)
        if link:
            out_file.write_text(link, encoding="utf-8")   # persist for the launcher

if __name__ == "__main__":
    production(data)
