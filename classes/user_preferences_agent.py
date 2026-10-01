import json


class UserPreferencesAgent:
    def __init__(self, openai_client, model_deployment_name, redis_memory, config):
        self.openai_client = openai_client
        self.model_deployment_name = model_deployment_name
        self.redis_memory = redis_memory
        self.max_tokens = config["slm"]["max_tokens"]
        self.temperature = config["slm"]["temperature"]
        self.top_p = config["slm"]["top_p"]

    def process_message(
        self,
        current_preferences,
        session_id,
    ):
        conversation_history = self.redis_memory.load_conversation(session_id)

        system_instruction = self._get_system_instruction()

        # Remove the first message from the history, as that is the prior system instructions
        conversation_history = conversation_history[1:]

        messages = [{"role": "system", "content": system_instruction}]
        messages.extend(conversation_history)

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model_deployment_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            assistant_reply = response.choices[0].message.content
        except Exception as error:
            print(f"ERROR: LLM call failed: {error}")
            return f"I encountered an error: {error}"

        user_preferences = self._post_process_reply_into_preferences(
            assistant_reply, current_preferences
        )

        return user_preferences

    def _get_system_instruction(self):
        system_instruction = """ 
        You are designed to determine the user's preferences based on their conversation messages and interactions.

        The final formt we need the response to be in is a JSON object, with the following format:
        {
            "language": "example",
            "language_preference": "example",
            "email_address": "example@hotmail.com,
        }

        Do not include any other information in the response, just the JSON object with those three fields.
        language should be the user's preferred language for communication.
        language_preference should be either "professional" or "casual" depending on the user's tone and style in the conversation.
        email_address should be the user's email address if it can be determined from the conversation, otherwise it should be null.
        """
        return system_instruction

    def _post_process_reply_into_preferences(self, reply, current_preferences):

        # Simple normalization: convert Python-style None to JSON null and single quotes to double
        reply = reply.strip().replace("None", "null").replace("'", '"')

        try:
            new_preferences = json.loads(reply)
        except Exception:
            return current_preferences

        if not isinstance(new_preferences, dict):
            return current_preferences

        return new_preferences
