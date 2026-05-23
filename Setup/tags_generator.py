import Setup.setup as setup
from dotenv import load_dotenv
from pathlib import Path
import os
# load_dotenv(Path(__file__).parent / "Setup/.env", override=True)

# # setup._get_sheet_values(
# #     sheet_id=os.getenv("PPA_SHEET_ID"),
# #     worksheet_name="Color list",
# #     range_name="A:B",
# # )


def generate_tags(STYLE, COLOR): #loook for better method
    style = STYLE.upper()
    color = COLOR.upper()
    color = color.split("/")[0]

    tags = STYLE.lower()+", "

    #--------------- fundamental -----------------------
    tags += "sweater, sweaters, sweatshirt, outfit, outfits, casual, "
    #-----------------tags of composition------------------
    if style.split(" ")[-1] == "COTTON" or  style.split(" ")[-1]== "MERCER":
        tags += "cotton blend, cottons, cotton-vo, "
    else:
        tags += "wool blend, grassy, "


    #----------------- ply ---------------------

    if "CHUNKY" in style:
        tags += "chunky blend, chunky tag, chunky-vo, "
    else: tags += "lightweight, "


    #-----------------tags of-sleeves -------------------------

    if "TEE" in style:
        tags += "tee, top tee, tee-vo, vo-design-1, sleeveless, vo-design-1, short sleeve, vo-design-1, "
    elif "3/4" in style:
        tags += "3/4 sleeve, "
    elif "HALF SLEEVE" in style :
        tags += "Half Sleeve, half sleeve, vo-design-1, "
    else:
        tags +="Long Sleeve, long sleeve, "

    #--------------tags size------------------------
    # tags += "FILTERBY-X/S, FILTERBY-S/M, FILTERBY-M/L, FILTERBY-X/L, L/XL, X/L, "

    #-----------------tags of type sweater----------
    if "HOODIE" in style:
        tags += "hoodie, hood, hoods, "

    if "ZIP" in style:
        tags += "zipper, cardigan, cardi, "
    elif "CARDIGAN" in style or "CARDI" in style:
        tags += "cardigan, cardi, "
    else: 
        tags += "Pullover (Standard), "
        
    #---------------tags pattern -------------
    if "STRIPED" in style:
        tags+= "stripe, stripes, "

    if "PRINTED" in style:
        tags+= "hand printed, printed, "

    if "MARLED" in style or "HEATHERED" in style:
        tags += "heather, heathered, marl, marled, melange, "

    #----------------additional-----------------
    if "POCKET" in style:
        tags += "pocket, pockets, "

    if "CABLE" in style:
        tags += "cable, cables, cableknit, cable knit, "

    #-----------------neck----------------------
    if " V " in style:
        tags += "vneck, v neck, vneck-vo, "

    if "CREW" in style:
        tags+= "crew, crewneck, crewneck-vo, "

    if "COLLAR" in style:
        tags+= "collar, collarneck, "
    if "MULTI" in color:
        tags+= "Multi, "
    #-------------------------------------------------
    
    
    return tags

def additional_tags(tags,sizes,qty):
    if qty is not None:
        try:
            qty = int(str(qty).strip() or 0)
        except (TypeError, ValueError):
            qty = 0
    if qty==1:
        tags+="LAST ONE LEFT!, "
        tmp_suffix = "nearly-gone"
    elif qty != None:
        print(qty)
        if qty <6:
            tags+= "NEARLY GONE!, "
            tmp_suffix = "nearly-gone"
        else:
            tmp_suffix = None
    else: tmp_suffix = None
    if "X/S" in sizes:
        tags+= "FILTERBY-X/S, "
    if "S/M" in sizes:
        tags+= "FILTERBY-S/M, "
    if "M/L" in sizes:
        tags+= "FILTERBY-M/L, "
    if "X/L" in sizes:
        tags+= "FILTERBY-X/L, L/XL, X/L, "

    return tags, tmp_suffix


    
