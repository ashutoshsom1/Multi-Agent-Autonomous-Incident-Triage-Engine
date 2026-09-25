"""Unit and integration tests for local Ollama LLM provider."""

import pytest
from pydantic import BaseModel
from incidentops.config import settings
from incidentops.agents.llm_factory import extract_json_from_text, llm_engine


class DummySchema(BaseModel):
    message: str
    status: str


def test_extract_json_with_thinking_tags():
    raw_output = """
    <think>
    The user wants an incident report.
    Let me construct the JSON carefully.
    </think>
    ```json
    {
      "message": "Outage detected in order-service",
      "status": "CRITICAL"
    }
    ```
    """
    parsed = extract_json_from_text(raw_output)
    assert parsed["message"] == "Outage detected in order-service"
    assert parsed["status"] == "CRITICAL"


def test_extract_json_raw_braces():
    raw_output = 'Some preamble: {"message": "All good", "status": "HEALTHY"} and postscript'
    parsed = extract_json_from_text(raw_output)
    assert parsed["message"] == "All good"
    assert parsed["status"] == "HEALTHY"


@pytest.mark.asyncio
async def test_ollama_provider_fallback_resilience():
    # Set provider to ollama pointing to non-existent endpoint
    original_provider = settings.llm_provider
    original_url = settings.ollama_base_url
    settings.llm_provider = "ollama"
    settings.ollama_base_url = "http://127.0.0.1:9999"  # invalid port

    mock_fallback = {
        "message": "Fallback test message",
        "status": "FALLBACK_OK"
    }

    try:
        result = await llm_engine.generate_structured(
            system_prompt="Test system prompt",
            user_message="Test user message",
            response_model=DummySchema,
            mock_fallback=mock_fallback
        )
        assert result.message == "Fallback test message"
        assert result.status == "FALLBACK_OK"
    finally:
        settings.llm_provider = original_provider
        settings.ollama_base_url = original_url
