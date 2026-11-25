#!/usr/bin/env bash
# One-time Azure setup for AV Desk. Run once by a person signed in with
# `az login`; after it, every change is made by the pipeline (infra/README.md).
#
# Idempotent where Azure allows it: `create` on an existing resource with the
# same settings changes nothing, so the script can be re-run after a failure.
#
# Every resource is pay-per-use (ADR-8): Container Apps Consumption scaling to
# zero, Azure SQL serverless (billed per second while active, auto-pause after 60 min), a
# Storage static website, and a managed identity (free). Images live on GHCR.
#
# Passwords are generated here and written only to infra/.secrets.local
# (gitignored), from where they are copied into GitHub Actions secrets.
set -euo pipefail
# Git Bash on Windows rewrites arguments starting with / (Azure resource IDs
# such as /subscriptions/...) into Windows paths; this turns that off.
export MSYS_NO_PATHCONV=1

AZ=${AZ:-az}
PREFIX=lhoffmann
LOCATION=belgiumcentral      # allowed for this subscription and accepting new SQL servers (infra/README.md)
REPO=Hoffalo/sdd-assignment-1
RG=rg-$PREFIX
SQL_SERVER=$PREFIX-sql3        # infra/README.md: failed attempts elsewhere still hold -sql and -sql2
SQL_ADMIN=avdeskadmin
ENVIRONMENT=$PREFIX-env
STORAGE=${PREFIX}ui
SERVICES=(requests feedback)
SECRETS_FILE="$(dirname "$0")/.secrets.local"

# Letters and digits only: they survive a mssql:// URL unescaped, and the mix
# of upper, lower and digits meets Azure SQL's complexity rule.
new_password() { echo "Av$(openssl rand -hex 16)9Q"; }

step() { echo; echo "== $*"; }

if [ -f "$SECRETS_FILE" ]; then
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"   # a re-run keeps the passwords already handed out
else
  SQL_ADMIN_PASSWORD=$(new_password)
  REQUESTS_DB_PASSWORD=$(new_password)
  FEEDBACK_DB_PASSWORD=$(new_password)
  ADMIN_TOKEN_SECRET=$(openssl rand -hex 32)
  # Saved before anything is created, so a run that fails halfway never
  # leaves a server whose password nobody knows.
  cat > "$SECRETS_FILE" <<EOF
SQL_ADMIN_PASSWORD=$SQL_ADMIN_PASSWORD
REQUESTS_DB_PASSWORD=$REQUESTS_DB_PASSWORD
FEEDBACK_DB_PASSWORD=$FEEDBACK_DB_PASSWORD
ADMIN_TOKEN_SECRET=$ADMIN_TOKEN_SECRET
EOF
fi

step "Resource providers"
for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  $AZ provider register --namespace "$provider" --wait --output none
done

step "Resource group $RG in $LOCATION"
# The group may already exist from the course's setup guide, possibly in
# another location; a group's location only holds its metadata, so it is
# reused as it is and every resource below still goes to $LOCATION.
if [ "$($AZ group exists -n "$RG")" != "true" ]; then
  $AZ group create -n "$RG" -l "$LOCATION" --output none
fi
RG_ID=$($AZ group show -n "$RG" --query id -o tsv)

step "Managed identity $PREFIX-github, trusted only for pushes to main of $REPO"
if ! $AZ identity show -g "$RG" -n "$PREFIX-github" --output none 2>/dev/null; then
  $AZ identity create -g "$RG" -n "$PREFIX-github" -l "$LOCATION" --output none
fi
CLIENT_ID=$($AZ identity show -g "$RG" -n "$PREFIX-github" --query clientId -o tsv)
PRINCIPAL_ID=$($AZ identity show -g "$RG" -n "$PREFIX-github" --query principalId -o tsv)
$AZ identity federated-credential create -g "$RG" --identity-name "$PREFIX-github" -n github-main \
  --issuer https://token.actions.githubusercontent.com \
  --subject "repo:$REPO:ref:refs/heads/main" \
  --audiences api://AzureADTokenExchange --output none
# Contributor on this resource group only: the pipeline can update the apps
# and upload the UI, and can touch nothing else in the subscription.
if [ -z "$($AZ role assignment list --assignee "$PRINCIPAL_ID" --role Contributor --scope "$RG_ID" --query "[].id" -o tsv)" ]; then
  $AZ role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
    --role Contributor --scope "$RG_ID" --output none
fi

step "SQL server $SQL_SERVER and one serverless database per service (auto-pause after 60 min)"
if $AZ sql server show -g "$RG" -n "$SQL_SERVER" --output none 2>/dev/null; then
  # Re-run: make the admin password match the one in the secrets file.
  $AZ sql server update -g "$RG" -n "$SQL_SERVER" --admin-password "$SQL_ADMIN_PASSWORD" --output none
else
  $AZ sql server create -g "$RG" -n "$SQL_SERVER" -l "$LOCATION" \
    --admin-user "$SQL_ADMIN" --admin-password "$SQL_ADMIN_PASSWORD" --output none
fi
# 0.0.0.0-0.0.0.0 is Azure's notation for "Azure services", which is how the
# Container Apps reach the server; no other address is allowed.
$AZ sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none
for service in "${SERVICES[@]}"; do
  $AZ sql db create -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-$service-db" \
    --edition GeneralPurpose --family Gen5 --compute-model Serverless \
    --min-capacity 0.5 --capacity 1 --backup-storage-redundancy Local \
    --auto-pause-delay 60 --output none
done

step "Container Apps environment $ENVIRONMENT (creates its Log Analytics workspace)"
$AZ containerapp env create -g "$RG" -n "$ENVIRONMENT" -l "$LOCATION" --output none
for service in "${SERVICES[@]}"; do
  # A placeholder image until the first pipeline run replaces it. Port 8000,
  # 0 to 1 replica: one replica at most, so startup migrations never race.
  if ! $AZ containerapp show -g "$RG" -n "$PREFIX-$service" --output none 2>/dev/null; then
    $AZ containerapp create -g "$RG" -n "$PREFIX-$service" --environment "$ENVIRONMENT" \
      --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8000 \
      --min-replicas 0 --max-replicas 1 --output none
  fi
done

step "Storage account $STORAGE with a static website"
$AZ storage account create -g "$RG" -n "$STORAGE" -l "$LOCATION" --sku Standard_LRS --kind StorageV2 \
  --min-tls-version TLS1_2 --output none
$AZ storage blob service-properties update --account-name "$STORAGE" --auth-mode key \
  --static-website --index-document index.html --404-document index.html --output none
WEB_URL=$($AZ storage account show -g "$RG" -n "$STORAGE" --query primaryEndpoints.web -o tsv)

cat > "$SECRETS_FILE" <<EOF
# Generated by infra/setup.sh. Never commit (gitignored). Copy the values
# marked GitHub into the repository's Actions secrets, then keep this file
# somewhere safe or delete it.
SQL_ADMIN_PASSWORD=$SQL_ADMIN_PASSWORD
REQUESTS_DB_PASSWORD=$REQUESTS_DB_PASSWORD
FEEDBACK_DB_PASSWORD=$FEEDBACK_DB_PASSWORD
ADMIN_TOKEN_SECRET=$ADMIN_TOKEN_SECRET
# --- GitHub Actions secrets ---
# AZURE_CLIENT_ID=$CLIENT_ID
# AZURE_TENANT_ID=$($AZ account show --query tenantId -o tsv)
# AZURE_SUBSCRIPTION_ID=$($AZ account show --query id -o tsv)
# REQUESTS_DATABASE_URL=mssql://avdesk_requests:$REQUESTS_DB_PASSWORD@$SQL_SERVER.database.windows.net:1433/$PREFIX-requests-db
# FEEDBACK_DATABASE_URL=mssql://avdesk_feedback:$FEEDBACK_DB_PASSWORD@$SQL_SERVER.database.windows.net:1433/$PREFIX-feedback-db
# ADMIN_TOKEN_SECRET=$ADMIN_TOKEN_SECRET
# ADMIN_PASSWORD=<choose one yourself>
EOF

step "Done"
echo "Static website: $WEB_URL"
echo "Next: python infra/create_db_users.py, then copy the GitHub secrets from $SECRETS_FILE"
