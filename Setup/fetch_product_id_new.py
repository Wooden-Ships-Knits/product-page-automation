import requests
try:
  from Setup import set_sy, setup
except:
  import set_sy,setup
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import pandas as pd
from dotenv import load_dotenv
import os
from pathlib import Path
load_dotenv(Path(__file__).parent / "Setup/.env", override=True)

"""
Bagian ini digunakan untuk fetch Product ID yang diupload ke google sheet guna untuk menghindari duplicate product page jika sudah ada product page dengan style-color yang sama.
This section is used to fetch the Product ID uploaded to Google Sheets in order to avoid duplicate product pages when a product page with the same style-color already exists.
"""


headers = set_sy.headers_
sheet = setup.sheet
RANGE = "PP SY LIST!A2"

# -------------------------
# SHOPIFY GRAPHQL SETUP
# -------------------------
url = f"https://wooden-ships.myshopify.com/admin/api/2024-01/graphql.json"


query = """
query ($cursor: String) {
  products(first: 250, after: $cursor) {
    edges {
      node {
        id
        title
        status
        description
        variants(first: 1) {
          edges {
            node {
              selectedOptions {
                name
                value
              }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# -------------------------
# FETCH DATA
# -------------------------
def fetch():
  rows = []

  # Header row (matches your screenshot)
  rows.append([
      "Page Title",
      "Color",
      "Style",
      "Product ID",
      "Page Status",
      "FP/DC",
      "Description"
  ])

  cursor = None

  while True:
      response = requests.post(
          url,
          headers=headers,
          json={"query": query, "variables": {"cursor": cursor}}
      )

      data = response.json()["data"]["products"]

      for edge in data["edges"]:
          p = edge["node"]

          product_id = p["id"].split("/")[-1]
          title = p["title"]
          status = p["status"]
          description = p.get("description") or ""

          # Extract first variant color
          color = ""
          variants = p["variants"]["edges"]

          if variants:
              for opt in variants[0]["node"]["selectedOptions"]:
                  if opt["name"].lower() in ["color", "colour"]:
                      color = opt["value"]
                      break

          rows.append([
              title,
              color,
              "",             # Style (filled in preprocessing)
              product_id,
              status,
              "",             # FP/DC (filled in preprocessing)
              description,
          ])

      if not data["pageInfo"]["hasNextPage"]:
          break

      cursor = data["pageInfo"]["endCursor"]

  print(f"Fetched {len(rows)-1} products")

  # -------------------------
  # PREPROCESSING
  # -------------------------

  df = pd.DataFrame(rows[1:],columns=rows[0])

  df['Style'] = df['Page Title']
  df['Style'] = df['Style'].str.replace("*SALE* - ", "", regex=False)
  df['Style'] = df['Style'].str.replace("*SALE* ", "", regex=False)
  df['Style'] = df['Style'].str.replace("*SALE*- ", "", regex=False)
  df['Style'] = df['Style'].str.replace("SALE* - ", "", regex=False)
  df['Style'] = df['Style'].str.replace("*SALES* - ", "", regex=False)
  df['Style'] = df['Style'].str.replace("*SALE * - ", "", regex=False)
  df['Style'] = df['Style'].str.strip()
  df['FP/DC'] = ["DC" if "SALE" in d else "FP" for d in df['Page Title']]
  
  boilerplate = [
      "Composition: 60% Cotton, 40% Acrylic",
      "Composition: 76% acrylic, 12% Mohair and 12% Wool",
      "Sale items are FINAL SALE: No Returns, Refunds or Exchanges.\nWhy is this on Sale? Sometimes a shopper changes their mind leaving us with perfectly fabulous sweaters, or we have extra yarn with which we knit new sweaters.",
      "Sale items are FINAL SALE: No Returns, Refunds, or Exchanges.\nWhy is this on Sale? These pieces are knit as samples for our wholesale business. They have been handled during sales appointments, but they are carefully inspected before shipping.",
  ]
  for b in boilerplate:
      df['Description'] = df['Description'].str.replace(b, "", regex=False)
  df['Description'] = df['Description'].str.strip()
  df = df[['Style','Color','Product ID','Page Status','FP/DC','Description']]

  rows = df.values.tolist()
  
  # -------------------------
  # WRITE TO GOOGLE SHEETS
  # -------------------------
  sheet.values().clear(
      spreadsheetId=os.getenv("PPA_SHEET_ID"),
      range=RANGE
  ).execute()

  sheet.values().update(
      spreadsheetId=os.getenv("PPA_SHEET_ID"),
      range=RANGE,
      valueInputOption="RAW",
      body={"values": rows}
  ).execute()

  print("Data uploaded to Google Sheets ✅")

if __name__ == "__main__":
    fetch()