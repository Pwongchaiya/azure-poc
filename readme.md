# Azure Function Pipeline POC

A proof of concept for streamlining Azure Function deployment via GitHub Actions.

## Overview

This project demonstrates an end-to-end CI/CD pipeline that automatically deploys a Python-based Azure Function on every push to `main`. Authentication is handled via OIDC (Workload Identity Federation), eliminating the need for long-lived credentials stored as secrets.

## Stack

- **Runtime:** Python 3.11
- **Platform:** Azure Functions v4 (Consumption plan)
- **CI/CD:** GitHub Actions
- **Auth:** OIDC via Azure Managed Identity + Federated Credentials
- **Infrastructure:** Provisioned via Azure CLI (`setup-azure.sh`)

## Project Structure

```
├── .github/
│   └── workflows/
│       └── deploy.yml       # GitHub Actions deployment workflow
├── hello_function/
│   ├── init.py              # HTTP trigger function
│   └── function.json        # Binding configuration
├── host.json                # Azure Functions host configuration
├── requirements.txt         # Python dependencies
└── setup-azure.sh           # Azure resource provisioning script
```

## Getting Started

### 1. Provision Azure resources

```bash
az login
bash +x setup-azure.sh
./setup-azure.sh
```

### 2. Add GitHub Actions secrets

After running the script, add the following secrets to your repository under **Settings → Secrets and variables → Actions**:

| Secret                    | Description                |
| ------------------------- | -------------------------- |
| `AZURE_CLIENT_ID`         | Managed identity client ID |
| `AZURE_TENANT_ID`         | Azure AD tenant ID         |
| `AZURE_SUBSCRIPTION_ID`   | Azure subscription ID      |
| `AZURE_FUNCTION_APP_NAME` | Function App name          |
| `AZURE_RESOURCE_GROUP`    | Resource group name        |

### 3. Deploy

Push to `main` — the workflow triggers automatically.

```bash
git push origin main
```

### 4. Test

```bash
curl https://<function-app-name>.azurewebsites.net/api/hello_function
# Hello from Azure Functions!
```
