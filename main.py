import Setup.fetch_product_id_new as fetch
import fetch_to_product_page as ftp
import pandas as pd 
import create_pp

STYLE= "APRÈS SEA CREW COTTON"
COLOR= "BLUE WIND/BREAKER WHITE"
SEASON = "26 Spring"

if __name__ == "__main__":
    # # fetch.fetch()
    # S = ftp.ProductInfo( style="MARINA CREW MERCER", color="HALF MOON", season="26 SPRING", sample=False , sale=False, sas = False)
    # print(S.get_sku_barcode())
    create_pp.create_unfix(STYLE,COLOR,SEASON)
