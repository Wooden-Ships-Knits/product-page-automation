from dotenv import load_dotenv
from openai import OpenAI
import setup
import os
import pandas as pd

load_dotenv()
client = OpenAI()

list_of_generic_color = [
    "Red",
    "Pink",
    "Peach",
    "Orange",
    "Yellow",
    "Green",
    "Blue",
    "Purple",
    "White",
    "Black",
    "Grey",
    "Brown",
    "Cream"
]

generic_colors = ", ".join(list_of_generic_color)

values = setup._get_sheet_values(
    os.getenv("PPA_SHEET_ID"),
    worksheet_name="Color list",
    range_name="A:B",
)

worksheet = setup._get_worksheet(
    os.getenv("PPA_SHEET_ID"),
    worksheet_name="Color list",
)

def ask_gpt(question):
    response = client.responses.create(
        model="gpt-5.4",
        input=question,
    )
    return response.output_text.strip()

def get_colors_to_fill(values):
    header = values[0]
    rows = [row + [""] * (len(header) - len(row)) for row in values[1:]]
    df = pd.DataFrame(rows, columns=header)

    return df.loc[
        df["GENERIC COLOR (AI GENERATED)"].fillna("").str.strip().eq(""), #GENERIC COLOR (AI GENERATED)
        "COLOR",
    ]

def fill_gen_color(worksheet, sheet_row, color):
    prompt = f"""
Please answer with only one word mentioning the generic color of this color: {color}.
Choose only from this list: ({generic_colors}).
"""
    worksheet.update(f"B{sheet_row}", [[ask_gpt(prompt)]])

if __name__ == "__main__":
    for df_index, color in get_colors_to_fill(values).items():
        fill_gen_color(worksheet, df_index + 2, color)
