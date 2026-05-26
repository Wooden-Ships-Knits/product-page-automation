import Setup.fetch_product_id_new as fetch
import fetch_to_product_page as ftp
import pandas as pd 
from Setup import setup

"""
this will be the source for which colors and styles that is going to be processed
"""
def feth_pp_status():
    data = []
    values = setup._get_sheet_values(
        "MASTER_DATA_ID"

    )






    data.append(
        {"Styles": f"{STYLE.upper()}",
        "Colors": f"{COLOR.upper()}", 
        "Production": f"{production_type}"},
    )

