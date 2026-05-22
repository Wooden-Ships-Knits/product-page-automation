"""
Integrate with Master Grid of Return
https://docs.google.com/spreadsheets/d/1MJZVuYaQ2u512pgTJm79CJbVzSe7C5VhrJ1gOfqi8oo/edit?pli=1&gid=1799346438#gid=1799346438
"""
from pathlib import Path
from dotenv import load_dotenv
import traceback
load_dotenv(Path(__file__).parent / "Setup/.env", override=True)
import os
import pandas as pd
from Setup import set_sy,setup
import update_pp
import post_update_decision as PUD
from datetime import date
sheet = setup.sheet

worksheet_name = f'{date.today().strftime("%d %B, %Y")}'

values = setup._get_sheet_values(
        sheet_id=os.getenv("RETURN_ID"),
    worksheet_name = worksheet_name,
    use_all_values=True
)
try:
    dfs = pd.DataFrame(values[6:],columns=values[5])

    zz_columns = dfs.columns[dfs.columns.str.contains("ZZ")]

    dfs = dfs[~(dfs[zz_columns] == "ZZ").any(axis=1)]

    def _first(x):
        return x.iloc[0] if hasattr(x, 'iloc') else x

    for idx, row in dfs.iterrows():
        sheet_row = idx + 7 
        STYLE = _first(row['Style']).strip()
        COLOR = _first(row['Color']).strip()
        print(f'processing {STYLE} - {COLOR}')
        SEASON = "26 Spring"
        added_to_fp = str(_first(row["Added to full price"])).strip().lower()
        added_to_sale = str(_first(row["Added to sale"])).strip().lower()

        if added_to_fp == "x" and added_to_sale == "x":
            print("columns are marked x, please verify the sheet.")
            FP_DC = None
            SALE = False
            continue

        elif added_to_fp == "x":
            print("add to full price")
            FP_DC = "FP"
            SALE = False

        elif added_to_sale == "x":
            print("add to sale")
            FP_DC = "DC"
            SALE = True
        else:
            print("neither full price nor sale is marked x")
            FP_DC = None
            SALE = False
            continue
        create_new, product_id,status= PUD.decide(STYLE, COLOR, FP_DC)
        if create_new:
            print('no product page found, create new one.')
        else:
            U = update_pp.UpdatePP(STYLE,COLOR,SEASON,product_id,SALE)

            if status.upper()== 'DRAFT':
                if FP_DC =="FP":
                    print("proceed updating full price product")
                    link = U.update_fixed()

                elif FP_DC == "DC":
                    print("proceed updating sale stock product")
                    link = U.update_sale_stock()
                else: 
                    print("can't proceed")
                    continue
                sheet.values().update(
                    spreadsheetId=os.getenv("RETURN_ID"),
                    range=f"'{worksheet_name}'!R{sheet_row}",
                    valueInputOption="RAW",
                    body={"values": [[link]]}
                ).execute()

            else:
                print('this is an active product, retracting....') 

except:
    traceback.print_exc()