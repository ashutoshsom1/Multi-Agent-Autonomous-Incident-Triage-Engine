"""Unit tests for structured logging and Prometheus metrics exporter."""

import json
import logging
from incidentops.telemetry import JSONFormatter, PrometheusMetricsRegistry


def test_json_formatter_structure():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="incidentops.test",
        level=logging.ERROR,
        pathname="test_path.py",
        lineno=42,
        msg="Test error event",
        args=(),
        exc_info=None
    )
    record.incident_id = "inc-9821"
    record.worker = "log_analyzer"
    record.duration_ms = 450.5

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "ERROR"
    assert parsed["message"] == "Test error event"
    assert parsed["incident_id"] == "inc-9821"
    assert parsed["worker"] == "log_analyzer"
    assert parsed["duration_ms"] == 450.5


def test_prometheus_metrics_registry():
    reg = PrometheusMetricsRegistry()
    reg.record_incident("CRITICAL", "AWAITING_APPROVAL")
    reg.record_triage_duration(1.45)
    reg.record_worker_execution("supervisor", 0.32)
    reg.record_worker_execution("log_analyzer", 0.65)
    reg.record_mcp_call("mcp__loki_search", "success")
    reg.record_remediation("REVERT_DEPLOYMENT", "SUCCESS")

    exported = reg.export()

    assert "incidentops_incidents_total" in exported
    assert 'severity="CRITICAL",status="AWAITING_APPROVAL"' in exported
    assert "incidentops_triage_duration_seconds_sum" in exported
    assert 'incidentops_worker_duration_seconds_sum{worker="log_analyzer"}' in exported
    assert 'incidentops_mcp_tool_calls_total{tool="mcp__loki_search",status="success"}' in exported
    assert 'incidentops_remediations_total{action_type="REVERT_DEPLOYMENT",status="SUCCESS"}' in exported
