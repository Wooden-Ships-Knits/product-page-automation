"""
List images / files stored in Shopify's content (Files API).

Usage:
    from Setup.fetch_images_name_link import list_shop_files

    # all files
    files = list_shop_files()

    # filter by filename prefix
    files = list_shop_files(query="filename:wooden-ships-knits*")
"""
import requests
try:
    from Setup import set_sy,setup
except ImportError:
    import set_sy,setup
from dotenv import load_dotenv
from pathlib import Path
import os
sheet = setup.sheet
load_dotenv(Path(__file__).parent / ".env", override=True)

headers = set_sy.headers_
url = "https://wooden-ships.myshopify.com/admin/api/2026-01/graphql.json"

query_gql = """
query ($cursor: String, $q: String) {
  files(first: 250, after: $cursor, query: $q) {
    edges {
      node {
        ... on MediaImage {
          id
          alt
          image { url }
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


def list_shop_files(query=None):
    """
    Fetch all MediaImage files from Shopify Files.
    Returns a list of dicts: {"id", "url", "filename", "alt"}.

    `query` accepts Shopify's file search syntax, e.g. "filename:foo*".
    """
    files = []
    cursor = None
    while True:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query_gql, "variables": {"cursor": cursor, "q": query}},
        )
        result = response.json()
        if "errors" in result:
            print("GraphQL errors:", result["errors"])
            break
        if "data" not in result or result["data"] is None:
            print("Unexpected response:", result)
            break
        data = result["data"]["files"]
        for edge in data["edges"]:
            node = edge["node"]
            img = node.get("image")
            if not img:
                continue
            file_url = img["url"]
            filename = file_url.split("/")[-1].split("?")[0]
            files.append({
                "id": node["id"],
                "url": file_url,
                "filename": filename,
                "alt": node.get("alt"),
            })
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return files


if __name__ == "__main__":
    matches = list_shop_files(query="filename:wooden-ships-knits*")
    matches = [f for f in matches if f["filename"].endswith(".webp")]

    header = ["ID", "URL", "Filename", "Alt"]
    rows = [
        [m["id"], m["url"], m["filename"], m.get("alt") or ""]
        for m in matches
    ]

    sheet.values().clear(
        spreadsheetId=os.getenv("PPA_SHEET_ID"),
        range="'Links storage'!A:D"
    ).execute()

    sheet.values().update(
        spreadsheetId=os.getenv("PPA_SHEET_ID"),
        range="'Links storage'!A1",
        valueInputOption="RAW",
        body={"values": [header] + rows}
    ).execute()
    print(f"Wrote {len(rows)} files to 'Links storage'")

    