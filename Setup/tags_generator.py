"""
Create tags for each product page, so that we can easily search for them in the future
"""

def generate_tags(STYLE, COLOR):
    COLOR = COLOR.split("/")[0]
    tags = STYLE.lower()+", "
    #-----------------tags of composition------------------
    if STYLE.split(" ")[-1].uppper() == "COTTON" or  STYLE.split(" ")[-1].upper() == "MERCER":
        tags += "cotton blend, cottons, cotton-vo, "
    else:
        tagas += "wool blend, grassy, "

    
    #-----------------tags of 
    
    return tags


tags = generate_tags("T-Shirt", "Red")
print(tags)  