#!/usr/bin/env python3
"""
setup_graph_subscription.py

Run this script ONCE after deploying the Function App to register the
Microsoft Graph change notification subscription. It points Graph at your
Function App's webhook endpoint and tells it to notify you when users are
created or updated in your Azure AD tenant.

Prerequisites:
  - The Function App must already be deployed (graph_webhook must be live)
  - pip install requests

Usage:
  python setup_graph_subscription.py

After running, copy the subscription ID printed at the end and add it as
an app setting on your Function App:

  az functionapp config appsettings set \
    --name <FUNCTION_APP_NAME> \
    --resource-group <RESOURCE_GROUP> \
    --settings GRAPH_SUBSCRIPTION_ID=<subscription-id>
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Configuration — fill these in before running ──────────────────────────────
TENANT_ID = os.environ.get("GRAPH_TENANT_ID", "<your-tenant-id>")
CLIENT_ID = os.environ.get("GRAPH_CLIENT_ID", "<your-client-id>")
CLIENT_SECRET = os.environ.get("GRAPH_CLIENT_SECRET", "<your-client-secret>")
AZURE_FUNCTION_APP_NAME = os.environ.get("AZURE_FUNCTION_APP_NAME", "<your-function-app-name>")

# The full URL of your deployed graph_webhook function.
# Replace with your actual Function App name.
NOTIFICATION_URL = os.environ.get(
    "GRAPH_NOTIFICATION_URL",
    f"https://{AZURE_FUNCTION_APP_NAME}.azurewebsites.net/api/graph_webhook"
)

print(TENANT_ID, CLIENT_ID, CLIENT_SECRET, NOTIFICATION_URL)


def get_token() -> str:
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }
    response = requests.post(url, data=payload, timeout=10)
    response.raise_for_status()
    return response.json()["access_token"]


def create_subscription(token: str) -> dict:
    url = "https://graph.microsoft.com/v1.0/subscriptions"

    # Subscriptions for Azure AD user resources expire after a maximum of
    # 3 days. The subscription_renewal function handles auto-renewal.
    expiry = (datetime.now(timezone.utc) + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%S.0000000Z"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        # "users" resource with no filter means all users in the tenant.
        "resource": "users",

        # Listen for both created and updated events.
        "changeType": "created,updated",

        # The URL Graph will POST notifications to. Must be HTTPS and
        # publicly reachable — localhost will not work.
        "notificationUrl": NOTIFICATION_URL,

        # A secret value included in every notification payload so your
        # function can verify the request genuinely came from Graph.
        # Store this securely in production.
        "clientState": "azure-poc-webhook-secret",

        "expirationDateTime": expiry,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=10)

    if response.status_code != 201:
        print(f"\nError creating subscription:")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
        sys.exit(1)

    return response.json()


def main():
    print("──────────────────────────────────────────")
    print(" Microsoft Graph Subscription Setup")
    print("──────────────────────────────────────────")

    if "<your" in TENANT_ID or "<your" in CLIENT_ID or "<your" in CLIENT_SECRET or "<your" in NOTIFICATION_URL:
        print("\nError: One or more configuration values are still placeholders.")
        print("Set the following environment variables before running:")
        print("  GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_NOTIFICATION_URL")
        sys.exit(1)

    print("\n[1/2] Acquiring Graph token...")
    try:
        token = get_token()
        print("      ✓ Token acquired.")
    except requests.HTTPError as e:
        print(f"      ✗ Failed to acquire token: {e}")
        sys.exit(1)

    print("[2/2] Creating subscription...")
    subscription = create_subscription(token)

    print("\n══════════════════════════════════════════")
    print(" Subscription created successfully.")
    print("══════════════════════════════════════════")
    print(f"\n  Subscription ID : {subscription['id']}")
    print(f"  Resource        : {subscription['resource']}")
    print(f"  Change Types    : {subscription['changeType']}")
    print(f"  Expires         : {subscription['expirationDateTime']}")
    print(f"\n Add this as an app setting on your Function App:")
    print(f"\n  az functionapp config appsettings set \\")
    print(f"    --name <FUNCTION_APP_NAME> \\")
    print(f"    --resource-group <RESOURCE_GROUP> \\")
    print(f"    --settings GRAPH_SUBSCRIPTION_ID={subscription['id']}")
    print()


if __name__ == "__main__":
    main()