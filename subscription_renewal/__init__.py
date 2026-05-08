import logging
import os
import requests
import azure.functions as func

def get_graph_token() -> str:
    """
    Acquires an app-only access token from Azure AD for Microsoft Graph.
    Identical to the one in graph_webhook — in a larger project this would
    live in a shared utility module to avoid duplication.
    """
    tenant_id = os.environ["GRAPH_TENANT_ID"]
    client_id = os.environ["GRAPH_CLIENT_ID"]
    client_secret = os.environ["GRAPH_CLIENT_SECRET"]

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }

    response = requests.post(url, data=payload, timeout=10)
    response.raise_for_status()

    return response.json()["access_token"]


def main(mytimer: func.TimerRequest) -> None:
    """
    Timer-triggered function that renews the Microsoft Graph webhook
    subscription every 2 days.

    Graph subscriptions for Azure AD user resources expire after a maximum
    of 3 days. If the subscription expires, Graph stops sending notifications
    and you lose visibility into user events until a new subscription is
    manually created. This function keeps the subscription alive automatically.

    The GRAPH_SUBSCRIPTION_ID app setting must be populated after the initial
    subscription is created via setup_graph_subscription.py.
    """
    logging.info("subscription_renewal timer triggered.")

    if mytimer.past_due:
        # past_due is True if the timer fired later than scheduled — for
        # example if the function app was cold and the timer missed its window.
        # Log it but proceed with renewal anyway.
        logging.warning("Timer is past due — proceeding with renewal regardless.")

    subscription_id = os.environ.get("GRAPH_SUBSCRIPTION_ID")

    if not subscription_id:
        logging.error(
            "GRAPH_SUBSCRIPTION_ID app setting is not set. "
            "Run setup_graph_subscription.py first to create the initial subscription, "
            "then add the returned subscription ID as an app setting."
        )
        return

    try:
        token = get_graph_token()
    except requests.HTTPError as e:
        logging.error(f"Failed to acquire Graph token during renewal: {e}")
        return

    # Extend the subscription expiration by another 3 days from now.
    # The expirationDateTime must be in ISO 8601 UTC format.
    # We use a fixed offset rather than computing from the current expiry
    # to keep this simple — we always extend by the maximum allowed duration.
    from datetime import datetime, timezone, timedelta
    new_expiry = (datetime.now(timezone.utc) + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%S.0000000Z"
    )

    url = f"https://graph.microsoft.com/v1.0/subscriptions/{subscription_id}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "expirationDateTime": new_expiry
    }

    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        logging.info(
            f"Subscription {subscription_id} successfully renewed. "
            f"New expiry: {new_expiry}"
        )

    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"

        if status == 404:
            # The subscription no longer exists — it may have already expired.
            # Log clearly so the developer knows they need to re-run the
            # setup script to create a fresh subscription.
            logging.error(
                f"Subscription {subscription_id} not found (404). "
                "It may have already expired. Re-run setup_graph_subscription.py "
                "to create a new subscription and update GRAPH_SUBSCRIPTION_ID."
            )
        else:
            logging.error(f"Failed to renew subscription {subscription_id}: {e}")