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
import update_pp,create_pp
import post_update_decision as PUD
from datetime import date
sheet = setup.sheet

# worksheet_name = f'Jun 5, 2026'
worksheet_name = date.today().strftime("%b %d, %Y")

values = setup._get_sheet_values(
        sheet_id=os.getenv("RETURN_ID"),
    worksheet_name = worksheet_name,
    use_all_values=True
)
try:
    dfs = pd.DataFrame(values[6:],columns=values[5])

    zz_columns = dfs.columns[dfs.columns.str.contains("ZZ")]

    dfs = dfs[~(dfs[zz_columns] == "ZZ").any(axis=1)]
    dfs = dfs.drop_duplicates(subset=['Style', 'Color'])
    
    def _first(x):
        return x.iloc[0] if hasattr(x, 'iloc') else x

    styles = []
    colors = []
    product_ids = []
    FP_DCs = []

    for idx, row in dfs.iterrows():
        sheet_row = idx + 7 
        STYLE = _first(row['Style']).strip()
        COLORS = [_first(row['Color']).strip()]
        print(f'processing {STYLE} - {COLORS[0]}')
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
        create_new, PRODUCT_ID, status, DESCRIPTION = PUD.decide(STYLE, COLORS[0], FP_DC)
        if create_new:
            print('no product page found, creating new one......')
            C = create_pp.CreatePP(STYLE, COLORS, SEASON, SALE, DESCRIPTION)
            if FP_DC == "FP":
                print("proceed creating full price product")
                link, product_id = C.create_fixed()
            elif FP_DC == "DC":
                print("proceed creating sale stock product")
                link, product_id = C.create_sale_stock()
            else:
                print("can't proceed")
                continue
            if link:
                sheet.values().update(
                    spreadsheetId=os.getenv("RETURN_ID"),
                    range=f"'{worksheet_name}'!R{sheet_row}",
                    valueInputOption="RAW",
                    body={"values": [[link]]}
                ).execute()
                styles.append(STYLE)
                colors.append(COLORS[0])
                product_ids.append(product_id)
                FP_DCs.append(FP_DC)
        else:
            U = update_pp.UpdatePP(STYLE,COLORS,SEASON,PRODUCT_ID,SALE,DESCRIPTION)

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
                [s, c, pid, "DRAFT", fp]
                for s, c, pid, fp in zip(styles, colors, product_ids, FP_DCs)
            ]
            sheet.values().update(
                spreadsheetId="1CX6tjxos0N2p_YRmrgo6sA7KSPM5bZnBdyaQZuJWoCk",
                range=f"'PP SY LIST'!A{start_idx + 2}",
                valueInputOption="RAW",
                body={"values": new_rows}
            ).execute()

except:
    traceback.print_exc()