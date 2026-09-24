"""FastAPI Application Entrypoint for IncidentOps AI."""

from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from incidentops.config import settings
from incidentops.api.routes_alert import router as alert_router
from incidentops.api.routes_slack import router as slack_router
from incidentops.api.routes_incident import router as incident_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup log
    print(f"🚀 {settings.app_name} initialized in {settings.app_env} mode.")
    print(f"🤖 LLM Provider: {settings.llm_provider} (Model: {settings.primary_model})")
    print(f"⚡ Mock MCP Telemetry: {settings.use_mock_mcp}")
    yield
    print("🛑 Shutting down IncidentOps AI.")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="Autonomous Enterprise SRE Incident Response Engine with LangGraph & MCP",
        version="0.1.0",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API Routers
    app.include_router(alert_router)
    app.include_router(slack_router)
    app.include_router(incident_router)

    @app.get("/health", tags=["Health"])
    async def health_check() -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "primary_model": settings.primary_model,
            "mock_mcp_enabled": settings.use_mock_mcp,
            "max_iteration_guard": settings.max_iteration_guard
        }

    return app


app = create_app()
