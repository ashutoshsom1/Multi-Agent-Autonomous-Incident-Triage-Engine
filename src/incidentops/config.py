"""Enterprise configuration manager for IncidentOps AI."""

import os
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Environment & Application
    app_name: str = "IncidentOps AI - Autonomous Incident Triage Engine"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = True
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # LLM Settings
    llm_provider: Literal["anthropic", "gemini", "openai", "mock"] = "anthropic"
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    primary_model: str = "claude-3-5-sonnet-20241022"
    fallback_model: str = "gemini-2.5-flash"

    # FSM & Loop Bounds
    max_iteration_guard: int = 3

    # Slack HITL & HMAC Verification
    slack_signing_secret: str = Field(
        default="incidentops-dev-secret-key-hmac-sha256-signature",
        alias="SLACK_SIGNING_SECRET"
    )
    slack_bot_token: str = Field(default="", alias="SLACK_BOT_TOKEN")
    slack_channel: str = "#incidents-critical"
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")

    # Checkpoint Persistence
    postgres_uri: str = Field(default="", alias="POSTGRES_DB_URI")
    enable_postgres_checkpointer: bool = False

    # Observability & MCP Providers
    prometheus_url: str = "http://localhost:9090"
    loki_url: str = "http://localhost:3100"
    elasticsearch_url: str = "http://localhost:9200"
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    k8s_namespace_default: str = "production"

    # Simulation / Mock Mode
    use_mock_mcp: bool = True


settings = Settings()
