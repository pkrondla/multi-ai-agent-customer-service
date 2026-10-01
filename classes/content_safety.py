# =============================================================================
# CONTENT SAFETY CLASS
# =============================================================================

from azure.ai.contentsafety.models import AnalyzeTextOptions


class ContentSafety:
    def __init__(self, content_safety_client, config):
        self.content_safety_client = content_safety_client
        self.severity_threshold = config["content_safety"]["severity_threshold"]

    def is_text_safe(self, text_to_check):
        """
        Scan text for harmful content using Azure AI Content Safety.
        Returns True if safe (below threshold for all categories).
        Returns False if any category exceeds the threshold.

        The four categories Content Safety checks:
        1. HATE: Attacks based on race, religion, gender identity, etc.
        2. SEXUAL: Explicit sexual content or references
        3. VIOLENCE: Threats, descriptions of harm, or glorification of violence
        4. SELF_HARM: Content related to self-injury or suicide
        """
        analysis_request = AnalyzeTextOptions(text=text_to_check)
        analysis_result = self.content_safety_client.analyze_text(analysis_request)

        categories_result = analysis_result["categoriesAnalysis"]
        hate_severity = next(
            (c["severity"] for c in categories_result if c["category"] == "Hate"), None
        )
        sexual_severity = next(
            (c["severity"] for c in categories_result if c["category"] == "Sexual"),
            None,
        )
        violence_severity = next(
            (c["severity"] for c in categories_result if c["category"] == "Violence"),
            None,
        )
        self_harm_severity = next(
            (c["severity"] for c in categories_result if c["category"] == "SelfHarm"),
            None,
        )

        # Check each category against the severity threshold
        if hate_severity > self.severity_threshold:
            print(f"Blocked: HATE content (severity {hate_severity})")
            return False

        if sexual_severity > self.severity_threshold:
            print(f"Blocked: SEXUAL content (severity {sexual_severity})")
            return False

        if violence_severity > self.severity_threshold:
            print(f"Blocked: VIOLENCE content (severity {violence_severity})")
            return False

        if self_harm_severity > self.severity_threshold:
            print(f"Blocked: SELF_HARM content (severity {self_harm_severity})")
            return False

        return True
