"""
Multi-Agent Customer Service System — Production-Ready Architecture

KEY CAPABILITIES:
1. Azure Key Vault — Securely store and manage secrets, keys, and certificates; integrated with managed identities to avoid hardcoded credentials.
2. Content Safety — Integrated content safety checks before processing user inputs and responses.
3. Azure AI Clients & Multimodel Capability — Integrates Vision, Speech, Document Intelligence, Text Analytics, and Azure OpenAI clients; supports selecting and using multiple model endpoints for multimodal workflows.
4. NLP Preprocessing — Standardized preprocessing pipeline for text (tokenization, normalization, stopword handling).
5. Cosmos DB Long-Term Memory — Loads and saves user profiles via `CosmosMemory` and is injected before agent invocation for context-aware responses.
6. SLM Memory Updates — Short-lived model (SLM) flow to update long-term memory after agent responses.
7. Redis Local Cache Mode — Redis integration implemented with a local-cache fallback (no external Redis connection required).
8. Conversational Loop — Continuous conversation loop enabling multi-turn agent interactions.
9. Manager & Support Agents — Manager agent plus support agent for orchestration and external integrations.
10. MCP Servers — Agents can call MCP servers as tools; MCP server URLs and API keys are configurable via environment variables and `config.yaml`, enabling external tool integrations and remote task execution.
"""

import os
import yaml

from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.vision.imageanalysis import ImageAnalysisClient
import azure.cognitiveservices.speech as speechsdk
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from azure.keyvault.secrets import SecretClient
from azure.cosmos import CosmosClient

from functions.helper_functions import count_tokens
from classes.content_safety import ContentSafety
from classes.azure_ai_services import AzureAIService
from classes.azure_nlp_services import AzureNLPService
from classes.secret_manager import SecretManager
from classes.cosmos_memory import CosmosMemory
from classes.redis_memory import RedisMemory
from classes.refund_agent import RefundAgent
from classes.product_agent import ProductAgent
from classes.manager_agent import ManagerAgent
from classes.user_preferences_agent import UserPreferencesAgent

# =============================================================================
# CONFIGURATION
# =============================================================================

key_vault_url = os.getenv("KEY_VAULT_URL")
user_name = os.getenv("USER_NAME")
user_role = os.getenv("USER_ROLE")
region = os.getenv("REGION")
mcp_server_url = os.getenv("MCP_SERVER_URL")
mcp_api_key = os.getenv("MCP_API_KEY")

with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

# =============================================================================
# AUTHENTICATION
# =============================================================================

credential = DefaultAzureCredential()
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
secret_manager = SecretManager(secret_client)

token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
openai_client = OpenAI(
    base_url=secret_manager.get_secret("AZURE-OPENAI-ENDPOINT"), api_key=token_provider
)
content_safety_client = ContentSafetyClient(
    endpoint=secret_manager.get_secret("CONTENT-SAFETY-ENDPOINT"), credential=credential
)
vision_client = ImageAnalysisClient(
    endpoint=secret_manager.get_secret("VISION-ENDPOINT"),
    credential=AzureKeyCredential(secret_manager.get_secret("VISION-KEY")),
)
speech_config_client = speechsdk.SpeechConfig(
    subscription=secret_manager.get_secret("SPEECH-KEY"), region=region
)
doc_intel_client = DocumentIntelligenceClient(
    endpoint=secret_manager.get_secret("DOC-INTEL-ENDPOINT"),
    credential=AzureKeyCredential(secret_manager.get_secret("DOC-INTEL-KEY")),
)
language_client = TextAnalyticsClient(
    endpoint=secret_manager.get_secret("LANGUAGE-ENDPOINT"),
    credential=AzureKeyCredential(secret_manager.get_secret("LANGUAGE-KEY")),
)
cosmos_db_client = CosmosClient(
    url=secret_manager.get_secret("COSMOSDB-ENDPOINT"),
    credential=secret_manager.get_secret("COSMOSDB-PRIMARY-KEY"),
)
database_client = cosmos_db_client.get_database_client(
    secret_manager.get_secret("COSMOSDB-DATABASE-NAME")
)
if database_client.read():
    print("Successfully connected to Cosmos DB database")
container_client = database_client.get_container_client(
    secret_manager.get_secret("COSMOSDB-CONTAINER-NAME")
)
if container_client.read():
    print("Successfully connected to Cosmos DB container")

# =============================================================================
# INSTANTIATE CLASSES
# =============================================================================

# Instantiate ContentSafety class
content_safety = ContentSafety(content_safety_client, config)

# Instantiate AzureAIService class
azure_ai_service = AzureAIService(
    vision_client=vision_client,
    speech_config=speech_config_client,
    doc_intel_client=doc_intel_client,
)

# Instantiate AzureNLPService class
azure_nlp_service = AzureNLPService(language_client=language_client, config=config)

# Instantiate CosmosMemory class
cosmos_memory = CosmosMemory(
    cosmos_client=cosmos_db_client,
    database_client=database_client,
    container_client=container_client,
    config=config,
)

# Instantiate RedisMemory class
redis_memory = RedisMemory(redis_client=None, config=config)  # No Redis in this unit

# Instantiate RefundAgent class
refund_agent = RefundAgent(
    openai_client=openai_client,
    model_deployment_name=secret_manager.get_secret("LLM-MODEL-DEPLOYMENT-NAME"),
    redis_memory=redis_memory,
    user_name=user_name,
    user_role=user_role,
    config=config,
)

# Instantiate ProductAgent class
product_agent = ProductAgent(
    openai_client=openai_client,
    model_deployment_name=secret_manager.get_secret("LLM-MODEL-DEPLOYMENT-NAME"),
    redis_memory=redis_memory,
    user_name=user_name,
    user_role=user_role,
    mcp_server_url=mcp_server_url,
    mcp_api_key=mcp_api_key,
    config=config,
)

# Instantiate ManagerAgent class
manager_agent = ManagerAgent(
    openai_client=openai_client,
    model_deployment_name=secret_manager.get_secret("LLM-MODEL-DEPLOYMENT-NAME"),
    refund_agent=refund_agent,
    product_agent=product_agent,
    user_name=user_name,
    user_role=user_role,
    config=config,
)

# Instantiate UserPreferencesAgent class
user_preferences_agent = UserPreferencesAgent(
    openai_client=openai_client,
    model_deployment_name=secret_manager.get_secret("SLM-MODEL-DEPLOYMENT-NAME"),
    redis_memory=redis_memory,
    config=config,
)

# =============================================================================
# MAIN SCRIPT LOGIC
# =============================================================================

session_id = "session_12346"  # In a real application, this would be dynamically generated per user session


def interactive_loop():
    print("Interactive mode started. Type 'exit' or 'quit' to stop.")
    message_count = 0
    while True:
        try:
            user_message_text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive mode.")
            break

        if not user_message_text:
            continue
        if user_message_text.lower() in ("exit", "quit"):
            print("Exiting interactive mode.")
            break

        # Input filtering
        print("\n[INPUT FILTER] Scanning user message...")
        if not content_safety.is_text_safe(user_message_text):
            print("User message blocked by Content Safety.")
            continue
        print("User message passed safety check.")

        # For the first message include a fixed multimodal artifact (image); skip later messages
        if message_count == 0:
            print(
                "\n[AZURE NLP SERVICE] Preprocessing user input with Azure AI Language (multimodal)..."
            )
            azure_ai_service_response = azure_ai_service.route_multimodal_request(
                content_type="jpeg", content_path="inputs/broken_tv.jpeg"
            )
            print(f"\nAzure AI Service response: {azure_ai_service_response}")
        else:
            azure_ai_service_response = None

        azure_nlp_service_response = azure_nlp_service.preprocess_user_input(
            user_message_text
        )

        # Replace original user message with redacted and tagged version for the agent to process
        user_message_for_agent = azure_nlp_service_response.get(
            "tagged", user_message_text
        )
        print(
            f"Preprocessed user message (with sensitive info redacted and entities tagged): {user_message_for_agent}"
        )

        # Get user preferences from Cosmos DB
        print("\n[LONG-TERM MEMORY] Retrieving user preferences from Cosmos DB...")
        user_preferences = cosmos_memory.get_user_or_default_profile(user_id=user_name)
        print(f"\nUser preferences: {user_preferences}")

        # Process with ManagerAgent
        print("\n[MANAGER AGENT] Processing message with agent...")
        reply = manager_agent.process_message(
            user_message=user_message_for_agent,
            user_preferences=user_preferences,
            azure_ai_service_response=azure_ai_service_response,
            azure_nlp_service_response=azure_nlp_service_response,
            session_id=session_id,
        )

        # Check if we got a valid response
        if reply is None:
            print("ERROR: Failed to get response from model.")
            continue

        # Output filtering
        print("\n[OUTPUT FILTER] Scanning assistant response...")
        if not content_safety.is_text_safe(reply):
            print("Assistant response blocked by Content Safety.")
            print(f"Returning safe default message: '{config['safe_responce']}'")
            print("\n" + "=" * 50)
            print("ASSISTANT REPLY (SAFE DEFAULT):")
            print("=" * 50)
            print(config["safe_responce"])
            print("=" * 50)
        else:
            print("Assistant response passed safety check.")
            print("\n" + "=" * 50)
            print("ASSISTANT REPLY:")
            print("=" * 50)
            print(reply)
            print("=" * 50)

        message_count += 1

    # Update user preferences via UserPreferencesAgent and save to Cosmos
    print(
        "\n[USER PREFERENCES AGENT] Processing conversation history to extract user preferences..."
    )
    user_preferences_reply = user_preferences_agent.process_message(
        current_preferences=user_preferences,
        session_id=session_id,
    )
    print(f"\nUser Preferences Agent reply: {user_preferences_reply}")

    print("\n[LONG-TERM MEMORY] Saving updated user preferences to Cosmos DB...")
    cosmos_memory.save_user_profile(
        user_id=user_name, preferences=user_preferences_reply
    )
    print("\nUser preferences updated in Cosmos DB.")


if __name__ == "__main__":
    interactive_loop()

# =============================================================================
# SYSTEM OVERVIEW
# =============================================================================
# This is a production-ready, secure, multimodal agent system with
# long-term memory, safety checks, caching strategies, and external tool integrations.

# 1. Azure Key Vault — Securely store and manage secrets, keys, and certificates; integrated with managed identities to avoid hardcoded credentials.
# 2. Content Safety — Integrated content safety checks before processing user inputs and responses.
# 3. Azure AI Clients & Multimodel Capability — Integrates Vision, Speech, Document Intelligence, Text Analytics, and Azure OpenAI clients; supports selecting and using multiple model endpoints for multimodal workflows.
# 4. NLP Preprocessing — Standardized preprocessing pipeline for text (tokenization, normalization, stopword handling).
# 5. Cosmos DB Long-Term Memory — Loads and saves user profiles via `CosmosMemory` and is injected before agent invocation for context-aware responses.
# 6. SLM Memory Updates — Short-lived model (SLM) flow to update long-term memory after agent responses.
# 7. Redis Local Cache Mode — Redis integration implemented with a local-cache fallback (no external Redis connection required).
# 8. Conversational Loop — Continuous conversation loop enabling multi-turn agent interactions.
# 9. Manager & Support Agents — Manager agent plus support agent for orchestration and external integrations.
# 10. MCP Servers — Agents can call MCP servers as tools; MCP server URLs and API keys are configurable via environment variables and `config.yaml`, enabling external tool integrations and remote task execution.
