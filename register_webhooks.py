"""
Register / list / remove the Shopify product webhooks that feed webhook_receiver.py.

  venv/bin/python register_webhooks.py            # list current subscriptions
  venv/bin/python register_webhooks.py create     # subscribe PRODUCTS_CREATE/UPDATE/DELETE
  venv/bin/python register_webhooks.py delete     # remove the ones pointing at WEBHOOK_URL

WEBHOOK_URL defaults to the production domain; override with the env var for testing
(e.g. an ngrok URL). Run from the project root.
"""
import os
import sys

import requests

from Setup import set_sy

GRAPHQL_URL = "https://wooden-ships.myshopify.com/admin/api/2026-01/graphql.json"
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL", "https://product-page-automation.pt-infashion.com/shopify/webhook"
)
TOPICS = ["PRODUCTS_CREATE", "PRODUCTS_UPDATE", "PRODUCTS_DELETE"]


def gql(query, variables=None):
    r = requests.post(
        GRAPHQL_URL,
        headers=set_sy.headers_,
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def list_subscriptions():
    data = gql("""
    {
      webhookSubscriptions(first: 100) {
        edges { node { id topic uri } }
      }
    }
    """)
    return [e["node"] for e in data["webhookSubscriptions"]["edges"]]


def create():
    existing = {(s["topic"], s["uri"]) for s in list_subscriptions()}
    for topic in TOPICS:
        if (topic, WEBHOOK_URL) in existing:
            print(f"= {topic} already subscribed")
            continue
        data = gql("""
        mutation ($topic: WebhookSubscriptionTopic!, $sub: WebhookSubscriptionInput!) {
          webhookSubscriptionCreate(topic: $topic, webhookSubscription: $sub) {
            webhookSubscription { id }
            userErrors { field message }
          }
        }
        """, {"topic": topic, "sub": {"uri": WEBHOOK_URL, "format": "JSON"}})
        res = data["webhookSubscriptionCreate"]
        if res["userErrors"]:
            print(f"✗ {topic}: {res['userErrors']}")
        else:
            print(f"✓ {topic} -> {WEBHOOK_URL}")


def delete():
    for s in list_subscriptions():
        if s["uri"] != WEBHOOK_URL:
            continue
        data = gql("""
        mutation ($id: ID!) {
          webhookSubscriptionDelete(id: $id) { deletedWebhookSubscriptionId userErrors { message } }
        }
        """, {"id": s["id"]})
        print(f"✓ removed {s['topic']}", data["webhookSubscriptionDelete"]["userErrors"] or "")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    if action == "create":
        create()
    elif action == "delete":
        delete()
    for s in list_subscriptions():
        print(f"  {s['topic']:<18} {s['uri']}")
