# Azure Function Pipeline POC

A proof of concept for streamlining Azure Function deployment via GitHub Actions, with Microsoft Graph webhook integration for real-time Azure AD user event tracking.

## Overview

This project demonstrates an end-to-end CI/CD pipeline that automatically deploys Python-based Azure Functions on every push to `main`. Authentication is handled via OIDC (Workload Identity Federation), eliminating the need for long-lived credentials stored as secrets.

The pipeline includes three functions: a basic HTTP trigger, a Microsoft Graph webhook that logs user created and updated events from Azure AD, and a timer function that automatically renews the Graph webhook subscription every 48 hours.

## Stack

- **Runtime:** Python 3.11
- **Platform:** Azure Functions v4 (Consumption plan)
- **CI/CD:** GitHub Actions
- **Auth:** OIDC via Azure Managed Identity + Federated Credentials
- **Infrastructure:** Provisioned via Azure CLI (`setup-azure.sh`)
- **API Integration:** Microsoft Graph API (change notifications)

## Project Structure

```
├── .github/
│   └── workflows/
│       └── deploy.yml                  # GitHub Actions deployment workflow
├── hello_function/
│   ├── __init__.py                     # HTTP trigger — returns hello message
│   └── function.json                   # Binding configuration
├── graph_webhook/
│   ├── __init__.py                     # HTTP trigger — receives Graph change notifications
│   └── function.json                   # Binding configuration
├── subscription_renewal/
│   ├── __init__.py                     # Timer trigger — renews Graph subscription every 48hrs
│   └── function.json                   # Binding configuration
├── host.json                           # Azure Functions host configuration
├── requirements.txt                    # Python dependencies
├── setup-azure.sh                      # Azure resource provisioning script
├── setup_graph_subscription.py         # Registers the initial Graph webhook subscription
└── check_subscription.py              # Verifies active Graph subscriptions
```

## Getting Started

### 1. Create the Azure AD App Registration

In Microsoft Entra ID, create an App Registration with `User.Read.All` application permission and grant admin consent. Note down the tenant ID, client ID, and client secret value.

### 2. Provision Azure resources

Run in Azure Cloud Shell (recommended over local bash on Windows):

```bash
bash setup-azure.sh
```

### 3. Add GitHub Actions secrets

After running the script, add the following secrets to your repository under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `AZURE_CLIENT_ID` | Managed identity client ID |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_FUNCTION_APP_NAME` | Function App name |
| `AZURE_RESOURCE_GROUP` | Resource group name |

### 4. Add Function App environment variables

```bash
az functionapp config appsettings set \
  --name <FUNCTION_APP_NAME> \
  --resource-group rg-hellofn-poc \
  --settings \
    GRAPH_TENANT_ID=<your-tenant-id> \
    GRAPH_CLIENT_ID=<your-client-id> \
    GRAPH_CLIENT_SECRET=<your-client-secret>
```

### 5. Deploy

Push to `main` — the workflow triggers automatically.

```bash
git push origin main
```

### 6. Register the Graph webhook subscription

Once the functions are deployed, set environment variables and run:

```powershell
$env:GRAPH_TENANT_ID = "your-tenant-id"
$env:GRAPH_CLIENT_ID = "your-client-id"
$env:GRAPH_CLIENT_SECRET = "your-secret-value"
$env:GRAPH_NOTIFICATION_URL = "https://<function-app-name>.azurewebsites.net/api/graph_webhook"

python setup_graph_subscription.py
```

Then run the `az` command printed by the script to save the subscription ID as a Function App setting.

### 7. Test

```bash
# Test hello function
curl https://<function-app-name>.azurewebsites.net/api/hello_function
# Hello from Azure Functions!

# Test Graph webhook — create a user in Microsoft Entra ID and check logs:
# Function App → Functions → graph_webhook → Logs
```

## Notes

- Graph webhook subscriptions expire every 3 days. The `subscription_renewal` function handles auto-renewal every 48 hours.
- To verify an active subscription exists: `python check_subscription.py`
- The setup script is best run in Azure Cloud Shell to avoid Windows bash compatibility issues.

## Environment Variables

A `.env` file is used to run the supporting scripts locally. Create a `.env` file in the project root with the following variables:

```
AZURE_FUNCTION_APP_NAME=func-hellofn-poc001
GRAPH_TENANT_ID=your-tenant-id
GRAPH_CLIENT_ID=your-client-id
GRAPH_CLIENT_SECRET=your-client-secret
GRAPH_SUBSCRIPTION_ID=your-subscription-id  # Added after running setup_graph_subscription.py
```

These same variables must also be configured as App Settings on the Azure Function App (see Step 4 above). The functions read them at runtime via `os.environ`.

> **Never commit your `.env` file to Git.** It is listed in `.gitignore` to prevent accidental exposure of credentials.

To load the `.env` file automatically when running scripts locally, install `python-dotenv` and add the following to the top of any script:

```python
from dotenv import load_dotenv
load_dotenv()
```