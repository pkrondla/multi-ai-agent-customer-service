# =============================================================================
# MANAGER AGENT
# =============================================================================
# The manager agent receives all user messages, identifies intent, and delegates
# to the appropriate sub-agent. It never answers directly - its only job is routing.

import json


class ManagerAgent:
    """
    The Manager (Magentic) pattern agent.
    Receives user requests and delegates to specialized sub-agents.
    Does not answer questions directly - only routes and synthesizes responses.
    """

    def __init__(
        self,
        openai_client,
        model_deployment_name,
        refund_agent,
        product_agent,
        user_name,
        user_role,
        config,
    ):
        self.openai_client = openai_client
        self.model_deployment_name = model_deployment_name
        self.refund_agent = refund_agent
        self.product_agent = product_agent
        self.user_name = user_name
        self.user_role = user_role
        self.max_tokens = config["llm"]["max_tokens"]
        self.temperature = config["llm"]["temperature"]
        self.top_p = config["llm"]["top_p"]

    def get_system_instruction(self):
        """Build the system instruction for the manager agent."""
        return f"""
        [PERSONA]
        You are a Manager Agent for Contoso Corporation.
        You coordinate between specialist agents. You do NOT answer questions directly.

        [BOUNDARIES - CRITICAL]
        1. NEVER answer user questions directly. ALWAYS delegate to a specialist.
        2. You have two specialists: RefundAgent and ProductAgent
        3. Your only job is to identify which specialist should handle the request.

        [HANDOFF RULES]
        - Use delegate_to_refund when user asks about: refund, return money, reimbursement
        - Use delegate_to_product when user asks about: product features, specifications, searching the internet for product info

        [RESPONSE FORMAT]
        After receiving the specialist's response, present it to the user exactly as given.
        Do not modify or summarize the specialist's answer.

        You are helping user: {self.user_name} who has the role of {self.user_role}.
        """

    def delegate_to_refund(
        self,
        user_message,
        user_preferences,
        azure_ai_service_response,
        azure_nlp_service_response,
        session_id,
    ):
        """Delegate a refund request to the RefundAgent."""
        print("[MANAGER] Delegating to RefundAgent")
        return self.refund_agent.process_message(
            user_message,
            user_preferences,
            azure_ai_service_response,
            azure_nlp_service_response,
            session_id,
        )

    def delegate_to_product(
        self,
        user_message,
        user_preferences,
        azure_ai_service_response,
        azure_nlp_service_response,
        session_id,
    ):
        """Delegate a product question to the ProductAgent."""
        print("[MANAGER] Delegating to ProductAgent")
        return self.product_agent.process_message(
            user_message,
            user_preferences,
            azure_ai_service_response,
            azure_nlp_service_response,
            session_id,
        )

    def process_message(
        self,
        user_message,
        user_preferences,
        azure_ai_service_response,
        azure_nlp_service_response,
        session_id,
    ):
        """
        Process a user message by:
        1. Classifying the intent (which specialist is needed)
        2. Delegating to the appropriate specialist
        3. Returning the specialist's response
        """
        # Build delegation tools for the manager LLM
        delegation_tools = [
            {
                "type": "function",
                "function": {
                    "name": "delegate_to_refund",
                    "description": "Send request to Refund Agent for refunds or returns",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_message": {
                                "type": "string",
                                "description": "The user's original request",
                            }
                        },
                        "required": ["user_message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "delegate_to_product",
                    "description": "Send request to Product Agent for product questions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_message": {
                                "type": "string",
                                "description": "The user's original request",
                            }
                        },
                        "required": ["user_message"],
                    },
                },
            },
        ]

        # Build system instruction and messages
        system_instruction = self.get_system_instruction()
        system_message = {"role": "system", "content": system_instruction}
        messages = [system_message, {"role": "user", "content": user_message}]

        # Call LLM to determine which specialist should handle the request
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model_deployment_name,
                messages=messages,
                tools=delegation_tools,
                tool_choice="auto",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
        except Exception as error:
            print(f"ERROR: ManagerAgent call failed: {error}")
            return "I encountered an error processing your request."

        assistant_message = response.choices[0].message

        # Check which tool the manager wants to call
        if assistant_message.tool_calls:
            tool_call = assistant_message.tool_calls[0]
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            user_message_text = arguments.get("user_message", user_message)

            # Route to the appropriate specialist
            if tool_name == "delegate_to_refund":
                specialist_response = self.delegate_to_refund(
                    user_message_text,
                    user_preferences,
                    azure_ai_service_response,
                    azure_nlp_service_response,
                    session_id,
                )
            elif tool_name == "delegate_to_product":
                specialist_response = self.delegate_to_product(
                    user_message_text,
                    user_preferences,
                    azure_ai_service_response,
                    azure_nlp_service_response,
                    session_id,
                )
            else:
                specialist_response = (
                    "I cannot determine which specialist can help with your request."
                )

            return specialist_response

        # No tool call - manager couldn't determine intent
        return (
            "I'm not sure which specialist can help with that. "
            "Please ask about refunds or products"
        )
