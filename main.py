import Setup.fetch_product_id_new as fetch
import fetch_to_product_page as ftp
import pandas as pd 
import create_pp

STYLE= "Maura Marled Chunky Top Cotton".upper()
COLOR= "Ventana Blue/Almond Butter Marl".upper()
SEASON = "26 Spring"

if __name__ == "__main__":

    S = ftp.ProductInfo(STYLE,COLOR,SEASON ,sample=False, sale=False, sas = False)
    create_pp.create_fixed(STYLE,COLOR,SEASON)
    