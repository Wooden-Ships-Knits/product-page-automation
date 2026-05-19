import Setup.fetch_product_id_new as fetch
import fetch_to_product_page as ftp
import pandas as pd 
if __name__ == "__main__":
    # fetch.fetch()
    S = ftp.ProductInfo( style="MARINA CREW MERCER", color="HALF MOON", season="26 SPRING", sample=False , sale=False)
    print(S.get_SEL())