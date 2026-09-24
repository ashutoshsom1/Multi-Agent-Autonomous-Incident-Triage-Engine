"""Pytest fixtures for IncidentOps AI tests."""

import pytest
from incidentops.config import settings
from incidentops.models.alert import AlertPayload


@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure test settings are active."""
    settings.app_env = "test"
    settings.use_mock_mcp = True
    settings.llm_provider = "mock"


@pytest.fixture
def sample_alert() -> AlertPayload:
    return AlertPayload(
        alert_id="test-alert-001",
        service_name="order-service-api",
        environment="production",
        severity="CRITICAL",
        description="HighHttp5xxErrorRate: 450 err/sec on /v2/orders/checkout",
        labels={"namespace": "production", "cluster": "prod-us-east-1"}
    )
