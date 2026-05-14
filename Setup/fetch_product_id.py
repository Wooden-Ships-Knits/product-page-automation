import requests
import Setup.set_sy as set_sy
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
# -------------------------
# CONFIG
# -------------------------
SHOP = "wooden-ships"
SPREADSHEET_ID = "1CX6tjxos0N2p_YRmrgo6sA7KSPM5bZnBdyaQZuJWoCk"
RANGE = "Sheet1!A1"



# -------------------------
# GOOGLE SHEETS SETUP
# -------------------------
creds = Credentials.from_service_account_file(
    "credentials/dialy-report-automation-e20c53e67542.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)


service = build("sheets", "v4", credentials=creds)
sheet = service.spreadsheets()


# -------------------------
# SHOPIFY GRAPHQL SETUP
# -------------------------
url = f"https://{SHOP}.myshopify.com/admin/api/2024-01/graphql.json"

headers = {
    "X-Shopify-Access-Token": set_sy.get_token(),
    "Content-Type": "application/json"
}


query = """
query ($cursor: String) {
  products(first: 250, after: $cursor, query: "status:active OR status:draft") {
    edges {
      node {
        id
        title
        status
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
      "Style",
      "Color",
      "FP/DC",
      "Product ID",
      "Page Status",
      "Current Production Type"
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
              "",             # FP/DC
              product_id,
              status,
              ""              # Current Production Type
          ])

      if not data["pageInfo"]["hasNextPage"]:
          break

      cursor = data["pageInfo"]["endCursor"]

  print(f"Fetched {len(rows)-1} products")

  # -------------------------
  # WRITE TO GOOGLE SHEETS
  # -------------------------
  sheet.values().clear(
      spreadsheetId=SPREADSHEET_ID,
      range=RANGE
  ).execute()

  sheet.values().update(
      spreadsheetId=SPREADSHEET_ID,
      range=RANGE,
      valueInputOption="RAW",
      body={"values": rows}
  ).execute()

  print("Data uploaded to Google Sheets ✅")