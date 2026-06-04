import Setup.fetch_product_id_new as fetch_id
import Setup.fetch_images_name_link as fetch_image
import fetch_to_product_page as ftp
import pandas as pd
import create_pp
import update_pp
import post_update_decision as PUD
from Setup import setup
sheet = setup.sheet
SEASON = "26 Spring"

data = [
    {
    # "Styles": "NEWPORT STRIPED TANK COTTON".upper(), 
    # "Colors": [
    #     "TWILIGHT SKY/BREAKER WHITE"
    #     ], 
    # "Production": "sample" 
    #     },
    # {
    "Styles": "CROP BOYFRIEND CREW COTTON".upper(), 
    "Colors": [
        "REAL RED"
        ], 
    "Production": "fixed" 
        },
    # {
    # "Styles": "ANNA TEE CHUNKY TOP COTTON".upper(), 
    # "Colors": [
    #     "BREAKER WHITE"
    #     ], 
    # "Production": "fixed" 
    #     },
    # {
    # "Styles": "ANNA TEE CHUNKY TOP COTTON".upper(), 
    # "Colors": [
    #     "BLUE WIND"
    #     ], 
    # "Production": "fixed" 
    #     },
]


def production(data):
    styles = []
    colors = []
    product_ids = []
    FP_DCs = []

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

                if link is not None:
                    styles.append(STYLE)
                    colors.append(COLOR)
                    FP_DCs.append(FP_DC)
                    product_ids.append(product_id)

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

    if styles:
        values = setup._get_sheet_values(
            sheet_id="1CX6tjxos0N2p_YRmrgo6sA7KSPM5bZnBdyaQZuJWoCk",
            worksheet_name='PP SY LIST',
            use_all_values=True
        )
        df = pd.DataFrame(values[1:], columns=values[0])
        df = df[df['Style'].fillna('').astype(str).str.strip() == ""]
        if df.empty:
            print("PP SY LIST has no empty Style row to append to — aborting write")
        else:
            start_idx = df.index[0]
            new_rows = [
                [style, color, pid, "DRAFT", fpdc]
                for style, color, pid, fpdc in zip(styles, colors, product_ids, FP_DCs)
            ]
            sheet.values().update(
                spreadsheetId="1CX6tjxos0N2p_YRmrgo6sA7KSPM5bZnBdyaQZuJWoCk",
                range=f"'PP SY LIST'!A{start_idx + 2}",
                valueInputOption="RAW",
                body={"values": new_rows}
            ).execute()


if __name__ == "__main__":
    fetch_id.fetch()
    fetch_image.list_shop_files()
    production(data)
