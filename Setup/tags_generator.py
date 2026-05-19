import setup

setup._get_sheet_values(
    sheet_id=setup.PPA_SHEET_ID,
    worksheet_name="Color list",
    range_name="A:B",
)


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
    tags += "FILTERBY-X/S, FILTERBY-S/M, FILTERBY-M/L, FILTERBY-X/L, L/XL, X/L, "

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

    #-------------------------------------------------
    
    
    return tags