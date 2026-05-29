from Setup import setup
import pandas as pd
import os
from dotenv import load_dotenv
from config.varia import IM_header
from pathlib import Path
import time
from Setup import tags_generator as t, generic_color_generator as gcg, setup
from datetime import datetime
load_dotenv(Path(__file__).parent / "Setup/.env", override=True)
sheet = setup.sheet
import requests
headers = setup.HEADERS
"""
This is for fetching all the information needed for a style 
"""

class ProductInfo:
    def __init__(self,style, color,season,sample , sale, sas):
        self.style = style
        self.color = color
        self.season = season.title()
        self.sample = sample
        self.sale = sale
        self.seasonal_letter = season.split()[1][0]
        self.sas = sas
        self.season_code = self.seasonal_letter+season.split()[0]           # 26 SPRING -> S26
        self.IM_path = f"/Users/woodenship/Library/CloudStorage/GoogleDrive-web@pt-infashion.com/Shared drives/PTIF SERVER/Collection/{self.season}/IM/{self.season_code} IM MASTER.xlsx"
        # self.IM_path = f"Copy of {self.season_code} IM MASTER.xlsx"
        self.sizes = ["X/S (2/4)", "S/M (6/8)", "M/L (10/12)", "X/L (14/16)"]
        if self.seasonal_letter=="S":
            self.cat_code = f"K{(int(season.split()[0])+ 2)*2}"
        elif self.seasonal_letter =="F":
            self.cat_code = f"K{(int(season.split()[0])+ 2)*2+1}"

    def title_and_desc(self):
        print("processing title page")
        title_page = f"{self.style}"
        sale_title_page = f"*SALE* - {self.style}"
        ############################## Thread Type  ####################################
        thread = self.style.split(" ")
        if thread[-1]=="COTTON" or thread[-1]=="MERCER":
            thread_comp = "<p>Composition: 60% cotton, 40% acrylic</p>"
        else:
            thread_comp = "<p>Composition: 76% acrylic, 12% Mohair and 12% Wool</p>"

        ############################## Sale desc  ####################################
        if self.sample == True:
            sale_desc = """
            <p><meta charset="utf-8"><span data-mce-fragment="1">Sale items are FINAL SALE: No Returns, Refunds, or Exchanges. </span><span data-mce-fragment="1">&nbsp;</span><br data-mce-fragment="1"><span data-mce-fragment="1">Why is this on Sale? These pieces are knit as samples for our wholesale business. They have been handled during sales appointments, but they are carefully inspected before shipping.</span></p>
            """
        elif self.sample == True and self.sas == True:  
            sale_desc="""
            <p><meta charset="utf-8"><span data-mce-fragment="1">Sale items are FINAL SALE: No Returns, Refunds or Exchanges. </span><span data-mce-fragment="1"> </span><br data-mce-fragment="1"><span data-mce-fragment="1">Why is this on Sale? Sometimes a shopper changes their mind leaving us with perfectly fabulous sweaters, or we have extra yarn with which we knit new sweaters.</span></p>
            """
        else:
            sale_desc= ""

        if self.sale == True:
            title_page = sale_title_page
        return title_page, sale_title_page, sale_desc, thread_comp
    
    def _master_data(self):
        values_md = setup._get_sheet_values(
            sheet_id=os.getenv("MASTER_DATA_ID"),
            worksheet_name=self.season_code,
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

        header_level_1 = forward_fill(values_md[9])
        header_level_2 = forward_fill(values_md[10])
        header_level_3 = forward_fill(values_md[11])
        rows = values_md[12:]
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

        df_md = pd.DataFrame(rows, columns=combined_headers)
        
        df_md = df_md[df_md["FROM IM | DESCRIPTION"].str.contains(self.style, case=False, na=False)&
                df_md["FROM IM | COLOR"].str.contains(self.color, case=False, na=False)]
        
        return df_md

    def _IM_data(self):
        return setup._read_excel_cached(self.IM_path, header=IM_header)
    
    def _ppa_data(self,worksheet_name):
        values = setup._get_sheet_values(
            sheet_id=os.getenv("PPA_SHEET_ID"),
            worksheet_name=worksheet_name,
            use_all_values=True,
        )
        return values

    def get_weight(self):
        df_im = self._IM_data()
        df_im = df_im[df_im["DESCRIPTION"].str.contains(self.style, case=False, na=False)&
            df_im["WS TAG COLOR"].str.contains(self.color, case=False, na=False)]
        
        if self.sample ==True:
            df_im = df_im[df_im["DESCRIPTION"].str.contains('S/M', case=False, na=False)]

        weights = (df_im["PRE COMPONENT WT (PC WT)"].astype(float) * 1000).round().astype(int).tolist()
        sizes = df_im["DESCRIPTION"].str.split(" - ").str[-1].tolist()
        return sizes, weights

    def get_sizes(self):
        return ('X/S','S/M','M/L','X/L')
        ## this was added in newer vesion

    def get_sku_barcode(self):
        if self.sample ==True:
            sheet_name = "SAMPLE UPC LIST"
        else:
            sheet_name = "PRODUCTION UPC LIST"

        values = setup._get_sheet_values(
        sheet_id=os.getenv("SKU_UPC_ID"),
        worksheet_name=sheet_name,
        use_all_values=True,
        )

        df = pd.DataFrame(values[5:], columns=values[4]) ### need to inform PPIC we should change the header row
        
        df= df[
            df["Style"].str.contains(self.style, case=False, na=False) &
            df["Color"].str.contains(self.color, case=False, na=False)## need an adjustment for this when we 
        ]
        if self.sas ==True:
            df= df[df["Lineitem sku"].str.contains(f"P{self.cat_code}", case=False, na=False)]
        else:
           df = df[df["Lineitem sku"].str.contains(self.cat_code, case=False, na=False)]

        if self.sample == True:
            barcodes, skus = [0,df["UPC Barcode"].iloc[0],0,0], [0,df["Lineitem sku"].iloc[0],0,0]
        else: 
            barcodes, skus = df["UPC Barcode"].tolist(), df["Lineitem sku"].tolist()

        return barcodes, skus
    
    def get_generic_color(self):
        generic_colors = []
        values = self._ppa_data(worksheet_name='Color list')
        df = pd.DataFrame(values[1:], columns=values[0])
        color_list = self.color.split("/") if "/" in self.color else [self.color]
        for color in color_list:
            print(color)
            color = color.strip()
            matched_row = df[df['COLOR'].str.contains(color, case=False, na=False)]
            if not matched_row.empty:
                gc = matched_row['GENERIC COLOR (AI GENERATED)'].iloc[0]
                generic_colors.append(gc)
            else:
                print('Generic color not found. adding new color....')
                gc = gcg.gpt_choose_color(color)
                generic_colors.append(gc)
                df = pd.concat(
                    [df, pd.DataFrame([{"COLOR": color, "GENERIC COLOR (AI GENERATED)": gc }])],
                    ignore_index=True
                )

                sheet.values().update(
                spreadsheetId=os.getenv('PPA_SHEET_ID'),
                range='Color list!A2',
                valueInputOption="RAW",
                body={"values": df.fillna("").astype(str).values.tolist()}
                ).execute()

        return generic_colors

    def get_metachart(self):
        df = self._master_data()

        row = df.iloc[0]

        width_updated_cols = [
            col for col in df.columns
            if "UPDATED SIZE" in col and "Width" in col
        ]

        width_original_cols = [
            col for col in df.columns
            if "ORIGINAL SIZE" in col and "Width" in col
        ]

        length_updated_cols = [
            col for col in df.columns
            if "UPDATED SIZE" in col and "Length" in col
        ]

        length_original_cols = [
            col for col in df.columns
            if "ORIGINAL SIZE" in col and "Length" in col
        ]

        if df["DEV | XL | (Y/N)"].iloc[0]=="Y":
            XL = True
            size_order = ["X/S", "S/M", "M/L", "X/L"]
        elif df["DEV | XL | (Y/N)"].iloc[0]=="N":
            XL = False
            size_order = ["X/S", "S/M", "M/L"]
        else: 
            XL = True
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

        if XL ==True: 
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


        elif XL == False:
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
        # print("success extract all available information")
        return metafield, size_order
    
    def get_price(self):
        df = self._master_data()

        def _first_value(pattern):
            idx = df.columns.str.contains(pattern).argmax()
            return df.iat[0, idx]

        IM_price = _first_value("IM PRICE")
        latest_full_price = _first_value("LATEST FULL PRICE")
        full_price = _first_value("PB ADJUSTED FULL PRICE")
        latest_sale_price = _first_value("LATEST SALE PRICE")
        sale_price = _first_value("PB ADJUSTED SALE PRICE")

        if sale_price == "" or "N/A" in str(sale_price) or sale_price=="NO NEED FOR NOW":
            sale_price = latest_sale_price
            if sale_price == "" or "N/A" in str(sale_price) or sale_price=="NO NEED FOR NOW":
                sale_price = ""

        if full_price == "" or "N/A" in str(full_price) or full_price=="NO NEED FOR NOW":
            full_price = latest_full_price
            if full_price == "" or "N/A" in str(full_price) or full_price=="NO NEED FOR NOW":
                full_price = IM_price  

        if self.sale == False:
            sale_price = full_price
            full_price =""
            
        price = sale_price

        return full_price,price

    def get_SEL(self):
        #------------------ sale details
        if self.sale == True:
            sale_url = "sale-"
            sale_title = "SALE - "

        else: 
            sale_url = ""
            sale_title = ""

        #------------------ PAGE TITLE ------------------ 
        page_title =f"{sale_title}{self.style.title()} Sweater - {self.color.replace('/',' ').title()} | Wooden Ships"

        #------------- generic color fetch --------------
        generic_colors = self.get_generic_color()
        colors = self.color.split("/")
        text_generic_colors = []
        for i, c, in enumerate(generic_colors):
            if c.upper() in self.color.split("/")[i].upper():
                text_generic_colors.append("")
            else:
                text_generic_colors.append(f" {c}")

        print(text_generic_colors)

        #------------- meta description ---------------------
        if len(generic_colors) == 1:
            meta_desc = f"Shop the {self.style.title()} Sweater in {colors[0].title()}{text_generic_colors[0].title()} at Wooden Ships. Free shipping for any full-price sweaters."
        elif len(generic_colors) == 2:
            meta_desc = f"Shop the {self.style.title()} Sweater in {colors[0].title()}{text_generic_colors[0].title()} and {colors[1].title()}{text_generic_colors[1].title()} at Wooden Ships. Free shipping for any full-price sweaters."
        elif len(generic_colors)==3:
            meta_desc = f"Shop the {self.style.title()} Sweater in {colors[0].title()}{text_generic_colors[0].title()}, {colors[1].title()}{text_generic_colors[1].title()}, and {colors[2].title()}{text_generic_colors[2].title()} at Wooden Ships. Free shipping for any full-price sweaters."

        #------------- url ---------------------
        product_url = self.style.lower().replace(" ", "-")
        color_url = self.color.lower().replace("/", " ")
        color_url  =  color_url.replace(" ","-")


    
        # url = f"{sale_url}{product_url}-sweater-{color_url}{text_generic_colors[0].replace(' ', '-').lower()}-{int(time.time())}" # doesnt need this method anymore
        url = f"{sale_url}{product_url}-sweater-{color_url}{text_generic_colors[0].replace(' ', '-').lower()}"
        
        return page_title, meta_desc, url

    def get_type(self): #look for better method
        if " V " in self.style:
            type = "V-neck"
        elif "CREW" in self.style:
            type = "Crewneck"
        elif "CARDI" in self.style:
            type = "Cardigan"
        elif " T " in self.style:
            type = "T-neck"
        elif " COLLAR " in self.style:
            type = "Collar"
        else: type = ""

        return type

    def get_tags(self):  
        tags = t.generate_tags(self.style,self.color)
        if self.sale == True:
            if self.sample == True:
                tags+="no-returns, Sample, Sale, Off, Garage, Discount, Disc, final-sale, "
            elif self.sas == True:
                tags+= "no-returns, Obsolete, Sale, Off, Garage, Discount, Disc, Open Stock, Open Obsolete, check-qty, final-sale, "
            else:
                tags +="no-returns, Stock, Sale, Off, Garage, Discount, Disc, Additional Stock, additional discontinue items, final-sale, "

        df_ssi = self._master_data()

        if df_ssi["DEV | XL | (Y/N)"].iloc[0]=="N":
            tags = tags.replace("FILTERBY-X/L, L/XL, X/L, ","") 

        if df_ssi["WEB | PRINTED | (Y/N)"].iloc[0] == "Y":
            tags += "hand printed, printed, "

        generic_color = self.get_generic_color()[0].title()

        if generic_color== "Purple":
            generic_color = f"{generic_color}, Violet"
        if generic_color== "White" or generic_color=="Black" or generic_color=="Grey" or generic_color=="Brown":
            generic_color = f"{generic_color}, Neutral, "
        if generic_color=="Grey":
            generic_color = f"{generic_color}, Gray"
        if generic_color=="Brown":
            generic_color = f"{generic_color}, Chocolate, Tan, Cream, Nude"

        tags +=f"{generic_color}, "

        tags += f"Additional {datetime.now().strftime('%b %-d %Y')}, "

        return tags

    def get_NE_qty(self):
        df = self._ppa_data('NE STOCK')
        df = pd.DataFrame(df[1:], columns=df[0])
        df = df[
            df['style'].str.contains(self.style,case=False, na=False)&
            df['color'].str.contains(self.color, case=False, na=False)
        ]
        if df.empty:
            return [0, 0, 0, 0], ["", "", "", ""]
        sku_no_size = df['style_code'].iloc[0]+"-"+df['color'].iloc[0]
        skus = [sku_no_size+'-X/S',sku_no_size+'-S/M',sku_no_size+'-M/L',sku_no_size+'-X/L']
        qty_ne = [df['X/S'].iloc[0],df['S/M'].iloc[0],df['M/L'].iloc[0],df['X/L'].iloc[0]]
        return qty_ne, skus

    def get_BALI_qty(self):
        df = self._ppa_data('BALI STOCK')
        df = pd.DataFrame(df[1:], columns=df[0])
        df = df[
            df['style'].str.contains(self.style,case=False, na=False)&
            df['color'].str.contains(self.color, case=False, na=False)
        ]
        if df.empty:
            return [0, 0, 0, 0], ["", "", "", ""]
        sku_no_size = df['style_code'].iloc[0]+"-"+df['color'].iloc[0]
        skus = [sku_no_size+'-X/S',sku_no_size+'-S/M',sku_no_size+'-M/L',sku_no_size+'-X/L']
        qty_ba = [df['X/S'].iloc[0],df['S/M'].iloc[0],df['M/L'].iloc[0],0]
        return qty_ba, skus

    def get_sample_qty(self):
        df = self._ppa_data('NE SAMPLE STOCK')
        df = pd.DataFrame(df[1:], columns=df[0])
        df = df[
            df['style'].str.contains(self.style,case=False, na=False)&
            df['color'].str.contains(self.color, case=False, na=False)
        ]
        if not df.empty:
            qty = df['S/M'].iloc[0]
        else: 
            qty = 0
        return qty
    
    def fetch_barcode(self, skus):
        values = setup._get_sheet_values(
            sheet_id=os.getenv("SKU_UPC_ID"),
            worksheet_name="PRODUCTION UPC LIST",
            use_all_values=True
        )
        df = pd.DataFrame(values[5:], columns=values[4])

        sku_to_barcode = dict(zip(
            df['Lineitem sku'].astype(str).str.strip().str.upper(),
            df['UPC Barcode'].astype(str)
        ))

        barcodes = []
        for sku in skus:
            key = str(sku).strip().upper()
            barcodes.append(sku_to_barcode.get(key, ""))
        return barcodes

    def get_image(self):
        values = self._ppa_data('Links storage')
        df = pd.DataFrame(values[1:],columns=values[0])

        product_name = f" {self.style} "
        product_name = product_name.replace(" COTTON ", " CT ") \
                                .replace(" CREW ", " CR ") \
                                .replace(" CHUNKY ", " CH ") \
                                .replace(" LIGHTWEIGHT ", " LW ")
        product_name = product_name.strip()
        color_raw = self.color.replace("/"," ")
        file_name_template = f"{product_name.lower().replace(' ','-')}__{color_raw.lower().replace(' ','-')}"

        dfc = df[df["Filename"].str.contains(file_name_template,case=False,na=False)]
        
        if dfc.empty:
            file_name_template_alter = f"{self.style.lower().replace(' ','-')}__{color_raw.lower().replace(' ','-')}"
            dfc = df[df["Filename"].str.contains(file_name_template_alter,case=False,na=False)]
        alt = color_raw.lower().replace(" ", "-")
        images = [
            {"src": url, "alt": alt}
            for url in dfc["URL"].tolist()
        ]
        if not images:
            print(f"!!!! No images found in Links storage for template: {file_name_template} and {file_name_template_alter}!!!")
        
        return images 

        df_im = self._IM_data()
        df_im = df_im[df_im["DESCRIPTION"].str.contains(self.style, case=False, na=False)&
            df_im["WS TAG COLOR"].str.contains(self.colors[0], case=False, na=False)]

        weights = (df_im["PRE COMPONENT WT (PC WT)"].astype(float) * 1000).round().astype(int).tolist()
        return weights