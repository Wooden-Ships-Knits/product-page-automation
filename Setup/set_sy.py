import requests

from dotenv import load_dotenv
import os
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env", override=True)

token_url = f"https://wooden-ships.myshopify.com/admin/oauth/access_token"
product_url = "https://wooden-ships.myshopify.com/admin/api/2026-01/products.json"



def get_token():
    r = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id":os.getenv("CLIENT_ID"),
            "client_secret":os.getenv("CLIENT_SECRET"),
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(
            f"Failed to obtain access token (HTTP {r.status_code}): {r.text} "
            f"(CLIENT_ID set: {bool(os.getenv('CLIENT_ID'))}, CLIENT_SECRET set: {bool(os.getenv('CLIENT_SECRET'))})"
        )
    return r.json()["access_token"]
    
headers_ = {
    "X-Shopify-Access-Token": get_token(),
    "Content-Type": "application/json"
}
    
def post_product_page(headers,product_data):
    response = requests.post(product_url, headers=headers, json=product_data)
    product = response.json()["product"]
    product_id = product["id"]

    if response.status_code != 201:
        print("Product creation failed:", response.text)
        # continue


def collection_release(collection,product_id,headers):
    collect_url = f"https://wooden-ships.myshopify.com/admin/api/2024-01/collects.json"
    ########## tax:clothing always the same########
    collect_data = {
            "collect": {
            "product_id": product_id,
            "collection_id": get_collection_id("tax:clothing")
        }
    }
    requests.post(collect_url, headers=headers_, json=collect_data)
    collection = collection.upper()
    if collection != "TRANSITION" or collection != "SAS":
        if collection == "LAKE" or collection == "BEACH" or collection == "BEACH & LAKE":
            collection = "BEACH + LAKE"
            collect_data ={
                    "collect": {
                    "product_id": product_id,
                    "collection_id": get_collection_id(collection)
                }
            }
    requests.post(collect_url, headers=headers_, json=collect_data)
    print("✅Successfully assigned to collections")

def publish_to_all_channels(product_id,sale=True):

    graphql_url = f"https://wooden-ships.myshopify.com/admin/api/2026-01/graphql.json"
    # Convert numeric ID to GraphQL GID
    gid_product = f"gid://shopify/Product/{product_id}"

    mutation = """
    mutation publishProduct($id: ID!, $input: [PublicationInput!]!) {
      publishablePublish(id: $id, input: $input) {
        userErrors {
          field
          message
        }
      }
    }
    """
    
    ALL_PUBLICATION_IDS = []

    query = """
    {
      publications(first: 20) {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """

    response = requests.post(
        graphql_url,
        headers=headers_,
        json={"query": query}
    )

    data = response.json()
    for edge in data["data"]["publications"]["edges"]:
        print(edge["node"]["name"], "|", edge["node"]["id"])
        if sale and edge["node"]["name"] == "Pinterest":
            continue
        else: 
            ALL_PUBLICATION_IDS.append(edge["node"]["id"])
    variables = {
        "id": gid_product,
        "input": [{"publicationId": pid} for pid in ALL_PUBLICATION_IDS]
    }

    response = requests.post(
        graphql_url,
        headers=headers_,
        json={"query": mutation, "variables": variables}
    )

    result = response.json()

    # Safety check
    if "errors" in result:
        print("GraphQL Errors:", result["errors"])
    elif result["data"]["publishablePublish"]["userErrors"]:
        print("User Errors:", result["data"]["publishablePublish"]["userErrors"])
    else:
        print("✅ Product assigned to all sales channels successfully.")

    return result

def get_collection_id(title):
    custom_collections_url = f"https://wooden-ships.myshopify.com/admin/api/2024-01/custom_collections.json"
    response = requests.get(custom_collections_url, headers=headers_)

    for c in response.json()["custom_collections"]:
        if c["title"] == title:
            return c["id"]

    return None

print(get_token())