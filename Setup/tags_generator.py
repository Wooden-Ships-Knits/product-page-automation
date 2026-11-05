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


# =============================================================================
# TAG RULES — edit these tables, not the code below them.
#
# Matching is on the UPPERCASED style name:
#   ANY   -> every keyword that matches adds its tags
#   FIRST -> the first keyword that matches wins; key None = default
# A key can be one keyword ("HOODIE") or several (("MARLED", "HEATHERED")).
# Tag order in the output follows the order of these tables — keep it that way,
# the old product pages were built with this exact order.
# =============================================================================

ALWAYS = "sweater, sweaters, sweatshirt, outfit, outfits, casual"

COMPOSITION = [
    (("COTTON", "MERCER"), "cotton blend, cottons, cotton-vo"),
    (None,                 "wool blend, grassy"),
]

PLY = [
    ("CHUNKY", "chunky blend, chunky tag, chunky-vo"),
    (None,     "lightweight"),
]

SLEEVES = [
    # NOTE: 'vo-design-1' is repeated 3x for TEE — kept as-is from the original
    ("TEE",         "tee, top tee, tee-vo, sleeveless, short sleeve, vo-design-1"),
    ("TANK",        "tank, tanks, tank top, tank tops, tanktop, tanktops, vo-design-1, sleeveless"),
    ("3/4",         "3/4 sleeve, "),
    ("HALF SLEEVE", "short sleeve, Half Sleeve, half sleeve, vo-design-1"),
    (None,          "Long Sleeve, long sleeve, "),
]

SWEATER_TYPE = [
    ("ZIP",                     "zipper, cardigan, cardi"),
    (("CARDIGAN", "CARDI"),     "cardigan, cardi"),
    (None,                      "Pullover (Standard)"),
]

# independent keyword rules, applied BEFORE the sweater type
KEYWORDS_BEFORE_TYPE = {
    "HOODIE": "hoodie, hood, hoods",
}

# independent keyword rules, applied AFTER the sweater type
KEYWORDS_AFTER_TYPE = {
    "STRIPED":                "stripe, stripes",
    "PRINTED":                "hand printed, printed",
    ("MARLED", "HEATHERED"):  "heather, heathered, marl, marled, melange",
    "POCKET":                 "pocket, pockets",
    "CABLE":                  "cable, cables, cableknit, cable knit",
    " V ":                    "vneck, v neck, vneck-vo",       # spaces on purpose: not SYLVAN / CHEVRON
    "CREW":                   "crew, crewneck, crewneck-vo",
    ("COLLAR","POLO"):        "collar, collarneck",
    " T ":                    "turtleneck, turtle neck, mock neck, mockneck, mock-neck",
    ("COWL","COWLNECK"):      "cowl, cowl neck",
    "VEST":                   "vest",
}

# matched on the COLOR (first part before "/"), not the style
KEYWORDS_COLOR = {
    "MULTI": "Multi",
}


def _keys(key):
    return key if isinstance(key, tuple) else (key,)


def _any_match(text, rules):
    """Every rule whose keyword appears in `text`, in table order."""
    return [tags for key, tags in rules.items() if any(k in text for k in _keys(key))]


def _first_match(text, rules):
    """The first rule whose keyword appears in `text`; key None is the default."""
    for key, tags in rules:
        if key is None:
            return tags
        if any(k in text for k in _keys(key)):
            return tags
    return ""


def generate_tags(STYLE, COLOR):
    """Tags derived from the style name + color. Rules live in the tables above.

    Output is identical to the original if/else version (verified over every
    style in PP SY LIST) — including its duplicate tags.
    """
    style = STYLE.upper()
    color = COLOR.upper().split("/")[0]

    parts = [STYLE.lower(), ALWAYS]
    parts.append(_first_match(style, COMPOSITION))
    parts.append(_first_match(style, PLY))
    parts.append(_first_match(style, SLEEVES))
    parts += _any_match(style, KEYWORDS_BEFORE_TYPE)
    parts.append(_first_match(style, SWEATER_TYPE))
    parts += _any_match(style, KEYWORDS_AFTER_TYPE)
    parts += _any_match(color, KEYWORDS_COLOR)

    return ", ".join(p for p in parts if p) + ", "


# ----------------------------------------------------------------------------
# ORIGINAL version, replaced by the table-driven generate_tags() above.
# Kept for reference; delete once the new one has run for a while.
# ----------------------------------------------------------------------------
# def generate_tags(STYLE, COLOR): #loook for better method
#     style = STYLE.upper()
#     color = COLOR.upper()
#     color = color.split("/")[0]
#
#     tags = STYLE.lower()+", "
#
    #--------------- fundamental -----------------------
#     tags += "sweater, sweaters, sweatshirt, outfit, outfits, casual, "
    #-----------------tags of composition------------------
#     if style.split(" ")[-1] == "COTTON" or  style.split(" ")[-1]== "MERCER":
#         tags += "cotton blend, cottons, cotton-vo, "
#     else:
#         tags += "wool blend, grassy, "
#
#
    #----------------- ply ---------------------
#
#     if "CHUNKY" in style:
#         tags += "chunky blend, chunky tag, chunky-vo, "
#     else: tags += "lightweight, "
#
#
    #-----------------tags of-sleeves -------------------------
#
#     if "TEE" in style:
#         tags += "tee, top tee, tee-vo, vo-design-1, sleeveless, vo-design-1, short sleeve, vo-design-1, "
#     elif "3/4" in style:
#         tags += "3/4 sleeve, "
#     elif "HALF SLEEVE" in style :
#         tags += "Half Sleeve, half sleeve, vo-design-1, "
#     else:
#         tags +="Long Sleeve, long sleeve, "
#
    #--------------tags size------------------------
    # tags += "FILTERBY-X/S, FILTERBY-S/M, FILTERBY-M/L, FILTERBY-X/L, L/XL, X/L, "
#
    #-----------------tags of type sweater----------
#     if "HOODIE" in style:
#         tags += "hoodie, hood, hoods, "
#
#     if "ZIP" in style:
#         tags += "zipper, cardigan, cardi, "
#     elif "CARDIGAN" in style or "CARDI" in style:
#         tags += "cardigan, cardi, "
#     else: 
#         tags += "Pullover (Standard), "
#
    #---------------tags pattern -------------
#     if "STRIPED" in style:
#         tags+= "stripe, stripes, "
#
#     if "PRINTED" in style:
#         tags+= "hand printed, printed, "
#
#     if "MARLED" in style or "HEATHERED" in style:
#         tags += "heather, heathered, marl, marled, melange, "
#
    #----------------additional-----------------
#     if "POCKET" in style:
#         tags += "pocket, pockets, "
#
#     if "CABLE" in style:
#         tags += "cable, cables, cableknit, cable knit, "
#
    #-----------------neck----------------------
#     if " V " in style:
#         tags += "vneck, v neck, vneck-vo, "
#
#     if "CREW" in style:
#         tags+= "crew, crewneck, crewneck-vo, "
#
#     if "COLLAR" in style:
#         tags+= "collar, collarneck, "
#     if "MULTI" in color:
#         tags+= "Multi, "
    #-------------------------------------------------
#
#
#     return tags

def additional_tags(tags,sizes,qty, full_price=False):
    # full price = production type fixed / unfix (SALE == False)
    if full_price:
        tags += "full priced, "
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


    
