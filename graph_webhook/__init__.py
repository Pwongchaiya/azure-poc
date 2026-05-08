import logging
import os
import json
import requests
import azure.functions as func
from dotenv import load_dotenv

load_dotenv()

def get_graph_token() -> str:
    """
    Acquires an access token from Azure AD for the Microsoft Graph API
    using the client credentials flow (app-only authentication).

    This flow is used when the application acts on its own behalf rather
    than on behalf of a signed-in user. It requires the app registration's
    client ID and client secret, plus the tenant ID.
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


def get_user_details(user_id: str, token: str) -> dict:
    """
    Fetches full user profile from Microsoft Graph using the user's object ID.

    The notification payload only contains the user's ID and the change type.
    This follow-up call retrieves the full profile including display name,
    email, UPN, department, and job title.
    """
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}"

    # Select only the fields we care about logging — avoids fetching the
    # entire user object which can be large and contain sensitive fields.
    params = {
        "$select": "id,displayName,userPrincipalName,mail,department,jobTitle,createdDateTime"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()

    return response.json()


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Entry point for the Graph webhook function.

    Microsoft Graph sends two types of requests to this endpoint:
    1. Validation requests — a one-time handshake when the subscription is
       first created. Graph sends a validationToken query parameter and
       expects it echoed back as plain text with a 200 status.
    2. Change notifications — the actual event payloads sent when a user
       is created or updated.
    """
    logging.info("graph_webhook triggered.")

    # ── Validation Handshake ──────────────────────────────────────────────────
    # When a new subscription is registered, Graph sends a GET or POST request
    # with a validationToken query parameter to confirm the endpoint is live
    # and under your control. You must echo it back within 10 seconds or the
    # subscription registration fails.
    validation_token = req.params.get("validationToken")
    if validation_token:
        logging.info("Graph subscription validation request received.")
        return func.HttpResponse(
            validation_token,
            status_code=200,
            mimetype="text/plain",
        )

    # ── Change Notification Processing ───────────────────────────────────────
    try:
        body = req.get_json()
    except ValueError:
        logging.error("Failed to parse request body as JSON.")
        return func.HttpResponse("Bad request", status_code=400)

    notifications = body.get("value", [])

    if not notifications:
        logging.warning("Received webhook call with no notifications in payload.")
        return func.HttpResponse("OK", status_code=200)

    # Acquire a Graph token once and reuse it for all user lookups in this
    # batch. Graph can send multiple notifications in a single request.
    try:
        token = get_graph_token()
    except requests.HTTPError as e:
        logging.error(f"Failed to acquire Graph token: {e}")
        return func.HttpResponse("Internal error", status_code=500)

    for notification in notifications:
        change_type = notification.get("changeType", "unknown")
        resource = notification.get("resource", "")

        # The resource field looks like "users/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        # Extract the user ID from the end of the resource path.
        user_id = resource.split("/")[-1] if "/" in resource else resource

        if not user_id:
            logging.warning(f"Could not extract user ID from resource: {resource}")
            continue

        logging.info(f"Processing {change_type} event for user ID: {user_id}")

        try:
            user = get_user_details(user_id, token)

            # Log a structured summary to both console and Application Insights.
            # logging.info() feeds into Application Insights automatically when
            # the APPLICATIONINSIGHTS_CONNECTION_STRING app setting is configured.
            log_entry = {
                "event": f"user_{change_type}",
                "userId": user.get("id"),
                "displayName": user.get("displayName"),
                "userPrincipalName": user.get("userPrincipalName"),
                "mail": user.get("mail"),
                "department": user.get("department"),
                "jobTitle": user.get("jobTitle"),
                "createdDateTime": user.get("createdDateTime"),
            }

            logging.info(f"User event logged: {json.dumps(log_entry, indent=2)}")

        except requests.HTTPError as e:
            # Log and continue — one failed user lookup should not block
            # processing the rest of the notifications in the batch.
            logging.error(f"Failed to fetch details for user {user_id}: {e}")
            continue

    # Graph expects a 202 Accepted response. Returning anything other than
    # a 2xx causes Graph to retry the notification.
    return func.HttpResponse("Accepted", status_code=202)