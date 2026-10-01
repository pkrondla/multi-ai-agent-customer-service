# Resource names follow the Microsoft Cloud Adoption Framework abbreviations:
#   <resource-type-abbr>-<workload>-<env>-<region>[-<unique-suffix>]
# See main.bicep for the exact naming logic (a short unique suffix is appended
# to resource types that require a globally unique name, e.g. Key Vault, Cosmos DB,
# and the Cognitive Services custom subdomains).

RESOURCE_GROUP="rg-csagent-prod-eus2"
LOCATION="eastus2"
WORKLOAD_NAME="csagent"
ENVIRONMENT_NAME="prod"
REGION_CODE="eus2"
DEPLOYMENT_NAME="csagent-prod-deploy"

# First, create a resource group (if you haven't already)
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# Get the object ID of the currently signed-in user (granted Key Vault + Azure OpenAI RBAC access by the template)
PRINCIPAL_ID=$(az ad signed-in-user show --query id -o tsv)

# Deploy the Bicep file
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --template-file main.bicep \
  --parameters workloadName="$WORKLOAD_NAME" environmentName="$ENVIRONMENT_NAME" location="$LOCATION" regionCode="$REGION_CODE" principalId="$PRINCIPAL_ID" principalType="User"

# Get your deployment outputs
az deployment group show --resource-group "$RESOURCE_GROUP" --name "$DEPLOYMENT_NAME" --query properties.outputs

# --- Everything below reads resource names from the deployment outputs, so it stays correct ---
# even though the Cognitive Services / Key Vault / Cosmos names include a generated unique suffix.

KEY_VAULT_NAME=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.KEY_VAULT_NAME.value -o tsv)
AI_FOUNDRY_NAME=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.AI_FOUNDRY_NAME.value -o tsv)
CONTENT_SAFETY_NAME=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.CONTENT_SAFETY_NAME.value -o tsv)
VISION_NAME=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.VISION_NAME.value -o tsv)
SPEECH_NAME=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.SPEECH_NAME.value -o tsv)
DOC_INTEL_NAME=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.DOC_INTEL_NAME.value -o tsv)
LANGUAGE_NAME=$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.LANGUAGE_NAME.value -o tsv)

# Delete the entire deployment (So no more costs)
az group delete --name "$RESOURCE_GROUP" --yes --no-wait

# Verify deletion of deployed resources
az group list --output table

# View recently deleted Cognitive Services accounts in the region (to confirm deletion)
az cognitiveservices account list-deleted --output table

# The following commands permanently delete the soft-deleted accounts.
az cognitiveservices account purge --location "$LOCATION" --resource-group "$RESOURCE_GROUP" --name "$AI_FOUNDRY_NAME";
az cognitiveservices account purge --location "$LOCATION" --resource-group "$RESOURCE_GROUP" --name "$CONTENT_SAFETY_NAME";
az cognitiveservices account purge --location "$LOCATION" --resource-group "$RESOURCE_GROUP" --name "$LANGUAGE_NAME";
az cognitiveservices account purge --location "$LOCATION" --resource-group "$RESOURCE_GROUP" --name "$VISION_NAME";
az cognitiveservices account purge --location "$LOCATION" --resource-group "$RESOURCE_GROUP" --name "$SPEECH_NAME";
az cognitiveservices account purge --location "$LOCATION" --resource-group "$RESOURCE_GROUP" --name "$DOC_INTEL_NAME";

# Find all soft-deleted Key Vaults in the region (to confirm deletion)
az keyvault list-deleted

# Find when the key vault will be permanently deleted (scheduled purge date)
az keyvault list-deleted --resource-type vault --query "[?name=='$KEY_VAULT_NAME'].properties.scheduledPurgeDate"

# Permanently deletes the soft-deleted Key Vault.
az keyvault purge --name "$KEY_VAULT_NAME" --location "$LOCATION"