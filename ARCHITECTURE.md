# Architecture

## Overview

This project is a multi-agent customer service system built on Azure AI Foundry. A **Manager Agent**
classifies each user message and delegates to one of two specialist agents (**Refund Agent**,
**Product Agent**), while a shared set of Azure AI services handles safety, language preprocessing,
multimodal understanding, and memory.

## System diagram

```mermaid
flowchart TB
    User((User)) --> CLI[Interactive CLI loop\nmain.py]

    CLI --> CS1[Content Safety\ninput filter]
    CS1 --> Vision[Azure AI Vision\nSpeech / Document Intelligence]
    CS1 --> NLP[Azure AI Language\nlanguage detect, PII redact, NER,\nkey phrases, sentiment]

    NLP --> Cosmos[(Cosmos DB\nlong-term user profile)]
    NLP --> Manager[Manager Agent]

    Manager -->|refund / return intent| Refund[Refund Agent]
    Manager -->|product / spec intent| Product[Product Agent]

    Refund --> Redis[(Redis / in-memory\nsession cache)]
    Product --> Redis
    Product -->|tools/list, tools/call| MCP[(External MCP\ntool server)]

    Refund --> AOAI[Azure OpenAI\ngpt-4.1-mini]
    Product --> AOAI
    Manager --> AOAI

    Manager --> CS2[Content Safety\noutput filter]
    CS2 --> CLI

    CLI -->|on exit| Prefs[User Preferences Agent\nSLM: Phi-4-mini-instruct]
    Prefs --> Cosmos

    KeyVault[(Azure Key Vault\nsecrets & endpoints)] -.->|DefaultAzureCredential| AOAI
    KeyVault -.-> Vision
    KeyVault -.-> NLP
    KeyVault -.-> Cosmos
    KeyVault -.-> CS1
```

## Request lifecycle (single turn)

```mermaid
sequenceDiagram
    actor User
    participant CLI as main.py
    participant Safety as ContentSafety
    participant NLPsvc as AzureNLPService
    participant Cosmos as CosmosMemory
    participant Mgr as ManagerAgent
    participant Spec as RefundAgent / ProductAgent
    participant AOAI as Azure OpenAI

    User->>CLI: types message
    CLI->>Safety: is_text_safe(message)
    Safety-->>CLI: safe / blocked
    CLI->>NLPsvc: preprocess_user_input(message)
    NLPsvc-->>CLI: {redacted, tagged, language, sentiment, key_phrases}
    CLI->>Cosmos: get_user_or_default_profile(user_id)
    Cosmos-->>CLI: user preferences
    CLI->>Mgr: process_message(tagged_message, preferences, ...)
    Mgr->>AOAI: classify intent (function-calling)
    AOAI-->>Mgr: tool_call: delegate_to_refund | delegate_to_product
    Mgr->>Spec: process_message(...)
    Spec->>AOAI: chat completion (+ MCP tools if ProductAgent)
    AOAI-->>Spec: assistant reply
    Spec-->>Mgr: reply
    Mgr-->>CLI: reply
    CLI->>Safety: is_text_safe(reply)
    Safety-->>CLI: safe / blocked
    CLI-->>User: prints final reply
```

## Component responsibilities

| Component | File | Responsibility |
|---|---|---|
| `ManagerAgent` | [classes/manager_agent.py](classes/manager_agent.py) | Classifies intent via LLM function-calling; never answers directly, only routes |
| `RefundAgent` | [classes/refund_agent.py](classes/refund_agent.py) | Handles refund/return requests; builds persona + boundaries + behavior system prompt |
| `ProductAgent` | [classes/product_agent.py](classes/product_agent.py) | Handles product questions; discovers and calls tools on an external MCP server |
| `UserPreferencesAgent` | [classes/user_preferences_agent.py](classes/user_preferences_agent.py) | SLM (Phi-4-mini-instruct) that infers language/tone/email from conversation history |
| `ContentSafety` | [classes/content_safety.py](classes/content_safety.py) | Filters input/output against Hate, Sexual, Violence, SelfHarm severity thresholds |
| `AzureAIService` | [classes/azure_ai_services.py](classes/azure_ai_services.py) | Vision (image captions/OCR/tags), Speech-to-text, Document Intelligence extraction |
| `AzureNLPService` | [classes/azure_nlp_services.py](classes/azure_nlp_services.py) | Language detection, PII redaction, NER, key phrases, sentiment analysis |
| `CosmosMemory` | [classes/cosmos_memory.py](classes/cosmos_memory.py) | Long-term user profile storage (90-day TTL) |
| `RedisMemory` | [classes/redis_memory.py](classes/redis_memory.py) | Short-term conversation history (TTL-based), with in-memory fallback |
| `SecretManager` | [classes/secret_manager.py](classes/secret_manager.py) | Cached secret retrieval from Key Vault |

## Infrastructure (Bicep)

[main.bicep](main.bicep) provisions, following Cloud Adoption Framework naming (`<type-abbr>-<workload>-<env>-<region>[-<suffix>]`):

- **AI Foundry** (`Microsoft.CognitiveServices/accounts`, kind `AIServices`) with two model deployments:
  - `llm-gpt-41-mini-<env>` — `gpt-4.1-mini`, used by Manager/Refund/Product agents
  - `slm-phi-4-mini-<env>` — `Phi-4-mini-instruct`, used by the User Preferences agent
- **Content Safety**, **Vision**, **Speech**, **Document Intelligence**, **Language** Cognitive Services accounts
- **Cosmos DB** account/database/container for long-term memory (free tier, 90-day TTL, partitioned by `/userId`)
- **Key Vault** holding every endpoint/key the app needs, with RBAC-only access
- **RBAC role assignments**: `Key Vault Secrets User` and `Cognitive Services OpenAI User` granted to the deploying principal, since the app authenticates with `DefaultAzureCredential` (Azure CLI credential when run locally)

## Known limitation

`ProductAgent` calls an external MCP tool server (`MCP_SERVER_URL`) for product lookups. On networks with
TLS-inspecting corporate proxies, this call can fail with `CERTIFICATE_VERIFY_FAILED`. The agent degrades
gracefully in that case (responds without tool results) rather than crashing.
