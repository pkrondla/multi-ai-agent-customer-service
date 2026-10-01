import json
from datetime import datetime


class RedisMemory:
    """
    Manages short-term session memory using Redis.
    Stores conversation history with TTL expiration.
    """

    def __init__(self, redis_client, config):
        self.redis_client = redis_client
        self.ttl_seconds = config["redis"]["session_ttl_seconds"]
        self.max_messages_in_history = config["redis"]["max_messages_in_history"]
        self.in_memory_cache = {}  # Fallback when Redis is unavailable

    def _get_key(self, session_id, key_type):
        """Generate a Redis key for a session."""
        return f"session:{session_id}:{key_type}"

    def save_conversation(self, session_id, messages):
        """Save conversation messages to memory (keeps last N messages)."""
        # Removing tool calls is due to rate limit bugs and JSON serialization bugs.
        # In the future a more elegant solution should be implemented, that retains the tool calls.
        messages = self._remove_tool_calls(messages)

        trimmed_messages = messages[-self.max_messages_in_history :]
        data = json.dumps(trimmed_messages)

        if self.redis_client:
            key = self._get_key(session_id, "messages")
            self.redis_client.setex(key, self.ttl_seconds, data)
        else:
            self.in_memory_cache[self._get_key(session_id, "messages")] = {
                "data": data,
                "expires_at": datetime.now().timestamp() + self.ttl_seconds,
            }

    def _remove_tool_calls(self, messages):

        # The following code removes the tool calls from the conversation history before saving it to Redis.
        normalized = []
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content")
                role = msg.get("role")
            else:
                content = getattr(msg, "content", None)
                role = getattr(msg, "role", None)

            # Some ChatCompletionMessage wrappers may store content in an inner object
            if content is not None and not isinstance(content, str):
                inner = getattr(content, "content", None) or getattr(
                    content, "text", None
                )
                if isinstance(inner, str):
                    content = inner

            if not content:
                continue

            normalized.append({"role": role or "user", "content": content})

        messages = normalized
        messages = [msg for msg in messages if msg["role"] != "tool"]
        # Finished removing the tool calls from the conversation history.

        return messages

    def load_conversation(self, session_id):
        """Load conversation messages from memory."""
        if self.redis_client:
            key = self._get_key(session_id, "messages")
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return []
        else:
            key = self._get_key(session_id, "messages")
            cached = self.in_memory_cache.get(key)
            if cached and cached["expires_at"] > datetime.now().timestamp():
                return json.loads(cached["data"])
            return []

    def refresh_ttl(self, session_id):
        """Refresh expiration time for all session data."""
        if self.redis_client:
            for key_type in ["messages"]:
                key = self._get_key(session_id, key_type)
                self.redis_client.expire(key, self.ttl_seconds)

    def clear_session(self, session_id):
        """Clear all data for a session."""
        if self.redis_client:
            for key_type in ["messages"]:
                key = self._get_key(session_id, key_type)
                self.redis_client.delete(key)
        else:
            for key_type in ["messages"]:
                key = self._get_key(session_id, key_type)
                self.in_memory_cache.pop(key, None)
