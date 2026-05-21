import Setup.fetch_product_id_new as fetch
import fetch_to_product_page as ftp
import pandas as pd 
import create_pp
import update_pp

STYLE= "MARINA CREW MERCER".upper()
COLOR = "CANTALOUPE".upper()
SEASON = "26 Spring"
product_id = "7678133633072"


if __name__ == "__main__":

    # S = ftp.ProductInfo(STYLE,COLOR,SEASON ,sample=True, sale=True, sas = False)
    # create_pp.create_sample(STYLE,COLOR,SEASON)
    U = update_pp.UpdatePP(STYLE,COLOR,SEASON,product_id)
    U.update_fixed()
    