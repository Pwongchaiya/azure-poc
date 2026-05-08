import requests
import os
from dotenv import load_dotenv

load_dotenv()

tenant = os.environ["GRAPH_TENANT_ID"]
client = os.environ["GRAPH_CLIENT_ID"]
secret = os.environ["GRAPH_CLIENT_SECRET"]

# Get token
r = requests.post(
    f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
    data={
        "grant_type": "client_credentials",
        "client_id": client,
        "client_secret": secret,
        "scope": "https://graph.microsoft.com/.default"
    }
)
token = r.json()["access_token"]

# List subscriptions
r = requests.get(
    "https://graph.microsoft.com/v1.0/subscriptions",
    headers={"Authorization": f"Bearer {token}"}
)
print(r.json())