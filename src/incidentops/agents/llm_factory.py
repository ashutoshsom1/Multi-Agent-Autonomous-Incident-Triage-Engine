"""LLM Factory supporting Claude 3.5 Sonnet, Local Ollama Models, and Mock providers with structured JSON parsing."""

import json
import os
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel

from incidentops.config import settings
from incidentops.telemetry import logger

T = TypeVar("T", bound=BaseModel)


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Extract JSON object from markdown code fence, raw LLM output, or thinking-model stream."""
    text = text.strip()

    # 1. Strip reasoning model thinking tags (e.g. <think>...</think> from Qwen, DeepSeek)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # 2. Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Try extracting markdown fence ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 4. Try finding outermost matching braces { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse valid JSON from LLM output: {text[:200]}...")


class LLMEngine:
    """Enterprise LLM orchestration client supporting Local Ollama and Anthropic Claude."""

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

    async def _call_ollama(
        self,
        system_prompt: str,
        user_message: str,
        timeout: Optional[float] = None
    ) -> str:
        """Execute chat completion against local Ollama instance with structured JSON enforcement."""
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        req_timeout = timeout or float(settings.ollama_timeout_seconds)

        sys_content = (
            f"{system_prompt}\n\n"
            "CRITICAL: Output ONLY a single valid JSON object strictly matching the schema above. "
            "Do not include conversational preamble, thinking tags, or explanation."
        )

        payload = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": sys_content},
                {"role": "user", "content": user_message}
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0
            }
        }

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    async def generate_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        mock_fallback: Optional[Dict[str, Any]] = None
    ) -> T:
        """Generate structured output adhering strictly to the response_model Pydantic schema."""
        provider = settings.llm_provider

        # 1. Local Ollama Provider (for local testing without Anthropic API keys)
        if provider == "ollama":
            try:
                logger.info(
                    f"Invoking local Ollama model [{settings.ollama_model}] at {settings.ollama_base_url}"
                )
                raw_text = await self._call_ollama(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    timeout=settings.ollama_timeout_seconds
                )
                parsed_dict = extract_json_from_text(raw_text)
                return response_model.model_validate(parsed_dict)
            except Exception as e:
                err_detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                logger.warning(
                    f"Ollama inference error or timeout ({err_detail}). Utilizing high-fidelity scenario fallback."
                )
                if mock_fallback is not None:
                    return response_model.model_validate(mock_fallback)
                raise e

        # 2. Anthropic Claude 3.5 Sonnet Provider
        if provider == "anthropic" and self._client is not None:
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
                logger.warning(f"Claude API error ({e}). Utilizing fallback.")
                if mock_fallback is not None:
                    return response_model.model_validate(mock_fallback)
                raise e

        # 3. Deterministic Mock Fallback (for unit tests / offline execution)
        if mock_fallback is not None:
            return response_model.model_validate(mock_fallback)

        raise RuntimeError(
            f"Configured provider '{provider}' is not available and no fallback provided."
        )


llm_engine = LLMEngine()
