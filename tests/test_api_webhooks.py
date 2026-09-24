"""Integration tests for FastAPI alert webhook ingestion and Slack action routes."""

import json
import time
import pytest
from httpx import AsyncClient, ASGITransport
from incidentops.api.app import app
from incidentops.agents.approval_gate import generate_slack_hmac_signature
from incidentops.config import settings


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "HEALTHY"
        assert "primary_model" in data


@pytest.mark.asyncio
async def test_alert_webhook_prometheus_ingestion():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "alerts": [
                {
                    "labels": {
                        "alertname": "ConnectionPoolExhausted",
                        "service": "order-service-api",
                        "severity": "critical",
                        "namespace": "production"
                    },
                    "annotations": {
                        "description": "450 err/sec on order checkout"
                    }
                }
            ]
        }
        resp = await client.post("/api/v1/alerts/webhook", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "INCIDENT_TRIAGED_AWAITING_APPROVAL"
        assert data["service_name"] == "order-service-api"
        assert "thread_id" in data
        assert "root_cause_analysis" in data
        assert "proposed_remediation" in data


@pytest.mark.asyncio
async def test_simulate_incident_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/incidents/simulate",
            json={"scenario": "db_pool_exhaustion"}
        )
        assert resp.status_code == 200
        data = resp.json()
        thread_id = data["thread_id"]
        assert thread_id.startswith("inc-")
        assert "root_cause_analysis" in data

        # Direct approval
        app_resp = await client.post(
            f"/api/v1/incidents/{thread_id}/approval",
            json={"approved": True, "notes": "Approved by senior SRE"}
        )
        assert app_resp.status_code == 200
        app_data = app_resp.json()
        assert app_data["status"] == "REMEDIATION_EXECUTED_SUCCESSFULLY"


@pytest.mark.asyncio
async def test_slack_interactive_action_with_valid_hmac():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First trigger an incident to get thread_id
        sim_resp = await client.post(
            "/api/v1/incidents/simulate",
            json={"scenario": "oom_killed"}
        )
        thread_id = sim_resp.json()["thread_id"]

        # Prepare Slack payload
        slack_payload = {
            "type": "block_actions",
            "actions": [
                {
                    "action_id": "approve_remediation",
                    "value": f"approve:{thread_id}"
                }
            ]
        }
        body_str = f"payload={json.dumps(slack_payload)}"
        timestamp = str(int(time.time()))
        signature = generate_slack_hmac_signature(
            body=body_str,
            timestamp=timestamp,
            signing_secret=settings.slack_signing_secret
        )

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Signature": signature,
            "X-Slack-Request-Timestamp": timestamp
        }

        resp = await client.post("/api/v1/slack/actions", content=body_str, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "Remediation update" in data["text"]
        assert data["response_type"] == "in_channel"
