import json
import os

from fastapi import HTTPException, status

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - optional dependency
    genai = None
    types = None


class AIService:
    def __init__(self):
        self.client = None
        self.model = "gemini-2.5-flash"

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return

        if genai is None or types is None:
            return

        self.client = genai.Client(api_key=api_key)

    def analyze_interaction(self, content: str, interaction_type: str) -> dict:
        """
        Sends raw interaction text to Gemini and forces a structured JSON response
        containing targeted 'Next Best Actions' along with confidence metrics and reasons.
        """
        
        # System instructions to configure the behavior, reasoning constraints, and baseline expectations
        system_instruction = (
            "You are the Core Business Reasoning and Decision Intelligence Engine of an enterprise platform. "
            "Your job is to analyze customer interactions (like transcripts or emails) and determine the absolute "
            "Next Best Actions. For each action, provide an exact confidence score (0.0 to 100.0) and an explicit, "
            "evidence-based reason explaining your conclusion. Do not write a chatbot response; provide "
            "clear, actionable operational recommendations."
        )

        prompt = f"""
        Analyze the following customer interaction and generate a list of appropriate Next Best Actions.
        
        Interaction Type: {interaction_type}
        Raw Content:
        \"\"\"{content}\"\"\"
        """

        if self.client is None or types is None:
            return self._fallback_analysis(content, interaction_type)

        try:
            response_schema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "recommendations": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "action": types.Schema(type=types.Type.STRING, description="The specific, clear next action item."),
                                "confidence": types.Schema(type=types.Type.NUMBER, description="Percentage score from 0.0 to 100.0 representing certainty."),
                                "reason": types.Schema(type=types.Type.STRING, description="Detailed analysis and evidence behind why this action is recommended.")
                            },
                            required=["action", "confidence", "reason"],
                        ),
                    )
                },
                required=["recommendations"],
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.2,
                ),
            )

            return json.loads(response.text)

        except Exception as e:
            return self._fallback_analysis(content, interaction_type, str(e))

    def _fallback_analysis(self, content: str, interaction_type: str, error: str | None = None) -> dict:
        summary = (content or "").strip() or "No content provided"
        action = "Follow up with the customer"
        if "cancel" in summary.lower() or "refund" in summary.lower():
            action = "Offer a resolution and refund review"
        elif "complaint" in summary.lower() or "issue" in summary.lower():
            action = "Escalate the issue and confirm next steps"

        return {
            "recommendations": [
                {
                    "action": action,
                    "confidence": 82.0,
                    "reason": "Fallback analysis generated this recommendation because the AI service is unavailable.",
                }
            ],
            "meta": {
                "interaction_type": interaction_type,
                "fallback": True,
                "error": error,
            },
        }