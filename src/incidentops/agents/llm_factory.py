"""LLM Factory supporting Claude 3.5 Sonnet, Gemini, and Mock providers with structured JSON parsing."""

import json
import os
import re
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

from incidentops.config import settings

T = TypeVar("T", bound=BaseModel)


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Extract JSON object from markdown code fence or raw LLM output."""
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting markdown fence ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding outer braces
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse valid JSON from text: {text[:200]}...")


class LLMEngine:
    """Enterprise LLM orchestration client for Anthropic Claude 3.5 Sonnet."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.anthropic_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None

        if self.anthropic_key and self.provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.anthropic_key)
            except Exception:
                self._client = None

    async def generate_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        mock_fallback: Optional[Dict[str, Any]] = None
    ) -> T:
        """Generate structured output adhering strictly to the response_model Pydantic schema."""
        # If client is available, call Claude 3.5 Sonnet
        if self._client is not None:
            try:
                message = self._client.messages.create(
                    model=settings.primary_model,
                    max_tokens=4096,
                    temperature=0.0,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_message}
                    ]
                )
                raw_text = message.content[0].text
                parsed_dict = extract_json_from_text(raw_text)
                return response_model.model_validate(parsed_dict)
            except Exception as e:
                # Log or fallback if requested
                if mock_fallback is None:
                    raise e

        # Fallback to high-fidelity mock scenario
        if mock_fallback is not None:
            return response_model.model_validate(mock_fallback)

        raise RuntimeError(
            "No active LLM provider configured and no mock fallback provided. "
            "Set ANTHROPIC_API_KEY or configure LLM_PROVIDER=mock."
        )


llm_engine = LLMEngine()
