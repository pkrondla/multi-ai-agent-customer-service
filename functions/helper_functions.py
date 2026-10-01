# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

import tiktoken


def count_tokens(text, model="gpt-4o"):
    """Count tokens using tiktoken. Different models use different tokenizers."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback encoding for GPT-4.1-Mini family
        encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text))
