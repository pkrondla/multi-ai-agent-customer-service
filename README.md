# Multi-Agent Customer Service System

A production-style, multi-agent AI customer service system built on **Azure AI Foundry**, demonstrating
agent orchestration, content safety, multimodal understanding, NLP preprocessing, short/long-term memory,
and external tool integration via MCP (Model Context Protocol).

> Portfolio / interview project — see [ARCHITECTURE.md](ARCHITECTURE.md) for diagrams and a full component breakdown.

## Features

- **Multi-agent orchestration** — a Manager Agent classifies intent via LLM function-calling and delegates
  to a Refund Agent or Product Agent; each specialist owns its own persona, boundaries, and behavior rules.
- **Content Safety** — every user message and assistant reply is scanned (Hate, Sexual, Violence, Self-Harm)
  before being processed or returned.
- **Multimodal AI** — Azure AI Vision (image captioning/OCR/tags), Speech-to-text, and Document Intelligence
  (invoice/receipt/ID extraction) are available as tools the pipeline can route to.
- **NLP preprocessing** — Azure AI Language performs language detection, PII redaction, named entity
  recognition, key phrase extraction, and sentiment analysis (with automatic escalation flagging) on every
  message before it reaches an agent.
- **Long-term + short-term memory** — Cosmos DB persists user preferences across sessions (90-day TTL);
  Redis (with an in-memory fallback) holds the active conversation history.
- **Secure secrets management** — every endpoint and key lives in Azure Key Vault; the app authenticates
  with `DefaultAzureCredential` (no secrets hardcoded or committed).
- **External tool calling (MCP)** — the Product Agent discovers and calls tools on an external MCP server
  at runtime and degrades gracefully if that server is unreachable.
- **Infrastructure as Code** — the entire Azure footprint is defined in [main.bicep](main.bicep) using
  Cloud Adoption Framework resource naming conventions.

## Tech stack

| Layer | Technology |
|---|---|
| Language / runtime | Python 3.14 |
| LLM | Azure OpenAI `gpt-4.1-mini` (Azure AI Foundry) |
| SLM | `Phi-4-mini-instruct` (Azure AI Foundry) |
| Safety | Azure AI Content Safety |
| NLP | Azure AI Language |
| Multimodal | Azure AI Vision, Azure AI Speech, Azure AI Document Intelligence |
| Long-term memory | Azure Cosmos DB (SQL API) |
| Short-term memory | Redis (optional; falls back to in-memory cache) |
| Secrets | Azure Key Vault + Managed Identity / `DefaultAzureCredential` |
| External tools | MCP (Model Context Protocol) over JSON-RPC 2.0 / SSE |
| Infrastructure | Bicep |

## Project structure

```
├── main.py                 # Entry point: wiring, interactive CLI loop
├── main.bicep               # Infrastructure as Code (all Azure resources)
├── deploy.sh                 # Reference az CLI deployment script
├── config.yaml                # Tunable thresholds/limits (safety, LLM, memory, MCP)
├── requirements.txt
├── classes/
│   ├── manager_agent.py        # Routes requests to the right specialist
│   ├── refund_agent.py          # Refund/return specialist
│   ├── product_agent.py          # Product specialist + MCP tool calling
│   ├── user_preferences_agent.py  # SLM that learns user preferences over time
│   ├── content_safety.py          # Input/output moderation
│   ├── azure_ai_services.py        # Vision / Speech / Document Intelligence wrapper
│   ├── azure_nlp_services.py        # Language detection / PII / NER / sentiment
│   ├── cosmos_memory.py              # Long-term memory (Cosmos DB)
│   ├── redis_memory.py                # Short-term memory (Redis / in-memory)
│   └── secret_manager.py               # Cached Key Vault secret retrieval
├── functions/
│   └── helper_functions.py               # Token counting (tiktoken)
└── inputs/                                 # Sample multimodal files used by the demo
```

## Prerequisites

- An Azure subscription with access to Azure AI Foundry (gpt-4.1-mini, Phi-4-mini-instruct availability
  varies by region — this project was deployed to `eastus2`)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), logged in (`az login`)
- Python 3.11+ (tested on 3.14)
- Bicep CLI (bundled with recent Azure CLI versions)

## Deploy the infrastructure

```powershell
# 1. Create a resource group
az group create --name "rg-csagent-prod-eus2" --location "eastus2"

# 2. Get your Azure AD object ID (used for RBAC grants on Key Vault + Azure OpenAI)
$principalId = az ad signed-in-user show --query id -o tsv

# 3. Preview the deployment before creating anything (recommended)
az deployment group what-if `
  --resource-group "rg-csagent-prod-eus2" `
  --template-file main.bicep `
  --parameters workloadName="csagent" environmentName="prod" location="eastus2" regionCode="eus2" principalId="$principalId" principalType="User"

# 4. Deploy
az deployment group create `
  --resource-group "rg-csagent-prod-eus2" `
  --name "csagent-prod-deploy" `
  --template-file main.bicep `
  --parameters workloadName="csagent" environmentName="prod" location="eastus2" regionCode="eus2" principalId="$principalId" principalType="User"

# 5. Read the outputs you'll need for local configuration
az deployment group show --resource-group "rg-csagent-prod-eus2" --name "csagent-prod-deploy" --query properties.outputs
```

See [deploy.sh](deploy.sh) for the full reference script, including cleanup/purge commands for the free-tier
resources once you're done.

> **Note:** Bicep/ARM deployments are idempotent and declarative — if a deployment fails partway through
> (e.g. a transient `RequestConflict`), it's safe to simply re-run the same `az deployment group create`
> command; it will skip anything already provisioned correctly and finish the rest.

## Local setup

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set the required environment variables (see .env.example)
#    Values come from the deployment outputs above.
$env:KEY_VAULT_URL = "https://<your-key-vault-name>.vault.azure.net/"
$env:USER_NAME      = "Your Name"
$env:USER_ROLE       = "Customer"
$env:REGION           = "eastus2"
$env:MCP_SERVER_URL    = "https://mcp.exa.ai/mcp"
$env:MCP_API_KEY        = ""

# 4. Run
python main.py
```

Or use the **Python Debugger: Multi-Agent Customer Service** launch configuration in
[.vscode/launch.json](.vscode/launch.json) — update the placeholder `env` values with your own deployment
outputs first.

## Configuration

[config.yaml](config.yaml) controls runtime behavior without code changes:

| Section | Key | Purpose |
|---|---|---|
| `content_safety` | `severity_threshold` | Max allowed Content Safety severity (0-6) before blocking |
| `llm` | `max_tokens`, `temperature`, `top_p`, `max_messages_in_history` | Sampling + context window for the LLM agents |
| `slm` | `max_tokens`, `temperature`, `top_p` | Sampling for the User Preferences SLM agent |
| `redis` | `session_ttl_seconds`, `max_messages_in_history` | Short-term conversation cache limits |
| `nlp.sentiment_analysis` | `sentiment_escalation_threshold` | Negative-sentiment confidence that triggers an escalation flag |
| `cosmos` | `profile_ttl_seconds` | Long-term user profile retention (default 90 days) |
| `mcp` | `max_tool_response_length`, `tool_call_timeout_seconds`, `max_retries`, `backoff_seconds` | External tool-calling limits |

## Known limitations

- The Product Agent's MCP tool discovery can fail on networks with TLS-inspecting corporate proxies
  (`CERTIFICATE_VERIFY_FAILED`). The agent degrades gracefully and responds without tool results rather
  than crashing — see [ARCHITECTURE.md](ARCHITECTURE.md#known-limitation).
- Redis is optional; without a `redis_client`, `RedisMemory` transparently falls back to an in-memory,
  per-process cache (conversation history will not survive a restart).

## Security notes

- No secrets are hardcoded or committed — all credentials live in Azure Key Vault, retrieved via
  `DefaultAzureCredential` at runtime.
- Key Vault uses RBAC authorization (not access policies); the Bicep template grants only the minimum
  roles needed (`Key Vault Secrets User`, `Cognitive Services OpenAI User`).
- `.env` and any file containing real endpoints/keys are gitignored — copy [.env.example](.env.example)
  and fill in your own values locally.
- Every user message and assistant reply passes through Content Safety before being processed or displayed.

## License

[MIT](LICENSE) © 2026 Praveen Rondla