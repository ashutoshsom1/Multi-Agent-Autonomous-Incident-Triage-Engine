"""FastAPI Application Entrypoint for IncidentOps AI.

Enterprise hardened with API Key authentication, Prometheus metrics exporter,
structured logging, and Kubernetes liveness/readiness probes.
"""

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader

from incidentops.config import settings
from incidentops.telemetry import configure_logging, logger, metrics
from incidentops.api.routes_alert import router as alert_router
from incidentops.api.routes_slack import router as slack_router
from incidentops.api.routes_incident import router as incident_router

# Security Schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    bearer_auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
):
    """Enforce API Key or Bearer Token authentication in production/staging environments."""
    if not settings.enforce_auth and settings.app_env in ("development", "test"):
        return True

    configured_key = settings.api_key
    if not configured_key:
        return True

    # Check X-API-Key header
    if header_key and header_key == configured_key:
        return True

    # Check Bearer token
    if bearer_auth and bearer_auth.credentials == configured_key:
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Missing or invalid API Key / Bearer token.",
        headers={"WWW-Authenticate": "Bearer"}
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize structured JSON logging
    configure_logging()
    logger.info(
        f"IncidentOps AI engine started in [{settings.app_env}] environment",
        extra={"worker": "system"}
    )
    logger.info(
        f"Primary model: {settings.primary_model} | MCP Mock mode: {settings.use_mock_mcp}",
        extra={"worker": "system"}
    )
    yield
    logger.info("IncidentOps AI engine gracefully shutting down.", extra={"worker": "system"})


def create_app() -> FastAPI:
    """Create and configure production FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="Autonomous Enterprise SRE Incident Response Engine with LangGraph & MCP",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "production" or settings.debug else None,
        redoc_url="/redoc" if settings.app_env != "production" or settings.debug else None,
    )

    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware: Request timing
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        response = await call_next(request)
        return response

    # Include API Routers with security dependencies
    app.include_router(alert_router, dependencies=[Depends(verify_api_key)])
    app.include_router(incident_router, dependencies=[Depends(verify_api_key)])
    app.include_router(slack_router)  # Slack uses HMAC signature verification

    # =========================================================================
    # Observability & Health Endpoints
    # =========================================================================

    @app.get("/health", tags=["Health"])
    async def health_check() -> Dict[str, Any]:
        """General health check endpoint."""
        return {
            "status": "HEALTHY",
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "primary_model": settings.primary_model,
            "mock_mcp_enabled": settings.use_mock_mcp,
            "max_iteration_guard": settings.max_iteration_guard
        }

    @app.get("/health/liveness", tags=["Health"])
    async def liveness_probe() -> Dict[str, Any]:
        """Kubernetes liveness probe: verifies process responsiveness."""
        return {
            "status": "UP",
            "app": settings.app_name,
            "env": settings.app_env
        }

    @app.get("/health/readiness", tags=["Health"])
    async def readiness_probe() -> Dict[str, Any]:
        """Kubernetes readiness probe: verifies database and MCP backend readiness."""
        db_ready = True
        if settings.enable_postgres_checkpointer and settings.postgres_uri:
            try:
                import psycopg
                with psycopg.connect(settings.postgres_uri, connect_timeout=3) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
            except Exception:
                db_ready = False

        status_str = "READY" if db_ready else "DEGRADED"
        return {
            "status": status_str,
            "postgres_checkpointer": "connected" if db_ready else "disconnected",
            "mock_mcp": settings.use_mock_mcp,
            "llm_provider": settings.llm_provider,
            "model": settings.primary_model
        }

    @app.get("/metrics", tags=["Observability"])
    async def prometheus_metrics() -> Response:
        """Prometheus metrics endpoint for scraping."""
        return Response(content=metrics.export(), media_type="text/plain")

    return app


app = create_app()
