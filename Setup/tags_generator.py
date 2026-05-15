"""
Create tags for each product page, so that we can easily search for them in the future
"""

def generate_tags(STYLE, COLOR):
    STYLE = STYLE.upper()
    COLOR = COLOR.upper()
    COLOR = COLOR.split("/")[0]

    tags = STYLE.lower()+", "

    #--------------- fundamental -----------------------
    tags += "sweater, sweaters, sweatshirt, outfit, outfits, casual, "
    #-----------------tags of composition------------------
    if STYLE.split(" ")[-1] == "COTTON" or  STYLE.split(" ")[-1]== "MERCER":
        tags += "cotton blend, cottons, cotton-vo, "
    else:
        tags += "wool blend, grassy, "


    #----------------- ply ---------------------

    if "CHUNKY" in STYLE:
        tags += "chunky blend, chunky tag, chunky-vo, "
    else: tags += "lightweight, "


    #-----------------tags of-sleeves -------------------------

    if "TEE" in STYLE:
        tags += "tee, top tee, tee-vo, vo-design-1, sleeveless, vo-design-1, short sleeve, vo-design-1, "
    elif "3/4" in STYLE:
        tags += "3/4 sleeve, "
    elif "HALF SLEEVE" in STYLE:
        tags += "Half Sleeve, half sleeve, vo-design-1, "
    else:
        tags +="Long Sleeve, long sleeve, "

    #--------------tags size------------------------
    tags += "FILTERBY-X/S, FILTERBY-S/M, FILTERBY-M/L, FILTERBY-X/L, L/XL, X/L, "

    #-----------------tags of type sweater----------
    if "HOODIE" in STYLE:
        tags += "hoodie, hood, hoods, "

    if "ZIP" in STYLE:
        tags += "zipper, cardigan, cardi, "
    elif "CARDIGAN" in STYLE or "CARDI" in STYLE:
        tags += "cardigan, cardi, "
    else: 
        tags += "Pullover (Standard), "
        
    #---------------tags pattern -------------
    if "STRIPED" in STYLE:
        tags+= "stripe, stripes, "

    if "PRINTED" in STYLE:
        tags+= "hand printed, printed, "

    if "MARLED" in STYLE or "HEATHERED" in STYLE:
        tags += "heather, heathered, marl, marled, melange, "

    #----------------additional-----------------
    if "POCKET" in STYLE:
        tags += "pocket, pockets, "

    if "CABLE" in STYLE:
        tags += "cable, cables, cableknit, cable knit, "

    #-----------------neck----------------------
    if " V " in STYLE:
        tags += "vneck, v neck, vneck-vo, "

    if "CREW" in STYLE:
        tags+= "crew, crewneck, crewneck-vo, "

    if "COLLAR" in STYLE:
        tags+= "collar, collarneck, "

    #-------------------------------------------------
    
    
    return tags


tags = generate_tags("KAYA STRIPED 3/4 SLEEVE V COTTON", "ALMOND BUTTER/BLACK")
print(tags)  