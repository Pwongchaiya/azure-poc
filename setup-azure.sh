#!/usr/bin/env bash
# setup-azure.sh
#
# Provisions all Azure resources needed for the hello-function POC and
# configures OIDC-based Workload Identity Federation so GitHub Actions can
# authenticate without storing long-lived secrets.
#
# Prerequisites:
#   - Azure CLI installed and logged in (`az login`)
#   - Sufficient permissions: Contributor + User Access Administrator on the
#     subscription (needed to create the role assignment)
#
# Usage:
#   chmod +x setup-azure.sh
#   ./setup-azure.sh

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
# Edit these four variables before running.
GITHUB_ORG=""   # e.g. "joshsmith"
GITHUB_REPO=""               # e.g. "hello-azure-fn"
LOCATION=""
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Derived names — safe for a POC, all lowercase, globally unique via suffix.
SUFFIX="poc001"
RESOURCE_GROUP="rg-hellofn-poc"
STORAGE_ACCOUNT="sahellofn${SUFFIX}"         # Must be 3-24 chars, lowercase alphanumeric
FUNCTION_APP="func-hellofn-${SUFFIX}"
APP_SERVICE_PLAN="plan-hellofn-poc"          # Consumption plan
MANAGED_IDENTITY="id-hellofn-poc"

echo "──────────────────────────────────────────"
echo " Azure Hello Function — POC Setup"
echo " Subscription : $SUBSCRIPTION_ID"
echo " Resource Group: $RESOURCE_GROUP"
echo " Storage Account: $STORAGE_ACCOUNT"
echo " Function App: $FUNCTION_APP"
echo "──────────────────────────────────────────"
echo ""

# ─── 1. Resource Group ────────────────────────────────────────────────────────
echo "[1/6] Creating resource group..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none
echo "      ✓ Resource group '$RESOURCE_GROUP' created."

# ─── 2. Storage Account ───────────────────────────────────────────────────────
# Azure Functions requires a Storage Account for internal bookkeeping
# (function state, logs, deployment packages). LRS is sufficient for a POC.
echo "[2/6] Creating storage account..."
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --output none
echo "      ✓ Storage account '$STORAGE_ACCOUNT' created."

# ─── 3. Function App (Consumption plan) ───────────────────────────────────────
# --consumption-plan-location implicitly creates a Consumption (Y1) plan —
# no need to provision an App Service Plan separately for serverless.
echo "[3/6] Creating Function App..."
az functionapp create \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --consumption-plan-location "$LOCATION" \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --storage-account "$STORAGE_ACCOUNT" \
  --os-type Linux \
  --output none
echo "      ✓ Function App '$FUNCTION_APP' created."

# ─── 4. User-Assigned Managed Identity ────────────────────────────────────────
# We create a dedicated managed identity for GitHub Actions to assume via OIDC.
# This is cleaner than using a Service Principal with a client secret.
echo "[4/6] Creating managed identity..."
az identity create \
  --name "$MANAGED_IDENTITY" \
  --resource-group "$RESOURCE_GROUP" \
  --output none

IDENTITY_CLIENT_ID=$(az identity show \
  --name "$MANAGED_IDENTITY" \
  --resource-group "$RESOURCE_GROUP" \
  --query clientId -o tsv)

IDENTITY_OBJECT_ID=$(az identity show \
  --name "$MANAGED_IDENTITY" \
  --resource-group "$RESOURCE_GROUP" \
  --query principalId -o tsv)

TENANT_ID=$(az account show --query tenantId -o tsv)

echo "      ✓ Managed identity created (clientId: $IDENTITY_CLIENT_ID)."

# ─── 5. Role Assignment ───────────────────────────────────────────────────────
# Grant the identity Contributor on the resource group so it can deploy the
# Function App. Scope to the resource group (not the subscription) — least
# privilege for a POC.
echo "[5/6] Assigning Contributor role to managed identity..."
az role assignment create \
  --assignee-object-id "$IDENTITY_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role Contributor \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
  --output none
echo "      ✓ Role assignment created."

# ─── 6. Federated Credential (OIDC) ───────────────────────────────────────────
# This tells Azure AD to trust tokens issued by GitHub Actions for pushes to
# the main branch of your repo — no client secret needed.
echo "[6/6] Creating federated credential for OIDC..."
az identity federated-credential create \
  --name "github-actions-main" \
  --identity-name "$MANAGED_IDENTITY" \
  --resource-group "$RESOURCE_GROUP" \
  --issuer "https://token.actions.githubusercontent.com" \
  --subject "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main" \
  --audiences "api://AzureADTokenExchange" \
  --output none
echo "      ✓ Federated credential created."

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo " Setup complete. Add these as GitHub"
echo " Actions secrets in your repository:"
echo "══════════════════════════════════════════"
echo ""
echo "  AZURE_CLIENT_ID     = $IDENTITY_CLIENT_ID"
echo "  AZURE_TENANT_ID     = $TENANT_ID"
echo "  AZURE_SUBSCRIPTION_ID = $SUBSCRIPTION_ID"
echo "  AZURE_FUNCTION_APP_NAME = $FUNCTION_APP"
echo "  AZURE_RESOURCE_GROUP  = $RESOURCE_GROUP"
echo ""
echo " Function App URL (available after first deploy):"
echo "  https://${FUNCTION_APP}.azurewebsites.net/api/hello_function"
echo ""