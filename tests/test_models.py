"""Unit tests for Pydantic models, schemas, and alert normalizers."""

from incidentops.models.alert import AlertPayload
from incidentops.models.supervisor import SupervisorPlan, TaskDispatch
from incidentops.models.logs import LogDiagnosticResult
from incidentops.models.metrics import MetricsCorrelationResult, TelemetryEvidence
from incidentops.models.code import CodebaseInspectionResult
from incidentops.models.rca import (
    IncidentTriageReport,
    RootCauseAnalysis,
    ProposedRemediation,
    SlackBlockKitCard
)


def test_prometheus_alert_normalizer():
    payload = {
        "alerts": [
            {
                "labels": {
                    "alertname": "HighLatency",
                    "service": "checkout-service",
                    "severity": "critical",
                    "environment": "production"
                },
                "annotations": {
                    "description": "P99 latency > 2s for 5m"
                },
                "startsAt": "2026-09-24T12:00:00Z"
            }
        ]
    }
    alert = AlertPayload.from_prometheus_alertmanager(payload)
    assert alert.alert_id == "HighLatency"
    assert alert.service_name == "checkout-service"
    assert alert.severity == "CRITICAL"
    assert alert.environment == "production"
    assert "latency" in alert.description.lower()


def test_datadog_alert_normalizer():
    payload = {
        "id": 12345,
        "title": "Database CPU Saturation",
        "event_type": "error",
        "tags": ["env:production", "service:postgres-primary"],
        "body": "Host CPU > 95%",
        "date": "2026-09-24T12:00:00Z"
    }
    alert = AlertPayload.from_datadog(payload)
    assert alert.alert_id == "12345"
    assert alert.service_name == "postgres-primary"
    assert alert.severity == "CRITICAL"
    assert alert.environment == "production"


def test_pagerduty_alert_normalizer():
    payload = {
        "event": {
            "occurred_at": "2026-09-24T12:00:00Z",
            "data": {
                "id": "PD-999",
                "urgency": "high",
                "title": "Payment API Gateway Timeout",
                "service": {"summary": "payment-api"}
            }
        }
    }
    alert = AlertPayload.from_pagerduty(payload)
    assert alert.alert_id == "PD-999"
    assert alert.service_name == "payment-api"
    assert alert.severity == "CRITICAL"


def test_supervisor_plan_schema():
    plan = SupervisorPlan(
        incident_summary="Test outage",
        affected_component="order-api (prod)",
        suspected_fault_domains=["APPLICATION_CODE"],
        tasks_to_dispatch=[
            TaskDispatch(agent="log_analyzer", instruction="Search error logs", priority=1),
            TaskDispatch(agent="metrics_correlator", instruction="Inspect CPU/Mem", priority=1),
            TaskDispatch(agent="codebase_inspector", instruction="Check PR diffs", priority=2),
        ],
        iteration_increment=1,
        should_terminate_to_synthesis=False
    )
    assert len(plan.tasks_to_dispatch) == 3
    assert plan.should_terminate_to_synthesis is False


def test_rca_and_slack_card_generation():
    rca = RootCauseAnalysis(
        title="DB connection pool starvation",
        confidence_percentage=95,
        primary_fault_domain="APPLICATION_CODE",
        chain_of_events=["PR #412 merged", "Traffic burst", "Pool exhausted"]
    )
    rem = ProposedRemediation(
        action_type="REVERT_DEPLOYMENT",
        command_or_script="kubectl rollout undo deployment/order-api",
        expected_recovery_time_seconds=30,
        blast_radius="Zero data loss",
        rollback_plan="Re-apply image"
    )
    card = SlackBlockKitCard(
        headline="P1 Root Cause Isolated",
        confidence_badge="95% Confident",
        evidence_summary="DB pool exhausted",
        action_button_label="Approve Rollback",
        reject_button_label="Reject"
    )
    report = IncidentTriageReport(
        root_cause_analysis=rca,
        proposed_remediation=rem,
        slack_block_kit_card=card
    )
    blocks = card.to_slack_blocks("inc-123")
    assert len(blocks) >= 4
    assert blocks[0]["type"] == "header"
    assert blocks[3]["type"] == "divider"
    assert "approve:inc-123" in blocks[4]["elements"][0]["value"]
