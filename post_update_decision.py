from Setup import setup
from dotenv import load_dotenv
import os
from pathlib import Path
import pandas as pd
load_dotenv(Path(__file__).parent / ".env", override=True)

STYLE= "LOBSTER V-NECK COTTON"
COLOR = "Pure Snow/Cinders/White"
def decide():
    values = setup._get_sheet_values(
        sheet_id=os.getenv("PPA_SHEET_ID"),
        worksheet_name="PP SY LIST",
        use_all_values=True
    )

    df = pd.DataFrame(values[1:],columns=values[0])

    df = df[
        df["Style"].str.contains(STYLE) &
        df["Color"].str.contains(COLOR, case=False, na=False) &
        (df["Production Status"] == "FP")]

    if df.empty:
        return "Not found, can create new"
    return df["Product ID"].iloc[0]

print(decide())
    