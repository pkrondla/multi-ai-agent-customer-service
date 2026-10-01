//https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/00-basic/main.bicep
//
// Resource naming follows the Microsoft Cloud Adoption Framework abbreviations:
// <resource-type-abbr>-<workload>-<env>-<region>[-<unique-suffix>]
// https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations

@description('Short, lowercase workload name used to build standardized resource names')
param workloadName string = 'csagent'

@description('Deployment environment designator, e.g. dev, test, prod')
param environmentName string = 'prod'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Short region code used in resource names, e.g. eus2 for eastus2')
param regionCode string = 'eus2'

@description('Object ID of the principal (user, group, or service principal) granted Key Vault + Azure OpenAI access, since the app authenticates with DefaultAzureCredential')
param principalId string

@description('Type of the principal supplied in principalId')
@allowed([
  'User'
  'ServicePrincipal'
  'Group'
])
param principalType string = 'User'

// Short, globally-unique token appended to resource types that require a globally unique name
var uniqueSuffix = substring(uniqueString(resourceGroup().id), 0, 4)

var aiFoundryName = 'ais-${workloadName}-${environmentName}-${regionCode}-${uniqueSuffix}'
var aiProjectName = '${aiFoundryName}-proj'
var contentSafetyName = 'cog-safety-${workloadName}-${environmentName}-${regionCode}-${uniqueSuffix}'
var visionName = 'cog-vision-${workloadName}-${environmentName}-${regionCode}-${uniqueSuffix}'
var speechName = 'cog-speech-${workloadName}-${environmentName}-${regionCode}-${uniqueSuffix}'
var docIntelName = 'cog-docintel-${workloadName}-${environmentName}-${regionCode}-${uniqueSuffix}'
var languageName = 'cog-lang-${workloadName}-${environmentName}-${regionCode}-${uniqueSuffix}'
var cosmosDbAccountName = 'cosmos-${workloadName}-${environmentName}-${regionCode}-${uniqueSuffix}'
var databaseName = 'conversation-history'
var containerName = 'conversations'
// Key Vault names are capped at 24 characters, so the region code is dropped to stay within the limit
var keyVaultName = 'kv-${workloadName}-${environmentName}-${uniqueSuffix}'
var llmModelDeploymentName = 'llm-gpt-41-mini-${environmentName}'
var slmModelDeploymentName = 'slm-phi-4-mini-${environmentName}'

/*
  An AI Foundry resources is a variant of a CognitiveServices/account resource type
*/ 
resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiFoundryName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    // required to work in AI Foundry
    allowProjectManagement: true

    // Defines developer API endpoint subdomain
    customSubDomainName: aiFoundryName

    disableLocalAuth: false
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  name: aiProjectName
  parent: aiFoundry
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

/*
  Deploying models to use in playground, agents and other tools.
*/

// https://ai.azure.com/catalog/models/gpt-4.1-mini
resource llmModelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01'= {
  parent: aiFoundry
  name: llmModelDeploymentName
  sku : {
    capacity: 1
    name: 'GlobalStandard'
  }
  properties: {
    model:{
      name: 'gpt-4.1-mini'
      format: 'OpenAI'
      version: '2025-04-14'
    }
  }
}


// https://ai.azure.com/catalog/models/Phi-4-mini-instruct
// gpt-4o-mini (2024-07-18) is in the Deprecating lifecycle state and can no longer be used for
// new deployments, so the SLM role uses the Generally Available Phi-4-mini-instruct model instead.
resource slmModelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01'= {
  parent: aiFoundry
  name: slmModelDeploymentName
  dependsOn: [
    llmModelDeployment  // Explicitly wait for LLM to finish first
  ]
  sku : {
    capacity: 1
    name: 'GlobalStandard'
  }
  properties: {
    model:{
      name: 'Phi-4-mini-instruct'
      format: 'Microsoft'
      version: '1'
    }
  }
}

/*
  Content Safety service to moderate text, images, and other content
*/
resource contentSafety 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: contentSafetyName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  kind: 'ContentSafety'
  properties: {
    customSubDomainName: contentSafetyName
    disableLocalAuth: false
  }
}

/*
  Azure AI Vision service for image analysis (including OCR, captioning, and multimodal analysis)
*/
resource vision 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: visionName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'F0' // Free tier, change to 'S0' for production use (removing free tier limits and allowing SLA)
  }
  kind: 'ComputerVision'
  properties: {
    customSubDomainName: visionName
    disableLocalAuth: false
  }
}

/*
  Azure AI Speech service for speech-to-text, text-to-speech, and speech translation
*/
resource speech 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: speechName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'F0'
  }
  kind: 'SpeechServices'
  properties: {
    customSubDomainName: speechName
    disableLocalAuth: false
  }
}

/*
  Azure AI Document Intelligence service for document processing (forms, invoices, receipts, etc.)
*/
resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: docIntelName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'F0'
  }
  kind: 'FormRecognizer'
  properties: {
    customSubDomainName: docIntelName
    disableLocalAuth: false
  }
}

/*
  Azure AI Language service for Natural Language Processing (NLP)
  Provides: Language detection, PII redaction, NER, key phrase extraction, sentiment analysis
*/
resource language 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: languageName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'F0' // Free tier, change to 'S0' for production use
  }
  kind: 'TextAnalytics'  // Language service uses 'TextAnalytics' kind
  properties: {
    customSubDomainName: languageName
    disableLocalAuth: false
  }
}

/*
  Azure Cosmos DB for long-term conversation history storage
  Using Free Tier when available (25GB storage + 1000 RU/s free)
*/
resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: toLower(cosmosDbAccountName)  // Cosmos DB names must be lowercase
  location: location
  properties: {
    enableFreeTier: true               // FREE TIER ENABLED - 25GB + 1000 RU/s free
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'  // Perfect for conversation scenarios
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    enableAutomaticFailover: false      // Disabled for free tier optimization
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    capabilities: []                    // No additional capabilities for free tier
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: {
    environment: 'development'
    purpose: 'conversation-history-for-ai-agent'
  }
}

// Database for storing conversation history
resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosDbAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
    options: {
      throughput: 1000  // This will be FREE under the free tier (first 1000 RU/s)
    }
  }
}

// Container for conversation threads with optimized partition key for chat history
resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: cosmosDatabase
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          '/userId'     // Partition by user ID for efficient querying of user history
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'  // Index all fields for flexible querying
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'  // Exclude etag from indexing
          }
        ]
        // Add composite indexes for time-based queries
        compositeIndexes: [
          [
            {
              path: '/userId'
              order: 'ascending'
            }
            {
              path: '/timestamp'
              order: 'descending'
            }
          ]
        ]
      }
      // Optional: Add TTL for automatic cleanup of old conversations (90 days)
      defaultTtl: 7776000  // 90 days in seconds (comment out if you want to keep forever)
    }
  }
}

/*
  Azure Key Vault for secure secret storage
  Stores: API keys, endpoints, connection strings, etc.
*/
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true  // Use RBAC for access control
    softDeleteRetentionInDays: 7
    enablePurgeProtection: true  // Set to true in production
  }
}

// =============================================================================
// RBAC - grant the app's identity (managed identity in Azure, or the signed-in
// developer when running locally) access to Key Vault secrets and Azure OpenAI
// =============================================================================

// Built-in role: Key Vault Secrets User
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
// Built-in role: Cognitive Services OpenAI User
var cognitiveServicesOpenAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource keyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, principalId, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: principalId
    principalType: principalType
  }
}

resource openAiUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiFoundry.id, principalId, cognitiveServicesOpenAiUserRoleId)
  scope: aiFoundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: principalId
    principalType: principalType
  }
}

// =============================================================================
// SECRET STORAGE - Store credentials in Key Vault
// =============================================================================

/*
  Store Azure OpenAI endpoint as a secret
*/
resource openaiEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'AZURE-OPENAI-ENDPOINT'
  parent: keyVault
  properties: {
    value: 'https://${aiFoundry.properties.customSubDomainName}.services.ai.azure.com/openai/v1'
    contentType: 'text/plain'
  }
}

/*
  Store LLM Model Deployment Name as a secret
*/
resource llmModelSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'LLM-MODEL-DEPLOYMENT-NAME'
  parent: keyVault
  properties: {
    value: llmModelDeployment.name
    contentType: 'text/plain'
  }
}

/*
  Store SLM Model Deployment Name as a secret
*/
resource slmModelSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'SLM-MODEL-DEPLOYMENT-NAME'
  parent: keyVault
  properties: {
    value: slmModelDeployment.name
    contentType: 'text/plain'
  }
}

/*
  Store Content Safety Endpoint as a secret
*/
resource contentSafetyEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'CONTENT-SAFETY-ENDPOINT'
  parent: keyVault
  properties: {
    value: 'https://${contentSafety.properties.customSubDomainName}.cognitiveservices.azure.com/'
    contentType: 'text/plain'
  }
}

/*
  Store Vision Endpoint as a secret
*/
resource visionEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'VISION-ENDPOINT'
  parent: keyVault
  properties: {
    value: vision.properties.endpoint
    contentType: 'text/plain'
  }
}

/*
  Store Vision Key 1 as a secret
*/
resource visionKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'VISION-KEY'
  parent: keyVault
  properties: {
    value: vision.listKeys().key1
    contentType: 'text/plain'
  }
}

/*
  Store Speech Key 1 as a secret
*/
resource speechKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'SPEECH-KEY'
  parent: keyVault
  properties: {
    value: speech.listKeys().key1
    contentType: 'text/plain'
  }
}

/*
  Store Document Intelligence Endpoint as a secret
*/
resource docIntelEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'DOC-INTEL-ENDPOINT'
  parent: keyVault
  properties: {
    value: documentIntelligence.properties.endpoint
    contentType: 'text/plain'
  }
}

/*
  Store Document Intelligence Key 1 as a secret
*/
resource docIntelKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'DOC-INTEL-KEY'
  parent: keyVault
  properties: {
    value: documentIntelligence.listKeys().key1
    contentType: 'text/plain'
  }
}


/*
  Store Language Service Endpoint as a secret
*/
resource languageEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'LANGUAGE-ENDPOINT'
  parent: keyVault
  properties: {
    value: language.properties.endpoint
    contentType: 'text/plain'
  }
}

/*
  Store Language Service API Key as a secret
  IMPORTANT: Keys are sensitive and should never be in output logs
*/
resource languageKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'LANGUAGE-KEY'
  parent: keyVault
  properties: {
    value: language.listKeys().key1
    contentType: 'text/plain'
  }
}

/*
  Store Cosmos DB Endpoint as a secret
*/
resource cosmosDbEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'COSMOSDB-ENDPOINT'
  parent: keyVault
  properties: {
    value: cosmosDbAccount.properties.documentEndpoint
    contentType: 'text/plain'
  }
}

/*
  Store Cosmos DB Database Name as a secret
*/
resource cosmosDbNameSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'COSMOSDB-DATABASE-NAME'
  parent: keyVault
  properties: {
    value: databaseName
    contentType: 'text/plain'
  }
}

/*
  Store Cosmos DB Container Name as a secret
*/
resource cosmosDbContainerSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'COSMOSDB-CONTAINER-NAME'
  parent: keyVault
  properties: {
    value: containerName
    contentType: 'text/plain'
  }
}

/*
  Store Cosmos DB Primary Key as a secret
  IMPORTANT: Keys are sensitive and should never be in output logs
*/
resource cosmosDbKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'COSMOSDB-PRIMARY-KEY'
  parent: keyVault
  properties: {
    value: cosmosDbAccount.listKeys().primaryMasterKey
    contentType: 'text/plain'
  }
}

output KEY_VAULT_ENDPOINT string = keyVault.properties.vaultUri
output KEY_VAULT_NAME string = keyVault.name
output REGION string = location
output RESOURCE_GROUP_NAME string = resourceGroup().name
output AI_FOUNDRY_NAME string = aiFoundry.name
output CONTENT_SAFETY_NAME string = contentSafety.name
output VISION_NAME string = vision.name
output SPEECH_NAME string = speech.name
output DOC_INTEL_NAME string = documentIntelligence.name
output LANGUAGE_NAME string = language.name
output COSMOS_ACCOUNT_NAME string = cosmosDbAccount.name
