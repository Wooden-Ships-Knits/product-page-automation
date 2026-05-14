import time
import gspread
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials
import subprocess
from PIL import Image
import json

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "credentials/dialy-report-automation-e20c53e67542.json",
    scopes=scope
)
gc = gspread.authorize(creds)

_SPREADSHEET_CACHE = {}
_WORKSHEET_CACHE = {}
_VALUES_CACHE = {}
_EXCEL_CACHE = {}


def _get_spreadsheet(sheet_id):
    spreadsheet = _SPREADSHEET_CACHE.get(sheet_id)
    if spreadsheet is None:
        spreadsheet = gc.open_by_key(sheet_id)
        _SPREADSHEET_CACHE[sheet_id] = spreadsheet
    return spreadsheet

def _get_worksheet(sheet_id, worksheet_name=None, worksheet_index=None):
    if worksheet_name is None and worksheet_index is None:
        raise ValueError("Either worksheet_name or worksheet_index must be provided")

    worksheet_key = worksheet_name if worksheet_name is not None else f"__index__{worksheet_index}"
    cache_key = (sheet_id, worksheet_key)
    worksheet = _WORKSHEET_CACHE.get(cache_key)
    if worksheet is None:
        spreadsheet = _get_spreadsheet(sheet_id)
        if worksheet_name is not None:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.get_worksheet(worksheet_index)
        _WORKSHEET_CACHE[cache_key] = worksheet
    return worksheet

def _get_sheet_values(
    sheet_id,
    worksheet_name=None,
    worksheet_index=None,
    range_name=None,
    use_all_values=False,
):
    cache_key = (sheet_id, worksheet_name, worksheet_index, range_name, use_all_values)
    values = _VALUES_CACHE.get(cache_key)
    if values is not None:
        return values

    worksheet = _get_worksheet(
        sheet_id=sheet_id,
        worksheet_name=worksheet_name,
        worksheet_index=worksheet_index,
    )
    if use_all_values:
        values = worksheet.get_all_values()
    else:
        values = worksheet.get(range_name)
    _VALUES_CACHE[cache_key] = values
    return values

def _read_excel_cached(path, header):
    cache_key = (path, header)
    dataframe = _EXCEL_CACHE.get(cache_key)
    if dataframe is None:
        dataframe = pd.read_excel(path, header=header)
        _EXCEL_CACHE[cache_key] = dataframe
    return dataframe

class Product:
    def __init__(self, product_name, color_raw, season, collection):
        self.product_name = product_name
        self.color_raw = color_raw
        self.season = season
        self.collection = collection

    def _master_data(self,worksheet):
        values_md = _get_sheet_values(
            sheet_id="1u-Nk4CSmBjSFtopVXIsssVPsw9YRZJb2woHP9YLW3j0",
            worksheet_name=worksheet,
            use_all_values=True,
        )
        header = values_md[0]
        rows = values_md[1:]

        df_md = pd.DataFrame(rows, columns=header)

        filtered = df_md[df_md["STYLE"].str.contains(self.product_name, case=False,na=False)]
        filtered = filtered[filtered["COLOR"].str.contains(self.color_raw, case=False, na=False)]
        return filtered
    
    def title_and_desc(self,sample):
        print("processing title page")
        title_page = f"{self.product_name}"
        sale_title_page = f"*SALE* - {self.product_name}"
        ############################## Thread Type  ####################################
        thread = self.product_name.split(" ")
        if thread[-1]=="COTTON" or thread[-1]=="MERCER":
            thread_comp = "<p>Composition: 60% cotton, 40% acrylic</p>"
        else:
            thread_comp = "<p>Composition: 76% acrylic, 12% Mohair and 12% Wool</p>"
        if sample == True:
            sale_desc = """
            <p><meta charset="utf-8"><span data-mce-fragment="1">Sale items are FINAL SALE: No Returns, Refunds, or Exchanges. </span><span data-mce-fragment="1">&nbsp;</span><br data-mce-fragment="1"><span data-mce-fragment="1">Why is this on Sale? These pieces are knit as samples for our wholesale business. They have been handled during sales appointments, but they are carefully inspected before shipping.</span></p>
            """
        else:  
            sale_desc="""
            <p><meta charset="utf-8"><span data-mce-fragment="1">Sale items are FINAL SALE: No Returns, Refunds or Exchanges. </span><span data-mce-fragment="1"> </span><br data-mce-fragment="1"><span data-mce-fragment="1">Why is this on Sale? Sometimes a shopper changes their mind leaving us with perfectly fabulous sweaters, or we have extra yarn with which we knit new sweaters.</span></p>
            """
        ############################## Sale desc  ####################################
  
        return title_page, sale_title_page, sale_desc, thread_comp
    
    def old_product(self):
        old_chart = """ 
        <p style="margin-top: 15px; font-family: 'raleway'; font-size: 17px; font-weight: 600;">MEASUREMENTS FOR S/M (6-8):</p>
        <ul style="margin-left: 25px;">
        <li>Chest Width (1" down from armholes): 22"</li>
        <li>Length (from highest point shoulder to hem): 22.5"</li>
        </ul>
        """
        print("NEED EDIT SIZE MANUALLY, SIZE DETAIL IS NOT IN IM MASTER")
        return old_chart
    
    def ne_sample(self):
        print("processing sample stocks")
        filtered = self._master_data("STOCK NE SAMPLE")
        if filtered.empty:
            print("the specific item is not listed in the stock")
            return
        stocks = filtered["STOCK NE SAMPLE"].iloc[0]
        size = "S/M"
        SKUs = f"{filtered['SKU'].iloc[0]}-{filtered['COLOR'].iloc[0]}-S/M"
        return size, SKUs, stocks
   
    def ne_first_choice(self):
        print("processing ne stocks")
        filtered = self._master_data("STOCK NE FIRST CHOICE")
        if filtered.empty:
            print("the specific item is not listed in the stock")
            return
        sku_code = filtered["SKU"].iloc[0]

        SKUs = []
        sizes = []
        stocks = []


        if filtered["X/S"].iloc[0] != "0":
            sizes.append("X/S")
            SKUs.append(f"{sku_code}-{filtered['COLOR'].iloc[0]}-X/S")
            stocks.append(filtered["X/S"].iloc[0])

        if filtered["S/M"].iloc[0] != "0":
            sizes.append("S/M")
            SKUs.append(f"{sku_code}-{filtered['COLOR'].iloc[0]}-S/M")
            stocks.append(filtered["S/M"].iloc[0])

        if filtered["M/L"].iloc[0] != "0":
            sizes.append("M/L")
            SKUs.append(f"{sku_code}-{filtered['COLOR'].iloc[0]}-M/L")
            stocks.append(filtered["M/L"].iloc[0])

        if filtered["X/L"].iloc[0] != "0":
            sizes.append("X/L")
            SKUs.append(f"{sku_code}-{filtered['COLOR'].iloc[0]}-X/L")
            stocks.append(filtered["X/L"].iloc[0])
        return sizes, SKUs, stocks

    def bali_stocks(self):
        print("processing bali stocks")
        filtered = self._master_data("STOCK BALI ST5")
        if filtered.empty:
            print("the specific item is not listed in the stock")
            return
        sku_code = filtered["SKU"].iloc[0]

        SKUs = []
        sizes = []
        stocks = []

        if filtered["X/S"].iloc[0] != "0":
            sizes.append("X/S")
            SKUs.append(f"{sku_code}-{filtered['COLOR'].iloc[0]}-X/S")
            stocks.append(filtered["X/S"].iloc[0])

        if filtered["S/M"].iloc[0] != "0":
            sizes.append("S/M")
            SKUs.append(f"{sku_code}-{filtered['COLOR'].iloc[0]}-S/M")
            stocks.append(filtered["S/M"].iloc[0])

        if filtered["M/L"].iloc[0] != "0":
            sizes.append("M/L")
            SKUs.append(f"{sku_code}-{filtered['COLOR'].iloc[0]}-M/L")
            stocks.append(filtered["M/L"].iloc[0])

        # if filtered["X/L"].iloc[0] != "0":
        #     sizes.append("X/L")
        #     SKUs.append(f"{sku_code}-{filtered['COLOR'].iloc[0]}-X/L")
        #     stocks.append(filtered["X/L"].iloc[0])

        return sizes, SKUs, stocks

    def get_type(self):
        tipe = self.product_name.split(" ")
        tipe = tipe[-2]
        if tipe == "V":
            tipe ="V-neck"
        elif tipe == "CREW":
            tipe ="Crewneck"#
        elif tipe == "CARDI" or tipe == "CARDIGAN":
            tipe ="Cardigan"
            tipe = tipe.lower().title()
        elif tipe =="TOP":
            tipe_add =self.product_name.split(" ")[-3]
            if tipe_add == "POLO":
                tipe = "Collar"
            else: tipe = "Crewneck"
        elif tipe == "HOODIE":
            tipe = tipe.title()

        return tipe

    def unfix(self):
        print("processing unfix inventory details")
        sku_upc_ID = "1k-gCMaXqDtzROFUbIX3DFnA_MpzK__8eDDWlkRLhnCc"
        values = _get_sheet_values(
            sheet_id=sku_upc_ID,
            worksheet_name="PRODUCTION UPC LIST",
            use_all_values=True,
        )

        header = values[5]
        rows = values[6:]
        df = pd.DataFrame(rows, columns = header)
        filtered = df[df["Product Name"].str.contains(self.product_name, case=False, na=False)]
        filtered = filtered[filtered["Lineitem sku"].str.contains(self.color_raw, case=False, na=False)]
        #############WATCH THIS
        # filtered = filtered[filtered["Lineitem sku"].str.contains("K56", case=False, na=False)]
        ########## WATCH THIS
        if filtered.empty:
            print("the specific item is not listed in the NE first choice file")
            return
        sizes = []
        SKUs = []
        barcodes = []
        size_order = {"X/S": 0, "S/M": 1, "M/L": 2, "X/L": 3}

        # extract size from SKU (last part after "-")
        filtered = filtered.copy()
        filtered["SIZE"] = filtered["Lineitem sku"].str.split("-").str[-1].str.strip()

        # sort by your custom order; unknown sizes go to the end
        filtered["SIZE_ORDER"] = filtered["SIZE"].map(size_order).fillna(999)
        filtered = filtered.sort_values("SIZE_ORDER")

        for _, row in filtered.iterrows():
            SKU = row["Lineitem sku"]
            barcode = row["UPC Barcode"]
            size = row["SIZE"]
            sizes.append(size)
            SKUs.append(SKU)
            barcodes.append(barcode)

        print(f"{barcodes} , {sizes} , {SKUs}")
        return barcodes, sizes, SKUs    

    def get_weight(self):
        try:
            print("processing IM Master to obtain the weight")
            im_master_path = f"/Users/ptinfashion/Library/CloudStorage/GoogleDrive-web@pt-infashion.com/Shared drives/PTIF SERVER/Collection/26 SPRING/IM/S26 IM MASTER.xlsx"
            df = _read_excel_cached(im_master_path, header=56)

            filtered_im = df[
                (df["DESCRIPTION"].str.contains(self.product_name)) &
                (df["WS TAG COLOR"].str.contains(self.color_raw))
            ]
            if filtered_im.empty:
                print(" the product is not listed in IM master file, changing file TO FALL item")
        except Exception as e:
            print("ERROR: ", e)
            im_master_path = f"/Users/ptinfashion/Library/CloudStorage/GoogleDrive-web@pt-infashion.com/Shared drives/PTIF SERVER/Collection/25 FALL/IM/F25 IM MASTER.xlsx"
            df = _read_excel_cached(im_master_path, header=56)
            if filtered_im.empty:
                print(" item can not be found")
                return 
        filtered_im = filtered_im[filtered_im["DESCRIPTION"].str.contains("S/M")]

        weight_kg = filtered_im["PRE COMPONENT WT (PC WT)"]
        weight_g = weight_kg *1000
        weight_g = weight_g.iloc[0]
        weight_g = int(weight_g)

        return weight_g

    def get_weight_multiple(self,sizes):
        try:
            print("processing IM Master to obtain the weight")
            im_master_path = f"/Users/ptinfashion/Library/CloudStorage/GoogleDrive-web@pt-infashion.com/Shared drives/PTIF SERVER/Collection/26 SPRING/IM/S26 IM MASTER.xlsx"
            df = _read_excel_cached(im_master_path, header=56)

            base_filtered_im = df[
                (df["DESCRIPTION"].str.contains(self.product_name)) &
                (df["WS TAG COLOR"].str.contains(self.color_raw))
            ]
            if base_filtered_im.empty:
                print(" the product is not listed in IM master file, changing file TO FALL item")
        except Exception as e:
            print("ERROR: ", e)
            im_master_path = f"/Users/ptinfashion/Library/CloudStorage/GoogleDrive-web@pt-infashion.com/Shared drives/PTIF SERVER/Collection/25 FALL/IM/F25 IM MASTER.xlsx"
            df = _read_excel_cached(im_master_path, header=60)
            base_filtered_im = df[
            (df["DESCRIPTION"].str.contains(self.product_name)) &
            (df["""WS TAG COLOR
(Note - Tag color untuk style striped hanya STRIPE tanpa D)"""].str.contains(self.color_raw))
            ]
            if base_filtered_im.empty:
                print(" item can not be found")
                weight_gs = []
                old_product = True
                return  weight_gs, old_product       
        old_product = False
        weight_gs = []
        for s in sizes:
            filtered_im = base_filtered_im[base_filtered_im["DESCRIPTION"].str.contains(s, case =False, na= False )]
            if filtered_im.empty:
                print(f"the speficic size {s} product is not listed in IM master file")
                old_product = True
                weight_g = 0
            else:  
                weight_kg = filtered_im["PRE COMPONENT WT (PC WT)"]
                weight_g = weight_kg *1000
                weight_g = weight_g.iloc[0]
                weight_g = int(weight_g)
            weight_gs.append(weight_g)
            print(weight_gs)
        return weight_gs, old_product

    def get_tags(self, sale, sample, sas, sizes):
        print("processing tags")
        IMSY_ID = "1W5JJiunUbEZVv-vxUfEXgdVxw4wvrjayXwRz2VIkIQY" #IMSY ID
     
        values_IMSY = _get_sheet_values(
            sheet_id=IMSY_ID,
            worksheet_name=self.season,
            range_name="A:CW",
        )   # Only columns A to CW
        header = values_IMSY[4]
        rows = values_IMSY[5:]

        max_len = len(header)
        rows = [row + [""] * (max_len - len(row)) for row in rows]

        data_IMSY = pd.DataFrame(rows, columns=header)
        filtered_imsy = data_IMSY[data_IMSY["DESCRIPTION"].str.contains(self.product_name, case=False, na=False)]
        filtered_imsy = filtered_imsy[filtered_imsy["COLOR"].str.contains(self.color_raw, case=False, na=False)]
        if filtered_imsy.empty:
            tags = None
            print("NO TAGS YET IN IMSY FILE")
            # return None
        ########
        else:
            tags = filtered_imsy["ALL SUMMARY FOR CSV"].iloc[0]
        ########### tags removal######################
            if "FILTERBY-X/S," in tags:
                tags = tags.replace("FILTERBY-X/S,","")
            if "FILTERBY-M/L," in tags:
                tags = tags.replace("FILTERBY-M/L,","")
            if "FILTERBY-X/L," in tags:
                tags = tags.replace("FILTERBY-X/L, ","")
                tags = tags.replace("X/L, ","")
                tags = tags.replace("L/XL, ","")
        print("IMSY PART FINISH")
        additional_tags= "sweater, sweaters, sweatshirt, outfit, outfits, casual, "
        ##########down here are additional tags in case imsy file empty############################
        def forward_fill(row):
            filled = []
            last = ""
            for cell in row:
                cell = cell.strip()
                if cell:
                    last = cell
                filled.append(last)
            return filled
        
        SSI_ID = "1esbj3SiVjMGgdoBCnV75z3UircVUXj_gUR64BPpRPgU" #SSI ID
        values_ssi = _get_sheet_values(
            sheet_id=SSI_ID,
            worksheet_index=6,
            use_all_values=True,
        )

        header_level_1 = forward_fill(values_ssi[2])
        header_level_2 = forward_fill(values_ssi[3])
        header_level_3 = forward_fill(values_ssi[4])
        combined_headers = []
        for h1, h2, h3 in zip(header_level_1, header_level_2, header_level_3):

            parts = []

            if h1.strip():
                parts.append(h1.strip())
            if h2.strip():
                parts.append(h2.strip())
            if h3.strip():
                parts.append(h3.strip())

            combined_name = " | ".join(parts)
            combined_headers.append(combined_name)
        data_ssi = pd.DataFrame(values_ssi[5:], columns=combined_headers)

        data_ssi.columns = (
            data_ssi.columns
                .str.replace(r"\s+", " ", regex=True)  # collapse whitespace/newlines
                .str.strip()
        )

        filtered = data_ssi[data_ssi["FROM IM | DESCRIPTION"].str.contains(self.product_name, case=False, na=False)]
        filtered = filtered[filtered["FROM IM | COLOR"].str.contains(self.color_raw,case=False,na=False)]
        if filtered.empty:
            print("the item is not listed in seasonal style index file ")
        else:

            if filtered["WEB | PRINTED | (Y/N)"].iloc[0]=="Y":
                additional_tags += "hand printed, printed, "
            if filtered["WEB | BOYFRIEND | (Y/N)"].iloc[0]=="Y":
                additional_tags += "boyfriend, boyfriends, "
                if sale== True:
                    additional_tags+="boyfriend-vo, "
            if filtered["WEB | UPDATED | CROPPED (Y/N)"].iloc[0] == "Y":
                    additional_tags+="cropped, "
            elif filtered["WEB | ORIGINAL | CROPPED (Y/N)"].iloc[0] == "":
                if filtered ["WEB | ORIGINAL | CROPPED (Y/N)"].iloc[0] == "Y":
                    additional_tags += "cropped, "

        ### tag wajib##
       

        if sale == True:
            additional_tags_sale = "no-returns, Sample, Sale, Off, Garage, Discount, Disc, final-sale, outfit, outfits, sweater, sweaters, sweatshirt, casual"
        else:
            additional_tags_sale = ""
        if sample == True: 
            additional_tags_sample = "Sample, "
        else: 
            additional_tags_sample = ""
        if sas ==  True: 
            additional_tags_sas = "BOGO 50% OFF, SAS FEB 2026,"
        else:
            additional_tags_sas = ""
        print("SALE/not SALE PART FINISH")
        #############
        #additional tags depends on the product
        #############
        tipe = self.product_name.split(" ")[-2]
        print("sucessfully split")
        tipe = tipe.title()
        print(tipe)
        if tipe == "Top":
            tipe_add = self.product_name.split(" ")[-3]
            if tipe_add == "POLO":
                additional_tags += "collar, collarneck, "
            
        zipper = self.product_name.split(" ")[1]
        print(zipper)
        if tipe == "Crewneck":
            additional_tags += "crew, crewneck, "
            if sale == False:
                additional_tags += "crewneck-vo, "
        elif tipe == "V-neck":
            additional_tags += "vneck, v neck, "
            if sale == False:
                additional_tags += "vneck-vo, "
        elif tipe == "Cowl":
            additional_tags += "cowl, cowl neck, turtleneck, turtle neck, "
        elif tipe == "Cardigann" or tipe == "Cardi":
            additional_tags += "cardigan, Cardi, "
        elif tipe == "Hoodie":
            additional_tags += "hoodie, hood, hoods, "
        elif tipe == "Tank":
            additional_tags += "tank, tanks, tank top, tank tops, tanktop, tanktops, "
        if tipe !="Cardigan" or tipe != "Cardi" or zipper != "ZIP":
            additional_tags += "Pullover (Standard), "
        elif zipper == "ZIP":
            additional_tags += "zipper, "
        else:
            additional_tags += ""
        print("BASED ON DESIGN PART I FINISH")
        if self.collection.upper() == "ESSENTIALS" or self.collection.upper() == "ESSENTIALS ":
            additional_tags_colleciton="ESS 2026 release, "
        elif self.collection.upper() == "BLOSSOM":
            additional_tags_colleciton = "BLSSM 2026 release, "
        elif self.collection.upper() == "SAS":
            additional_tags_colleciton =""
        elif self.collection.upper() == "LAKE" or self.collection.upper()=="BEACH" or self.collection.upper() == "BEACH & LAKE":
            additional_tags_colleciton= "BCHLK release 2026, "
        elif self.collection.upper() == "AMERICANA":
            additional_tags_colleciton = "MRCN 2026"
        else:            additional_tags_colleciton = ""
        if "S" in self.season:
            additional_tags_season = "spring, summer, "
        elif "F" in self.season:
            additional_tags_season = "winter, fall, autumn, "
        print("BASED ON DESIGN PART II FINISH")
####unknown method of tags:
# boyfriend, boyfriends, boyfriend-vo, cropped, 
#
        generic_colors = {}
        pfc_ID = "1foCvn9twfZ-ucvL0LDoQFv-Yor2fDxxxGXMLxS7XQCc"
        letter = self.season[0]
        colors = [c.strip() for c in self.color_raw.split("/")]
        colors += [None] * (3 - len(colors))
        color1, color2, color3 = colors[:3]
        colors = [c for c in colors if c]
        if letter == "S":
            values_pfc = _get_sheet_values(
                sheet_id=pfc_ID,
                worksheet_name="S25 - COLOR GROUP",
                range_name="A:E",
            )   # Only columns A to E
            data_pfc = pd.DataFrame(values_pfc[5:], columns=values_pfc[4])
            for i, c in enumerate(colors, start=1):
                # filtered_pfc = data_pfc[
                #     data_pfc["S25 COLORS"].str.contains(c, case=False, na=False)
                #         ]
                filtered_pfc = data_pfc[
                    data_pfc["S25 COLORS"].astype(str).str.strip().str.casefold().eq(
                        c.strip().casefold()
                    )
                ]
                if not filtered_pfc.empty:
                    generic_colors[f"generic_c{i}"] = filtered_pfc["COLOR CATEGORY 1"].iloc[0]
                else:
                    generic_colors[f"generic_c{i}"] = None

        generic_c1 = generic_colors.get("generic_c1")
        additional_tags_color = generic_c1
        if additional_tags_color== "Purple":
            additional_tags_color = f"{additional_tags_color}, Violet, "
        if additional_tags_color== "White" or additional_tags_color=="Black" or additional_tags_color=="Grey" or additional_tags_color=="Brown":
            additional_tags_color = f"{additional_tags_color}, Neutral, "
        if additional_tags_color=="Grey":
            additional_tags_color = f"{additional_tags_color}, Gray, "
        if additional_tags_color=="Brown":
            additional_tags_color = f"{additional_tags_color}, Chocolate, Tan, Cream, Nude, "

        print("COLOR PART FINISH")
        def today_string():
            return datetime.now().strftime("%b %-d %Y")

        additional_tags_date = f"Additional {today_string()}, "
        additional_tags += f"{self.product_name.lower()}, "
        if "COTTON" in self.product_name:
            additional_tags += "cotton blend, cottons, "
            if sale == False:
                additional_tags += "cotton-vo, "
            if "CHUNKY"in self.product_name:
                additional_tags += "chunky blend, chunky tag,  "
                if sale == False:
                    additional_tags += "chunky-vo, "
            else:
                 additional_tags += "lightweight, "
        elif "MERCER" in self.product_name:
                additional_tags += "mercer, lightweight, "
        else:
            additional_tags += "wool blend, grassy, "
            if "CHUNKY"in self.product_name:
                additional_tags += "chunky blend, chunky tag, "
                if sale == False:
                    additional_tags += "chunky-vo, "
            elif "LIGHTWEIGHT" in self.product_name:
                additional_tags += "lightweight, "
        if "CABLE" in self.product_name:
            additional_tags+="cable, cables, cableknit, cable knit, "     
        if "3/4" in self.product_name:
            additional_tags += "3/4 sleeves, "
        elif "TEE" in self.product_name:
            additional_tags += "Short Sleeves, Tee, tee, top tee, "
            if sale == False:
                additional_tags += "tee-vo, "
        elif "SLEEVELESS" in self.product_name:
            additional_tags += "Sleeveless, "
        elif "HALF SLEEVE" in self.product_name: 
            additional_tags += "Short Sleeves, Half Sleeve, half sleeve, "
        else:
            additional_tags += "Long Sleeve, long sleeve, "

        if "STRIPE" in self.product_name:
            additional_tags += "Stripe, "
        if "MARLED" in self.product_name or "MARL" in self.product_name:
            additional_tags += "marl, marled, melange "
        if "HEATHERED" in self.product_name:
            additional_tags += "heather, heathered, "
                    
        if "X/S" in sizes:
            additional_tags+="FILTERBY-X/S, "
        if  "S/M" in sizes:
            additional_tags+="FILTERBY-S/M, "
        if "M/L" in sizes:
            additional_tags+="FILTERBY-M/L, "
        if "X/L" in sizes:
            additional_tags+="FILTERBY-X/L, L/XL, X/L, "
        if tags:
            tags = f"{tags}, {additional_tags_sample}, {additional_tags_sale}, {additional_tags_sas}, {additional_tags_color}, {additional_tags}, {additional_tags_colleciton}, {additional_tags_season}"
        else:
            tags = f"{additional_tags_sample}, {additional_tags_sale}, {additional_tags_sas}, {additional_tags_color}, {additional_tags}, {additional_tags_date}, {additional_tags_season}, {additional_tags_colleciton}"
        print("BASED ON DESIGN PART II FINISH")
        return tags
        
    def get_price(self):
        ###################### NEED NEW CLEAN PIPELINE ASAP ###########################
        print("ENTER PRICE PART")
        PRICE_ID = "16GWane0VWG5Usuk9iXk8-_DzPcCOsRHfi_eMnyupUao" #PRICE ID
        values_price = _get_sheet_values(
            sheet_id=PRICE_ID,
            worksheet_name="2026 - BEACH & LAKE",
            use_all_values=True,
        )
        header = values_price[10]     # row 11
        rows = values_price[11:]      # row 12 onwards
        data_price = pd.DataFrame(rows,columns=header)
        
        filtered_price = data_price[data_price["STYLE"].astype(str).str.strip().str.casefold().eq(self.product_name.strip().casefold())]
        filtered_price = filtered_price[filtered_price["COLOR"].astype(str).str.strip().str.casefold().eq(self.color_raw.strip().casefold())]
        if filtered_price.empty:
            print("ITEM IS NOT LISTED IN THE SALE PRICE")
            price = 0
            compare_at_price =0
            return price, compare_at_price
        price = filtered_price["PB ADJUSTED SALE PRICE ON FEB 26"].iloc[0]
        if price =="" or price =="N/A":
            print("PB YET ADJUST THE PRICE, TAKING THE LATEST SALE PRICE INSTEAD")
            price = filtered_price["LATEST SALE PRICE"].iloc[0]
            if price == "N/A":
                print("PRICE IS N/A, SET AS 0 FOR NOW")
                price = 0 
        else:
            price = float(price.replace("$", "").replace(",", ""))
        compare_at_price = filtered_price["PB ADJUSTED FULL PRICE"].iloc[0]
        if compare_at_price =="":
            compare_at_price= filtered_price["LATEST FULL PRICE"].iloc[0]
            compare_at_price = float(compare_at_price.replace("$", "").replace(",", ""))
            return price, compare_at_price
        else:
            compare_at_price = float(compare_at_price.replace("$", "").replace(",", ""))

        return price, compare_at_price
    
    def get_fullprice(self):
        print("processing IM Master to obtain the weight")
        im_master_path = f"/Users/ptinfashion/Library/CloudStorage/GoogleDrive-web@pt-infashion.com/Shared drives/PTIF SERVER/Collection/26 SPRING/IM/S26 IM MASTER.xlsx"
        df = _read_excel_cached(im_master_path, header=56)
        base_filtered_im = df[
        (df["DESCRIPTION"].str.contains(self.product_name)) &
        (df["WS TAG COLOR"].str.contains(self.color_raw))
        ]
        if base_filtered_im.empty: 
            print("the item is nowhere to be found or yet to be made, set price as zero")
            price = 0
            return price
        price=base_filtered_im["FINAL RETAIL PRICE"].iloc[0]
        # price = float(price.replace("$", "").replace(",", ""))
        return price

    def get_seo(self):
        extra1=None
        extra2=None
        extra3=None
        print("processing seo")
        colors = [c.strip() for c in self.color_raw.split("/")]
        colors += [None] * (3 - len(colors))
        color1, color2, color3 = colors[:3]
        colors = [c for c in colors if c]
        print(colors)
        generic_colors = {}
        color_just_name = self.color_raw.replace("/", " ")
        pfc_ID = "1foCvn9twfZ-ucvL0LDoQFv-Yor2fDxxxGXMLxS7XQCc"
        letter = self.season[0]
        if letter == "S":
            values_pfc = _get_sheet_values(
                sheet_id=pfc_ID,
                worksheet_name="S25 - COLOR GROUP",
                range_name="A:E",
            )   # Only columns A to E
            data_pfc = pd.DataFrame(values_pfc[5:], columns=values_pfc[4])
            for i, c in enumerate(colors, start=1):
                try:
                    if "HEATHER" in c or "STRIPE" in c or "MARL" in c: 
                        extra = c.split()[-1]
                        print(extra)
                        c = c.replace(extra, "").strip()
                        print(c)                   
                        
                    filtered_pfc = data_pfc[
                        data_pfc["S25 COLORS"].astype(str).str.strip().str.casefold().eq(
                            c.strip().casefold()
                        )
                    ]
                except Exception as e:
                    print(e)
                if not filtered_pfc.empty:
                  generic_colors[f"generic_c{i}"] = filtered_pfc["COLOR CATEGORY 1"].iloc[0]
                else:
                    # generic_colors[f"generic_c{i}"] = None
                    values_pfc = _get_sheet_values(
                        sheet_id=pfc_ID,
                        worksheet_name="F24 - COLOR GROUP",
                        range_name="A:C",
                    )   # Only columns A to C
                    data_pfc = pd.DataFrame(values_pfc[1:], columns=values_pfc[0])
                    for i, c in enumerate(colors, start=1):
                        #####
                        if "HEATHER" in c or "STRIPE" in c or "MARL" in c: 
                            extra = c.split()[-1]
                            c = c.replace(extra, "").strip()
                            print(c)
                        ######
                        filtered_pfc = data_pfc[
                                data_pfc["F24 COLOR"].astype(str).str.strip().str.casefold().eq(
                                    c.strip().casefold()
                                )
                            ]
                        if not filtered_pfc.empty:
                            generic_colors[f"generic_c{i}"] = filtered_pfc["COLOR CATEGORY 1"].iloc[0]
                        else:
                            generic_colors[f"generic_c{i}"] = None

        else:
            values_pfc = _get_sheet_values(
                sheet_id=pfc_ID,
                worksheet_name="F24 - COLOR GROUP",
                range_name="A:C",
            )   # Only columns A to C
            data_pfc = pd.DataFrame(values_pfc[1:], columns=values_pfc[0])
            for i, c in enumerate(colors, start=1):
                filtered_pfc = data_pfc[
                    data_pfc["F24 COLOR"].str.contains(c, case=False, na=False)
                ]
                if not filtered_pfc.empty:
                    generic_colors[f"generic_c{i}"] = filtered_pfc["COLOR CATEGORY 1"].iloc[0]
                else:
                    generic_colors[f"generic_c{i}"] = None
        print(generic_colors)      
        generic_c1 = generic_colors.get("generic_c1")            
        if generic_c1:
            generic_c1 = generic_c1.lower().title()
        else:
            print("unknown generic color from PFC file")
            return None
        generic_c2 = generic_colors.get("generic_c2")
        generic_c3 = generic_colors.get("generic_c3")
        if generic_c2:
            generic_c2 = generic_c2.lower().title()
        if generic_c3:
            generic_c3 = generic_c3.lower().title()
        product = self.product_name.lower().title()
        color = color_just_name.lower().title()
        color1 = color1.lower().title()
        if "Heather" in color1 or "Stripe" in color1 or "Marl" in color1: 
            extra1 = color1.split()[-1]
            color1 = color1.replace(extra1, "").strip()
        if color2:
            color2 = color2.lower().title()
            print(color2)
            if "Heather" in color2 or "Stripe" in color2 or "Marl" in color2: 
                extra2 = color2.split()[-1]
                color2 = color2.replace(extra2, "").strip()
                print(extra2)
                print(color2)
            generic_c2 = generic_c2.split("/")[0]
            if generic_c2.lower() in color2.lower():
                generic_c2=None
 
        if color3:
            color3 = color3.lower().title()
            if "Heather" in color3 or "Stripe" in color3 or "Marl" in color3: 
                extra3 = color3.split()[-1]
                color3 = color3.replace(extra3, "").strip()
            generic_c3 = generic_c3.split("/")[0]
            if generic_c3.lower() in color3.lower():
                generic_c3=None
        generic_c1 = generic_c1.split("/")[0]
        product_url = self.product_name.lower().replace(" ", "-")
        color_url = color.lower().replace(" ", "-")
        generic_c1_url = generic_c1.lower().replace(" ", "-")
        sale_url = f"sale-{product_url}-sweater-{color_url}-{generic_c1_url}-{int(time.time())}"
        url = f"{product_url}-sweater-{color_url}-{generic_c1_url}-{int(time.time())}"
        if generic_c1 and generic_c1.lower() in color1.lower():
            sale_url=f"sale-{product_url}-sweater-{color_url}-{int(time.time())}"
            url = f"{product_url}-sweater-{color_url}-{int(time.time())}"
        sale_title =f"SALE - {product} Sweater - {color} | Wooden Ships"
        title =f"{product} Sweater - {color} | Wooden Ships"
        if generic_c1.lower() in color1.lower():
            generic_c1=None

        if color2 and color3:
            desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''}, {color2}{' ' + generic_c2 if generic_c2 else ''} and {color3}{' ' + generic_c3 if generic_c3 else ''} at Wooden Ships. Free shipping for any full-price sweaters."
            if extra1:
                desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''} {extra1}, {color2}{' ' + generic_c2 if generic_c2 else ''} and {color3}{' ' + generic_c3 if generic_c3 else ''} at Wooden Ships. Free shipping for any full-price sweaters."
            elif extra2:
                desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''}, {color2}{' ' + generic_c2 if generic_c2 else ''} {extra2} and {color3}{' ' + generic_c3 if generic_c3 else ''} at Wooden Ships. Free shipping for any full-price sweaters."
            elif extra3: 
                desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''}, {color2}{' ' + generic_c2 if generic_c2 else ''} and {color3}{' ' + generic_c3 if generic_c3 else ''} {extra3} at Wooden Ships. Free shipping for any full-price sweaters."

        elif color2:
            desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''} and {color2}{' ' + generic_c2 if generic_c2 else ''} at Wooden Ships. Free shipping for any full-price sweaters."
            if extra1:
                desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''} and {color2}{' ' + generic_c2 if generic_c2 else ''} {extra1}at Wooden Ships. Free shipping for any full-price sweaters."
            elif extra2:
                desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''} and {color2}{' ' + generic_c2 if generic_c2 else ''} {extra2} at Wooden Ships. Free shipping for any full-price sweaters."
        else:
            desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''} at Wooden Ships. Free shipping for any full-price sweaters."
            if extra1: 
                desc = f"Shop the {product} Sweater in {color1}{' ' + generic_c1 if generic_c1 else ''} {extra1} at Wooden Ships. Free shipping for any full-price sweaters."
        return title, sale_title, desc, url, sale_url

    def get_meta_chart(self):
        print("processing meta chart")

        SSI_ID = "1esbj3SiVjMGgdoBCnV75z3UircVUXj_gUR64BPpRPgU" #SSI ID
        values = _get_sheet_values(
            sheet_id=SSI_ID,
            worksheet_index=6,
            use_all_values=True,
        )
        def forward_fill(row):
            filled = []
            last = ""
            for cell in row:
                cell = cell.strip()
                if cell:
                    last = cell
                filled.append(last)
            return filled
        
        header_level_1 = forward_fill(values[2])
        header_level_2 = forward_fill(values[3])
        header_level_3 = forward_fill(values[4])
        combined_headers = []

        for h1, h2, h3 in zip(header_level_1, header_level_2, header_level_3):

            parts = []

            if h1.strip():
                parts.append(h1.strip())
            if h2.strip():
                parts.append(h2.strip())
            if h3.strip():
                parts.append(h3.strip())

            combined_name = " | ".join(parts)
            combined_headers.append(combined_name)
        data = pd.DataFrame(values[5:], columns=combined_headers)
        # print(data.columns.tolist())
        filtered = data[data["FROM IM | DESCRIPTION"].str.contains(self.product_name, case=False, na=False)]
        filtered = filtered[filtered["FROM IM | COLOR"].str.contains(self.color_raw,case=False,na=False)]
        if filtered.empty:
            print("the item is not listed in seasonal style index file ")
            metafield =" "
            return metafield
        row = filtered.iloc[0]

        width_updated_cols = [
            col for col in data.columns
            if "UPDATED SIZE (CM)" in col and "Width" in col
        ]

        width_original_cols = [
            col for col in data.columns
            if "ORIGINAL SIZE" in col and "Width" in col
        ]

        length_updated_cols = [
            col for col in data.columns
            if "UPDATED SIZE (CM)" in col and "Length" in col
        ]

        length_original_cols = [
            col for col in data.columns
            if "ORIGINAL SIZE" in col and "Length" in col
        ]
        if filtered["DEV | GRADED (incl XL if XL is applicable) | (Y/N)"].iloc[0]=="Y":
            size_order = ["X/S", "S/M", "M/L", "X/L"]
        elif filtered["DEV | GRADED (incl XL if XL is applicable) | (Y/N)"].iloc[0]=="N":
            size_order = ["X/S", "S/M", "M/L"]
        else: 
            size_order = ["X/S", "S/M", "M/L", "X/L"]
        def sort_by_size(cols):
            valid_cols = []

            for col in cols:
                size_name = col.split(" | ")[0].split(" - ")[0]
                if size_name in size_order:
                    valid_cols.append(col)

            return sorted(
                valid_cols,
                key=lambda x: size_order.index(
                    x.split(" | ")[0].split(" - ")[0]
                )
            )
        width_updated_cols = sort_by_size(width_updated_cols)
        width_original_cols = sort_by_size(width_original_cols)
        length_updated_cols = sort_by_size(length_updated_cols)
        length_original_cols = sort_by_size(length_original_cols)

        size_data = []

        for wu, wo, lu, lo in zip(
            width_updated_cols,
            width_original_cols,
            length_updated_cols,
            length_original_cols
        ):

            updated_width = str(row[wu]).strip()
            original_width = str(row[wo]).strip()

            updated_length = str(row[lu]).strip()
            original_length = str(row[lo]).strip()

            # Width fallback
            if updated_width:
                width = updated_width
            elif original_width:
                width = original_width
            else:
                width = "-"

            # Length fallback
            if updated_length:
                length = updated_length
            elif original_length:
                length = original_length
            else:
                length = "-"

            size_data.append((width, length))

        formatted_size_data = []

        for width, length in size_data:
            if width != "-":
                width = f"{float(width):.2f}"
            if length != "-":
                length = f"{float(length):.2f}"
            formatted_size_data.append((width, length))

        size_data = formatted_size_data
        if filtered["DEV | GRADED (incl XL if XL is applicable) | (Y/N)"].iloc[0]=="Y" or filtered["DEV | GRADED (incl XL if XL is applicable) | (Y/N)"].iloc[0]=="": 
            print(size_data)
            (a, b), (c, d), (e, f), (g, h) = size_data
            if a=="-" or b=="-":
                print("one or more size(s) chart is/are empty")
            metafield = f"""
<p>See our <a href="/pages/sizing-chart%20" target="_blank">Measuring Guide</a> for how to measure properly.</p>
<p>Measurements are in Centimeters.</p>
<table class="size" style="text-align: center;">
<colgroup> <col style="width: 60px;"> <col style="width: 60px;"> <col style="width: auto;"> <col style="width: auto;"> </colgroup>
<thead>
<tr>
<th class="size-head" colspan="2" style="text-align: center;">SIZE</th>
<th class="size-width">CHEST WIDTH (CM)</th>
<th class="size-width">LENGTH (CM)</th>
</tr>
</thead>
<tbody>
<!-- MULAI EDIT SIZE DARI SINI YAA -->
<tr>
<td class="size-isi">X/S</td>
<td class="size-isi">2-4</td>
<td class="size-isi">{a}</td>
<td class="size-isi">{b}</td>
</tr>
<tr>
<td class="size-isi">S/M</td>
<td class="size-isi">6-8</td>
<td class="size-isi">{c}</td>
<td class="size-isi">{d}</td>
</tr>
<tr>
<td class="size-isi">M/L</td>
<td class="size-isi">10-12</td>
<td class="size-isi">{e}</td>
<td class="size-isi">{f}</td>
</tr>
<tr>
<td class="size-isi">X/L</td>
<td class="size-isi">14-16</td>
<td class="size-isi">{g}</td>
<td class="size-isi">{h}</td>
</tr>
<!-- MULAI EDIT SIZE SAMPAI SINI YAA -->
</tbody>
</table>
        """


        elif filtered["DEV | GRADED (incl XL if XL is applicable) | (Y/N)"].iloc[0]=="N":
            print(size_data)
            (a, b), (c, d), (e, f) = size_data
            if a=="-" or b=="-":
                print("one or more size(s) chart is/are empty")
            metafield = f"""
<p>See our <a href="/pages/sizing-chart%20" target="_blank">Measuring Guide</a> for how to measure properly.</p>
<p>Measurements are in Centimeters.</p>
<table class="size" style="text-align: center;">
<colgroup> <col style="width: 60px;"> <col style="width: 60px;"> <col style="width: auto;"> <col style="width: auto;"> </colgroup>
<thead>
<tr>
<th class="size-head" colspan="2" style="text-align: center;">SIZE</th>
<th class="size-width">CHEST WIDTH (CM)</th>
<th class="size-width">LENGTH (CM)</th>
</tr>
</thead>
<tbody>
<!-- MULAI EDIT SIZE DARI SINI YAA -->
<tr>
<td class="size-isi">X/S</td>
<td class="size-isi">2-4</td>
<td class="size-isi">{a}</td>
<td class="size-isi">{b}</td>
</tr>
<tr>
<td class="size-isi">S/M</td>
<td class="size-isi">6-8</td>
<td class="size-isi">{c}</td>
<td class="size-isi">{d}</td>
</tr>
<tr>
<td class="size-isi">M/L</td>
<td class="size-isi">10-12</td>
<td class="size-isi">{e}</td>
<td class="size-isi">{f}</td>
</tr>
<!-- MULAI EDIT SIZE SAMPAI SINI YAA -->
</tbody>
</table>
        """
        print("success extract all available information")
        return metafield

    def get_barcodes(self,SKUs,sample):
        barcodes=[]
        print("processing barcodes")
        sku_upc_ID = "1k-gCMaXqDtzROFUbIX3DFnA_MpzK__8eDDWlkRLhnCc"
        try:
            if sample == True:
                values = _get_sheet_values(
                    sheet_id=sku_upc_ID,
                    worksheet_name="SAMPLE UPC LIST",
                    use_all_values=True,
                )
                header = values[4]
                rows = values[5:]
                df = pd.DataFrame(rows, columns = header)
                for sku in SKUs:
                    filtered = df[df["Lineitem sku"].str.contains(sku, case=False, na=False)]
                    barcodes.append(filtered["UPC Barcode"].iloc[0])
                    print(barcodes)
                return barcodes

            else:
                values = _get_sheet_values(
                    sheet_id=sku_upc_ID,
                    worksheet_name="PRODUCTION UPC LIST",
                    use_all_values=True,
                )

                header = values[5]
                rows = values[6:]
                df = pd.DataFrame(rows, columns = header)
                for sku in SKUs:
                    filtered = df[df["Lineitem sku"].str.contains(sku, case=False, na=False)]
                    barcodes.append(filtered["UPC Barcode"].iloc[0])
                    print(barcodes)
                return barcodes
        except:
            print("lol sku cant find the barcode!!!")
            barcodes =[0,0,0,0]

            return barcodes
       
    ##after a careful thought, better to make it in separate file
    def crop_image(self,image_raw_path_ref, image_raw_path_tar):

        i =0


        result = subprocess.run(
            [
                "exiftool",
                "-j",
                "-ImageWidth",
                "-ImageHeight",
                "-CropLeft",
                "-CropTop",
                "-CropRight",
                "-CropBottom",
                image_raw_path_ref
            ],
            capture_output=True,
            text=True
        )

        image_raw_path_tar=image_raw_path_ref ## for testing only

        data = json.loads(result.stdout)[0]

        width = data["ImageWidth"]
        height = data["ImageHeight"]

        left = int(data["CropLeft"]* width)
        top = int(data["CropTop"]* height)
        right = int(data["CropRight"] *width)
        bottom = int(data["CropBottom"] *height)

        img = Image.open(image_raw_path_tar)

        cropped = img.crop((left, top, right, bottom))

        cropped = cropped.resize((819, 1024), Image.LANCZOS)
        
        self.color_raw=self.color_raw.replace(" ","-").lower()
        self.product_name=self.product_name.replace(" ","-").lower()
        output_path = f"/Users/ptinfashion/Documents/SAS_L/wooden-ship-knits__{self.product_name}__{self.color_raw}-{i+1}.webp"
        cropped.save(output_path, "WEBP", quality = 100)

        print("image is saved to", output_path)

    def images(self):
        if "COTTON" in self.product_name:
            product_name = self.product_name.replace("COTTON","CT")
        if "CREW" in self.product_name:
            product_name = self.product_name.replace("CREW","CR")
        if "CHUNKY" in self.product_name:
            product_name = self.product_name.replace("CHUNKY", "CH")
        if "LIGHTWEIGHT" in self.product_name:
            product_name = self.product_name.replace("LIGHTWEIGHT","LW")
        if "/" in self.color_raw:
            color_raw = self.color_raw.replace("/"," ")
            images = []

        for i in range(6):
            image ={
            "src": f"https://cdn.shopify.com/s/files/1/1436/4400/files/wooden-ships-knits__{product_name.lower().replace(' ','-')}__{color_raw.lower().replace('/','-')}-{1+i}.webp",
            "alt": color_raw.lower().replace("/", "-")
            }
            images.append(image)
        return images 
    