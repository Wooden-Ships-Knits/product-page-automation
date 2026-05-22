from Setup import setup
from dotenv import load_dotenv
import os
from pathlib import Path
import pandas as pd
load_dotenv(Path(__file__).parent / ".env", override=True)

# STYLE= "Maura Marled Chunky Top Cotton"
# COLOR = "Ventana Blue/Almond Butter Marl"
# FP_DC = "DC"

def decide(STYLE,COLOR,FP_DC):
    values = setup._get_sheet_values(
        sheet_id=os.getenv("PPA_SHEET_ID"),
        worksheet_name="PP SY LIST",
        use_all_values=True
    )

    df = pd.DataFrame(values[1:],columns=values[0])

    df = df[
        df["Style"].str.contains(STYLE, case=False, na=False) &
        df["Color"].str.contains(COLOR, case=False, na=False) &
        (df["FP/DC"] == FP_DC)]

    if df.empty:
        print("Create new")
        create_new = True
        product_id = ""
        status = "DRAFT"

    else:
        print("Update")
        create_new = False
        product_id = df['Product ID'].iloc[0]
        status = df['Page Status'].iloc[0]
    return create_new, product_id,status

# print(decide())
    