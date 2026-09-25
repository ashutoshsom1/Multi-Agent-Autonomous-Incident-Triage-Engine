"""Unit & integration tests for production security, auth guards, and health probes."""

import pytest
from httpx import AsyncClient, ASGITransport
from incidentops.api.app import app
from incidentops.config import settings


@pytest.mark.asyncio
async def test_liveness_and_readiness_probes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Liveness
        live_resp = await client.get("/health/liveness")
        assert live_resp.status_code == 200
        assert live_resp.json()["status"] == "UP"

        # Readiness
        ready_resp = await client.get("/health/readiness")
        assert ready_resp.status_code == 200
        data = ready_resp.json()
        assert data["status"] in ("READY", "DEGRADED")
        assert "postgres_checkpointer" in data


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert "incidentops_incidents_total" in resp.text


@pytest.mark.asyncio
async def test_api_key_authentication_enforcement():
    # Temporarily enforce authentication
    original_enforce = settings.enforce_auth
    original_key = settings.api_key
    settings.enforce_auth = True
    settings.api_key = "test-secret-api-key-999"

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Unauthenticated request should be rejected with 401
            unauth_resp = await client.post(
                "/api/v1/incidents/simulate",
                json={"scenario": "db_pool_exhaustion"}
            )
            assert unauth_resp.status_code == 401
            assert "Unauthorized" in unauth_resp.json()["detail"]

            # 2. Authenticated via X-API-Key header should succeed
            auth_header_resp = await client.post(
                "/api/v1/incidents/simulate",
                json={"scenario": "db_pool_exhaustion"},
                headers={"X-API-Key": "test-secret-api-key-999"}
            )
            assert auth_header_resp.status_code == 200
            assert "thread_id" in auth_header_resp.json()

            # 3. Authenticated via Bearer token should succeed
            auth_bearer_resp = await client.post(
                "/api/v1/incidents/simulate",
                json={"scenario": "db_pool_exhaustion"},
                headers={"Authorization": "Bearer test-secret-api-key-999"}
            )
            assert auth_bearer_resp.status_code == 200
    finally:
        # Restore configuration
        settings.enforce_auth = original_enforce
        settings.api_key = original_key
