import Setup.fetch_product_id_new as fetch
import fetch_to_product_page as ftp
import pandas as pd 
import create_pp
import update_pp
import post_update_decision as PUD

STYLE= "EMORY TIPPED L/S TOP COTTON".upper()
COLOR = "Ventana Blue/Twilight Sky".upper()
SEASON = "26 Spring"
production_type = "fixed"

if production_type == 'fixed' or production_type == "unfix":
    FP_DC = "FP"
    SALE = False
else:
    FP_DC = "DC"
    SALE =True

create_new, product_id, status =PUD.decide(STYLE,COLOR,FP_DC)

print(create_new,product_id,status)

if __name__ == "__main__":
    if status.upper() == "DRAFT":
        if create_new==True:
            C = create_pp.CreatePP(STYLE,COLOR,SEASON,SALE)
            if production_type == 'unfix':
                C.create_unfix()
            elif production_type == 'fixed':
                C.create_fixed() 
            elif production_type == 'sale_stock':
                C.create_sale_stock()
            elif production_type == 'o4':
                C.create_o4()
            elif production_type == 'sample':
                C.create_sample()
        elif  create_new == False:
            U = update_pp.UpdatePP(STYLE,COLOR,SEASON,product_id,SALE)
            if production_type == 'unfix':
                U.update_unfix()
            elif production_type == 'fixed':
                U.update_fixed() 
            elif production_type == 'sale_stock':
                U.update_sale_stock()
            elif production_type == 'o4':
                U.update_o4()
            elif production_type == 'sample':
                U.update_sample()
    else: print('not found or an active pp. skipping')

